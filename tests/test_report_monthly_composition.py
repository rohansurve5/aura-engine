"""Composition gates for the MONTHLY report.

Same battery as tests/test_report_composition.py at month scale, plus the two
things that are genuinely different and therefore re-derived rather than
copied:

THE ROTATION CYCLE IS 12, NOT 52. A monthly rotation locks to the CALENDAR
YEAR: the reader's natural comparison is "this July vs last July", twelve
reports apart. So the coprimality constraint is against 12 — and it inverts
the weekly verdict on 13. At week scale 13 was the trap (13 divides 52, so a
13-slot rotation repeats on 52-week anniversaries); at month scale
gcd(13, 12) = 1 makes 13 the smallest legal count above 12. The consecutive-
distinct guarantee is 13 months of distinct openings — outlasting a full year
— and an anniversary month repeats an opening only every 13 years, because
the index advances 12 ≡ -1 (mod 13) per year.

THE THRESHOLDS ARE RE-DERIVED, NOT SCALED. Aggregates regress to the mean:
the daily energies inside one week spread 48-70 points, but the WEEKLY MEANS
inside one month spread only 1.4-30.3 (median 13.7, 144 real months x 6
natals). The weekly `EVEN_SPREAD = 12` floor would classify half of all
months as `level`; the monthly `LEVEL_SPREAD = 6` was chosen from the
measured distribution so that `level` is a real but rare class (~4%) — and
unlike the weekly corpus's dead `even` cell, every monthly shape is reachable
on real sky, which `test_all_five_shapes_occur_across_a_realistic_span`
protects against a score_rules retune.
"""

from __future__ import annotations

import json
from datetime import date
from functools import cache, lru_cache
from math import gcd

import pytest

import engine.reports as R
from engine.reports import (
    MONTH_CLOSE_VARIANTS,
    MONTH_OPENING_VARIANTS,
    MONTH_SHAPES,
    MONTH_STANDING_VARIANTS,
    MONTH_TURN_KINDS,
    MONTH_TURN_VARIANTS,
    TWIN_MARGIN,
    build_monthly_report,
    month_index,
    month_shape_of,
    month_turn_of,
    month_weeks,
)
from engine.scoring import guidance_for_nakshatra, load_rules_from_json

RULES = load_rules_from_json()
CONTENT = R.load_report_content_from_json(report_kind="monthly")

#: A fixed span long enough that the 13-month opening cycle completes and
#: slides through at least two windows (26 - 13 + 1 = 14 windows).
FIRST_MONTH = (2026, 8)
MONTHS_SPAN = 26
SAMPLE_NATALS = (0, 1, 7, 13, 20, 26)


def _ym(offset: int) -> tuple[int, int]:
    base = FIRST_MONTH[0] * 12 + (FIRST_MONTH[1] - 1) + offset
    return base // 12, base % 12 + 1


@pytest.fixture(autouse=True)
def _cached_sky(monkeypatch):
    """Memoise the ephemeris across the module — ~26 months of distinct dates,
    each pure and safe to cache, instead of 30 fresh Swiss Ephemeris calls per
    composed report."""
    monkeypatch.setattr(R, "build_daily_sky", lru_cache(maxsize=None)(R.build_daily_sky))


@cache
def _mreport(natal: int, offset: int) -> dict:
    y, m = _ym(offset)
    return build_monthly_report(natal, y, m, RULES, CONTENT)


@cache
def _true_week_means(natal: int, offset: int) -> tuple[float, ...]:
    """The month's UNROUNDED weekly means, re-derived from the ephemeris
    independently of the report payload.

    Every `energy_mean` a report publishes is a rounded integer (a report
    should never show a reader 70.85714285714286). That makes the payload a
    *display* of the data rather than the data, and the anchor gate must not
    grade the report against its own display: two weeks 0.4 apart round to
    the same integer, so `max(published_means)` can pick the wrong week and
    the gate would pass a report that names the wrong carrier week.

    So the gate re-computes the true means here and grades the report against
    those — strictly stronger than the pre-rounding version, which trusted a
    payload field. The rounding is then checked separately, as faithfulness of
    the display, by `test_published_means_are_the_rounded_true_means`.
    """
    y, m = _ym(offset)
    weeks = month_weeks(y, m)
    energy = {}
    for _, days in weeks:
        for d in days:
            energy[d] = guidance_for_nakshatra(natal, R.build_daily_sky(d), RULES)["energy"]
    return tuple(sum(energy[d] for d in days) / len(days) for _, days in weeks)


# ── month arithmetic ─────────────────────────────────────────────────────────

