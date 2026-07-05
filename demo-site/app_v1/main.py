"""Skyfinder v1 — form ids: #from #to #date, URL params: from/to/date.

The /results URL encodes the whole search — a shortcut the agent can discover.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flights import search_flights  # noqa: E402

app = FastAPI(title="Skyfinder v1")

_PAGE = """<!doctype html><html><head><title>Skyfinder — search flights</title>
<style>
 body {{ font-family: system-ui; max-width: 720px; margin: 3rem auto; }}
 label {{ display:block; margin-top: .8rem; }}
 input {{ padding: .4rem; width: 14rem; }}
 button {{ margin-top: 1rem; padding: .5rem 1.4rem; }}
 table {{ border-collapse: collapse; margin-top: 1.5rem; width: 100%; }}
 td, th {{ border: 1px solid #ccc; padding: .45rem .7rem; text-align: left; }}
</style></head><body>
<h1>✈️ Skyfinder</h1>
<form action="/results" method="get">
  <label>From <input id="from" name="from" placeholder="e.g. LAX" required></label>
  <label>To <input id="to" name="to" placeholder="e.g. JFK" required></label>
  <label>Date <input id="date" name="date" placeholder="YYYY-MM-DD" required></label>
  <button id="search-btn" type="submit">Search flights</button>
</form>
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
    origin: str = Query(alias="from"),
    dest: str = Query(alias="to"),
    date: str = Query(),
) -> str:
    return render(results_table(origin, dest, date))
