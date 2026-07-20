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
    return json.loads(G.SEED_PATH.read_text())


def _expect_red(monkeypatch, data, gate, *args) -> str:
    monkeypatch.setattr(G, "_load", lambda: data)
    with pytest.raises(AssertionError) as exc:
        gate(*args)
    return str(exc.value)


def _expect_green(monkeypatch, gate, *args) -> None:
    monkeypatch.setattr(G, "_load", lambda: json.loads(G.SEED_PATH.read_text()))
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
    n = 221
    limit = G._share_limit(n)
    assert limit == 13

    at = _synthetic(n, "template", limit)
    assert G.check_word_share(at) == {}, "the limit itself must pass"

    over = _synthetic(n, "template", limit + 1)
    assert G.check_word_share(over) == {"template": limit + 1}


def test_frame_exemption_is_load_bearing_in_both_directions(monkeypatch):
    """`week` may saturate the corpus; `momentum` at the same rate may not.

    Without both halves, FRAME_WORDS is an escape hatch that grows every time
    the cap is inconvenient.
    """
    n = 221
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
    assert gcd(11, 52) == 1 and gcd(7, 52) == 1 and gcd(5, 52) == 1
    assert gcd(12, 52) == 4, "12 is the trap: a monthly table would lock"
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
