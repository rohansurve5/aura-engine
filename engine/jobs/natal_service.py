"""REFERENCE-ONLY natal-lookup microservice (FastAPI) — golden source, not deployed.

The app's natal lookup now runs INSIDE the aura-api Cloudflare Worker
(astronomy-engine, MIT — see aura-api/src/natal.ts), so this service is no
longer part of the runtime path and is NOT deployed. It stays in the repo as
the golden source of truth: `scripts/crossval_natal.py` cross-validates the
Worker's math against this engine on 1,000+ random births (100% agreement on
nakshatra_index and moon_sign required) and that golden set gates every
aura-api deploy. If the two ever disagree, THIS side is correct.

It links Swiss Ephemeris, which is why it lives in the engine repo (AGPL). The
private `aura-api` never imports it and never links Swiss Ephemeris.

Correctness note: the natal nakshatra, Moon sign and Sun sign are all GEOCENTRIC
sidereal quantities — they do NOT depend on birth latitude/longitude. `lat`/`lon`
are accepted for forward-compatibility (future ascendant/house work) but are
ignored here. If the birth time is unknown, noon IST is assumed (the Moon moves
~13°/day, so a whole-day assumption can land on an adjacent nakshatra at the
~1-in-27 boundary cases — surfaced via `time_assumed`).

Run locally:
    uv sync --extra api
    uv run uvicorn engine.jobs.natal_service:app --reload --port 8000
    curl "http://localhost:8000/v1/natal?dob=1989-09-23&time=04:47"
"""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from ..positions import positions_from_ist
from ..vimshottari import nakshatra_of

app = FastAPI(title="aura natal-service", version="0.1.0")

# The app calls this from a mobile client; CORS is permissive because the
# endpoint is public and returns no secrets (pure birth-data → nakshatra math).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/v1/natal")
def natal(
    dob: str = Query(..., description="birth date, YYYY-MM-DD (IST)"),
    time: str = Query("12:00", description="birth time HH:MM (IST); noon if unknown"),
    lat: float | None = Query(None, description="ignored (natal nakshatra is geocentric)"),
    lon: float | None = Query(None, description="ignored (natal nakshatra is geocentric)"),
) -> dict:
    """Resolve the natal nakshatra + Moon/Sun signs from birth date & time."""
    try:
        year, month, day = (int(part) for part in dob.split("-"))
        hour, minute = (int(part) for part in time.split(":"))
        birth = datetime(year, month, day, hour, minute)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400, detail="dob must be YYYY-MM-DD and time HH:MM"
        ) from None

    positions = positions_from_ist(birth)
    moon = positions["Moon"]
    sun = positions["Sun"]
    nak = nakshatra_of(moon.longitude)

    return {
        "nakshatra_index": nak.index,
        "nakshatra": nak.name,
        "pada": nak.pada,
        "lord": nak.lord,
        "moon_sign": moon.sign,
        "sun_sign": sun.sign,
        "time_assumed": time == "12:00",
    }


@app.get("/v1/health")
def health() -> dict:
    return {"ok": True, "service": "aura natal-service"}
