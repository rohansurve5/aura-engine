"""Falsification battery for the compatibility VOICE — the central-risk gates.

Compatibility is where astrology does the most real-world harm: matches called
off over Nadi dosha, people told they are "manglik" and unmarriageable. The
binding voice rules forbid fatalism and fear-selling, and the A5/transit gates
proved dread is CONSTRUCTIBLE FROM PERMITTED WORDS — a vocabulary scan cannot
see it. So this file, like tests/test_transit_content_seed's fear gates, mutates
a deep copy of the REAL shipped corpus (`engine.compatibility.DESCRIPTORS`),
calls the ACTUAL gate function, and pairs every red with a green.

Five gates, escalating exactly as the transit battery does:
  A. no verdict vocabulary (the ordinary scan);
  B. every dosha line is FRAMED (one tradition's marker), keeps the reader's
     AGENCY, and makes no outcome promise — the fatalism gate;
  C. the low tally is reported as honestly as the high one (non-verdict signal);
  D. THE SYMMETRY GATE — the bad-news band may not read heavier than the
     good-news band, caught by a measurement even when every added word is
     permitted (the signature a vocabulary scan structurally cannot see); and
  E. the two biggest harm vectors — Nadi and Mangal — carry an explicit
     'not a verdict on anyone's future' clause, always.
"""

from __future__ import annotations

import copy
import re

import pytest

import engine.compatibility as C

WORD_RE = re.compile(r"[a-z']+")
# A minimal function-word set: reassurance is function-word heavy ("it is one
# tradition's count rather than a verdict, and many..."), so density built on
# this set does NOT rise on reassurance but DOES rise on piled-on content.
STOP = frozenset(
    "a an the it is as of and or to in on at rather than not one this here they "
    "you your for be with into so we do does that these those but".split()
)


def _words(s: str) -> list[str]:
    return WORD_RE.findall(s.lower())


def _content(s: str) -> list[str]:
    return [w for w in _words(s) if w not in STOP]


def _density(s: str) -> float:
    w = _words(s)
    return len(_content(s)) / len(w) if w else 0.0


def _data() -> dict:
    return copy.deepcopy(C.DESCRIPTORS)


def _all_lines(data: dict) -> list[str]:
    return list(data["band"].values()) + list(data["dosha"].values())


# ── vacuous-pass guard: the corpus is the declared size ─────────────────────
def test_descriptor_corpus_is_the_declared_size():
    """Every gate below iterates this corpus; if it were empty they would pass
    having examined nothing. Pin the shape first."""
    assert set(C.DESCRIPTORS["band"]) == {"high", "mid", "low"}
    assert set(C.DESCRIPTORS["dosha"]) == {"Nadi", "Bhakoot", "Yoni", "Mangal"}


# ── GATE A: no verdict vocabulary ────────────────────────────────────────────
def check_no_verdict_words(data: dict) -> dict:
    """A decree ends the reader's agency ('incompatible', 'should not marry',
    'avoid this match'). Return {line: offending_phrase}."""
    offenders = {}
    for line in _all_lines(data):
        low = line.lower()
        for phrase in C.VERDICT_WORDS:
            if phrase in low:
                offenders[line] = phrase
    return offenders


def test_no_verdict_vocabulary_in_the_shipped_corpus():
    assert check_no_verdict_words(C.DESCRIPTORS) == {}


@pytest.mark.parametrize(
    "phrase", ["incompatible", "should not marry", "avoid", "unmarriageable", "will divorce"]
)
def test_verdict_gate_fires(phrase):
    data = _data()
    data["dosha"]["Nadi"] = f"This match is {phrase} in the tradition, full stop."
    assert check_no_verdict_words(data)
    # ...and green on the real, unmutated corpus.
    assert check_no_verdict_words(C.DESCRIPTORS) == {}


# ── GATE B: every dosha line is framed, keeps agency, promises no outcome ────
FRAME = re.compile(r"\btradition")
AGENCY = re.compile(
    r"not a barrier|not fate|not a ruling|not the last word|to discuss|"
    r"conversation|among the eight|set it aside|rather than a"
)
# Outcome promises: a dosha stating a CONSEQUENCE ("harms health", "leads to
# separation", "will suffer"). The fatalism a vocabulary scan misses because the
# words are ordinary.
OUTCOME = re.compile(
    r"\b(harms?|damages?|ruins?|destroys?|causes?|leads? to|results? in|"
    r"ends? in|will (?:suffer|fail|break|part)|prevents?)\b"
)


