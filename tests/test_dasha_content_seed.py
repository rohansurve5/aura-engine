"""Quality gates for db/seed/dasha_content_v2.json — the dasha content library.

Locks the structural contract (9 maha entries, all 81 ordered maha-antar pairs,
required fields, chip counts), the voice hard-rules (no fatalism, no
fear-selling, no death/illness/divorce prediction), and — new in v2 — the
distinctness gates.

## Why the distinctness gates here differ from content_v3's

`test_per_day_distinctness.py` protects the score cards at their reading unit:
the six areas a user sees **on one date**. Dasha has a different read pattern,
so the same gate shape would prove nothing:

* the **timeline screen** shows all nine mahadasha entries at once, so the
  nine eras are the unit — no two may open the same way or share a skeleton;
* the **detail screen** shows all nine antars of ONE mahadasha together, so
  each maha's nine sub-periods are a unit — asserted per maha, for the `line`
  and the `now` independently.

v1 failed exactly this: every essence opened with the planet as its
grammatical subject ("Ketu asks…", "Venus turns up…", "Mars hands you…"), which
is one template with the name swapped in. `test_essence_never_opens_with_the_lord`
encodes that specific regression.

## The one deliberate carve-out

Titles are gated on exact distinctness and a distinct opening frame, but NOT on
skeleton. They are five- and six-word era labels read as a parallel set down the
timeline ("The years that make you earn it" / "The years the doors open"), where
the shared stem is what makes them scannable as one family. Every such title
reduces to the skeleton `the _ _ _ _`, so a skeleton gate on titles would fail
correct design while catching nothing real. The substantive prose — essences and
all 162 antar strings — carries the full gate.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parents[1] / "db" / "seed"
SEED_PATH = SEED_DIR / "dasha_content_v2.json"
V1_PATH = SEED_DIR / "dasha_content_v1.json"

LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]

# Vocabulary the voice rules ban outright: fatalism, fear-selling, and
# death/illness/divorce prediction. Matched as whole words, case-insensitive.
BANNED_WORDS = [
    "death", "die", "dying", "disease", "illness", "cancer", "divorce",
    "widow", "curse", "cursed", "doom", "doomed", "destroyed", "destruction",
    "ruin", "ruined", "disaster", "tragedy", "inauspicious", "malefic",
    "fate", "fated", "destiny", "destined",
]
BANNED_RE = re.compile(r"\b(" + "|".join(BANNED_WORDS) + r")\b", re.IGNORECASE)

MAX_WORD_SHARE = 0.06

WORD_RE = re.compile(r"[a-z'-]+")

# Frame words naming the unit every entry in this corpus is *about* — the
# dasha equivalent of the day/moon/star exemptions in the score-card gate.
# Their frequency measures what the library is, not how repetitive the writing
# is. Nothing else is exempt: "stretch" was a filler synonym for "period" that
# reached 26 of 237 lines in the first v2 draft, and this gate is what caught it.
FRAME_WORDS = {"period", "periods", "year", "years", "era", "eras"}

STOPWORDS = set(
    """a an the and or but so if then than as at by for from in into of off on onto out
    over to under up with without within is are was were be been being am do does did
    done have has had will would can could may might shall should must not no it its
    this that these those there here they them their you your yours yourself we us our
    i me my one who what when where how why all any both each few more most other some
    such own same too very just only also still once again ever never always now today
    day days week cannot about back through while every""".split()
) | FRAME_WORDS


def _load() -> dict:
    return json.loads(SEED_PATH.read_text())


def _words(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def _frame(text: str) -> str:
    """The opening frame — the first four words. Two lines sharing one read as
    the same sentence starting up again."""
    return " ".join(_words(text)[:4])


def _skeleton(text: str) -> str:
    """Content words blanked, function words kept: the "same sentence with the
    names swapped in" signature."""
    return " ".join(t if t in STOPWORDS else "_" for t in _words(text))


def _all_text(data: dict) -> list[tuple[str, str]]:
    """Every user-visible string in the library as (where, text) pairs."""
    out: list[tuple[str, str]] = []
    for lord, entry in data["maha"].items():
        out.append((f"maha/{lord}/title", entry["title"]))
        out.append((f"maha/{lord}/essence", entry["essence"]))
        for chip in entry["favours"]:
            out.append((f"maha/{lord}/favours", chip))
        for chip in entry["watch"]:
            out.append((f"maha/{lord}/watch", chip))
    for key, entry in data["maha_antar"].items():
        out.append((f"maha_antar/{key}/line", entry["line"]))
        out.append((f"maha_antar/{key}/now", entry["now"]))
    return out


# ── Structure ────────────────────────────────────────────────────────────────


def test_version() -> None:
    assert _load()["version"] == "dasha_content_v2"


def test_v1_is_retained_for_rollback() -> None:
    """Versions are additive: v1 stays on disk (and in the table) so a bad
    rewrite can be rolled back by re-seeding, not by reverting a commit."""
    assert V1_PATH.exists()
    assert json.loads(V1_PATH.read_text())["version"] == "dasha_content_v1"


