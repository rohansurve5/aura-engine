"""Golden tests: the chart file's facts (reshape B2–B4, engine/chart_file.py).

Strongest evidence first:

  * EXTERNAL references, fetched — never typed from memory:
      - AstroSage's planetary positions at sunrise and the day's panchang
        elements with their end times (astrosage_sky_2026_10_19.json);
      - DrikPanchang's slow-planet ingress dates/times for Oct 2026 – Dec 2027
        (drik_ingress_2026_2027.json);
      - DrikPanchang's Pune day panchang for the golden birth date and nine
        other days (drik_panchang.json, already the panchang golden);
      - AstroSage's own Kundli for the golden chart at Thane — planets, D9,
        houses, R/C marks, dignity, birth panchang, Manglik verdicts
        (chart_file_golden_1.json), its 45-row Sadesati report
        (astrosage_sadesati_golden_1.json) and every dasha date it printed
        (astrosage_dasha.json, astrosage_dasha_tables.json), from the chart
        owner's screenshots, PDF and docx.
  * CLASSICAL RULES restated independently of the code under test: the D9
    movable/fixed/dual rule, the D7 and D10 odd/even rules, the BPHS dignity
    table, the combustion orbs.
  * STRUCTURAL invariants: pratyantar rows tile their antar exactly; dasha
    rows are contiguous; an ingress really is a sign change.
  * ENGINE-PINNED values for the golden chart (chart_file_golden_1.json) — a
    regression guard for what AstroSage does not print (pratyantar rows, the
    running markers, the Saturn cycles as of a date).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, timedelta

import pytest

from engine.chart_file import (
    ARCTIC_LIMIT,
    EXALTATION,
    INGRESS_BODIES,
    MANGAL_DOSHA_HOUSES,
    OWN_SIGNS,
    SATURN_LOOKAHEAD_DAYS,
    SATURN_LOOKBACK_DAYS,
    SIGN_LORDS,
    _utc_from_ms,
    chart_file_facts,
    dasamsa_sign,
    dasha_facts,
    dignity,
    house_from,
    ingresses,
    is_combust,
    mangal_dosha,
    natal_facts,
    navamsa_sign,
    saptamsa_sign,
    saturn_changes,
    saturn_cycles,
    separation,
    sign_index,
    sky_facts,
)
from engine.ephemeris import DRIKPANCHANG_AYANAMSA
from engine.panchang import YOGA_NAMES, karana_name, panchang_at, tithi_name, vara_at
from engine.positions import SIGNS, sidereal_longitude, sidereal_positions
from engine.timezones import local_to_utc
from engine.vimshottari import (
    NAKSHATRAS,
    calendar_children,
    calendar_dasha,
    calendar_gap,
    calendar_mahas,
    nakshatra_of,
)

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")
IST = "Asia/Kolkata"

BIRTH = datetime(1989, 9, 23, 4, 47)
THANE = (19 + 11 / 60, 72 + 58 / 60)   # Golden-1's birthplace; AstroSage: 19:11 N 72:58 E
PUNE = (18.5204, 73.8567)              # DrikPanchang's place in drik_panchang.json
AS_OF = date(2026, 10, 19)


def _load(name: str) -> dict:
    with open(os.path.join(GOLDEN_DIR, name)) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def facts() -> dict:
    return chart_file_facts(BIRTH, IST, *THANE, AS_OF)


# ── D9 navamsa vs the classical rule ────────────────────────────────────────
MOVABLE, FIXED = (0, 3, 6, 9), (1, 4, 7, 10)


def _navamsa_by_rule(lon: float) -> int:
    """BPHS as written: movable signs count from themselves, fixed from their
    9th, dual from their 5th; then one sign per 3°20′ part."""
    sign = int(lon // 30)
    part = int((lon % 30) // (30 / 9))
    first = sign if sign in MOVABLE else (sign + 8) % 12 if sign in FIXED else (sign + 4) % 12
    return (first + part) % 12


def test_navamsa_matches_the_classical_rule_in_every_part():
    for k in range(108):
        for f in (0.001, 0.5, 0.999):
            lon = (k + f) * 30 / 9
            assert navamsa_sign(lon) == _navamsa_by_rule(lon), lon


@pytest.mark.parametrize(("lon", "sign"), [
    (0.5, "Aries"),          # Aries 1st part → Aries (movable: itself)
    (30.5, "Capricorn"),     # Taurus 1st part → Capricorn (fixed: its 9th)
    (60.5, "Libra"),         # Gemini 1st part → Libra (dual: its 5th)
    (90.5, "Cancer"),        # Cancer 1st part → Cancer
    (125.0, "Taurus"),       # Leo 5° = 2nd part; Leo's 1st is its 9th (Aries)
    (359.5, "Pisces"),       # the zodiac's last navamsa
])
def test_navamsa_hand_examples(lon, sign):
    assert SIGNS[navamsa_sign(lon)] == sign


def test_vargottama_parts_fall_where_the_texts_put_them():
    # Vargottama = same sign in D1 and D9: the first navamsa of a movable sign,
    # the middle (5th) of a fixed sign, the last (9th) of a dual sign.
    assert navamsa_sign(0 * 30 + 1) == 0
    assert navamsa_sign(1 * 30 + 15) == 1
    assert navamsa_sign(2 * 30 + 29) == 2


# ── D7 saptamsa and D10 dasamsa vs the classical rule ───────────────────────
def _varga_by_rule(lon: float, parts: int, even_from: int) -> int:
    """BPHS as written: an odd sign (Aries is the 1st) counts its parts from
    itself, an even sign from its `even_from`-th sign, counted inclusively."""
    sign = int(lon // 30)
    part = int((lon % 30) // (30 / parts))
    first = sign if sign % 2 == 0 else (sign + even_from - 1) % 12
    return (first + part) % 12


def test_d7_and_d10_match_the_classical_rule_in_every_part():
    for parts, fn, even_from in ((7, saptamsa_sign, 7), (10, dasamsa_sign, 9)):
        for k in range(12 * parts):
            for f in (0.001, 0.5, 0.999):
                lon = (k + f) * 30 / parts
                assert fn(lon) == _varga_by_rule(lon, parts, even_from), (parts, lon)


def test_d7_is_the_continuous_count_from_aries():
    # 84 parts dealt onto the signs in order from Aries: the same rule, since
    # 7 × an odd sign index ≡ that index + 6 (mod 12).
    for k in range(84):
        assert saptamsa_sign((k + 0.5) * 30 / 7) == k % 12


@pytest.mark.parametrize(("lon", "d7", "d10"), [
    (0.5, "Aries", "Aries"),           # odd sign, 1st part: the sign itself
    (29.5, "Libra", "Capricorn"),      # Aries, last part
    (30.5, "Scorpio", "Capricorn"),    # Taurus (even), 1st part: its 7th / its 9th
    (59.5, "Taurus", "Libra"),         # Taurus, last part
    (60.5, "Gemini", "Gemini"),        # Gemini (odd), 1st part
    (359.5, "Pisces", "Leo"),          # Pisces (even), last part
])
def test_d7_and_d10_hand_examples(lon, d7, d10):
    assert (SIGNS[saptamsa_sign(lon)], SIGNS[dasamsa_sign(lon)]) == (d7, d10)


# ── Dignity (BPHS) and sign lords ───────────────────────────────────────────
@pytest.mark.parametrize(("body", "sign", "deg", "expected"), [
    ("Sun", 0, 10, "exalted"), ("Sun", 6, 10, "debilitated"),
    ("Sun", 4, 10, "moolatrikona"), ("Sun", 4, 25, "own sign"),
    ("Moon", 1, 2, "exalted"), ("Moon", 1, 4, "moolatrikona"), ("Moon", 3, 4, "own sign"),
    ("Moon", 7, 4, "debilitated"),
    ("Mars", 9, 28, "exalted"), ("Mars", 0, 11, "moolatrikona"), ("Mars", 0, 13, "own sign"),
    ("Mars", 7, 1, "own sign"), ("Mars", 3, 28, "debilitated"),
    ("Mercury", 5, 10, "exalted"), ("Mercury", 5, 17, "moolatrikona"),
    ("Mercury", 5, 25, "own sign"), ("Mercury", 2, 1, "own sign"),
    ("Mercury", 11, 15, "debilitated"),
    ("Jupiter", 3, 5, "exalted"), ("Jupiter", 8, 5, "moolatrikona"), ("Jupiter", 8, 15, "own sign"),
    ("Jupiter", 11, 1, "own sign"), ("Jupiter", 9, 5, "debilitated"),
    ("Venus", 11, 27, "exalted"), ("Venus", 6, 10, "moolatrikona"), ("Venus", 6, 20, "own sign"),
    ("Venus", 1, 1, "own sign"), ("Venus", 5, 27, "debilitated"),
    ("Saturn", 6, 20, "exalted"), ("Saturn", 10, 10, "moolatrikona"),
    ("Saturn", 10, 25, "own sign"),
    ("Saturn", 9, 1, "own sign"), ("Saturn", 0, 20, "debilitated"),
    ("Sun", 2, 15, None), ("Jupiter", 4, 15, None),
    ("Rahu", 1, 15, None), ("Ketu", 7, 15, None),   # traditions disagree: never asserted
])
def test_dignity_table(body, sign, deg, expected):
    assert dignity(body, sign * 30 + deg) == expected


def test_sign_lords_agree_with_own_signs():
    for body, signs in OWN_SIGNS.items():
        for s in signs:
            assert SIGN_LORDS[s] == body
    assert len(SIGN_LORDS) == 12
    assert set(EXALTATION) == set(OWN_SIGNS)


# ── Combustion ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize(("body", "gap", "retro", "expected"), [
    ("Moon", 11.9, False, True), ("Moon", 12.1, False, False),
    ("Mars", 16.9, False, True), ("Mars", 17.1, False, False),
    ("Mercury", 13.0, False, True), ("Mercury", 13.0, True, False),  # retro orb 12
    ("Jupiter", 10.9, False, True), ("Jupiter", 11.1, False, False),
    ("Venus", 9.0, False, True), ("Venus", 9.0, True, False),        # retro orb 8
    ("Saturn", 14.9, True, True), ("Saturn", 15.1, False, False),
    ("Sun", 0.0, False, None), ("Rahu", 1.0, True, None), ("Ketu", 1.0, True, None),
])
def test_combustion_orbs(body, gap, retro, expected):
    sun = 100.0
    assert is_combust(body, sun + gap, sun, retro) == expected
    assert is_combust(body, sun - gap, sun, retro) == expected  # either side


def test_separation_wraps_through_aries():
    assert separation(359.0, 1.0) == pytest.approx(2.0)
    assert separation(10.0, 190.0) == pytest.approx(180.0)


# ── Transit snapshot vs AstroSage (external) ────────────────────────────────
SKY = _load("astrosage_sky_2026_10_19.json")

# Moon (0.5″/s) and the mean node pin the CONVENTION — lahiri_vp285 + mean
# node — so they are held tight. The other planets are held at 2′: AstroSage's
# planet theory sits up to 106″ (Jupiter) from Swiss here, the same order as
# its known +65″ ascendant residual (docs/ASCENDANT.md). Sign, nakshatra and
# pada must all agree exactly.
TIGHT = {"Moon": 15.0, "Rahu": 15.0, "Ketu": 15.0}
LOOSE = 120.0


def _dms(text: str) -> float:
    d, m, s = (int(x) for x in text.split("-"))
    return d + m / 60 + s / 3600


@pytest.mark.parametrize("body", list(SKY["positions_at_sunrise"]))
def test_positions_match_astrosage_at_sunrise(body):
    ref = SKY["positions_at_sunrise"][body]
    instant = local_to_utc(datetime(2026, 10, 19, 6, 24), IST)
    lon = sidereal_positions(instant)[body].longitude
    nak = nakshatra_of(lon)
    assert SIGNS[sign_index(lon)] == ref["sign"]
    assert (nak.name, nak.pada) == (ref["nakshatra"], ref["pada"])
    gap = abs((lon % 30) - _dms(ref["dms"])) * 3600
    assert gap <= TIGHT.get(body, LOOSE), f"{body} {gap:.1f}″ from AstroSage"


def _ist(day: str, hms: str) -> datetime:
    h, m, s = (int(x) for x in hms.split(":"))
    return datetime.fromisoformat(day) + timedelta(hours=h, minutes=m, seconds=s)


def _element(p, kind: str) -> str:
    return {"tithi": p.tithi, "nakshatra": p.nakshatra, "karana": p.karana, "yoga": p.yoga}[kind]


# 3 min either side of a printed boundary: our ends match the references to
# ±2 min (test_panchang.py), the vp285/plain-Lahiri flavour gap is ~1 min.
EDGE = timedelta(minutes=3)


@pytest.mark.parametrize("kind", ["tithi", "nakshatra", "karana", "yoga"])
def test_panchang_at_matches_astrosage_boundaries(kind):
    rows = SKY["elements"][kind]
    for i, row in enumerate(rows):
        end = local_to_utc(_ist(SKY["date"], row["upto"]), IST)
        before = panchang_at(end - EDGE, ayanamsa="lahiri_vp285")
        after = panchang_at(end + EDGE, ayanamsa="lahiri_vp285")
        assert _element(before, kind) == row["name"]
        if i + 1 < len(rows):
            assert _element(after, kind) == rows[i + 1]["name"]
        else:
            assert _element(after, kind) != row["name"]
    noon = panchang_at(local_to_utc(_ist(SKY["date"], "12:00:00"), IST))
    assert noon.paksha == SKY["paksha"]


def test_vara_and_sunrise_match_astrosage():
    lat, lon = SKY["lat"], SKY["lon"]
    day = datetime.fromisoformat(SKY["date"])
    after = vara_at(day.replace(hour=8), IST, lat, lon)
    assert after.weekday == "Monday" and not after.before_sunrise   # AstroSage "Somavara"
    ref_rise = _ist(SKY["date"], SKY["sunrise"])
    assert abs((after.sunrise - ref_rise).total_seconds()) <= 120
    early = vara_at(day.replace(hour=5), IST, lat, lon)
    assert early.weekday == "Sunday" and early.civil_weekday == "Monday" and early.before_sunrise


# ── Birth panchang vs DrikPanchang (external) ───────────────────────────────
DRIK = _load("drik_panchang.json")


@pytest.mark.parametrize("day", DRIK["days"], ids=[d["date"] for d in DRIK["days"]])
def test_panchang_at_matches_drikpanchang_boundaries(day):
    """Every printed end on every golden Pune day: the element holds 3 min
    before it and its successor 3 min after — in DrikPanchang's own zodiac."""
    checked = 0
    for kind in ("tithi", "nakshatra", "karana", "yoga"):
        rows = day[kind]
        for i, row in enumerate(rows):
            if row["end"] is None:
                continue
            end = local_to_utc(datetime.fromisoformat(row["end"]), IST)
            before = panchang_at(end - EDGE, ayanamsa=DRIKPANCHANG_AYANAMSA)
            after = panchang_at(end + EDGE, ayanamsa=DRIKPANCHANG_AYANAMSA)
            assert _element(before, kind) == row["name"], (kind, row)
            if i + 1 < len(rows):
                assert _element(after, kind) == rows[i + 1]["name"], (kind, row)
            checked += 1
    assert checked >= 4


