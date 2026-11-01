import json
import os
import re
import hashlib
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# System prompt for grounded female teacher persona
TEACHER_PROMPT = """You are a knowledgeable, articulate female teacher conducting an online class. Explain the provided document section clearly, accurately, and naturally.

CRITICAL ACCURACY & GROUNDING RULES:
1. STRICT SEQUENCE: Cover every source chunk in its supplied order. Never merge, reorder, or skip chunks.
2. ACCURATE & GROUNDED: Every claim must be supported by that chunk or by an explicit relationship stated in the supplied content.
3. NO FABRICATION: Never invent facts, data, statistics, causes, or background knowledge.
4. EXAMPLES: Include an example only when the source provides one or when it is a direct restatement of the source; otherwise use an empty example.
5. FORMAT: Return valid JSON only, matching the requested schema. Do not include markdown or commentary."""


class ExplanationResponse(dict):
    """
    Dictionary response containing both 'explanation' and 'segments',
    while behaving cleanly as a string when evaluated as str(obj).
    """
    def __init__(self, explanation: str, segments: List[Dict[str, Any]]):
        super().__init__(explanation=explanation, segments=segments)
        self.explanation = explanation
        self.segments = segments

    def __str__(self) -> str:
        return self.explanation

    def __repr__(self) -> str:
        return self.explanation


# In-memory explanation cache: hash(content, slide_number) -> ExplanationResponse
_explanation_cache: Dict[str, ExplanationResponse] = {}


def _get_content_hash(content: str, slide_number: int) -> str:
    key = f"{slide_number}:{content.strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def semantic_chunks(content: str) -> List[Dict[str, Any]]:
    """Create ordered, source-addressable chunks from extracted slide text."""
    raw_lines = content.strip().splitlines()
    if not raw_lines:
        return []

    chunks = []
    for source_index, line in enumerate(raw_lines):
        text = line.strip()
        if not text:
            continue
        is_title = not chunks
        chunks.append({
            "chunk_id": f"chunk-{len(chunks) + 1}",
            "type": "title" if is_title else "body",
            "line_index": -1 if is_title else source_index - 1,
            "source_text": text,
        })
    return chunks


