"""The chart file's facts — the source of truth behind aura-api POST /v1/chart-file.

Reshape Phase B. The product is a plain-text chart file that a user shares
into an AI assistant, so every number in it must be right. This module owns
the VALUES: Swiss Ephemeris, lahiri_vp285 (the Lahiri flavour AstroSage uses),
mean lunar node, Whole Sign houses, Vimshottari on a 365.25-day year. The
Worker never links Swiss Ephemeris (AGPL boundary): it ports these functions
to astronomy-engine and is gated on scripts/crossval_chart_file.py →
aura-api/test/golden/chart_file_crossval.json. The Worker renders the text;
the facts are decided here.

What this module adds (everything else is reused, already golden-tested):

  * D9 navamsa ........ navamsa_sign()
  * dignity ........... dignity()            — BPHS exaltation / moolatrikona /
                                               own sign / debilitation
  * combustion ........ is_combust()         — classical orbs, see COMBUST_ORB
  * transit snapshot .. sky_facts()
  * 12-month ingresses  ingresses()          — exact instants, root-found
  * the assembly ...... chart_file_facts()

plus panchang.panchang_at / panchang.vara_at (birth panchang) and
vimshottari.rounded_pratyantar (pratyantar). Aspects and yogas are
deliberately absent — not in this phase.

Every field is JSON-ready (plain dicts, epoch-ms instants, ISO dates) because
its first consumer is the crossval golden.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, time, timedelta

from .chart import compute_chart
from .ephemeris import DEFAULT_AYANAMSA
from .panchang import panchang_at, vara_at
from .positions import BODIES, sidereal_positions
from .timezones import local_to_utc, offset_minutes_at
from .vimshottari import (
    NAKSHATRA_ARC,
    compute_dasha,
    nakshatra_of,
    rounded_pratyantar,
    rounded_table,
)

# Same refusal as aura-api's /v1/chart (ARCTIC_LIMIT) and chart.py's Placidus
# limit: past the polar circles the ascendant stops being unique.
ARCTIC_LIMIT = 66.0

# ── Signs ───────────────────────────────────────────────────────────────────
# Classical sign rulers, Aries → Pisces (Rahu/Ketu rule nothing here).
SIGN_LORDS = (
    "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
    "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter",
)


def sign_index(longitude: float) -> int:
    return math.floor(longitude / 30) % 12


def house_from(sign: int, reference_sign: int) -> int:
    """Whole Sign house (1–12) of `sign` counted from `reference_sign`."""
    return (sign - reference_sign) % 12 + 1


# ── D9 navamsa ──────────────────────────────────────────────────────────────
NAVAMSA_ARC = 30 / 9  # 3°20′ — exactly one nakshatra pada


def navamsa_sign(longitude: float) -> int:
    """D9 sign index (0 = Aries) of a sidereal longitude.

    The continuous form of the classical rule (BPHS, Shodasavarga chapter):
    the zodiac's 108 navamsas are dealt onto the signs in order starting from
    Aries, so a movable sign's first navamsa is the sign itself, a fixed
    sign's is its 9th and a dual sign's its 5th. tests/test_chart_file.py
    checks this one-liner against that rule stated independently. A navamsa
    boundary IS a pada boundary, so D9 is exactly as robust as the pada.
    """
    return math.floor(longitude / NAVAMSA_ARC) % 12


# ── Dignity (BPHS) ──────────────────────────────────────────────────────────
# (sign index, from°, to°) — a half-open degree range inside the sign.
# Exaltation is the whole sign except where BPHS splits a sign: the Moon's
# Taurus (0–3° exalted, 3–30° moolatrikona) and Mercury's Virgo (0–15°
# exalted, 15–20° moolatrikona, 20–30° own sign).
EXALTATION = {
    "Sun": (0, 0, 30), "Moon": (1, 0, 3), "Mars": (9, 0, 30), "Mercury": (5, 0, 15),
    "Jupiter": (3, 0, 30), "Venus": (11, 0, 30), "Saturn": (6, 0, 30),
}
MOOLATRIKONA = {
    "Sun": (4, 0, 20), "Moon": (1, 3, 30), "Mars": (0, 0, 12), "Mercury": (5, 15, 20),
    "Jupiter": (8, 0, 10), "Venus": (6, 0, 15), "Saturn": (10, 0, 20),
}
DEBILITATION = {
    "Sun": 6, "Moon": 7, "Mars": 3, "Mercury": 11, "Jupiter": 9, "Venus": 5, "Saturn": 0,
}
OWN_SIGNS = {
    "Sun": (4,), "Moon": (3,), "Mars": (0, 7), "Mercury": (2, 5),
    "Jupiter": (8, 11), "Venus": (1, 6), "Saturn": (9, 10),
}


def dignity(body: str, longitude: float) -> str | None:
    """'exalted' | 'moolatrikona' | 'own sign' | 'debilitated' | None.

    Checked in that order (exaltation and moolatrikona are degree ranges, so
    their order only matters inside the two split signs above). None means
    none of the four — friendship-based dignity is not computed. Rahu and
    Ketu are always None: the traditions disagree on their signs, and the
    file says so rather than picking one.
    """
    if body not in EXALTATION:
        return None
    s = sign_index(longitude)
    deg = longitude - math.floor(longitude / 30) * 30
    for label, table in (("exalted", EXALTATION), ("moolatrikona", MOOLATRIKONA)):
        sign, lo, hi = table[body]
        if s == sign and lo <= deg < hi:
            return label
    if s == DEBILITATION[body]:
        return "debilitated"
    if s in OWN_SIGNS[body]:
        return "own sign"
    return None


# ── Combustion ──────────────────────────────────────────────────────────────
# Classical orbs (Surya Siddhanta, as used by the common Parashari software):
# a planet within this many degrees of the Sun's longitude is combust (asta).
# Mercury and Venus take a tighter orb while retrograde. The Sun itself, Rahu
# and Ketu are never combust (None = not applicable).
COMBUST_ORB = {"Moon": 12.0, "Mars": 17.0, "Mercury": 14.0, "Jupiter": 11.0,
               "Venus": 10.0, "Saturn": 15.0}
COMBUST_ORB_RETROGRADE = {"Mercury": 12.0, "Venus": 8.0}


def separation(a: float, b: float) -> float:
    """Smallest angle between two longitudes, degrees in [0, 180]."""
    d = abs(a - b) % 360
    return min(d, 360 - d)


def combust_orb(body: str, retrograde: bool) -> float | None:
    if body not in COMBUST_ORB:
        return None
    if retrograde and body in COMBUST_ORB_RETROGRADE:
        return COMBUST_ORB_RETROGRADE[body]
    return COMBUST_ORB[body]


def is_combust(body: str, longitude: float, sun_longitude: float, retrograde: bool) -> bool | None:
    orb = combust_orb(body, retrograde)
    if orb is None:
        return None
    return separation(longitude, sun_longitude) < orb


# ── Natal ───────────────────────────────────────────────────────────────────
def _ms(when_utc: datetime) -> int:
    return round(when_utc.timestamp() * 1000)


def _point(longitude: float) -> dict:
    nak = nakshatra_of(longitude)
    return {
        "longitude": longitude,
        "sign_index": sign_index(longitude),
        "nakshatra_index": nak.index,
        "pada": nak.pada,
        "navamsa_sign_index": navamsa_sign(longitude),
    }


def natal_facts(local_birth: datetime, zone: str, lat: float, lon: float) -> dict:
    """Ascendant + the nine grahas, fully qualified, and the birth panchang."""
    if abs(lat) >= ARCTIC_LIMIT:
        raise ValueError(f"|lat| >= {ARCTIC_LIMIT}: the ascendant is not unique there")
    utc = local_to_utc(local_birth, zone)
    chart = compute_chart(utc, lat, lon, ayanamsa=DEFAULT_AYANAMSA)
    asc = chart.ascendant.longitude
    asc_sign = sign_index(asc)
    d9_asc = navamsa_sign(asc)
    sun = chart.placements["Sun"].position.longitude

    planets: dict[str, dict] = {}
    for body in BODIES:
        pos = chart.placements[body].position
        d9 = navamsa_sign(pos.longitude)
        planets[body] = {
            **_point(pos.longitude),
            "house": house_from(sign_index(pos.longitude), asc_sign),
            "speed": pos.speed,
            "retrograde": pos.retrograde,
            "combust": is_combust(body, pos.longitude, sun, pos.retrograde),
            "dignity": dignity(body, pos.longitude),
            "navamsa_house": house_from(d9, d9_asc),
        }

    p = panchang_at(utc, ayanamsa=DEFAULT_AYANAMSA)
    v = vara_at(local_birth, zone, lat, lon)
    return {
        "utc_ms": _ms(utc),
        "utc_offset_minutes": offset_minutes_at(zone, local_birth),
        "ascendant": _point(asc),
        "planets": planets,
        "panchang": {
            "tithi_index": p.tithi_index,
            "nakshatra_index": p.nakshatra_index,
            "pada": p.pada,
            "yoga_index": p.yoga_index,
            "karana_index": p.karana_index,
            "elongation": p.elongation,
            "yoga_sum": p.yoga_sum,
        },
        "vara": {
            "vara": v.vara,
            "civil_weekday": v.civil_weekday,
            "before_sunrise": v.before_sunrise,
            "sunrise_ms": None if v.sunrise is None else _ms(local_to_utc(v.sunrise, zone)),
        },
    }


# ── Vimshottari ─────────────────────────────────────────────────────────────
MAHA_COUNT = 9  # one full cycle from the birth maha: every lord once


def _rows(periods, birth_day: date) -> list[dict]:
    """[start, end) rows with pre-birth rows dropped and the first clamped."""
    out = []
    for lord, start, end in periods:
        if end <= birth_day:
            continue
        out.append({"lord": lord, "start": max(start, birth_day).isoformat(),
                    "end": end.isoformat()})
    return out


def _running(rows: list[dict], on: str) -> int | None:
    for i, r in enumerate(rows):
        if r["start"] <= on < r["end"]:
            return i
    return None


def dasha_facts(moon_longitude: float, local_birth: datetime, as_of: date) -> dict:
    """All 9 mahas with antars, what runs on `as_of`, and the pratyantars of the
    running antar and the next one. Dates are day-rounded on the AstroSage
    cascade, in the birth place's calendar; every row is [start, end)."""
    res = compute_dasha(moon_longitude, local_birth, levels=3, cycles=2)
    birth_day = local_birth.date()
    table = rounded_table(res, local_birth, blocks=MAHA_COUNT)

    mahas = []
    for m in table:
        antar_spans, start = [], m.start
        for lord, end in m.antar:
            antar_spans.append((lord, start, end))
            start = end
        antar_spans[-1] = (*antar_spans[-1][:2], m.end)  # see _close
        mahas.append({
            "lord": m.lord,
            "start": max(m.start, birth_day).isoformat(),
            "end": m.end.isoformat(),
            "antar": _rows(antar_spans, birth_day),
            "_spans": antar_spans,
        })

    on = as_of.isoformat()
    running = None
    prat = {"current": None, "next": None}
    mi = _running(mahas, on)
    if mi is not None:
        ai = _running(mahas[mi]["antar"], on)
        if ai is not None:
            # Index into the FULL antar list (pre-birth rows included) for the
            # tree, since rounded_pratyantar addresses the unclamped table.
            full_ai = [s[0] for s in mahas[mi]["_spans"]].index(mahas[mi]["antar"][ai]["lord"])
            cur = _rows(_prat_spans(res, mi, full_ai, mahas[mi]["_spans"][full_ai][2]),
                        birth_day)
            running = {"maha": mi, "antar": ai, "pratyantar": _running(cur, on)}
            prat["current"] = {"maha": mi, "antar": ai, "rows": cur}
            # The next antar: the following row of this maha, else the first
            # of the next maha (only the birth maha ever drops rows, so a
            # displayed index and a tree index differ only there).
            if full_ai + 1 < 9:
                nxt_tree, nxt_shown = (mi, full_ai + 1), (mi, ai + 1)
            else:
                nxt_tree, nxt_shown = (mi + 1, 0), (mi + 1, 0)
            if nxt_tree[0] < MAHA_COUNT:
                nxt_end = mahas[nxt_tree[0]]["_spans"][nxt_tree[1]][2]
                prat["next"] = {"maha": nxt_shown[0], "antar": nxt_shown[1],
                                "rows": _rows(_prat_spans(res, *nxt_tree, nxt_end), birth_day)}
    for m in mahas:
        del m["_spans"]

    b = res.balance
    return {
        "nakshatra_index": res.nakshatra.index,
        "pada": res.nakshatra.pada,
        "lord": res.nakshatra.lord,
        "balance": {"years": b.years, "months": b.months, "days": b.days,
                    "total_days": b.total_days},
        "mahas": mahas,
        "running": running,
        "pratyantar": prat,
    }