def test_golden_birth_panchang_matches_drikpanchang():
    """The golden birth instant (04:47 IST, 1989-09-23) read at DrikPanchang's
    PUNE page — before that morning's 06:24 sunrise there, so the elements are
    the ones DrikPanchang lists as prevailing at sunrise and the vara is the
    PREVIOUS day's (Friday). AstroSage's Thane page agrees (see below)."""
    ref = next(d for d in DRIK["days"] if d["date"] == "1989-09-23")
    p = panchang_at(local_to_utc(BIRTH, IST), ayanamsa="lahiri_vp285")
    assert p.tithi == ref["tithi"][0]["name"] and p.paksha == ref["paksha"]
    assert p.nakshatra == ref["nakshatra"][0]["name"]
    assert p.yoga == ref["yoga"][0]["name"]
    assert p.karana == ref["karana"][0]["name"]
    v = vara_at(BIRTH, IST, *PUNE)
    assert v.civil_weekday == ref["weekday"] == "Saturday"
    assert v.before_sunrise and v.weekday == "Friday" and v.vara == "Shukrawara"
    rise = datetime.fromisoformat(f"{ref['date']}T{ref['sunrise']}")
    assert abs((v.sunrise - rise).total_seconds()) <= 60


def test_birth_panchang_uses_the_charts_zodiac(facts):
    """The panchang nakshatra must be the Moon's nakshatra in the planet table,
    or the file contradicts itself."""
    n = facts["natal"]
    assert n["panchang"]["nakshatra_index"] == n["planets"]["Moon"]["nakshatra_index"]
    assert n["panchang"]["pada"] == n["planets"]["Moon"]["pada"]


