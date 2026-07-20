"""The content_v3_1 PER-DAY distinctness gate — the unit that matters is what
ONE PERSON READS IN ONE DAY.

Why this file exists (and why test_content_diversity.py could not catch the
failure it guards against):

    The corpus gate reasons over the *whole seed at once*. It asks "does any
    word dominate all ~450 lines" and "do any two areas share a skeleton
    anywhere in the corpus". Under content_v3 the answer to both was no — the
    six areas' CAUSE lines were separately authored, lexically varied, and
    skeleton-disjoint, so the corpus looked healthy.

    But content_v3 resolved every area's CAUSE from ONE source, (day lord ×
    paksha). So on 2026-07-20 a real user opened six cards and read six
    variations of "Monday belongs to the Moon". Each line was unique in the
    corpus; the *slice a person actually sees* was six-for-six identical in
    framing. A corpus-wide 6% share threshold cannot see a 100% share inside a
    six-line slice — the denominators are different objects.

    So this gate evaluates the rendered slice: for a given date and natal
    nakshatra, take the six score_why strings a user would see and assert they
    differ in SOURCE, in OPENING FRAME and in SKELETON. Keep both gates: the
    corpus gate protects the library, this one protects the reading.

Coverage is deterministic (a fixed 120-day span, longer than the 84-day
rotation × weekday cycle) plus the live rolling 14-day precompute window, so
the gate also runs against exactly the dates the nightly job is about to seed.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from engine.daily import build_daily_sky
from engine.scoring import (
    _cause,
    _pick,
    cause_sources_for,
    guidance_for_nakshatra,
    load_rules_from_json,
    tara_of,
)

RULES = load_rules_from_json()
AREAS = RULES["areas"]["order"]
LABELS = RULES["areas"]["labels"]

# Natal nakshatras spanning the tara cycle (each has a different relationship to
# any given day-Moon, so the `tara` cause source is exercised across its range).
SAMPLE_NATALS = (0, 1, 7, 13, 20, 26)

FIXED_START = date(2026, 7, 20)  # the date testers read six identical causes on
FIXED_DAYS = 120
ROLLING_DAYS = 14

OPENING_WORDS = 4

WORD_RE = re.compile(r"[a-z']+")
SLOT_RE = re.compile(r"\{[a-z_]+\}")

# Kept in sync with tests/test_content_diversity.py — function words are what a
# skeleton keeps, so two lines with the same skeleton are the same sentence with
# different content words dropped in.
from tests.test_content_diversity import STOPWORDS  # noqa: E402


def _words(line: str) -> list[str]:
    return WORD_RE.findall(SLOT_RE.sub(" ", line.lower()))


def _opening(line: str) -> str:
    return " ".join(_words(line)[:OPENING_WORDS])


def _skeleton(line: str) -> str:
    return " ".join(t if t in STOPWORDS else "_" for t in _words(line))


def _dates() -> list[date]:
    fixed = [FIXED_START + timedelta(days=i) for i in range(FIXED_DAYS)]
    today = date.today()
    rolling = [today + timedelta(days=i) for i in range(ROLLING_DAYS)]
    return fixed + [d for d in rolling if d not in set(fixed)]


def _causes(day: date, natal: int) -> dict[str, tuple[str, str]]:
    """area → (source id, the CAUSE half alone) as rendered for this reader."""
    sky = build_daily_sky(day)
    tara = tara_of(natal, sky["day_nakshatra_index"])
    ordinal = day.toordinal()
    sources = cause_sources_for(ordinal, RULES)
    out = {}
    for i, area in enumerate(AREAS):
        def pick(variants, i=i):
            return _pick(variants, ordinal, natal, salt=23 + i)

        out[area] = (sources[area], _cause(sources[area], area, sky, RULES, tara, pick))
    return out


def _assert_unique(kind: str, values: dict[str, str], day: date, natal: int) -> None:
    seen: dict[str, str] = {}
    for area, value in values.items():
        if value in seen:
            raise AssertionError(
                f"{day} natal={natal}: {seen[value]} and {area} share the same "
                f"{kind} — a reader opening both cards sees the same thing.\n"
                f"  {kind}: {value!r}"
            )
        seen[value] = area


def test_no_two_areas_share_a_cause_source_on_a_date():
    """The v3 defect exactly: six areas, one explanation source."""
    for day in _dates():
        sources = cause_sources_for(day.toordinal(), RULES)
        _assert_unique("cause source", sources, day, natal=-1)


def test_every_rotation_row_is_a_permutation_of_all_sources():
    expected = sorted({s for row in RULES["cause_rotation"] for s in row})
    assert len(expected) >= 5, f"too few cause sources to separate six areas: {expected}"
    for i, row in enumerate(RULES["cause_rotation"]):
        assert len(row) == len(AREAS), f"rotation row {i} does not cover the six areas"
        assert sorted(row) == expected, (
            f"rotation row {i} is not a permutation of the sources: {row}"
        )


def test_every_area_meets_every_source_across_the_cycle():
    """No area may be permanently wedded to one kind of explanation — a user
    must not be able to learn that Money is always explained the same way."""
    rotation = RULES["cause_rotation"]
    sources = {s for row in rotation for s in row}
    for i, area in enumerate(AREAS):
        used = {row[i] for row in rotation}
        assert used == sources, f"{area} never draws source(s) {sources - used}"


def test_no_two_areas_share_a_cause_opening_frame_on_a_date():
    for day in _dates():
        for natal in SAMPLE_NATALS:
            causes = _causes(day, natal)
            openings = {
                area: _opening(text)
                for area, (_, text) in causes.items()
                if text  # the `none` source renders no cause at all
            }
            _assert_unique(f"cause opening ({OPENING_WORDS} words)", openings, day, natal)


def test_no_two_areas_share_a_cause_skeleton_on_a_date():
    for day in _dates():
        for natal in SAMPLE_NATALS:
            causes = _causes(day, natal)
            skeletons = {
                area: _skeleton(text) for area, (_, text) in causes.items() if text
            }
            _assert_unique("cause sentence skeleton", skeletons, day, natal)


def test_no_two_rendered_cards_share_an_opening_or_skeleton_on_a_date():
    """The whole thing the user reads — RECOGNITION + CAUSE — must differ too."""
    for day in _dates():
        sky = build_daily_sky(day)
        for natal in SAMPLE_NATALS:
            why = guidance_for_nakshatra(natal, sky, RULES)["score_why"]
            _assert_unique("card", why, day, natal)
            _assert_unique(
                f"card opening ({OPENING_WORDS} words)",
                {a: _opening(t) for a, t in why.items()},
                day,
                natal,
            )
            _assert_unique(
                "card sentence skeleton",
                {a: _skeleton(t) for a, t in why.items()},
                day,
                natal,
            )


def test_exactly_one_card_a_day_stands_without_a_cause():
    """Short line among longer ones is deliberate texture, not a missing cell."""
    for day in _dates():
        empty = [a for a, (_, text) in _causes(day, SAMPLE_NATALS[0]).items() if not text]
        assert len(empty) == 1, f"{day}: {len(empty)} cards render without a cause"


def test_every_cause_cell_the_rotation_can_reach_is_filled():
    """Any (source, area, sky) combination reachable in a year must resolve —
    a missing cell would raise in the nightly job, not in review."""
    for offset in range(370):
        day = FIXED_START + timedelta(days=offset)
        sky = build_daily_sky(day)
        ordinal = day.toordinal()
        for natal in SAMPLE_NATALS:
            tara = tara_of(natal, sky["day_nakshatra_index"])
            for source in {s for row in RULES["cause_rotation"] for s in row}:
                for area in AREAS:
                    def pick(variants, ordinal=ordinal, natal=natal):
                        return _pick(variants, ordinal, natal, salt=23)

                    text = _cause(source, area, sky, RULES, tara, pick)
                    assert source == "none" or text, f"{source}/{area} empty on {day}"
