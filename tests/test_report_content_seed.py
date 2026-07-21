"""Corpus gate for the period-report library (`report_content_v1`).

THE DENOMINATOR PROBLEM, THIRD INSTANCE. content_v3 taught that a corpus can be
perfectly diverse and still render six identical-feeling cards, because
diversity measured over the library says nothing about the slice one reader
sees at once (docs/CONTENT_KEYS.md § three gates, three denominators). So the
first question for any new corpus is: what is the reading unit?

For reports it is NOT the screen. A weekly report renders four movements at
once, and those four are drawn from four disjoint corpora that could not
collide even in principle. The unit that actually matters is
**consecutive reports one reader receives over time** — a person who reads four
monthlies in a row must not see one skeleton four times. That gate lives in
tests/test_report_composition.py, where the composition function is available;
this module is the library-level half: share, skeleton, banned vocabulary and
structure.

WHY THE SHARE CAP IS HARDER HERE than in score_rules. Report copy is *about*
the range, so the range's own nouns recur by necessity — see FRAME_WORDS. The
exemption is deliberately narrow, and `test_frame_exemption_is_narrow` pins
that narrowness by requiring an ordinary content word at the same frequency to
FAIL. The dasha library's `stretch` incident (a filler synonym for "period" in
26 of 237 lines, caught by the cap) is the exact failure this guards.
"""

from __future__ import annotations

import json
import re
from collections import Counter

import pytest

from engine.content import REPORT_SEED_PATH
from engine.reports import (
    CLOSE_VARIANTS,
    MONTH_CLOSE_VARIANTS,
    MONTH_OPENING_VARIANTS,
    MONTH_SHAPES,
    MONTH_STANDING_VARIANTS,
    MONTH_TURN_KINDS,
    MONTH_TURN_VARIANTS,
    OPENING_VARIANTS,
    ROLES,
    SHAPES,
    STANDING_VARIANTS,
    TURN_KINDS,
    TURN_VARIANTS,
)

SEED_PATH = REPORT_SEED_PATH

#: Same value and same `int()` truncation as the score_rules gate. The identity
#: gate uses round(); the two differ deliberately and each pins its own choice,
#: because which one you get changes the threshold by a whole line.
MAX_LINE_SHARE = 0.06

WORD_RE = re.compile(r"[a-z']+")

AREAS = ("love", "money", "career", "mind", "health", "mood")

#: Function words. Kept verbatim by `_skeleton`, excluded from the share count.
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "so", "than", "then", "that",
    "this", "these", "those", "it", "its", "is", "are", "was", "be", "been",
    "being", "am", "as", "at", "by", "for", "from", "in", "into", "of", "off",
    "on", "onto", "out", "over", "to", "up", "with", "without", "not", "no",
    "nor", "you", "your", "yours", "yourself", "i", "me", "my", "we", "us",
    "our", "they", "them", "their", "he", "she", "his", "her", "him", "what",
    "which", "who", "whom", "when", "where", "why", "how", "all", "any",
    "both", "each", "few", "more", "most", "other", "some", "such", "only",
    "own", "same", "too", "very", "can", "will", "just", "should", "would",
    "could", "may", "might", "must", "do", "does", "did", "done", "have",
    "has", "had", "there", "here", "one", "two", "about", "after", "before",
    "again", "against", "between", "during", "through", "under", "until",
    "while", "because", "rather", "already", "still", "yet", "also", "even",
    "much", "many", "less", "least", "every", "anything", "nothing",
    "something", "everything", "whatever", "whoever", "wherever", "however",
    "it's", "don't", "doesn't", "won't", "you've", "you'll", "you'd",
    "does't", "isn't", "cannot", "let", "get", "gets", "keep", "keeps",
    "make", "makes", "made", "give", "gives", "given", "put", "puts",
}

#: The unit words a report is unavoidably ABOUT. Exempt from the share cap for
#: the same reason `period`/`years`/`era` are in the dasha gate and
#: `day`/`moon`/`star` in the score-card gate: their frequency measures what the
#: library IS, not how repetitive the writing is. NOTHING ELSE is exempt — in
#: particular `stretch`, `span`, `part` and `thread` are NOT here, because a
#: filler synonym for the unit is precisely what the dasha cap caught.
FRAME_WORDS = {"week", "weeks", "weekly", "day", "days", "seven", "monday", "sunday"}

