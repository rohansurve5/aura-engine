"""KP (Krishnamurti Paddhati) facts — the chart file's KP section (reshape E.3).

Data only, like the rest of the chart file: the KP zodiac, the 12 Placidus
cusps and the nine grahas with their sign / star / sub lords, each graha's
Placidus house, the four standard significator levels (planet-wise and
house-wise), the ruling planets at birth and the Vimshottari dasha on the KP
Moon. The Worker ports this module (aura-api/src/kp.ts) and is gated on
scripts/crossval_chart_file.py, which now carries these facts for all 300
births; AstroSage's own KP page for Golden-1 is the external reference
(tests/golden/astrosage_kp_golden_1.json, tests/test_kp.py).

THE KP ZODIAC. "KP New" is the ayanamsa of Prof. K. Balachandran (KP &
Astrology Year Book 2003) — the one AstroSage offers as "K. P. New". It is
not in Swiss Ephemeris. Its published shape is a value at 1900.0 plus
Newcomb's general precession in longitude, 5025.64″ T + 1.11″ T² (T in Julian
centuries from 1900 Jan 0.5); the 1900 value is pinned by AstroSage's printed
KP New values: 23°37′23″ on Golden-1's birth (1989-09-22 23:17 UT),
23°46′04″ on 2000-02-01 and 23°53′19″ on 2008-10-05 — one constant,
22°22′12.54″, reproduces all three to within 0.8″ (the printed second).

That printed value is NOT where AstroSage's KP positions sit, and the reason
is the Lahiri flavour this engine already settled on. AstroSage prints the
plain Lahiri ayanamsa (023-42-47 at this birth) but its positions follow
Lahiri VP285 (023-43-11.9): README > "Chart file vs AstroSage". Its KP page
then moves every point by the printed gap — Golden-1's nine grahas and lagna
all sit exactly 5′23″ (printed seconds) past their Lahiri places. So the KP
zodiac here is KP New carried onto the same VP285 base the file's Lahiri
section uses: KP New + (VP285 − plain Lahiri), a constant 23.0″ (Swiss:
23.02″ in 1900 … 22.97″ in 2100 — tests/test_kp.py pins it). Without it
every KP position would sit 23″ behind the chart above it.

HOUSES. Placidus, from Swiss Ephemeris' houses_ex (apparent sidereal time,
true obliquity) in the chart's VP285 zodiac, then moved onto the KP zodiac by
the same offset as the planets. A graha is in the house whose cusp it has
passed: [cusp n, cusp n+1). No "5° before the cusp" rule — AstroSage applies
none (its Sun, 4° before cusp 2, signifies house 1 only).

SIGNIFICATORS — the four standard levels, strongest first:
  planet-wise  A houses its star lord occupies   B the house it occupies
               C houses its star lord owns       D houses it owns
  house-wise   A planets in the star of its occupants   B its occupants
               C planets in the star of its owner       D its owner
"Owns" = the sign lord of the cusp's sign; Rahu and Ketu own none. AstroSage's
"Planet Signification" / "Significators of Houses" lists are exactly the
unions of these levels (all 21 rows for Golden-1).
"""

from __future__ import annotations

import math
from datetime import date, datetime

from .chart import compute_chart
from .chart_file import SIGN_LORDS, dasha_facts, sign_index
from .ephemeris import DEFAULT_AYANAMSA, ayanamsa_value, julday_utc, set_ayanamsa
from .panchang import vara_at
from .positions import BODIES
from .timezones import local_to_utc
from .vimshottari import DASHA_YEARS, LORD_SEQUENCE, NAKSHATRA_ARC

# ── The KP zodiac ───────────────────────────────────────────────────────────
KP_NEW_1900 = 22 + 22 / 60 + 12.54 / 3600       # KP New at JD 2415020.0 (1900 Jan 0.5)
NEWCOMB_ARCSEC = (5025.64, 1.11)                # ″ per century, ″ per century²
VP285_LAHIRI_GAP = 23.0 / 3600                  # VP285 − plain Lahiri (Swiss), degrees
_JD_1900 = 2415020.0


def kp_new_ayanamsa(jd_ut: float) -> float:
    """KP New (Balachandran), degrees — the value AstroSage prints."""
    t = (jd_ut - _JD_1900) / 36525
    return KP_NEW_1900 + (NEWCOMB_ARCSEC[0] * t + NEWCOMB_ARCSEC[1] * t * t) / 3600


def kp_ayanamsa(jd_ut: float) -> float:
    """The KP zodiac the file's KP positions are on: KP New on the VP285 base."""
    return kp_new_ayanamsa(jd_ut) + VP285_LAHIRI_GAP


# ── Lords ───────────────────────────────────────────────────────────────────
SUB_SPAN_ARCSEC = {lord: NAKSHATRA_ARC * 3600 * years / 120 for lord, years in DASHA_YEARS.items()}


def _from(lord: str) -> list[str]:
    i = LORD_SEQUENCE.index(lord)
    return [LORD_SEQUENCE[(i + k) % 9] for k in range(9)]


