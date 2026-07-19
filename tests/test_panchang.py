"""Golden tests: panchang + choghadiya vs DrikPanchang (Pune).

Tolerances per Prompt B: names exact; element end times ±2 min;
sunrise/sunset ±1 min. Choghadiya/kaal windows ±2 min (they derive from
sunrise/sunset, so they inherit the ±1 min there).

Conventions these tests prove (see engine/panchang.py + README):
* sunrise/sunset = upper limb + refraction (Hindu-udaya is ~4 min off);
* panchang ayanamsa = plain Lahiri (VP285 — AstroSage's dasha flavour —
  drifts ~+0.7 min here);
* a residual systematic ~+1 min on tithi/karana ends (ayanamsa-independent,
  likely their Moon theory / display truncation) — inside tolerance, reported
  in README > Known deviations.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timedelta

import pytest

from engine.choghadiya import (
    day_choghadiya,
    gulika_kaal,
    night_choghadiya,
    rahu_kaal,
    yamaganda_kaal,
)
from engine.panchang import compute_panchang

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "drik_panchang.json")

RISE_SET_TOL = 1.0   # minutes
END_TOL = 2.0        # minutes
WINDOW_TOL = 2.0     # minutes


@pytest.fixture(scope="session")
def golden() -> dict:
    with open(GOLDEN) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def computed(golden):
    """Panchang per golden day, computed once."""
    lat, lon = golden["location"]["lat"], golden["location"]["lon"]
    return {
        day["date"]: compute_panchang(date.fromisoformat(day["date"]), lat, lon)
        for day in golden["days"]
    }


def _mins(a: datetime, b: datetime) -> float:
    return abs((a - b).total_seconds()) / 60


def _local(day: str, hhmm: str) -> datetime:
    return datetime.combine(date.fromisoformat(day), time.fromisoformat(hhmm))


def _nearest(a: datetime, day: date, hhmm: str) -> float:
    """Minutes from `a` to hh:mm on whichever adjacent day is closest."""
    return min(
        _mins(a, datetime.combine(day + timedelta(days=k), time.fromisoformat(hhmm)))
        for k in (-1, 0, 1)
    )


# ── Sunrise / sunset (±1 min) ───────────────────────────────────────────────
def test_sunrise_sunset_within_one_minute(golden, computed):
    for day in golden["days"]:
        p = computed[day["date"]]
        assert _mins(p.sunrise, _local(day["date"], day["sunrise"])) <= RISE_SET_TOL, (
            f"{day['date']} sunrise {p.sunrise:%H:%M:%S} vs {day['sunrise']}"
        )
        assert _mins(p.sunset, _local(day["date"], day["sunset"])) <= RISE_SET_TOL, (
            f"{day['date']} sunset {p.sunset:%H:%M:%S} vs {day['sunset']}"
        )


# ── Elements: names exact, ends ±2 min ──────────────────────────────────────
@pytest.mark.parametrize("category", ["tithi", "nakshatra", "yoga", "karana"])
def test_elements_match_golden(golden, computed, category):
    for day in golden["days"]:
        p = computed[day["date"]]
        ours = getattr(p, category)
        for i, g in enumerate(day[category]):
            assert i < len(ours), f"{day['date']} {category}[{i}] missing ({g['name']})"
            assert ours[i].name == g["name"], (
                f"{day['date']} {category}[{i}] {ours[i].name} != {g['name']}"
            )
            if g["end"]:
                delta = _mins(ours[i].end, datetime.fromisoformat(g["end"]))
                assert delta <= END_TOL, (
                    f"{day['date']} {category} {g['name']} end "
                    f"{ours[i].end:%H:%M:%S} vs {g['end']} (Δ{delta:.1f}m)"
                )


def test_paksha_and_weekday(golden, computed):
    for day in golden["days"]:
        p = computed[day["date"]]
        assert p.paksha == day["paksha"], f"{day['date']} paksha"
        assert p.weekday == day["weekday"]
        assert p.waxing == (day["paksha"] == "Shukla")
        assert 0.0 <= p.phase_fraction < 1.0


def test_full_night_nakshatra_extends_past_next_sunrise(golden, computed):
    # 2026-06-05: DrikPanchang prints "Shravana upto Full Night".
    p = computed["2026-06-05"]
    assert p.nakshatra[0].name == "Shravana"
    assert p.nakshatra[0].end > p.next_sunrise


def test_element_chains_are_contiguous(computed):
    # Each element's end is the next one's start (exact solver invariant).
    for p in computed.values():
        for cat in ("tithi", "nakshatra", "yoga", "karana"):
            elems = getattr(p, cat)
            for a, b in zip(elems, elems[1:], strict=False):
                assert a.end == b.start


# ── Choghadiya (names exact, boundaries ±2 min) ─────────────────────────────
def test_choghadiya_tables(golden, computed):
    for cg in golden["choghadiya"]:
        d = date.fromisoformat(cg["date"])
        p = computed[cg["date"]]
        day_slots = day_choghadiya(p.sunrise, p.sunset)
        night_slots = night_choghadiya(p.sunset, p.next_sunrise)
        for ours, gold in (
            (day_slots, cg["day"]),
            (night_slots, cg["night"]),
        ):
            assert len(ours) == 8
            for i, g in enumerate(gold):
                assert ours[i].name == g["name"], (
                    f"{cg['date']} slot[{i}] {ours[i].name} != {g['name']}"
                )
                assert _nearest(ours[i].start, d, g["start"]) <= WINDOW_TOL
                assert _nearest(ours[i].end, d, g["end"]) <= WINDOW_TOL


# ── Kaal windows across all 10 days (±2 min) ────────────────────────────────
def test_kaal_windows(golden, computed):
    fns = {
        "rahu_kalam": rahu_kaal,
        "gulika_kalam": gulika_kaal,
        "yamaganda": yamaganda_kaal,
    }
    for day in golden["days"]:
        d = date.fromisoformat(day["date"])
        p = computed[day["date"]]
        for key, fn in fns.items():
            w = fn(p.sunrise, p.sunset)
            assert _nearest(w.start, d, day[key][0]) <= WINDOW_TOL, f"{d} {key} start"
            assert _nearest(w.end, d, day[key][1]) <= WINDOW_TOL, f"{d} {key} end"
