"""Muhurat ranking — structure pins and the two honesty invariants.

Like test_compatibility.py this is not an ephemeris cross-validation (the
rise/set + choghadiya names are already gated by test_panchang.py against
DrikPanchang and by crossval_window.py engine-vs-Worker). It pins the
*composition* layer engine/muhurat.py adds, and the two properties the whole
paywall decision rests on:

  1. No birth time  ⇒  the ranking is a pure function of (place, day, purpose):
     identical for every user. 'personal muhurat' is impossible here.
  2. Birth time     ⇒  the ranking keys ONLY on the natal lagna SIGN (12 classes)
     — two users sharing a lagna sign get an identical ranking (the measured
     12-way altitude), and the lagna term genuinely re-ranks vs the impersonal
     order (it is not a relabelling).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

import engine.muhurat as M
from engine.ephemeris import IST


# ── purpose model shape (vacuous-pass guard for the gate battery) ───────────
def test_purposes_use_only_favourable_choghadiya():
    """No purpose may ever admit Kaal/Rog/Udveg — the inauspicious names."""
    inauspicious = {"Kaal", "Rog", "Udveg"}
    for purpose, favoured in M.PURPOSES.items():
        assert favoured, purpose
        assert not (favoured & inauspicious), f"{purpose} admits an inauspicious slot"
        assert favoured <= set(M.CHOG_RANK), f"{purpose} favours an unranked slot"


def test_lagna_sign_classes_partition_the_zodiac():
    assert M.MOVABLE | M.FIXED | M.DUAL == set(range(12))
    assert not (M.MOVABLE & M.FIXED) and not (M.FIXED & M.DUAL) and not (M.MOVABLE & M.DUAL)


# ── a synthetic day of 16 windows, ephemeris-free ───────────────────────────
def _synthetic_windows(lagna_start: int = 0) -> list[tuple]:
    """16 named slots with a plausible rising-sign progression (one sign per
    ~1.5 slots). Names chosen so several purposes have >=2 candidates."""
    names = [
        "Amrit", "Kaal", "Shubh", "Rog", "Labh", "Udveg", "Chal", "Amrit",   # day
        "Shubh", "Labh", "Chal", "Rog", "Kaal", "Amrit", "Udveg", "Shubh",   # night
    ]
    out = []
    for i, nm in enumerate(names):
        start = datetime(2026, 7, 21, 6, 0) + timedelta(hours=i * 1.1)
        end = start + timedelta(hours=1.1)
        lagna = (lagna_start + i) % 12  # rising sign advances through the day
        out.append((nm, start, end, lagna))
    return out


def test_rank_windows_rejects_unknown_purpose():
    with pytest.raises(ValueError):
        M.rank_windows(_synthetic_windows(), set(), "wedding")


def test_kaal_slots_and_inauspicious_names_are_excluded():
    windows = _synthetic_windows()
    kaal_starts = {windows[0][1]}  # exclude the first (an Amrit) as a kaal
    res = M.rank_windows(windows, kaal_starts, "start")
    picked = {(c.name, c.start) for c in res["candidates"]}
    assert (windows[0][0], windows[0][1]) not in picked  # kaal removed
    assert all(c.name in M.PURPOSES["start"] for c in res["candidates"])
    # ranking is sorted best-first
    scores = [c.score for c in res["candidates"]]
    assert scores == sorted(scores, reverse=True)


# ── INVARIANT 1: no birth time ⇒ impersonal, identical for everyone ─────────
def test_no_birth_time_ranking_is_impersonal():
    windows = _synthetic_windows()
    res = M.rank_windows(windows, set(), "business")
    assert res["personalisation"] == "impersonal"
    assert all(not c.personal for c in res["candidates"])
    # It does not depend on any user input — there is no user input to depend on.
    again = M.rank_windows(windows, set(), "business")
    assert [c.start for c in res["candidates"]] == [c.start for c in again["candidates"]]


# ── INVARIANT 2: birth time ⇒ 12-way (lagna-sign) personalisation ───────────
def test_same_lagna_sign_gives_identical_ranking():
    """Two 'users' with the same natal lagna sign — any other birth difference is
    irrelevant to muhurat ranking (tarabala/chandrabala are day-constant and not
    scored). Identical ranking, by construction — the 12-way altitude."""
    windows = _synthetic_windows(lagna_start=3)
    a = M.rank_windows(windows, set(), "start", natal_lagna_sign=5)
    b = M.rank_windows(windows, set(), "start", natal_lagna_sign=5)
    assert [c.start for c in a["candidates"]] == [c.start for c in b["candidates"]]
    assert a["personalisation"] == "personal_12way"


def test_lagna_term_actually_reranks_across_signs():
    """The birth-time term is not a relabelling: at least two natal lagna signs
    must produce a different best window on some day, or the personalisation is
    hollow (the task's stop-condition)."""
    windows = _synthetic_windows(lagna_start=0)
    tops = {
        M.rank_windows(windows, set(), "start", natal_lagna_sign=asc)["candidates"][0].start
        for asc in range(12)
    }
    assert len(tops) >= 2, "natal lagna never changes the top window — hollow"


def test_lagna_house_favours_kendra_trikona():
    # rising sign == natal lagna ⇒ house 1 (a kendra) ⇒ personal bonus applies.
    assert M._lagna_house(4, 4) == 1
    assert M.score_window("Amrit", 4, "start", 4) > M.score_window("Amrit", 4, "start", None)
    # rising sign in the native's 3rd (not a sweet-spot house) ⇒ no personal bonus:
    # the birth-time score equals the impersonal score for that same window.
    assert M._lagna_house(6, 4) == 3
    assert M.score_window("Amrit", 6, "start", 4) == M.score_window("Amrit", 6, "start", None)


# ── the real ephemeris entrypoint runs and stays honest end-to-end ──────────
def test_auspicious_timings_end_to_end_impersonal_vs_personal():
    pune = (18.5204, 73.8567)
    imp = M.auspicious_timings(date(2026, 7, 21), *pune, "start", tz=IST)
    per = M.auspicious_timings(date(2026, 7, 21), *pune, "start", natal_lagna_sign=7, tz=IST)
    assert imp["personalisation"] == "impersonal"
    assert per["personalisation"] == "personal_12way"
    # same candidate SET (day-quality filter is identical); ranking may differ.
    assert {c.start for c in imp["candidates"]} == {c.start for c in per["candidates"]}
    assert imp["candidates"], "no auspicious window found — filter too strict?"
