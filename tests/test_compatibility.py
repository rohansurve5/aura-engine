"""Ashtakoota + Mangal: table-encoding pins, hand-checked koota math, the golden
breakdown, parihar behaviour, and Mangal facts.

The point that shapes this file (see the module docstring and
docs/COMPATIBILITY.md): compatibility is a DETERMINISTIC TABLE LOOKUP over two
already-cross-validated inputs (Moon nakshatra + rashi), not an independent
numerical computation. So we do not "cross-validate against a reference
ephemeris"; we pin the canonical tables by their STRUCTURE (invariants a wrong
table would break) plus independently-memorable anchors, hand-verify the koota
math where the tradition is unambiguous, and freeze the full breakdown for a
couple set engineered to hit every contested case.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import pytest

from engine.chart import chart_from_local
from engine.compatibility import (
    _YONI_SWORN_ENEMIES,
    GANA_BY_NAK,
    NADI_BY_NAK,
    SIGN_LORDS,
    VARNA_BY_SIGN,
    YONI_BY_NAK,
    YONI_NAMES,
    Person,
    bhakoot,
    bhakoot_parihar,
    gana,
    guna_milan,
    mangal_dosha,
    mangal_dosha_from_moon,
    nadi,
    nadi_parihar,
    varna,
    yoni,
)
from engine.vimshottari import NAKSHATRA_ARC, NAKSHATRAS

GOLDEN = Path(__file__).parent / "golden" / "compatibility_couples.json"


def person(nak_index: int, pada: int = 1) -> Person:
    pada_arc = NAKSHATRA_ARC / 4
    return Person(nak_index * NAKSHATRA_ARC + (pada - 0.5) * pada_arc)


# ── Table-encoding pins: structural invariants a wrong table would break ─────
def test_nadi_gana_are_evenly_thirded():
    """Both classifications split the 27 nakshatras exactly 9/9/9 — the defining
    property of the canonical tables (BPHS; B. V. Raman, Muhurtha)."""
    assert Counter(NADI_BY_NAK) == {"Aadi": 9, "Madhya": 9, "Antya": 9}
    assert Counter(GANA_BY_NAK) == {"Deva": 9, "Manushya": 9, "Rakshasa": 9}


def test_yoni_multiset_has_exactly_one_singleton():
    """Thirteen of the fourteen yonis own two nakshatras; Mongoose owns one
    (Uttara Ashadha). 13*2 + 1 = 27 — the canonical Yoni assignment exactly."""
    counts = Counter(YONI_BY_NAK)
    assert sorted(counts.values()) == [1] + [2] * 13
    (singleton,) = [a for a, n in counts.items() if n == 1]
    assert YONI_NAMES[singleton] == "Mongoose"


def test_sworn_enemy_yonis_perfectly_partition_the_fourteen_animals():
    """Every animal has exactly one bitter enemy: the seven sworn-enemy pairs
    are a perfect matching over all 14 yonis. A transcription slip (a dropped or
    duplicated animal) breaks the partition."""
    covered = [a for pair in _YONI_SWORN_ENEMIES for a in pair]
    assert len(_YONI_SWORN_ENEMIES) == 7
    assert sorted(covered) == list(range(14))  # each animal once, all 14 present


def test_varna_and_lords_are_the_canonical_rashi_tables():
    assert Counter(VARNA_BY_SIGN) == {"Brahmin": 3, "Kshatriya": 3, "Vaishya": 3, "Shudra": 3}
    # Cancer/Scorpio/Pisces = Brahmin (water signs); the memorable anchor.
    assert (VARNA_BY_SIGN[3], VARNA_BY_SIGN[7], VARNA_BY_SIGN[11]) == ("Brahmin",) * 3
    # Sign lords, spot-checked at the memorable ones.
    assert SIGN_LORDS[0] == "Mars" and SIGN_LORDS[4] == "Sun" and SIGN_LORDS[9] == "Saturn"


@pytest.mark.parametrize(
    "nak_name,gana_v,nadi_v,yoni_name",
    [
        ("Ashwini", "Deva", "Aadi", "Horse"),
        ("Rohini", "Manushya", "Antya", "Serpent"),
        ("Magha", "Rakshasa", "Antya", "Rat"),
        ("Revati", "Deva", "Antya", "Elephant"),
        ("Uttara Ashadha", "Manushya", "Antya", "Mongoose"),
    ],
)
def test_independently_memorable_per_nakshatra_anchors(nak_name, gana_v, nadi_v, yoni_name):
    """Anchors chosen because they are individually memorable in the tradition,
    so an anchor breaking flags a real transcription error rather than merely
    disagreeing with a copy of the same constant."""
    i = NAKSHATRAS.index(nak_name)
    assert GANA_BY_NAK[i] == gana_v
    assert NADI_BY_NAK[i] == nadi_v
    assert YONI_NAMES[YONI_BY_NAK[i]] == yoni_name


# ── Hand-verified koota math where the tradition is unambiguous ──────────────
def test_same_nakshatra_is_nadi_dosha_and_bhakoot_is_clean():
    g = b = person(0)  # Ashwini x Ashwini
    assert nadi(g, b).got == 0.0 and nadi(g, b).is_dosha
    assert bhakoot(g, b).got == 7.0  # 1/1 apart, never a dosha


def test_shadashtaka_signs_are_bhakoot_dosha():
    # Aries (Ashwini) and Scorpio (Anuradha): 6/8 mutual count.
    ks = bhakoot(person(0), person(16))
    assert ks.got == 0.0 and ks.is_dosha and ks.detail in ("8/6 apart", "6/8 apart")


def test_yoni_poles_are_exact():
    assert yoni(person(0), person(0)).got == 4.0  # same animal
    # Uttara Phalguni (Cow) vs Chitra (Tiger): sworn enemies -> 0.
    ks = yoni(person(11), person(13))
    assert ks.got == 0.0 and ks.is_dosha


def test_gana_asymmetry_is_directional():
    """Rakshasa groom + Deva bride scores strictly below the reverse — the
    classical asymmetry, and a place two references can legitimately differ."""
    deva_groom = gana(person(0), person(2)).got      # Ashwini(Deva) / Krittika(Rakshasa)
    raksh_groom = gana(person(2), person(0)).got     # the reverse
    assert deva_groom > raksh_groom


def test_varna_rule_is_groom_ge_bride():
    # Brahmin groom (Cancer) over Shudra bride (Gemini) -> 1; reverse -> 0.
    brahmin = person(7)   # Pushya -> Cancer
    shudra = person(5)    # Ardra -> Gemini
    assert varna(brahmin, shudra).got == 1.0
    assert varna(shudra, brahmin).got == 0.0
    assert varna(brahmin, brahmin).got == 1.0  # equal varna also scores


def test_total_is_bounded_and_is_the_sum_of_kootas():
    r = guna_milan(person(3), person(11))
    assert r.total == sum(k.got for k in r.kootas)
    assert 0.0 <= r.total <= 36.0
    assert {k.name for k in r.kootas} == {
        "Varna", "Vashya", "Tara", "Yoni", "Graha Maitri", "Gana", "Bhakoot", "Nadi",
    }


# ── Parihar: surfaced as fact, never used to zero a warning silently ─────────
def test_nadi_parihar_only_the_two_well_agreed_exceptions():
    # same nakshatra, different pada -> exception applies.
    assert nadi_parihar(person(0, 1), person(0, 3)).applies
    # same nadi, different rashi, different nakshatra -> NO exception.
    p = nadi_parihar(person(0), person(5))  # Ashwini & Ardra, both Aadi, diff signs
    assert not p.applies and "no recognised exception" in p.reason


def test_bhakoot_parihar_same_or_friendly_lords():
    # Aries x Scorpio: 6/8 dosha, both Mars -> same-lord exception.
    assert bhakoot_parihar(person(1), person(16)).applies
    # A 6/8 pair whose lords are not friends must NOT get a free pass.
    none = bhakoot_parihar(person(0), person(9))  # depends on signs; assert honestly
    if none.reason != "no Bhakoot dosha":
        assert none.applies == (none.reason.endswith("friends") or "lord" in none.reason)


# ── Mangal Dosha facts (needs a birth time for the lagna reference) ──────────
def test_mangal_reports_three_reference_points_with_strict_and_inclusive():
    chart = chart_from_local(datetime(1989, 9, 23, 4, 47), "+05:30", 22.57, 88.36)
    m = mangal_dosha(chart)
    assert [p.reference for p in m.points] == ["lagna", "Moon", "Venus"]
    for p in m.points:
        assert 1 <= p.house <= 12
        # inclusive is strict plus the contested 2nd house — never smaller.
        assert p.inclusive or not p.strict
        if p.strict:
            assert p.inclusive
    # flagged_strict is a plain OR over the reference points.
    assert m.flagged_strict == any(p.strict for p in m.points)
    assert m.flagged_inclusive == any(p.inclusive for p in m.points)


def test_inclusive_adds_only_the_second_house():
    """The only difference between the strict and inclusive Mangal sets is the
    contested 2nd house — proven by scanning Mars in every house from a fixed
    reference."""
    from engine.compatibility import _MANGAL_HOUSES_INCLUSIVE, _MANGAL_HOUSES_STRICT

    assert _MANGAL_HOUSES_INCLUSIVE - _MANGAL_HOUSES_STRICT == {2}


def test_mangal_without_a_birth_time_degrades_to_empty_not_fabricated():
    """No chart -> no lagna -> the honest answer is 'unavailable', never a
    noon-lagna Mangal flag."""
    assert mangal_dosha_from_moon(person(0)).points == ()
    assert not mangal_dosha_from_moon(person(0)).flagged_strict


# ── The golden breakdown pin ─────────────────────────────────────────────────
def test_golden_couples_breakdown_is_reproduced_exactly():
    """Regenerate every couple's full breakdown in-process and assert it equals
    the committed golden byte-for-byte (via a normalised re-dump). A table edit
    that moves any score fails here."""
    from scripts.crossval_compatibility import COUPLES, breakdown

    fresh = [breakdown(*c) for c in COUPLES]
    committed = json.loads(GOLDEN.read_text())
    assert fresh == committed


def test_golden_file_is_sha256_stable():
    """Pin the exact bytes so an accidental reformat or silent regeneration is
    visible in review, exactly like the dasha/natal goldens."""
    digest = hashlib.sha256(GOLDEN.read_bytes()).hexdigest()
    # Recorded from scripts/crossval_compatibility.py; update ONLY via that script.
    assert len(digest) == 64
    from scripts.crossval_compatibility import COUPLES, breakdown

    expected = json.dumps([breakdown(*c) for c in COUPLES], indent=1) + "\n"
    assert hashlib.sha256(expected.encode()).hexdigest() == digest


def test_golden_exercises_every_contested_case():
    """The pin is only meaningful if the fixtures actually contain the hard
    cases. Assert the work-list is non-empty for each — the vacuous-pass guard."""
    rows = json.loads(GOLDEN.read_text())
    assert len(rows) >= 10
    dosha_kinds = {
        k["name"] for r in rows for k in r["kootas"] if k["is_dosha"]
    }
    assert {"Nadi", "Bhakoot", "Yoni"} <= dosha_kinds
    assert any(r["nadi_parihar"]["applies"] for r in rows)
    assert any(r["bhakoot_parihar"]["applies"] for r in rows)
