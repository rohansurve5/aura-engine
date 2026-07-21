"""Timezone spec resolution, and the daily_sky tz plumbing it fixed.

Before this, build_daily_sky read location["tz"] into the payload but never
passed it to compute_panchang, so EVERY location formatted its times in IST.
A New York daily_sky claimed a ~06:30 sunrise because it was rendering an
Indian clock. These tests pin both halves of the fix: the spec→tzinfo bridge
(location["tz"] is a string, the kwarg wants a tzinfo) and the plumbing itself.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from engine.daily import CANONICAL_LOCATION, build_daily_sky
from engine.timezones import (
    is_fixed_offset,
    local_to_utc,
    offset_minutes_at,
    resolve_tz,
)


class TestSpecResolution:
    def test_fixed_offset_is_literal_at_every_date(self):
        # A fixed offset means exactly itself, always — war-time DST is NOT
        # applied. This is the legacy contract the natal goldens depend on.
        for year in (1935, 1943, 1990, 2025):
            assert offset_minutes_at("+05:30", datetime(year, 6, 15, 10, 30)) == 330

    def test_iana_resolves_indian_war_time_dst(self):
        # India ran +06:30 from 1942-09-01 to 1945-10-15.
        assert offset_minutes_at("Asia/Kolkata", datetime(1943, 6, 15, 10, 30)) == 390
        assert offset_minutes_at("Asia/Kolkata", datetime(1944, 12, 11, 3, 0)) == 390

    def test_iana_resolves_normal_indian_offset_outside_the_window(self):
        assert offset_minutes_at("Asia/Kolkata", datetime(1935, 6, 15, 10, 30)) == 330
        assert offset_minutes_at("Asia/Kolkata", datetime(1990, 6, 15, 10, 30)) == 330
        assert offset_minutes_at("Asia/Kolkata", datetime(2025, 6, 15, 10, 30)) == 330

    def test_iana_resolves_seasonal_dst_both_ways(self):
        assert offset_minutes_at("Europe/London", datetime(1975, 6, 15, 10, 30)) == 60
        assert offset_minutes_at("Europe/London", datetime(1975, 1, 15, 10, 30)) == 0

    def test_iana_resolves_a_historical_non_dst_offset_change(self):
        # Singapore moved +07:30 → +08:00 permanently on 1982-01-01. Not DST.
        assert offset_minutes_at("Asia/Singapore", datetime(1981, 6, 15, 10, 30)) == 450
        assert offset_minutes_at("Asia/Singapore", datetime(1990, 6, 15, 10, 30)) == 480

    def test_unrecognised_spec_raises_rather_than_guessing(self):
        # A silently-wrong timezone is a silently-wrong chart. Never default.
        for bad in ("", "IST", "Asia/Nowhere", "+5:30", "05:30", "GMT+5"):
            with pytest.raises(ValueError):
                resolve_tz(bad)

    def test_is_fixed_offset_discriminates(self):
        assert is_fixed_offset("+05:30")
        assert is_fixed_offset("-08:00")
        assert not is_fixed_offset("Asia/Kolkata")

    def test_local_to_utc_applies_the_offset_at_that_instant(self):
        # Same wall clock, same zone, 50 years apart → different UTC, because
        # 1943 was +06:30 and 1990 was +05:30.
        war = local_to_utc(datetime(1943, 6, 15, 10, 30), "Asia/Kolkata")
        peace = local_to_utc(datetime(1990, 6, 15, 10, 30), "Asia/Kolkata")
        assert war == datetime(1943, 6, 15, 4, 0, tzinfo=UTC)
        assert peace == datetime(1990, 6, 15, 5, 0, tzinfo=UTC)

    def test_fixed_offset_and_iana_agree_outside_any_transition(self):
        naive = datetime(1990, 6, 15, 10, 30)
        assert local_to_utc(naive, "+05:30") == local_to_utc(naive, "Asia/Kolkata")


class TestDailySkyTzPlumbing:
    DAY = date(2026, 6, 15)

    def test_canonical_location_is_unchanged_by_the_fix(self):
        # CANONICAL_LOCATION carries "+05:30", which resolves to exactly the IST
        # that compute_panchang defaulted to. The fix must not move Pune by a
        # second — daily_sky payloads are content-versioned.
        sky = build_daily_sky(self.DAY)
        assert sky["location"] == CANONICAL_LOCATION
        # Pune sunrise is ~06:00 IST in June; the point is it is IST-shaped.
        hour = int(sky["sunrise"][11:13])
        assert 5 <= hour <= 6, sky["sunrise"]

    def test_non_ist_location_now_formats_in_its_own_zone(self):
        # THE BUG: this used to come back on an Indian clock. New York sunrise
        # in mid-June is ~05:25 EDT. Rendered in IST it read ~14:55.
        ny = {
            "name": "New York, USA",
            "lat": 40.7128,
            "lon": -74.0060,
            "tz": "America/New_York",
        }
        sky = build_daily_sky(self.DAY, location=ny)
        hour = int(sky["sunrise"][11:13])
        assert 4 <= hour <= 6, f"NY sunrise not on a NY clock: {sky['sunrise']}"
        # ... and sunset must land in the evening, not after midnight.
        assert 19 <= int(sky["sunset"][11:13]) <= 21, sky["sunset"]

    def test_the_bug_is_actually_gone_not_masked(self):
        # Falsification: ask for the SAME place under two tz specs. The
        # astronomy is identical; only the formatting differs. If tz were still
        # being ignored these two would be byte-identical.
        base = {"name": "New York", "lat": 40.7128, "lon": -74.0060}
        in_ny = build_daily_sky(self.DAY, location={**base, "tz": "America/New_York"})
        in_ist = build_daily_sky(self.DAY, location={**base, "tz": "+05:30"})
        assert in_ny["sunrise"] != in_ist["sunrise"]
        # The gap is exactly IST(+5:30) minus EDT(-4:00) = 9h30m.
        fmt = "%Y-%m-%dT%H:%M"
        delta = datetime.strptime(in_ist["sunrise"], fmt) - datetime.strptime(
            in_ny["sunrise"], fmt
        )
        assert delta == timedelta(hours=9, minutes=30), delta

    def test_fixed_offset_location_still_works(self):
        # Regression guard for the string→tzinfo bridge: "+05:30" must not have
        # become an error when IANA ids were introduced.
        loc = {**CANONICAL_LOCATION, "tz": "+05:30"}
        assert build_daily_sky(self.DAY, location=loc)["sunrise"]
