"""Golden tests: ascendant (lagna) + houses vs DrikPanchang and AstroSage.

Reference data: tests/golden/lagna_reference.json (8 DrikPanchang lagna tables
across latitudes -41.3..61.2 and years 1943-2026, + 4 AstroSage sunrise-lagna
degree anchors). Full analysis of the reference sites' systematics — the
TT-frame discovery, AstroSage's arithmetic-table sawtooth, DrikPanchang's
per-city constants — lives in docs/ASCENDANT.md.

Tolerances, and their defence (docs/ASCENDANT.md > Tolerances):
* SIGN agreement everywhere except within BOUNDARY_TOL of a boundary — the
  quantity the product will consume (A4).
* Boundary times: |engine - reference| <= 180 s globally, <= 120 s for the
  Indian/low-latitude tables. The references themselves are only defined to
  this level: +-30 s display rounding, a ~deltaT (26-69 s) time-frame
  ambiguity, and unexplained per-city constants (<= 158 s, worst at 61 N).
  AstroSage's own lagna table deviates from its own exact sunrise anchor by
  up to ~2.5 min, so no public reference pins a boundary tighter than this.
* AstroSage sunrise-lagna DEGREES: evaluated at displayed instant + deltaT
  (their TT frame), modern anchors agree to well under 2 arc-min — measured
  +10" (2026) and +65" (1989) with the library ayanamsa; asserted <= 90
  arc-sec (~6 s of birth time). Historical (pre-1972) anchors carry an
  additional unexplained site-side shift; asserted <= 10 arc-min
  (sign-level exact regardless).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

import pytest
import swisseph as swe

from engine.chart import (
    ascendant_sidereal,
    chart_from_local,
    compute_chart,
)
from engine.ephemeris import DEFAULT_AYANAMSA, julday_utc
from engine.timezones import local_to_utc, resolve_tz

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "lagna_reference.json")

SIGN0 = {
    "Aries": 0.0, "Taurus": 30.0, "Gemini": 60.0, "Cancer": 90.0,
    "Leo": 120.0, "Virgo": 150.0, "Libra": 180.0, "Scorpio": 210.0,
    "Sagittarius": 240.0, "Capricorn": 270.0, "Aquarius": 300.0, "Pisces": 330.0,
}

BOUNDARY_TOL = 180.0        # seconds, all tables
BOUNDARY_TOL_INDIA = 120.0  # seconds, Indian + low-latitude tables
EDGE_MARGIN = 240.0         # seconds inside a window edge for sign sampling
ANCHOR_TOL_MODERN = 90.0    # arc-sec, AstroSage sunrise anchors post-1972
ANCHOR_TOL_HISTORIC = 600.0  # arc-sec (10'), pre-1972 anchors

INDIA_TABLES = {"pune-1989", "kolkata-1943", "chennai-1965", "srinagar-1975", "singapore-2000"}


@pytest.fixture(scope="session")
def golden() -> dict:
    with open(GOLDEN) as f:
        return json.load(f)


def _local(date_str: str, hhmm: str) -> datetime:
    """Parse a table time; hours >= 24 roll into the next civil day."""
    y, mo, d = (int(x) for x in date_str.split("-"))
    parts = [int(x) for x in hhmm.split(":")]
    h, m = parts[0], parts[1]
    s = parts[2] if len(parts) > 2 else 0
    days, h = divmod(h, 24)
    return datetime(y, mo, d, h, m, s) + timedelta(days=days)


def _asc(local: datetime, tz: str, lat: float, lon: float, ayanamsa: str = "lahiri"):
    return ascendant_sidereal(local_to_utc(local, tz), lat, lon, ayanamsa=ayanamsa)


def _find_crossing(target: float, approx: datetime, tz: str, lat: float, lon: float):
    """Root-find the instant the ascendant crosses `target` near `approx`."""
    lo, hi = approx - timedelta(minutes=8), approx + timedelta(minutes=8)

    def f(t: datetime) -> float:
        a = _asc(t, tz, lat, lon).longitude
        return (a - target + 180) % 360 - 180

    if f(lo) > 0 or f(hi) < 0:
        return None
    for _ in range(34):
        mid = lo + (hi - lo) / 2
        if f(mid) < 0:
            lo = mid
        else:
            hi = mid
    return lo + (hi - lo) / 2


def _windows(table: dict) -> list[tuple[str, datetime, datetime]]:
    """(sign, begin, end) for the 11 fully-bounded windows of a table."""
    rows = [(sign, _local(table["date"], t)) for sign, t in table["begins"].items()]
    rows.sort(key=lambda r: r[1])
    return [
        (rows[i][0], rows[i][1], rows[i + 1][1]) for i in range(len(rows) - 1)
    ]


# ── DrikPanchang tables: signs ─────────────────────────────────────────────
def test_drik_window_signs(golden):
    """Inside every reference window (4 min off the edges), signs agree."""
    checked = 0
    for table in golden["drik_tables"]:
        lat, lon, tz = table["lat"], table["lon"], table["tz"]
        for sign, begin, end in _windows(table):
            samples = [begin + (end - begin) / 2]
            if (end - begin).total_seconds() > 2 * EDGE_MARGIN:
                samples += [
                    begin + timedelta(seconds=EDGE_MARGIN),
                    end - timedelta(seconds=EDGE_MARGIN),
                ]
            for t in samples:
                got = _asc(t, tz, lat, lon).sign
                assert got == sign, (
                    f"{table['id']} {t}: engine {got} != reference {sign}"
                )
                checked += 1
    assert checked >= 250  # 8 tables x 11 windows x up to 3 samples


# ── DrikPanchang tables: boundary times ────────────────────────────────────
def test_drik_boundary_times(golden):
    """Every reference ingress is reproduced within the defended tolerance."""
    worst = 0.0
    for table in golden["drik_tables"]:
        lat, lon, tz = table["lat"], table["lon"], table["tz"]
        tol = BOUNDARY_TOL_INDIA if table["id"] in INDIA_TABLES else BOUNDARY_TOL
        for sign, begins in table["begins"].items():
            ref = _local(table["date"], begins)
            eng = _find_crossing(SIGN0[sign], ref, tz, lat, lon)
            assert eng is not None, f"{table['id']} {sign}: no crossing near {ref}"
            delta = abs((eng - ref).total_seconds())
            worst = max(worst, delta)
            assert delta <= tol, (
                f"{table['id']} {sign}: engine {eng} vs reference {ref} "
                f"({delta:.0f}s > {tol:.0f}s)"
            )
    assert worst > 0  # the comparison genuinely ran


# ── AstroSage sunrise-lagna degree anchors ─────────────────────────────────
def test_astrosage_sunrise_anchor_degrees(golden):
    """AstroSage's exact lagna degrees, evaluated in their TT frame."""
    for anchor in golden["astrosage_sunrise_anchors"]:
        local = _local(anchor["date"], anchor["sunrise"])
        utc = local_to_utc(local, anchor["tz"])
        delta_t_sec = swe.deltat(julday_utc(utc)) * 86400
        asc = ascendant_sidereal(
            utc + timedelta(seconds=delta_t_sec),
            anchor["lat"],
            anchor["lon"],
            ayanamsa=DEFAULT_AYANAMSA,
        )
        d, m, s = anchor["longitude_dms"]
        ref = d + m / 60 + s / 3600
        delta_asec = abs((asc.longitude - ref + 180) % 360 - 180) * 3600
        tol = ANCHOR_TOL_MODERN if anchor["era"] == "modern" else ANCHOR_TOL_HISTORIC
        assert delta_asec <= tol, (
            f"{anchor['date']}: engine {asc.longitude:.5f} vs AstroSage {ref:.5f} "
            f"({delta_asec:.0f}\" > {tol:.0f}\")"
        )
        assert asc.sign == anchor["sign"]