def test_vara_without_sunrise_falls_back_to_the_civil_day():
    # Tromsø (69.6° N) in late June: the Sun never sets, so it never rises.
    v = vara_at(datetime(2020, 6, 21, 3, 0), "Europe/Oslo", 69.65, 18.96)
    assert v.sunrise is None and not v.before_sunrise
    assert v.weekday == v.civil_weekday == "Sunday"


# ── Ingresses vs DrikPanchang (external) ────────────────────────────────────
INGRESS = _load("drik_ingress_2026_2027.json")


@pytest.fixture(scope="module")
def ingress_runs():
    start = local_to_utc(datetime.fromisoformat(INGRESS["window"][0]), IST)
    first, last = (date.fromisoformat(d) for d in INGRESS["window"])
    days = (last - first).days
    return ingresses(start, days), ingresses(start, days, ayanamsa="lahiri")


def test_ingresses_are_drikpanchangs_events(ingress_runs):
    ref = [(e["body"], e["to"]) for e in INGRESS["events"]]
    for run in ingress_runs:
        assert [(e["body"], SIGNS[e["to_sign_index"]]) for e in run] == ref


def test_ingress_instants_match_drikpanchang(ingress_runs):
    """At DrikPanchang's printed minute, the engine (lahiri_vp285) must put the
    body within 40″ of the boundary it is crossing: the vp285/plain-Lahiri
    flavour gap is ~23″, and DrikPanchang's Lahiri measurably sits near it
    (between the two for every planet event, ~1.3″ past vp285 for the slow
    mean node — 10 min of its motion). Measured in ARC, not minutes, because a
    fixed time window means 40× more arc for Jupiter than for the node. Also:
    same IST date, and the retrograde mark where DrikPanchang prints one."""
    vp285, _ = ingress_runs
    for a, ref in zip(vp285, INGRESS["events"], strict=True):
        drik = local_to_utc(datetime.strptime(ref["ist"], "%Y-%m-%d %H:%M"), IST)
        lon = sidereal_positions(drik)[a["body"]].longitude
        boundary = 30.0 * (a["from_sign_index"] if a["retrograde"] else a["to_sign_index"])
        assert separation(lon, boundary) * 3600 <= 40.0, (ref, separation(lon, boundary) * 3600)
        ta = _utc_from_ms(a["utc_ms"])
        assert (ta + timedelta(hours=5, minutes=30)).date().isoformat() == ref["ist"][:10]
        if ref["body"] == "Rahu":
            assert a["retrograde"]  # the mean node only ever moves backward
        else:
            assert a["retrograde"] == ref["drik_retro_mark"], ref


