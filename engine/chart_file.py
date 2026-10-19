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
  * transit snapshot .. sky_facts()          — always India time (TRANSIT_ZONE)
  * 12-month ingresses  ingresses()          — exact instants, root-found
  * Saturn cycles ..... saturn_changes() + saturn_cycles() — Sade Sati and
                                               Dhaiya from the natal Moon sign
  * Mangal dosha ...... mangal_dosha()       — houses 1/2/4/7/8/12 from the
                                               lagna and the Moon, exact
                                               cancellations only
  * the assembly ...... chart_file_facts()

plus panchang.panchang_at / panchang.vara_at (birth panchang) and
vimshottari.rounded_pratyantar (pratyantar). Aspects and yogas are not
computed: the file lets the assistant interpret them from these values,
labelled as its own interpretation (reshape B review).

Every field is JSON-ready (plain dicts, epoch-ms instants, ISO dates) because
its first consumer is the crossval golden.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, time, timedelta

from .chart import compute_chart
from .ephemeris import DEFAULT_AYANAMSA
from .panchang import panchang_at, vara_at
from .positions import BODIES, sidereal_longitude, sidereal_positions
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


# ── Mangal dosha ────────────────────────────────────────────────────────────
# The rule Rohan set (reshape B review): Mars in the 1st, 2nd, 4th, 7th, 8th or
# 12th Whole Sign house, counted separately from the lagna and from the Moon
# sign — compatibility.py's INCLUSIVE set. Traditions differ on the 2nd house
# (compatibility.py's STRICT set drops it, and so does AstroSage's report), so
# the file says so whenever the 2nd decides. Like compatibility.py, this is a
# description of a placement, never a verdict on anyone's marriage.
MANGAL_DOSHA_HOUSES = (1, 2, 4, 7, 8, 12)

# Only cancellations that are a pure fact of sign positions — nothing that
# needs a judgement of strength, the partner's chart or the person's age:
#   own_sign / exalted — Mars in Aries or Scorpio / in Capricorn;
#   with_jupiter       — Jupiter in Mars's sign;
#   jupiter_aspect     — Mars in the 5th, 7th or 9th sign from Jupiter
#                        (Jupiter's full aspects, counted by whole sign).
MANGAL_CANCELLATIONS = ("own_sign", "exalted", "with_jupiter", "jupiter_aspect")


