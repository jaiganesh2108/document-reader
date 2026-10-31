import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi.testclient import TestClient
from main import app
from tts_engine import tts_service

client = TestClient(app)


def test_api():
    print("==========================================")
    print("TESTING FASTAPI ENDPOINTS & CACHING")
    print("==========================================")

    # 1. Health check
    res_health = client.get("/api/health")
    assert res_health.status_code == 200, f"Health check failed: {res_health.status_code}"
    health_data = res_health.json()
    assert health_data["status"] == "online"
    assert "primary_tts" in health_data
    assert "tts_fallback" in health_data
    print(f"[PASS] /api/health -> {health_data}")

    # 2. Upload invalid file format
    res_bad_upload = client.post(
        "/api/upload",
        files={"file": ("test.txt", b"plain text", "text/plain")}
    )
    assert res_bad_upload.status_code == 400, "Should reject non-pdf/pptx files"
    print("[PASS] /api/upload rejection of unsupported format (400) verified.")

    # 3. Upload empty file
    res_empty_upload = client.post(
        "/api/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")}
    )
    assert res_empty_upload.status_code == 400, "Should reject empty files"
    print("[PASS] /api/upload rejection of 0-byte file (400) verified.")

    # 4. Upload sample.pdf
    sample_pdf_path = Path("documents/sample.pdf")
    if sample_pdf_path.exists():
        with open(sample_pdf_path, "rb") as f:
            pdf_bytes = f.read()

        res_upload = client.post(
            "/api/upload",
            files={"file": ("sample.pdf", pdf_bytes, "application/pdf")}
        )
        assert res_upload.status_code == 200, f"Upload failed: {res_upload.text}"
        data = res_upload.json()
        assert data["total_slides"] > 0
        file_id = data["file_id"]
        print(f"[PASS] /api/upload -> Extracted {data['total_slides']} slides, file_id={file_id}")

        # Test upload caching: second upload of identical bytes should return cached: True
        res_upload_cached = client.post(
            "/api/upload",
            files={"file": ("sample.pdf", pdf_bytes, "application/pdf")}
        )
        assert res_upload_cached.status_code == 200
        cached_upload_data = res_upload_cached.json()
        assert cached_upload_data["cached"] is True
        assert cached_upload_data["file_id"] == file_id
        print(f"[PASS] /api/upload Document Caching verified (instant response without re-parsing).")

        slide_content = data["slides"][0]["content"]

        # 5. Explain slide
        res_explain = client.post(
            "/api/explain",
            json={"slide_number": 1, "content": slide_content, "file_id": file_id}
        )
        assert res_explain.status_code == 200, f"Explain failed: {res_explain.text}"
        exp_data = res_explain.json()
        assert "explanation" in exp_data
        assert len(exp_data["explanation"]) > 20
        print(f"[PASS] /api/explain -> Explanation: {exp_data['explanation'][:80]}...")

        # Test empty content explanation error
        res_explain_empty = client.post(
            "/api/explain",
            json={"slide_number": 1, "content": "   "}
        )
        assert res_explain_empty.status_code == 400
        print("[PASS] /api/explain validation of empty content (400) verified.")

        # 6. Test /api/speech validation
        res_speech_empty = client.post(
            "/api/speech",
            json={"text": ""}
        )
        assert res_speech_empty.status_code == 400
        print("[PASS] /api/speech validation of empty text (400) verified.")

        # 7. Test /api/speech caching and headers
        test_speech_text = "Good morning students, today we are exploring data structures."
        cache_key = tts_service._get_cache_key(test_speech_text, "auto", 1.0)
        mock_audio = b"RIFF" + b"\x00" * 36
        tts_service._add_to_cache(cache_key, (mock_audio, "audio/wav", "Gemini TTS (Aoede)"))

        res_speech = client.post(
            "/api/speech",
            json={"text": test_speech_text}
        )
        assert res_speech.status_code == 200
        assert res_speech.headers.get("x-tts-provider") == "Gemini TTS (Aoede)"
        assert res_speech.headers.get("x-audio-cached") == "true"
        assert res_speech.content == mock_audio
        print(f"[PASS] /api/speech Caching & Audio Headers verified: X-TTS-Provider={res_speech.headers.get('x-tts-provider')}")

    print("\n" + "=" * 42)
    print("ALL FASTAPI ENDPOINT TESTS PASSED! [OK]")
    print("=" * 42)


if __name__ == "__main__":
    test_api()
