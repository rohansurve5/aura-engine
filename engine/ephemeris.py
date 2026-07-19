"""Swiss Ephemeris initialisation and ayanamsa registry.

This is the single place that configures pyswisseph: where the vendored `.se1`
data files live, and which sidereal (ayanamsa) mode maps to which name. Every
other module asks *this* module for a configured `swisseph` handle so there is
exactly one source of truth for the ephemeris path and zodiac mode.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta, timezone

import swisseph as swe

# ── Vendored ephemeris data ────────────────────────────────────────────────
# sepl_18.se1 / semo_18.se1 cover 1800–2399, so Aura's supported 1900–2100
# birth range is fully inside the high-precision Swiss files (no Moshier
# fallback). See README > "Ephemeris data range".
_EPHE_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "ephe")
SUPPORTED_YEARS = (1900, 2100)

_initialised = False


def _ensure_init() -> None:
    global _initialised
    if not _initialised:
        swe.set_ephe_path(os.path.abspath(_EPHE_DIR))
        _initialised = True


# ── Ayanamsa registry ──────────────────────────────────────────────────────
# All keys are flavours of Lahiri (Chitrapaksha) plus a few common alternates,
# so we can prove *which* one AstroSage/DrikPanchang actually use against the
# golden chart. `lahiri` is the plain Swiss default; `lahiri_vp285` is the
# variant that matches AstroSage's Vimshottari table (see golden test).
AYANAMSAS: dict[str, int] = {
    "lahiri": swe.SIDM_LAHIRI,
    "lahiri_1940": swe.SIDM_LAHIRI_1940,
    "lahiri_vp285": swe.SIDM_LAHIRI_VP285,
    "lahiri_icrc": swe.SIDM_LAHIRI_ICRC,
    "true_citra": swe.SIDM_TRUE_CITRA,
    "raman": swe.SIDM_RAMAN,
    "krishnamurti": swe.SIDM_KRISHNAMURTI,
}

# The Lahiri flavour that reproduces AstroSage's Vimshottari table (proven in
# tests/test_vimshottari.py): exact balance, all maha boundaries within ±1 day.
ASTROSAGE_AYANAMSA = "lahiri_vp285"

# The Lahiri flavour that reproduces DrikPanchang's panchang timings (proven in
# tests/test_panchang.py): with plain `lahiri`, yoga ends match to ±0.8 min and
# nakshatra to ±1.0 min; with `lahiri_vp285` both drift ~+0.7 min further.
# Yes — the two reference sites use *different* Lahiri flavours.
DRIKPANCHANG_AYANAMSA = "lahiri"

# Library-wide default. Switched from plain `lahiri` to `lahiri_vp285` in
# Prompt A.1: Aura's accuracy bar is "matches the references users check
# against" (AstroSage/DrikPanchang), and plain Swiss Lahiri is ~3–4 days off
# on dasha boundaries for the golden chart. See README > "Ayanamsa discovery".
DEFAULT_AYANAMSA = ASTROSAGE_AYANAMSA

# India Standard Time has been a fixed UTC+05:30 since 1945-09; every birth in
# our supported range uses it with no DST. Kept as a constant so the offset is
# auditable rather than buried in arithmetic.
IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def set_ayanamsa(name: str) -> int:
    """Configure swisseph for the named ayanamsa and return its swe mode int."""
    _ensure_init()
    try:
        mode = AYANAMSAS[name]
    except KeyError:
        raise ValueError(
            f"unknown ayanamsa {name!r}; choose from {sorted(AYANAMSAS)}"
        ) from None
    swe.set_sid_mode(mode, 0, 0)
    return mode


def julday_utc(when_utc: datetime) -> float:
    """Julian Day (UT) for a timezone-aware or naive-UTC datetime."""
    _ensure_init()
    if when_utc.tzinfo is not None:
        when_utc = when_utc.astimezone(UTC)
    hour = when_utc.hour + when_utc.minute / 60 + when_utc.second / 3600
    return swe.julday(when_utc.year, when_utc.month, when_utc.day, hour, swe.GREG_CAL)


def ist_to_utc(local: datetime) -> datetime:
    """Interpret a naive datetime as IST wall-clock and return aware UTC."""
    return local.replace(tzinfo=IST).astimezone(UTC)


def ayanamsa_value(jd_ut: float) -> float:
    """The ayanamsa (degrees) for the currently configured mode at `jd_ut`."""
    _ensure_init()
    return swe.get_ayanamsa_ut(jd_ut)
