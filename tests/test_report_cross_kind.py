"""Cross-kind collision gates: the weekly and monthly corpora, read together.

THE READING UNIT SPANS TWO CORPORA. A subscriber receives BOTH reports and
often reads them in the same sitting — the weekly for this week, the monthly
for the month containing it. If the two say "scattered, with a whiplash turn"
in similar words, the pair reads as one claim padded into two. That is the
exact failure IDENTITY.md §5 solved for nakshatra vs moon sign, one level up:
per-corpus gates (tests/test_report_content_seed.py) cannot see it, because
each runs inside a single kind.

THE DIVISION OF LABOUR (the §5 rule, at report scale):

    WEEKLY OWNS DAYS. MONTHLY OWNS WEEKS.

    weekly   names days and weekdays; its claims are where the strong DAYS
             fall inside seven of them
    monthly  names weeks and month-halves; its claims are which WEEK carries
             the month; it NEVER names a day or a weekday

The keeping-them-apart rule, made mechanical: monthly copy may not contain a
day-scale token, and weekly copy may not contain a month-scale token. If a
monthly line needs the word "Thursday", the claim it is making belongs to the
weekly report. ("half"/"halves" are shared on purpose — weekly halves are
week-halves and monthly halves are month-halves — which is why every monthly
opening and turn line must NAME the month: "the month's front half", never a
bare "the first half" that could sit in either report.)

WHICH PAIRS CAN ACTUALLY CO-OCCUR. Identity's gate runs over 36 real
(nakshatra, sign) pairs because only those share a screen. Here the reader
reads whole movements side by side, and every weekly shape can co-occur with
every monthly shape (a scattered week inside a core-carried month is common),
so the work-list is the full cross product WITHIN each movement slot:
openings x openings, turns x turns, closes x closes — plus standing at the
SAME area.role key, which is the sharpest surface: weekly money.leads and
monthly money.leads answer the same question about the same area and differ
only in span. Cross-movement pairs (a weekly opening vs a monthly close) never
occupy the same slot in the reader's attention and are not compared — same
scoping argument as the identity gate's 36-not-324.

VACUOUS-PASS PROTECTION. Every gate here iterates a work-list built from both
corpora. `test_the_work_lists_are_the_declared_sizes` pins the exact pair
counts, so an empty or half-built work-list (a renamed key, a kind that failed
to load) fails loudly instead of letting every comparison gate go green having
compared nothing. tests/test_report_gates_falsify.py proves each gate fires.
"""

from __future__ import annotations

import json
import re

import pytest

import tests.test_report_content_seed as G

AREAS = G.AREAS
ROLES = ("leads", "lags", "steadies")

#: Day-scale vocabulary — the weekly report's unit. Forbidden in monthly copy.
DAY_TOKENS = {
    "day", "days", "daily", "today", "tomorrow", "tonight", "morning",
    "evening", "midweek", "weekday", "weekdays", "weekend", "monday",
    "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
}

#: Month-scale vocabulary — the monthly report's unit. Forbidden in weekly copy.
MONTH_TOKENS = {"month", "months", "monthly", "month's", "fortnight"}


def _weekly() -> dict:
    return G._load()


def _monthly() -> dict:
    return G._load_monthly()


def _openings(data: dict) -> list[str]:
    return [line for cell in data["shape"].values() for line in cell["openings"]]


def _turns(data: dict) -> list[str]:
    return [line for cell in data["turn"].values() for line in cell["lines"]]


def _closes(data: dict) -> list[str]:
    return [line for cell in data["close"].values() for line in cell["lines"]]


def movement_pairs(weekly: dict, monthly: dict) -> dict[str, list[tuple[str, str]]]:
    """The full work-list: every (weekly line, monthly line) pair that can
    occupy the same movement slot in one reader's sitting."""
    out: dict[str, list[tuple[str, str]]] = {}
    out["opening"] = [(w, m) for w in _openings(weekly) for m in _openings(monthly)]
    out["turn"] = [(w, m) for w in _turns(weekly) for m in _turns(monthly)]
    out["close"] = [(w, m) for w in _closes(weekly) for m in _closes(monthly)]
    standing: list[tuple[str, str]] = []
    for area in AREAS:
        for role in ROLES:
            key = f"{area}.{role}"
            for w in weekly["standing"][key]["lines"]:
                for m in monthly["standing"][key]["lines"]:
                    standing.append((w, m))
    out["standing"] = standing
    return out


# ── the vacuous-pass signature, stated first ─────────────────────────────────

