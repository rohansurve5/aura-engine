"""Composition gates for the weekly report.

THE READING UNIT FOR A REPORT IS NOT A SCREEN — IT IS A SEQUENCE.

docs/CONTENT_KEYS.md records the lesson that every content gate must be aimed
at the unit a reader actually consumes at once, and that the daily and dasha
corpora needed *different* units (six cards on one date vs nine eras on one
timeline). Reports need a third, and it is the one that has been wrong in both
previous cases if copied blindly:

  * copying the per-DAY gate would prove that the four movements of one report
    do not collide — which is true by construction, since they are drawn from
    four disjoint corpora and could not collide even in principle. It would
    assert nothing.
  * copying the dasha SCREEN gate would prove the same thing.

What a reader of reports actually experiences is **one report per week, in
sequence**. The failure they can see is not "these four paragraphs rhyme", it
is "this is the fourth week in a row that opened the same way". So the gate
below is a SLIDING WINDOW over consecutive weeks, and the window widths are the
exact periods the variant arithmetic guarantees (17 / 7 / 5).

That guarantee is worth stating precisely, because it is the answer to "how
does this stay non-repetitive when the underlying data is similar":

    opening variant = (wk * 1 + natal * 3) % 17

`wk` advances by exactly 1 per week, so over any 17 consecutive weeks the index
takes 17 distinct values. If those weeks share a shape, the 17 openings drawn
are distinct by that arithmetic; if they do not share a shape, they are drawn
from disjoint corpora and are distinct anyway. Either way the reader cannot see
a repeat inside 17 weeks — and the same argument gives 7 for turns and 5 for
closes, with 17/7/5 mutually coprime so the triple recurs only every 595 weeks.
(Openings were 11; reports #1 and #12 could then draw the same cell. 13 was NOT
the fix: 13 divides 52, so a 13-slot rotation repeats on 52-week anniversaries.)

REGRESSION TO THE MEAN is the other half of the problem and is why variety
cannot come from rotation alone. The longer the range, the more its aggregate
flattens toward the same middling numbers, so a monthly or yearly report has
genuinely *less* data-driven variety than a daily card. Two forces compensate:
`shape` is derived from the data (a rising week does not read like a flat one,
honestly rather than decoratively), and the anchors name real dates and real
areas that differ every single time regardless of which cells were drawn.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache

import pytest

import engine.reports as R
from engine.reports import (
    CLOSE_VARIANTS,
    OPENING_VARIANTS,
    ROLES,
    SHAPES,
    TURN_KINDS,
    TURN_VARIANTS,
    area_standing,
    build_weekly_report,
    shape_of,
    turn_of,
    week_index,
    week_start,
)
from engine.scoring import load_rules_from_json

RULES = load_rules_from_json()
CONTENT = R.load_report_content_from_json()

#: A fixed span so the suite is deterministic, long enough that the 17-week
#: opening cycle completes and slides through at least two windows.
FIRST_MONDAY = date(2026, 7, 20)  # a Monday
WEEKS = 26
SAMPLE_NATALS = (0, 1, 7, 13, 20, 26)


@pytest.fixture(autouse=True)
def _cached_sky(monkeypatch):
    """Memoise the ephemeris across the whole module.

    26 weeks x 6 natals is 1092 build_daily_sky calls over only 182 distinct
    dates. Caching is safe precisely because the function is pure — the same
    property the whole pipeline is built on.
    """
    monkeypatch.setattr(R, "build_daily_sky", lru_cache(maxsize=None)(R.build_daily_sky))


def _report(natal: int, week: int) -> dict:
    return build_weekly_report(
        natal, FIRST_MONDAY + timedelta(weeks=week), RULES, CONTENT
    )


# ── shape classification: every threshold pinned at both edges ───────────────

def test_week_start_is_always_a_monday():
    for offset in range(14):
        d = date(2026, 7, 15) + timedelta(days=offset)
        assert week_start(d).weekday() == 0
        assert 0 <= (d - week_start(d)).days < 7


def test_week_index_advances_by_exactly_one_per_week():
    """The whole non-repetition argument rests on this. If the index ever
    jumped, the coprime periods would stop guaranteeing distinct variants."""
    base = week_index(FIRST_MONDAY)
    for w in range(60):
        assert week_index(FIRST_MONDAY + timedelta(weeks=w)) == base + w


def test_even_floor_fires_at_its_boundary():
    """Under EVEN_SPREAD no day stands out enough for a distribution claim to
    mean anything, so making one would be inventing structure."""
    assert shape_of([50, 51, 52, 53, 54, 55, 61]) == "even"      # spread 11 < 12
    assert shape_of([50, 51, 52, 53, 54, 55, 62]) != "even"      # spread 12


def test_each_third_claims_a_week_when_it_holds_two_strong_days():
    assert shape_of([90, 88, 40, 42, 45, 44, 43]) == "front"
    assert shape_of([40, 42, 45, 44, 43, 90, 88]) == "back"
    assert shape_of([40, 42, 90, 88, 85, 44, 43]) == "centre"


def test_split_outranks_the_single_third_classes():
    """Strong at both ends with an empty centre is a more specific true claim
    than "strong at the front", and both are true of this series."""
    energies = [90, 88, 40, 42, 43, 85, 44]
    assert set(R.strong_days(energies)) == {0, 1, 5}
    assert shape_of(energies) == "split"


def test_scattered_is_the_honest_default_not_a_nearest_match():
    """One strong day in each third clusters nowhere. Forcing it into the
    nearest third would be the report claiming structure the week lacks."""
    energies = [90, 40, 85, 42, 43, 80, 44]
    assert set(R.strong_days(energies)) == {0, 2, 5}
    assert shape_of(energies) == "scattered"


def test_strong_days_break_ties_toward_the_earlier_day():
    """A reader is never told to wait for a later day scoring the same as one
    already available."""
    assert R.strong_days([80, 60, 80, 60, 80, 60, 60]) == [0, 2, 4]
    assert R.strong_days([70, 70, 70, 70, 70, 70, 70]) == [0, 1, 2]


def test_shape_of_is_total_and_returns_a_known_class():
    """Exhaustiveness: no energy series may fall through the classifier. A
    report whose shape is None has no opening to draw."""
    import itertools
    for combo in itertools.product((30, 45, 55, 70, 90), repeat=3):
        series = list(combo) + list(reversed(combo)) + [combo[0]]
        assert shape_of(series) in SHAPES


def test_shape_of_rejects_a_wrong_length_window():
    with pytest.raises(ValueError):
        shape_of([50] * 6)


def test_every_turn_kind_is_a_known_kind_and_even_never_turns():
    for shape in SHAPES:
        assert turn_of([50, 55, 70, 72, 60, 55, 52], shape) in TURN_KINDS
    assert turn_of([50, 50, 50, 50, 50, 50, 50], "even") == "no_turn"


def test_whiplash_outranks_peak_position():
    """When the best and worst days are neighbours, that adjacency is the fact
    worth telling a reader — it is the practical consequence of the sawtooth,
    and it outranks merely saying where the peak sits."""
    energies = [90, 30, 60, 55, 50, 45, 40]
    assert energies.index(max(energies)) == 0  # would otherwise be peak_early
    assert turn_of(energies, "front") == "whiplash"


def test_peak_position_is_reported_when_the_extremes_are_not_adjacent():
    assert turn_of([90, 85, 60, 30, 50, 45, 40], "front") == "peak_early"
    assert turn_of([40, 45, 50, 30, 60, 85, 90], "back") == "peak_late"
    assert turn_of([40, 45, 90, 85, 60, 30, 44], "centre") == "peak_mid"


def test_area_standing_assigns_exactly_the_three_roles():
    scores = {
        "love": [70, 71, 72, 70, 71, 72, 70],
        "money": [40, 60, 30, 70, 35, 65, 40],
        "career": [55, 55, 55, 55, 55, 55, 55],
        "mind": [60, 61, 59, 60, 61, 59, 60],
        "health": [50, 52, 48, 50, 52, 48, 50],
        "mood": [45, 46, 44, 45, 46, 44, 45],
    }
    standing = area_standing(scores)
    assert standing["love"] == "leads"
    assert sorted(standing.values()) == ["lags", "leads", "steadies"]
    assert standing["career"] == "steadies"  # zero spread


# ── determinism ──────────────────────────────────────────────────────────────

def test_same_inputs_produce_byte_identical_reports():
    a = _report(7, 3)
    b = _report(7, 3)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_two_natals_in_the_same_week_do_not_receive_the_same_opening():
    """natal * 3 mod 11 separates readers, so a household comparing phones
    does not see one generated-looking template."""
    openings = {n: _report(n, 0)["opening"] for n in SAMPLE_NATALS}
    assert len(set(openings.values())) == len(SAMPLE_NATALS), openings


# ── the claim-consistency gate: a report may not contradict its own data ─────

@pytest.mark.parametrize("natal", SAMPLE_NATALS)
def test_anchors_name_the_actual_extremes(natal):
    """The single gate no previous corpus needed.

    Daily copy makes no checkable claim about anything outside itself. A report
    does: it names a peak day. If that day is not the highest-energy day in the
    window, the report is not merely repetitive, it is WRONG — and wrong in a
    way a reader can verify against the calendar screen we already ship.
    """
    for w in range(WEEKS):
        rep = _report(natal, w)
        energies = rep["energies"]
        peak = rep["anchors"]["peak"]
        trough = rep["anchors"]["trough"]

        assert peak["energy"] == max(energies), rep["week_start"]
        assert trough["energy"] == min(energies), rep["week_start"]

        start = date.fromisoformat(rep["week_start"])
        assert (date.fromisoformat(peak["date"]) - start).days == energies.index(max(energies))
        assert (date.fromisoformat(trough["date"]) - start).days == energies.index(min(energies))
        assert peak["weekday"] == date.fromisoformat(peak["date"]).strftime("%A")


@pytest.mark.parametrize("natal", SAMPLE_NATALS)
def test_reported_shape_and_spread_agree_with_the_energies(natal):
    for w in range(WEEKS):
        rep = _report(natal, w)
        assert rep["shape"] == shape_of(rep["energies"])
        assert rep["energy_spread"] == max(rep["energies"]) - min(rep["energies"])
        assert rep["turn"] == turn_of(rep["energies"], rep["shape"])
        if rep["shape"] == "even":
            assert rep["turn"] == "no_turn"


@pytest.mark.parametrize("natal", SAMPLE_NATALS)
def test_standing_names_three_distinct_areas_with_distinct_roles(natal):
    for w in range(WEEKS):
        rep = _report(natal, w)
        roles = sorted(rep["standing"].values())
        assert roles == ["lags", "leads", "steadies"], rep["week_start"]
        assert set(rep["standing"]) == set(rep["standing_lines"])


# ── the reading-unit gate: consecutive weeks ─────────────────────────────────

@pytest.mark.parametrize("natal", SAMPLE_NATALS)
def test_no_repeated_opening_inside_the_guaranteed_window(natal):
    """17 consecutive weeks, the exact period the variant arithmetic promises.

    This is the assertion that would have caught a stride sharing a factor with
    the variant count — the report-cadence analogue of the 12-row table that
    hands every January the same row.
    """
    openings = [_report(natal, w)["opening"] for w in range(WEEKS)]
    for start in range(WEEKS - OPENING_VARIANTS + 1):
        window = openings[start : start + OPENING_VARIANTS]
        assert len(set(window)) == OPENING_VARIANTS, (
            f"natal {natal}, weeks {start}..{start + OPENING_VARIANTS}: repeat"
        )


@pytest.mark.parametrize("natal", SAMPLE_NATALS)
def test_no_repeated_turn_or_close_inside_their_windows(natal):
    # Turn lines are drawn per turn KIND and closes per SHAPE, and both keys are
    # data-driven, so the guarantee is per-key rather than blanket: within one
    # key the coprime stride must not repeat inside its own period.
    for start in range(WEEKS - TURN_VARIANTS + 1):
        by_kind: dict[str, list[str]] = {}
        for w in range(start, start + TURN_VARIANTS):
            rep = _report(natal, w)
            by_kind.setdefault(rep["turn"], []).append(rep["turn_line"])
        for kind, lines in by_kind.items():
            assert len(set(lines)) == len(lines), f"natal {natal} kind {kind}: {lines}"
    for start in range(WEEKS - CLOSE_VARIANTS + 1):
        by_shape: dict[str, list[str]] = {}
        for w in range(start, start + CLOSE_VARIANTS):
            rep = _report(natal, w)
            by_shape.setdefault(rep["shape"], []).append(rep["close"])
        for shape, lines in by_shape.items():
            assert len(set(lines)) == len(lines), f"natal {natal} shape {shape}: {lines}"


@pytest.mark.parametrize("natal", SAMPLE_NATALS)
def test_no_two_consecutive_weeks_are_identical_reports(natal):
    """The weakest possible version of the above, asserted separately because
    it is the one a user would notice within a fortnight."""
    for w in range(WEEKS - 1):
        a, b = _report(natal, w), _report(natal, w + 1)
        assert (a["opening"], a["turn_line"], a["close"]) != (
            b["opening"], b["turn_line"], b["close"]
        ), f"natal {natal} weeks {w}/{w + 1} identical"


def test_variant_periods_are_mutually_coprime_and_clear_of_the_calendar():
    """The arithmetic the whole scheme rests on, asserted as arithmetic.

    52 is weeks-per-year; a variant count sharing a factor with it would lock
    to the calendar. Pairwise coprimality is what makes the combined period the
    product rather than something much smaller.
    """
    from math import gcd
    for n in (OPENING_VARIANTS, TURN_VARIANTS, CLOSE_VARIANTS):
        assert gcd(n, 52) == 1, n
    assert gcd(OPENING_VARIANTS, TURN_VARIANTS) == 1
    assert gcd(OPENING_VARIANTS, CLOSE_VARIANTS) == 1
    assert gcd(TURN_VARIANTS, CLOSE_VARIANTS) == 1
    assert OPENING_VARIANTS * TURN_VARIANTS * CLOSE_VARIANTS == 595


# ── coverage: every authored cell is reachable ───────────────────────────────

def test_every_authored_line_is_drawable():
    """A cell no rotation can reach is dead copy that still passes every
    distinctness gate. Asserted over the variant space directly rather than by
    hoping the sample span happens to hit each one."""
    for shape in SHAPES:
        drawn = {
            CONTENT["shape"][shape]["openings"][R._variant(OPENING_VARIANTS, wk, 0, 1)]
            for wk in range(OPENING_VARIANTS)
        }
        assert len(drawn) == OPENING_VARIANTS, shape
    for kind in TURN_KINDS:
        drawn = {
            CONTENT["turn"][kind]["lines"][R._variant(TURN_VARIANTS, wk, 0, 3, 1)]
            for wk in range(TURN_VARIANTS)
        }
        assert len(drawn) == TURN_VARIANTS, kind


def test_the_classifier_is_not_degenerate_on_real_sky_data():
    """THE TEST THAT CAUGHT THE ORIGINAL DESIGN ERROR.

    The first taxonomy (rising/falling/cresting/dipping/volatile/flat) failed
    here with `{'volatile', 'cresting'}` — real data produced two of six, and
    four sixths of the authored corpus was unreachable copy that every
    distinctness gate still passed. A corpus can be flawless and still describe
    a shape the data does not have.

    Keep this assertion aimed at REAL sky rather than synthetic series. Any
    future retune of `score_rules` (the tara energies especially, which are what
    make the series a sawtooth) can silently collapse the distribution again,
    and this is the only thing watching for it.
    """
    seen = {
        _report(natal, w)["shape"]
        for natal in SAMPLE_NATALS
        for w in range(WEEKS)
    }
    assert len(seen) >= 4, f"classifier looks degenerate on real data: {seen}"


def test_even_is_currently_unreachable_and_that_is_recorded_not_hidden():
    """`even` requires a weekly spread under 12. Measured across 27 natal stars
    x 26 weeks, the observed spread was 48-70 in EVERY week, because tara's nine
    energies alternate by design and tara advances one step per day.

    So `even` and its `no_turn` partner are dead copy under `content_v3_2` —
    kept deliberately, for two reasons. `shape_of` must be total (a report with
    no shape has no opening to draw), and `score_rules` is tunable without a
    code change, so a future retune that flattens tara makes this class live
    immediately with copy already gated. Recording the fact in a test is the
    honest alternative to quietly shipping unreachable cells.

    If this test starts FAILING, `even` has become reachable — delete it and
    let `test_the_classifier_is_not_degenerate_on_real_sky_data` cover the case.
    """
    shapes = [_report(natal, w)["shape"] for natal in SAMPLE_NATALS for w in range(WEEKS)]
    assert "even" not in shapes
    spreads = [_report(natal, w)["energy_spread"] for natal in SAMPLE_NATALS for w in range(4)]
    assert min(spreads) >= R.EVEN_SPREAD, min(spreads)


def test_report_rejects_a_non_monday_start():
    with pytest.raises(ValueError):
        build_weekly_report(0, FIRST_MONDAY + timedelta(days=1), RULES, CONTENT)


def test_roles_and_shapes_constants_match_the_seed():
    assert set(CONTENT["shape"]) == set(SHAPES)
    assert set(CONTENT["close"]) == set(SHAPES)
    assert set(CONTENT["turn"]) == set(TURN_KINDS)
    assert all(
        f"{a}.{r}" in CONTENT["standing"]
        for a in RULES["areas"]["order"]
        for r in ROLES
    )
