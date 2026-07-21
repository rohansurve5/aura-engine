"""Cross-kind collision gates: weekly, monthly and transit, read together.

THE READING UNIT SPANS THREE CORPORA. A subscriber receives every long-form
artefact the product makes and often reads them in one sitting — the weekly for
this week, the monthly for the month containing it, and the transit reading
standing behind both. If two of them say "scattered, with a whiplash turn" in
similar words, the pair reads as one claim padded into two. That is the exact
failure IDENTITY.md §5 solved for nakshatra vs moon sign, one level up:
per-corpus gates (tests/test_report_content_seed.py,
tests/test_transit_content_seed.py) cannot see it, because each runs inside a
single kind.

THE DIVISION OF LABOUR (the §5 rule, at report scale). The first half of this
module covers the weekly/monthly pair; the transit section at the bottom adds
the third term, which is not a subdivision of calendar time at all:

    WEEKLY OWNS DAYS. MONTHLY OWNS WEEKS. TRANSIT OWNS PASSAGES.

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

#: Week-scale vocabulary. Shared between weekly and monthly (both speak of
#: weeks — the weekly IS one, the monthly names them), so it is not a
#: separator for THAT pair. It separates both from transit, which may not name
#: a calendar unit at any scale.
WEEK_TOKENS = {"week", "weeks", "weekly"}

#: Calendar vocabulary as a whole — every unit the two range reports own,
#: forbidden in transit copy. `half`/`halves` are included because they are a
#: calendar-subdivision claim in both range kinds; transit expresses duration
#: through the DATES in its payload, never through a unit noun in its copy.
CALENDAR_TOKENS = DAY_TOKENS | MONTH_TOKENS | WEEK_TOKENS | {
    "half", "halves", "year", "years",
}

#: Passage-scale vocabulary — transit's unit. Forbidden in weekly and monthly
#: copy. Verified against the shipped v3 corpora before adoption: all nine
#: tokens occur zero times in either, so this rule cost no weekly or monthly
#: edit and the goldens stayed byte-identical.
#:
#: NOTE WHAT IS ABSENT. `sign`, `sky`, `stand`/`stands`/`standing` and `orbit`
#: are the obvious candidates and are deliberately NOT here — each already
#: occurs in the shipped weekly or monthly copy in an ordinary English sense
#: ("standing" is a weekly movement name; "under a clear sky" is not an
#: astronomical claim). Banning them would have forced a rewrite of gated,
#: shipped copy to satisfy a gate written afterwards, which is the wrong way
#: round. The set is narrower than it could be and is honest about why.
PASSAGE_TOKENS = {
    "house", "houses", "passage", "passages", "phase", "phases",
    "ingress", "transit", "transits",
}

#: Planet names. Forbidden in weekly and monthly copy, and REQUIRED in every
#: transit passage line — the sharpest edge of the three-way division, and
#: mechanically checkable in both directions.
PLANET_TOKENS = {
    "saturn", "jupiter", "rahu", "ketu", "mars", "venus", "mercury",
    "saturn's", "jupiter's", "rahu's", "ketu's",
}


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


# ═════════════════════════════════════════════════════════════════════════════
# THE THIRD TERM: TRANSIT
#
# Weekly and monthly divide by CALENDAR unit, one nesting inside the other.
# Transit needs a term that is not a subdivision of calendar time at all,
# because its claim is not about a span the calendar names:
#
#     WEEKLY OWNS DAYS.  MONTHLY OWNS WEEKS.  TRANSIT OWNS PASSAGES.
#
#     weekly    dated days, weekday names          never months
#     monthly   ISO weeks, month-halves            never days, never weekdays
#     transit   movers, houses, phases             never ANY calendar unit
#
# This is a CLEANER separation than weekly/monthly have with each other, and
# mechanically checkable in both directions: transit is the only kind that may
# name a planet, and it may never name a calendar unit. Where weekly and
# monthly needed a positive rule bolted on (every monthly opening must NAME the
# month, because both kinds speak of "halves"), transit needs none — the two
# vocabularies are disjoint by construction.
#
# WHICH SLOTS CO-OCCUPY. The movements differ, so the pairing is by SLOT rather
# than by name (docs/REPORTS.md § 6.7):
#
#     transit `weather`  <->  weekly/monthly `shape` openings
#         both answer "what is this whole thing?" and both open the reading
#     transit `passage`  <->  weekly/monthly `standing`
#         both are the per-item judgment the reader scans down
#
# `phase` and `sade_sati` occupy no slot the range reports have, and are not
# compared — the same scoping argument as the identity gate's 36-not-324 and
# the weekly/monthly gate's same-movement rule.
# ═════════════════════════════════════════════════════════════════════════════

import tests.test_transit_content_seed as TG  # noqa: E402


def _transit() -> dict:
    return TG._load()


def _weather(data: dict) -> list[str]:
    return [line for cell in data["weather"].values() for line in cell["lines"]]


def _passages(data: dict) -> list[str]:
    return [line for cell in data["passage"].values() for line in cell["lines"]]


def slot_pairs() -> dict[str, list[tuple[str, str]]]:
    """Every (range-report line, transit line) pair that can occupy the same
    slot in one reader's sitting, across BOTH range kinds."""
    wk, mo, tr = _weekly(), _monthly(), _transit()
    return {
        "opening": [
            (r, t)
            for r in _openings(wk) + _openings(mo)
            for t in _weather(tr)
        ],
        "standing": [
            (r, t)
            for r in (
                [ln for c in wk["standing"].values() for ln in c["lines"]]
                + [ln for c in mo["standing"].values() for ln in c["lines"]]
            )
            for t in _passages(tr)
        ],
    }


