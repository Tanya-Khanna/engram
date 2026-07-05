"""Deterministic fake flight data shared by Skyfinder v1 and v2."""
from __future__ import annotations

import hashlib

AIRLINES = ["Aether Air", "BlueMeridian", "Cirrus Lines", "Dawnjet", "Everflight"]


def search_flights(origin: str, dest: str, date: str) -> list[dict[str, str | int]]:
    """Same inputs → same results, every time. Benchmarks depend on this."""
    seed = f"{origin.upper().strip()}|{dest.upper().strip()}|{date.strip()}"
    digest = hashlib.sha256(seed.encode()).digest()
    flights = []
    for i in range(5):
        b = digest[i * 6 : i * 6 + 6]
        depart_h, depart_m = b[0] % 24, (b[1] % 4) * 15
        duration = 120 + b[2] % 600
        arrive_h = (depart_h + duration // 60) % 24
        arrive_m = (depart_m + duration % 60) % 60
        flights.append(
            {
                "airline": AIRLINES[b[3] % len(AIRLINES)],
                "flight_no": f"{AIRLINES[b[3] % len(AIRLINES)][:2].upper()}{100 + b[4] * 3}",
                "depart": f"{depart_h:02d}:{depart_m:02d}",
                "arrive": f"{arrive_h:02d}:{arrive_m:02d}",
                "stops": b[5] % 3,
                "price_usd": 180 + b[5] * 7 + b[0] * 3,
            }
        )
    return sorted(flights, key=lambda f: f["price_usd"])
