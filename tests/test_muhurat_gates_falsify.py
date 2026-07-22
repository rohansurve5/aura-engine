"""Falsification battery for the muhurat VOICE — the §3 anti-fear-selling gates.

Muhurat's failure mode is superstition-selling: implying HARM from acting
outside an auspicious window. Rahu kaal is the single most weaponised timing in
this market — used to frighten people out of acting. The A5/transit/compatibility
work proved dread is CONSTRUCTIBLE FROM PERMITTED WORDS, so a vocabulary scan
cannot see it. This file, exactly like tests/test_compatibility_gates_falsify.py,
mutates a deep copy of the REAL shipped corpus (engine.muhurat.DESCRIPTORS),
calls the ACTUAL gate function, and pairs every red with a green.

Five gates, escalating as the compatibility battery does:
  A. no harm-verdict vocabulary (the ordinary scan);
  B. every kaal line is FRAMED (one tradition's), keeps AGENCY, and promises no
     outcome — the fatalism gate that catches dread built from ordinary words;
  C. the inauspicious band is reported as agentively as the auspicious one;
  D. THE SYMMETRY GATE — the inauspicious band may not read heavier than the
     auspicious band (length + density), the signature a vocabulary scan cannot
     see; and
  E. Rahu Kaal — the most weaponised line — always carries the explicit
     'not a warning of harm' clause.
"""

from __future__ import annotations

import copy
import re

import pytest

import engine.muhurat as M

WORD_RE = re.compile(r"[a-z']+")
STOP = frozenset(
    "a an the it is as of and or to in on at rather than not one this here they "
    "you your for be with into so we do does that these those but every".split()
)


def _words(s: str) -> list[str]:
    return WORD_RE.findall(s.lower())


def _content(s: str) -> list[str]:
    return [w for w in _words(s) if w not in STOP]


def _density(s: str) -> float:
    w = _words(s)
    return len(_content(s)) / len(w) if w else 0.0


def _data() -> dict:
    return copy.deepcopy(M.DESCRIPTORS)


def _all_lines(data: dict) -> list[str]:
    return list(data["band"].values()) + list(data["kaal"].values())


# ── vacuous-pass guard: the corpus is the declared size ─────────────────────
def test_descriptor_corpus_is_the_declared_size():
    assert set(M.DESCRIPTORS["band"]) == {"auspicious", "inauspicious"}
    assert set(M.DESCRIPTORS["kaal"]) == {"Rahu Kaal", "Gulika Kaal", "Yamaganda"}
    assert set(M.DESCRIPTORS["personalisation"]) == {"impersonal", "personal_12way"}


# ── GATE A: no harm-verdict vocabulary ──────────────────────────────────────
def check_no_verdict_words(data: dict) -> dict:
    offenders = {}
    for line in _all_lines(data):
        low = line.lower()
        for phrase in M.VERDICT_WORDS:
            if phrase in low:
                offenders[line] = phrase
    return offenders


def test_no_verdict_vocabulary_in_the_shipped_corpus():
    assert check_no_verdict_words(M.DESCRIPTORS) == {}


@pytest.mark.parametrize(
    "phrase", ["cursed", "will fail", "disaster", "never begin", "brings misfortune"]
)
def test_verdict_gate_fires(phrase):
    data = _data()
    data["kaal"]["Rahu Kaal"] = f"Rahu Kaal is {phrase} — do not act."
    assert check_no_verdict_words(data)
    assert check_no_verdict_words(M.DESCRIPTORS) == {}


# ── GATE B: every kaal line is framed, keeps agency, promises no outcome ─────
def check_kaal_lines_are_framed_and_agentive(data: dict) -> list[str]:
    bad = []
    for key, line in data["kaal"].items():
        low = line.lower()
        if not M.FRAME.search(low) or not M.AGENCY.search(low) or M.OUTCOME.search(low):
            bad.append(key)
    return bad


def test_every_shipped_kaal_line_is_framed_and_agentive():
    assert check_kaal_lines_are_framed_and_agentive(M.DESCRIPTORS) == []


@pytest.mark.parametrize(
    "planted,label",
    [
        ("Rahu Kaal is a period that harms any venture begun in it.",
         "consequence stated as fact — permitted words, no frame, no agency"),
        ("Starting during Gulika Kaal leads to loss and setback for the work.",
         "outcome promise built from ordinary words"),
        ("Acting in Yamaganda brings failure to the new undertaking over time.",
         "the fear line a vocabulary scan cannot see"),
    ],
)
def test_kaal_fatalism_gate_fires(planted, label):
    """Each planted line carries zero VERDICT_WORDS — gate A passes it — yet each
    is exactly the superstition-selling this product must never ship. Gate B sees
    the stated consequence."""
    assert check_no_verdict_words({"band": {}, "kaal": {"X": planted}}) == {}, label
    data = _data()
    data["kaal"]["Rahu Kaal"] = planted
    assert "Rahu Kaal" in check_kaal_lines_are_framed_and_agentive(data), label
    assert check_kaal_lines_are_framed_and_agentive(M.DESCRIPTORS) == []


# ── GATE C: the inauspicious band keeps agency as the auspicious one does ────
NONVERDICT = re.compile(r"not a rule|rather than a rule|many good things|one tradition")


