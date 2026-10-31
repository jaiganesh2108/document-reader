import os
import io
import wave
import hashlib
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, List
from collections import OrderedDict
from dotenv import load_dotenv

import edge_tts
from text_cleaner import clean_text_for_speech, split_text_into_chunks

load_dotenv()


def _pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000) -> bytes:
    """
    Wraps raw 16-bit mono PCM bytes in a standard RIFF/WAV container
    so all HTML5 web browsers can decode and play it natively.
    """
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)      # Mono
        wf.setsampwidth(2)      # 16-bit PCM = 2 bytes per sample
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def _ensure_valid_audio(audio_data: bytes, reported_mime: str = "") -> Tuple[bytes, str]:
    """
    Inspects audio byte signatures and wraps PCM to WAV if needed.
    Returns (audio_bytes, mime_type).
    """
    if not audio_data:
        return audio_data, reported_mime or "audio/mpeg"

    # RIFF/WAV header signature
    if audio_data[:4] == b"RIFF" and len(audio_data) > 12 and audio_data[8:12] == b"WAVE":
        return audio_data, "audio/wav"

    # ID3 or MP3 sync frame
    if audio_data[:3] == b"ID3" or (len(audio_data) > 2 and audio_data[0] == 0xFF and (audio_data[1] & 0xE0) == 0xE0):
        return audio_data, "audio/mpeg"

    # If raw PCM or reported as audio/pcm, convert to valid WAV
    sample_rate = 24000
    if "rate=" in reported_mime:
        try:
            sample_rate = int(reported_mime.split("rate=")[1].split(";")[0].strip())
        except Exception:
            sample_rate = 24000

    wav_bytes = _pcm_to_wav(audio_data, sample_rate=sample_rate)
    return wav_bytes, "audio/wav"


