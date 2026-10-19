"""Golden tests: Vimshottari dasha for births OUTSIDE India (reshape B1).

The bug these pin: every dasha caller read the birth wall clock as IST. For a
New York birth that samples the Moon 9½ hours early — wrong pada, and a Saturn
balance of 16Y 3M instead of 9Y 7M, so every period was ~7 years off. The fix
is `positions_from_local(birth, zone)`: the zone's offset is resolved AT the
birth instant (DST and historical offsets included), and only the Moon's
sampling instant changes — the timeline stays in the birth place's calendar.

Three layers, strongest first (see tests/golden/dasha_abroad.json):
  * tz facts written by hand (UTC instant, offset), independent of the engine;
  * the AstroSage reference — skipped, visibly, until Rohan supplies it;
  * engine-pinned values — a regression guard, not an external reference.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, timedelta

import pytest

from engine.positions import positions_from_ist, positions_from_local, sidereal_positions
from engine.timezones import local_to_utc, offset_minutes_at
from engine.vimshottari import compute_dasha, rounded_table

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "dasha_abroad.json")

with open(GOLDEN) as _f:
    CASES = json.load(_f)["cases"]

IDS = [c["label"] for c in CASES]


def _birth(case: dict) -> datetime:
    return datetime.fromisoformat(f"{case['dob']}T{case['time']}")


def _dasha(case: dict):
    birth = _birth(case)
    moon = positions_from_local(birth, case["zone"])["Moon"].longitude
    return compute_dasha(moon, birth, levels=2)


def test_golden_covers_three_births_abroad_for_astrosage():
    asked = [c for c in CASES if c["ask_astrosage"]]
    assert len(asked) >= 3
    assert all(c["zone"] != "Asia/Kolkata" for c in asked)
    # At least one DST birth, one no-DST birth.
    assert {c["zone"] for c in asked} >= {"America/New_York", "Asia/Dubai"}


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_zone_resolves_to_the_hand_written_utc_instant(case):
    birth = _birth(case)
    assert offset_minutes_at(case["zone"], birth) == case["utc_offset_minutes"]
    expected = datetime.fromisoformat(case["utc"]).replace(tzinfo=UTC)
    assert local_to_utc(birth, case["zone"]) == expected


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_moon_is_sampled_at_the_true_birth_instant(case):
    # Independent of timezones.py: the hand-written UTC goes straight to Swiss.
    utc = datetime.fromisoformat(case["utc"]).replace(tzinfo=UTC)
    zoned = positions_from_local(_birth(case), case["zone"])["Moon"].longitude
    assert zoned == sidereal_positions(utc)["Moon"].longitude


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_the_ist_reading_was_wrong(case):
    # Falsification: if the zone were still ignored, these would be equal.
    birth = _birth(case)
    ist = compute_dasha(positions_from_ist(birth)["Moon"].longitude, birth, levels=2)
    assert ist.balance.total_days != pytest.approx(_dasha(case).balance.total_days, abs=1)


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_engine_pinned_values(case):
    result = _dasha(case)
    pin = case["engine_pinned"]
    assert (result.nakshatra.name, result.nakshatra.pada, result.nakshatra.lord) == (
        pin["nakshatra"], pin["pada"], pin["lord"]
    )
    b = result.balance
    assert {"years": b.years, "months": b.months, "days": b.days} == pin["balance"]
    got = [{"lord": m.lord, "end": m.end.isoformat()}
           for m in rounded_table(result, _birth(case), blocks=len(pin["maha"]))]
    assert got == pin["maha"]


@pytest.mark.parametrize(
    "case", [c for c in CASES if c["ask_astrosage"]],
    ids=[c["label"] for c in CASES if c["ask_astrosage"]],
)
def test_matches_astrosage(case):
    ref = case["astrosage"]
    if ref is None:
        pytest.skip("awaiting AstroSage reference values from Rohan (see dasha_abroad.json)")
    result = _dasha(case)
    assert (result.nakshatra.name, result.nakshatra.pada) == (ref["nakshatra"], ref["pada"])
    b = result.balance
    assert {"years": b.years, "months": b.months, "days": b.days} == ref["balance"]
    # Same tolerance the India golden earns: every maha boundary within ±1 day.
    for maha, end in zip(result.mahas, ref["maha_ends"], strict=False):
        delta = abs(maha.end.date() - date.fromisoformat(end))
        assert delta <= timedelta(days=1), f"{maha.lord} ends {maha.end.date()} vs {end}"