def check_inauspicious_band_keeps_agency(data: dict) -> bool:
    return bool(NONVERDICT.search(data["band"]["inauspicious"].lower()))


def test_inauspicious_band_carries_the_non_verdict_signal():
    assert check_inauspicious_band_keeps_agency(M.DESCRIPTORS)


def test_inauspicious_band_gate_fires_on_a_bare_bad_hour():
    data = _data()
    data["band"]["inauspicious"] = "A bad window. Avoid starting anything now."
    assert not check_inauspicious_band_keeps_agency(data)
    assert check_inauspicious_band_keeps_agency(M.DESCRIPTORS)


# ── GATE D: THE SYMMETRY GATE — bad news may not read heavier than good ──────
# Same-kind comparison: the INAUSPICIOUS band against the AUSPICIOUS band.
# Fear-selling makes the bad-news line longer and/or denser; reassurance is
# function-word heavy, so it moves length mildly and density not at all.
SYMMETRY_LENGTH_TOLERANCE = 0.35
SYMMETRY_DENSITY_TOLERANCE = 0.18


def symmetry_stats(data: dict) -> dict:
    good, bad = data["band"]["auspicious"], data["band"]["inauspicious"]
    g_len, b_len = len(_words(good)), len(_words(bad))
    assert g_len and b_len, "a band line is empty — ratio undefined"
    return {"length_ratio": b_len / g_len, "density_gap": _density(bad) - _density(good)}


def test_symmetry_gate_passes_on_the_shipped_corpus():
    s = symmetry_stats(M.DESCRIPTORS)
    assert s["length_ratio"] <= 1 + SYMMETRY_LENGTH_TOLERANCE, s
    assert s["density_gap"] <= SYMMETRY_DENSITY_TOLERANCE, s


def _inflate(line: str, factor: float = 0.4) -> str:
    """Grow a line with ONLY permitted words already present in the corpus — the
    dread no vocabulary gate can see."""
    padding = [
        "This is a period many readers weigh with care in the tradition.",
        "It is a customary pause that some families still treat as important.",
        "The timing is one many almanacs still print in bold for the day.",
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
    """THE DECISIVE SIGNATURE. Inflate the inauspicious band 40% with permitted
    words. Gate A stays green; the symmetry measurement catches it."""
    data = _data()
    data["band"]["inauspicious"] = _inflate(M.DESCRIPTORS["band"]["inauspicious"], 0.4)
    assert check_no_verdict_words(data) == {}
    s = symmetry_stats(data)
    assert s["length_ratio"] > 1 + SYMMETRY_LENGTH_TOLERANCE, s


def test_symmetry_gate_also_fires_on_density_alone():
    data = _data()
    heavy = " ".join(["danger", "risk", "loss", "setback", "failure", "misfortune"] * 5)
    data["band"]["inauspicious"] = heavy
    s = symmetry_stats(data)
    assert s["density_gap"] > SYMMETRY_DENSITY_TOLERANCE, s


def test_symmetry_stats_refuses_an_empty_side():
    data = _data()
    data["band"]["inauspicious"] = ""
    with pytest.raises(AssertionError):
        symmetry_stats(data)


# ── GATE E: Rahu Kaal always carries the explicit non-harm clause ───────────
NON_HARM_CLAUSE = re.compile(r"not a warning|not a warning of harm|customary pause")


def check_rahu_is_defused(data: dict) -> bool:
    return bool(NON_HARM_CLAUSE.search(data["kaal"]["Rahu Kaal"].lower()))


def test_rahu_kaal_is_defused_in_the_shipped_corpus():
    assert check_rahu_is_defused(M.DESCRIPTORS)


def test_rahu_gate_fires_when_it_loses_its_clause():
    data = _data()
    data["kaal"]["Rahu Kaal"] = (
        "Rahu Kaal: a period counted from sunrise by the weekday, which many "
        "traditions set aside for beginnings. Plenty is done in these hours."
    )
    # Still framed + agentive (gate B green) and carries no banned word (gate A
    # green) — but it dropped the explicit 'not a warning of harm' clause.
    assert "Rahu Kaal" not in check_kaal_lines_are_framed_and_agentive(data)
    assert check_no_verdict_words(data) == {}
    assert not check_rahu_is_defused(data)
    assert check_rahu_is_defused(M.DESCRIPTORS)


# ── the describe_timings output obeys every gate (the code, not just the seed) ─
def test_describe_timings_output_passes_the_full_battery():
    """Compose a real reading and assert the emitted lines carry no verdict word
    and no outcome promise — proving the gates guard the SHIPPED path."""
    windows = [
        ("Amrit", None, None, 4), ("Shubh", None, None, 7), ("Labh", None, None, 1),
    ]
    # rank_windows needs datetimes for sorting; give trivial distinct ones.
    from datetime import datetime, timedelta
    windows = [
        (nm, datetime(2026, 7, 21) + timedelta(hours=i), None, lag)
        for i, (nm, _, _, lag) in enumerate(windows)
    ]
    result = M.rank_windows(windows, set(), "start", natal_lagna_sign=4)
    reading = M.describe_timings(result)
    joined = " ".join(reading["lines"]).lower()
    for phrase in M.VERDICT_WORDS:
        assert phrase not in joined
    assert not M.OUTCOME.search(joined)
    assert reading["personalisation"] == "personal_12way"
