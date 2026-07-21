"""The content_v3 lexical diversity gate — so "tender" can never recur.

Runs in CI against the checked-in seed (db/seed/score_rules_content_v3.json)
and fails the build when the corpus regrows the failure modes testers caught
in content_v2's fallback era:

1. **Signature-word tic** — no content word may appear in more than
   MAX_WORD_SHARE of all corpus lines. Threshold: 6%. Justification: the
   corpus is ~450 lines; 6% ≈ 27 lines, roomy enough for natural reuse of
   everyday words across six differently-voiced areas, but an order of
   magnitude below the failure it guards against (a shared vocabulary word
   like "tender" labelling every low card put it in ~20% of what a user read
   in a day). Function words and the product's frame words (today/day/moon —
   the mechanism every CAUSE line legitimately names) are exempt; everything
   else counts.
2. **Shared band label** — no band label may be used by two areas
   (case-insensitive), and none may collide with the app's five day-level
   energy labels (Radiant/Bright/Steady/Quiet/Tender).
3. **Shared sentence skeleton** — no two AREAS may contain lines with the
   same skeleton (content words blanked, function words kept). This is
   exactly the "template with the area name swapped in" smell.
4. **Banned words** — fear/fatalism vocabulary and the retired "tender" must
   not appear anywhere in user-visible content.
"""

from __future__ import annotations

import json
import re
from collections import Counter

# The gate always runs against the ACTIVE seed — the corpus users will read —
# not a hand-typed filename that can silently lag a version bump.
from engine.content import SEED_PATH as SEED

RULES = json.loads(SEED.read_text())["rules"]

MAX_WORD_SHARE = 0.06

# Day-level energy labels (app + narrative bands) — area band labels must not
# reuse them, or the day headline and a card could read identically again.
DAY_LEVEL_LABELS = {"radiant", "bright", "steady", "quiet", "tender"}

# Words that must never appear in user-visible copy: the retired v2 tic plus
# fear-selling / fatalism vocabulary the voice rules prohibit.
BANNED_WORDS = {
    "tender", "tenderly", "doom", "doomed", "curse", "cursed", "beware",
    "danger", "dangerous", "death", "divorce", "disease", "illness",
    "fate", "fated", "destiny", "destined", "inauspicious",
}

# Function/frame words exempt from the frequency gate. Standard English
# function words plus the product's temporal frame (today/day) and "moon" —
# the astronomical mechanism every CAUSE line legitimately names.
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "so", "nor", "yet", "if", "then",
    "than", "as", "at", "by", "for", "from", "in", "into", "of", "off", "on",
    "onto", "out", "over", "to", "under", "up", "with", "without", "within",
    "is", "are", "was", "were", "be", "been", "being", "am", "do", "does",
    "did", "done", "have", "has", "had", "will", "would", "can", "could",
    "may", "might", "shall", "should", "must", "not", "no", "nothing",
    "it", "its", "itself", "this", "that", "these", "those", "there", "here",
    "he", "she", "they", "them", "their", "his", "her", "you", "your",
    "yours", "yourself", "we", "us", "our", "i", "me", "my", "one", "ones",
    "who", "whom", "whose", "which", "what", "when", "where", "how", "why",
    "all", "any", "both", "each", "few", "more", "most", "other", "some",
    "such", "own", "same", "too", "very", "just", "only", "also", "still",
    "once", "again", "ever", "never", "always", "now",
    "today", "day", "days", "tomorrow", "tonight", "week", "moon",
    # content_v3_1 mechanism nouns, exempt for the same reason "moon" is: they
    # NAME the sky fact a whole cause source is built on, so their frequency
    # measures how many sources we have, not how repetitive the writing is.
    # "star" carries the nakshatra + tara sources; "light" carries the paksha +
    # phase sources. The risk they'd otherwise mask — every card explaining
    # itself the same way — is now caught directly, per rendered day, by
    # tests/test_per_day_distinctness.py.
    "star", "stars", "light",
    "let", "get", "gets", "keep", "make", "makes", "made", "give", "gives",
    "it's", "don't", "doesn't", "won't", "you've", "you'll", "you'd",
}

WORD_RE = re.compile(r"[a-z']+")
SLOT_RE = re.compile(r"\{[a-z_]+\}")  # format placeholders are not words


def _walk_strings(node, out: list[str]) -> None:
    """Every user-visible string in the rules dict (values only, never keys)."""
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for value in node.values():
            _walk_strings(value, out)
    elif isinstance(node, list):
        for value in node:
            _walk_strings(value, out)