def _prat_spans(res, maha_index: int, antar_index: int, antar_end: date):
    rows = [(p.lord, p.start, p.end) for p in rounded_pratyantar(res, maha_index, antar_index)]
    rows[-1] = (*rows[-1][:2], antar_end)  # see _close
    return rows


# _close: the LAST child row of a period ends on the parent's printed end.
# Maha ends are rounded from their exact floats (that is what matches
# AstroSage), but the antar chain is cascaded from the ROUNDED maha start, so
# the two can land a day apart — measured: the golden chart's Moon maha ends
# 2078-08-17 while its cascaded last antar ended 2078-08-18. A file that
# contradicts itself invites the assistant to "correct" it, so the parent's
# date wins and the last child absorbs the day. Pratyantars inherit the same
# rule from their antar (their first row already starts on the antar's start:
# rounded_pratyantar shares rounded_table's cascade root).


# ── Transits ────────────────────────────────────────────────────────────────
INGRESS_BODIES = ("Saturn", "Jupiter", "Rahu")  # Ketu = Rahu + 180°, same instants
INGRESS_WINDOW_DAYS = 365
_BISECT_STEPS = 24  # 1 day / 2^24 ≈ 5 ms of time — far below any meaningful precision

# Upper bounds on |sidereal speed|, °/day, with margin: Jupiter peaks ~0.25,
# Saturn ~0.13, the mean node is a steady ~0.053. They make the scan adaptive
# WITHOUT risk: a body at distance d from the nearest sign boundary cannot
# reach it in fewer than d / _MAX_SPEED days, so stepping that far (whole
# days, at least one) can never step over a crossing. The Worker's
# MAX_SPEED must equal this (its CPU budget is why the walk is adaptive).
_MAX_SPEED = {"Saturn": 0.15, "Jupiter": 0.3, "Rahu": 0.06}

