import io
import os
import sys
from pathlib import Path

# Force UTF-8 stdout if possible on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from pdf_reader import read_pdf
from ppt_reader import read_ppt
from explainer import explain_slide_content, generate_fallback_explanation, TEACHER_PROMPT
from tts_engine import (
    tts_service,
    _ensure_valid_audio,
    _pcm_to_wav,
    EdgeTTSProvider,
    GeminiTTSProvider,
    ElevenLabsTTSProvider
)
from text_cleaner import clean_text_for_speech, split_text_into_chunks


def test_pdf_extraction():
    """Verify PDF extraction and slide page numbering."""
    sample_pdf = Path("documents/sample.pdf")
    if sample_pdf.exists():
        slides = read_pdf(str(sample_pdf))
        assert len(slides) > 0, "PDF slides should be extracted"
        assert slides[0]["number"] == 1, "First slide should be number 1"
        assert "text" in slides[0], "Slide must contain text key"
        assert "is_empty" in slides[0], "Slide must contain is_empty flag"
        print(f"[PASS] PDF Extraction: Successfully extracted {len(slides)} slides from {sample_pdf.name}")
    else:
        print("[WARN] documents/sample.pdf not found.")


def test_pptx_extraction():
    """Create a temporary small PPTX in memory to test PPTX extraction and empty slide detection."""
    from pptx import Presentation
    prs = Presentation()
    slide_layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "Introduction to Operating Systems"
    content_box = slide.placeholders[1]
    content_box.text = "Process Management:\n- Context switching overhead\n- Scheduling algorithms"

    # Add an empty slide to test empty slide handling
    empty_layout = prs.slide_layouts[6]
    prs.slides.add_slide(empty_layout)

    test_pptx_path = Path("documents/temp_test.pptx")
    test_pptx_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(test_pptx_path))

    try:
        slides = read_ppt(str(test_pptx_path))
        assert len(slides) == 2, f"Expected 2 slides, got {len(slides)}"
        assert not slides[0]["is_empty"], "Slide 1 should not be empty"
        assert slides[1]["is_empty"], "Slide 2 should be marked empty"
        assert "Process Management" in slides[0]["text"]
        print("[PASS] PPTX Extraction & Empty Slide Handling verified.")
    finally:
        if test_pptx_path.exists():
            test_pptx_path.unlink()


def test_text_normalization():
    """Verify Markdown removal, Big-O preservation, abbreviations, and list transitions."""
    raw = (
        "# Unit 3: Database Indexing\n"
        "**Key Concept**: B-Tree vs Hash indexing.\n"
        "* Hash index lookup is O(1) constant time w/ O(N) worst-case.\n"
        "* e.g. see Fig. 2 for 99% hit rate & latency approx. 2ms."
    )
    cleaned = clean_text_for_speech(raw)
    assert "#" not in cleaned, "Markdown headers should be stripped"
    assert "**" not in cleaned, "Bold markdown should be stripped"
    assert "versus" in cleaned, "'vs' should be normalized to 'versus'"
    assert "for example" in cleaned, "'e.g.' should be normalized to 'for example'"
    assert "percent" in cleaned, "'%' should be normalized to 'percent'"
    assert "figure 2" in cleaned, "'Fig. 2' should be normalized to 'figure 2'"
    assert "First," in cleaned, "First bullet point should have a natural spoken transition"
    print("[PASS] Text Normalization & Natural Speech Punctuation verified.")

    # Test chunking helper
    long_text = ". ".join([f"This is educational sentence number {i} with valuable facts" for i in range(25)]) + "."
    chunks = split_text_into_chunks(long_text, max_chars=400)
    assert len(chunks) > 1, "Should split long text into multiple chunks"
    for c in chunks:
        assert len(c) <= 450, f"Chunk exceeded size: {len(c)}"
        assert c.strip().endswith("."), "Chunks must break cleanly at sentence ends"
    print("[PASS] Sentence-boundary Chunking verified.")


