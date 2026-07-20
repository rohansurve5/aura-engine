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
    return json.loads(SEED_PATH.read_text())


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
    data = _load()
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
    """66 + 35 + 90 + 30 = 221. A count assertion catches a half-authored seed
    that every per-cell check above would pass one cell at a time."""
    lines = _all_lines(_load())
    expected = (
        len(SHAPES) * OPENING_VARIANTS
        + len(TURN_KINDS) * TURN_VARIANTS
        + len(AREAS) * len(ROLES) * STANDING_VARIANTS
        + len(SHAPES) * CLOSE_VARIANTS
    )
    assert len(lines) == expected == 221


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

    221 * 0.06 = 13.26. int() gives 13 (fails at 14); round() would give 13 as
    well, but at 217 lines they diverge (13.02 → 13 vs 13), and at 200 lines
    (12.0) they agree while at 208 (12.48) they do not. Stating the choice is
    what stops a later re-count from silently moving the gate.
    """
    assert _share_limit(221) == 13
    assert _share_limit(250) == 15


def test_no_content_word_dominates():
    offenders = check_word_share(_load())
    assert offenders == {}, f"over {_share_limit(221)} lines: {offenders}"


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
    poisoned = json.loads(SEED_PATH.read_text())
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