def test_every_ingress_is_a_real_sign_change(ingress_runs):
    for e in ingress_runs[0]:
        t = _utc_from_ms(e["utc_ms"])
        before = sidereal_positions(t - timedelta(minutes=1))[e["body"]].longitude
        after = sidereal_positions(t + timedelta(minutes=1))[e["body"]].longitude
        assert sign_index(before) == e["from_sign_index"]
        assert sign_index(after) == e["to_sign_index"]
        assert e["body"] in INGRESS_BODIES


@pytest.mark.parametrize("start", ["2019-01-01", "2040-11-01", "1993-06-01"])
def test_adaptive_walk_finds_the_short_stays_a_daily_scan_finds(start):
    """Real short sign stays (Swiss, 1900–2100): Jupiter 24 days in Sagittarius
    from 2019-03-30, Saturn 8 days in Libra from 2041-01-29 and 27 days in
    Capricorn from 1993-10-15. The adaptive walk's whole safety argument is
    that it never steps over a crossing — so it must equal a brute-force
    daily scan exactly where over-stepping would bite."""
    t0 = datetime.fromisoformat(start).replace(tzinfo=UTC)
    brute = []
    for body in INGRESS_BODIES:
        prev = sign_index(sidereal_positions(t0)[body].longitude)
        for k in range(1, 366):
            cur = sign_index(sidereal_positions(t0 + timedelta(days=k))[body].longitude)
            if cur != prev:
                brute.append((body, prev, cur))
            prev = cur
    fast = [(e["body"], e["from_sign_index"], e["to_sign_index"]) for e in ingresses(t0)]
    assert sorted(fast) == sorted(brute)
    assert any(b != "Rahu" and (cur - prev) % 12 == 11 for b, prev, cur in brute)  # a dip


def test_sky_is_always_india_time():
    """India-only (reshape B review): today's positions at 12:00 IST, the
    12-month scan from IST midnight — whatever the birth zone was."""
    sky = sky_facts(date(2026, 10, 19))
    assert _utc_from_ms(sky["instant_ms"]) == datetime(2026, 10, 19, 6, 30, tzinfo=UTC)
    assert _utc_from_ms(sky["window_start_ms"]) == datetime(2026, 10, 18, 18, 30, tzinfo=UTC)
    assert all(sky["window_start_ms"] <= e["utc_ms"] for e in sky["ingresses"])


# ── The dasha section: AstroSage's calendar ────────────────────────────────
@pytest.fixture(scope="module")
def moon():
    return natal_facts(BIRTH, IST, *THANE)["planets"]["Moon"]["longitude"]


def test_pratyantars_tile_every_antar_exactly(moon):
    cal = calendar_dasha(moon, BIRTH.date())
    for maha in calendar_mahas(cal):
        antars = calendar_children(maha)
        assert (antars[0].start, antars[-1].end) == (maha.start, maha.end)
        for antar in antars:
            rows = calendar_children(antar)
            assert rows[0].lord == antar.lord and len(rows) == 9
            assert (rows[0].start, rows[-1].end) == (antar.start, antar.end)
            assert all(a.end == b.start for a, b in zip(rows, rows[1:], strict=False))


