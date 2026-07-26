"""Quality gates for the ACTIVE knowledge corpus — the interpretive significations.

Implements every gate `docs/voice/KNOWLEDGE.md` §7 specifies, the two §8
review gates, and the SOURCE-CITATION gate added by the authoring task's
binding editorial rule 1 (recorded in KNOWLEDGE.md §11). Runs in CI and gates
the nightly pre-seed, like the four existing content gates.

## The seed path is derived, never typed here

`SEED_PATH` comes from `engine.content.KNOWLEDGE_SEED_PATH` — the one line that
declares which corpus is live. This is the same discipline
`test_identity_content_seed.py` had to learn the hard way: when identity v2 was
activated, every gate in that file silently went on grading v1, because the file
carried its own literal. A gate pointed at the wrong file is not a weaker gate,
it is no gate.

## What is different about THIS corpus's gates

Two things, both of which follow from §3 rather than from a preference:

1. **The fear gates are COMPARATIVE.** `test_demand_length_symmetry` and
   `test_heavy_token_density_parity` do not grade an entry — they grade an entry
   *against its category*. That is deliberate (§3: "Groups, not entries, because
   a single entry's density is noise at n=9") and it is the reason migration 015
   seeds all three categories under one version marker. A per-category marker
   would let a half-rolled-back corpus be live with the comparison that licensed
   it no longer in the database.

2. **The hard groups are READ, not typed.** The nine hard nakshatras come from
   `score_rules_content_v4`'s seeded `nakshatra_traits` (`ugra`/`tikshna`), not
   from a list in this file. §3 requires that explicitly — "reusing the seeded
   trait table rather than inventing a list means the grouping is not the
   author's opinion". `test_hard_nakshatras_match_brihat_samhita_98` additionally
   checks that seeded table against the classical grouping it claims to encode,
   so the gate rests on a citable source rather than on a JSON file agreeing
   with itself.

## What these gates CANNOT do — stated, not implied

Per §3's own table, nothing here can tell whether a `demand` reads as a
*condition* or as a *threat*, and nothing here can tell whether a signification
is *traditionally correct*. §8 makes the second of those a recorded human
checkpoint. The SOURCE-CITATION gate narrows it — an entry that cannot name a
text and a locus fails — but a citation proves the claim is *traceable*, not
that it is *right*. The distance between those two is exactly the astrologer's
job, and `test_corpus_is_not_marked_shippable_without_checkpoint_b` is what
stops that distance being crossed silently.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

import pytest
from _pytest.outcomes import Skipped

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.content import IDENTITY_SEED_PATH, KNOWLEDGE_SEED_PATH, SEED_PATH as RULES_SEED_PATH  # noqa: E402
from engine.content import DASHA_SEED_PATH  # noqa: E402

#: Derived from the ONE line that activates a corpus — never typed twice.
SEED_PATH = KNOWLEDGE_SEED_PATH

# Canonical order, identical to aura-api's src/natal.ts NAKSHATRAS and to
# test_identity_content_seed.py. The Worker computes the reader's nakshatra; a
# key that is not on this list is a row nothing will ever look up.
NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
    "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]
#: The nine grahas, keyed exactly as dasha_content_v2's `maha` is keyed — the
#: dasha lord and the weekday day-lord both arrive as these strings.
PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
HOUSES = [f"house_{i}" for i in range(1, 13)]

CATEGORIES = ("nakshatra", "planet", "house")
FULL_N = {"nakshatra": 27, "planet": 9, "house": 12}
KEYS = {"nakshatra": NAKSHATRAS, "planet": PLANETS, "house": HOUSES}

#: §5's spine, plus the sixth field the authoring task added (KNOWLEDGE.md §11).
ENTRY_FIELDS = {"title", "governs", "demand", "source", "source_ref", "distinct_from"}
#: What actually ships as PROSE and is therefore measured for voice, share and
#: distinctness. `source_ref` is a citation, not prose: it is gated by
#: `test_every_entry_cites_a_classical_source` and checked for banned
#: vocabulary, but it is not word-shared or skeleton-compared, because 48
#: citations into six texts SHOULD repeat their text names.
PROSE = ("title", "governs", "demand", "source")
#: The substantive prose — what §6's cross-corpus gate and §7d's density gate
#: measure. Excludes `title` (a label) and `source` (attribution, §4.4).
SUBSTANTIVE = ("governs", "demand")

# §7a — separate denominators per category, re-derived in KNOWLEDGE.md §7a.
MAX_ENTRY_SHARE = {"nakshatra": 0.185, "planet": 0.30, "house": 0.25}

WORD_RE = re.compile(r"[a-z'-]+")

# ── Vocabulary ───────────────────────────────────────────────────────────────

#: Carried over WHOLESALE from test_dasha_content_seed.py via
#: test_identity_content_seed.py, per KNOWLEDGE.md §3. Not re-litigated here.
BANNED_WORDS = [
    "death", "die", "dying", "disease", "illness", "cancer", "divorce",
    "widow", "curse", "cursed", "doom", "doomed", "destroyed", "destruction",
    "ruin", "ruined", "disaster", "tragedy", "inauspicious", "malefic",
    "fate", "fated", "destiny", "destined",
]
#: §3's first addition — the HIERARCHY lexicon. `benefic` is the load-bearing
#: entry: `malefic` was already banned and `benefic` was not, and banning only
#: the bad half of a two-sided hierarchy leaves the hierarchy standing.
HIERARCHY_WORDS = [
    "benefic", "benefics", "auspicious", "dusthana", "evil", "afflicted",
    "affliction", "exalted", "debilitated", "harsh", "cruel", "unfortunate",
    "misfortune",
]
BANNED_RE = re.compile(
    r"\b(" + "|".join(BANNED_WORDS + HIERARCHY_WORDS) + r")\b", re.IGNORECASE
)

#: §7e jargon. `lord` and `ruled by` are carved out INSIDE `source` only — that
#: field's entire job is naming the traditional basis, and without the carve-out
#: an author is forced into "the planet the tradition assigns to Saturday" in a
#: field designed to say "Saturn's day".
JARGON_WORDS = ["gana", "guna", "yoni", "nadi"]
JARGON_RE = re.compile(r"\b(" + "|".join(JARGON_WORDS) + r")\b", re.IGNORECASE)
LORDSHIP_RE = re.compile(r"\b(lord|lords|lordship|ruler|rulers|ruled by)\b", re.IGNORECASE)

#: §4.1 — second person, banned OUTRIGHT. The exact inversion of IDENTITY.md
#: §6c, which requires `you` in every core and cost. One regex enforces the
#: whole reader-vs-system boundary.
SECOND_PERSON_RE = re.compile(r"\b(you|your|yours|yourself)\b", re.IGNORECASE)

#: §4.2 — second person wearing a coat.
READER_CLASS = [
    r"those born under", r"\bnatives\b", r"\bnative\b", r"people with",
    r"anyone with", r"individuals born", r"people born",
]
READER_CLASS_RE = re.compile("|".join(READER_CLASS), re.IGNORECASE)

#: §7e — prediction shapes. Bare `will` is included and is excluded from
#: `source` only, per the spec.
PREDICTION = [
    r"will bring", r"will give", r"will cause", r"results in", r"leads to",
    r"is likely to", r"can expect", r"promises", r"guarantees",
    r"predict\w*", r"forecast\w*",
]
PREDICTION_RE = re.compile("|".join(PREDICTION), re.IGNORECASE)
BARE_WILL_RE = re.compile(r"\bwill\b", re.IGNORECASE)

#: §7e — remedy. Block 5B measured this surface and cut ALL of it; this corpus
#: does not reopen that decision.
REMEDY = [
    "wear", "wears", "wearing", "gemstone", "gemstones", "gem", "gems",
    "stone", "stones",
    "ruby", "sapphire", "emerald", "coral", "pearl", "topaz", "diamond",
    "hessonite", "chant", "chants", "chanting", "mantra", "mantras", "japa",
    "donate", "donation", "charity", "fast", "fasting", "puja", "pooja",
    "yantra", "rudraksha", "temple", "temples", "ritual", "rituals",
    "propitiate", "propitiation", "remedy", "remedies", "remedial",
    "dosha", "parihara",
]
REMEDY_RE = re.compile(
    r"\b(" + "|".join(REMEDY) + r")\b|cat's eye", re.IGNORECASE
)

#: §4.4 — attribution lives in a FIELD, never in prose. Thirty entries in,
#: "traditionally" is a tic, and sprinkled attribution is indistinguishable
#: from hedging.
ATTRIBUTION_RE = re.compile(
    r"\b(traditionally|tradition|traditions|traditional|classically|classical)\b",
    re.IGNORECASE,
)

#: §1.1 / §7e — systems the engine cannot compute. A corpus entry that reads one
#: is describing a system Aura does not have, so it could never be connected to
#: a real reader's data.
EXCLUDED_SYSTEMS_RE = re.compile(
    r"\b(sub-?lords?|navamsa|d9|kp|shadbala|combust\w*|drishti|avastha)\b",
    re.IGNORECASE,
)

#: §7d.2 — the explicit lexicon of PERMITTED-BUT-WEIGHTED words. Any change to
#: this list is a change to KNOWLEDGE.md, not to this file: the lexicon IS the
#: gate, and a lexicon quietly trimmed to make a draft pass is the same failure
#: as an allowlist quietly added.
HEAVY = {
    "slow", "slowly", "delay", "delays", "wait", "waits", "waiting",
    "withhold", "withholds", "refuse", "refuses", "deny", "denies",
    "cost", "costs", "loss", "lose", "loses", "end", "ends", "ended",
    "break", "breaks", "strip", "strips", "hard", "alone", "pain",
    "undo", "undoes", "take", "takes", "taken", "cannot", "never", "nothing",
}

#: §7a — the NARROW frame-word exemption. These name the unit each category is
#: ABOUT, so their frequency measures what the library is. Explicitly NOT
#: exempt, and named in the spec as where this corpus will drift: `life`,
#: `time`, `work`, `people`, `things`, `matters`, `area`, `domain`, `governs`,
#: `read`, `place`.
#: `bhava` and `graha` are the ONE exemption added beyond §7a's list, and it is
#: documented in KNOWLEDGE.md §11 with its justification rather than added
#: quietly here — §6's standing rule for this corpus. They are the Sanskrit
#: names of the units the house and planet categories are ABOUT, they appear
#: only inside `source` and `source_ref`, and exempting them is the identical
#: argument that already exempts `house` and `planet`. Twelve house entries
#: naming their bhava is a fact about the library, not a template.
FRAME_WORDS = {
    "house", "houses", "planet", "planets", "star", "stars",
    "nakshatra", "nakshatras", "sign", "signs", "chart",
    "bhava", "bhavas", "graha", "grahas",
}

STOPWORDS = set(
    """a an the and or but so if then than as at by for from in into of off on onto out
    over to under up with without within is are was were be been being am do does did
    done have has had will would can could may might shall should must not no it its
    this that these those there here they them their you your yours yourself we us our
    i me my one who what when where how why all any both each few more most other some
    such own same too very just only also still once again ever never always now today
    day days week cannot about back through while every
    before after until since during""".split()
) | FRAME_WORDS


# ── Loading ──────────────────────────────────────────────────────────────────


def _load() -> dict:
    return json.loads(SEED_PATH.read_text())


def _words(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def _frame(text: str) -> str:
    """The opening frame — first four words. Reused from the dasha gate."""
    return " ".join(_words(text)[:4])


def _skeleton(text: str) -> str:
    """Content words blanked, function words kept — the "same sentence with the
    name swapped in" signature. Reused from the dasha gate. This corpus is
    unusually exposed to it: 48 entries all answering the same question."""
    return " ".join(t if t in STOPWORDS else "_" for t in _words(text))


def _norm(word: str) -> str:
    """Light suffix normalisation, so a plural alone cannot slip past the strict
    cross-corpus gate. Not lemmatisation, and documented as such."""
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _content_words(text: str) -> set[str]:
    return {_norm(w) for w in _words(text)} - {_norm(s) for s in STOPWORDS} - STOPWORDS


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"[.!?]", text) if s.strip()]


def _entries(data: dict, category: str) -> dict:
    return data[category]


def _all_entries(data: dict):
    for category in CATEGORIES:
        for key, entry in data[category].items():
            yield category, key, entry


def _all_strings(data: dict) -> list[tuple[str, str]]:
    """Every authored string, as (where, text). Includes `source_ref` and the
    `distinct_from.because` scaffolding: neither is shipped prose, but both are
    authored text and neither gets a pass on banned vocabulary."""
    out: list[tuple[str, str]] = []
    for category, key, entry in _all_entries(data):
        for field in PROSE:
            out.append((f"{category}/{key}/{field}", entry[field]))
        out.append((f"{category}/{key}/source_ref", entry["source_ref"]))
        out.append((f"{category}/{key}/distinct_from", entry["distinct_from"]["because"]))
    return out


def _shipped_words(entry: dict) -> int:
    return sum(len(_words(entry[f])) for f in PROSE)


# ── The hard groups, READ rather than typed (§3, §7d.2) ──────────────────────


def _seeded_nakshatra_traits() -> dict[int, str]:
    """The `ugra`/`tikshna` classification as SEEDED, from score_rules.

    §3 requires the nakshatra hard group come from this table rather than from a
    list written by the author of the corpus being graded. Reading it here means
    the grouping is a fact about the product's own data, not an opinion.
    """
    rules = json.loads(RULES_SEED_PATH.read_text())["rules"]
    return {int(k): v for k, v in rules["nakshatra_traits"].items()}


def hard_group(category: str) -> set[str]:
    """The traditionally-difficult group, fixed in advance per §3."""
    if category == "planet":
        return {"Saturn", "Mars", "Rahu", "Ketu"}
    if category == "house":
        return {"house_6", "house_8", "house_12"}
    traits = _seeded_nakshatra_traits()
    return {NAKSHATRAS[i] for i, t in traits.items() if t in ("ugra", "tikshna")}


def test_hard_nakshatras_match_brihat_samhita_98() -> None:
    """The seeded trait table must encode the classical grouping it claims to.

    §3 names the nine as Bharani, Magha, Purva Phalguni, Purva Ashadha, Purva
    Bhadrapada (ugra) and Ardra, Ashlesha, Jyeshtha, Mula (tikshna). Those are
    Brihat Samhita 98.7 (tikshna/sharp: Mula, Ardra, Jyeshtha, Ashlesha) and
    98.8 (ugra/severe: Purva Phalguni, Purva Ashadha, Purva Bhadrapada,
    Bharani, Magha) exactly.

    Asserted here rather than assumed because the density gate's entire claim to
    objectivity is that the grouping came from somewhere other than this corpus.
    If score_rules' table is ever edited, this fails and the edit has to argue
    with a sixth-century source rather than with a colleague.
    """
    assert hard_group("nakshatra") == {
        "Bharani", "Magha", "Purva Phalguni", "Purva Ashadha", "Purva Bhadrapada",
        "Ardra", "Ashlesha", "Jyeshtha", "Mula",
    }


# ── Structure (§7b) ──────────────────────────────────────────────────────────


def test_version() -> None:
    """The corpus declares the version its own filename claims."""
    assert _load()["version"] == SEED_PATH.stem


def test_all_48_entries_present_and_canonically_keyed() -> None:
    """§7b: 27 named nakshatras, 9 named planets, 12 numbered houses. No extras,
    no gaps. A key that is not canonical is a row nothing will ever look up."""
    data = _load()
    for category in CATEGORIES:
        assert set(data[category]) == set(KEYS[category]), (
            f"{category}: seeded keys do not match the canonical set. "
            f"missing={sorted(set(KEYS[category]) - set(data[category]))} "
            f"extra={sorted(set(data[category]) - set(KEYS[category]))}"
        )
        assert len(data[category]) == FULL_N[category]


def test_every_entry_has_every_field_non_empty() -> None:
    for category, key, entry in _all_entries(_load()):
        assert set(entry) == ENTRY_FIELDS, f"{category}/{key} fields: {sorted(entry)}"
        for field in PROSE + ("source_ref",):
            assert isinstance(entry[field], str) and entry[field].strip(), (
                f"{category}/{key}/{field} is empty"
            )


def test_field_lengths_inside_the_spec_bands() -> None:
    """§5's table, verbatim."""
    for category, key, entry in _all_entries(_load()):
        where = f"{category}/{key}"
        n_title = len(_words(entry["title"]))
        assert 3 <= n_title <= 6, f"{where} title is {n_title} words, spec says 3-6"
        assert entry["title"] != key, f"{where} title is the bare name of the thing"

        n_gov = len(_words(entry["governs"]))
        assert 25 <= n_gov <= 40, f"{where} governs is {n_gov} words, spec says 25-40"
        assert 1 <= len(_sentences(entry["governs"])) <= 2, (
            f"{where} governs must be 1-2 sentences"
        )

        n_dem = len(_words(entry["demand"]))
        assert 15 <= n_dem <= 30, f"{where} demand is {n_dem} words, spec says 15-30"
        assert len(_sentences(entry["demand"])) == 1, f"{where} demand must be 1 sentence"

        n_src = len(_words(entry["source"]))
        assert n_src <= 15, f"{where} source is {n_src} words, spec says <=15"


