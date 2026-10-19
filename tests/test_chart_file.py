"""Golden tests: the chart file's facts (reshape B2–B4, engine/chart_file.py).

Strongest evidence first:

  * EXTERNAL references, fetched — never typed from memory:
      - AstroSage's planetary positions at sunrise and the day's panchang
        elements with their end times (astrosage_sky_2026_10_19.json);
      - DrikPanchang's slow-planet ingress dates/times for Oct 2026 – Dec 2027
        (drik_ingress_2026_2027.json);
      - DrikPanchang's Pune day panchang for the golden birth date and nine
        other days (drik_panchang.json, already the panchang golden).
  * CLASSICAL RULES restated independently of the code under test: the D9
    movable/fixed/dual rule, the BPHS dignity table, the combustion orbs.
  * STRUCTURAL invariants: pratyantar rows tile their antar exactly; dasha
    rows are contiguous; an ingress really is a sign change.
  * ENGINE-PINNED values for the golden chart (chart_file_rohan.json) — a
    regression guard, not a reference; its AstroSage slot is skipped, visibly,
    until Rohan reads the chart off AstroSage.
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
    OWN_SIGNS,
    SIGN_LORDS,
    _utc_from_ms,
    chart_file_facts,
    dasha_facts,
    dignity,
    house_from,
    ingresses,
    is_combust,
    natal_facts,
    navamsa_sign,
    separation,
    sign_index,
    sky_facts,
)
from engine.ephemeris import DRIKPANCHANG_AYANAMSA
from engine.panchang import YOGA_NAMES, karana_name, panchang_at, tithi_name, vara_at
from engine.positions import SIGNS, sidereal_positions
from engine.timezones import local_to_utc
from engine.vimshottari import NAKSHATRAS, compute_dasha, nakshatra_of, rounded_pratyantar

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")
IST = "Asia/Kolkata"

BIRTH = datetime(1989, 9, 23, 4, 47)
PUNE = (18.5204, 73.8567)
AS_OF = date(2026, 10, 19)


def _load(name: str) -> dict:
    with open(os.path.join(GOLDEN_DIR, name)) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def facts() -> dict:
    return chart_file_facts(BIRTH, IST, *PUNE, AS_OF)


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
    """04:47 IST, Pune, 1989-09-23 — before that morning's 06:24 sunrise, so
    the elements are the ones DrikPanchang lists as prevailing at sunrise and
    the vara is the PREVIOUS day's (Friday)."""
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


def test_sky_reads_today_at_local_noon_and_scans_from_local_midnight():
    sky = sky_facts(date(2026, 10, 19), "America/New_York")
    assert _utc_from_ms(sky["instant_ms"]) == datetime(2026, 10, 19, 16, 0, tzinfo=UTC)  # EDT
    assert _utc_from_ms(sky["window_start_ms"]) == datetime(2026, 10, 19, 4, 0, tzinfo=UTC)
    assert all(sky["window_start_ms"] <= e["utc_ms"] for e in sky["ingresses"])


# ── Pratyantar and the dasha section ────────────────────────────────────────
@pytest.fixture(scope="module")
def dasha():
    moon = natal_facts(BIRTH, IST, *PUNE)["planets"]["Moon"]["longitude"]
    return compute_dasha(moon, BIRTH, levels=3, cycles=2), moon


def test_pratyantars_tile_every_antar_exactly(dasha):
    from engine.vimshottari import rounded_table
    res, _ = dasha
    for mi, maha in enumerate(rounded_table(res, BIRTH, blocks=9)):
        start = maha.start
        for ai, (lord, end) in enumerate(maha.antar):
            rows = rounded_pratyantar(res, mi, ai)
            assert rows[0].start == start and rows[-1].end == end
            assert rows[0].lord == lord and len(rows) == 9
            assert all(a.end == b.start for a, b in zip(rows, rows[1:], strict=False))
            start = end


def test_pratyantar_needs_the_third_level(dasha):
    _, moon = dasha
    with pytest.raises(ValueError):
        rounded_pratyantar(compute_dasha(moon, BIRTH, levels=2), 0, 0)


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


def test_maha_ends_still_match_astrosage(facts):
    """dasha_facts presents the AstroSage golden's own boundaries (±1 day, the
    tolerance test_vimshottari.py holds)."""
    ref = _load("astrosage_dasha.json")["maha"]
    for got, want in zip(facts["dasha"]["mahas"], ref, strict=False):  # ref has 10 blocks
        assert got["lord"] == want["lord"]
        gap = abs(date.fromisoformat(got["end"]) - date.fromisoformat(want["end"]))
        assert gap <= timedelta(days=1), (got, want)


def test_running_period_boundaries_are_start_inclusive(dasha):
    res, moon = dasha
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


# ── The golden chart, engine-pinned (+ AstroSage, pending) ──────────────────
ROHAN = _load("chart_file_rohan.json")


def _named(p: dict) -> dict:
    return {"sign": SIGNS[p["sign_index"]], "nakshatra": NAKSHATRAS[p["nakshatra_index"]],
            "pada": p["pada"], "navamsa_sign": SIGNS[p["navamsa_sign_index"]]}


def test_golden_chart_engine_pinned(facts):
    pin = ROHAN["engine_pinned"]
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
    assert facts["dasha"]["running"] == pin["running"]
    assert facts["dasha"]["pratyantar"]["current"] == pin["pratyantar_current"]
    assert facts["dasha"]["pratyantar"]["next"] == pin["pratyantar_next"]


def test_golden_chart_matches_astrosage(facts):
    ref = ROHAN["astrosage"]
    if ref is None:
        pytest.skip("awaiting AstroSage planet table / D9 / birth panchang from Rohan "
                    "(see chart_file_rohan.json)")
    n = facts["natal"]
    # Expected shape once filled: {"ascendant": {sign, nakshatra, pada, navamsa_sign},
    #   "planets": {body: {sign, nakshatra, pada, navamsa_sign[, retrograde][, combust]}},
    #   "panchang": {tithi, paksha, yoga, karana[, vara]}} — only keys AstroSage shows.
    for key, want in ref["ascendant"].items():
        assert _named(n["ascendant"])[key] == want, ("ascendant", key)
    for body, fields in ref["planets"].items():
        p = n["planets"][body]
        got = {**_named(p), "retrograde": p["retrograde"], "combust": p["combust"]}
        for key, want in fields.items():
            assert got[key] == want, (body, key)
    pp = n["panchang"]
    got = {"tithi": tithi_name(pp["tithi_index"]),
           "paksha": "Shukla" if pp["tithi_index"] < 15 else "Krishna",
           "yoga": YOGA_NAMES[pp["yoga_index"]], "karana": karana_name(pp["karana_index"]),
           "vara": n["vara"]["vara"]}
    for key, want in ref["panchang"].items():
        assert got[key] == want, ("panchang", key)


def test_whole_sign_houses_count_from_the_lagna(facts):
    n = facts["natal"]
    asc = n["ascendant"]["sign_index"]
    for p in n["planets"].values():
        assert p["house"] == house_from(p["sign_index"], asc)
    assert house_from(asc, asc) == 1 and house_from((asc + 11) % 12, asc) == 12


def test_refuses_above_the_arctic_limit():
    with pytest.raises(ValueError):
        natal_facts(BIRTH, "Europe/Oslo", ARCTIC_LIMIT + 0.5, 18.96)
