"""Voice in: qwen3-asr-flash via the single llm wrapper."""
from __future__ import annotations

import base64

from engram import llm


def transcribe(audio: bytes, mime: str = "audio/webm") -> str:
    """Transcribe recorded audio bytes (browser MediaRecorder output)."""
    data_uri = f"data:{mime};base64,{base64.b64encode(audio).decode()}"
    return llm.asr(data_uri)