BANNED_WORDS = {
    "tender", "tenderly", "doom", "doomed", "curse", "cursed", "beware",
    "danger", "dangerous", "death", "divorce", "disease", "illness", "fate",
    "fated", "destiny", "destined", "inauspicious", "malefic", "ruin",
    "ruined", "disaster", "tragedy",
}

#: Report copy predicts a SHAPE, never an OUTCOME. These are the phrasings that
#: turn a described trend into a promise, which is the single fastest way for a
#: guidance product to become unfalsifiable — and the money voice spec bans
#: outcome guarantees outright (docs/voice/money.md § banned).
FORTUNE_PATTERNS = (
    r"\bwill (?:bring|arrive|come to you|be yours|happen for you)\b",
    r"\bguarantee\w*\b",
    r"\bdestined to\b",
    r"\bwindfall\b",
    r"\bjackpot\b",
    r"\bfortune (?:awaits|is)\b",
    r"\bwealth is coming\b",
    r"\byou will (?:succeed|fail|win|lose)\b",
)


def _load() -> dict:
    """The WEEKLY corpus. The v2 seed nests corpora by report_kind (migration
    010) so weekly and monthly share one version and one activation marker;
    the gates below run per kind, over the movements that render together."""
    return json.loads(SEED_PATH.read_text())["weekly"]


def _words(line: str) -> list[str]:
    return WORD_RE.findall(line.lower())


def _content_words(line: str) -> set[str]:
    return {w for w in _words(line)} - STOPWORDS - FRAME_WORDS


def _skeleton(line: str) -> str:
    """Content words blanked, function words kept — the sentence's shape."""
    return " ".join(t if t in STOPWORDS else "_" for t in _words(line))


def _frame(line: str) -> str:
    return " ".join(_words(line)[:4])


def _all_lines(data: dict) -> list[str]:
    out: list[str] = []
    for shape in data["shape"].values():
        out.extend(shape["openings"])
    for turn in data["turn"].values():
        out.extend(turn["lines"])
    for cell in data["standing"].values():
        out.extend(cell["lines"])
    for close in data["close"].values():
        out.extend(close["lines"])
    return out


def _share_limit(n: int) -> int:
    return int(n * MAX_LINE_SHARE)


# ── structure ────────────────────────────────────────────────────────────────

def test_version_matches_filename():
    data = json.loads(SEED_PATH.read_text())
    assert data["version"] == SEED_PATH.stem


def test_every_shape_has_exactly_the_declared_openings():
    data = _load()
    assert set(data["shape"]) == set(SHAPES)
    for shape, cell in data["shape"].items():
        assert len(cell["openings"]) == OPENING_VARIANTS, shape
        assert len(set(cell["openings"])) == OPENING_VARIANTS, f"{shape} repeats an opening"


def test_every_turn_kind_has_exactly_the_declared_lines():
    data = _load()
    assert set(data["turn"]) == set(TURN_KINDS)
    for kind, cell in data["turn"].items():
        assert len(cell["lines"]) == TURN_VARIANTS, kind
        assert len(set(cell["lines"])) == TURN_VARIANTS, f"{kind} repeats a line"


def test_every_area_role_pair_is_authored():
    data = _load()
    expected = {f"{a}.{r}" for a in AREAS for r in ROLES}
    assert set(data["standing"]) == expected
    for key, cell in data["standing"].items():
        assert len(cell["lines"]) == STANDING_VARIANTS, key
        assert len(set(cell["lines"])) == STANDING_VARIANTS, f"{key} repeats a line"


def test_every_shape_has_a_close():
    data = _load()
    assert set(data["close"]) == set(SHAPES)
    for shape, cell in data["close"].items():
        assert len(cell["lines"]) == CLOSE_VARIANTS, shape
        assert len(set(cell["lines"])) == CLOSE_VARIANTS, f"{shape} repeats a close"


