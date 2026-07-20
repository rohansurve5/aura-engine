"""Quality gates for the ACTIVE identity corpus — the "About your star" library.

Implements every gate IDENTITY.md §6 specifies. Runs in CI and gates the nightly
pre-seed, like the three existing content gates.

## The seed path is derived, never typed here

`SEED_PATH` comes from `engine.content.IDENTITY_SEED_PATH` — the one line that
declares which corpus is live. It was originally a literal `identity_content_v1.json`
in this file, which made this module a SECOND declaration of the active seed, and
that is the precise bug the repo has now closed three times: `content_v3_2` was
gated green while precompute read a different version, and
`test_migrate_seeds_the_exact_identity_file_content_py_activates` exists to stop
`db/migrate.py` doing the same thing. The test suite had the identical defect and
nothing was watching it. When v2 was activated, every gate in this file silently
went on grading v1 — including the two that had been waiting for a full corpus to
wake up. A gate pointed at the wrong file is not a weaker gate, it is no gate.

## The word-share cap and its skip (§6a)

The cap is a *ratio against a corpus denominator*, and IDENTITY.md derives its two
thresholds specifically against n=27 and n=12. Below that the limit degenerates —
at n=3, round(3 × 0.185) = 1, which fails the moment any content word appears in
two of three profiles. That is not the spec's gate, it is noise wearing the spec's
name. So the gate skips below a meaningful corpus size and says so out loud.

**The skip is closed as of identity_content_v2**, which seeds the full 27 + 12: the
limit is 5 and 3, both >= 2, so both gates run. `test_share_gate_is_not_skipped_when_complete`
makes it impossible to reach a full corpus with the gate still asleep, and
`test_no_gate_skips_on_a_complete_corpus` asserts the stronger property that
nothing in this module skips once the corpus is complete. The gate is additionally
falsified on the real corpus and against a synthetic full-size one in
test_identity_gates_falsify.py, so it is a gate that has been *seen to fire*
rather than one merely written down.

## A note on `round` vs `int`

IDENTITY.md §6a's table states nakshatra/0.185 "fails at 6 entries" and
moon_sign/0.25 "fails at 4 entries". With `int()` — the function the old
dasha gate used, and which §6a's prose mentions — 27 × 0.185 = 4.995 floors to
4 and the gate would fail at 5, not 6. Only `round()` reproduces the spec's own
stated behaviour (round(4.995) = 5, fails at 6; round(12 × 0.25) = 3, fails at
4). We follow the table, because the table is what states the intent. This
discrepancy is recorded rather than silently resolved.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytest
from _pytest.outcomes import Skipped

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.content import IDENTITY_SEED_PATH  # noqa: E402

SEED_DIR = Path(__file__).resolve().parents[1] / "db" / "seed"
#: Derived from the ONE line that activates a corpus — never typed twice. See
#: the module docstring for why this is not a style preference.
SEED_PATH = IDENTITY_SEED_PATH

# Canonical order, identical to aura-api's src/natal.ts NAKSHATRAS/SIGNS. The
# Worker computes the reader's nakshatra and moon sign; if these lists drift
# apart the corpus is keyed on names nothing will ever look up.
NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
    "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]
SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

FULL_NAKSHATRA_N = 27
FULL_MOON_SIGN_N = 12

NAKSHATRA_FIELDS = {"title", "core", "cost", "misread", "contrast"}
MOON_SIGN_FIELDS = {"title", "need", "unsettles"}

#: Prose fields — what actually ships to a reader. `contrast` is excluded
#: everywhere prose is measured: it is authoring scaffolding, not rendered at v1.
NAKSHATRA_PROSE = ("title", "core", "cost", "misread")
MOON_SIGN_PROSE = ("title", "need", "unsettles")

MAX_ENTRY_SHARE = {"nakshatra": 0.185, "moon_sign": 0.25}
FULL_N = {"nakshatra": FULL_NAKSHATRA_N, "moon_sign": FULL_MOON_SIGN_N}

WORD_RE = re.compile(r"[a-z'-]+")

# Carried over wholesale from test_dasha_content_seed.py, per IDENTITY.md §7.
BANNED_WORDS = [
    "death", "die", "dying", "disease", "illness", "cancer", "divorce",
    "widow", "curse", "cursed", "doom", "doomed", "destroyed", "destruction",
    "ruin", "ruined", "disaster", "tragedy", "inauspicious", "malefic",
    "fate", "fated", "destiny", "destined",
]
BANNED_RE = re.compile(r"\b(" + "|".join(BANNED_WORDS) + r")\b", re.IGNORECASE)

# IDENTITY.md §7: no astrological jargon a non-expert would not recognise.
JARGON_WORDS = ["gana", "guna", "yoni", "nadi", "exalted", "debilitated"]
JARGON_RE = re.compile(r"\b(" + "|".join(JARGON_WORDS) + r")\b", re.IGNORECASE)

# §2 — the Barnum carriers. Whole-phrase, case-insensitive.
BARNUM_CARRIERS = [
    r"sometimes\b.{0,40}\bsometimes",
    r"part of you",
    r"deep down",
    r"more than people realise",
    r"more than people realize",
    r"a side of you that few see",
    r"you may find that",
    r"at times",
    r"there are moments when",
    r"you have a tendency to",
    r"like everyone",
    r"whether you admit it or not",
    r"secretly",
]
BARNUM_RE = re.compile("|".join(BARNUM_CARRIERS), re.IGNORECASE)

# §3 — the humblebrag shapes.
HUMBLEBRAG = [
    r"too (honest|loyal|generous|driven|kind|much|deeply|hard)",
    r"car(e|ing) too much",
    r"feel(ing)? (things )?too deeply",
    r"lov(e|ing) too hard",
    r"only flaw",
    r"higher standard than",
    r"don'?t always deserve",
]
HUMBLEBRAG_RE = re.compile("|".join(HUMBLEBRAG), re.IGNORECASE)

# §6c — hedge density: at most ONE per entry. Barnum copy is hedged copy.
HEDGES = [r"\bmay\b", r"\bmight\b", r"\bcan be\b", r"\btend(s)? to\b",
          r"\boften\b", r"\busually\b"]
HEDGE_RE = re.compile("|".join(HEDGES), re.IGNORECASE)

MAX_HEDGES_PER_ENTRY = 1

# §6d.3 — the vocabulary lanes. Nakshatra owns what you DO; moon sign owns
# what you NEED. These are the mechanical form of that split.
NAKSHATRA_BANNED_LANE = re.compile(
    r"\b(need|needs|needed|safe|safety|settled|unsettled|comfort|comforts|"
    r"comfortable|reassur\w*)\b", re.IGNORECASE
)
MOON_SIGN_BANNED_LANE = re.compile(
    r"\b(push\w*|finish\w*|deliver\w*|decide|decides|decided|decision\w*|"
    r"take on|takes on|hold out|holds out)\b", re.IGNORECASE
)

# §6a — the narrow frame-word exemption. These name the unit every entry is
# ABOUT, so their frequency measures what the library is, not how repetitive
# the writing is. NOTHING else is exempt — and specifically not `work`,
# `people`, `others`, `notice`, `hold`, which are where this corpus will drift.
FRAME_WORDS = {"star", "stars", "born", "nakshatra", "sign", "moon"}

STOPWORDS = set(
    """a an the and or but so if then than as at by for from in into of off on onto out
    over to under up with without within is are was were be been being am do does did
    done have has had will would can could may might shall should must not no it its
    this that these those there here they them their you your yours yourself we us our
    i me my one who what when where how why all any both each few more most other some
    such own same too very just only also still once again ever never always now today
    day days week cannot about back through while every""".split()
    # Temporal prepositions/conjunctions the inherited dasha list happens to
    # omit. `through`, `while` and `about` are already there; `before` and its
    # siblings are the same word class and carry no content. Added because the
    # strict cross-corpus gate (§6d.1) flagged `before` shared between Purva
    # Ashadha's title and Sagittarius's `unsettles` — a preposition collision,
    # not the "same thing said twice" padding the rule exists to catch. This is
    # a correction to a function-word list, and it is the ONLY category admitted:
    # no content word is ever added here to make copy pass.
    + "before after until since during".split()
) | FRAME_WORDS


def _load() -> dict:
    return json.loads(SEED_PATH.read_text())


def _words(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def _frame(text: str) -> str:
    """The opening frame — first four words. Reused from the dasha gate."""
    return " ".join(_words(text)[:4])


def _skeleton(text: str) -> str:
    """Content words blanked, function words kept — the "same sentence with the
    name swapped in" signature. Reused from the dasha gate."""
    return " ".join(t if t in STOPWORDS else "_" for t in _words(text))


