"""Skyfinder v2 — the overnight redesign that breaks stale procedures.

Diffs vs v1: form ids from/to → origin-field/destination-field, URL params
from/to → origin/dest, submit button moved above the form and renamed.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flights import search_flights  # noqa: E402

app = FastAPI(title="Skyfinder v2")

_PAGE = """<!doctype html><html><head><title>Skyfinder — flight search, redesigned</title>
<style>
 body {{ font-family: system-ui; max-width: 720px; margin: 3rem auto; background: #f6f8fb; }}
 .card {{ background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 2px 8px #0002; }}
 label {{ display:block; margin-top: .8rem; }}
 input {{ padding: .5rem; width: 15rem; border-radius: 6px; border: 1px solid #bbb; }}
 button {{ margin: 1rem 0; padding: .6rem 1.6rem; border-radius: 8px; background: #2563eb; color: white; border: none; }}
 table {{ border-collapse: collapse; margin-top: 1.5rem; width: 100%; }}
 td, th {{ border: 1px solid #ddd; padding: .45rem .7rem; text-align: left; }}
</style></head><body>
<h1>✈️ Skyfinder <small>2.0</small></h1>
<div class="card">
<form action="/results" method="get">
  <button id="go" type="submit">Find my flight</button>
  <label>Origin <input id="origin-field" name="origin" placeholder="e.g. LAX" required></label>
  <label>Destination <input id="destination-field" name="dest" placeholder="e.g. JFK" required></label>
  <label>Travel date <input id="travel-date" name="date" placeholder="YYYY-MM-DD" required></label>
</form>
</div>
{results}
</body></html>"""


def render(results: str = "") -> str:
    return _PAGE.format(results=results)


def results_table(origin: str, dest: str, date: str) -> str:
    rows = "".join(
        f"<tr><td>{f['airline']}</td><td>{f['flight_no']}</td><td>{f['depart']}</td>"
        f"<td>{f['arrive']}</td><td>{f['stops']}</td><td>${f['price_usd']}</td></tr>"
        for f in search_flights(origin, dest, date)
    )
    return (
        f"<h2>Flights {origin.upper()} → {dest.upper()} on {date}</h2>"
        '<table class="results"><tr><th>Airline</th><th>Flight</th><th>Depart</th>'
        f"<th>Arrive</th><th>Stops</th><th>Price</th></tr>{rows}</table>"
    )


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return render()


@app.get("/results", response_class=HTMLResponse)
def results(
    origin: str = Query(),
    dest: str = Query(),
    date: str = Query(),
) -> str:
    return render(results_table(origin, dest, date))
