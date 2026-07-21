"""Falsification: prove the report gates actually fire.

METHOD, copied deliberately from tests/test_identity_gates_falsify.py: mutate a
deep copy of the real seed (or the real composition inputs) in memory, then call
**the actual gate function** — never a reimplementation, which would only prove
that a copy of the logic works, the one thing not in question. Every red is
paired with a green on the unmutated input, so a gate that fails on everything
cannot masquerade as a discriminating one.

MORE THAN ONE SIGNATURE. A gate can stay green under a *fallback-shaped*
violation — one that removes the thing being checked rather than corrupting it.
Two gates here have that shape and each gets a second signature:

  * the sliding-window distinctness gate goes vacuously green if the span is
    shorter than the window (the `range()` is empty), so a second test asserts
    the span is long enough for the window to exist at all; and
  * the anchor gate goes vacuously green if the week loop never executes, so a
    second test asserts the loop body actually ran.

Both are the report-shaped version of the `seeded_pairs(data) == []` signature
in the identity suite: prove the work-list is non-empty, or the pass means
nothing.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from math import gcd

import pytest

import engine.reports as R
import tests.test_report_composition as C
import tests.test_report_content_seed as G


def _data() -> dict:
    """The WEEKLY corpus, matching what G._load() returns — mutations land on
    the same structure the gates read."""
    return json.loads(G.SEED_PATH.read_text())["weekly"]


def _expect_red(monkeypatch, data, gate, *args) -> str:
    monkeypatch.setattr(G, "_load", lambda: data)
    with pytest.raises(AssertionError) as exc:
        gate(*args)
    return str(exc.value)


def _expect_green(monkeypatch, gate, *args) -> None:
    monkeypatch.setattr(G, "_load", lambda: json.loads(G.SEED_PATH.read_text())["weekly"])
    gate(*args)


# ── word share ───────────────────────────────────────────────────────────────

def _token(*parts) -> str:
    """Letters-only synthetic token — WORD_RE is [a-z']+, so digits would split."""
    return "z" + "q".join(
        "".join(chr(ord("a") + int(d)) for d in str(p)) for p in parts
    )


def _synthetic(n_lines: int, filler: str, repeat_in: int) -> dict:
    """A full-size corpus where `filler` sits in exactly `repeat_in` lines and
    every other token is unique — so the only possible offender is `filler`."""
    lines = []
    for i in range(n_lines):
        body = " ".join(_token(i, j) for j in range(9))
        lines.append(f"{filler} {body}." if i < repeat_in else f"{body}.")
    data = _data()
    it = iter(lines)
    for cell in data["shape"].values():
        cell["openings"] = [next(it) for _ in cell["openings"]]
    for cell in data["turn"].values():
        cell["lines"] = [next(it) for _ in cell["lines"]]
    for cell in data["standing"].values():
        cell["lines"] = [next(it) for _ in cell["lines"]]
    for cell in data["close"].values():
        cell["lines"] = [next(it) for _ in cell["lines"]]
    return data


def test_share_gate_fires_at_over_limit_and_passes_at_the_limit():
    """BOTH edges. Firing only above proves *a* threshold; passing exactly at
    the limit proves it is THE threshold the spec states."""
    n = 257
    limit = G._share_limit(n)
    assert limit == 15

    at = _synthetic(n, "template", limit)
    assert G.check_word_share(at) == {}, "the limit itself must pass"

    over = _synthetic(n, "template", limit + 1)
    assert G.check_word_share(over) == {"template": limit + 1}


def test_frame_exemption_is_load_bearing_in_both_directions(monkeypatch):
    """`week` may saturate the corpus; `momentum` at the same rate may not.

    Without both halves, FRAME_WORDS is an escape hatch that grows every time
    the cap is inconvenient.
    """
    n = 257
    over = G._share_limit(n) + 1
    assert G.check_word_share(_synthetic(n, "week", over)) == {}
    assert G.check_word_share(_synthetic(n, "momentum", over)) == {"momentum": over}


def test_share_gate_fires_on_the_real_corpus_with_real_prose(monkeypatch):
    """A nonsense token would fire trivially. This tops up a word that already
    exists in the corpus, so the fixture has to count what is there first."""
    data = _data()
    word = "deliberately"
    lines = G._all_lines(data)
    limit = G._share_limit(len(lines))
    have = sum(1 for line in lines if word in G._content_words(line))

    need = limit + 1 - have
    assert need > 0, "fixture assumption broken: word already over the cap"
    topped = 0
    for shape in data["shape"].values():
        for i, line in enumerate(shape["openings"]):
            if topped >= need:
                break
            if word not in G._content_words(line):
                shape["openings"][i] = line[:-1] + ", deliberately."
                topped += 1
    assert topped == need

    offenders = G.check_word_share(data)
    assert word in offenders, offenders
    assert offenders[word] == limit + 1


# ── distinctness / banned vocabulary ─────────────────────────────────────────

def test_shared_opening_frame_between_two_shapes_is_caught(monkeypatch):
    data = _data()
    stolen = data["shape"]["front"]["openings"][0]
    data["shape"]["back"]["openings"][0] = stolen
    msg = _expect_red(monkeypatch, data, G.test_no_two_shapes_share_an_opening_frame)
    assert "share opening" in msg
    _expect_green(monkeypatch, G.test_no_two_shapes_share_an_opening_frame)


def _skeleton_twin(source: str) -> str:
    """A different sentence with an IDENTICAL skeleton.

    Built from `G._words(source)` rather than `source.split()`: splitting on
    whitespace leaves punctuation attached, so `"them,"` misses the stopword set
    and gets mangled into a content word, and the twin silently stops being a
    twin. Rebuilding through the same tokenizer the gate uses makes the skeleton
    equal by construction rather than by luck.
    """
    return " ".join(
        w if w in G.STOPWORDS else _token(i, len(w))
        for i, w in enumerate(G._words(source))
    )


def test_shared_skeleton_between_two_shapes_is_caught(monkeypatch):
    """The fixture self-verifies: if the mutation does not actually produce a
    matching skeleton, the test proves nothing."""
    data = _data()
    source = data["shape"]["front"]["openings"][1]
    mutated = _skeleton_twin(source)
    assert G._skeleton(source) == G._skeleton(mutated), "fixture is not skeleton-equal"
    assert source != mutated
    data["shape"]["back"]["openings"][1] = mutated
    msg = _expect_red(monkeypatch, data, G.test_no_two_shapes_share_an_opening_skeleton)
    assert "share skeleton" in msg
    _expect_green(monkeypatch, G.test_no_two_shapes_share_an_opening_skeleton)


def test_shared_standing_skeleton_within_a_role_is_caught(monkeypatch):
    data = _data()
    source = data["standing"]["love.leads"]["lines"][0]
    mutated = _skeleton_twin(source)
    assert G._skeleton(source) == G._skeleton(mutated), "fixture is not skeleton-equal"
    data["standing"]["money.leads"]["lines"][0] = mutated
    msg = _expect_red(
        monkeypatch, data, G.test_no_two_areas_share_a_standing_skeleton_in_the_same_role,
        "leads",
    )
    assert "skeleton" in msg
    _expect_green(
        monkeypatch, G.test_no_two_areas_share_a_standing_skeleton_in_the_same_role, "leads"
    )


@pytest.mark.parametrize("word", ["doom", "curse", "divorce", "inauspicious"])
def test_banned_vocabulary_is_caught(monkeypatch, word):
    data = _data()
    data["turn"]["whiplash"]["lines"][0] = f"This week may {word} the plan you had in mind."
    _expect_red(monkeypatch, data, G.test_no_banned_vocabulary)
    _expect_green(monkeypatch, G.test_no_banned_vocabulary)


@pytest.mark.parametrize(
    "line",
    [
        "Money will bring what you have been waiting for, and the week confirms it.",
        "You are destined to close the deal that has been sitting open for months.",
        "This is the week a windfall lands, so keep the account details ready.",
        "You will succeed at whatever you attempt across these seven days now.",
    ],
)
def test_outcome_promises_are_caught(monkeypatch, line):
    """The gate that keeps a report falsifiable. "The week is front-loaded" can
    be checked against the numbers; "money will come to you" cannot be checked
    against anything."""
    data = _data()
    data["close"]["front"]["lines"][0] = line
    fired = False
    for pattern in G.FORTUNE_PATTERNS:
        monkeypatch.setattr(G, "_load", lambda: data)
        try:
            G.test_no_outcome_promises(pattern)
        except AssertionError:
            fired = True
            break
    assert fired, f"no fortune pattern caught: {line!r}"
    for pattern in G.FORTUNE_PATTERNS:
        _expect_green(monkeypatch, G.test_no_outcome_promises, pattern)


def test_structure_gate_catches_a_short_cell(monkeypatch):
    data = _data()
    data["shape"]["front"]["openings"].pop()
    msg = _expect_red(monkeypatch, data, G.test_every_shape_has_exactly_the_declared_openings)
    assert "front" in msg or "assert" in msg
    _expect_green(monkeypatch, G.test_every_shape_has_exactly_the_declared_openings)


def test_count_gate_catches_a_half_authored_seed(monkeypatch):
    """Every per-cell check can pass one cell at a time while the corpus is
    short overall, which is why the total is asserted separately."""
    data = _data()
    del data["shape"]["scattered"]
    _expect_red(monkeypatch, data, G.test_corpus_is_the_declared_size)
    _expect_green(monkeypatch, G.test_corpus_is_the_declared_size)


# ── the anchor / claim-consistency gate ──────────────────────────────────────

def test_anchor_gate_catches_a_report_that_misnames_its_peak(monkeypatch):
    """The gate no previous corpus needed: a report makes a checkable claim
    about data outside itself, so it can be WRONG rather than merely repetitive.
    """
    real = R.build_weekly_report

    def sabotaged(natal, monday, rules, content):
        rep = real(natal, monday, rules, content)
        # Point the peak anchor one day later than the actual maximum.
        start = date.fromisoformat(rep["week_start"])
        wrong = start + timedelta(days=(rep["energies"].index(max(rep["energies"])) + 1) % 7)
        rep["anchors"]["peak"]["date"] = wrong.isoformat()
        rep["anchors"]["peak"]["weekday"] = wrong.strftime("%A")
        return rep

    monkeypatch.setattr(C, "build_weekly_report", sabotaged)
    with pytest.raises(AssertionError):
        C.test_anchors_name_the_actual_extremes(0)

    monkeypatch.setattr(C, "build_weekly_report", real)
    C.test_anchors_name_the_actual_extremes(0)


def test_anchor_gate_catches_a_shape_that_contradicts_the_energies(monkeypatch):
    real = R.build_weekly_report

    def sabotaged(natal, monday, rules, content):
        rep = real(natal, monday, rules, content)
        rep["shape"] = "even" if rep["shape"] != "even" else "front"
        return rep

    monkeypatch.setattr(C, "build_weekly_report", sabotaged)
    with pytest.raises(AssertionError):
        C.test_reported_shape_and_spread_agree_with_the_energies(0)
    monkeypatch.setattr(C, "build_weekly_report", real)
    C.test_reported_shape_and_spread_agree_with_the_energies(0)


def test_anchor_gate_would_not_pass_vacuously():
    """SECOND SIGNATURE. The gate iterates weeks; with WEEKS == 0 the loop body
    never runs and the assertion passes having checked nothing. Prove the
    work-list is non-empty — the report analogue of `seeded_pairs(data) == []`.
    """
    assert C.WEEKS > 0
    assert len(C.SAMPLE_NATALS) > 0
    checked = 0
    for w in range(C.WEEKS):
        rep = C._report(0, w)
        assert rep["anchors"]["peak"]["energy"] == max(rep["energies"])
        checked += 1
    assert checked == C.WEEKS


# ── the consecutive-week distinctness gate ───────────────────────────────────

def test_distinctness_gate_catches_a_stride_sharing_a_factor(monkeypatch):
    """THE FAILURE THIS WHOLE SCHEME EXISTS TO PREVENT.

    A stride sharing a factor with the variant count collapses the rotation —
    the report-cadence analogue of a 12-row table indexed by month handing every
    January the same row. With stride 11 against 11 variants the index never
    advances at all, so every week draws the same opening.
    """
    real = R._variant

    def collapsed(count, wk, natal_index, stride, salt=0):
        if count == R.OPENING_VARIANTS:
            return (wk * R.OPENING_VARIANTS + natal_index * 3 + salt) % count
        return real(count, wk, natal_index, stride, salt)

    monkeypatch.setattr(R, "_variant", collapsed)
    with pytest.raises(AssertionError) as exc:
        C.test_no_repeated_opening_inside_the_guaranteed_window(0)
    assert "repeat" in str(exc.value)

    monkeypatch.setattr(R, "_variant", real)
    C.test_no_repeated_opening_inside_the_guaranteed_window(0)


def test_distinctness_gate_catches_two_consecutive_identical_reports(monkeypatch):
    real = R._variant
    monkeypatch.setattr(R, "_variant", lambda count, wk, n, stride, salt=0: 0)
    with pytest.raises(AssertionError) as exc:
        C.test_no_two_consecutive_weeks_are_identical_reports(0)
    assert "identical" in str(exc.value)
    monkeypatch.setattr(R, "_variant", real)
    C.test_no_two_consecutive_weeks_are_identical_reports(0)


def test_distinctness_gate_would_not_pass_vacuously():
    """SECOND SIGNATURE, and the one that matters most here.

    The window gate is `for start in range(WEEKS - OPENING_VARIANTS + 1)`. If
    WEEKS ever drops below OPENING_VARIANTS that range is EMPTY and the gate
    passes having compared nothing — a green that means the span was too short,
    not that the copy was distinct. Assert the window exists.
    """
    assert C.WEEKS >= R.OPENING_VARIANTS, "span shorter than the window it checks"
    assert C.WEEKS - R.OPENING_VARIANTS + 1 > 0
    windows = list(range(C.WEEKS - R.OPENING_VARIANTS + 1))
    assert len(windows) >= 2, "at least two windows or the slide is not exercised"


def test_the_coprimality_premise_is_itself_guarded():
    """Not a test of our code so much as of the fact our code depends on.

    If any variant count shared a factor with 52, the rotation would lock to the
    calendar however carefully the strides were chosen.
    """
    assert gcd(17, 52) == 1 and gcd(7, 52) == 1 and gcd(5, 52) == 1
    assert gcd(12, 52) == 4, "12 is the trap: a monthly table would lock"
    assert gcd(13, 52) == 13, (
        "13 is the same trap one door down: prime, yet it divides 52, so a "
        "13-slot rotation hands every 52-week anniversary the same cell"
    )
    assert gcd(26, 52) == 26


# ── the degeneracy gate that caught the original design error ────────────────

def test_degeneracy_gate_catches_a_classifier_that_collapses(monkeypatch):
    """This is the gate that failed on the FIRST taxonomy with
    `{'volatile', 'cresting'}`. Prove it still fires — it is the only thing
    watching for a score_rules retune silently flattening the distribution."""
    real = R.shape_of
    monkeypatch.setattr(R, "shape_of", lambda energies: "scattered")
    with pytest.raises(AssertionError) as exc:
        C.test_the_classifier_is_not_degenerate_on_real_sky_data()
    assert "degenerate" in str(exc.value)
    monkeypatch.setattr(R, "shape_of", real)
    C.test_the_classifier_is_not_degenerate_on_real_sky_data()


def test_determinism_gate_catches_a_report_that_varies_between_calls(monkeypatch):
    counter = {"n": 0}
    real = R._variant

    def drifting(count, wk, natal_index, stride, salt=0):
        counter["n"] += 1
        return (real(count, wk, natal_index, stride, salt) + counter["n"]) % count

    monkeypatch.setattr(R, "_variant", drifting)
    with pytest.raises(AssertionError):
        C.test_same_inputs_produce_byte_identical_reports()
    monkeypatch.setattr(R, "_variant", real)
    C.test_same_inputs_produce_byte_identical_reports()


def test_reader_desync_gate_catches_a_natal_independent_rotation(monkeypatch):
    """Drop the natal term and every reader receives the same report."""
    real = R._variant
    monkeypatch.setattr(
        R, "_variant", lambda count, wk, n, stride, salt=0: (wk * stride + salt) % count
    )
    with pytest.raises(AssertionError):
        C.test_two_natals_in_the_same_week_do_not_receive_the_same_opening()
    monkeypatch.setattr(R, "_variant", real)
    C.test_two_natals_in_the_same_week_do_not_receive_the_same_opening()


# ═════════════════════════════════════════════════════════════════════════════
# CROSS-KIND GATES (tests/test_report_cross_kind.py)
#
# Same method: mutate a deep copy, call the REAL gate, pair every red with a
# green. The signature that matters most here is the VACUOUS PASS: every
# cross-kind gate iterates a work-list built from BOTH corpora, and a monthly
# corpus that fails to load would empty that list and turn every comparison
# into a no-comparison. That shape gets its own falsifications.
# ═════════════════════════════════════════════════════════════════════════════

import tests.test_report_cross_kind as X  # noqa: E402


def _monthly() -> dict:
    return json.loads(G.SEED_PATH.read_text())["monthly"]


def _patch_monthly(monkeypatch, data: dict) -> None:
    monkeypatch.setattr(G, "_load_monthly", lambda: data)


def test_cross_kind_frame_gate_fires_on_a_shared_frame(monkeypatch):
    """A monthly opening that opens with a weekly opening's first four words."""
    weekly_line = G._load()["shape"]["front"]["openings"][0]
    data = _monthly()
    words = G._words(weekly_line)[:4]
    data["shape"]["core"]["openings"][0] = (
        " ".join(words) + " month carrier week claim for the falsification."
    )
    _patch_monthly(monkeypatch, data)
    with pytest.raises(AssertionError):
        X.test_no_weekly_and_monthly_line_share_a_frame_in_the_same_slot("opening")
    monkeypatch.setattr(G, "_load_monthly", lambda: _monthly())
    X.test_no_weekly_and_monthly_line_share_a_frame_in_the_same_slot("opening")


def test_cross_kind_skeleton_gate_fires_on_a_skeleton_twin(monkeypatch):
    """The padded-pair failure itself: one sentence shape across two kinds."""
    weekly_line = G._load()["standing"]["money.leads"]["lines"][0]
    twin = _skeleton_twin(weekly_line)
    assert G._skeleton(twin) == G._skeleton(weekly_line), "fixture is not skeleton-equal"
    data = _monthly()
    data["standing"]["money.leads"]["lines"][0] = twin
    _patch_monthly(monkeypatch, data)
    with pytest.raises(AssertionError):
        X.test_no_weekly_and_monthly_line_share_a_skeleton_in_the_same_slot("standing")
    monkeypatch.setattr(G, "_load_monthly", lambda: _monthly())
    X.test_no_weekly_and_monthly_line_share_a_skeleton_in_the_same_slot("standing")


@pytest.mark.parametrize("token", ["Thursday", "tomorrow", "morning", "days"])
def test_division_gate_fires_when_monthly_copy_names_a_day(monkeypatch, token):
    data = _monthly()
    data["turn"]["hinge"]["lines"][0] = (
        f"The month pivots and {token} is when the pivot in question lands."
    )
    _patch_monthly(monkeypatch, data)
    with pytest.raises(AssertionError):
        X.test_monthly_copy_never_speaks_in_days()
    monkeypatch.setattr(G, "_load_monthly", lambda: _monthly())
    X.test_monthly_copy_never_speaks_in_days()


def test_division_gate_fires_when_weekly_copy_names_the_month(monkeypatch):
    data = _data()
    data["close"]["front"]["lines"][0] = (
        "Close the week early and let the month absorb whatever remains open."
    )
    monkeypatch.setattr(G, "_load", lambda: data)
    with pytest.raises(AssertionError):
        X.test_weekly_copy_never_speaks_in_months()
    monkeypatch.setattr(G, "_load", lambda: json.loads(G.SEED_PATH.read_text())["weekly"])
    X.test_weekly_copy_never_speaks_in_months()


def test_unit_anchoring_gate_fires_on_a_bare_halves_claim(monkeypatch):
    """A monthly turn line that never names the month could sit in either
    report — the exact ambiguity the positive obligation exists to prevent."""
    data = _monthly()
    data["turn"]["lifts"]["lines"][0] = (
        "The second half runs stronger than the first, so move what can move."
    )
    _patch_monthly(monkeypatch, data)
    with pytest.raises(AssertionError):
        X.test_monthly_openings_and_turns_name_the_month()
    monkeypatch.setattr(G, "_load_monthly", lambda: _monthly())
    X.test_monthly_openings_and_turns_name_the_month()


def test_standing_overlap_gate_fires_at_four_shared_content_words(monkeypatch):
    """BOTH edges of the ≤3 cap, built from the real weekly line's own words."""
    weekly_line = G._load()["standing"]["love.leads"]["lines"][0]
    content = sorted(G._content_words(weekly_line) - {"love"})
    assert len(content) >= 4, "fixture needs four content words to borrow"
    data = _monthly()
    data["standing"]["love.leads"]["lines"][0] = (
        "For the month " + " ".join(content[:4]) + " in a sentence long enough to pass."
    )
    _patch_monthly(monkeypatch, data)
    with pytest.raises(AssertionError):
        X.test_same_key_standing_pairs_differ_beyond_the_area_noun()

    data2 = _monthly()
    data2["standing"]["love.leads"]["lines"][0] = (
        "For the month " + " ".join(content[:3]) + " in a sentence long enough to pass."
    )
    _patch_monthly(monkeypatch, data2)
    X.test_same_key_standing_pairs_differ_beyond_the_area_noun()  # 3 shared: at the cap

    monkeypatch.setattr(G, "_load_monthly", lambda: _monthly())
    X.test_same_key_standing_pairs_differ_beyond_the_area_noun()


def test_cross_kind_gates_cannot_pass_on_an_empty_work_list(monkeypatch):
    """THE VACUOUS-PASS SHAPE, in both of its guards.

    If the monthly corpus fails to load as empty cells, (1) the declared-size
    pin fails loudly, and (2) each comparison gate's own non-empty assert
    fails rather than iterating nothing to a green. Both reds are proven, so
    an empty work-list has no path to a pass."""
    hollow = {
        "shape": {s: {"openings": []} for s in _monthly()["shape"]},
        "turn": {t: {"lines": []} for t in _monthly()["turn"]},
        "standing": {k: {"lines": []} for k in _monthly()["standing"]},
        "close": {s: {"lines": []} for s in _monthly()["close"]},
    }
    _patch_monthly(monkeypatch, hollow)
    with pytest.raises(AssertionError):
        X.test_the_work_lists_are_the_declared_sizes()
    with pytest.raises(AssertionError) as exc:
        X.test_no_weekly_and_monthly_line_share_a_frame_in_the_same_slot("opening")
    assert "vacuous" in str(exc.value)
    with pytest.raises(AssertionError):
        X.test_monthly_copy_never_speaks_in_days()

    monkeypatch.setattr(G, "_load_monthly", lambda: _monthly())
    X.test_the_work_lists_are_the_declared_sizes()


def test_monthly_share_gate_fires_at_over_limit_and_passes_at_the_limit():
    """The monthly denominator is its own: 208 lines → limit 12. A synthetic
    corpus with a filler in exactly 12 lines passes; 13 fires."""
    import tests.test_report_content_seed as S

    def synthetic(repeat_in: int) -> dict:
        data = _monthly()
        i = 0
        cells = (
            [c["openings"] for c in data["shape"].values()]
            + [c["lines"] for c in data["turn"].values()]
            + [c["lines"] for c in data["standing"].values()]
            + [c["lines"] for c in data["close"].values()]
        )
        for cell in cells:
            for j in range(len(cell)):
                body = " ".join(_token(i, k) for k in range(9))
                cell[j] = f"template {body}." if i < repeat_in else f"{body}."
                i += 1
        assert i == 208
        return data

    limit = S._share_limit(208)
    assert limit == 12
    assert S.check_word_share_monthly(synthetic(limit)) == {}
    assert S.check_word_share_monthly(synthetic(limit + 1)) == {"template": limit + 1}


# ── monthly composition sabotage ─────────────────────────────────────────────

import tests.test_report_monthly_composition as M  # noqa: E402


@pytest.fixture()
def _fresh_monthly_cache(monkeypatch):
    """M._mreport memoises composed reports; a sabotage that leaves stale
    entries behind would leak into later tests (or be masked by them)."""
    from functools import lru_cache
    monkeypatch.setattr(R, "build_daily_sky", lru_cache(maxsize=None)(R.build_daily_sky))
    M._mreport.cache_clear()
    yield
    M._mreport.cache_clear()


def test_monthly_anchor_gate_catches_a_mispointed_carrier_week(
    monkeypatch, _fresh_monthly_cache
):
    real = R.build_monthly_report

    def sabotaged(natal, year, month, rules, content):
        rep = real(natal, year, month, rules, content)
        weeks = rep["weeks"]
        means = [w["energy_mean"] for w in weeks]
        wrong = (means.index(max(means)) + 1) % len(weeks)
        rep["anchors"]["carrier_week"] = {
            "week_start": weeks[wrong]["week_start"],
            "energy_mean": weeks[wrong]["energy_mean"],
        }
        return rep

    monkeypatch.setattr(M, "build_monthly_report", sabotaged)
    with pytest.raises(AssertionError):
        M.test_anchors_name_the_actual_extreme_weeks(0)

    M._mreport.cache_clear()
    monkeypatch.setattr(M, "build_monthly_report", real)
    M.test_anchors_name_the_actual_extreme_weeks(0)


def test_monthly_window_gate_catches_a_collapsed_rotation(
    monkeypatch, _fresh_monthly_cache
):
    """Stride ≡ 0 mod 13 is the monthly 12-row trap: the opening index stops
    advancing and every month of a shape draws one cell."""
    real = R._variant

    def collapsed(count, wk, natal_index, stride, salt=0):
        if count == R.MONTH_OPENING_VARIANTS:
            return (wk * R.MONTH_OPENING_VARIANTS + natal_index * 3 + salt) % count
        return real(count, wk, natal_index, stride, salt)

    monkeypatch.setattr(R, "_variant", collapsed)
    with pytest.raises(AssertionError) as exc:
        M.test_no_repeated_opening_inside_thirteen_consecutive_months(0)
    assert "repeat" in str(exc.value)

    M._mreport.cache_clear()
    monkeypatch.setattr(R, "_variant", real)
    M.test_no_repeated_opening_inside_thirteen_consecutive_months(0)


def test_monthly_degeneracy_gate_catches_a_collapsed_classifier(
    monkeypatch, _fresh_monthly_cache
):
    real = R.month_shape_of
    monkeypatch.setattr(R, "month_shape_of", lambda means: "core")
    with pytest.raises(AssertionError) as exc:
        M.test_all_five_shapes_occur_across_a_realistic_span()
    assert "degenerate" in str(exc.value)

    M._mreport.cache_clear()
    monkeypatch.setattr(R, "month_shape_of", real)
    M.test_all_five_shapes_occur_across_a_realistic_span()


def test_monthly_window_gate_would_not_pass_vacuously():
    """The span must exceed the window or the sliding range is empty and the
    gate greens having compared nothing."""
    assert M.MONTHS_SPAN >= R.MONTH_OPENING_VARIANTS
    assert M.MONTHS_SPAN - R.MONTH_OPENING_VARIANTS + 1 >= 2


# ═════════════════════════════════════════════════════════════════════════════
# THE TRANSIT GATES, AND THE ONE THAT MATTERS MOST
#
# The fear gates are the first gates in this repo written against a failure
# mode that is INVISIBLE TO VOCABULARY. Everything else here falsifies by
# planting a forbidden word or a broken number. Fear does not work like that —
# § 6.6's example is dread built from entirely permitted words:
#
#     "This is a demanding stretch. Old patterns surface. What you built may be
#      tested in ways that are not immediately obvious."
#
# So the signatures below escalate deliberately. Gates 1-4 are falsified the
# ordinary way, one planted signature each and more than one per gate. Gate 5
# is falsified by INFLATING EVERY DEMANDING LINE 40% WITH PERMITTED WORDS, and
# the test asserts that gates 1-4 STAY GREEN while gate 5 goes red. That is the
# entire argument for gate 5's existence, and it is the case a vocabulary scan
# structurally cannot see.
# ═════════════════════════════════════════════════════════════════════════════

import tests.test_transit_content_seed as TG  # noqa: E402


def _tdata() -> dict:
    return json.loads(TG.SEED_PATH.read_text())["transit"]


def _t_red(monkeypatch, data, gate, *args) -> str:
    monkeypatch.setattr(TG, "_load", lambda: data)
    with pytest.raises(AssertionError) as exc:
        gate(*args)
    return str(exc.value)


def _t_green(monkeypatch, gate, *args) -> None:
    monkeypatch.setattr(TG, "_load", lambda: json.loads(TG.SEED_PATH.read_text())["transit"])
    gate(*args)


# ── structure and share ──────────────────────────────────────────────────────

def test_transit_size_pin_catches_a_half_authored_corpus(monkeypatch):
    """THE VACUOUS-PASS SIGNATURE. An emptied demanding corpus must fail the
    declared-size pin — otherwise every fear gate below would iterate an empty
    work-list and go green having examined nothing, which is the most dangerous
    possible outcome for this particular battery."""
    data = _tdata()
    for key in list(data["passage"]):
        if not TG._is_supportive(key):
            data["passage"][key]["lines"] = []
    msg = _t_red(monkeypatch, data, TG.test_transit_corpus_is_the_declared_size)
    assert "71" in msg or "==" in msg
    _t_green(monkeypatch, TG.test_transit_corpus_is_the_declared_size)


def test_transit_share_cap_catches_a_dominating_word(monkeypatch):
    data = _tdata()
    keys = list(data["passage"])
    for i in range(G._share_limit(71) + 1):
        data["passage"][keys[i]]["lines"][0] += " Momentum."
    assert "momentum" in TG.check_word_share(data)
    monkeypatch.setattr(TG, "_load", lambda: data)
    with pytest.raises(AssertionError):
        TG.test_transit_no_content_word_dominates()
    _t_green(monkeypatch, TG.test_transit_no_content_word_dominates)


def test_transit_frame_exemption_is_load_bearing_in_both_directions(monkeypatch):
    """`Saturn` saturating must PASS and an ordinary word at the same rate must
    FAIL — otherwise the frame list is an escape hatch that grows every time
    the cap is inconvenient."""
    data = _tdata()
    saturny = sum(
        1 for ln in TG._all_lines(data) if set(G._words(ln)) & {"saturn", "saturn's"}
    )
    assert saturny > G._share_limit(71)
    assert TG.check_word_share(data) == {}


# ── FEAR GATE 1: planet as agent — three signatures ──────────────────────────

@pytest.mark.parametrize(
    "planted,rx,label",
    [
        ("Saturn tests you here, and the pressure is real. Keep your routines "
         "and let the passage run its course.",
         TG.AGENT_ADJACENT, "adjacent"),
        ("Rahu quietly pulls your attention away from home. Track where it "
         "goes and protect one steady routine.",
         TG.AGENT_ADJACENT, "adverb between"),
        ("Jupiter brings opportunity toward the work you have been building. "
         "Accept the openings and staff them properly.",
         TG.AGENT_VERBS, "agency verb, no direct object"),
        ("Whatever you have built will be examined closely by Saturn before "
         "this passage finishes. Keep the paperwork exact.",
         TG.PASSIVE_AGENT, "passive"),
    ],
)
def test_planet_agency_gate_fires_on_more_than_one_signature(
    monkeypatch, planted, rx, label
):
    """FOUR signatures across the three patterns, because the fatalism claim
    reappears in a new grammar the moment one form is banned. The passive is
    the one a careful author reaches for after the active is closed."""
    data = _tdata()
    data["passage"]["Saturn.1"]["lines"] = [planted]
    monkeypatch.setattr(TG, "_load", lambda: data)
    with pytest.raises(AssertionError) as exc:
        TG.test_no_planet_acts_on_the_reader(rx, label)
    assert planted in str(exc.value)
    _t_green(monkeypatch, TG.test_no_planet_acts_on_the_reader, rx, label)


def test_planet_agency_gate_permits_a_locative(monkeypatch):
    """The discrimination, checked from the other side: a planet may be WHERE
    it is. If this went red the gate would be unusable and the corpus could not
    name a position at all — which is the one thing transit copy must do."""
    data = _tdata()
    data["passage"]["Saturn.1"]["lines"] = [
        "Saturn stands in your own footing and sits over the ordinary business "
        "of the body. Move deliberately and keep your standards high."
    ]
    monkeypatch.setattr(TG, "_load", lambda: data)
    for rx, label in ((TG.AGENT_ADJACENT, "a"), (TG.AGENT_VERBS, "b"), (TG.PASSIVE_AGENT, "c")):
        TG.test_no_planet_acts_on_the_reader(rx, label)


# ── FEAR GATE 2: actionless difficulty — two signatures ──────────────────────

@pytest.mark.parametrize(
    "planted,label",
    [
        ("Saturn is over your own footing, and old patterns surface here. "
         "What you built may be examined in ways that are not immediately obvious.",
         "the section 6.6 example — permitted words only"),
        ("Rahu sits over joint finances and the things nobody discusses. "
         "The appetite for shortcuts is strong and the exposure is genuine.",
         "named and bounded but with no move"),
    ],
)
def test_actionless_demanding_line_is_caught(monkeypatch, planted, label):
    """The § 6.6 example itself is signature one. It carries zero banned words,
    zero intensifiers, no promise and no planet-as-agent — it passes gates 1, 3
    and 4 outright — and it is exactly the copy this product must never ship."""
    data = _tdata()
    data["passage"]["Saturn.1"]["lines"] = [planted]
    msg = _t_red(monkeypatch, data, TG.test_every_demanding_line_carries_an_action)
    assert planted in msg, label
    _t_green(monkeypatch, TG.test_every_demanding_line_carries_an_action)


# ── FEAR GATE 3: unbounded difficulty — two signatures ───────────────────────

@pytest.mark.parametrize(
    "planted,label",
    [
        ("Saturn asks a great deal and the asking does not let up. "
         "Reduce, simplify, and accept that some things must give.",
         "actionable but names no domain and no horizon"),
        ("Jupiter enlarges whatever it touches and the consequences spread. "
         "Choose carefully and prepare for more than you expected.",
         "actionable, vivid, entirely unbounded"),
    ],
)
def test_unbounded_demanding_line_is_caught(monkeypatch, planted, label):
    """Both signatures carry an action, so gate 2 passes them. What neither
    carries is a domain or a horizon — the reader finishes not knowing what is
    demanding or when it ends, which is the definition of dread."""
    data = _tdata()
    data["passage"]["Saturn.1"]["lines"] = [planted]
    msg = _t_red(monkeypatch, data, TG.test_every_demanding_line_is_bounded)
    assert planted in msg, label
    _t_green(monkeypatch, TG.test_every_demanding_line_is_bounded)


# ── FEAR GATE 4: intensifiers — two signatures ───────────────────────────────

@pytest.mark.parametrize("word", ["relentless", "devastating"])
def test_intensifier_gate_fires(monkeypatch, word):
    data = _tdata()
    planted = (
        f"Saturn is over your own footing and the {word} part of it is the pace. "
        "Move deliberately and keep your standards steady."
    )
    data["passage"]["Saturn.1"]["lines"] = [planted]
    msg = _t_red(monkeypatch, data, TG.test_no_intensifiers_anywhere_in_the_transit_corpus)
    assert word in msg
    _t_green(monkeypatch, TG.test_no_intensifiers_anywhere_in_the_transit_corpus)


def test_intensifiers_are_not_already_banned_words(monkeypatch):
    """Gate 4 must be doing work the existing vocabulary gate does not. If
    these were already in BANNED_WORDS the gate would be decoration."""
    assert not (TG.INTENSIFIERS & G.BANNED_WORDS)


# ── FEAR GATE 5: THE SYMMETRY GATE — the signature that cannot be gamed ──────

#: Padding built ENTIRELY from words already present in the shipped corpus and
#: permitted by every other gate. No banned word, no intensifier, no promise,
#: no planet as agent, a domain noun and an action verb in every fragment — so
#: gates 1-4 cannot see any of it.
PERMITTED_PADDING = [
    "Give this the attention it asks for and keep the pace steady.",
    "Hold your routines and protect the basics of sleep and food.",
    "Notice what the work costs you and record it honestly.",
    "Keep your commitments small and check them against what you can carry.",
]


def _inflate_demanding(data: dict, factor: float = 0.4) -> dict:
    """Grow every demanding passage line by ~`factor`, using permitted words
    only. This is what fear-selling looks like from the outside: the hard copy
    quietly acquires more words than the easy copy."""
    for key, cell in data["passage"].items():
        if TG._is_supportive(key):
            continue
        line = cell["lines"][0]
        target = int(len(G._words(line)) * factor)
        added, i = 0, 0
        parts = [line]
        while added < target:
            frag = PERMITTED_PADDING[i % len(PERMITTED_PADDING)]
            parts.append(frag)
            added += len(G._words(frag))
            i += 1
        cell["lines"] = [" ".join(parts)]
    return data


@pytest.mark.parametrize("body", ["Saturn", "Jupiter", "Rahu"])
def test_symmetry_gate_fires_on_permitted_word_inflation(monkeypatch, body):
    """THE DECISIVE SIGNATURE, and the reason gate 5 exists at all.

    Every demanding line grows 40% using nothing but vocabulary the corpus
    already ships. A vocabulary scan CANNOT see this — there is no word to
    find. What can see it is the measurement over the library: the demanding
    copy is now visibly longer than the supportive copy for the same mover,
    which is the statistical fingerprint of fear-selling.
    """
    data = _inflate_demanding(_tdata())
    stats = TG.symmetry_stats(data, body)
    assert stats["length_ratio"] > 1 + TG.SYMMETRY_LENGTH_TOLERANCE, stats
    gate = TG.test_demanding_and_supportive_copy_are_statistically_comparable
    _t_red(monkeypatch, data, gate, body)
    _t_green(monkeypatch, gate, body)


def test_the_inflated_corpus_still_passes_gates_one_through_four(monkeypatch):
    """THE OTHER HALF OF THE ARGUMENT, and the whole point of the exercise.

    If the inflated corpus also tripped gates 1-4, gate 5 would be redundant
    and could be deleted. It does not: the padding is built from permitted
    words, so the vocabulary and grammar gates see nothing wrong with it. Only
    the symmetry measurement catches it — which is precisely why a corpus can
    pass every gate this repo had before transit and still read as dread.
    """
    data = _inflate_demanding(_tdata())
    monkeypatch.setattr(TG, "_load", lambda: data)

    for rx, label in (
        (TG.AGENT_ADJACENT, "adjacent"),
        (TG.AGENT_VERBS, "verb"),
        (TG.PASSIVE_AGENT, "passive"),
    ):
        TG.test_no_planet_acts_on_the_reader(rx, label)          # gate 1 green
    TG.test_every_demanding_line_carries_an_action()             # gate 2 green
    TG.test_every_demanding_line_is_bounded()                    # gate 3 green
    TG.test_no_intensifiers_anywhere_in_the_transit_corpus()     # gate 4 green
    TG.test_transit_no_banned_vocabulary()                       # and the old gate

    # ...and gate 5 is red.
    with pytest.raises(AssertionError):
        TG.test_demanding_and_supportive_copy_are_statistically_comparable("Saturn")


def test_symmetry_gate_also_fires_on_density_alone(monkeypatch):
    """A second, independent signature: same word COUNT, denser words. An
    author who knows the length check exists would reach for exactly this —
    swap the function words out for content words and the line reads heavier
    at identical length."""
    data = _tdata()
    for key, cell in data["passage"].items():
        if TG._is_supportive(key):
            continue
        n = len(G._words(cell["lines"][0]))
        cell["lines"] = [" ".join(["pressure", "burden", "weight", "cost"] * n)[: 400]]
    stats = TG.symmetry_stats(data, "Saturn")
    assert stats["density_gap"] > TG.SYMMETRY_DENSITY_TOLERANCE, stats
    _t_red(
        monkeypatch, data,
        TG.test_demanding_and_supportive_copy_are_statistically_comparable, "Saturn",
    )


def test_symmetry_stats_refuses_an_empty_side(monkeypatch):
    """The vacuous-pass signature for gate 5 specifically: if either side is
    emptied, the ratio is undefined and the gate must refuse rather than
    divide by zero into a green."""
    data = _tdata()
    for key in list(data["passage"]):
        if TG._is_supportive(key) and key.startswith("Saturn"):
            data["passage"][key]["lines"] = []
    with pytest.raises(AssertionError):
        TG.symmetry_stats(data, "Saturn")


# ── cross-kind, three ways ───────────────────────────────────────────────────

def test_transit_calendar_trespass_gate_fires(monkeypatch):
    """A transit line naming a calendar unit is asserting a cadence the
    artefact does not have."""
    data = _tdata()
    data["passage"]["Saturn.1"]["lines"] = [
        "Saturn is on your own footing this month and the week ahead asks for "
        "care. Move deliberately and keep your standards steady."
    ]
    monkeypatch.setattr(TG, "_load", lambda: data)
    with pytest.raises(AssertionError):
        X.test_transit_copy_never_names_a_calendar_unit()
    _t_green(monkeypatch, X.test_transit_copy_never_names_a_calendar_unit)


def test_range_report_planet_trespass_gate_fires(monkeypatch):
    """The other direction: a weekly line naming a planet is making transit's
    claim inside a range report."""
    data = _data()
    data["shape"]["front"]["openings"][0] = (
        "Saturn sits behind the front of this week, and the strong days land "
        "early. Take the openings while they are there."
    )
    monkeypatch.setattr(G, "_load", lambda: data)
    with pytest.raises(AssertionError):
        X.test_the_range_reports_never_name_a_planet_or_a_passage()
    monkeypatch.setattr(G, "_load", lambda: json.loads(G.SEED_PATH.read_text())["weekly"])
    X.test_the_range_reports_never_name_a_planet_or_a_passage()


def test_transit_passage_must_name_its_mover_gate_fires(monkeypatch):
    data = _tdata()
    data["passage"]["Saturn.1"]["lines"] = [
        "Your own footing needs re-earning at present, which is why everything "
        "feels heavier. Move deliberately and let your standards decide."
    ]
    monkeypatch.setattr(TG, "_load", lambda: data)
    with pytest.raises(AssertionError) as exc:
        X.test_every_transit_passage_line_names_its_mover()
    assert "never names saturn" in str(exc.value)
    _t_green(monkeypatch, X.test_every_transit_passage_line_names_its_mover)


# ── within-reading collision ─────────────────────────────────────────────────

def test_within_reading_frame_gate_fires(monkeypatch):
    """Two movers opening identically in ONE payload — the collision surface
    no cross-kind or consecutive-reading gate can see."""
    data = _tdata()
    # The first four words must MATCH for a frame collision — which is the
    # realistic failure: two cells written from one template, the mover name
    # arriving later in the sentence.
    data["passage"]["Saturn.4"]["lines"] = [
        "Over the base you rest on, Saturn asks for repair rather than change. "
        "Fix what you have and sleep properly."
    ]
    data["passage"]["Jupiter.4"]["lines"] = [
        "Over the base you rest on, Jupiter enlarges comfort and expense alike. "
        "Enjoy that and keep the household numbers visible."
    ]
    monkeypatch.setattr(TG, "_load", lambda: data)
    with pytest.raises(AssertionError):
        X.test_two_movers_never_open_the_same_way_in_one_reading()
    _t_green(monkeypatch, X.test_two_movers_never_open_the_same_way_in_one_reading)


def test_within_reading_same_house_overlap_gate_fires(monkeypatch):
    """Two movers in the same house saying the same thing in different words —
    the sharper case, caught on content overlap rather than on frame."""
    data = _tdata()
    data["passage"]["Saturn.4"]["lines"] = [
        "Saturn presses on home, domestic life, rest and the household routine. "
        "Repair what you have and sleep properly."
    ]
    data["passage"]["Rahu.4"]["lines"] = [
        "Where home, domestic life, rest and the household routine are concerned, "
        "Rahu unsettles things. Keep one room steady."
    ]
    monkeypatch.setattr(TG, "_load", lambda: data)
    with pytest.raises(AssertionError) as exc:
        X.test_two_movers_in_the_same_house_do_not_say_the_same_thing()
    # The gate reports the FIRST offending pair in key order, which may be
    # Jupiter.4/Rahu.4 rather than Saturn.4/Rahu.4 — the planted Rahu line
    # collides with the shipped Jupiter one too. Either way it must be a
    # 4th-house pair, which is what the assertion checks.
    msg = str(exc.value)
    assert ".4 / " in msg and msg.split(":")[0].endswith(".4"), msg
    _t_green(monkeypatch, X.test_two_movers_in_the_same_house_do_not_say_the_same_thing)


def test_within_reading_work_list_would_not_pass_vacuously():
    """432 cross-mover pairs and 36 same-house pairs. If the corpus lost a
    mover the work-list would shrink and every gate above would green having
    compared less than it claims."""
    assert len(X.cross_mover_pairs()) == 432
    same_house = [
        1 for ka, _, kb, _ in X.cross_mover_pairs() if ka.split(".")[1] == kb.split(".")[1]
    ]
    assert len(same_house) == 36