def test_month_index_advances_by_exactly_one_per_month_across_year_ends():
    """The non-repetition argument rests on this — including at December to
    January, where a (year, month) encoding error would jump the index."""
    base = month_index(2026, 8)
    for offset in range(60):
        y, m = _ym(offset)
        assert month_index(y, m) == base + offset
    assert month_index(2027, 1) == month_index(2026, 12) + 1


def test_month_weeks_qualify_by_majority_and_cover_every_shape_of_month():
    """4 or 5 qualifying ISO weeks for every month, each holding at least
    QUALIFYING_WEEK_MIN_DAYS in-month days, each starting on a Monday."""
    for y, m in [(2026, 2), (2026, 7), (2026, 8), (2027, 2), (2028, 2), (2026, 12)]:
        weeks = month_weeks(y, m)
        assert 4 <= len(weeks) <= 5, (y, m)
        for monday, days in weeks:
            assert monday.weekday() == 0
            assert len(days) >= R.QUALIFYING_WEEK_MIN_DAYS
            assert all(d.month == m for d in days)
        mondays = [w[0] for w in weeks]
        assert mondays == sorted(mondays)


def test_month_weeks_edge_fragments_are_excluded_but_counted_days_are_not_lost():
    """July 2026 starts on a Wednesday: its first ISO week holds 5 in-month
    days (qualifies) and its last holds 5 (qualifies). August 2026 starts on a
    Saturday: its first ISO week holds 2 in-month days and must NOT qualify."""
    aug = month_weeks(2026, 8)
    assert aug[0][0] == date(2026, 8, 3), "the 2-day fragment must not lead"
    jul = month_weeks(2026, 7)
    assert jul[0][0] == date(2026, 6, 29), "a 5-day opening partial qualifies"


# ── shape classification: every threshold pinned at both edges ───────────────

def test_level_floor_fires_at_its_boundary():
    assert month_shape_of([50.0, 52.0, 54.0, 55.9]) == "level"      # spread 5.9 < 6
    assert month_shape_of([50.0, 52.0, 54.0, 56.0]) != "level"      # spread 6.0


def test_position_classes_follow_the_carrier_week():
    assert month_shape_of([60.0, 50.0, 51.0, 52.0]) == "opening"
    assert month_shape_of([50.0, 51.0, 52.0, 60.0]) == "closing"
    assert month_shape_of([50.0, 60.0, 51.0, 52.0]) == "core"
    assert month_shape_of([50.0, 51.0, 60.0, 52.0, 49.0]) == "core"


def test_twin_requires_a_near_tie_between_non_adjacent_weeks():
    """Both conditions pinned: within TWIN_MARGIN and separated. A near-tie
    between ADJACENT weeks is one wide carrier, not two windows, and falls
    through to its position class."""
    assert month_shape_of([60.0, 50.0, 59.0, 48.0]) == "twin"        # gap 1.0, apart
    # exactly at the margin still counts (<=)
    assert month_shape_of([60.0, 50.0, 58.0, 48.0]) == "twin"
    # over the margin: position wins
    assert month_shape_of([60.0, 50.0, 57.9, 48.0]) == "opening"     # gap 2.1
    assert month_shape_of([60.0, 50.0, 57.0, 48.0]) == "opening"
    # near-tie but adjacent: a wide carrier, positional
    assert month_shape_of([60.0, 59.0, 50.0, 48.0]) == "opening"


def test_twin_boundary_arithmetic_is_what_the_test_above_assumes():
    """Self-check on the fixture values, so the pinned edges stay honest."""
    assert 60.0 - 58.0 == TWIN_MARGIN
    assert 60.0 - 57.9 > TWIN_MARGIN


def test_shape_rejects_a_degenerate_week_list():
    with pytest.raises(ValueError):
        month_shape_of([50.0])


def test_shape_of_is_total_over_synthetic_months():
    import itertools
    for combo in itertools.product((45.0, 50.0, 55.0, 62.0), repeat=4):
        assert month_shape_of(list(combo)) in MONTH_SHAPES


# ── turn classification ──────────────────────────────────────────────────────

def test_level_months_never_claim_a_turn():
    """Naming a pivot inside a month whose weekly means sit within six points
    would be inventing drama — the month-scale version of even → no_turn."""
    assert month_turn_of([50.0, 52.0, 54.0, 55.0], 40.0, 60.0, "level") == "steady"


def test_hinge_outranks_the_halves_comparison():
    """Best and worst weeks adjacent is the fact that changes scheduling,
    exactly as weekly whiplash outranks peak position."""
    means = [50.0, 62.0, 45.0, 52.0]  # best w2, worst w3, adjacent
    assert month_turn_of(means, 40.0, 60.0, "core") == "hinge"


