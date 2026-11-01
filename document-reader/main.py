import os
import sys
import tempfile
import hashlib
from pathlib import Path
from typing import Optional, List, Dict

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from pdf_reader import read_pdf
from ppt_reader import read_ppt
from speech_engine import SpeechEngine
from text_cleaner import clean_text_for_speech
from explainer import explain_slide_content
from tts_engine import tts_service, EdgeTTSProvider

load_dotenv()

# Maximum allowed file upload size: 25 MB
MAX_FILE_SIZE = 25 * 1024 * 1024

# In-memory document cache to avoid repeated file extraction
# file_id -> {"filename": str, "slides": List[Dict]}
document_cache: Dict[str, Dict] = {}

# FastAPI application initialization
app = FastAPI(
    title="AI Teaching Assistant API",
    description="Backend API for PDF/PPTX slide extraction, natural female teacher explanations, and speech synthesis.",
    version="2.0.0"
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-TTS-Provider", "X-Audio-Cached"]
)


# Pydantic Request Models
class ExplainRequest(BaseModel):
    slide_number: int
    content: str
    file_id: Optional[str] = None


class SpeechRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    speed: Optional[float] = 1.0


def _compute_file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


@app.get("/api/health")
async def health_check():
    """
    Returns server status, configured Gemini API key presence, and active default voice.
    """
    has_gemini = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    return {
        "status": "online",
        "gemini_configured": has_gemini,
        "primary_tts": "Gemini TTS (Aoede - Female)",
        "tts_fallback": f"Edge TTS {EdgeTTSProvider.DEFAULT_VOICE} (Indian English Female)",
        "default_voice": EdgeTTSProvider.DEFAULT_VOICE,
        "cached_documents": len(document_cache)
    }


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Uploads a PDF or PPTX document, extracts content slide-by-slide,
    and caches the extracted structure once per upload.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    extension = Path(file.filename).suffix.lower()
    if extension not in [".pdf", ".pptx"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{extension}'. Please upload a PDF or PowerPoint (.pptx) file."
        )

    # Read file content safely with size check
    content_bytes = await file.read()
    if len(content_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum allowed size of 25MB (size: {len(content_bytes)/(1024*1024):.1f}MB)."
        )

    if len(content_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    file_id = _compute_file_hash(content_bytes)

    # Return cached extraction if already processed
    if file_id in document_cache:
        cached = document_cache[file_id]
        return {
            "file_id": file_id,
            "filename": cached["filename"],
            "total_slides": len(cached["slides"]),
            "slides": cached["slides"],
            "cached": True
        }

    # Write to a temporary file for reader extraction
    temp_dir = tempfile.gettempdir()
    temp_path = Path(temp_dir) / f"{file_id}{extension}"

    try:
        with open(temp_path, "wb") as f:
            f.write(content_bytes)

        if extension == ".pdf":
            sections = read_pdf(str(temp_path))
        else:
            sections = read_ppt(str(temp_path))

        if not sections:
            raise HTTPException(
                status_code=400,
                detail="Unable to extract any slides or pages from the document."
            )

        slides_data = [
            {
                "slide_number": sec["number"],
                "content": sec["text"],
                "is_empty": sec.get("is_empty", False)
            }
            for sec in sections
        ]

        document_cache[file_id] = {
            "filename": file.filename,
            "slides": slides_data
        }

        return {
            "file_id": file_id,
            "filename": file.filename,
            "total_slides": len(slides_data),
            "slides": slides_data,
            "cached": False
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting document text: {str(e)}")
    finally:
        # Safe cleanup of temporary file
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass


@app.post("/api/explain")
async def explain_slide(req: ExplainRequest):
    """
    Generates a natural, conversational female teacher explanation for the specified slide.
    Reuses cached explanation if content has not changed.
    """
    content = req.content
    if req.file_id:
        document = document_cache.get(req.file_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Uploaded document was not found in the document cache.")

        cached_slide = next(
            (slide for slide in document["slides"] if slide["slide_number"] == req.slide_number),
            None,
        )
        if cached_slide is None:
            raise HTTPException(
                status_code=404,
                detail=f"Slide {req.slide_number} was not found in the uploaded document.",
            )
        content = cached_slide["content"]

    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="Slide content cannot be empty.")

    try:
        res = explain_slide_content(
            content=content,
            slide_number=req.slide_number
        )
        explanation = res.get("explanation", str(res)) if isinstance(res, dict) else str(res)
        segments = res.get("segments", []) if isinstance(res, dict) else []

        return {
            "slide_number": req.slide_number,
            "explanation": explanation,
            "segments": segments
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Explanation generation failed: {str(e)}")


@app.post("/api/speech")
async def generate_speech(req: SpeechRequest):
    """
    Converts educational explanation into realistic female teacher speech audio (MP3/WAV).
    Uses Gemini TTS (primary) or Edge TTS en-IN-NeerjaNeural (fallback).
    Reuses cached audio for identical narration and voice settings.
    """
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Text for speech synthesis cannot be empty.")

    try:
        audio_bytes, mime_type, provider, is_cached = await tts_service.generate_speech(
            text=req.text,
            voice=req.voice,
            speed=req.speed or 1.0
        )

        ext = "wav" if "wav" in mime_type else "mp3"
        return Response(
            content=audio_bytes,
            media_type=mime_type,
            headers={
                "X-TTS-Provider": provider,
                "X-Audio-Cached": str(is_cached).lower(),
                "Content-Disposition": f"inline; filename=explanation.{ext}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice synthesis failed: {str(e)}")


# ==========================================
# CLI Fallback Implementation (Preserved)
# ==========================================

def load_document(file_path):
    extension = Path(file_path).suffix.lower()
    if extension == ".pdf":
        return read_pdf(file_path)
    elif extension == ".pptx":
        return read_ppt(file_path)
    else:
        raise ValueError("Unsupported file. Use PDF or PPTX.")


def run_cli():
    print("=" * 45)
    print("       AI VIRTUAL TEACHER")
    print("       Document Voice Reader (CLI)")
    print("=" * 45)

    file_path = input("\nEnter PDF or PPTX file path: ").strip().strip('"')
    if not Path(file_path).is_file():
        print("File not found!")
        return

    try:
        sections = load_document(file_path)
    except Exception as error:
        print(f"Unable to read document: {error}")
        return

    if not sections:
        print("No readable text found.")
        return

    print(f"\nLoaded {len(sections)} text sections.")
    teacher = SpeechEngine()

    print("\nStarting lesson...\n")
    for section in sections:
        number = section["number"]
        content = section["text"]

        print(f"\n{'=' * 45}")
        print(f"PAGE / SLIDE {number}")
        print(f"{'=' * 45}")
        print(content)

        print("\nGenerating AI Educator Explanation...")
        explanation = explain_slide_content(content, number)
        print(f"\n[Teacher Explanation]:\n{explanation}\n")

        try:
            teacher.speak(f"Let's look at section {number}.")
            teacher.speak(explanation)
        except KeyboardInterrupt:
            teacher.stop()
            print("\nReading interrupted.")
            return

        choice = input("\nEnter = Next | r = Repeat | q = Quit: ").strip().lower()
        if choice == "q":
            break
        if choice == "r":
            teacher.speak(explanation)

    teacher.stop()
    print("\nLesson finished!")


if __name__ == "__main__":
    if "--server" in sys.argv:
        import uvicorn
        port = int(os.getenv("PORT", "8000"))
        print(f"Starting AI Teaching Assistant FastAPI server on http://localhost:{port}...")
        uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
    else:
        run_cli()