def test_dasha_rows_are_contiguous_and_start_at_birth(facts):
    mahas = facts["dasha"]["mahas"]
    assert [m["lord"] for m in mahas] == [
        "Rahu", "Jupiter", "Saturn", "Mercury", "Ketu", "Venus", "Sun", "Moon", "Mars"]
    assert mahas[0]["start"] == mahas[0]["antar"][0]["start"] == "1989-09-23"
    for a, b in zip(mahas, mahas[1:], strict=False):
        assert a["end"] == b["start"]
    for m in mahas:
        assert m["antar"][-1]["end"] == m["end"]
        assert all(x["end"] == y["start"] for x, y in zip(m["antar"], m["antar"][1:], strict=False))
    for which in ("current", "next"):
        p = facts["dasha"]["pratyantar"][which]
        antar = mahas[p["maha"]]["antar"][p["antar"]]
        assert (p["rows"][0]["start"], p["rows"][-1]["end"]) == (antar["start"], antar["end"])


def test_golden_maha_and_antar_dates_are_astrosages(facts):
    """Every maha and antar date the file prints is AstroSage's own — all 9
    maha ends and all 76 antar ends exact (the 365.25-day year got 42/76;
    test_vimshottari.py has why). Pre-birth antars AstroSage blanks are the
    ones the file drops."""
    ref = _load("astrosage_dasha.json")["maha"]
    for got, want in zip(facts["dasha"]["mahas"], ref, strict=False):  # ref has 10 blocks
        assert (got["lord"], got["start"], got["end"]) == (
            want["lord"], want["start"], want["end"])
        shown = [(a["lord"], a["end"]) for a in want["antar"] if a["end"] is not None]
        assert [(a["lord"], a["end"]) for a in got["antar"]] == shown
    assert sum(len(m["antar"]) for m in facts["dasha"]["mahas"]) == 76


def test_golden_pratyantars_sit_on_astrosages_calendar(facts):
    """The two pratyantar tables vs AstroSage's docx: 13 of 18 ends exact, the
    other 5 one calendar day early, because our Moon is 2.4″ further on than
    AstroSage's (its own ephemeris — README). Fed AstroSage's Moon, the same
    code gives every date: test_vimshottari.py."""
    abbr = {"KET": "Ketu", "VEN": "Venus", "SUN": "Sun", "MON": "Moon", "MAR": "Mars",
            "RAH": "Rahu", "JUP": "Jupiter", "SAT": "Saturn", "MER": "Mercury"}
    blocks = _load("astrosage_dasha_tables.json")["blocks"]
    exact = 0
    for which, label in (("current", ["SAT", "JUP"]), ("next", ["MER", "MER"])):
        want = next(b for b in blocks if b["label"] == label)["rows"]
        got = facts["dasha"]["pratyantar"][which]["rows"]
        assert [r["lord"] for r in got] == [abbr[lord] for lord, _ in want]
        for r, (_, (d, m, y, *_)) in zip(got, want, strict=True):
            gap = calendar_gap(date(y, m, d), date.fromisoformat(r["end"]))
            assert gap <= 1 and r["end"] <= date(y, m, d).isoformat(), (r, (d, m, y))
            exact += gap == 0
    assert exact == 13


def test_running_period_boundaries_are_start_inclusive(moon):
    cur = dasha_facts(moon, BIRTH, AS_OF)["pratyantar"]["current"]["rows"]
    switch = date.fromisoformat(cur[1]["end"])  # Saturn → Mercury pratyantar
    on_eve = dasha_facts(moon, BIRTH, switch - timedelta(days=1))["running"]
    on_day = dasha_facts(moon, BIRTH, switch)["running"]
    assert on_eve["pratyantar"] == 1 and on_day["pratyantar"] == 2


def test_next_antar_rolls_into_the_next_maha(facts):
    # Saturn–Jupiter is Saturn's LAST antar, so "next" is Mercury–Mercury.
    p = facts["dasha"]["pratyantar"]
    assert (p["current"]["maha"], p["current"]["antar"]) == (2, 8)
    assert (p["next"]["maha"], p["next"]["antar"]) == (3, 0)
    assert p["next"]["rows"][0]["start"] == facts["dasha"]["mahas"][3]["start"]


def test_birth_maha_drops_only_the_antars_that_ended_before_birth(moon):
    """The birth maha's virtual start is years before birth: rows that ended
    by the birth date are dropped (AstroSage prints them blank), the first
    kept row is clamped to the birth date."""
    rows = dasha_facts(moon, BIRTH, AS_OF)["mahas"][0]["antar"]
    assert [r["lord"] for r in rows] == ["Venus", "Sun", "Moon", "Mars"]
    assert (rows[0]["start"], rows[0]["end"]) == ("1989-09-23", "1990-03-05")


# ── The golden chart: AstroSage (external) + engine-pinned ─────────────────
GOLDEN_1 = _load("chart_file_golden_1.json")
AS = GOLDEN_1["astrosage"]


def _named(p: dict) -> dict:
    return {"sign": SIGNS[p["sign_index"]], "nakshatra": NAKSHATRAS[p["nakshatra_index"]],
            "pada": p["pada"], "navamsa_sign": SIGNS[p["navamsa_sign_index"]]}


def test_golden_birth_is_thane():
    b = GOLDEN_1["birth"]
    assert (b["place"], b["lat"], b["lon"]) == (
        "Thane, Maharashtra, India", *(round(x, 6) for x in THANE))