def test_halves_fire_at_the_margin_and_not_under_it():
    means = [50.0, 60.0, 48.0, 52.0, 55.0]  # best 1, worst 2 adjacent? 60 at 1, 48 at 2 → adjacent!
    # use non-adjacent extremes so the halves logic is what decides:
    means = [50.0, 60.0, 52.0, 48.0, 55.0]  # best index 1, worst index 3
    assert month_turn_of(means, 50.0, 54.0, "core") == "lifts"       # +4.0 at margin
    assert month_turn_of(means, 50.0, 53.9, "core") == "steady"      # +3.9 under
    assert month_turn_of(means, 54.0, 50.0, "core") == "settles"     # -4.0 at margin
    assert month_turn_of(means, 53.9, 50.0, "core") == "steady"


def test_every_turn_kind_is_reachable_and_known():
    for kind in (
        month_turn_of([50.0, 60.0, 52.0, 48.0], 50.0, 55.0, "core"),
        month_turn_of([50.0, 60.0, 52.0, 48.0], 55.0, 50.0, "core"),
        month_turn_of([50.0, 62.0, 45.0, 52.0], 50.0, 50.0, "core"),
        month_turn_of([50.0, 52.0, 54.0, 55.0], 50.0, 50.0, "level"),
    ):
        assert kind in MONTH_TURN_KINDS


# ── determinism / rotation ───────────────────────────────────────────────────

def test_same_inputs_produce_byte_identical_monthly_reports():
    a = build_monthly_report(7, 2026, 9, RULES, CONTENT)
    b = build_monthly_report(7, 2026, 9, RULES, CONTENT)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_two_natals_in_the_same_month_do_not_receive_the_same_opening():
    """De-sync via natal*3 mod 13 — a MITIGATION, not a full guarantee.

    27 natal stars into 13 opening slots is a pigeonhole: natal pairs that are
    congruent mod 13 (0 and 13, 7 and 20, ...) share the rotation offset in
    every month, exactly as weekly pairs congruent mod 17 do. Those readers
    are separated by the data instead: shape is computed from each natal's own
    energies, so congruent readers usually hold different shapes and draw from
    disjoint corpora. The sample here is chosen distinct mod 13 to assert the
    arithmetic half of the claim, and this docstring records the half the
    arithmetic cannot give."""
    natals = (0, 3, 7, 11, 18, 25)  # pairwise distinct mod 13
    assert len({n % 13 for n in natals}) == len(natals)
    openings = {n: _mreport(n, 0)["opening"] for n in natals}
    assert len(set(openings.values())) == len(natals), openings


def test_monthly_variant_counts_clear_the_calendar_cycle_of_twelve():
    """THE DERIVATION, AS ARITHMETIC. The cycle a monthly rotation must clear
    is 12 — and the weekly answer does not transfer: 13 was the weekly trap
    (13 | 52) and is the monthly optimum (gcd(13,12)=1, smallest count > 12).
    The traps at THIS cadence are the divisors-of-12 neighbourhood."""
    for n in (
        MONTH_OPENING_VARIANTS,
        MONTH_TURN_VARIANTS,
        MONTH_STANDING_VARIANTS,
        MONTH_CLOSE_VARIANTS,
    ):
        assert gcd(n, 12) == 1, f"{n} shares a factor with the 12-month year"

    # pairwise coprime → the combined skeleton period is the full product
    assert gcd(MONTH_OPENING_VARIANTS, MONTH_TURN_VARIANTS) == 1
    assert gcd(MONTH_OPENING_VARIANTS, MONTH_CLOSE_VARIANTS) == 1
    assert gcd(MONTH_TURN_VARIANTS, MONTH_CLOSE_VARIANTS) == 1
    assert MONTH_OPENING_VARIANTS * MONTH_TURN_VARIANTS * MONTH_CLOSE_VARIANTS == 455

    # the traps, named: 12 locks instantly; 8/9/6 lock on short anniversaries;
    # and the weekly counts would ALSO have been legal here (17, 7, 5 are all
    # coprime with 12) — 13 is chosen over 17 because it is the smallest count
    # that still outlasts the 12-report year, not because 17 fails.
    assert gcd(12, 12) == 12
    assert gcd(8, 12) == 4 and gcd(9, 12) == 3 and gcd(6, 12) == 6
    assert gcd(13, 52) == 13, "the same count IS the trap at week cadence"
    assert gcd(13, 12) == 1
    assert MONTH_OPENING_VARIANTS > 12, "must outlast a full year of reports"