def check_dosha_lines_are_framed_and_agentive(data: dict) -> list[str]:
    """Return the dosha keys whose line fails to (a) frame the marker as one
    tradition's, (b) preserve the reader's agency, and (c) promise no outcome."""
    bad = []
    for key, line in data["dosha"].items():
        low = line.lower()
        if not FRAME.search(low) or not AGENCY.search(low) or OUTCOME.search(low):
            bad.append(key)
    return bad


def test_every_shipped_dosha_line_is_framed_and_agentive():
    assert check_dosha_lines_are_framed_and_agentive(C.DESCRIPTORS) == []


@pytest.mark.parametrize(
    "planted,label",
    [
        ("Both charts share the same nadi, which harms health and the children.",
         "consequence stated as fact — no frame, no agency"),
        ("The moon signs sit in a hard count and this leads to household discord.",
         "outcome promise with permitted words"),
        ("Mars sits in a marked house and this damages the marriage over time.",
         "the manglik dread line, entirely permitted vocabulary"),
    ],
)
def test_dosha_fatalism_gate_fires(planted, label):
    """Each planted line carries zero VERDICT_WORDS — gate A passes it — yet each
    is exactly the fatalism this product must never ship. Only gate B sees it."""
    assert check_no_verdict_words({"band": {}, "dosha": {"X": planted}}) == {}, label
    data = _data()
    data["dosha"]["Nadi"] = planted
    assert "Nadi" in check_dosha_lines_are_framed_and_agentive(data), label
    # green on the real corpus
    assert check_dosha_lines_are_framed_and_agentive(C.DESCRIPTORS) == []


# ── GATE C: the low tally is reported as honestly as the high one ───────────
NONVERDICT = re.compile(r"not a verdict|rather than a verdict|many close bonds|one tradition")


def check_low_band_keeps_agency(data: dict) -> bool:
    return bool(NONVERDICT.search(data["band"]["low"].lower()))


def test_low_band_carries_the_non_verdict_signal():
    assert check_low_band_keeps_agency(C.DESCRIPTORS)


def test_low_band_gate_fires_on_a_bare_poor_match():
    data = _data()
    data["band"]["low"] = "A low score. This is a poor match by the numbers."
    assert not check_low_band_keeps_agency(data)
    assert check_low_band_keeps_agency(C.DESCRIPTORS)


# ── GATE D: THE SYMMETRY GATE — bad news may not read heavier than good ──────
# Same-kind comparison: the LOW band (bad news) against the HIGH band (good
# news). Fear-selling makes the bad-news line longer and/or denser. Reassurance
# ("it is one tradition's count rather than a verdict") is function-word heavy,
# so it moves length only mildly and density not at all — the shipped low band
# passes with margin, a dread-inflated one does not.
SYMMETRY_LENGTH_TOLERANCE = 0.35   # low may be up to 35% longer than high
SYMMETRY_DENSITY_TOLERANCE = 0.18  # ...and no denser than high by > 0.18


def symmetry_stats(data: dict) -> dict:
    high, low = data["band"]["high"], data["band"]["low"]
    hi_len, lo_len = len(_words(high)), len(_words(low))
    assert hi_len and lo_len, "a band line is empty — ratio undefined"
    return {
        "length_ratio": lo_len / hi_len,
        "density_gap": _density(low) - _density(high),
    }


def test_symmetry_gate_passes_on_the_shipped_corpus():
    s = symmetry_stats(C.DESCRIPTORS)
    assert s["length_ratio"] <= 1 + SYMMETRY_LENGTH_TOLERANCE, s
    assert s["density_gap"] <= SYMMETRY_DENSITY_TOLERANCE, s


