"""Skyfinder v1/v2: deterministic data + the exact breakage the demo needs."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "demo-site"))
from app_v1.main import app as app_v1  # noqa: E402
from app_v2.main import app as app_v2  # noqa: E402
from flights import search_flights  # noqa: E402

v1 = TestClient(app_v1)
v2 = TestClient(app_v2)


def test_deterministic_results():
    assert search_flights("SFO", "NRT", "2026-07-20") == search_flights(
        "sfo", "nrt", "2026-07-20"
    )
    assert search_flights("SFO", "NRT", "2026-07-20") != search_flights(
        "SFO", "NRT", "2026-07-21"
    )


def test_v1_form_and_url_shortcut():
    page = v1.get("/").text
    assert 'id="from"' in page and 'id="search-btn"' in page
    results = v1.get("/results", params={"from": "SFO", "to": "NRT", "date": "2026-07-20"})
    assert results.status_code == 200
    assert "SFO → NRT" in results.text


def test_v2_breaks_v1_selectors_and_params():
    page = v2.get("/").text
    assert 'id="from"' not in page, "v2 must rename v1's form ids"
    assert 'id="origin-field"' in page
    # v1's URL params 404/422 on v2 — the staleness cliff
    assert v2.get("/results", params={"from": "SFO", "to": "NRT", "date": "x"}).status_code == 422
    ok = v2.get("/results", params={"origin": "SFO", "dest": "NRT", "date": "2026-07-20"})
    assert ok.status_code == 200


def test_same_data_both_versions():
    r1 = v1.get("/results", params={"from": "SFO", "to": "NRT", "date": "2026-07-20"}).text
    r2 = v2.get("/results", params={"origin": "SFO", "dest": "NRT", "date": "2026-07-20"}).text
    row = "$" + r1.split("$")[1].split("<")[0]
    assert row in r2, "v2 redesign must not change the underlying data"