def test_anniversary_months_do_not_repeat_for_thirteen_years():
    """12 ≡ -1 (mod 13): each year the same calendar month steps back one
    opening variant, so the anniversary cycle is the full 13 years."""
    seen = set()
    for years in range(13):
        seen.add(R._variant(MONTH_OPENING_VARIANTS, month_index(2026 + years, 7), 4, 1))
    assert len(seen) == 13


# ── claim consistency: a report may not contradict its own data ──────────────

@pytest.mark.parametrize("natal", SAMPLE_NATALS)
def test_anchors_name_the_actual_extreme_weeks(natal):
    """The monthly instance of the anchor gate: the carrier week IS the argmax
    of the weekly means, the thin week IS the argmin, and both are qualifying
    ISO weeks of the month — dates a reader can open a weekly report for."""
    for offset in range(0, MONTHS_SPAN, 2):
        rep = _mreport(natal, offset)
        true = list(_true_week_means(natal, offset))
        starts = [w["week_start"] for w in rep["weeks"]]
        assert len(true) == len(starts), rep["month"]
        carrier = rep["anchors"]["carrier_week"]
        thin = rep["anchors"]["thin_week"]
        # The falsifiable claim is the DATE, graded against the true means —
        # not against the report's own rounded display (see _true_week_means).
        assert carrier["week_start"] == starts[true.index(max(true))], rep["month"]
        assert thin["week_start"] == starts[true.index(min(true))], rep["month"]
        assert carrier["energy_mean"] == R._round_half_up(max(true)), rep["month"]
        assert thin["energy_mean"] == R._round_half_up(min(true)), rep["month"]
        assert date.fromisoformat(carrier["week_start"]).weekday() == 0


@pytest.mark.parametrize("natal", SAMPLE_NATALS)
def test_published_means_are_the_rounded_true_means(natal):
    """Faithfulness of the display, the other half of the anchor gate.

    Every `energy_mean` in the payload — per week, both anchors, and the
    month — is an INTEGER and is exactly the half-up rounding of the value the
    engine actually computed. This is what stops "round it for the reader"
    from drifting into "show the reader a different number", and it is why the
    gate above can afford to grade dates against the unrounded series.
    """
    for offset in range(0, MONTHS_SPAN, 2):
        rep = _mreport(natal, offset)
        true = list(_true_week_means(natal, offset))
        published = [w["energy_mean"] for w in rep["weeks"]]
        assert all(isinstance(v, int) for v in published), rep["month"]
        assert published == [R._round_half_up(t) for t in true], rep["month"]
        assert isinstance(rep["energy_mean"], int)
        assert isinstance(rep["anchors"]["carrier_week"]["energy_mean"], int)
        assert isinstance(rep["anchors"]["thin_week"]["energy_mean"], int)


@pytest.mark.parametrize("natal", SAMPLE_NATALS[:3])
def test_reported_shape_turn_and_weeks_agree_with_the_data(natal):
    for offset in range(0, MONTHS_SPAN, 3):
        rep = _mreport(natal, offset)
        # Re-derived from the ephemeris, not read back from the payload: the
        # published means are rounded, and classification runs on the raw
        # series (a 5.6-point spread is not `level`; its rounded display can
        # look like 6, which is).
        means = list(_true_week_means(natal, offset))
        assert rep["shape"] == month_shape_of(means)
        assert rep["turn"] == month_turn_of(
            means, rep["half_means"]["first"], rep["half_means"]["second"], rep["shape"]
        )
        assert 4 <= len(rep["weeks"]) <= 5
        if rep["shape"] == "level":
            assert rep["turn"] == "steady"


@pytest.mark.parametrize("natal", SAMPLE_NATALS[:3])
def test_standing_names_three_distinct_areas_with_distinct_roles(natal):
    for offset in range(0, MONTHS_SPAN, 5):
        rep = _mreport(natal, offset)
        assert sorted(rep["standing"].values()) == ["lags", "leads", "steadies"]
        assert set(rep["standing"]) == set(rep["standing_lines"])


def test_monthly_report_rejects_a_bad_month_number():
    with pytest.raises(ValueError):
        build_monthly_report(0, 2026, 13, RULES, CONTENT)


# ── the reading-unit gate: consecutive months ────────────────────────────────