# The instant "today's" transit positions are read at: local noon of the
# as-of date in the requested zone — the middle of that person's day. (The
# Moon moves ~13°/day, so the file says the instant out loud.)
TRANSIT_LOCAL_TIME = time(12, 0)


def _lon(body: str, when_utc: datetime, ayanamsa: str) -> float:
    return sidereal_positions(when_utc, ayanamsa=ayanamsa)[body].longitude


def ingresses(
    start_utc: datetime, days: int = INGRESS_WINDOW_DAYS, *, ayanamsa: str = DEFAULT_AYANAMSA
) -> list[dict]:
    """Every sign change of Saturn, Jupiter and Rahu in [start, start + days].

    Per body, an adaptive walk over WHOLE days from `start_utc` (step =
    floor(distance to the nearest boundary / _MAX_SPEED), at least 1 day),
    each change then bisected to the exact crossing. A retrograde re-entry is
    its own event — real information (Jupiter re-crosses 7 of its 12
    boundaries within a decade, see transits.sign_runs). The one blind spot —
    two crossings inside a single 1-day step, i.e. a station sitting on a
    boundary — is shared with the Worker and is a sub-day dip no reference
    site lists either. `ayanamsa` exists so the golden test can replay
    DrikPanchang's own zodiac; the file always uses the chart's lahiri_vp285.
    """
    out: list[dict] = []
    for body in INGRESS_BODIES:
        t = 0
        lon = _lon(body, start_utc, ayanamsa)
        while t < days:
            within = lon - math.floor(lon / 30) * 30
            dist = min(within, 30 - within)
            t2 = min(t + max(1, math.floor(dist / _MAX_SPEED[body])), days)
            lon2 = _lon(body, start_utc + timedelta(days=t2), ayanamsa)
            src, dst = sign_index(lon), sign_index(lon2)
            if dst != src:
                lo = start_utc + timedelta(days=t)
                hi = start_utc + timedelta(days=t2)
                for _ in range(_BISECT_STEPS):
                    mid = lo + (hi - lo) / 2
                    if sign_index(_lon(body, mid, ayanamsa)) == src:
                        lo = mid
                    else:
                        hi = mid
                out.append({
                    "body": body,
                    "utc_ms": _ms(hi),
                    "from_sign_index": src,
                    "to_sign_index": dst,
                    "retrograde": (dst - src) % 12 == 11,
                })
            t, lon = t2, lon2
    return sorted(out, key=lambda e: (e["utc_ms"], e["body"]))


