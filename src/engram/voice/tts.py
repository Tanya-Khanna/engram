"""Voice out: qwen3-tts-flash via the single llm wrapper.

CosyVoice needs a websocket session; the Qwen TTS model does the same job
over one request, so rung 1 ships with it.
"""
from __future__ import annotations

import urllib.request

from engram import llm


def speak(text: str, voice: str = "Cherry") -> bytes:
    """Synthesize text, return WAV bytes ready to stream to the browser."""
    url = llm.tts(text, voice=voice)
    with urllib.request.urlopen(url, timeout=60) as response:
        return bytes(response.read())