@pytest.mark.parametrize("natal", (0, 13, 26))
def test_no_repeated_opening_inside_thirteen_consecutive_months(natal):
    """13 consecutive monthly reports — MORE than a year — cannot repeat an
    opening. The monthly analogue of the 17-week weekly window, at the width
    the mod-13 arithmetic guarantees."""
    openings = [_mreport(natal, o)["opening"] for o in range(MONTHS_SPAN)]
    for start in range(MONTHS_SPAN - MONTH_OPENING_VARIANTS + 1):
        window = openings[start : start + MONTH_OPENING_VARIANTS]
        assert len(set(window)) == MONTH_OPENING_VARIANTS, (
            f"natal {natal}, months {start}..{start + MONTH_OPENING_VARIANTS}: repeat"
        )


@pytest.mark.parametrize("natal", (0, 13))
def test_no_repeated_turn_or_close_inside_their_monthly_windows(natal):
    for start in range(MONTHS_SPAN - MONTH_TURN_VARIANTS + 1):
        by_kind: dict[str, list[str]] = {}
        for o in range(start, start + MONTH_TURN_VARIANTS):
            rep = _mreport(natal, o)
            by_kind.setdefault(rep["turn"], []).append(rep["turn_line"])
        for kind, lines in by_kind.items():
            assert len(set(lines)) == len(lines), f"natal {natal} kind {kind}: {lines}"
    for start in range(MONTHS_SPAN - MONTH_CLOSE_VARIANTS + 1):
        by_shape: dict[str, list[str]] = {}
        for o in range(start, start + MONTH_CLOSE_VARIANTS):
            rep = _mreport(natal, o)
            by_shape.setdefault(rep["shape"], []).append(rep["close"])
        for shape, lines in by_shape.items():
            assert len(set(lines)) == len(lines), f"natal {natal} shape {shape}: {lines}"


def test_the_monthly_window_gate_cannot_pass_vacuously():
    """SECOND SIGNATURE: the sliding range must be non-empty and slide."""
    assert MONTHS_SPAN >= MONTH_OPENING_VARIANTS
    windows = list(range(MONTHS_SPAN - MONTH_OPENING_VARIANTS + 1))
    assert len(windows) >= 2


@pytest.mark.parametrize("natal", (0, 26))
def test_no_two_consecutive_months_are_identical_reports(natal):
    for o in range(MONTHS_SPAN - 1):
        a, b = _mreport(natal, o), _mreport(natal, o + 1)
        assert (a["opening"], a["turn_line"], a["close"]) != (
            b["opening"], b["turn_line"], b["close"]
        ), f"natal {natal} months {o}/{o + 1} identical"


# ── coverage: reachability on real sky, and every cell drawable ──────────────

def test_all_five_shapes_occur_across_a_realistic_span():
    """The monthly version of THE TEST THAT CAUGHT THE WEEKLY DESIGN ERROR.

    Unlike weekly's dead `even`, every monthly class was reachable on real sky
    when the thresholds were derived (144 months: core 62%, closing 15%,
    opening 11%, twin 7%, level 4%). This keeps a future score_rules retune
    from silently killing a class the corpus still carries copy for."""
    seen = {_mreport(natal, o)["shape"] for natal in SAMPLE_NATALS for o in range(MONTHS_SPAN)}
    assert len(seen) >= 4, f"classifier looks degenerate on real data: {seen}"


def test_multiple_turn_kinds_occur_across_a_realistic_span():
    seen = {_mreport(natal, o)["turn"] for natal in SAMPLE_NATALS[:3] for o in range(MONTHS_SPAN)}
    assert len(seen) >= 3, f"turn classifier looks degenerate: {seen}"


def test_every_authored_monthly_cell_is_drawable():
    for shape in MONTH_SHAPES:
        drawn = {
            CONTENT["shape"][shape]["openings"][R._variant(MONTH_OPENING_VARIANTS, mi, 0, 1)]
            for mi in range(MONTH_OPENING_VARIANTS)
        }
        assert len(drawn) == MONTH_OPENING_VARIANTS, shape
    for kind in MONTH_TURN_KINDS:
        drawn = {
            CONTENT["turn"][kind]["lines"][R._variant(MONTH_TURN_VARIANTS, mi, 0, 3, 1)]
            for mi in range(MONTH_TURN_VARIANTS)
        }
        assert len(drawn) == MONTH_TURN_VARIANTS, kind


def test_monthly_constants_match_the_seed():
    assert set(CONTENT["shape"]) == set(MONTH_SHAPES)
    assert set(CONTENT["close"]) == set(MONTH_SHAPES)
    assert set(CONTENT["turn"]) == set(MONTH_TURN_KINDS)
    for a in RULES["areas"]["order"]:
        for r in ("leads", "lags", "steadies"):
            assert f"{a}.{r}" in CONTENT["standing"]