def test_shipped_length_target() -> None:
    """§5: ~65 words of shipped prose, +/-15. Twelve houses read in one sitting
    is ~4 minutes at this size; at IDENTITY.md's 100 it is 1,200 words nobody
    finishes."""
    for category, key, entry in _all_entries(_load()):
        n = _shipped_words(entry)
        assert 50 <= n <= 80, f"{category}/{key} ships {n} words, target 65 +/-15"


def test_distinct_from_is_well_formed() -> None:
    """§7b/§7c.4: one target, valid, same category, not self."""
    data = _load()
    for category, key, entry in _all_entries(data):
        df = entry["distinct_from"]
        assert set(df) == {"entry", "because"}, f"{category}/{key} distinct_from shape"
        assert df["entry"] in data[category], (
            f"{category}/{key} contrasts with {df['entry']!r}, not a "
            f"{category} id in this corpus"
        )
        assert df["entry"] != key, f"{category}/{key} contrasts with itself"
        assert len(_words(df["because"])) >= 4, (
            f"{category}/{key} contrast reason too short to name a difference: "
            f"{df['because']!r}"
        )


def test_distinct_from_coverage(  ) -> None:
    """§7c.4: every entry in a category must be named as at least one other
    entry's target. A jurisdiction nobody contrasts with is one nobody can be
    distinguished from.

    This is the property `contrast` graph-connectivity buys in IDENTITY.md, at
    one target instead of two — affordable because significations collide
    predictably and locally (Mars/Sun both read for drive, 2nd/11th both for
    money) rather than anywhere in the space.
    """
    data = _load()
    for category in CATEGORIES:
        named = {e["distinct_from"]["entry"] for e in data[category].values()}
        missing = sorted(set(data[category]) - named)
        assert not missing, (
            f"{category}: never named as anyone's distinct_from target: {missing}"
        )