def test_golden_chart_engine_pinned(facts):
    pin = GOLDEN_1["engine_pinned"]
    n = facts["natal"]
    assert _named(n["ascendant"]) == pin["ascendant"]
    for body, want in pin["planets"].items():
        p = n["planets"][body]
        got = {**_named(p), **{k: p[k] for k in
               ("house", "retrograde", "combust", "dignity", "navamsa_house")}}
        assert got == want, body
    pp, v = n["panchang"], n["vara"]
    assert {
        "tithi": tithi_name(pp["tithi_index"]),
        "paksha": "Shukla" if pp["tithi_index"] < 15 else "Krishna",
        "nakshatra": NAKSHATRAS[pp["nakshatra_index"]], "pada": pp["pada"],
        "yoga": YOGA_NAMES[pp["yoga_index"]], "karana": karana_name(pp["karana_index"]),
        "vara": v["vara"], "civil_weekday": v["civil_weekday"],
        "before_sunrise": v["before_sunrise"],
    } == pin["panchang"]
    assert n["mangal_dosha"] == pin["mangal_dosha"]
    assert facts["dasha"]["running"] == pin["running"]
    assert facts["dasha"]["pratyantar"]["current"] == pin["pratyantar_current"]
    assert facts["dasha"]["pratyantar"]["next"] == pin["pratyantar_next"]
    assert facts["saturn_cycles"] == pin["saturn_cycles"]


def test_golden_chart_matches_astrosage_exactly(facts):
    """Everything AstroSage prints exactly: sign, nakshatra, pada, D9 sign,
    D1 and D9 houses, R and C marks, BPHS dignity where AstroSage states one."""
    n = facts["natal"]
    assert {k: v for k, v in _named(n["ascendant"]).items()} == {
        k: AS["ascendant"][k] for k in ("sign", "nakshatra", "pada", "navamsa_sign")}
    dignity_word = {"Exalted": "exalted", "Own": "own sign", "Debilitated": "debilitated"}
    for body, ref in AS["planets"].items():
        p = n["planets"][body]
        assert _named(p) == {k: ref[k] for k in ("sign", "nakshatra", "pada", "navamsa_sign")}, body
        assert (p["house"], p["navamsa_house"]) == (ref["house"], ref["navamsa_house"]), body
        assert p["retrograde"] == ref["retrograde"], body
        assert p["combust"] == ref["combust"], body
        # AstroSage's relation column is friendship-based; the file states BPHS
        # dignity only, so the comparable words must agree and the rest be none.
        assert p["dignity"] == dignity_word.get(ref["relation"]), body


def test_golden_d7_d9_d10_match_astrosages_shodashvarga(facts):
    """AstroSage's Shodashvarga table (page 40): the sign and house of the
    lagna and all nine grahas in D7, D9 and D10 — exact. AstroSage prints
    sign 12 as 0 (Saturn's D7; its house table confirms Pisces)."""
    sv = AS["shodashvarga"]
    n = facts["natal"]
    pts = [n["ascendant"], *(n["planets"][b] for b in sv["columns"][1:])]
    keys = {"D7": ("d7_sign_index", "d7_house"), "D9": ("navamsa_sign_index", "navamsa_house"),
            "D10": ("d10_sign_index", "d10_house")}
    for varga, (sign_key, house_key) in keys.items():
        assert [p[sign_key] + 1 for p in pts] == [x or 12 for x in sv["sign"][varga]], varga
        assert [1, *(p[house_key] for p in pts[1:])] == sv["house"][varga], varga


# Degrees: the Moon (0.5″/s of time), the mean node and the lagna pin the
# CONVENTION (lahiri_vp285, mean node, Thane, IST) and are held to 15″. The
# planets are held to 2′: AstroSage's planetary theory sits up to 112″ (Mars)
# from Swiss Ephemeris here and changes sign over time — not a setting this
# engine can match (README > "AstroSage's planet degrees").
AS_TIGHT = {"Asc": 15.0, "Moon": 15.0, "Rahu": 15.0, "Ketu": 15.0}


def test_golden_chart_degrees_match_astrosage(facts):
    n = facts["natal"]
    got = {"Asc": n["ascendant"]["longitude"],
           **{b: p["longitude"] for b, p in n["planets"].items()}}
    refs = {"Asc": AS["ascendant"], **AS["planets"]}
    for body, ref in refs.items():
        gap = abs((got[body] % 30) - _dms(ref["dms"])) * 3600
        assert gap <= AS_TIGHT.get(body, LOOSE), f"{body} {gap:.1f}″ from AstroSage"


def test_golden_birth_panchang_matches_astrosage(facts):
    n = facts["natal"]
    pp, v = n["panchang"], n["vara"]
    ref = AS["panchang"]
    assert tithi_name(pp["tithi_index"]) == ref["tithi"]
    assert ("Shukla" if pp["tithi_index"] < 15 else "Krishna") == ref["paksha"]
    assert YOGA_NAMES[pp["yoga_index"]] == ref["yoga"]
    assert karana_name(pp["karana_index"]) == ref["karana"]
    assert v["vara"] == ref["vara"] and v["civil_weekday"] == ref["civil_day"]
    rise = vara_at(BIRTH, IST, *THANE).sunrise
    assert abs((rise - _ist("1989-09-23", ref["sunrise"])).total_seconds()) <= 60


def test_golden_dasha_balance_matches_astrosage(facts):
    ref = AS["dasha_balance"]
    b = facts["dasha"]["balance"]
    assert (facts["dasha"]["lord"], b["years"], b["months"], b["days"]) == (
        ref["lord"], ref["years"], ref["months"], ref["days"])


# ── Mangal dosha ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("house", range(1, 13))
def test_mangal_dosha_counts_astrosages_five_houses_from_the_lagna(house):
    # Mars fixed in Gemini (no own sign, no exaltation), Moon and Jupiter
    # placed so neither the Moon rule nor a cancellation can fire.
    mars = 2
    asc = (mars - (house - 1)) % 12
    d = mangal_dosha(asc, mars, (mars + 2) % 12, (mars + 2) % 12)
    assert d["from_lagna"] == {"house": house, "dosha": house in (1, 4, 7, 8, 12)}
    assert d["from_moon"] == {"house": 11, "dosha": False}
    assert d["cancelled_by"] == [] and d["present"] == (house in MANGAL_DOSHA_HOUSES)
    assert d["present_counting_2nd"] == (house in (1, 2, 4, 7, 8, 12))