# ── Hard case: birth minutes from a lagna boundary ─────────────────────────
def test_boundary_flip_within_minutes(golden):
    """4 min either side of a reference ingress lands on opposite signs."""
    pune = next(t for t in golden["drik_tables"] if t["id"] == "pune-1989")
    ingress = _local("1989-09-23", pune["begins"]["Libra"])  # 08:06
    before = _asc(ingress - timedelta(minutes=4), pune["tz"], pune["lat"], pune["lon"])
    after = _asc(ingress + timedelta(minutes=4), pune["tz"], pune["lat"], pune["lon"])
    assert before.sign == "Virgo"
    assert after.sign == "Libra"


# ── Hard case: war-time DST flows through the chart ────────────────────────
def test_war_time_dst_flows_through():
    """A 1943 Kolkata birth resolves at UTC+06:30, and it is load-bearing."""
    local = datetime(1943, 6, 15, 7, 0)
    offset = local.replace(tzinfo=resolve_tz("Asia/Kolkata")).utcoffset()
    assert offset == timedelta(hours=6, minutes=30)

    dst = chart_from_local(local, "Asia/Kolkata", 22.56263, 88.36304)
    assert dst.ascendant.sign == "Gemini"  # drik window 05:55-08:08

    flat = chart_from_local(local, "+05:30", 22.56263, 88.36304)
    hour_apart = abs(
        (flat.ascendant.longitude - dst.ascendant.longitude + 180) % 360 - 180
    )
    assert hour_apart > 10  # one wall-clock hour of ascendant motion