# ── Voice (§7e) ──────────────────────────────────────────────────────────────


def test_no_banned_vocabulary() -> None:
    """§3 — BANNED_WORDS plus the hierarchy lexicon, `benefic` included."""
    for where, text in _all_strings(_load()):
        match = BANNED_RE.search(text)
        assert match is None, f"banned word {match.group(0)!r} in {where}: {text!r}"


def test_second_person_is_absent_everywhere() -> None:
    """§4.1 — zero occurrences, anywhere in the corpus. The exact inversion of
    IDENTITY.md §6c, and the one regex that enforces the whole reader-vs-system
    boundary."""
    for where, text in _all_strings(_load()):
        match = SECOND_PERSON_RE.search(text)
        assert match is None, (
            f"second person {match.group(0)!r} in {where} — this corpus explains "
            f"the SYSTEM and never addresses the READER: {text!r}"
        )


def test_no_reader_class_third_person() -> None:
    """§4.2 — second person wearing a coat is still a claim about people."""
    for where, text in _all_strings(_load()):
        match = READER_CLASS_RE.search(text)
        assert match is None, f"reader-class phrase {match.group(0)!r} in {where}"


def test_no_prediction_shapes() -> None:
    """§7e. Bare `will` is permitted in `source` only — the spec's carve-out."""
    data = _load()
    for where, text in _all_strings(data):
        match = PREDICTION_RE.search(text)
        assert match is None, f"prediction shape {match.group(0)!r} in {where}: {text!r}"
    for category, key, entry in _all_entries(data):
        for field in ("title", "governs", "demand"):
            match = BARE_WILL_RE.search(entry[field])
            assert match is None, (
                f"{category}/{key}/{field} contains a bare `will` — the corpus "
                f"states what a domain is READ FOR, never what happens in it"
            )