def _norm(word: str) -> str:
    """Light suffix normalisation, so `find`/`finds` and `decision`/`decisions`
    cannot slip past the strict cross-corpus gate on a plural alone. Irregular
    forms (leave/left, is/was) are NOT caught — this is a tightening of a token
    match, not lemmatisation, and it is documented as such rather than sold as
    more than it is."""
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _content_words(text: str) -> set[str]:
    """Normalised non-stopword, non-frame-word tokens."""
    return {_norm(w) for w in _words(text)} - {_norm(s) for s in STOPWORDS} - STOPWORDS


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"[.!?]", text) if s.strip()]


def _prose(entry: dict, fields: tuple[str, ...]) -> list[str]:
    return [entry[f] for f in fields]


def _shipped_word_count(entry: dict, fields: tuple[str, ...]) -> int:
    """Words of prose actually shown to a reader — `contrast` excluded."""
    return sum(len(_words(entry[f])) for f in fields if f != "title")


def _all_strings(data: dict) -> list[tuple[str, str]]:
    """Every authored string incl. contrast reasons, as (where, text)."""
    out: list[tuple[str, str]] = []
    for name, entry in data["nakshatra"].items():
        for field in NAKSHATRA_PROSE:
            out.append((f"nakshatra/{name}/{field}", entry[field]))
        for i, c in enumerate(entry["contrast"]):
            out.append((f"nakshatra/{name}/contrast[{i}]", c["because"]))
    for name, entry in data["moon_sign"].items():
        for field in MOON_SIGN_PROSE:
            out.append((f"moon_sign/{name}/{field}", entry[field]))
    return out