def sky_facts(as_of: date, zone: str) -> dict:
    """Today's nine grahas (at local noon) and the next 365 days of ingresses."""
    instant = local_to_utc(datetime.combine(as_of, TRANSIT_LOCAL_TIME), zone)
    pos = sidereal_positions(instant, ayanamsa=DEFAULT_AYANAMSA)
    planets = {
        body: {**_point(p.longitude), "speed": p.speed, "retrograde": p.retrograde}
        for body, p in pos.items()
    }
    window_start = local_to_utc(datetime.combine(as_of, time()), zone)
    return {
        "as_of": as_of.isoformat(),
        "instant_ms": _ms(instant),
        "window_start_ms": _ms(window_start),
        "planets": planets,
        "ingresses": ingresses(window_start),
    }


# ── The whole file's facts ──────────────────────────────────────────────────
def chart_file_facts(
    local_birth: datetime, zone: str, lat: float, lon: float, as_of: date
) -> dict:
    """Everything the chart file states, for one birth, as of one date."""
    natal = natal_facts(local_birth, zone, lat, lon)
    moon = natal["planets"]["Moon"]["longitude"]
    return {
        "natal": natal,
        "dasha": dasha_facts(moon, local_birth, as_of),
        "sky": sky_facts(as_of, zone),
    }


def _utc_from_ms(ms: int) -> datetime:  # test/debug helper
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


__all__ = [
    "ARCTIC_LIMIT", "COMBUST_ORB", "COMBUST_ORB_RETROGRADE", "DEBILITATION",
    "EXALTATION", "INGRESS_BODIES", "INGRESS_WINDOW_DAYS", "MOOLATRIKONA",
    "NAKSHATRA_ARC", "NAVAMSA_ARC", "OWN_SIGNS", "SIGN_LORDS",
    "chart_file_facts", "combust_orb", "dasha_facts", "dignity", "house_from",
    "ingresses", "is_combust", "natal_facts", "navamsa_sign", "separation",
    "sign_index", "sky_facts",
]