# ── Hard case: high latitude ───────────────────────────────────────────────
def test_polar_latitude_whole_sign_survives():
    """69.6 N (refused by DrikPanchang): Whole Sign works, Placidus is None."""
    chart = compute_chart(datetime(2010, 6, 21, 10, 0), 69.6492, 18.9553)
    assert 0 <= chart.ascendant.longitude < 360
    assert len(set(chart.house_signs)) == 12
    assert chart.placidus_cusps is None
    assert len(chart.placements) == 9


def test_subpolar_placidus_present():
    """Anchorage (61.2 N) still gets Placidus cusps."""
    chart = chart_from_local(
        datetime(2015, 7, 4, 12, 0), "America/Anchorage", 61.21806, -149.90028
    )
    assert chart.placidus_cusps is not None
    assert len(chart.placidus_cusps) == 12


# ── The golden chart, fully placed ─────────────────────────────────────────
def test_golden_chart_placements():
    """1989-09-23 04:47 IST, Pune — the chart every other golden pins."""
    chart = chart_from_local(datetime(1989, 9, 23, 4, 47), "+05:30", 18.5204, 73.8567)
    asc = chart.ascendant
    assert asc.sign == "Leo"
    assert asc.sign_degrees == pytest.approx(12.5266, abs=0.01)
    assert asc.nakshatra.name == "Magha"
    assert asc.nakshatra.pada == 4
    assert chart.house_signs[0] == "Leo"
    assert chart.house_signs[1] == "Virgo"

    # Whole Sign: house = sign distance from the lagna sign + 1.
    assert chart.placements["Sun"].sign == "Virgo"
    assert chart.placements["Sun"].house == 2
    assert chart.placements["Moon"].sign == "Gemini"
    assert chart.placements["Moon"].house == 11
    assert chart.placements["Moon"].nakshatra.name == "Ardra"

    # Mean nodes are always retrograde; Ketu opposes Rahu exactly.
    assert chart.placements["Rahu"].retrograde
    assert chart.placements["Ketu"].retrograde
    opposition = (
        chart.placements["Ketu"].position.longitude
        - chart.placements["Rahu"].position.longitude
    ) % 360
    assert opposition == pytest.approx(180.0, abs=1e-9)

    # Internal consistency: Placidus cusp 1 IS the ascendant; cusp 10 the MC.
    assert chart.placidus_cusps is not None
    assert chart.placidus_cusps[0] == pytest.approx(asc.longitude, abs=1e-6)
    assert chart.placidus_cusps[9] == pytest.approx(chart.midheaven, abs=1e-6)


def test_ascendant_speed_one_degree_per_four_minutes():
    """The number that makes birth time load-bearing: ~1 deg / 4 min."""
    base = local_to_utc(datetime(1989, 9, 23, 4, 47), "+05:30")
    a0 = ascendant_sidereal(base, 18.5204, 73.8567).longitude
    a1 = ascendant_sidereal(base + timedelta(minutes=4), 18.5204, 73.8567).longitude
    moved = (a1 - a0) % 360
    assert 0.7 < moved < 1.4


def test_chart_requires_explicit_timezone():
    """No default zone: a silently-wrong timezone is a silently-wrong lagna."""
    with pytest.raises(ValueError):
        chart_from_local(datetime(1989, 9, 23, 4, 47), "IST?", 18.5, 73.8)
