"""§4 — non-IST cross-check of choghadiya + Rahu Kaal against DrikPanchang.

The Pune golden (test_panchang.py) already pins names + boundaries in IST.
This extends it 'in kind' to three non-IST cities on three different weekdays,
both hemispheres, two DST zones — proving the weekday arithmetic and the kaal
part-numbers hold away from IST. DrikPanchang's choghadiya page is GET-fetchable
(the fixtures were verified against a live fetch; see the golden's `notes`).

The DST-safe fixed-offset method mirrors scripts/crossval_window.py: choghadiya
math must be fed LOCAL naive datetimes (it keys weekday off `.date()` and does
wall-clock arithmetic), so we offset each half by the zone offset at the START
of that half — exact durations, correct civil date.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import swisseph as swe

from engine.choghadiya import day_choghadiya, night_choghadiya, rahu_kaal

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "drik_choghadiya_intl.json")


@pytest.fixture(scope="module")
def golden():
    swe.set_ephe_path(os.path.join(os.path.dirname(__file__), os.pardir, "ephe"))
    with open(GOLDEN) as f:
        return json.load(f)


def _rise_set(jd0: float, lat: float, lon: float, *, rise: bool) -> float:
    flag = swe.CALC_RISE if rise else swe.CALC_SET
    res, times = swe.rise_trans(jd0, swe.SUN, flag, (lon, lat, 0.0))
    if res != 0:
        raise ValueError("no rise/set")
    return times[0]


def _compute(city: dict):
    tz = ZoneInfo(city["zone"])
    lat, lon = city["lat"], city["lon"]
    midnight = datetime.strptime(city["date"], "%Y-%m-%d").replace(tzinfo=tz)
    utc_mid = midnight.astimezone(UTC)
    jd_mid = swe.julday(utc_mid.year, utc_mid.month, utc_mid.day,
                        utc_mid.hour + utc_mid.minute / 60)
    jd_rise = _rise_set(jd_mid, lat, lon, rise=True)
    jd_set = _rise_set(jd_rise, lat, lon, rise=False)
    jd_next = _rise_set(jd_set, lat, lon, rise=True)

    def utc(jd: float) -> datetime:
        y, m, d, h = swe.revjul(jd, swe.GREG_CAL)
        return (datetime(y, m, d, tzinfo=UTC) + timedelta(hours=h))

    rise_u, set_u, next_u = utc(jd_rise), utc(jd_set), utc(jd_next)

    def naive_at(instant: datetime, ref: datetime) -> datetime:
        off = ref.astimezone(tz).utcoffset()
        return (instant + off).replace(tzinfo=None)

    rise = naive_at(rise_u, rise_u)
    sset_day = naive_at(set_u, rise_u)
    sset_night = naive_at(set_u, set_u)
    nxt = naive_at(next_u, set_u)
    return {
        "rise_local": rise, "set_local": sset_day,
        "day": day_choghadiya(rise, sset_day),
        "night": night_choghadiya(sset_night, nxt),
        "rahu": rahu_kaal(rise, sset_day),
    }


def _hhmm_delta(dt: datetime, hhmm: str) -> float:
    """Absolute seconds between a computed local datetime and a HH:MM display on
    the same civil date (the display is minute-rounded)."""
    h, m = (int(x) for x in hhmm.split(":"))
    target = dt.replace(hour=h, minute=m, second=0, microsecond=0)
    return abs((dt - target).total_seconds())


def test_intl_choghadiya_names_match_drikpanchang(golden):
    for city in golden["cities"]:
        c = _compute(city)
        got_day = [w.name for w in c["day"]]
        got_night = [w.name for w in c["night"]]
        assert got_day == city["day"], f"{city['place']} day: {got_day} != {city['day']}"
        assert got_night == city["night"], f"{city['place']} night"


def test_intl_sunrise_sunset_within_tolerance(golden):
    tol = golden["tolerance_s"]
    for city in golden["cities"]:
        c = _compute(city)
        assert _hhmm_delta(c["rise_local"], city["sunrise"]) <= tol, f"{city['place']} sunrise"
        assert _hhmm_delta(c["set_local"], city["sunset"]) <= tol, f"{city['place']} sunset"


def test_intl_rahu_kaal_matches_where_fetched(golden):
    tol = golden["tolerance_s"]
    checked = 0
    for city in golden["cities"]:
        if not city["rahu"]:
            continue
        c = _compute(city)
        assert _hhmm_delta(c["rahu"].start, city["rahu"]) <= tol, f"{city['place']} rahu"
        checked += 1
    assert checked >= 1, "no Rahu Kaal fixture to check"