def test_the_transit_work_lists_are_the_declared_sizes():
    """Vacuous-pass protection, same as the weekly/monthly gate above.
    Openings: (102 weekly + 65 monthly) x 21 weather. Standing: (90 + 90) x 36
    passages."""
    pairs = slot_pairs()
    assert len(pairs["opening"]) == (102 + 65) * 21 == 3507
    assert len(pairs["standing"]) == (90 + 90) * 36 == 6480


@pytest.mark.parametrize("slot", ["opening", "standing"])
def test_no_range_report_and_transit_line_share_a_frame_in_the_same_slot(slot):
    pairs = slot_pairs()[slot]
    assert pairs, "empty work-list — the pass would be vacuous"
    offenders = [(r, t) for r, t in pairs if G._frame(r) == G._frame(t)]
    assert offenders == [], f"{slot}: {offenders}"


@pytest.mark.parametrize("slot", ["opening", "standing"])
def test_no_range_report_and_transit_line_share_a_skeleton_in_the_same_slot(slot):
    pairs = slot_pairs()[slot]
    assert pairs, "empty work-list — the pass would be vacuous"
    offenders = [
        (r, t)
        for r, t in pairs
        if len(G._words(r)) >= 6 and len(G._words(t)) >= 6 and G._skeleton(r) == G._skeleton(t)
    ]
    assert offenders == [], f"{slot}: {offenders}"


def test_transit_copy_never_names_a_calendar_unit():
    """The negative half of the division, and the strictest of the three.

    Weekly may not say "month" and monthly may not say "day", but each still
    speaks in SOME calendar unit. Transit speaks in none: its cadence is the
    ingress, so a calendar noun in transit copy is not merely trespassing on
    another kind's unit — it is asserting a cadence the artefact does not have.
    Duration reaches the reader through the DATES in the payload
    (`start`, `end`, `days_remaining`, `next_change`), which are specific and
    checkable, rather than through a vague unit noun in a sentence.
    """
    lines = TG._all_lines(_transit())
    assert len(lines) == 71, "work-list short — the pass would be vacuous"
    assert check_unit_trespass(lines, CALENDAR_TOKENS) == []


def test_the_range_reports_never_name_a_planet_or_a_passage():
    """The other direction, and it held on the shipped v3 corpora WITHOUT A
    SINGLE EDIT — verified before the rule was adopted, which is why the weekly
    and monthly goldens are byte-identical across this change.

    That it held for free is itself the evidence the division is real: the
    range reports never wanted planet vocabulary, because their claims are
    about energy distribution over a span and have nothing to do with where a
    body stands.
    """
    for kind, lines in (("weekly", G._all_lines(_weekly())), ("monthly", G._all_lines(_monthly()))):
        assert lines, f"{kind}: empty work-list"
        assert check_unit_trespass(lines, PLANET_TOKENS) == [], kind
        assert check_unit_trespass(lines, PASSAGE_TOKENS) == [], kind