def test_explanation_pedagogy():
    """Verify teaching style prompt, fallback structure, and explanation caching."""
    # 1. Verify prompt contains required female teacher persona instructions
    assert "friendly, knowledgeable female teacher" in TEACHER_PROMPT
    assert "clear Indian English" in TEACHER_PROMPT
    assert "conversational sentences" in TEACHER_PROMPT

    # 2. Test fallback generation follows the 7-step pedagogical structure
    sample_content = (
        "REST APIs & HTTP Methods\n"
        "- GET retrieves resources safely without side-effects\n"
        "- POST creates new records in the database\n"
        "- PUT updates existing entities idempotently"
    )
    fallback_exp = generate_fallback_explanation(sample_content, slide_number=2)
    assert "slide 2" in fallback_exp.lower()
    assert "REST APIs" in fallback_exp
    assert "think of this like" in fallback_exp.lower() or "analogy" in fallback_exp.lower() or "real-world" in fallback_exp.lower()
    assert "recap" in fallback_exp.lower()
    print("[PASS] Female Educator Explanation & Fallback Generation verified.")

    # 3. Test in-memory explanation caching
    exp1 = explain_slide_content(sample_content, slide_number=2)
    exp2 = explain_slide_content(sample_content, slide_number=2)
    assert exp1 == exp2, "Cached explanation should return identical result"
    print("[PASS] In-Memory Explanation Cache verified.")


def test_audio_format_and_wav_packaging():
    """Verify PCM to WAV packaging and RIFF header validation."""
    dummy_pcm = b"\x00\x00" * 2400  # 100ms of silence
    wav_bytes, mime = _ensure_valid_audio(dummy_pcm, "audio/pcm;rate=24000")
    assert mime == "audio/wav", f"Expected audio/wav, got {mime}"
    assert wav_bytes[:4] == b"RIFF", "Should prepend standard RIFF header"
    assert wav_bytes[8:12] == b"WAVE", "Should contain WAVE format signature"
    print("[PASS] PCM to standard RIFF/WAV packaging verified.")


def test_modular_tts_providers():
    """Verify modular TTS structure, provider naming, and caching without requiring external network."""
    edge = EdgeTTSProvider()
    assert edge.is_available() is True
    assert "NeerjaNeural" in edge.DEFAULT_VOICE
    assert edge.name == f"Edge TTS ({edge.DEFAULT_VOICE})"
    print(f"[PASS] EdgeTTSProvider verified: {edge.name}")

    gemini = GeminiTTSProvider()
    assert gemini.DEFAULT_FEMALE_VOICE == "Aoede"
    print(f"[PASS] GeminiTTSProvider verified: {gemini.name} (Available: {gemini.is_available()})")

    elevenlabs = ElevenLabsTTSProvider()
    assert elevenlabs.name == "ElevenLabs TTS"
    assert elevenlabs.is_available() is False  # Not configured by default
    print(f"[PASS] ElevenLabsTTSProvider pluggable modular adapter verified.")

    # Test cache key calculation and bounded LRU cache operations
    key = tts_service._get_cache_key("Test sentence for audio caching.", "auto", 1.0)
    assert len(key) == 64, "Cache key should be valid 64-char sha256"

    mock_audio = b"RIFF" + b"\x00" * 32
    tts_service._add_to_cache(key, (mock_audio, "audio/wav", "Gemini TTS (Aoede)"))
    assert key in tts_service._cache
    cached_val = tts_service._cache[key]
    assert cached_val[0] == mock_audio
    assert cached_val[1] == "audio/wav"
    assert cached_val[2] == "Gemini TTS (Aoede)"
    print("[PASS] Modular TTS Engine Caching and Registry verified.")


def main():
    print("=" * 55)
    print("RUNNING AI TEACHING ASSISTANT COMPREHENSIVE TESTS")
    print("=" * 55)

    test_pdf_extraction()
    test_pptx_extraction()
    test_text_normalization()
    test_explanation_pedagogy()
    test_audio_format_and_wav_packaging()
    test_modular_tts_providers()

    print("\n" + "=" * 55)
    print("ALL CORE LOGIC & MODULAR COMPONENTS VERIFIED SUCCESSFULLY! [OK]")
    print("=" * 55)


if __name__ == "__main__":
    main()
