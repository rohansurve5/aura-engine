"""Deterministic daily_sky payload builder.

`build_daily_sky(day)` turns a civil date into the JSON blob stored in
`daily_sky.payload`: panchang (tithi/nakshatra/yoga/karana with end times),
sunrise/sunset, day+night choghadiya, the three kaals, moon phase and the
planet-of-day. It is a pure function of `day` (+ the canonical location) — no
`datetime.now()`, no randomness — so two runs for the same date produce
byte-identical payloads (see tests/test_precompute.py).

MVP LIMITATION: one canonical location (Pune, IST). Solar times are that city's;
per-user city-level times are deferred. Documented here and in the migration.
"""

from __future__ import annotations

import math
from datetime import date, datetime

from .choghadiya import (
    Window,
    day_choghadiya,
    gulika_kaal,
    night_choghadiya,
    rahu_kaal,
    yamaganda_kaal,
)
from .panchang import Element, Panchang, compute_panchang
from .timezones import resolve_tz

# One canonical location for the whole app (see module docstring / migration).
CANONICAL_LOCATION = {"name": "Pune, India", "lat": 18.5204, "lon": 73.8567, "tz": "+05:30"}

# Indexed by Python weekday(): Monday=0 … Sunday=6.
PLANET_OF_DAY = ("Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Sun")

# Eight lunar phases keyed by elongation octant (round(fraction*8) mod 8).
MOON_PHASES = (
    "New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
    "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent",
)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def _elems(elements: tuple[Element, ...]) -> list[dict]:
    return [{"name": e.name, "index": e.index, "end": _iso(e.end)} for e in elements]


def _win(w: Window) -> dict:
    return {"name": w.name, "start": _iso(w.start), "end": _iso(w.end)}


def build_daily_sky(day: date, *, location: dict = CANONICAL_LOCATION) -> dict:
    """The deterministic `daily_sky.payload` dict for `day` at `location`."""
    # location["tz"] is a spec string ("+05:30" or an IANA id); compute_panchang
    # wants a tzinfo. Before this was plumbed through, every location formatted
    # its times in IST regardless of where it actually was.
    p: Panchang = compute_panchang(
        day, location["lat"], location["lon"], tz=resolve_tz(location["tz"])
    )

    elong = p.phase_fraction * 360.0
    illumination = round((1 - math.cos(math.radians(elong))) / 2, 4)
    phase_name = MOON_PHASES[int(round(p.phase_fraction * 8)) % 8]

    return {
        "date": day.isoformat(),
        "location": location,
        "weekday": p.weekday,
        "weekday_index": day.weekday(),
        "vaar": p.vaar,
        "planet_of_day": PLANET_OF_DAY[day.weekday()],
        "sunrise": _iso(p.sunrise),
        "sunset": _iso(p.sunset),
        "next_sunrise": _iso(p.next_sunrise),
        "paksha": p.paksha,
        "waxing": p.waxing,
        "moon_phase": {
            "name": phase_name,
            "fraction": round(p.phase_fraction, 4),
            "illumination": illumination,
            "waxing": p.waxing,
        },
        "day_nakshatra_index": p.nakshatra[0].index,
        "tithi": _elems(p.tithi),
        "nakshatra": _elems(p.nakshatra),
        "yoga": _elems(p.yoga),
        "karana": _elems(p.karana),
        "choghadiya": {
            "day": [_win(w) for w in day_choghadiya(p.sunrise, p.sunset)],
            "night": [_win(w) for w in night_choghadiya(p.sunset, p.next_sunrise)],
        },
        "kaals": {
            "rahu": _win(rahu_kaal(p.sunrise, p.sunset)),
            "gulika": _win(gulika_kaal(p.sunrise, p.sunset)),
            "yamaganda": _win(yamaganda_kaal(p.sunrise, p.sunset)),
        },
    }