def kp_lords(longitude: float) -> dict:
    """Sign, star, sub and sub-sub lord of a KP longitude, plus the distance
    (arc-seconds) to the nearest boundary that decides each — the crossval's
    boundary-honesty input."""
    lon = longitude % 360
    within = (lon % NAKSHATRA_ARC) * 3600           # arc-seconds into the nakshatra
    star = LORD_SEQUENCE[math.floor(lon / NAKSHATRA_ARC) % 9]
    at = 0.0
    for sub in _from(star):
        span = SUB_SPAN_ARCSEC[sub]
        if within < at + span or sub == _from(star)[-1]:
            break
        at += span
    sub_from = within - at
    at2 = 0.0
    for sub_sub in _from(sub):
        span2 = span * DASHA_YEARS[sub_sub] / 120
        if sub_from < at2 + span2 or sub_sub == _from(sub)[-1]:
            break
        at2 += span2
    sign_deg = (lon % 30) * 3600
    star_deg = within
    return {
        "sign_lord": SIGN_LORDS[sign_index(lon)],
        "star_lord": star,
        "sub_lord": sub,
        "sub_sub_lord": sub_sub,
        "edge_arcsec": {
            "sign": min(sign_deg, 108_000 - sign_deg),
            "star": min(star_deg, NAKSHATRA_ARC * 3600 - star_deg),
            "sub": min(sub_from, span - sub_from),
            "sub_sub": min(sub_from - at2, at2 + span2 - sub_from),
        },
    }


# ── Houses and significators ────────────────────────────────────────────────
def placidus_house(longitude: float, cusps: list[float]) -> int:
    """1–12: the house whose cusp the point has passed, [cusp n, cusp n+1)."""
    for n in range(12):
        start, end = cusps[n], cusps[(n + 1) % 12]
        if (longitude - start) % 360 < (end - start) % 360:
            return n + 1
    raise AssertionError("cusps do not tile the circle")


def significators(planets: dict[str, dict], cusp_sign_lords: list[str]) -> tuple[dict, dict]:
    """(planet-wise, house-wise) — each entry the four levels A, B, C, D."""
    owns = {b: [h + 1 for h, lord in enumerate(cusp_sign_lords) if lord == b] for b in BODIES}
    occupants = {h: [b for b in BODIES if planets[b]["house"] == h] for h in range(1, 13)}
    in_star_of = {b: [p for p in BODIES if planets[p]["star_lord"] == b] for b in BODIES}

    planet_wise = {}
    for b in BODIES:
        star = planets[b]["star_lord"]
        planet_wise[b] = {
            "a": [planets[star]["house"]],
            "b": [planets[b]["house"]],
            "c": owns[star],
            "d": owns[b],
        }
    house_wise = {}
    for h in range(1, 13):
        owner = cusp_sign_lords[h - 1]
        house_wise[str(h)] = {
            "a": [p for p in BODIES if any(p in in_star_of[o] for o in occupants[h])],
            "b": occupants[h],
            "c": in_star_of[owner],
            "d": [owner],
        }
    return planet_wise, house_wise


# ── Vara → day lord ─────────────────────────────────────────────────────────
VARA_LORDS = {  # engine.panchang.VAAR_NAMES → the weekday's planet
    "Raviwara": "Sun", "Somawara": "Moon", "Mangalawara": "Mars", "Budhawara": "Mercury",
    "Guruwara": "Jupiter", "Shukrawara": "Venus", "Shaniwara": "Saturn",
}


# ── The KP section's facts ──────────────────────────────────────────────────
def kp_facts(local_birth: datetime, zone: str, lat: float, lon: float, as_of: date) -> dict:
    """Everything the file's KP section states, for one birth, as of one date."""
    utc = local_to_utc(local_birth, zone)
    jd = julday_utc(utc)
    set_ayanamsa(DEFAULT_AYANAMSA)
    base = ayanamsa_value(jd)                    # VP285, mean — the chart's zodiac
    kp = kp_ayanamsa(jd)
    shift = base - kp                            # VP285 longitude → KP longitude

    chart = compute_chart(utc, lat, lon, ayanamsa=DEFAULT_AYANAMSA)
    if chart.placidus_cusps is None:
        raise ValueError("Placidus is undefined at this latitude")
    cusps = [(c + shift) % 360 for c in chart.placidus_cusps]

    cusp_rows = [{"longitude": c, "sign_index": sign_index(c), **kp_lords(c)} for c in cusps]
    planets: dict[str, dict] = {}
    for body in BODIES:
        p = (chart.placements[body].position.longitude + shift) % 360
        planets[body] = {"longitude": p, "sign_index": sign_index(p), **kp_lords(p),
                         "house": placidus_house(p, cusps),
                         "cusp_edge_arcsec": min(
                             min((p - c) % 360, (c - p) % 360) for c in cusps) * 3600}
    planet_wise, house_wise = significators(planets, [r["sign_lord"] for r in cusp_rows])

    vara = vara_at(local_birth, zone, lat, lon)
    lagna, moon = cusp_rows[0], planets["Moon"]
    dasha = dasha_facts(moon["longitude"], local_birth, as_of)
    dasha.pop("pratyantar")                      # the KP section prints maha + antar only
    if dasha["running"] is not None:
        dasha["running"].pop("pratyantar")
    return {
        "ayanamsa": kp,
        "kp_new": kp_new_ayanamsa(jd),
        "cusps": cusp_rows,
        "planets": planets,
        "significators": {"planets": planet_wise, "houses": house_wise},
        "ruling": {
            "day_lord": VARA_LORDS[vara.vara],
            "vara": vara.vara,
            "lagna": {k: lagna[k] for k in ("sign_lord", "star_lord", "sub_lord")},
            "moon": {k: moon[k] for k in ("sign_lord", "star_lord", "sub_lord")},
        },
        "dasha": dasha,
    }


__all__ = [
    "KP_NEW_1900", "NEWCOMB_ARCSEC", "VARA_LORDS", "VP285_LAHIRI_GAP",
    "kp_ayanamsa", "kp_facts", "kp_lords", "kp_new_ayanamsa", "placidus_house",
    "significators",
]
