"""Corpus gate for the transit library (report_kind='transit', v4).

THE SAME BATTERY AS THE RANGE-REPORT CORPORA, PLUS A CLASS OF GATE NOTHING
ELSE IN THIS REPO HAS NEEDED.

Transit content is where astrology apps fear-sell hardest, and the existing
defences do not reach it. `BANNED_WORDS` already carries `doom`, `curse`,
`malefic`, `inauspicious`, `fate`, `disaster`; `FORTUNE_PATTERNS` already
catches the promise. Neither can see this:

    "This is a demanding stretch. Old patterns surface. What you built may be
     tested in ways that are not immediately obvious."

Zero banned words. Zero promises. Reads as dread. **Fear is constructible
entirely from permitted vocabulary**, so a vocabulary scan is structurally
incapable of catching it, and a corpus can pass every gate this repo had and
still be the thing the product is positioned against.

The rule the copy holds instead, from docs/REPORTS.md § 6.6:

    A hard transit is NAMED, BOUNDED and ACTIONABLE — in that order. The
    reader must finish knowing WHAT is demanding, HOW LONG it lasts, and WHAT
    TO DO about it. Remove any one and it becomes either a threat or a
    platitude.

Five gates enforce it. The first four are still, in the end, patterns over
words — a sufficiently careful author could satisfy all four and still write
dread. THE FIFTH IS THE ONE THAT CANNOT BE GAMED, because it is a measurement
over the corpus that no individual line reveals: for each mover, the demanding
copy and the supportive copy must be statistically comparable in length and in
content-word density. **You cannot write dread without spending more words on
it.** Fear-selling shows up as the hard copy being longer and more vivid than
the easy copy, and gate 5 fires on copy that passes gates 1-4 completely.

That is the transit analogue of the share cap: a property of the library that
is invisible line by line. tests/test_report_gates_falsify.py proves it by
inflating every demanding line 40% USING ONLY PERMITTED WORDS — gate 5 goes
red while 1-4 stay green, which is the whole argument for its existence.

SIZE, AND WHY IT IS NOT UNIFORM. 71 lines: 21 weather (3 classes x 7), 36
passage (3 movers x 12 houses x 1), 9 phase (3 movers x 3 x 1), 5 sade_sati.
The one-line cells are not under-authored — they are the audit's own
conclusion (§ 6.8). A reader returns to a given (mover, house) cell once per
that mover's sidereal period, so the soonest any of them can recur is twelve
years (Jupiter's 11.9 is the shortest), against the weekly corpus's 17-week
guarantee. Consecutive distinctness is FREE here, and a rotation on top would
change the words while the fact stood still — decorative variety, which § 3
rejects by name. `weather` is the sole exception and the sole rotated cell: it
is a three-class claim over ~37 states per decade, so a reader meets
`demanding` some sixteen times in ten years, and one line per class would be
the "fourth report running that opened the same way" failure at the one slot
where it can actually occur.
"""

from __future__ import annotations

import json
import re
from collections import Counter

import pytest

import tests.test_report_content_seed as G
from engine.reports import KEY_TYPES
from engine.transits import (
    INDEPENDENT_MOVERS,
    SADE_SATI_PHASES,
    SUPPORTIVE_HOUSES,
    WEATHER_VARIANTS,
)

SEED_PATH = G.SEED_PATH

WEATHER_CLASSES = ("supported", "mixed", "demanding")
PHASES = ("early", "middle", "late")
SADE_SATI_KEYS = ("rising", "peak", "setting", "resuming", "brief")

#: The unit words a transit reading is unavoidably ABOUT — the same narrow
#: exemption the weekly corpus gives `week` and the monthly gives `month`, and
#: pinned as narrow by `test_transit_frame_exemption_is_narrow` in both
#: directions.
#:
#: THE PLANET NAMES ARE FRAME WORDS AND THAT IS LOAD-BEARING. `Saturn` appears
#: in 15 of 71 lines by construction — 12 passage cells plus 3 phase cells —
#: because transit is the only kind that may name a planet at all and its
#: passage copy is REQUIRED to. That frequency measures what the library is,
#: not how repetitive the writing is, which is exactly the FRAME_WORDS test.
#: The possessives are included on the same morphological-variant grounds the
#: monthly set includes `month's`: WORD_RE keeps the apostrophe, so `Saturn's`
#: is its own token and would otherwise be capped as an ordinary word.
TRANSIT_FRAME_WORDS = {
    "saturn", "jupiter", "rahu", "ketu",
    "saturn's", "jupiter's", "rahu's", "ketu's",
    "passage", "passages", "house", "houses", "phase", "phases",
    "transit", "transits", "mover", "movers",
    "placement", "position", "positions",
}