def test_corpus_is_the_declared_size():
    """102 + 35 + 90 + 30 = 257. A count assertion catches a half-authored seed
    that every per-cell check above would pass one cell at a time."""
    lines = _all_lines(_load())
    expected = (
        len(SHAPES) * OPENING_VARIANTS
        + len(TURN_KINDS) * TURN_VARIANTS
        + len(AREAS) * len(ROLES) * STANDING_VARIANTS
        + len(SHAPES) * CLOSE_VARIANTS
    )
    assert len(lines) == expected == 257


def test_every_line_is_exactly_unique_across_the_whole_corpus():
    lines = _all_lines(_load())
    dupes = [line for line, n in Counter(lines).items() if n > 1]
    assert dupes == [], f"repeated verbatim: {dupes}"


# ── share ────────────────────────────────────────────────────────────────────

def check_word_share(data: dict) -> dict[str, int]:
    """Document frequency over LINES, each word counted once per line.

    A word twice inside one line is style; a word across many lines is a
    template. Returns offenders → line count, so a failure names the word.
    """
    lines = _all_lines(data)
    seen_in: Counter[str] = Counter()
    for line in lines:
        for word in _content_words(line):
            seen_in[word] += 1
    limit = _share_limit(len(lines))
    return {w: n for w, n in seen_in.items() if n > limit and len(w) > 2}


def test_share_threshold_matches_the_spec():
    """int(), not round() — pinned because the two disagree here.

    257 * 0.06 = 15.42. int() gives 15 (fails at 16); round() agrees at 257 but
    the two diverge on nearby counts (e.g. 259 * 0.06 = 15.54 → int 15, round
    16). Stating the choice is what stops a later re-count from silently moving
    the gate.
    """
    assert _share_limit(257) == 15
    assert _share_limit(250) == 15


def test_no_content_word_dominates():
    offenders = check_word_share(_load())
    assert offenders == {}, f"over {_share_limit(257)} lines: {offenders}"


def test_frame_exemption_is_narrow():
    """`week` may saturate; an ordinary content word at the same rate may not.

    Without this, FRAME_WORDS is an escape hatch that grows every time the cap
    is inconvenient. Here it is load-bearing in both directions.
    """
    data = _load()
    assert check_word_share(data) == {}

    n = len(_all_lines(data))
    # `week` is genuinely frequent in the real corpus and passes...
    weeky = sum(1 for line in _all_lines(data) if "week" in _words(line))
    assert weeky > 0
    # ...while an ordinary word injected at over the limit must fail.
    over = _share_limit(n) + 1
    poisoned = json.loads(SEED_PATH.read_text())["weekly"]
    for i in range(over):
        shape = SHAPES[i % len(SHAPES)]
        idx = i // len(SHAPES)
        poisoned["shape"][shape]["openings"][idx] += " Momentum."
    assert "momentum" in check_word_share(poisoned)


# ── distinctness ─────────────────────────────────────────────────────────────

def test_no_two_shapes_share_an_opening_frame():
    """Openings are the movement a reader meets first, and the six shapes are
    the report's whole claim about what a week IS. Two shapes opening the same
    way is the v3 failure — one template with the label swapped."""
    data = _load()
    seen: dict[str, str] = {}
    for shape, cell in data["shape"].items():
        for line in cell["openings"]:
            frame = _frame(line)
            assert frame not in seen, f"{shape} and {seen[frame]} share opening {frame!r}"
            seen[frame] = shape


def test_no_two_shapes_share_an_opening_skeleton():
    data = _load()
    seen: dict[str, str] = {}
    for shape, cell in data["shape"].items():
        for line in cell["openings"]:
            skel = _skeleton(line)
            if len(_words(line)) < 6:
                continue
            assert skel not in seen, f"{shape} and {seen[skel]} share skeleton {skel!r}"
            seen[skel] = shape


