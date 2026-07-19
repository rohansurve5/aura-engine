"""Determinism + shape tests for the precompute payloads (no DB required).

The two guarantees the nightly job relies on:
  1. same date + same rules version → byte-identical payloads (idempotent
     upserts, and a value the app can cache hard);
  2. every date yields all 27 nakshatra rows with scores in [0, 100].
"""

from __future__ import annotations

import json
import os
from datetime import date

import pytest

from engine.daily import build_daily_sky
from engine.scoring import (
    SCORE_RULES_VERSION,
    all_guidance,
    guidance_for_nakshatra,
    load_rules_from_json,
    tara_of,
)

RULES = load_rules_from_json()
SAMPLE_DATES = (date(2026, 7, 18), date(1989, 9, 23), date(2026, 1, 14), date(2026, 12, 25))


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def test_sky_is_byte_identical_across_runs():
    for day in SAMPLE_DATES:
        assert _canon(build_daily_sky(day)) == _canon(build_daily_sky(day))


def test_guidance_is_byte_identical_across_runs():
    for day in SAMPLE_DATES:
        sky = build_daily_sky(day)
        assert _canon(all_guidance(sky, RULES)) == _canon(all_guidance(sky, RULES))


def test_all_27_nakshatra_rows_present_and_ordered():
    sky = build_daily_sky(date(2026, 7, 18))
    rows = all_guidance(sky, RULES)
    assert len(rows) == 27
    assert [r["nakshatra_index"] for r in rows] == list(range(27))


def test_scores_and_energy_within_0_100():
    for day in SAMPLE_DATES:
        sky = build_daily_sky(day)
        for row in all_guidance(sky, RULES):
            assert 0 <= row["energy"] <= 100
            for value in row["scores"].values():
                assert 0 <= value <= 100


def test_tara_is_the_nine_fold_cycle():
    assert tara_of(5, 5) == 1                       # janma: day-Moon on the natal star
    assert tara_of(0, 8) == 9                        # 9th star from natal → Parama Mitra
    assert tara_of(0, 9) == 1                        # 10th wraps back to Janma
    assert {tara_of(0, d) for d in range(27)} == set(range(1, 10))


def test_guidance_payload_shape():
    sky = build_daily_sky(date(2026, 7, 18))
    row = guidance_for_nakshatra(5, sky, RULES)      # Ardra — Rohan's natal star
    assert set(row) >= {
        "nakshatra_index", "nakshatra", "tara", "energy", "scores",
        "lucky", "good_for", "avoid", "opportunity", "warning",
    }
    assert set(row["lucky"]) == {"color", "number", "direction"}
    assert set(row["scores"]) == {"Career", "Finances", "Relationships", "Health", "Mind", "Growth"}
    assert "{area}" not in row["opportunity"] and "{area}" not in row["warning"]


def test_sky_payload_shape():
    sky = build_daily_sky(date(2026, 7, 18))
    assert sky["date"] == "2026-07-18"
    assert sky["planet_of_day"] == "Saturn"          # 2026-07-18 is a Saturday
    assert 0 <= sky["day_nakshatra_index"] <= 26
    assert len(sky["choghadiya"]["day"]) == 8
    assert len(sky["choghadiya"]["night"]) == 8
    assert set(sky["kaals"]) == {"rahu", "gulika", "yamaganda"}


@pytest.mark.skipif(not os.environ.get("NEON_DATABASE_URL"), reason="no NEON_DATABASE_URL")
def test_db_rules_match_seed():
    """When a DB is configured, its seeded rules equal the JSON seed."""
    from engine.jobs.db import connect
    from engine.scoring import load_rules_from_db

    with connect() as conn:
        assert load_rules_from_db(conn, SCORE_RULES_VERSION) == RULES