def test_no_remedies() -> None:
    """§1.3 / §7e. Block 5B cut this surface entirely and this corpus does not
    reopen it: a signification that names a problem and a remedy in the same
    breath is the fear-sell-then-charge shape Aura refuses."""
    for where, text in _all_strings(_load()):
        match = REMEDY_RE.search(text)
        assert match is None, f"remedy vocabulary {match.group(0)!r} in {where}: {text!r}"


def test_no_attribution_words_in_prose() -> None:
    """§4.4 — attribution is structural, not prose. It lives in `source`, is
    rendered once from the field, and is banned from `governs` and `demand`
    outright so it cannot become a 48-entry tic that the share cap would catch
    the shape of without catching the cause."""
    for category, key, entry in _all_entries(_load()):
        for field in ("governs", "demand"):
            match = ATTRIBUTION_RE.search(entry[field])
            assert match is None, (
                f"{category}/{key}/{field} says {match.group(0)!r}; attribution "
                f"belongs in `source` (§4.4)"
            )


def test_no_astrological_jargon() -> None:
    """§7e. `lord` / `ruled by` are the single documented carve-out and are
    permitted INSIDE `source` only."""
    data = _load()
    for where, text in _all_strings(data):
        match = JARGON_RE.search(text)
        assert match is None, f"jargon {match.group(0)!r} in {where}"
    for category, key, entry in _all_entries(data):
        for field in ("title", "governs", "demand"):
            match = LORDSHIP_RE.search(entry[field])
            assert match is None, (
                f"{category}/{key}/{field} uses {match.group(0)!r}; the carve-out "
                f"is for `source` only (§7e)"
            )


def test_no_systems_the_engine_cannot_compute() -> None:
    """§1.1. A sub-lord or a divisional chart can never be connected to a real
    reader's data — it would be decoration claiming to be personalisation."""
    for where, text in _all_strings(_load()):
        match = EXCLUDED_SYSTEMS_RE.search(text)
        assert match is None, f"excluded system {match.group(0)!r} in {where}"


def test_subject_discipline_governs_opens_with_the_thing() -> None:
    """§4.3 — the grammatical subject is the thing itself or the domain it names.

    Checked at the one place it is mechanically visible: `governs` must open on
    the entry's own subject. This is the positive counterpart to the second-
    person ban — banning `you` stops the reader being addressed, but it does not
    by itself stop an entry drifting into a subjectless generality.

    Deliberately narrow, and the limit is stated: this proves the SENTENCE
    starts on the thing, not that every clause keeps it. §7f leaves the rest to
    review, and this test does not pretend otherwise.
    """
    data = _load()
    for category, key, entry in _all_entries(data):
        opening = " ".join(_words(entry["governs"])[:6])
        if category == "house":
            number = key.removeprefix("house_")
            ordinals = {
                "1": "first", "2": "second", "3": "third", "4": "fourth",
                "5": "fifth", "6": "sixth", "7": "seventh", "8": "eighth",
                "9": "ninth", "10": "tenth", "11": "eleventh", "12": "twelfth",
            }
            assert ordinals[number] in opening or number in opening, (
                f"house/{key} governs does not open on the house itself: {opening!r}"
            )
        else:
            first_word = key.split()[0].lower()
            assert first_word in opening, (
                f"{category}/{key} governs does not open on {key}: {opening!r}"
            )