PLANET_WORDS = {
    "saturn", "jupiter", "rahu", "ketu",
    "saturn's", "jupiter's", "rahu's", "ketu's",
}

# ─── the five fear gates ─────────────────────────────────────────────────────

#: GATE 1. The fatalism signature is GRAMMATICAL, not lexical: the planet as
#: agent and the reader as patient. "Saturn tests you", "Rahu pulls you",
#: "Jupiter brings you". Every one of those is built from permitted words, so
#: this is matched as a pattern.
#:
#: The discrimination that makes it usable: a planet may be the SUBJECT of a
#: locative ("Saturn stands in your tenth", "Jupiter sits over home"), because
#: that states where a body is — a fact. It may not take the reader as a direct
#: OBJECT, because that states what a body is doing TO them — a claim the maths
#: cannot support and the voice specs forbid. The adjacency requirement is what
#: separates the two: "stands in your" has a preposition between the verb and
#: the reader; "tests you" does not.
AGENT_ADJACENT = re.compile(
    r"\b(saturn|jupiter|rahu|ketu)\b(?:\s+\w+){0,2}?\s+\w+s\s+(?:you|your)\b",
    re.IGNORECASE,
)

#: GATE 1, second signature: the classic agency verbs, caught even when an
#: adverb or an object separates them from the reader.
AGENT_VERBS = re.compile(
    r"\b(saturn|jupiter|rahu|ketu)\b\s+(?:\w+\s+){0,2}?"
    r"(tests|pulls|brings|forces|denies|blocks|punishes|rewards|strikes|drags|"
    r"pushes|takes|breaks|hurts|threatens|controls|rules|governs)\b",
    re.IGNORECASE,
)

#: GATE 1, third signature: the same claim in the passive, which is how it
#: reappears the moment the active form is banned.
PASSIVE_AGENT = re.compile(
    r"\b(?:you|your)\b[^.]{0,40}\bby (?:saturn|jupiter|rahu|ketu)\b", re.IGNORECASE
)

#: GATE 2's vocabulary. IDENTITY.md §7: never a warning the reader must pay to
#: resolve. A difficulty stated with no action IS that warning — it leaves the
#: reader with a problem and no move, which is the shape of a paid upsell even
#: when nothing is being sold.
ACTION_VERBS = {
    "use", "begin", "start", "push", "ask", "commit", "take", "make", "choose",
    "spend", "put", "lean", "match", "hold", "pick", "narrow", "protect",
    "reduce", "consolidate", "give", "move", "set", "repair", "sleep",
    "continue", "build", "state", "renegotiate", "get", "test", "deliver",
    "record", "rest", "finish", "agree", "complete", "raise", "prune",
    "guard", "read", "study", "travel", "accept", "widen", "offer", "decide",
    "separate", "automate", "produce", "enter", "slow", "check", "refuse",
    "prefer", "cultivate", "track", "close", "notice", "steer", "avoid",
    "expect", "rebuild", "treat", "stop", "examine", "enjoy", "select",
    "tighten", "price", "allow", "watch", "attend", "wait", "consider",
    "trim", "cut", "postpone", "plan", "write", "speak", "judge", "carry",
    "spread", "run",
    # `keep` is also a STOPWORD — the two sets answer different questions and
    # deliberately overlap. STOPWORDS excludes it from the SHARE count, where
    # it is a function word; here it is an imperative ("Keep your agreements
    # small") and is exactly the kind of move gate 2 exists to require.
    "keep",
}

#: GATE 3's vocabulary. An UNBOUNDED negative is the definition of dread: "what
#: you built may be tested" names no domain and no horizon, so there is nothing
#: the reader can check it against and nothing they can do when it is over —
#: because it is never over. A demanding line must name either a life domain
#: (WHAT is demanding) or a horizon (HOW LONG).
HORIZON_TOKENS = {
    "passage", "phase", "while", "until", "through", "here", "now", "run",
    "later", "before", "after", "still", "lasts", "holds", "period", "season",
    "ahead", "briefly", "moves", "present", "moment", "yet",
}

