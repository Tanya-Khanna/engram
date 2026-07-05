"""Single Qwen client wrapper — the only module allowed to touch the API.

Routing table maps intent tiers to models; never use `deep` where `cheap`
works. Every call is metered through metrics.log_call.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Any

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, OpenAI

from engram import metrics

load_dotenv()

BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

ROUTING: dict[str, str] = {
    "vision": "qwen3.7-plus",   # cold-path browser loop
    "cheap": "qwen3.6-flash",   # verification + reverify probes
    "deep": "qwen3.7-max",      # consolidation
}

EMBEDDING_MODEL = os.getenv("ENGRAM_EMBEDDING_MODEL", "text-embedding-v4")

SESSION_ID = os.getenv("ENGRAM_SESSION_ID", uuid.uuid4().hex[:12])

_RETRY_DELAYS = (1.0, 2.0, 4.0, 8.0)

_client_instance: OpenAI | None = None


def _client() -> OpenAI:
    global _client_instance
    if _client_instance is None:
        key = os.getenv("DASHSCOPE_API_KEY")
        if not key:
            raise RuntimeError("DASHSCOPE_API_KEY is not set (see .env.example)")
        _client_instance = OpenAI(api_key=key, base_url=BASE_URL)
    return _client_instance


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, APIConnectionError):
        return True
    return isinstance(exc, APIStatusError) and (
        exc.status_code == 429 or exc.status_code >= 500
    )


def _with_retries(fn: Any) -> Any:
    for attempt, delay in enumerate((*_RETRY_DELAYS, None)):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — classified below
            if delay is None or not _retryable(exc):
                raise
            time.sleep(delay)
    raise RuntimeError("unreachable")


def complete(
    purpose: str,
    messages: list[dict[str, Any]],
    model_tier: str = "cheap",
    think: bool | None = None,
    **kwargs: Any,
) -> Any:
    """Chat completion via the routing table. Returns the raw response.

    think=False disables Qwen's reasoning mode (DashScope enable_thinking) —
    use it for verification probes where latency matters more than depth.
    """
    model = ROUTING[model_tier]
    if think is not None:
        kwargs.setdefault("extra_body", {})["enable_thinking"] = think
    start = time.monotonic()
    response = _with_retries(
        lambda: _client().chat.completions.create(
            model=model, messages=messages, **kwargs
        )
    )
    latency_ms = (time.monotonic() - start) * 1000
    usage = response.usage
    details = getattr(usage, "completion_tokens_details", None)
    metrics.log_call(
        purpose=purpose,
        model=model,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        reasoning_tokens=getattr(details, "reasoning_tokens", 0) or 0,
        latency_ms=latency_ms,
        session_id=SESSION_ID,
    )
    return response


NATIVE_BASE = "https://dashscope-intl.aliyuncs.com/api/v1"
TTS_MODEL = os.getenv("ENGRAM_TTS_MODEL", "qwen3-tts-flash")
ASR_MODEL = os.getenv("ENGRAM_ASR_MODEL", "qwen3-asr-flash")


def _native(body: dict[str, Any], purpose: str) -> dict[str, Any]:
    """DashScope-native endpoint (audio lives here, not on compatible-mode)."""
    import httpx

    start = time.monotonic()
    response = _with_retries(
        lambda: httpx.post(
            f"{NATIVE_BASE}/services/aigc/multimodal-generation/generation",
            json=body,
            headers={"Authorization": f"Bearer {os.getenv('DASHSCOPE_API_KEY')}"},
            timeout=120,
        ).raise_for_status()
    )
    payload: dict[str, Any] = response.json()
    usage = payload.get("usage", {})
    metrics.log_call(
        purpose=purpose,
        model=body["model"],
        prompt_tokens=usage.get("input_tokens", 0) or 0,
        completion_tokens=usage.get("output_tokens", 0) or 0,
        latency_ms=(time.monotonic() - start) * 1000,
        session_id=SESSION_ID,
    )
    return payload


def tts(text: str, voice: str = "Cherry") -> str:
    """Text to speech. Returns a short-lived URL to the synthesized WAV."""
    payload = _native(
        {"model": TTS_MODEL, "input": {"text": text, "voice": voice}},
        purpose="tts",
    )
    return str(payload["output"]["audio"]["url"])


def asr(audio_data_uri: str) -> str:
    """Speech to text. Takes a data URI or URL, returns the transcript."""
    payload = _native(
        {
            "model": ASR_MODEL,
            "input": {"messages": [{"role": "user", "content": [{"audio": audio_data_uri}]}]},
        },
        purpose="asr",
    )
    return str(payload["output"]["choices"][0]["message"]["content"][0]["text"])


def embed(texts: list[str], purpose: str = "embedding") -> list[list[float]]:
    """Embedding endpoint on the same client — metered like everything else."""
    start = time.monotonic()
    response = _with_retries(
        lambda: _client().embeddings.create(model=EMBEDDING_MODEL, input=texts)
    )
    latency_ms = (time.monotonic() - start) * 1000
    usage = response.usage
    metrics.log_call(
        purpose=purpose,
        model=EMBEDDING_MODEL,
        prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        completion_tokens=0,
        latency_ms=latency_ms,
        session_id=SESSION_ID,
    )
    return [item.embedding for item in response.data]