# ── Fear symmetry — the §3 battery (§7d) ─────────────────────────────────────


def _demand_lengths(data: dict, category: str) -> dict[str, int]:
    return {k: len(_words(e["demand"])) for k, e in data[category].items()}


def _heavy_density(entry: dict) -> float:
    words = [w for f in SUBSTANTIVE for w in _words(entry[f])]
    if not words:
        return 0.0
    return sum(1 for w in words if w in HEAVY) / len(words)


@pytest.mark.parametrize("category", CATEGORIES)
def test_demand_length_symmetry(category: str) -> None:
    """§7d.1: within a category, no `demand` may exceed 1.5x the category median
    word count, nor fall below 0.6x.

    This is the gate for the failure the banned-word list cannot see: four
    sentences where Jupiter got one, at three times the corpus heavy-token
    density, using nothing forbidden. It reads as dread and no vocabulary gate
    on earth catches it.
    """
    data = _load()
    lengths = _demand_lengths(data, category)
    median = statistics.median(lengths.values())
    lo, hi = 0.6 * median, 1.5 * median
    offenders = {k: n for k, n in lengths.items() if not (lo <= n <= hi)}
    assert not offenders, (
        f"{category}: demand lengths outside [{lo:.1f}, {hi:.1f}] "
        f"(median {median}): {offenders}"
    )


@pytest.mark.parametrize("category", CATEGORIES)
def test_heavy_token_density_parity(category: str) -> None:
    """§7d.2: the traditionally-hard group's MEAN heavy-token density may not
    exceed 1.25x the mean of the rest of its category.

    Groups, not entries, because a single entry's density is noise at n=9. The
    hard groups are fixed in advance and, for nakshatras, read from the seeded
    trait table (see `hard_group`).
    """
    data = _load()
    hard_keys = hard_group(category)
    hard = [_heavy_density(e) for k, e in data[category].items() if k in hard_keys]
    rest = [_heavy_density(e) for k, e in data[category].items() if k not in hard_keys]
    assert hard and rest, f"{category}: hard/rest split is degenerate"
    hard_mean, rest_mean = statistics.mean(hard), statistics.mean(rest)
    # A zero baseline is the §7d.3 direction expressed at group level: the easy
    # entries have been written into weightless reassurance. Reported as its own
    # failure rather than left to divide by zero inside the message — a gate that
    # raises ZeroDivisionError instead of AssertionError still stops CI, but it
    # stops it with a stack trace that names arithmetic instead of the defect.
    assert rest_mean > 0, (
        f"{category}: the non-hard entries carry NO heavy tokens at all "
        f"(hard group mean {hard_mean:.4f}). The easy half has become "
        f"reassurance, which is the half §3 says authors forget."
    )
    assert hard_mean <= 1.25 * rest_mean, (
        f"{category}: the hard group ({sorted(hard_keys)}) carries mean heavy-token "
        f"density {hard_mean:.4f} against {rest_mean:.4f} for the rest — "
        f"{hard_mean / rest_mean:.2f}x, over the 1.25x cap. That is dread built "
        f"from permitted words."
    )


@pytest.mark.parametrize("category", CATEGORIES)
def test_inverse_floor_every_demand_has_weight(category: str) -> None:
    """§7d.3 — the direction that gets forgotten.

    EVERY demand, including Jupiter's and the 5th house's, must carry at least
    one HEAVY token. This is what stops the traditionally-easy entries becoming
    reassurance: a corpus where Jupiter's demand is absent has reproduced the
    hierarchy in tone while passing every vocabulary check.
    """
    data = _load()
    for key, entry in data[category].items():
        found = [w for w in _words(entry["demand"]) if w in HEAVY]
        assert found, (
            f"{category}/{key} has a costless demand — no HEAVY token. "
            f"Saturn may not read as doomed, AND Jupiter may not read as free."
        )


def test_heavy_lexicon_is_the_spec_lexicon() -> None:
    """§7d.2's closing rule: any change to HEAVY is a change to KNOWLEDGE.md,
    not to this file. Encoded so a lexicon quietly trimmed to make a draft pass
    has to argue with the spec first."""
    spec_stems = {
        "slow", "delay", "wait", "withhold", "refuse", "deny", "cost", "loss",
        "lose", "end", "ends", "break", "strip", "hard", "alone", "pain",
        "undo", "take", "taken", "cannot", "never", "nothing",
    }
    assert spec_stems <= HEAVY, f"HEAVY has lost spec stems: {sorted(spec_stems - HEAVY)}"


# ── Distinctness within a category (§7c) ─────────────────────────────────────


def test_every_shipped_string_is_unique() -> None:
    """§7c.3."""
    texts = [t for _, t in _all_strings(_load())]
    dupes = [t for t, n in Counter(texts).items() if n > 1]
    assert not dupes, f"duplicated string: {dupes[:2]}"


@pytest.mark.parametrize("category", CATEGORIES)
def test_no_two_entries_share_an_opening_frame(category: str) -> None:
    """§7c.1, per field, per category — the reading unit is the category: a
    reader browses all twelve houses in one sitting."""
    data = _load()
    for field in PROSE:
        by_frame: dict[str, str] = {}
        for key, entry in data[category].items():
            frame = _frame(entry[field])
            assert frame not in by_frame, (
                f"{category} {key} and {by_frame[frame]} open their {field} "
                f"identically: {frame!r}"
            )
            by_frame[frame] = key