DOMAIN_TOKENS = {
    "money", "save", "saving", "savings", "price", "numbers", "home",
    "domestic", "household", "health", "routine", "routines", "service",
    "sleep", "work", "standing", "partnership", "agreements", "friends",
    "networks", "belief", "teachers", "creative", "creativity", "play",
    "learning", "effort", "footing", "identity", "appetite", "resources",
    "paperwork", "accounts", "obligations", "role", "commitments", "energy",
    "people", "relationships", "retreat", "expense", "reserves", "habit",
    "project", "client", "contest", "competition", "ambition", "attention",
    "connection", "circle", "food", "movement", "journeys", "plans", "output",
    "confidence", "nerve", "reasoning", "conclusions", "audience", "print",
    "quota", "structures", "standards", "standard", "moon", "room", "meeting",
    "offer", "proposal", "introduction", "raise", "difference", "load",
    "basics", "pace", "tempo", "finances", "promises", "maintenance",
    "traffic", "goodwill", "comfort", "capacity", "initiative", "enthusiasm",
    "release", "scale", "results", "questions", "review", "help", "scrutiny",
    "recognition", "gains", "life",
}

#: GATE 4. Separate from BANNED_WORDS on purpose: none of these is a forbidden
#: CLAIM (no fatalism, no promise, no diagnosis), which is exactly why the
#: existing list does not carry them. They are the vocabulary of ALARM, and
#: their only function in a transit reading is to make a real difficulty feel
#: larger than it is.
INTENSIFIERS = {
    "severe", "intense", "brutal", "harsh", "crushing", "relentless",
    "overwhelming", "devastating", "dire", "grim", "ordeal", "suffering",
    "torment", "misfortune", "calamity",
}

#: GATE 5's tolerances. Demanding copy may not run meaningfully longer or
#: denser than supportive copy FOR THE SAME MOVER — per mover, because the
#: movers have genuinely different supportive/demanding splits (Saturn 3/9,
#: Jupiter 5/7, Rahu 4/8) and pooling them would let one mover's balance mask
#: another's.
#:
#: The bounds are set from what the shipped corpus actually measures (worst
#: length ratio 1.028, worst density gap 0.050) with room for honest editing,
#: and are tight enough that the +40% falsification signature fires. Both
#: numbers are pinned in `test_symmetry_bounds_are_stated_not_derived` so a
#: later loosening is a visible decision rather than a quiet one.
SYMMETRY_LENGTH_TOLERANCE = 0.15   # |ratio - 1| may not exceed this
SYMMETRY_DENSITY_TOLERANCE = 0.10  # absolute difference in content-word share


# ─── loaders ─────────────────────────────────────────────────────────────────

def _load() -> dict:
    return json.loads(SEED_PATH.read_text())["transit"]


def _all_lines(data: dict) -> list[str]:
    out: list[str] = []
    for key_type in KEY_TYPES["transit"]:
        for cell in data[key_type].values():
            out.extend(cell["lines"])
    return out


def _content_words(line: str) -> set[str]:
    return set(G._words(line)) - G.STOPWORDS - TRANSIT_FRAME_WORDS


def _is_supportive(passage_key: str) -> bool:
    body, house = passage_key.split(".")
    return int(house) in SUPPORTIVE_HOUSES[body]


def _passage_lines(data: dict, body: str | None = None, supportive: bool | None = None):
    out = []
    for key, cell in data["passage"].items():
        if body is not None and key.split(".")[0] != body:
            continue
        if supportive is not None and _is_supportive(key) != supportive:
            continue
        out.extend(cell["lines"])
    return out


def demanding_lines(data: dict) -> list[str]:
    """Every line that speaks about difficulty — the work-list gates 2 and 3
    run over. Demanding passages, the demanding weather class, and ALL of
    sade_sati: a Sade Sati line is about a hard passage whichever key it
    carries, including the two that exist to say "this is not the hard thing"."""
    return (
        _passage_lines(data, supportive=False)
        + data["weather"]["demanding"]["lines"]
        + [ln for cell in data["sade_sati"].values() for ln in cell["lines"]]
    )


def check_word_share(data: dict) -> dict[str, int]:
    """Document frequency over the TRANSIT corpus's own lines — its own
    denominator, per the IDENTITY.md §6a lesson that a pooled denominator lets
    a larger corpus's headroom mask repetition in a smaller one."""
    lines = _all_lines(data)
    seen_in: Counter[str] = Counter()
    for line in lines:
        for word in _content_words(line):
            seen_in[word] += 1
    limit = G._share_limit(len(lines))
    return {w: n for w, n in seen_in.items() if n > limit and len(w) > 2}


# ─── structure ───────────────────────────────────────────────────────────────