def test_mangal_dosha_counts_from_the_moon_separately():
    d = mangal_dosha(asc_sign=0, mars_sign=5, moon_sign=2, jupiter_sign=7)   # 6th / 4th
    assert d["from_lagna"]["dosha"] is False and d["from_moon"] == {"house": 4, "dosha": True}
    assert d["present"] is True


def test_mangal_dosha_in_the_2nd_only_counts_under_the_other_rule():
    d = mangal_dosha(asc_sign=1, mars_sign=2, moon_sign=0, jupiter_sign=4)   # 2nd / 3rd
    assert (d["from_lagna"], d["from_moon"]) == (
        {"house": 2, "dosha": False}, {"house": 3, "dosha": False})
    assert d["present"] is False and d["present_counting_2nd"] is True


@pytest.mark.parametrize(("mars", "jupiter", "reasons"), [
    (0, 3, ["own_sign"]),                  # Aries
    (7, 3, ["own_sign", "jupiter_aspect"]),  # Scorpio, 5th from Jupiter in Cancer
    (9, 1, ["exalted", "jupiter_aspect"]),   # Capricorn, 9th from Jupiter in Taurus
    (5, 5, ["with_jupiter"]),
    (5, 1, ["jupiter_aspect"]),            # Virgo is the 5th from Taurus
    (5, 11, ["jupiter_aspect"]),           # 7th from Pisces
    (5, 9, ["jupiter_aspect"]),            # 9th from Capricorn
    (5, 2, []), (5, 4, []), (5, 8, []),    # 4th, 2nd, 10th from Jupiter: no aspect
])
def test_mangal_dosha_cancellations_are_exact_sign_facts(mars, jupiter, reasons):
    asc = mars  # Mars in the 1st: the dosha is there unless cancelled
    d = mangal_dosha(asc, mars, mars, jupiter)
    assert d["cancelled_by"] == reasons
    assert d["present"] is d["present_counting_2nd"] is (not reasons)


def test_golden_mangal_dosha_is_astrosages(facts):
    """AstroSage's Manglik report: Mars 2nd from the lagna, 4th from the Moon;
    dosha in the Moon chart, not in the lagna chart. Same houses, same
    verdicts, same rule. Counting the 2nd as well would add the lagna
    placement; the overall result would stay "present"."""
    d = facts["natal"]["mangal_dosha"]
    ref = AS["manglik"]
    assert (d["from_lagna"]["house"], d["from_moon"]["house"]) == (
        ref["from_lagna_house"], ref["from_moon_house"])
    assert (d["from_lagna"]["dosha"], d["from_moon"]["dosha"]) == (
        ref["lagna_chart"], ref["moon_chart"])
    assert d["present"] and d["present_counting_2nd"] and d["cancelled_by"] == []


# ── Saturn cycles: Sade Sati and Dhaiya ─────────────────────────────────────
SADESATI = _load("astrosage_sadesati_golden_1.json")
IST_OFFSET = timedelta(hours=5, minutes=30)


@pytest.fixture(scope="module")
def saturn_runs_1990_2100():
    """(sign, IST entry date, IST exit date) for every Saturn sign stay."""
    start = local_to_utc(datetime(1990, 1, 1), IST)
    ev = ingresses(start, (date(2100, 1, 1) - date(1990, 1, 1)).days, bodies=("Saturn",))
    runs = []
    for a, b in zip(ev, ev[1:], strict=False):
        runs.append((a["to_sign_index"], (_utc_from_ms(a["utc_ms"]) + IST_OFFSET).date(),
                     (_utc_from_ms(b["utc_ms"]) + IST_OFFSET).date()))
    return runs


def test_saturn_stays_match_astrosages_sadesati_report(saturn_runs_1990_2100):
    """Every AstroSage Sade Sati / Small Panoti row is one of our Saturn sign
    stays — same sign, same order, nothing missing or extra — with entry and
    exit within a day. AstroSage's Saturn sits up to ~1′ from Swiss, which
    near a station moves an instant across midnight; measured over 43 rows:
    28 entries and 27 exits identical, the rest exactly one day apart."""
    moon = SIGNS.index(SADESATI["moon_sign"])
    rows = [r for r in SADESATI["rows"] if r["start"] < "2099-12-01"]
    ours = [r for r in saturn_runs_1990_2100
            if house_from(r[0], moon) in (12, 1, 2, 4, 8) and r[1] >= date(1990, 3, 1)]
    assert len(ours) == len(rows) == 43
    same = 0
    for (sign, enter, leave), ref in zip(ours, rows, strict=True):
        assert SIGNS[sign] == ref["sign"], ref
        d_in = (enter - date.fromisoformat(ref["start"])).days
        # AstroSage's end is the last day in the sign; ours the day Saturn leaves
        d_out = (leave - date.fromisoformat(ref["end"])).days
        assert abs(d_in) <= 1 and abs(d_out) <= 1, (ref, enter, leave)
        same += d_in == 0
        phase = {12: "Rising", 1: "Peak", 2: "Setting"}.get(house_from(sign, moon))
        assert phase == ref["phase"] and (ref["kind"] == "Sade Sati") == (phase is not None)
    assert same >= 28