@pytest.mark.parametrize("category", CATEGORIES)
def test_no_two_entries_share_a_sentence_skeleton(category: str) -> None:
    """§7c.2 — the "one template, name swapped in" gate that caught
    dasha_content_v1. Titles are carved out per §7c: they are short parallel
    labels read as one family, and a skeleton gate there fails correct design
    while catching nothing."""
    data = _load()
    for field in PROSE:
        if field == "title":
            continue  # the deliberate carve-out
        by_skeleton: dict[str, str] = {}
        for key, entry in data[category].items():
            skeleton = _skeleton(entry[field])
            assert skeleton not in by_skeleton, (
                f"{category} {key} and {by_skeleton[skeleton]} share a sentence "
                f"skeleton in {field}"
            )
            by_skeleton[skeleton] = key


# ── Word share (§7a) ─────────────────────────────────────────────────────────


def _share_limit(category: str, n: int) -> int:
    """round(), not int() — following IDENTITY.md's recorded resolution of the
    same discrepancy: the spec's TABLE states the intent."""
    return round(n * MAX_ENTRY_SHARE[category])


def check_word_share(data: dict, category: str) -> dict[str, int]:
    """Content words counted ONCE PER ENTRY (§7a: a word twice in one entry is
    style; a word across many entries is a template)."""
    seen_in: Counter[str] = Counter()
    for entry in data[category].values():
        words: set[str] = set()
        for field in PROSE:
            words |= _content_words(entry[field])
        for word in words:
            seen_in[word] += 1
    limit = _share_limit(category, len(data[category]))
    return {w: n for w, n in seen_in.items() if n > limit and len(w) > 2}


@pytest.mark.parametrize("category", CATEGORIES)
def test_no_content_word_dominates(category: str) -> None:
    data = _load()
    n = len(data[category])
    offenders = check_word_share(data, category)
    assert not offenders, (
        f"{category} content words above the {MAX_ENTRY_SHARE[category]:.1%} entry "
        f"share ({_share_limit(category, n)} of {n} entries): {offenders}"
    )


def test_share_thresholds_match_the_spec_table() -> None:
    """§7a's table is the contract: nakshatra fails at 6 entries, house at 4,
    planet at 4. Encoded so a threshold edit that silently loosens the gate has
    to argue with the spec first."""
    assert _share_limit("nakshatra", 27) == 5  # fails at 6
    assert _share_limit("house", 12) == 3      # fails at 4
    assert _share_limit("planet", 9) == 3      # fails at 4


def test_governs_is_not_the_verb_of_every_entry() -> None:
    """§7a names `governs` specially: it is the field name, and it will become
    the verb of all 48 entries unless the cap is allowed to catch it. The cap
    already would — this asserts the outcome directly so the reason is legible
    at the point of failure rather than as a bare word in an offenders dict."""
    data = _load()
    for category in CATEGORIES:
        n = sum(
            1 for e in data[category].values()
            if "govern" in " ".join(_words(e["governs"]) + _words(e["demand"]))
        )
        assert n <= _share_limit(category, len(data[category])), (
            f"{category}: `govern*` appears in {n} entries — the field name has "
            f"become the corpus's verb"
        )


# ── Cross-corpus collision — three surfaces, all 1:1 (§6) ────────────────────


def _identity_corpus() -> dict:
    return json.loads(IDENTITY_SEED_PATH.read_text())["nakshatra"]


def _dasha_corpus() -> dict:
    return json.loads(DASHA_SEED_PATH.read_text())["maha"]


def _substantive_words(entry: dict) -> set[str]:
    words: set[str] = set()
    for field in SUBSTANTIVE:
        words |= _content_words(entry[field])
    return words


def test_collision_surfaces_are_the_expected_size() -> None:
    """§6 claims three surfaces, every one a perfect 1:1 mapping, 48 pairs
    total. Load-bearing: the affordability of zero-tolerance rests on the
    surface being small, and the gates below silently test nothing if a
    corpus is keyed differently than assumed."""
    data = _load()
    identity, dasha = _identity_corpus(), _dasha_corpus()
    assert set(data["nakshatra"]) == set(identity), "nakshatra surface is not 1:1"
    assert set(data["planet"]) == set(dasha), "planet surface is not 1:1"
    baseline = data["_about"]["definitional_baseline"]
    assert set(data["house"]) == set(baseline), "house surface is not 1:1"
    assert len(identity) + len(dasha) + len(baseline) == 48


def test_no_shared_content_word_with_identity_content() -> None:
    """§6a — Identity owns the PERSON; Knowledge owns the SYMBOL.

    27 pairs, zero tolerance, over `governs`+`demand` against `core`+`cost`.
    The specific failure mode this catches is identity's core claim rewritten in
    the third person: the easiest entry to write, and the one that makes the app
    say the same thing twice with a grammar change.
    """
    data = _load()
    identity = _identity_corpus()
    for name, entry in data["nakshatra"].items():
        theirs = _content_words(identity[name]["core"]) | _content_words(
            identity[name]["cost"]
        )
        shared = {w for w in _substantive_words(entry) & theirs if len(w) > 2}
        assert not shared, (
            f"knowledge/{name} and identity_content/{name} share content "
            f"word(s) {sorted(shared)} — a reader reaches one from the other "
            f"(Block 7 follow-up 3de3a53 wired that link)"
        )


def test_no_shared_content_word_with_dasha_content() -> None:
    """§6b — Dasha owns the PERIOD; Knowledge owns the PLANET. 9 pairs."""
    data = _load()
    dasha = _dasha_corpus()
    for name, entry in data["planet"].items():
        theirs = _content_words(dasha[name]["essence"])
        shared = {w for w in _substantive_words(entry) & theirs if len(w) > 2}
        assert not shared, (
            f"knowledge/{name} and dasha_content/{name} share content word(s) "
            f"{sorted(shared)}"
        )


def test_no_shared_content_word_with_the_definitional_house_card() -> None:
    """§6c — 12 pairs, against the COPY of the shipped Block 7 card.

    This gate deliberately does NOT import the Flutter source. Three crossval
    suites in aura-api broke CI for ten consecutive runs by importing
    `../../aura-engine/db/seed/...`, a sibling path that exists on a laptop and
    not in a runner. Repeating that across the Aura repo boundary would be
    worse. So the twelve definitional lines are copied into `_about`, the gate
    runs against the copy, and keeping it in sync is a named review-checklist
    item (§8) rather than a pretend-mechanical one.
    """
    data = _load()
    baseline = data["_about"]["definitional_baseline"]
    for key, entry in data["house"].items():
        theirs = _content_words(baseline[key])
        shared = {w for w in _substantive_words(entry) & theirs if len(w) > 2}
        assert not shared, (
            f"knowledge/{key} restates the Block 7 definitional line "
            f"({baseline[key]!r}) — shared: {sorted(shared)}"
        )