def mangal_dosha(asc_sign: int, mars_sign: int, moon_sign: int, jupiter_sign: int) -> dict:
    from_lagna = house_from(mars_sign, asc_sign)
    from_moon = house_from(mars_sign, moon_sign)
    cancelled_by = []
    if mars_sign in OWN_SIGNS["Mars"]:
        cancelled_by.append("own_sign")
    if mars_sign == EXALTATION["Mars"][0]:
        cancelled_by.append("exalted")
    if mars_sign == jupiter_sign:
        cancelled_by.append("with_jupiter")
    if house_from(mars_sign, jupiter_sign) in (5, 7, 9):
        cancelled_by.append("jupiter_aspect")
    lagna = from_lagna in MANGAL_DOSHA_HOUSES
    moon = from_moon in MANGAL_DOSHA_HOUSES
    return {
        "from_lagna": {"house": from_lagna, "dosha": lagna},
        "from_moon": {"house": from_moon, "dosha": moon},
        "cancelled_by": cancelled_by,
        "present": (lagna or moon) and not cancelled_by,
    }


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
    sign_of = {body: planets[body]["sign_index"] for body in ("Mars", "Moon", "Jupiter")}
    return {
        "utc_ms": _ms(utc),
        "utc_offset_minutes": offset_minutes_at(zone, local_birth),
        "ascendant": _point(asc),
        "planets": planets,
        "mangal_dosha": mangal_dosha(
            asc_sign, sign_of["Mars"], sign_of["Moon"], sign_of["Jupiter"]),
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

# Aura is for births in India (reshape B review), so "today" and the transit
# picture are always India's: the as-of date is the date in India, positions
# are read at 12:00 noon IST — the middle of the day; the Moon moves ~13°/day,
# so the file says the instant out loud — and dates are IST dates.
TRANSIT_ZONE = "Asia/Kolkata"
TRANSIT_LOCAL_TIME = time(12, 0)


def _lon(body: str, when_utc: datetime, ayanamsa: str) -> float:
    return sidereal_longitude(body, when_utc, ayanamsa=ayanamsa)


def ingresses(
    start_utc: datetime,
    days: int = INGRESS_WINDOW_DAYS,
    *,
    ayanamsa: str = DEFAULT_AYANAMSA,
    bodies: tuple[str, ...] = INGRESS_BODIES,
) -> list[dict]:
    """Every sign change of `bodies` (Saturn, Jupiter, Rahu) in [start, start + days].

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
    for body in bodies:
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


def _ist_midnight(day: date) -> datetime:
    return local_to_utc(datetime.combine(day, time()), TRANSIT_ZONE)


def sky_facts(as_of: date) -> dict:
    """Today's nine grahas (12:00 IST), the next 365 days of ingresses, and
    Saturn's sign changes for the Saturn-cycle section."""
    instant = local_to_utc(datetime.combine(as_of, TRANSIT_LOCAL_TIME), TRANSIT_ZONE)
    pos = sidereal_positions(instant, ayanamsa=DEFAULT_AYANAMSA)
    planets = {
        body: {**_point(p.longitude), "speed": p.speed, "retrograde": p.retrograde}
        for body, p in pos.items()
    }
    window_start = _ist_midnight(as_of)
    return {
        "as_of": as_of.isoformat(),
        "instant_ms": _ms(instant),
        "window_start_ms": _ms(window_start),
        "planets": planets,
        "ingresses": ingresses(window_start),
        "saturn": saturn_changes(as_of),
    }


# ── Saturn cycles: Sade Sati and Dhaiya ─────────────────────────────────────
# Saturn's sign counted from the natal MOON sign (not the lagna):
#   Sade Sati — Saturn in the 12th, 1st or 2nd sign: the rising, peak and
#               setting phases, about 2½ years each, ~7½ in all;
#   Dhaiya    — Saturn in the 4th sign (Kantaka Shani) or the 8th (Ashtama
#               Shani), about 2½ years; AstroSage calls both "Small Panoti".
#
# transits.sade_sati_episodes (the retired daily app's reading) models the same
# passage differently on two counts, and the chart file departs on purpose:
#   * it splits an episode at ANY gap and flags detached dips as "not a full
#     passage"; here a retrograde pause stays inside one cycle, so "when does
#     it end?" is answered by the FINAL exit — the failure that module's own
#     docstring warns about (an April 2022 "end" for a Sagittarius Moon that
#     really ran to January 2023) cannot be printed;
#   * it reads signs at 00:00 IST; here a stretch is dated by the IST day the
#     sign change happens, which matches AstroSage's Sadesati report on 28/43
#     start dates (00:00 sampling: 15/43) and never misses by more than a day.
SATURN_CYCLES = (
    ("sade_sati", {12: "rising", 1: "peak", 2: "setting"}),
    ("kantaka", {4: None}),
    ("ashtama", {8: None}),
)

# The search window around the as-of date. Back 10 years: a running Sade
# Sati (the longest cycle, ≤ ~8½ years with its retrograde re-entries) began
# inside it. Ahead 32 years: Saturn's 29½-year round brings every cycle back,
# so the NEXT one has ended inside it. saturn_cycles refuses — never guesses —
# if either assumption fails (tests sweep every Moon sign over 1960–2060).
SATURN_LOOKBACK_DAYS = 3653
SATURN_LOOKAHEAD_DAYS = 11688

# Saturn's retrograde loop can carry it back out of the cycle's signs for a
# few months (≤ ~8) before it re-enters; that is one cycle, paused. A return
# of the same cycle is ~20+ years away, so 2 years separates them cleanly.
SATURN_PAUSE_MAX_DAYS = 730


def saturn_changes(as_of: date) -> dict:
    """Every Saturn sign change in [as_of − 10 y, as_of + 32 y] (IST midnights)."""
    start = _ist_midnight(as_of) - timedelta(days=SATURN_LOOKBACK_DAYS)
    days = SATURN_LOOKBACK_DAYS + SATURN_LOOKAHEAD_DAYS
    return {
        "window_start_ms": _ms(start),
        "window_end_ms": _ms(start + timedelta(days=days)),
        "start_sign_index": sign_index(_lon("Saturn", start, DEFAULT_AYANAMSA)),
        "changes": [
            {"utc_ms": e["utc_ms"], "to_sign_index": e["to_sign_index"]}
            for e in ingresses(start, days, bodies=("Saturn",))
        ],
    }


def _ist_date(ms: int) -> str:
    return (_utc_from_ms(ms) + timedelta(minutes=330)).date().isoformat()


def saturn_cycles(moon_sign: int, saturn: dict, as_of: date) -> list[dict]:
    """Sade Sati, Kantaka and Ashtama for a natal Moon sign: whether each runs
    at 12:00 IST on `as_of`, and the current (else the next) one's dates.

    A cycle is the stretch from Saturn's first entry into its signs to its
    final exit, retrograde pauses included; `segments` are the in-sign runs
    with their phase. Dates are IST dates of the sign changes — a segment
    runs from the day Saturn enters to the day it leaves.
    """
    now = _ms(local_to_utc(datetime.combine(as_of, TRANSIT_LOCAL_TIME), TRANSIT_ZONE))
    runs, sign, t = [], saturn["start_sign_index"], None   # t None = window edge
    for c in saturn["changes"]:
        runs.append((sign, t, c["utc_ms"]))
        sign, t = c["to_sign_index"], c["utc_ms"]
    runs.append((sign, t, None))

    out = []
    for kind, phases in SATURN_CYCLES:
        cycles: list[list[tuple]] = []
        for s, a, b in runs:
            house = house_from(s, moon_sign)
            if house not in phases:
                continue
            last = cycles[-1][-1] if cycles else None
            if last is not None and a is not None and last[2] is not None \
                    and a - last[2] <= SATURN_PAUSE_MAX_DAYS * 86_400_000:
                cycles[-1].append((s, a, b, house))
            else:
                cycles.append([(s, a, b, house)])
        current = next((c for c in cycles if (c[0][1] is None or c[0][1] <= now)
                        and (c[-1][2] is None or now < c[-1][2])), None)
        cycle = current or next((c for c in cycles if c[0][1] is not None and c[0][1] > now), None)
        if cycle is None or cycle[0][1] is None or cycle[-1][2] is None:
            raise RuntimeError(f"{kind}: the cycle runs past the search window")
        here = next((seg for seg in cycle if seg[1] <= now < seg[2]), None) if current else None
        out.append({
            "kind": kind,
            "houses": list(phases),
            "signs": [(moon_sign + h - 1) % 12 for h in phases],
            "state": "running" if here else "paused" if current else "none",
            "phase": phases[here[3]] if here else None,
            "start": _ist_date(cycle[0][1]),
            "end": _ist_date(cycle[-1][2]),
            "segments": [
                {"sign_index": s, "house": h, "phase": phases[h],
                 "start": _ist_date(a), "end": _ist_date(b)}
                for s, a, b, h in cycle
            ],
        })
    return out


# ── The whole file's facts ──────────────────────────────────────────────────
def chart_file_facts(
    local_birth: datetime, zone: str, lat: float, lon: float, as_of: date
) -> dict:
    """Everything the chart file states, for one birth, as of one date (IST)."""
    natal = natal_facts(local_birth, zone, lat, lon)
    moon = natal["planets"]["Moon"]["longitude"]
    sky = sky_facts(as_of)
    return {
        "natal": natal,
        "dasha": dasha_facts(moon, local_birth, as_of),
        "sky": sky,
        "saturn_cycles": saturn_cycles(sign_index(moon), sky["saturn"], as_of),
    }


def _utc_from_ms(ms: int) -> datetime:  # test/debug helper
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


__all__ = [
    "ARCTIC_LIMIT", "COMBUST_ORB", "COMBUST_ORB_RETROGRADE", "DEBILITATION",
    "EXALTATION", "INGRESS_BODIES", "INGRESS_WINDOW_DAYS", "MANGAL_CANCELLATIONS",
    "MANGAL_DOSHA_HOUSES", "MOOLATRIKONA", "NAKSHATRA_ARC", "NAVAMSA_ARC",
    "OWN_SIGNS", "SATURN_CYCLES", "SIGN_LORDS", "TRANSIT_ZONE",
    "chart_file_facts", "combust_orb", "dasha_facts", "dignity", "house_from",
    "ingresses", "is_combust", "mangal_dosha", "natal_facts", "navamsa_sign",
    "saturn_changes", "saturn_cycles", "separation", "sign_index", "sky_facts",
]