def test_every_weather_class_has_exactly_the_declared_lines():
    data = _load()
    assert set(data["weather"]) == set(WEATHER_CLASSES)
    for cls, cell in data["weather"].items():
        assert len(cell["lines"]) == WEATHER_VARIANTS, cls
        assert len(set(cell["lines"])) == WEATHER_VARIANTS, f"{cls} repeats a line"


def test_every_mover_house_pair_is_authored_and_ketu_is_not():
    """36 cells, not 48. Ketu is always exactly six houses from Rahu — asserted
    over all 360 measured states by test_transits.py — so a Ketu cell would be
    a duplication rather than a gap. It is a position to RENDER, never a claim
    to author, and `build_transit_reading` renders it without a corpus row."""
    data = _load()
    expected = {f"{b}.{h}" for b in INDEPENDENT_MOVERS for h in range(1, 13)}
    assert set(data["passage"]) == expected
    assert len(expected) == 36
    assert not any(k.startswith("Ketu") for k in data["passage"])
    for key, cell in data["passage"].items():
        assert len(cell["lines"]) == 1, f"{key}: passage cells do not rotate (§ 6.8)"


def test_every_mover_phase_pair_is_authored():
    """Per MOVER, not shared. "Early in a Saturn passage" and "early in a
    Jupiter passage" are different amounts of time (2.5 years against about
    one) and want different tone, so a single early/middle/late triple would
    be saying one thing about three unlike spans."""
    data = _load()
    expected = {f"{b}.{p}" for b in INDEPENDENT_MOVERS for p in PHASES}
    assert set(data["phase"]) == expected
    for key, cell in data["phase"].items():
        assert len(cell["lines"]) == 1, key


def test_sade_sati_has_all_five_keys_including_the_two_that_are_not_phases():
    """`resuming` and `brief` are not classical phases and that is the point.
    `is_full_passage` distinguishes a real passage from a detached run, but it
    does NOT distinguish the two detached cases from each other — and they need
    opposite copy. Sagittarius' 189-day return after 2022-07-13 must read as
    "this is back"; Pisces' 73-day dip in 2022 must read as "this is not the
    thing you have heard about". One key could not carry both."""
    data = _load()
    assert set(data["sade_sati"]) == set(SADE_SATI_KEYS)
    assert set(SADE_SATI_PHASES.values()) < set(SADE_SATI_KEYS)
    for key, cell in data["sade_sati"].items():
        assert len(cell["lines"]) == 1, key


def test_transit_corpus_is_the_declared_size():
    """21 + 36 + 9 + 5 = 71. A count assertion catches a half-authored seed
    that every per-cell check above would pass one cell at a time — and it is
    the pin the vacuous-pass falsification signature fires against."""
    lines = _all_lines(_load())
    expected = (
        len(WEATHER_CLASSES) * WEATHER_VARIANTS
        + len(INDEPENDENT_MOVERS) * 12
        + len(INDEPENDENT_MOVERS) * len(PHASES)
        + len(SADE_SATI_KEYS)
    )
    assert len(lines) == expected == 71


def test_no_line_repeats_across_all_three_kinds():
    """Verbatim uniqueness over the whole seed file — 465 range-report lines
    plus 71 transit. The per-kind gates cannot see a transit line pasted from
    the weekly corpus, which is the laziest possible cross-kind collision."""
    lines = (
        G._all_lines(json.loads(SEED_PATH.read_text())["weekly"])
        + G._all_lines(json.loads(SEED_PATH.read_text())["monthly"])
        + _all_lines(_load())
    )
    assert len(lines) == 536
    dupes = [ln for ln, n in Counter(lines).items() if n > 1]
    assert dupes == [], f"repeated verbatim across kinds: {dupes}"


# ─── share ───────────────────────────────────────────────────────────────────

def test_transit_share_threshold_matches_the_spec():
    """int() truncation over the TRANSIT denominator: 71 * 0.06 = 4.26, so a
    word may sit in 4 lines and fails at 5. This is the tightest cap any corpus
    in the repo runs under, because 71 is the smallest denominator — which is
    the correct consequence of a small corpus, not a reason to pool it."""
    assert G._share_limit(71) == 4


def test_transit_no_content_word_dominates():
    offenders = check_word_share(_load())
    assert offenders == {}, f"over {G._share_limit(71)} lines: {offenders}"