def test_no_shared_skeleton_across_any_collision_pair() -> None:
    """§6's rule 2, on all three surfaces."""
    data = _load()
    identity, dasha = _identity_corpus(), _dasha_corpus()
    for name, entry in data["nakshatra"].items():
        ours = {_skeleton(entry[f]) for f in SUBSTANTIVE}
        theirs = {_skeleton(identity[name][f]) for f in ("core", "cost")}
        assert not ours & theirs, f"{name}: shared skeleton with identity_content"
    for name, entry in data["planet"].items():
        ours = {_skeleton(entry[f]) for f in SUBSTANTIVE}
        assert _skeleton(dasha[name]["essence"]) not in ours, (
            f"{name}: shared skeleton with dasha_content"
        )


def test_knowledge_prose_avoids_the_dasha_period_lane() -> None:
    """§6's rule 3 — vocabulary lanes. Dasha owns the period; the period
    vocabulary is banned here outside `source`."""
    lane = re.compile(r"\b(period|periods|years|era|eras|stretch|stretches)\b", re.I)
    for category, key, entry in _all_entries(_load()):
        for field in ("title", "governs", "demand"):
            match = lane.search(entry[field])
            assert match is None, (
                f"{category}/{key}/{field} uses {match.group(0)!r}, the dasha "
                f"lane's period vocabulary (§6b: Dasha owns the PERIOD)"
            )


def test_definitional_baseline_is_the_shipped_twelve_lines() -> None:
    """§6c: the copy must be a copy. Shape-checked here; SYNC with the shipped
    card is a named human review item, and this test says so rather than
    implying it is covered."""
    baseline = _load()["_about"]["definitional_baseline"]
    assert set(baseline) == set(HOUSES)
    for key, line in baseline.items():
        number = key.removeprefix("house_")
        assert line.startswith(f"{number} — "), (
            f"{key} baseline is not in the shipped card's `N — a, b, c` shape: {line!r}"
        )


# ── SOURCE CITATION — the accuracy standard (KNOWLEDGE.md §11) ───────────────
#
# Binding editorial rule 1 of the authoring task: "correct" means "traceable to
# the tradition", the same way the engine cites AstroSage/DrikPanchang for its
# numbers. A signification that cannot be sourced is flagged, never fabricated.
#
# What this gate proves and what it does not: it proves every entry NAMES a
# classical text and a locus inside it. It does not prove the text says what the
# entry says — that is §8, and only an astrologer.

CITABLE_TEXTS = {
    "BPHS": "Brihat Parashara Hora Shastra",
    "Phaladeepika": "Phaladeepika (Mantreswara)",
    "Uttara Kalamrita": "Uttara Kalamrita (Kalidasa)",
    "Brihat Samhita": "Brihat Samhita (Varahamihira)",
    "Brihat Jataka": "Brihat Jataka (Varahamihira)",
    "Taittiriya Brahmana": "Taittiriya Brahmana",
}
#: `<Text> <locator> — <gloss>`, clauses joined by "; ". The locator must open
#: on a digit or a Roman numeral, so "BPHS — the planets" cannot pass as a
#: citation of a 97-chapter book.
CITATION_RE = re.compile(
    r"^(?P<text>" + "|".join(re.escape(t) for t in CITABLE_TEXTS) + r")"
    r" (?P<locator>[0-9IVX][^—]*?) — (?P<gloss>.+)$"
)


def _citations(source_ref: str) -> list[re.Match]:
    return [CITATION_RE.match(clause.strip()) for clause in source_ref.split(";")]


def test_every_entry_cites_a_classical_source() -> None:
    """The SOURCE-CITATION gate. Every entry, or it fails."""
    for category, key, entry in _all_entries(_load()):
        ref = entry["source_ref"]
        matches = _citations(ref)
        assert all(m is not None for m in matches), (
            f"{category}/{key} source_ref is not parseable as "
            f"`<Text> <locator> — <gloss>` clauses: {ref!r}. "
            f"Citable texts: {sorted(CITABLE_TEXTS)}"
        )
        for m in matches:
            assert len(_words(m.group("gloss"))) >= 2, (
                f"{category}/{key} citation gloss names nothing: {m.group(0)!r}"
            )


def test_no_category_rests_on_a_single_text() -> None:
    """A corpus where all 27 nakshatras cite one chapter has a citation habit,
    not a grounding. Each category must draw on at least two distinct texts."""
    data = _load()
    for category in CATEGORIES:
        texts = {
            m.group("text")
            for e in data[category].values()
            for m in _citations(e["source_ref"])
        }
        assert len(texts) >= 2, (
            f"{category} cites only {texts} across {FULL_N[category]} entries"
        )


def test_source_field_is_plain_english_not_a_citation() -> None:
    """§5: `source` is the traditional basis in PLAIN ENGLISH — the symbol, the
    presiding figure, the weekday. The citation lives in `source_ref`. Keeping
    them apart is what lets the app render one and audit the other."""
    for category, key, entry in _all_entries(_load()):
        for text in CITABLE_TEXTS:
            assert text.lower() not in entry["source"].lower(), (
                f"{category}/{key} source names {text!r}; citations belong in "
                f"source_ref (§5)"
            )