def test_maha_entries_complete() -> None:
    maha = _load()["maha"]
    assert sorted(maha) == sorted(LORDS)
    for lord, entry in maha.items():
        assert set(entry) == {"title", "essence", "favours", "watch"}, lord
        # Title is a plain-language era name, never the bare planet name.
        assert entry["title"].strip() and entry["title"] != lord
        # Essence is 2-3 sentences of real substance.
        sentences = [s for s in re.split(r"[.!?]", entry["essence"]) if s.strip()]
        assert 2 <= len(sentences) <= 3, lord
        assert 3 <= len(entry["favours"]) <= 4, lord
        assert 2 <= len(entry["watch"]) <= 3, lord
        for chip in entry["favours"] + entry["watch"]:
            assert chip.strip()


def test_maha_antar_pairs_complete() -> None:
    pairs = _load()["maha_antar"]
    expected = {f"{m}-{a}" for m in LORDS for a in LORDS}
    assert set(pairs) == expected  # all 81 ordered pairs, incl. same-planet
    assert len(pairs) == 81
    for key, entry in pairs.items():
        assert set(entry) == {"line", "now"}, key
        assert entry["line"].strip(), key
        assert entry["now"].strip(), key


# ── Voice ────────────────────────────────────────────────────────────────────


def test_no_banned_vocabulary() -> None:
    for where, text in _all_text(_load()):
        match = BANNED_RE.search(text)
        assert match is None, f"banned word {match.group(0)!r} in {where}: {text!r}"


def test_essence_never_opens_with_the_lord() -> None:
    """The v1 regression, encoded. Every v1 essence made the planet the opening
    subject, which is what made nine different eras read as one template."""
    maha = _load()["maha"]
    for lord, entry in maha.items():
        first = _words(entry["essence"])[0]
        assert first != lord.lower(), (
            f"{lord} essence opens with the planet name — that is the v1 template: "
            f"{entry['essence'][:60]!r}"
        )


# ── Distinctness: the timeline screen (all nine eras at once) ────────────────


def test_maha_titles_are_distinct() -> None:
    titles = {lord: _load()["maha"][lord]["title"] for lord in LORDS}
    assert len(set(titles.values())) == len(LORDS), "duplicate era title"
    frames = Counter(_frame(t) for t in titles.values())
    dupes = [f for f, n in frames.items() if n > 1]
    assert not dupes, f"era titles share an opening frame: {dupes}"


def test_no_two_maha_essences_share_a_frame_or_skeleton() -> None:
    maha = _load()["maha"]
    by_frame: dict[str, str] = {}
    by_skeleton: dict[str, str] = {}
    for lord in LORDS:
        essence = maha[lord]["essence"]
        frame, skeleton = _frame(essence), _skeleton(essence)
        assert frame not in by_frame, (
            f"{lord} and {by_frame[frame]} essences open identically: {frame!r}"
        )
        assert skeleton not in by_skeleton, (
            f"{lord} and {by_skeleton[skeleton]} essences share a sentence skeleton"
        )
        by_frame[frame] = lord
        by_skeleton[skeleton] = lord


# ── Distinctness: the detail screen (one maha's nine antars at once) ─────────


def test_within_each_maha_the_nine_antars_are_distinct() -> None:
    """The unit a user actually reads together. Asserted per maha and per field,
    because `line` and `now` are read as two separate columns of nine."""
    pairs = _load()["maha_antar"]
    for maha in LORDS:
        for field in ("line", "now"):
            by_frame: dict[str, str] = {}
            by_skeleton: dict[str, str] = {}
            for antar in LORDS:
                text = pairs[f"{maha}-{antar}"][field]
                frame, skeleton = _frame(text), _skeleton(text)
                assert frame not in by_frame, (
                    f"in the {maha} period, the {antar} and {by_frame[frame]} "
                    f"antars open identically ({field}): {frame!r}"
                )
                assert skeleton not in by_skeleton, (
                    f"in the {maha} period, the {antar} and {by_skeleton[skeleton]} "
                    f"antars share a sentence skeleton ({field})"
                )
                by_frame[frame] = antar
                by_skeleton[skeleton] = antar


def test_every_antar_string_is_unique_corpus_wide() -> None:
    pairs = _load()["maha_antar"]
    for field in ("line", "now"):
        texts = [entry[field] for entry in pairs.values()]
        dupes = [t for t, n in Counter(texts).items() if n > 1]
        assert not dupes, f"duplicated antar {field}: {dupes[:2]}"


# ── Corpus-level lexical diversity (as in content_v3) ────────────────────────


def test_no_content_word_dominates_the_corpus() -> None:
    lines = [text for _, text in _all_text(_load())]
    seen_in: Counter[str] = Counter()
    for line in lines:
        for word in set(_words(line)) - STOPWORDS:
            seen_in[word] += 1
    limit = int(len(lines) * MAX_WORD_SHARE)
    offenders = {w: n for w, n in seen_in.items() if n > limit and len(w) > 2}
    assert not offenders, (
        f"content words above the {MAX_WORD_SHARE:.0%} share "
        f"({limit} of {len(lines)} lines): {offenders}"
    )