def test_transit_frame_exemption_is_narrow():
    """`Saturn` may saturate; an ordinary content word at the same rate may not.

    Load-bearing in both directions, as in the weekly and monthly gates. The
    planet names genuinely do saturate — 15 of 71 lines carry `Saturn` — and
    without the exemption the corpus could not be written at all, so the
    exemption must be proved narrow rather than assumed so.
    """
    data = _load()
    assert check_word_share(data) == {}

    lines = _all_lines(data)
    saturny = sum(1 for ln in lines if set(G._words(ln)) & {"saturn", "saturn's"})
    assert saturny > G._share_limit(71), "fixture: 'saturn' should saturate the corpus"

    over = G._share_limit(len(lines)) + 1
    poisoned = json.loads(SEED_PATH.read_text())["transit"]
    keys = list(poisoned["passage"])
    for i in range(over):
        poisoned["passage"][keys[i]]["lines"][0] += " Momentum."
    assert "momentum" in check_word_share(poisoned)


# ─── distinctness ────────────────────────────────────────────────────────────

def test_no_two_transit_lines_share_a_frame():
    data = _load()
    seen: dict[str, str] = {}
    for line in _all_lines(data):
        frame = G._frame(line)
        assert frame not in seen, f"shared frame {frame!r}:\n  {line}\n  {seen[frame]}"
        seen[frame] = line


def test_no_two_transit_lines_share_a_skeleton():
    data = _load()
    seen: dict[str, str] = {}
    for line in _all_lines(data):
        if len(G._words(line)) < 6:
            continue
        skel = G._skeleton(line)
        assert skel not in seen, f"shared skeleton:\n  {line}\n  {seen[skel]}"
        seen[skel] = line


# ─── safety: the gates every corpus runs ─────────────────────────────────────

def test_transit_no_banned_vocabulary():
    offenders = [
        (ln, sorted(set(G._words(ln)) & G.BANNED_WORDS))
        for ln in _all_lines(_load())
        if set(G._words(ln)) & G.BANNED_WORDS
    ]
    assert offenders == [], offenders


@pytest.mark.parametrize("pattern", G.FORTUNE_PATTERNS)
def test_transit_no_outcome_promises(pattern):
    rx = re.compile(pattern, re.IGNORECASE)
    offenders = [ln for ln in _all_lines(_load()) if rx.search(ln)]
    assert offenders == [], f"{pattern}: {offenders}"


def test_transit_every_line_is_second_person_or_impersonal_never_third():
    rx = re.compile(r"\b(he|she|his|hers)\b", re.IGNORECASE)
    offenders = [ln for ln in _all_lines(_load()) if rx.search(ln)]
    assert offenders == [], offenders


def test_transit_lines_are_within_length_bounds():
    for ln in _all_lines(_load()):
        n = len(G._words(ln))
        assert 8 <= n <= 40, f"{n} words: {ln!r}"


# ─── FEAR GATE 1: no planet may act on the reader ────────────────────────────

@pytest.mark.parametrize(
    "rx,label",
    [(AGENT_ADJACENT, "adjacent"), (AGENT_VERBS, "agency verb"), (PASSIVE_AGENT, "passive")],
)
def test_no_planet_acts_on_the_reader(rx, label):
    """A planet may be where it is; it may not be doing something to you.

    "Saturn stands in your tenth" is a position — checkable, and true or false
    of the sky. "Saturn tests you" is a claim about causation that this product
    has no mechanism to support and that the voice specs forbid outright. Both
    are built from permitted words, so only the grammar separates them.
    """
    lines = _all_lines(_load())
    assert len(lines) == 71, "work-list short — the pass would be vacuous"
    offenders = [ln for ln in lines if rx.search(ln)]
    assert offenders == [], f"{label}: {offenders}"


# ─── FEAR GATE 2: every demanding line carries an action ─────────────────────

def test_every_demanding_line_carries_an_action():
    """IDENTITY.md §7: never a warning the reader must pay to resolve.

    A difficulty stated with no move IS that warning — it hands the reader a
    problem and no handle, which is the shape of an upsell whether or not
    anything is for sale. This is the gate that most directly separates a
    guidance product from a fear product.
    """
    lines = demanding_lines(_load())
    assert len(lines) == 24 + 7 + 5, "work-list short — the pass would be vacuous"
    offenders = [ln for ln in lines if not set(G._words(ln)) & ACTION_VERBS]
    assert offenders == [], offenders


# ─── FEAR GATE 3: every demanding line is bounded ────────────────────────────