# ── The co-occurrence map, derived rather than typed ─────────────────────────


def co_occurring_pairs() -> list[tuple[str, str]]:
    """The (nakshatra, sign) pairs that can appear on ONE screen.

    Derived from the arithmetic — a nakshatra spans 360/27 = 13°20', a sign
    spans 30° — rather than transcribed from IDENTITY.md §5, so the test
    verifies the spec's claim instead of trusting it. A hardcoded table would
    make a typo in the spec permanently invisible.
    """
    arc = 360.0 / 27.0
    pairs: list[tuple[str, str]] = []
    for i, nak in enumerate(NAKSHATRAS):
        start, end = i * arc, (i + 1) * arc
        first, last = int(start // 30), int((end - 1e-9) // 30)
        for j in range(first, last + 1):
            pairs.append((nak, SIGNS[j]))
    return pairs


def test_the_spec_claim_about_36_pairs_and_9_straddlers() -> None:
    """IDENTITY.md §5 claims 36 co-occurring pairs and names 9 straddling
    nakshatras. Both are load-bearing — the collision gate's whole affordability
    argument rests on the surface being 36 and not 324."""
    pairs = co_occurring_pairs()
    assert len(pairs) == 36, f"expected 36 co-occurring pairs, derived {len(pairs)}"

    counts = Counter(nak for nak, _ in pairs)
    straddlers = sorted(n for n, c in counts.items() if c > 1)
    assert sorted(straddlers) == sorted([
        "Krittika", "Mrigashira", "Punarvasu", "Uttara Phalguni", "Chitra",
        "Vishakha", "Uttara Ashadha", "Dhanishta", "Purva Bhadrapada",
    ]), f"straddling nakshatras do not match IDENTITY.md §5: {straddlers}"
    assert len(straddlers) == 9
    assert set(counts) == set(NAKSHATRAS)


def seeded_pairs(data: dict) -> list[tuple[str, str]]:
    """Co-occurring pairs where BOTH halves are authored — the pairs the
    collision gate can actually run over today."""
    naks, signs = data["nakshatra"], data["moon_sign"]
    return [(n, s) for n, s in co_occurring_pairs() if n in naks and s in signs]


# ── Structure ────────────────────────────────────────────────────────────────


def test_version() -> None:
    """The corpus declares the version its own filename claims.

    Asserted against the FILENAME rather than a literal, so activating a new
    corpus needs one edit (engine/content.py) and not two. A literal here is how
    this module ended up grading v1 after v2 went live.
    """
    assert _load()["version"] == SEED_PATH.stem


def test_keys_are_canonical_names() -> None:
    """A key that is not a real nakshatra/sign name is a row nothing will ever
    look up — the Worker keys on exactly these strings."""
    data = _load()
    for name in data["nakshatra"]:
        assert name in NAKSHATRAS, f"unknown nakshatra key {name!r}"
    for name in data["moon_sign"]:
        assert name in SIGNS, f"unknown sign key {name!r}"


def test_nakshatra_entries_well_formed() -> None:
    for name, entry in _load()["nakshatra"].items():
        assert set(entry) == NAKSHATRA_FIELDS, name
        assert entry["title"].strip() and entry["title"] != name, name
        assert 4 <= len(_words(entry["title"])) <= 7, (
            f"{name} title is {len(_words(entry['title']))} words, spec says 4-7"
        )
        assert len(_sentences(entry["core"])) == 2, f"{name} core must be 2 sentences"
        assert 35 <= len(_words(entry["core"])) <= 55, (
            f"{name} core is {len(_words(entry['core']))} words, spec says 35-55"
        )
        assert 1 <= len(_sentences(entry["cost"])) <= 2, f"{name} cost 1-2 sentences"
        assert 25 <= len(_words(entry["cost"])) <= 40, (
            f"{name} cost is {len(_words(entry['cost']))} words, spec says 25-40"
        )
        assert len(_sentences(entry["misread"])) == 1, f"{name} misread 1 sentence"
        assert 15 <= len(_words(entry["misread"])) <= 25, (
            f"{name} misread is {len(_words(entry['misread']))} words, spec says 15-25"
        )


def test_moon_sign_entries_well_formed() -> None:
    for name, entry in _load()["moon_sign"].items():
        assert set(entry) == MOON_SIGN_FIELDS, name
        assert entry["title"].strip() and entry["title"] != name, name
        assert 3 <= len(_words(entry["title"])) <= 6, (
            f"{name} title is {len(_words(entry['title']))} words, spec says 3-6"
        )
        assert len(_sentences(entry["need"])) == 2, f"{name} need must be 2 sentences"
        assert 30 <= len(_words(entry["need"])) <= 45, (
            f"{name} need is {len(_words(entry['need']))} words, spec says 30-45"
        )
        assert len(_sentences(entry["unsettles"])) == 1, f"{name} unsettles 1 sentence"
        assert 15 <= len(_words(entry["unsettles"])) <= 25, (
            f"{name} unsettles is {len(_words(entry['unsettles']))} words, spec 15-25"
        )


def test_shipped_length_targets() -> None:
    """§4: nakshatra ~100 words ±20, moon sign ~60. Titles excluded — they are
    labels, not the read."""
    data = _load()
    for name, entry in data["nakshatra"].items():
        n = _shipped_word_count(entry, NAKSHATRA_PROSE)
        assert 80 <= n <= 120, f"{name} ships {n} words of prose, target 100 ±20"
    for name, entry in data["moon_sign"].items():
        n = _shipped_word_count(entry, MOON_SIGN_PROSE)
        assert 45 <= n <= 75, f"{name} ships {n} words of prose, target 60 ±15"


# ── Voice ────────────────────────────────────────────────────────────────────


def test_no_banned_vocabulary() -> None:
    for where, text in _all_strings(_load()):
        match = BANNED_RE.search(text)
        assert match is None, f"banned word {match.group(0)!r} in {where}: {text!r}"


def test_no_astrological_jargon() -> None:
    for where, text in _all_strings(_load()):
        match = JARGON_RE.search(text)
        assert match is None, f"jargon {match.group(0)!r} in {where}"


def test_no_barnum_carriers() -> None:
    """§2. These constructions are how universal statements disguise themselves."""
    for where, text in _all_strings(_load()):
        match = BARNUM_RE.search(text)
        assert match is None, f"Barnum carrier {match.group(0)!r} in {where}: {text!r}"


def test_no_humblebrag_shapes() -> None:
    """§3. A cost phrased so it flatters is not a cost."""
    for where, text in _all_strings(_load()):
        match = HUMBLEBRAG_RE.search(text)
        assert match is None, f"humblebrag {match.group(0)!r} in {where}: {text!r}"


def test_hedge_density_per_entry() -> None:
    """§6c: at most one hedge per entry. Specific copy asserts; Barnum hedges."""
    data = _load()
    for kind, fields in (("nakshatra", NAKSHATRA_PROSE), ("moon_sign", MOON_SIGN_PROSE)):
        for name, entry in data[kind].items():
            joined = " ".join(_prose(entry, fields))
            found = HEDGE_RE.findall(joined)
            assert len(found) <= MAX_HEDGES_PER_ENTRY, (
                f"{kind}/{name} carries {len(found)} hedges "
                f"({found}), max is {MAX_HEDGES_PER_ENTRY}"
            )


def test_core_and_cost_are_second_person() -> None:
    """§6c structural check."""
    for name, entry in _load()["nakshatra"].items():
        for field in ("core", "cost"):
            words = set(_words(entry[field]))
            assert words & {"you", "your"}, f"{name}/{field} is not second person"


# ── The vocabulary lanes (§6d.3) ─────────────────────────────────────────────


def test_nakshatra_copy_never_names_an_emotional_need() -> None:
    for name, entry in _load()["nakshatra"].items():
        for field in NAKSHATRA_PROSE:
            match = NAKSHATRA_BANNED_LANE.search(entry[field])
            assert match is None, (
                f"nakshatra/{name}/{field} uses {match.group(0)!r}, which belongs "
                f"to the moon-sign lane (§5: nakshatra owns what you DO)"
            )


def test_moon_sign_copy_never_names_a_behaviour_under_pressure() -> None:
    for name, entry in _load()["moon_sign"].items():
        for field in MOON_SIGN_PROSE:
            match = MOON_SIGN_BANNED_LANE.search(entry[field])
            assert match is None, (
                f"moon_sign/{name}/{field} uses {match.group(0)!r}, which belongs "
                f"to the nakshatra lane (§5: moon sign owns what you NEED)"
            )


# ── Contrast: well-formedness and graph connectivity (§6b.4) ─────────────────


def test_contrast_fields_well_formed() -> None:
    for name, entry in _load()["nakshatra"].items():
        contrast = entry["contrast"]
        assert isinstance(contrast, list) and len(contrast) == 2, (
            f"{name} must name exactly 2 contrast targets, got {len(contrast)}"
        )
        targets = []
        for c in contrast:
            assert set(c) == {"nakshatra", "because"}, f"{name} contrast shape"
            assert c["nakshatra"] in NAKSHATRAS, (
                f"{name} contrasts with {c['nakshatra']!r}, not a nakshatra"
            )
            assert c["nakshatra"] != name, f"{name} contrasts with itself"
            assert len(_words(c["because"])) >= 4, (
                f"{name} contrast reason is too short to name a difference: "
                f"{c['because']!r}"
            )
            targets.append(c["nakshatra"])
        assert targets[0] != targets[1], f"{name} names the same contrast twice"


def test_contrast_graph_is_connected() -> None:
    """§6b.4: a disposition nobody contrasts with is one nobody can be
    distinguished from.

    At full corpus this is the spec's rule verbatim — every one of the 27 must
    be named by some other entry. While the corpus is partial it is asserted
    over the AUTHORED set, which is the strongest form the data supports: every
    authored entry must be named as a contrast by another authored entry. That
    is a real constraint at n=3 (it forces the pilot entries to distinguish
    themselves from each other, which is exactly the pressure the two Ashadhas
    are here to apply), and it hardens to the spec's rule automatically.
    """
    data = _load()
    naks = data["nakshatra"]
    named_by: dict[str, set[str]] = {name: set() for name in naks}
    for name, entry in naks.items():
        for c in entry["contrast"]:
            target = c["nakshatra"]
            if target in named_by:
                named_by[target].add(name)

    complete = len(naks) == FULL_NAKSHATRA_N
    universe = set(NAKSHATRAS) if complete else set(naks)
    for target in universe:
        assert named_by.get(target), (
            f"{target} is named as a contrast by no other authored entry — its "
            f"disposition is not distinguished from anything"
        )


def test_contrast_graph_gate_hardens_to_all_27_when_complete() -> None:
    """Guards the carve-out above from becoming permanent: once 27 entries are
    seeded, connectivity is asserted over all 27, not over an authored subset."""
    data = _load()
    if len(data["nakshatra"]) == FULL_NAKSHATRA_N:
        named = {c["nakshatra"] for e in data["nakshatra"].values() for c in e["contrast"]}
        missing = sorted(set(NAKSHATRAS) - named)
        assert not missing, f"corpus is complete but these are never contrasted: {missing}"


# ── Distinctness (§6b) ───────────────────────────────────────────────────────


def test_every_shipped_string_is_unique() -> None:
    """§6b.3."""
    texts = [t for _, t in _all_strings(_load())]
    dupes = [t for t, n in Counter(texts).items() if n > 1]
    assert not dupes, f"duplicated string: {dupes[:2]}"


def test_no_two_entries_share_an_opening_frame() -> None:
    """§6b.1, per field, per corpus. Two entries opening the same way read as
    the same sentence starting up again."""
    data = _load()
    for kind, fields in (("nakshatra", NAKSHATRA_PROSE), ("moon_sign", MOON_SIGN_PROSE)):
        for field in fields:
            by_frame: dict[str, str] = {}
            for name, entry in data[kind].items():
                frame = _frame(entry[field])
                assert frame not in by_frame, (
                    f"{kind} {name} and {by_frame[frame]} open their {field} "
                    f"identically: {frame!r}"
                )
                by_frame[frame] = name


def test_no_two_entries_share_a_sentence_skeleton() -> None:
    """§6b.2 — the "same sentence, name swapped in" gate that caught
    dasha_content_v1. Titles are carved out per §6b: they are short parallel
    labels read as one family, every one of which reduces to roughly `the _ _ _`,
    so a skeleton gate there fails correct design while catching nothing."""
    data = _load()
    for kind, fields in (("nakshatra", NAKSHATRA_PROSE), ("moon_sign", MOON_SIGN_PROSE)):
        for field in fields:
            if field == "title":
                continue  # the deliberate carve-out
            by_skeleton: dict[str, str] = {}
            for name, entry in data[kind].items():
                skeleton = _skeleton(entry[field])
                assert skeleton not in by_skeleton, (
                    f"{kind} {name} and {by_skeleton[skeleton]} share a sentence "
                    f"skeleton in {field}"
                )
                by_skeleton[skeleton] = name


# ── Word share (§6a) ─────────────────────────────────────────────────────────


def _share_limit(kind: str, n: int) -> int:
    """round(), not int() — see the module docstring."""
    return round(n * MAX_ENTRY_SHARE[kind])


def check_word_share(data: dict, kind: str, fields: tuple[str, ...]) -> dict[str, int]:
    """Content words counted ONCE PER ENTRY (§6a: a word twice inside one profile
    is style; a word across many profiles is a template). Returns offenders."""
    entries = data[kind]
    seen_in: Counter[str] = Counter()
    for entry in entries.values():
        words: set[str] = set()
        for field in fields:
            words |= _content_words(entry[field])
        for word in words:
            seen_in[word] += 1
    limit = _share_limit(kind, len(entries))
    return {w: n for w, n in seen_in.items() if n > limit and len(w) > 2}


@pytest.mark.parametrize("kind,fields", [
    ("nakshatra", NAKSHATRA_PROSE),
    ("moon_sign", MOON_SIGN_PROSE),
])
def test_no_content_word_dominates(kind: str, fields: tuple[str, ...]) -> None:
    data = _load()
    n = len(data[kind])
    limit = _share_limit(kind, n)
    if limit < 2:
        pytest.skip(
            f"{kind} share gate is not meaningful at n={n}: the limit would be "
            f"{limit}, failing on any word shared by two entries. IDENTITY.md "
            f"§6a derives {MAX_ENTRY_SHARE[kind]} against n={FULL_N[kind]}. "
            f"Falsified against a synthetic full corpus in "
            f"test_identity_gates_falsify.py."
        )
    offenders = check_word_share(data, kind, fields)
    assert not offenders, (
        f"{kind} content words above the {MAX_ENTRY_SHARE[kind]:.1%} entry share "
        f"({limit} of {n} entries): {offenders}"
    )


def test_share_gate_is_not_skipped_when_complete() -> None:
    """The skip above must not outlive the pilot. Once either corpus is fully
    authored its limit is >= 2 by construction, so the gate runs."""
    data = _load()
    for kind in ("nakshatra", "moon_sign"):
        if len(data[kind]) == FULL_N[kind]:
            assert _share_limit(kind, FULL_N[kind]) >= 2, (
                f"{kind} corpus is complete but the share gate would still skip"
            )


def test_no_gate_skips_on_a_complete_corpus() -> None:
    """Once the corpus is complete, NOTHING in this module may skip.

    Stronger than `test_share_gate_is_not_skipped_when_complete`, which only
    covers the one gate whose skip was designed in. This runs the whole module
    and fails if any test reports skipped — the honest form of "all gates are
    now running", and the only version of that claim which stays true when a
    future author adds a second conditional skip and forgets it.

    Deliberately a no-op while a corpus is partial: the skip is legitimate then.

    Implemented by CALLING every gate in this module in-process and catching
    `Skipped`, not by shelling out to pytest. The subprocess version of this test
    recursed into itself and hung; more importantly, executing the gates directly
    is the stronger check — it proves each one ran to completion on the real
    corpus rather than parsing a summary line for the word "skipped".
    """
    data = _load()
    if len(data["nakshatra"]) != FULL_NAKSHATRA_N or len(data["moon_sign"]) != FULL_MOON_SIGN_N:
        return

    import inspect

    module = sys.modules[__name__]
    skipped: list[str] = []
    ran = 0
    for name, fn in sorted(vars(module).items()):
        if not name.startswith("test_") or not inspect.isfunction(fn):
            continue
        if name == "test_no_gate_skips_on_a_complete_corpus":
            continue  # no recursion
        params = inspect.signature(fn).parameters
        calls = []
        if marks := getattr(fn, "pytestmark", []):
            for mark in marks:
                if mark.name == "parametrize":
                    for argset in mark.args[1]:
                        calls.append(argset if isinstance(argset, tuple) else (argset,))
        if not calls:
            if params:
                continue  # a fixture-taking gate; nothing here uses one
            calls = [()]
        for args in calls:
            try:
                fn(*args)
                ran += 1
            except Skipped as exc:  # noqa: PERF203 — we want the name with it
                skipped.append(f"{name}{args}: {exc}")

    assert not skipped, (
        "the corpus is complete but these gates still skipped — a skip that "
        "outlives the pilot is a hole, not a carve-out:\n  " + "\n  ".join(skipped)
    )
    assert ran >= 20, f"only {ran} gates executed; this guard is not covering the module"


def test_share_thresholds_match_the_spec_table() -> None:
    """IDENTITY.md §6a's table is the contract: nakshatra fails at 6 entries,
    moon sign at 4. Encoded so a threshold edit that silently loosens the gate
    has to argue with the spec first."""
    assert _share_limit("nakshatra", FULL_NAKSHATRA_N) == 5  # fails at 6
    assert _share_limit("moon_sign", FULL_MOON_SIGN_N) == 3  # fails at 4


# ── Cross-corpus collision (§6d) ─────────────────────────────────────────────


def test_seeded_pairs_cover_real_co_occurrences() -> None:
    """The collision gate must be running over genuine screen combinations, not
    a synthetic pairing. If the pilot ever drifts to a nakshatra and a sign that
    cannot co-occur, this gate silently tests nothing."""
    pairs = seeded_pairs(_load())
    assert len(pairs) >= 5, (
        f"only {len(pairs)} co-occurring pairs are seeded; the pilot is supposed "
        f"to exercise the cross-corpus gate over real pairs"
    )
    assert set(pairs) <= set(co_occurring_pairs())


def test_no_shared_content_word_across_a_co_occurring_pair() -> None:
    """§6d.1 — strict, zero tolerance. 36 pairs is a small enough surface to
    afford it, and a shared content word across the two halves of ONE screen is
    exactly the "same thing twice" padding rule 5 exists to prevent."""
    data = _load()
    for nak, sign in seeded_pairs(data):
        nak_words: set[str] = set()
        for field in NAKSHATRA_PROSE:
            nak_words |= _content_words(data["nakshatra"][nak][field])
        sign_words: set[str] = set()
        for field in MOON_SIGN_PROSE:
            sign_words |= _content_words(data["moon_sign"][sign][field])
        shared = {w for w in nak_words & sign_words if len(w) > 2}
        assert not shared, (
            f"{nak} and {sign} appear on one screen and share content "
            f"word(s) {sorted(shared)} — that is the padding rule 5 bans"
        )


def test_no_shared_skeleton_across_a_co_occurring_pair() -> None:
    """§6d.2."""
    data = _load()
    for nak, sign in seeded_pairs(data):
        nak_skels = {_skeleton(data["nakshatra"][nak][f]) for f in NAKSHATRA_PROSE}
        sign_skels = {_skeleton(data["moon_sign"][sign][f]) for f in MOON_SIGN_PROSE}
        shared = nak_skels & sign_skels
        assert not shared, (
            f"{nak} and {sign} share a sentence skeleton on one screen: {shared}"
        )