def align_sentences_to_items(items: List[Dict[str, Any]], sentences: List[str]) -> List[Dict[str, Any]]:
    """
    Aligns narration sentences to slide items in strict sequential order.
    Uses keyword overlap where present, falling back to monotonic proportional distribution.
    """
    k = len(items)
    m = len(sentences)
    if k == 0:
        return []
    if k == 1:
        seg = dict(items[0])
        seg["narration"] = " ".join(sentences)
        return [seg]

    # Clean words per slide item for keyword matching
    item_words = []
    for it in items:
        w = set(re.findall(r'\b[a-zA-Z]{3,}\b', it["text"].lower()))
        item_words.append(w)

    assigned = [[] for _ in range(k)]
    curr_i = 0

    for s_idx, s in enumerate(sentences):
        s_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', s.lower()))
        best_match = curr_i
        best_score = 0
        for i in range(curr_i, k):
            overlap = len(item_words[i] & s_words)
            if overlap > best_score:
                best_score = overlap
                best_match = i

        if best_score > 0:
            curr_i = best_match
            assigned[curr_i].append(s)
        else:
            prop_i = min(k - 1, (s_idx * k) // m)
            curr_i = max(curr_i, prop_i)
            assigned[curr_i].append(s)

    result = []
    for i, it in enumerate(items):
        seg = dict(it)
        seg["narration"] = " ".join(assigned[i]) if assigned[i] else it["text"]
        result.append(seg)
    return result


def segment_explanation(content: str, full_narration: str) -> List[Dict[str, Any]]:
    """
    Decomposes the slide content into title and body lines, and aligns
    the spoken narration sentences to each corresponding item.
    """
    items = [
        {
            "chunk_id": chunk["chunk_id"],
            "type": chunk["type"],
            "line_index": chunk["line_index"],
            "text": chunk["source_text"],
        }
        for chunk in semantic_chunks(content)
    ]

    if not items:
        return [{
            "chunk_id": "chunk-1",
            "type": "title",
            "line_index": -1,
            "text": "",
            "source_text": "",
            "narration": full_narration,
            "timing_weight": max(1, len(full_narration.split())),
        }]

    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', full_narration.strip()) if s.strip()]
    if not sentences:
        sentences = [full_narration]

    return align_sentences_to_items(items, sentences)


def _structured_gemini_segments(
    payload: Any,
    chunks: List[Dict[str, Any]],
) -> Optional[List[Dict[str, Any]]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("segments"), list):
        return None
    generated = payload["segments"]
    if len(generated) != len(chunks):
        return None

    segments = []
    for chunk, item in zip(chunks, generated):
        if not isinstance(item, dict):
            return None
        narration = str(item.get("narration", "")).strip()
        if not narration:
            return None
        segments.append({
            "chunk_id": chunk["chunk_id"],
            "type": chunk["type"],
            "line_index": chunk["line_index"],
            "text": chunk["source_text"],
            "source_text": chunk["source_text"],
            "concept": str(item.get("concept", "")).strip(),
            "explanation": str(item.get("explanation", "")).strip(),
            "example": str(item.get("example", "")).strip(),
            "takeaway": str(item.get("takeaway", "")).strip(),
            "narration": narration,
            "timing_weight": max(1, len(narration.split())),
        })
    return segments


def generate_fallback_explanation(content: str, slide_number: int) -> ExplanationResponse:
    """
    Document-grounded fallback explanation that strictly follows the slide's
    topic sequence without generic, unrelated, or fabricated information.
    """
    clean_content = content.strip()
    if not clean_content or "No readable text" in clean_content:
        empty_text = f"Slide {slide_number} has no readable text to narrate."
        return ExplanationResponse(empty_text, [{"type": "title", "line_index": -1, "text": "", "narration": empty_text}])

    chunks = semantic_chunks(clean_content)
    title = chunks[0]["source_text"] if chunks else f"Slide {slide_number}"
    clean_title = title.lstrip("* -•▪▫◦0123456789.):#").strip()

    segments: List[Dict[str, Any]] = []
    narration_parts: List[str] = []

    title_narration = f"Slide {slide_number}: {clean_title}."
    segments.append({
        "chunk_id": chunks[0]["chunk_id"],
        "type": "title",
        "line_index": -1,
        "text": title,
        "source_text": title,
        "concept": clean_title,
        "explanation": clean_title,
        "example": "",
        "takeaway": clean_title,
        "narration": title_narration,
        "timing_weight": len(title_narration.split()),
    })
    narration_parts.append(title_narration)

    for chunk in chunks[1:]:
        clean_p = chunk["source_text"].lstrip("* -•▪▫◦0123456789.):#").strip()
        phrase = (
            f"Let's look at {clean_p}. "
            f"This means the document is describing {clean_p}. "
            f"No separate example is provided in the document. "
            f"The key idea to remember is {clean_p}."
        )

        segments.append({
            "chunk_id": chunk["chunk_id"],
            "type": "body",
            "line_index": chunk["line_index"],
            "text": chunk["source_text"],
            "source_text": chunk["source_text"],
            "concept": clean_p,
            "explanation": clean_p,
            "example": "",
            "takeaway": clean_p,
            "narration": phrase,
            "timing_weight": len(phrase.split()),
        })
        narration_parts.append(phrase)

    recap = f"To recap, this slide introduces {clean_title} and develops the related topics in sequence."
    narration_parts.append(recap)

    full_explanation = " ".join(narration_parts)
    return ExplanationResponse(full_explanation, segments)


def explain_slide_content(content: str, slide_number: int = 1) -> ExplanationResponse:
    """
    Generates a natural, document-grounded female educator explanation
    following the exact topic sequence of the slide.
    Returns an ExplanationResponse containing both the spoken text and aligned segments.
    """
    cache_key = _get_content_hash(content, slide_number)
    if cache_key in _explanation_cache:
        return _explanation_cache[cache_key]

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not api_key:
        response_obj = generate_fallback_explanation(content, slide_number)
        _explanation_cache[cache_key] = response_obj
        return response_obj

    # Call Gemini using google-genai SDK
    try:
        from google import genai
        client = genai.Client(api_key=api_key)

        chunks = semantic_chunks(content)
        user_prompt = (
            f"Slide Number: {slide_number}\n"
            "Source chunks (ordered; each must be explained exactly once):\n"
            f"{json.dumps(chunks, ensure_ascii=False)}\n\n"
            "Return JSON with this exact shape: "
            '{"segments":[{"chunk_id":"...", "concept":"...", "explanation":"...", '
            '"example":"", "takeaway":"...", "narration":"..."}]}. '
            "For each segment, narration should sound like a natural teacher explaining the source, "
            "with a clear introduction, explanation, relevant source-supported example when available, "
            "and takeaway. Do not say 'point', 'item', or use numbered-list language. "
            "Keep example empty when the source does not support one. "
            "Be concise: keep each field under 18 words and each narration under 55 words."
        )

        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
            contents=user_prompt,
            config={
                "system_instruction": TEACHER_PROMPT,
                "temperature": 0.2,
                "max_output_tokens": 2400
            }
        )

        text = response.text.strip() if response and response.text else ""
        if text:
            parsed_text = text.strip().removeprefix("```json").removesuffix("```").strip()
            structured = _structured_gemini_segments(json.loads(parsed_text), chunks)
            if structured:
                narration = " ".join(segment["narration"] for segment in structured)
                response_obj = ExplanationResponse(narration, structured)
                _explanation_cache[cache_key] = response_obj
                return response_obj
            raise ValueError("Gemini returned incomplete or invalid source mappings.")
        else:
            response_obj = generate_fallback_explanation(content, slide_number)
            _explanation_cache[cache_key] = response_obj
            return response_obj

    except Exception as e:
        print(f"[Explainer] Gemini API notice ({e}). Using natural grounded female educator fallback.")
        response_obj = generate_fallback_explanation(content, slide_number)
        _explanation_cache[cache_key] = response_obj
        return response_obj