def test_every_demanding_line_is_bounded():
    """An unbounded negative is the definition of dread.

    "What you built may be tested in ways that are not immediately obvious"
    names no domain and no horizon, so there is nothing to check it against and
    no point at which it ends. Every demanding line must say WHAT (a life
    domain) or HOW LONG (a horizon) — the difference between weather to dress
    for and a threat.
    """
    lines = demanding_lines(_load())
    assert lines, "work-list empty — the pass would be vacuous"
    offenders = [
        ln
        for ln in lines
        if not (set(G._words(ln)) & DOMAIN_TOKENS or set(G._words(ln)) & HORIZON_TOKENS)
    ]
    assert offenders == [], offenders


# ─── FEAR GATE 4: no intensifiers ────────────────────────────────────────────

def test_no_intensifiers_anywhere_in_the_transit_corpus():
    """Applied to the WHOLE corpus, not only the demanding half: an intensifier
    in a supportive line is the same inflation pointed the other way, and it
    would also skew gate 5's baseline in the direction that hides fear."""
    lines = _all_lines(_load())
    assert len(lines) == 71
    offenders = [
        (ln, sorted(set(G._words(ln)) & INTENSIFIERS))
        for ln in lines
        if set(G._words(ln)) & INTENSIFIERS
    ]
    assert offenders == [], offenders


# ─── FEAR GATE 5: the symmetry gate — the one that cannot be gamed ───────────

def symmetry_stats(data: dict, body: str) -> dict[str, float]:
    """Mean line length and mean content-word density, demanding vs supportive,
    for one mover. Returned rather than asserted so the falsification suite can
    measure the same numbers on a poisoned corpus."""
    dem = _passage_lines(data, body=body, supportive=False)
    sup = _passage_lines(data, body=body, supportive=True)
    assert dem and sup, f"{body}: empty side — the comparison would be vacuous"

    def length(ls):
        return sum(len(G._words(x)) for x in ls) / len(ls)

    def density(ls):
        return sum(len(_content_words(x)) / len(G._words(x)) for x in ls) / len(ls)

    return {
        "length_ratio": length(dem) / length(sup),
        "density_gap": abs(density(dem) - density(sup)),
        "n_demanding": len(dem),
        "n_supportive": len(sup),
    }


@pytest.mark.parametrize("body", INDEPENDENT_MOVERS)
def test_demanding_and_supportive_copy_are_statistically_comparable(body):
    """THE GATE THAT CANNOT BE GAMED BY WORD CHOICE.

    Gates 1-4 are patterns over vocabulary and grammar, and a careful author
    can satisfy all four while still writing dread — the § 6.6 example does
    exactly that with zero banned words. What that author cannot do is write
    dread without SPENDING MORE WORDS ON IT. Fear-selling has a measurable
    signature at the library level: the hard copy runs longer and denser than
    the easy copy, because vividness costs words.

    So this compares the two halves per mover and requires them to be
    statistically alike. It is the transit analogue of the share cap — a fact
    about the corpus that no individual line reveals — and the falsification
    suite proves it fires on copy that passes gates 1-4 completely.

    Per mover rather than pooled: the splits differ (Saturn 3 supportive to 9,
    Jupiter 5 to 7, Rahu 4 to 8), and pooling would let one mover's balance
    mask another's inflation.
    """
    stats = symmetry_stats(_load(), body)
    assert abs(stats["length_ratio"] - 1) <= SYMMETRY_LENGTH_TOLERANCE, (
        f"{body}: demanding/supportive mean length ratio {stats['length_ratio']:.3f} "
        f"({stats['n_demanding']} demanding vs {stats['n_supportive']} supportive) — "
        "hard copy is running longer than easy copy, which is what fear-selling "
        "measures like"
    )
    assert stats["density_gap"] <= SYMMETRY_DENSITY_TOLERANCE, (
        f"{body}: content-word density gap {stats['density_gap']:.3f} — "
        "hard copy is running denser than easy copy"
    )


def test_symmetry_bounds_are_stated_not_derived():
    """The tolerances are a decision, so they are pinned as one.

    Measured on the shipped corpus: worst length ratio 1.028, worst density gap
    0.050. The bounds sit above that with editing room and below the +40%
    inflation signature the falsification suite fires. Loosening them should
    require changing this line, which makes it an argument rather than a drift.
    """
    assert SYMMETRY_LENGTH_TOLERANCE == 0.15
    assert SYMMETRY_DENSITY_TOLERANCE == 0.10
    data = _load()
    for body in INDEPENDENT_MOVERS:
        s = symmetry_stats(data, body)
        assert abs(s["length_ratio"] - 1) < 0.05, (body, s)
        assert s["density_gap"] < 0.06, (body, s)