def test_the_work_lists_are_the_declared_sizes():
    """An empty work-list passing is the failure shape the identity suite pins
    as `seeded_pairs(data) == []`. Exact counts: 102x65 openings, 35x28 turns,
    30x25 closes, 18 keys x 5x5 standings."""
    pairs = movement_pairs(_weekly(), _monthly())
    assert len(pairs["opening"]) == 102 * 65 == 6630
    assert len(pairs["turn"]) == 35 * 28 == 980
    assert len(pairs["close"]) == 30 * 25 == 750
    assert len(pairs["standing"]) == 18 * 5 * 5 == 450


# ── structural collision: frames and skeletons across kinds ──────────────────

@pytest.mark.parametrize("movement", ["opening", "turn", "close", "standing"])
def test_no_weekly_and_monthly_line_share_a_frame_in_the_same_slot(movement):
    """Two reports opening with the same four words read as one template."""
    pairs = movement_pairs(_weekly(), _monthly())[movement]
    assert pairs, "empty work-list — the pass would be vacuous"
    offenders = [
        (w, m) for w, m in pairs if G._frame(w) == G._frame(m)
    ]
    assert offenders == [], f"{movement}: {offenders}"


@pytest.mark.parametrize("movement", ["opening", "turn", "close", "standing"])
def test_no_weekly_and_monthly_line_share_a_skeleton_in_the_same_slot(movement):
    """The v3 failure mode across kinds: one sentence shape, labels swapped."""
    pairs = movement_pairs(_weekly(), _monthly())[movement]
    assert pairs, "empty work-list — the pass would be vacuous"
    offenders = [
        (w, m)
        for w, m in pairs
        if len(G._words(w)) >= 6
        and len(G._words(m)) >= 6
        and G._skeleton(w) == G._skeleton(m)
    ]
    assert offenders == [], f"{movement}: {offenders}"


# ── the division of labour, made mechanical ──────────────────────────────────

def check_unit_trespass(lines: list[str], forbidden: set[str]) -> list[tuple[str, list[str]]]:
    """Lines containing tokens from the other kind's unit vocabulary."""
    out = []
    for line in lines:
        hits = sorted(set(G._words(line)) & forbidden)
        if hits:
            out.append((line, hits))
    return out


def test_monthly_copy_never_speaks_in_days():
    """Monthly claims are at week granularity; a monthly line that needs a day
    word is making a claim that belongs to the weekly report."""
    lines = G._all_lines(_monthly())
    assert len(lines) == 208, "work-list short — the pass would be vacuous"
    assert check_unit_trespass(lines, DAY_TOKENS) == []


def test_weekly_copy_never_speaks_in_months():
    """The other direction. This held for the v2 weekly corpus without edits
    (verified before the rule was adopted) and pins it for every future weekly
    line: a weekly line that needs the month is trespassing upward."""
    lines = G._all_lines(_weekly())
    assert len(lines) == 257, "work-list short — the pass would be vacuous"
    assert check_unit_trespass(lines, MONTH_TOKENS) == []


def test_monthly_openings_and_turns_name_the_month():
    """The positive half of the division. Weekly and monthly both speak of
    "halves"; a bare "the first half holds the better ground" could sit in
    either report and therefore reads as padding when both arrive together.
    Every monthly opening and turn line must anchor its unit by naming the
    month, so the two reports are visibly about different spans."""
    monthly = _monthly()
    lines = _openings(monthly) + _turns(monthly)
    assert len(lines) == 65 + 28, "work-list short — the pass would be vacuous"
    offenders = [
        line for line in lines if not set(G._words(line)) & {"month", "month's", "months"}
    ]
    assert offenders == [], offenders


# ── the sharpest surface: same-key standing, checked at claim level ──────────

def test_same_key_standing_pairs_differ_beyond_the_area_noun():
    """Weekly money.leads and monthly money.leads answer the same question
    about the same area. Frames and skeletons are already gated above; this
    adds a content-overlap cap on the 25 pairs of each key: after dropping
    stopwords, frame words of both kinds and the area's own nouns, no pair may
    share more than 3 content words. At 4+ shared content words two short
    lines about the same area are the same sentence wearing different
    function words — measured worst case on the shipped corpora is 3."""
    weekly, monthly = _weekly(), _monthly()
    frame = G.FRAME_WORDS | G.MONTH_FRAME_WORDS
    checked = 0
    worst: tuple[int, str, str] | None = None
    for area in AREAS:
        for role in ROLES:
            key = f"{area}.{role}"
            for w in weekly["standing"][key]["lines"]:
                for m in monthly["standing"][key]["lines"]:
                    shared = (
                        (set(G._words(w)) & set(G._words(m)))
                        - G.STOPWORDS
                        - frame
                        - {area}
                    )
                    checked += 1
                    if worst is None or len(shared) > worst[0]:
                        worst = (len(shared), w, m)
                    assert len(shared) <= 3, (
                        f"{key}: {sorted(shared)}\n  weekly: {w}\n  monthly: {m}"
                    )
    assert checked == 450, "work-list short — the pass would be vacuous"