def _inflate(line: str, factor: float = 0.4) -> str:
    """Grow a line by ~factor using ONLY words already permitted and present in
    the shipped corpus — the dread that no vocabulary gate can see."""
    padding = [
        "This is a marker some readers weigh heavily in the tradition.",
        "It can shape health and children and the household for years.",
        "The count is one many families still treat as a serious concern.",
    ]
    target = int(len(_words(line)) * factor)
    added, i, parts = 0, 0, [line]
    while added < target:
        frag = padding[i % len(padding)]
        parts.append(frag)
        added += len(_words(frag))
        i += 1
    return " ".join(parts)


def test_symmetry_gate_fires_on_permitted_word_inflation():
    """THE DECISIVE SIGNATURE. Inflate the low band 40% with permitted words.
    Gate A stays green (no banned word); the symmetry measurement catches it."""
    data = _data()
    data["band"]["low"] = _inflate(C.DESCRIPTORS["band"]["low"], 0.4)
    # Gate A cannot see it:
    assert check_no_verdict_words(data) == {}
    # Gate D can:
    s = symmetry_stats(data)
    assert s["length_ratio"] > 1 + SYMMETRY_LENGTH_TOLERANCE, s


def test_symmetry_gate_also_fires_on_density_alone():
    """Same length, heavier words — the author who knows the length check swaps
    function words for content words."""
    data = _data()
    heavy = " ".join(["dosha", "danger", "risk", "concern", "flaw", "problem"] * 5)
    data["band"]["low"] = heavy
    s = symmetry_stats(data)
    assert s["density_gap"] > SYMMETRY_DENSITY_TOLERANCE, s


def test_symmetry_stats_refuses_an_empty_side():
    data = _data()
    data["band"]["low"] = ""
    with pytest.raises(AssertionError):
        symmetry_stats(data)


# ── GATE E: Nadi & Mangal always carry the non-verdict clause ────────────────
FUTURE_CLAUSE = re.compile(r"not a barrier|not a ruling|not fate|not the last word")


def check_harm_vectors_are_defused(data: dict) -> list[str]:
    """Nadi and Mangal are the two lines most weaponised in this market. Each
    must carry an explicit 'not a verdict on the future' clause — not merely
    avoid banned words."""
    return [k for k in ("Nadi", "Mangal") if not FUTURE_CLAUSE.search(data["dosha"][k].lower())]


def test_harm_vectors_are_defused_in_the_shipped_corpus():
    assert check_harm_vectors_are_defused(C.DESCRIPTORS) == []


def test_harm_vector_gate_fires_when_mangal_loses_its_clause():
    data = _data()
    data["dosha"]["Mangal"] = (
        "Mangal: Mars sits in one of the houses this tradition marks. "
        "It is a marker to discuss together, and traditional exceptions can set it aside."
    )
    # It still frames + keeps agency (gate B green) and carries no banned word
    # (gate A green) — but it dropped the explicit non-verdict clause.
    assert "Mangal" not in check_dosha_lines_are_framed_and_agentive(data)
    assert check_no_verdict_words(data) == {}
    assert "Mangal" in check_harm_vectors_are_defused(data)
    assert check_harm_vectors_are_defused(C.DESCRIPTORS) == []


# ── the describe_match output obeys every gate (the code, not just the seed) ─
def test_describe_match_output_passes_the_full_battery():
    """Compose a real reading with two doshas and Mangal, and assert the actual
    emitted lines carry no verdict word and no outcome promise — proving the
    gates guard the SHIPPED path, not only the static corpus."""
    from datetime import datetime

    from engine.chart import chart_from_local

    arc = 13 + 20 / 60
    # Aries x Scorpio double-dosha pair from the golden, plus a Mangal chart.
    g = C.Person(1 * arc + 0.5 * arc / 4)
    b = C.Person(16 * arc + 1.5 * arc / 4)
    chart = chart_from_local(datetime(1989, 9, 23, 4, 47), "+05:30", 22.57, 88.36)
    reading = C.describe_match(g, b, mangal=C.mangal_dosha(chart))
    joined = " ".join(reading["lines"]).lower()
    for phrase in C.VERDICT_WORDS:
        assert phrase not in joined
    assert not OUTCOME.search(joined)
    assert reading["total"] == sum(k["got"] for k in reading["kootas"])