@pytest.mark.parametrize("role", ROLES)
def test_no_two_areas_share_a_standing_skeleton_in_the_same_role(role):
    """Within one role the six areas are directly comparable — a reader whose
    Money leads this week and Career leads next week is reading the same slot
    twice. Across roles a shared skeleton is far less visible, so the gate is
    scoped to the slot rather than blanket-applied."""
    data = _load()
    seen: dict[str, str] = {}
    for area in AREAS:
        for line in data["standing"][f"{area}.{role}"]["lines"]:
            if len(_words(line)) < 6:
                continue
            skel = _skeleton(line)
            assert skel not in seen, f"{area} and {seen[skel]} share {role} skeleton {skel!r}"
            seen[skel] = area


def test_no_two_areas_share_a_standing_frame_in_the_same_role():
    data = _load()
    for role in ROLES:
        seen: dict[str, str] = {}
        for area in AREAS:
            for line in data["standing"][f"{area}.{role}"]["lines"]:
                frame = _frame(line)
                assert frame not in seen, (
                    f"{area} and {seen[frame]} share {role} frame {frame!r}"
                )
                seen[frame] = area


# ── safety ───────────────────────────────────────────────────────────────────

def test_no_banned_vocabulary():
    offenders = [
        (line, sorted(set(_words(line)) & BANNED_WORDS))
        for line in _all_lines(_load())
        if set(_words(line)) & BANNED_WORDS
    ]
    assert offenders == [], offenders


@pytest.mark.parametrize("pattern", FORTUNE_PATTERNS)
def test_no_outcome_promises(pattern):
    """A report describes a shape; it never promises a result.

    This is the gate that keeps reports falsifiable-in-principle. "The week
    rises" can be checked against the numbers; "money will come to you" cannot
    be checked against anything, and docs/voice/money.md bans it outright.
    """
    rx = re.compile(pattern, re.IGNORECASE)
    offenders = [line for line in _all_lines(_load()) if rx.search(line)]
    assert offenders == [], f"{pattern}: {offenders}"


def test_every_line_is_second_person_or_impersonal_never_third():
    """No line may address a third party — reports speak to the reader."""
    rx = re.compile(r"\b(he|she|his|hers)\b", re.IGNORECASE)
    offenders = [line for line in _all_lines(_load()) if rx.search(line)]
    assert offenders == [], offenders


def test_lines_are_within_length_bounds():
    """8-40 words. The floor stops a cell degenerating into a label; the ceiling
    stops one movement swallowing the report."""
    for line in _all_lines(_load()):
        n = len(_words(line))
        assert 8 <= n <= 40, f"{n} words: {line!r}"


# ═════════════════════════════════════════════════════════════════════════════
# THE MONTHLY CORPUS (report_kind = 'monthly', v3)
#
# Same gate battery as the weekly corpus above, with two deliberate differences:
#
#   * SEPARATE SHARE DENOMINATOR. The monthly corpus is 208 lines to weekly's
#     257. IDENTITY.md §6a records why the denominators must not be pooled: a
#     shared one lets the larger corpus's headroom mask repetition in the
#     smaller. Each kind is capped over its own line count.
#   * DIFFERENT FRAME WORDS. Monthly copy is unavoidably about months, weeks
#     and halves — its units. `day` is NOT a monthly frame word; monthly copy
#     that needs day vocabulary is trespassing on the weekly report's unit,
#     which tests/test_report_cross_kind.py bans outright.
#
# The cross-kind gates (weekly x monthly collisions, the §5 division of labour)
# live in tests/test_report_cross_kind.py, because their reading unit — one
# subscriber holding both reports in one sitting — spans the two corpora that
# this module checks one at a time.
# ═════════════════════════════════════════════════════════════════════════════

#: Unit words the MONTHLY corpus is unavoidably about. `week`/`weeks` are frame
#: words here too: the monthly report's claims are AT WEEK GRANULARITY (which
#: week carries the month), so the week-nouns measure what the corpus is, not
#: how repetitive the writing is. Day-nouns are deliberately absent — they are
#: not monthly frame words, they are monthly contraband (see the cross-kind
#: division-of-labour gate). `month's` is the possessive of the unit noun —
#: the same morphological-variant class as the weekly set's `weeks`/`weekly`,
#: NOT a new exemption: WORD_RE keeps the apostrophe, so the possessive is its
#: own token and would otherwise be capped as if it were an ordinary word.
MONTH_FRAME_WORDS = {
    "month", "months", "monthly", "month's", "week", "weeks", "half", "halves",
}