def _corpus_lines() -> list[str]:
    """All user-visible content lines across the whole seed (numeric rule
    sections carry no strings, so walking everything is safe)."""
    content_keys = (
        "area_lines", "narrative", "tara", "band_labels",
        "why_recognition", "lucky_by_weekday",
        *CAUSE_SECTIONS,
    )
    lines: list[str] = []
    for key in content_keys:
        _walk_strings(RULES[key], lines)
    return lines


def _words(line: str) -> list[str]:
    return WORD_RE.findall(SLOT_RE.sub(" ", line.lower()))


def _skeleton(line: str) -> str:
    """The line with content words blanked and function words kept — two lines
    sharing a skeleton are the same sentence with words swapped in."""
    tokens = _words(line)
    return " ".join(t if t in STOPWORDS else "_" for t in tokens)


AREAS = RULES["areas"]["order"]
BANDS = RULES["score_bands"]["order"]

# content_v3_1: the CAUSE half now has one corpus per explanation source. All of
# them are user-visible copy and all are subject to every gate below.
CAUSE_SECTIONS = (
    "why_cause", "why_cause_nakshatra", "why_cause_paksha",
    "why_cause_tara", "why_cause_phase",
    # content_v4 (A5): the read-time house-cause corpus — 72 lines, one per
    # (area, transit house of the area's primary significator). User-visible
    # copy like every other cause source, so every gate below applies to it.
    "why_cause_house",
)


def test_corpus_is_substantial():
    lines = _corpus_lines()
    assert len(lines) > 350, f"corpus unexpectedly small: {len(lines)} lines"


def test_no_content_word_dominates_the_corpus():
    lines = _corpus_lines()
    seen_in = Counter()
    for line in lines:
        for word in set(_words(line)) - STOPWORDS:
            seen_in[word] += 1
    limit = int(len(lines) * MAX_WORD_SHARE)
    offenders = {
        w: n for w, n in seen_in.items() if n > limit and len(w) > 2
    }
    assert not offenders, (
        f"content words above the {MAX_WORD_SHARE:.0%} share "
        f"({limit} of {len(lines)} lines): {offenders}"
    )


def test_no_band_label_is_shared_between_areas():
    seen: dict[str, str] = {}
    for area in AREAS:
        for label in RULES["band_labels"][area].values():
            key = label.strip().lower()
            assert key not in seen, (
                f"band label {label!r} used by both {seen[key]} and {area}"
            )
            assert key not in DAY_LEVEL_LABELS, (
                f"band label {label!r} ({area}) collides with a day-level energy label"
            )
            seen[key] = area


def test_every_area_band_cell_is_filled_and_labels_are_short():
    for area in AREAS:
        assert set(RULES["band_labels"][area]) == set(BANDS)
        for label in RULES["band_labels"][area].values():
            assert 0 < len(label) <= 16, f"label too long for the chip: {label!r}"


def _area_skeletons(area: str) -> dict[str, str]:
    """skeleton → sample line, for every line belonging to one area."""
    lines: list[str] = []
    _walk_strings(RULES["area_lines"][area], lines)
    _walk_strings(RULES["why_recognition"][area], lines)
    for section in CAUSE_SECTIONS:
        _walk_strings(RULES[section][area], lines)
    lines.extend(RULES["band_labels"][area].values())
    return {_skeleton(line): line for line in lines if len(_words(line)) >= 4}


def test_no_two_areas_share_a_line_or_skeleton():
    per_area = {area: _area_skeletons(area) for area in AREAS}
    for i, a in enumerate(AREAS):
        for b in AREAS[i + 1:]:
            shared = set(per_area[a]) & set(per_area[b])
            assert not shared, (
                f"{a} and {b} share sentence skeleton(s): "
                + "; ".join(
                    f"{per_area[a][s]!r} ~ {per_area[b][s]!r}" for s in sorted(shared)[:3]
                )
            )


def test_no_banned_word_anywhere():
    for line in _corpus_lines():
        used = set(_words(line)) & BANNED_WORDS
        assert not used, f"banned word(s) {used} in {line!r}"


def test_recognition_and_cause_cells_are_unique_within_each_area():
    """Every cell in an area's own corpus is distinct — a duplicated cell
    would silently collapse two keys into one mood."""
    for area in AREAS:
        for section in ("why_recognition", *CAUSE_SECTIONS):
            lines: list[str] = []
            _walk_strings(RULES[section][area], lines)
            dupes = [line for line, n in Counter(lines).items() if n > 1]
            assert not dupes, f"{area}.{section} repeats: {dupes[:2]}"