def test_every_transit_passage_line_names_its_mover():
    """The POSITIVE half, and transit's analogue of "every monthly opening must
    name the month".

    A passage line that does not name its mover could sit in any of the three
    corpora — and worse, inside transit it could sit in any of the 36 cells,
    since what distinguishes Saturn-in-the-2nd from Rahu-in-the-2nd is entirely
    which body is standing there. Requiring the name makes the cell's identity
    visible in its own text.
    """
    tr = _transit()
    for key, cell in tr["passage"].items():
        body = key.split(".")[0].lower()
        for line in cell["lines"]:
            words = set(G._words(line))
            assert words & {body, f"{body}'s"}, f"{key} never names {body}: {line!r}"


# ═════════════════════════════════════════════════════════════════════════════
# THE WITHIN-READING COLLISION GATE
#
# Every other gate in this repo compares lines the reader meets at DIFFERENT
# times — consecutive weeks, or two reports in one sitting. Transit has a
# collision surface none of them has: THREE MOVERS RENDER SIMULTANEOUSLY, in
# one payload, one under the other.
#
# So if Saturn and Jupiter both stand in the reader's 4th, two lines about home
# arrive together — and if they were written from the same template, the
# reading visibly says one thing twice. That cannot be caught by any
# cross-kind or consecutive-reading gate, because both lines are in the same
# corpus, in the same key_type, at the same moment.
#
# The work-list is the cross product over (mover A, house) x (mover B, house)
# for A != B, which is what actually co-occurs. Same-house pairs get the extra
# content-overlap cap, because two movers in the SAME house are writing about
# the same life domain and are the sharpest case — exactly the reasoning behind
# the same-key standing cap on weekly x monthly.
# ═════════════════════════════════════════════════════════════════════════════

def cross_mover_pairs() -> list[tuple[str, str, str, str]]:
    """(key A, line A, key B, line B) for every pair of passage cells belonging
    to DIFFERENT movers — the pairs that can render together."""
    tr = _transit()
    keys = sorted(tr["passage"])
    out = []
    for i, ka in enumerate(keys):
        for kb in keys[i + 1:]:
            if ka.split(".")[0] == kb.split(".")[0]:
                continue
            out.append((ka, tr["passage"][ka]["lines"][0], kb, tr["passage"][kb]["lines"][0]))
    return out


def test_the_within_reading_work_list_is_the_declared_size():
    """3 movers choose 2 = 3 unordered mover pairs, x 12 houses x 12 houses."""
    assert len(cross_mover_pairs()) == 3 * 12 * 12 == 432


def test_two_movers_never_open_the_same_way_in_one_reading():
    offenders = [
        (ka, kb) for ka, a, kb, b in cross_mover_pairs() if G._frame(a) == G._frame(b)
    ]
    assert offenders == [], offenders


def test_two_movers_never_share_a_sentence_shape_in_one_reading():
    offenders = [
        (ka, kb)
        for ka, a, kb, b in cross_mover_pairs()
        if len(G._words(a)) >= 6 and len(G._words(b)) >= 6 and G._skeleton(a) == G._skeleton(b)
    ]
    assert offenders == [], offenders


def test_two_movers_in_the_same_house_do_not_say_the_same_thing():
    """THE SHARPEST CASE. Saturn-in-the-4th and Jupiter-in-the-4th are both
    about home, arrive in the same payload, and are read one after the other.
    They must differ beyond the domain noun they unavoidably share.

    Cap of 3 shared content words after stopwords and transit frame words, the
    same threshold and the same reasoning as the weekly x monthly same-key
    standing gate. Measured worst case on the shipped corpus is 3.
    """
    checked = 0
    worst = (0, "", "")
    for ka, a, kb, b in cross_mover_pairs():
        if ka.split(".")[1] != kb.split(".")[1]:
            continue
        shared = (
            (set(G._words(a)) & set(G._words(b)))
            - G.STOPWORDS
            - TG.TRANSIT_FRAME_WORDS
        )
        checked += 1
        if len(shared) > worst[0]:
            worst = (len(shared), ka, kb)
        assert len(shared) <= 3, f"{ka} / {kb}: {sorted(shared)}\n  {a}\n  {b}"
    assert checked == 3 * 12 == 36, "work-list short — the pass would be vacuous"
