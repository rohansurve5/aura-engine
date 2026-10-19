"""Sidereal planetary longitudes for a moment of birth.

Given a UTC instant, return the geocentric *sidereal* longitudes (Lahiri VP285
by default — the flavour that matches AstroSage; see engine.ephemeris) of Sun
through Ketu. These are geocentric, so they do not depend on
the observer's location on Earth — latitude/longitude are accepted for API
symmetry and future topocentric/ascendant work, but do not change the numbers
returned here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import swisseph as swe

from .ephemeris import (
    DEFAULT_AYANAMSA,
    ayanamsa_value,
    ist_to_utc,
    julday_utc,
    set_ayanamsa,
)
from .timezones import local_to_utc

# Grahas in traditional order. Ketu is derived (Rahu + 180°), not a swe body.
_SWE_BODY = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mars": swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS,
    "Saturn": swe.SATURN,
}
BODIES = (*_SWE_BODY.keys(), "Rahu", "Ketu")

SIGNS = (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
)


@dataclass(frozen=True)
class Position:
    """One graha's sidereal placement."""

    body: str
    longitude: float          # sidereal ecliptic longitude, 0–360°
    speed: float              # °/day (negative = retrograde)
    retrograde: bool

    @property
    def sign(self) -> str:
        return SIGNS[int(self.longitude // 30)]

    @property
    def sign_degrees(self) -> float:
        return self.longitude % 30

    def __str__(self) -> str:
        d = self.sign_degrees
        deg = int(d)
        minute = int((d - deg) * 60)
        r = " R" if self.retrograde else ""
        return f"{self.body:8} {deg:02d}°{minute:02d}' {self.sign}{r}"


def sidereal_positions(
    when_utc: datetime,
    *,
    lat: float | None = None,
    lon: float | None = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    true_node: bool = False,
) -> dict[str, Position]:
    """Sidereal longitudes for Sun..Ketu at `when_utc`.

    `lat`/`lon` are accepted for API symmetry (geocentric longitudes are
    location-independent). `true_node=False` uses the mean lunar node — the
    common default for Vimshottari in AstroSage.
    """
    set_ayanamsa(ayanamsa)
    jd = julday_utc(when_utc)
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED

    out: dict[str, Position] = {}
    for name, code in _SWE_BODY.items():
        (lon_val, _lat, _dist, lon_spd, _a, _b), _ = swe.calc_ut(jd, code, flags)
        out[name] = Position(name, lon_val % 360, lon_spd, lon_spd < 0)

    node_code = swe.TRUE_NODE if true_node else swe.MEAN_NODE
    (rahu_lon, _lat, _dist, rahu_spd, _a, _b), _ = swe.calc_ut(jd, node_code, flags)
    out["Rahu"] = Position("Rahu", rahu_lon % 360, rahu_spd, rahu_spd < 0)
    out["Ketu"] = Position("Ketu", (rahu_lon + 180) % 360, rahu_spd, rahu_spd < 0)
    return out


def sidereal_longitude(body: str, when_utc: datetime, *, ayanamsa: str = DEFAULT_AYANAMSA) -> float:
    """One body's sidereal longitude — the same swe call `sidereal_positions`
    makes for it (mean node for Rahu/Ketu), without computing the other eight.
    For long searches (the chart file's 42-year Saturn walk)."""
    set_ayanamsa(ayanamsa)
    jd = julday_utc(when_utc)
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
    code = swe.MEAN_NODE if body in ("Rahu", "Ketu") else _SWE_BODY[body]
    lon = swe.calc_ut(jd, code, flags)[0][0]
    return (lon + (180 if body == "Ketu" else 0)) % 360


def positions_from_ist(
    local_birth: datetime,
    *,
    lat: float | None = None,
    lon: float | None = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    true_node: bool = False,
) -> dict[str, Position]:
    """Convenience wrapper: interpret `local_birth` as IST, then compute.

    IST-only by design (the legacy goldens). For a birth anywhere else use
    `positions_from_local` with the birth place's zone.
    """
    return sidereal_positions(
        ist_to_utc(local_birth),
        lat=lat,
        lon=lon,
        ayanamsa=ayanamsa,
        true_node=true_node,
    )


def positions_from_local(
    local_birth: datetime,
    zone: str,
    *,
    lat: float | None = None,
    lon: float | None = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    true_node: bool = False,
) -> dict[str, Position]:
    """Interpret `local_birth` as wall-clock time in `zone`, then compute.

    `zone` is an IANA id (offset resolved AT the birth instant, so historical
    DST and offset changes apply) or a fixed "+HH:MM" offset — see
    engine.timezones. This is what a birth outside India needs: reading a New
    York wall clock as IST samples the Moon 9½ hours early.
    """
    return sidereal_positions(
        local_to_utc(local_birth, zone),
        lat=lat,
        lon=lon,
        ayanamsa=ayanamsa,
        true_node=true_node,
    )


def ayanamsa_at(when_utc: datetime, ayanamsa: str = DEFAULT_AYANAMSA) -> float:
    """The ayanamsa in degrees at `when_utc` for the named mode."""
    set_ayanamsa(ayanamsa)
    return ayanamsa_value(julday_utc(when_utc))
