"""Skyfinder launcher — dispatches to v1 or v2 per request via a state file.

`make break-site` flips demo-site/.version to v2 with no restart: the running
server "changes overnight" underneath any stored procedure.

Run: uvicorn serve:app --port 8090   (from demo-site/)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from app_v1.main import app as app_v1
from app_v2.main import app as app_v2

VERSION_FILE = Path(__file__).resolve().parent / ".version"


def current_version() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip() or "v1"
    return "v1"


async def app(scope: dict[str, Any], receive: Callable, send: Callable) -> None:
    target = app_v2 if current_version() == "v2" else app_v1
    await target(scope, receive, send)