def test_every_hard_entry_logs_its_reframing() -> None:
    """Binding editorial rule 2: difficult significations render as
    demanding-and-meaningful, and each such reframing is LOGGED as a documented
    editorial choice — the way the engine logs its ayanamsa and delta-T choices.

    Enforced over exactly the §3 hard groups, so the log cannot quietly shrink
    to the three entries someone remembered.
    """
    data = _load()
    logged = {r["entry"] for r in data["_about"]["editorial_reframings"]}
    for category in CATEGORIES:
        missing = sorted(hard_group(category) - logged)
        assert not missing, (
            f"{category}: traditionally-difficult entries reframed but not "
            f"logged: {missing}"
        )
    for record in data["_about"]["editorial_reframings"]:
        assert set(record) == {"entry", "source_says", "rendered_as", "why"}, record
        assert len(_words(record["why"])) >= 5, f"reframing rationale too thin: {record}"


# ── §8 — the astrologer-review checkpoints, made un-skippable ────────────────


def _review(data: dict) -> dict:
    return data["_about"]["astrologer_review"]


def test_sample_review_recorded_before_full_corpus() -> None:
    """§8: if the seed carries more than 9 entries, `checkpoint_a` must be
    present and `approved*`."""
    data = _load()
    total = sum(len(data[c]) for c in CATEGORIES)
    if total <= 9:
        return
    a = _review(data)["checkpoint_a"]
    assert a.get("verdict", "").startswith("approved"), (
        f"corpus carries {total} entries but checkpoint_a verdict is "
        f"{a.get('verdict')!r} (§8: authoring does not proceed past the sample)"
    )
    for field in ("reviewer", "date", "sample"):
        assert a.get(field), f"checkpoint_a is missing {field}"


def test_checkpoint_a_sample_deviation_is_recorded_not_omitted() -> None:
    """§8 mandates the sample be the HARDEST cases: Ketu, the 8th house, and one
    of Ashlesha / Mula. "A sample of Jupiter, the 5th house and Rohini proves
    nothing about the only part that is hard."

    The sample actually reviewed was Saturn, Hasta and the 8th house, which
    meets one of the three mandatory slots. That is a real deviation from a
    binding spec, and the gate's job is to make it a DELIBERATE RECORDED ENTRY
    rather than an omission — the same difference §8 draws between a false entry
    and a forgotten one. So: either the mandatory sample is met, or
    `spec_deviations` names the shortfall explicitly.
    """
    data = _load()
    a = _review(data)["checkpoint_a"]
    sample = set(a["sample"])
    mandatory_met = (
        "Ketu" in sample and "house_8" in sample and bool(sample & {"Ashlesha", "Mula"})
    )
    if mandatory_met:
        return
    deviations = " ".join(_review(data)["spec_deviations"])
    assert "checkpoint_a" in deviations and "sample" in deviations, (
        "checkpoint_a's sample does not meet §8's mandatory hardest-cases set "
        f"({sorted(sample)}), and spec_deviations does not say so. An unrecorded "
        "shortfall against a binding spec is exactly what §8 exists to prevent."
    )


def test_reviewer_qualification_is_stated_not_implied() -> None:
    """§8's whole claim is that only an astrologer can answer "is this
    signification traditionally correct?". A review record that names a reviewer
    without stating whether they are one lets a product sign-off be read later as
    a practitioner's. The field is required to say which it was."""
    review = _review(_load())
    for checkpoint in ("checkpoint_a", "checkpoint_b"):
        qualification = review[checkpoint].get("reviewer_is_astrologer")
        assert isinstance(qualification, bool), (
            f"{checkpoint}.reviewer_is_astrologer must be an explicit boolean, "
            f"got {qualification!r}"
        )


def test_full_review_recorded_before_complete() -> None:
    """§8: if `status` is COMPLETE, `checkpoint_b` must be present, `approved*`,
    and `entries_marked_inaccurate == 0`."""
    data = _load()
    if not data["_about"]["status"].startswith("COMPLETE"):
        return
    b = _review(data)["checkpoint_b"]
    assert b.get("verdict", "").startswith("approved"), b
    assert b.get("entries_marked_inaccurate") == 0, b
    assert b.get("reviewer") and b.get("date"), b


def test_corpus_is_not_marked_shippable_without_checkpoint_b() -> None:
    """§8 Checkpoint B BLOCKS SHIP — "before any of it reaches a reader, through
    any surface: knowledge screen, explainer context, or otherwise".

    The seed therefore carries an explicit `shippable` flag, and it may be true
    only when checkpoint_b is approved by a stated astrologer with zero entries
    marked inaccurate. The Worker echoes this flag, so the app can refuse to
    render a corpus no practitioner has passed — which is the difference between
    a blocking gate and a note in a launch plan.
    """
    data = _load()
    about = data["_about"]
    b = _review(data)["checkpoint_b"]
    approved = (
        b.get("verdict", "").startswith("approved")
        and b.get("entries_marked_inaccurate") == 0
        and b.get("reviewer_is_astrologer") is True
    )
    assert about["shippable"] is approved, (
        f"_about.shippable is {about['shippable']} but checkpoint_b approval is "
        f"{approved}. This corpus's claim is 'here is what the tradition says', "
        f"and a writer cannot own that."
    )


def test_no_gate_skips_on_a_complete_corpus() -> None:
    """Once all 48 entries exist, NOTHING in this module may skip.

    The identity suite's guard, carried over: it runs every gate in this module
    in-process and fails if any reports skipped. A skip that outlives the pilot
    is a hole, not a carve-out — and this corpus has no pilot phase in which one
    would be legitimate.
    """
    data = _load()
    if any(len(data[c]) != FULL_N[c] for c in CATEGORIES):
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
        calls: list[tuple] = []
        for mark in getattr(fn, "pytestmark", []):
            if mark.name == "parametrize":
                for argset in mark.args[1]:
                    calls.append(argset if isinstance(argset, tuple) else (argset,))
        if not calls:
            if inspect.signature(fn).parameters:
                continue
            calls = [()]
        for args in calls:
            try:
                fn(*args)
                ran += 1
            except Skipped as exc:  # noqa: PERF203 — we want the name with it
                skipped.append(f"{name}{args}: {exc}")

    assert not skipped, (
        "the corpus is complete but these gates still skipped:\n  " + "\n  ".join(skipped)
    )
    assert ran >= 30, f"only {ran} gates executed; this guard is not covering the module"