def test_golden_saturn_cycles_as_of_2026(facts):
    """As of 2026-10-19 no cycle runs for a Gemini Moon (Saturn is in Pisces,
    the 10th); the next Sade Sati is AstroSage's rows 16–19 to the day."""
    c = {x["kind"]: x for x in facts["saturn_cycles"]}
    assert [x["state"] for x in facts["saturn_cycles"]] == ["none", "none", "none"]
    sade = c["sade_sati"]
    assert (sade["start"], sade["end"]) == ("2029-08-08", "2036-08-27")
    assert [(SIGNS[s["sign_index"]], s["phase"]) for s in sade["segments"]] == [
        ("Taurus", "rising"), ("Taurus", "rising"), ("Gemini", "peak"), ("Cancer", "setting")]
    assert [SIGNS[i] for i in sade["signs"]] == ["Taurus", "Gemini", "Cancer"]
    assert [SIGNS[i] for i in c["kantaka"]["signs"]] == ["Virgo"]
    assert [SIGNS[i] for i in c["ashtama"]["signs"]] == ["Capricorn"]
    assert c["kantaka"]["start"] < c["ashtama"]["start"]


def _cycles_on(day: date, moon_sign: int) -> dict:
    return {c["kind"]: c for c in saturn_cycles(moon_sign, saturn_changes(day), day)}


def test_saturn_cycle_states_running_paused_none():
    gemini = 2
    # 2003-02-15: Saturn had slipped back into Taurus — Sade Sati RISING again.
    assert (_cycles_on(date(2003, 2, 15), gemini)["sade_sati"]["state"],
            _cycles_on(date(2003, 2, 15), gemini)["sade_sati"]["phase"]) == ("running", "rising")
    # 2006-12-01: Saturn in Leo between two Cancer stays — paused, not over.
    c = _cycles_on(date(2006, 12, 1), gemini)["sade_sati"]
    assert (c["state"], c["phase"], c["start"], c["end"]) == (
        "paused", None, "2000-06-07", "2007-07-16")
    # 2010-06-01: Kantaka (Virgo) is running; Sade Sati is not.
    c = _cycles_on(date(2010, 6, 1), gemini)
    assert c["kantaka"]["state"] == "running" and c["sade_sati"]["state"] == "none"


def test_saturn_cycle_state_is_read_at_noon_ist():
    """Saturn enters Taurus (the 12th from a Gemini Moon) at 15:36 IST on
    2029-08-08: at 12:00 IST that day the Sade Sati has not begun — it is the
    NEXT one, starting that very date — and on the 9th it is running."""
    gemini = 2
    on_the_day = _cycles_on(date(2029, 8, 8), gemini)["sade_sati"]
    assert (on_the_day["state"], on_the_day["start"]) == ("none", "2029-08-08")
    next_day = _cycles_on(date(2029, 8, 9), gemini)["sade_sati"]
    assert (next_day["state"], next_day["phase"]) == ("running", "rising")


def test_saturn_changes_equal_a_daily_scan():
    """The adaptive walk over 42 years equals a brute-force scan of Saturn's
    sign at the end of every IST day: same days, same signs."""
    day = date(2026, 10, 19)
    sat = saturn_changes(day)
    got = [((_utc_from_ms(c["utc_ms"]) + IST_OFFSET).date(), c["to_sign_index"])
           for c in sat["changes"]]
    first = day - timedelta(days=SATURN_LOOKBACK_DAYS)   # the window's first IST day
    scan, prev = [], sat["start_sign_index"]
    for k in range(SATURN_LOOKBACK_DAYS + SATURN_LOOKAHEAD_DAYS):
        d = first + timedelta(days=k)
        end_of_day = local_to_utc(datetime.combine(d, datetime.max.time()), IST)
        cur = sign_index(sidereal_longitude("Saturn", end_of_day))
        if cur != prev:
            scan.append((d, cur))
        prev = cur
    assert got == scan and len(got) >= 30


def test_saturn_cycles_never_run_past_their_window():
    """Every Moon sign, as-of dates every 15 days over 1960–2060: the 10-year
    look-back and 32-year look-ahead always hold the current or next cycle
    whole (saturn_cycles raises otherwise). Sliced from one long walk."""
    t0 = local_to_utc(datetime(1949, 1, 1), IST)
    long = ingresses(t0, (date(2096, 1, 1) - date(1949, 1, 1)).days, bodies=("Saturn",))
    sign0 = sign_index(sidereal_longitude("Saturn", t0))
    day, checked = date(1960, 1, 1), 0
    while day < date(2060, 1, 1):
        w0 = (local_to_utc(datetime.combine(day, datetime.min.time()), IST)
              - timedelta(days=SATURN_LOOKBACK_DAYS))
        w1 = w0 + timedelta(days=SATURN_LOOKBACK_DAYS + SATURN_LOOKAHEAD_DAYS)
        before = [e for e in long if _utc_from_ms(e["utc_ms"]) < w0]
        sat = {"start_sign_index": before[-1]["to_sign_index"] if before else sign0,
               "changes": [{"utc_ms": e["utc_ms"], "to_sign_index": e["to_sign_index"]}
                           for e in long if w0 <= _utc_from_ms(e["utc_ms"]) <= w1]}
        for moon in range(12):
            for c in saturn_cycles(moon, sat, day):
                assert c["start"] <= c["end"] and c["segments"]
                if c["state"] == "none":   # the NEXT cycle: not begun (may begin later today)
                    assert c["start"] >= day.isoformat()
                else:                          # the CURRENT one: today lies inside it
                    assert c["start"] <= day.isoformat() <= c["end"]
                checked += 1
        day += timedelta(days=15)
    assert checked > 80_000


def test_whole_sign_houses_count_from_the_lagna(facts):
    n = facts["natal"]
    asc = n["ascendant"]["sign_index"]
    for p in n["planets"].values():
        assert p["house"] == house_from(p["sign_index"], asc)
    assert house_from(asc, asc) == 1 and house_from((asc + 11) % 12, asc) == 12


def test_refuses_above_the_arctic_limit():
    with pytest.raises(ValueError):
        natal_facts(BIRTH, "Europe/Oslo", ARCTIC_LIMIT + 0.5, 18.96)