def _load_monthly() -> dict:
    """The MONTHLY corpus — a separate loader so the falsification suite can
    mutate one kind without touching the other's gates."""
    return json.loads(SEED_PATH.read_text())["monthly"]


def _content_words_monthly(line: str) -> set[str]:
    return {w for w in _words(line)} - STOPWORDS - MONTH_FRAME_WORDS


def check_word_share_monthly(data: dict) -> dict[str, int]:
    """Document frequency over the monthly corpus's own lines — its own
    denominator, per the §6a lesson."""
    lines = _all_lines(data)
    seen_in: Counter[str] = Counter()
    for line in lines:
        for word in _content_words_monthly(line):
            seen_in[word] += 1
    limit = _share_limit(len(lines))
    return {w: n for w, n in seen_in.items() if n > limit and len(w) > 2}


# ── structure ────────────────────────────────────────────────────────────────

def test_monthly_every_shape_has_exactly_the_declared_openings():
    data = _load_monthly()
    assert set(data["shape"]) == set(MONTH_SHAPES)
    for shape, cell in data["shape"].items():
        assert len(cell["openings"]) == MONTH_OPENING_VARIANTS, shape
        assert len(set(cell["openings"])) == MONTH_OPENING_VARIANTS, f"{shape} repeats an opening"


def test_monthly_every_turn_kind_has_exactly_the_declared_lines():
    data = _load_monthly()
    assert set(data["turn"]) == set(MONTH_TURN_KINDS)
    for kind, cell in data["turn"].items():
        assert len(cell["lines"]) == MONTH_TURN_VARIANTS, kind
        assert len(set(cell["lines"])) == MONTH_TURN_VARIANTS, f"{kind} repeats a line"


def test_monthly_every_area_role_pair_is_authored():
    data = _load_monthly()
    expected = {f"{a}.{r}" for a in AREAS for r in ROLES}
    assert set(data["standing"]) == expected
    for key, cell in data["standing"].items():
        assert len(cell["lines"]) == MONTH_STANDING_VARIANTS, key
        assert len(set(cell["lines"])) == MONTH_STANDING_VARIANTS, f"{key} repeats a line"


def test_monthly_every_shape_has_a_close():
    data = _load_monthly()
    assert set(data["close"]) == set(MONTH_SHAPES)
    for shape, cell in data["close"].items():
        assert len(cell["lines"]) == MONTH_CLOSE_VARIANTS, shape
        assert len(set(cell["lines"])) == MONTH_CLOSE_VARIANTS, f"{shape} repeats a close"


def test_monthly_corpus_is_the_declared_size():
    """65 + 28 + 90 + 25 = 208."""
    lines = _all_lines(_load_monthly())
    expected = (
        len(MONTH_SHAPES) * MONTH_OPENING_VARIANTS
        + len(MONTH_TURN_KINDS) * MONTH_TURN_VARIANTS
        + len(AREAS) * len(ROLES) * MONTH_STANDING_VARIANTS
        + len(MONTH_SHAPES) * MONTH_CLOSE_VARIANTS
    )
    assert len(lines) == expected == 208


def test_no_line_repeats_across_the_entire_seed_file_both_kinds():
    """Verbatim uniqueness over ALL 465 lines, weekly and monthly together.

    The per-kind uniqueness gates cannot see a monthly line pasted from the
    weekly corpus, which is the laziest possible cross-kind collision.
    """
    lines = _all_lines(_load()) + _all_lines(_load_monthly())
    assert len(lines) == 465
    dupes = [line for line, n in Counter(lines).items() if n > 1]
    assert dupes == [], f"repeated verbatim across kinds: {dupes}"


# ── share ────────────────────────────────────────────────────────────────────

