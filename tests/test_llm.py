"""llm.py: routing, retry, and metrics logging — with the OpenAI client mocked."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from openai import APIStatusError

from engram import llm, metrics


def _response(prompt_tokens: int = 10, completion_tokens: int = 5):
    return SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            completion_tokens_details=SimpleNamespace(reasoning_tokens=3),
        ),
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
    )


def _rate_limit_error() -> APIStatusError:
    request = httpx.Request("POST", "http://test")
    response = httpx.Response(429, request=request)
    return APIStatusError("rate limited", response=response, body=None)


@pytest.fixture
def fake_client(monkeypatch):
    client = MagicMock()
    client.chat.completions.create.return_value = _response()
    monkeypatch.setattr(llm, "_client", lambda: client)
    return client


@pytest.mark.parametrize(
    ("tier", "expected_model"),
    [("vision", "qwen3.7-plus"), ("cheap", "qwen3.6-flash"), ("deep", "qwen3.7-max")],
)
def test_routing(fake_client, tier, expected_model):
    llm.complete("test", [{"role": "user", "content": "hi"}], model_tier=tier)
    assert fake_client.chat.completions.create.call_args.kwargs["model"] == expected_model


def test_unknown_tier_rejected(fake_client):
    with pytest.raises(KeyError):
        llm.complete("test", [], model_tier="giant")


def test_metrics_logged(fake_client):
    llm.complete("unit-test", [{"role": "user", "content": "hi"}])
    jsonl = metrics.data_dir() / "metrics.jsonl"
    record = json.loads(jsonl.read_text().splitlines()[-1])
    assert record["purpose"] == "unit-test"
    assert record["model"] == "qwen3.6-flash"
    assert record["prompt_tokens"] == 10
    assert record["reasoning_tokens"] == 3
    assert metrics.summary()[0]["calls"] == 1


def test_retry_on_429(fake_client, monkeypatch):
    monkeypatch.setattr(llm, "_RETRY_DELAYS", (0.0, 0.0))
    fake_client.chat.completions.create.side_effect = [
        _rate_limit_error(),
        _response(),
    ]
    llm.complete("retry-test", [{"role": "user", "content": "hi"}])
    assert fake_client.chat.completions.create.call_count == 2