class BaseTTSProvider(ABC):
    """
    Abstract base class for all TTS providers ensuring modularity
    and seamless integration of future voice engines like ElevenLabs.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    async def synthesize(self, text: str, voice: Optional[str] = None, speed: Optional[float] = 1.0) -> Tuple[bytes, str]:
        """
        Synthesizes text into audio bytes and returns (audio_bytes, mime_type).
        """
        pass


class GeminiTTSProvider(BaseTTSProvider):
    """
    Primary Option: Gemini text-to-speech utilizing Gemini's native audio modality.
    Uses warm, pedagogical female voices (Aoede or Kore) with instructional speaking guidance.
    """
    DEFAULT_FEMALE_VOICE = "Aoede"

    @property
    def name(self) -> str:
        return f"Gemini TTS ({self.DEFAULT_FEMALE_VOICE})"

    def is_available(self) -> bool:
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        return bool(key)

    async def synthesize(self, text: str, voice: Optional[str] = None, speed: Optional[float] = 1.0) -> Tuple[bytes, str]:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        # Select natural female voice: Aoede (warm, conversational) or Kore (gentle, clear)
        selected_voice = voice if voice in ["Aoede", "Kore"] else self.DEFAULT_FEMALE_VOICE
        model_name = os.getenv("GEMINI_TTS_MODEL", "gemini-2.0-flash")

        # Instruction guiding Gemini's speech delivery style
        prompt = (
            "You are a friendly, knowledgeable female teacher conducting an online class in clear Indian English. "
            "Speak naturally with clear pronunciation, comfortable teaching pauses, and engaging pacing. "
            f"Read the following classroom explanation directly:\n\n{text}"
        )

        def _call_gemini():
            config = types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=selected_voice
                        )
                    )
                ),
                temperature=0.6,
            )

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )

            if not response.candidates or not response.candidates[0].content:
                raise ValueError("No candidates returned by Gemini audio model.")

            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    mime = getattr(part.inline_data, "mime_type", "audio/wav")
                    return part.inline_data.data, mime

            raise ValueError("Gemini response did not contain inline audio data.")

        raw_bytes, raw_mime = await asyncio.to_thread(_call_gemini)
        return _ensure_valid_audio(raw_bytes, raw_mime)


class EdgeTTSProvider(BaseTTSProvider):
    """
    Fallback Option: High-quality Microsoft Edge Neural Speech.
    Default voice: en-IN-NeerjaNeural (expressive Indian English female teacher voice).
    Applies a slightly slower speaking rate for clear classroom instruction.
    """
    DEFAULT_VOICE = "en-IN-NeerjaNeural"

    @property
    def name(self) -> str:
        return f"Edge TTS ({self.DEFAULT_VOICE})"

    def is_available(self) -> bool:
        return True

    async def synthesize(self, text: str, voice: Optional[str] = None, speed: Optional[float] = 1.0) -> Tuple[bytes, str]:
        selected_voice = voice if voice and "Neural" in voice else self.DEFAULT_VOICE

        # Slightly slower speaking rate (-5% baseline for pedagogical clarity)
        base_rate = -5
        if speed and speed != 1.0:
            base_rate = int(-5 + (speed - 1.0) * 100)

        rate_str = f"{base_rate:+d}%"

        communicate = edge_tts.Communicate(
            text=text,
            voice=selected_voice,
            rate=rate_str
        )

        audio_buffer = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.extend(chunk["data"])

        if not audio_buffer:
            # Fallback to alternate expressive neural voice
            alt_voice = "en-IN-NeerjaExpressiveNeural" if selected_voice != "en-IN-NeerjaExpressiveNeural" else "en-IN-AnanyaNeural"
            communicate_alt = edge_tts.Communicate(
                text=text,
                voice=alt_voice,
                rate=rate_str
            )
            async for chunk in communicate_alt.stream():
                if chunk["type"] == "audio":
                    audio_buffer.extend(chunk["data"])

        if not audio_buffer:
            raise RuntimeError("Edge TTS returned empty audio stream.")

        return bytes(audio_buffer), "audio/mpeg"


class ElevenLabsTTSProvider(BaseTTSProvider):
    """
    Modular stub for future ElevenLabs integration without requiring any frontend changes.
    Only activates if ELEVENLABS_API_KEY is configured in the environment.
    """
    @property
    def name(self) -> str:
        return "ElevenLabs TTS"

    def is_available(self) -> bool:
        return bool(os.getenv("ELEVENLABS_API_KEY"))

    async def synthesize(self, text: str, voice: Optional[str] = None, speed: Optional[float] = 1.0) -> Tuple[bytes, str]:
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY is not configured.")

        # Modular future integration point
        raise NotImplementedError("ElevenLabs is configured as an optional modular expansion.")


class ModularTTSService:
    """
    Orchestrates text-to-speech synthesis with:
    - Primary: Gemini TTS (Aoede female voice)
    - Fallback: Edge TTS (en-IN-NeerjaNeural, slightly slower speaking rate)
    - In-memory bounded cache to prevent duplicate syntheses
    - Natural sentence chunking for long texts
    - Full modularity for future providers
    """
    MAX_CACHE_ENTRIES = 100

    def __init__(self):
        self.gemini_provider = GeminiTTSProvider()
        self.edge_provider = EdgeTTSProvider()
        self.elevenlabs_provider = ElevenLabsTTSProvider()

        # LRU cache: cache_key -> (audio_bytes, mime_type, provider_name)
        self._cache: OrderedDict[str, Tuple[bytes, str, str]] = OrderedDict()

    def _get_cache_key(self, text: str, voice: str, speed: float) -> str:
        data = f"{voice}:{speed:.2f}:{text.strip()}"
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def _add_to_cache(self, key: str, value: Tuple[bytes, str, str]):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self.MAX_CACHE_ENTRIES:
            self._cache.popitem(last=False)

    async def generate_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = 1.0
    ) -> Tuple[bytes, str, str, bool]:
        """
        Synthesizes speech from educational text.
        Returns: (audio_bytes, mime_type, provider_name, is_cached)
        """
        cleaned_text = clean_text_for_speech(text)
        if not cleaned_text:
            raise ValueError("No readable text provided for speech synthesis.")

        chosen_voice = voice or "auto"
        effective_speed = speed if speed else 1.0

        cache_key = self._get_cache_key(cleaned_text, chosen_voice, effective_speed)

        # 1. Check in-memory cache
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            audio_bytes, mime_type, provider = self._cache[cache_key]
            return audio_bytes, mime_type, provider, True

        audio_bytes = None
        mime_type = "audio/mpeg"
        used_provider = None

        # Check if caller specifically requested Edge TTS voice (e.g. en-IN-NeerjaNeural)
        is_edge_specific = bool(voice and "Neural" in voice)

        # 2. Try Gemini TTS if not specifically asked for Edge TTS
        if not is_edge_specific and self.gemini_provider.is_available():
            try:
                gemini_voice = voice if voice in ["Aoede", "Kore"] else GeminiTTSProvider.DEFAULT_FEMALE_VOICE
                audio_bytes, mime_type = await self.gemini_provider.synthesize(
                    cleaned_text, voice=gemini_voice, speed=effective_speed
                )
                used_provider = f"Gemini TTS ({gemini_voice})"
            except Exception as e:
                print(f"[TTS] Gemini TTS unavailable ({e}). Seamlessly falling back to Edge TTS ({EdgeTTSProvider.DEFAULT_VOICE}).")

        # 3. Fallback to Edge TTS (en-IN-NeerjaNeural)
        if not audio_bytes:
            edge_voice = voice if is_edge_specific else EdgeTTSProvider.DEFAULT_VOICE
            try:
                audio_bytes, mime_type = await self.edge_provider.synthesize(
                    cleaned_text, voice=edge_voice, speed=effective_speed
                )
                used_provider = f"Edge TTS ({edge_voice})"
            except Exception as e:
                print(f"[TTS] Edge TTS error: {e}")
                raise RuntimeError(f"Speech synthesis failed: {e}")

        # Store in cache
        self._add_to_cache(cache_key, (audio_bytes, mime_type, used_provider))
        return audio_bytes, mime_type, used_provider, False


# Global singleton instance
tts_service = ModularTTSService()