def test_monthly_share_threshold_matches_the_spec():
    """int() truncation over the MONTHLY denominator: 208 * 0.06 = 12.48 → a
    word may sit in 12 lines and fails at 13. Pinned so a later re-count cannot
    silently move the gate."""
    assert _share_limit(208) == 12


def test_monthly_no_content_word_dominates():
    offenders = check_word_share_monthly(_load_monthly())
    assert offenders == {}, f"over {_share_limit(208)} lines: {offenders}"


def test_monthly_frame_exemption_is_narrow():
    """`month`/`week` may saturate; an ordinary word at the same rate may not."""
    data = _load_monthly()
    assert check_word_share_monthly(data) == {}

    monthy = sum(1 for line in _all_lines(data) if "month" in _words(line))
    assert monthy > _share_limit(208), "fixture: 'month' should saturate the corpus"

    over = _share_limit(len(_all_lines(data))) + 1
    poisoned = json.loads(SEED_PATH.read_text())["monthly"]
    shapes = list(poisoned["shape"])
    for i in range(over):
        shape = shapes[i % len(shapes)]
        idx = i // len(shapes)
        poisoned["shape"][shape]["openings"][idx] += " Momentum."
    assert "momentum" in check_word_share_monthly(poisoned)


# ── distinctness ─────────────────────────────────────────────────────────────

def test_monthly_no_two_shapes_share_an_opening_frame():
    data = _load_monthly()
    seen: dict[str, str] = {}
    for shape, cell in data["shape"].items():
        for line in cell["openings"]:
            frame = _frame(line)
            assert frame not in seen, f"{shape} and {seen[frame]} share opening {frame!r}"
            seen[frame] = shape


def test_monthly_no_two_shapes_share_an_opening_skeleton():
    data = _load_monthly()
    seen: dict[str, str] = {}
    for shape, cell in data["shape"].items():
        for line in cell["openings"]:
            skel = _skeleton(line)
            if len(_words(line)) < 6:
                continue
            assert skel not in seen, f"{shape} and {seen[skel]} share skeleton {skel!r}"
            seen[skel] = shape


@pytest.mark.parametrize("role", ROLES)
def test_monthly_no_two_areas_share_a_standing_skeleton_in_the_same_role(role):
    data = _load_monthly()
    seen: dict[str, str] = {}
    for area in AREAS:
        for line in data["standing"][f"{area}.{role}"]["lines"]:
            if len(_words(line)) < 6:
                continue
            skel = _skeleton(line)
            assert skel not in seen, f"{area} and {seen[skel]} share {role} skeleton {skel!r}"
            seen[skel] = area


def test_monthly_no_two_areas_share_a_standing_frame_in_the_same_role():
    data = _load_monthly()
    for role in ROLES:
        seen: dict[str, str] = {}
        for area in AREAS:
            for line in data["standing"][f"{area}.{role}"]["lines"]:
                frame = _frame(line)
                assert frame not in seen, (
                    f"{area} and {seen[frame]} share {role} frame {frame!r}"
                )
                seen[frame] = area


# ── safety ───────────────────────────────────────────────────────────────────

def test_monthly_no_banned_vocabulary():
    offenders = [
        (line, sorted(set(_words(line)) & BANNED_WORDS))
        for line in _all_lines(_load_monthly())
        if set(_words(line)) & BANNED_WORDS
    ]
    assert offenders == [], offenders


@pytest.mark.parametrize("pattern", FORTUNE_PATTERNS)
def test_monthly_no_outcome_promises(pattern):
    rx = re.compile(pattern, re.IGNORECASE)
    offenders = [line for line in _all_lines(_load_monthly()) if rx.search(line)]
    assert offenders == [], f"{pattern}: {offenders}"


def test_monthly_every_line_is_second_person_or_impersonal_never_third():
    rx = re.compile(r"\b(he|she|his|hers)\b", re.IGNORECASE)
    offenders = [line for line in _all_lines(_load_monthly()) if rx.search(line)]
    assert offenders == [], offenders


def test_monthly_lines_are_within_length_bounds():
    for line in _all_lines(_load_monthly()):
        n = len(_words(line))
        assert 8 <= n <= 40, f"{n} words: {line!r}"
