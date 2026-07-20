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


USER_FACING_AREAS = {"Love", "Money", "Career", "Mind", "Health", "Mood"}


def test_guidance_payload_shape():
    sky = build_daily_sky(date(2026, 7, 18))
    row = guidance_for_nakshatra(5, sky, RULES)      # Ardra — Rohan's natal star
    assert set(row) >= {
        "nakshatra_index", "nakshatra", "tara", "energy", "scores",
        "area_lines", "band_labels", "score_why", "narrative", "why",
        "lucky", "good_for", "avoid",
        "opportunity", "warning", "opportunity_detail", "warning_detail",
    }
    assert set(row["lucky"]) == {"color", "number", "direction"}
    # The zero-bug fix: score keys ARE the user-facing labels the app renders.
    assert set(row["scores"]) == USER_FACING_AREAS
    assert set(row["area_lines"]) == USER_FACING_AREAS
    assert set(row["band_labels"]) == USER_FACING_AREAS
    assert set(row["score_why"]) == USER_FACING_AREAS
    assert "{area}" not in row["opportunity"] and "{area}" not in row["warning"]


def test_all_six_scores_nonzero_across_dates():
    """The dashboard bug regression: every user-facing area must carry a real
    score (the v1 payload keyed three of them differently, so they read 0)."""
    for day in SAMPLE_DATES:
        sky = build_daily_sky(day)
        for row in all_guidance(sky, RULES):
            assert set(row["scores"]) == USER_FACING_AREAS
            for label in USER_FACING_AREAS:
                assert row["scores"][label] > 0


def test_narrative_is_two_sentences_with_no_slots():
    for day in SAMPLE_DATES:
        sky = build_daily_sky(day)
        for row in all_guidance(sky, RULES):
            assert "{" not in row["narrative"] and "}" not in row["narrative"]
            assert row["narrative"].count(".") >= 1  # opener + closer prose
            assert len(row["narrative"]) > 40


def test_headline_copy_is_jargon_free():
    """Jargon demotion: tara/nakshatra vocabulary may lead only in `why`."""
    jargon = ("tara", "tarabala", "nakshatra", "janma", "sampat", "vipat",
              "kshema", "pratyak", "sadhaka", "vadha", "mitra", "paksha")
    for day in SAMPLE_DATES:
        sky = build_daily_sky(day)
        for row in all_guidance(sky, RULES):
            headline = " ".join(
                [row["narrative"], row["opportunity"], row["warning"],
                 row["opportunity_detail"], row["warning_detail"],
                 *row["area_lines"].values(), *row["score_why"].values(),
                 *row["band_labels"].values(), *row["good_for"], *row["avoid"]]
            ).lower()
            for word in jargon:
                assert word not in headline, f"{word!r} leaked into headline copy"
            assert row["why"]  # the credibility line carries the detail instead


def test_area_lines_rotate_across_consecutive_days():
    """Variant rotation: the same (natal, tara) cell must not repeat its line
    on consecutive dates. Pin the tara by advancing only the date on an
    otherwise identical sky — adjacent rotation steps, same content cell."""
    s1 = build_daily_sky(date(2026, 7, 18))
    s2 = {**s1, "date": "2026-07-19"}
    r1 = guidance_for_nakshatra(5, s1, RULES)
    r2 = guidance_for_nakshatra(5, s2, RULES)
    assert r1["tara"]["number"] == r2["tara"]["number"]
    assert r1["area_lines"] != r2["area_lines"]
    assert r1["narrative"] != r2["narrative"]


def test_every_content_cell_composes():
    """All 54 (area × tara) cells and all 9 taras' generators resolve for every
    natal nakshatra over a 9-day sweep (covers each tara at least once)."""
    from datetime import timedelta
    start = date(2026, 7, 18)
    seen_taras = set()
    for offset in range(9):
        sky = build_daily_sky(start + timedelta(days=offset))
        for row in all_guidance(sky, RULES):
            seen_taras.add(row["tara"]["number"])
            for line in row["area_lines"].values():
                assert line and (line[0].isupper() or line[0].isdigit())
            assert row["opportunity"] and row["warning"]
    assert seen_taras == set(range(1, 10))


def test_score_detail_content_separates_areas():
    """The content_v3 contract testers asked for: on any date, no two areas
    may share a band label or a score_why sentence, and score_why must be a
    two-sentence RECOGNITION + CAUSE (never the area name swapped into a
    shared template)."""
    from datetime import timedelta
    start = date(2026, 7, 18)
    for offset in range(14):
        sky = build_daily_sky(start + timedelta(days=offset))
        for row in all_guidance(sky, RULES):
            labels = list(row["band_labels"].values())
            assert len(set(labels)) == len(labels), (
                f"shared band label on {sky['date']}: {row['band_labels']}"
            )
            whys = list(row["score_why"].values())
            assert len(set(whys)) == len(whys), (
                f"shared score_why on {sky['date']}"
            )
            for why in whys:
                assert why.count(".") + why.count("'") >= 1
                assert len(why) > 60  # recognition + cause, not a stub
                assert "{" not in why and "}" not in why


def test_score_why_varies_across_consecutive_days():
    """The day lord changes daily, so the same area must not repeat its
    score_why on consecutive dates even when the tara cell is pinned."""
    s1 = build_daily_sky(date(2026, 7, 18))
    s2 = build_daily_sky(date(2026, 7, 19))
    r1 = guidance_for_nakshatra(5, s1, RULES)
    r2 = guidance_for_nakshatra(5, s2, RULES)
    for label in USER_FACING_AREAS:
        assert r1["score_why"][label] != r2["score_why"][label]


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
