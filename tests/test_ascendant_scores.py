"""content_v4 (A5) gates: the read-time ascendant arithmetic and its contracts.

Three things are pinned here:

1. **Additivity / rollback** — under the active v4 rules, a request WITHOUT an
   ascendant renders byte-identically to content_v3_2 (the compose bundle is
   the only new payload field), and the v3_2 seed still composes its exact
   old payloads. Repointing the marker back IS the rollback; this test is the
   proof it stays true.
2. **Arithmetic** — house_terms against hand-computed cases, and the clamp
   ordering guarantee (adjust the UNCLAMPED base, then clamp once).
3. **Coherence (A5 §2)** — after apply_ascendant, every band label and
   recognition line matches the band of the score actually shown; the
   opportunity/warning name the actual argmax/argmin areas; the narrative
   closer names the same best/caution; the biggest-|T| area's cause is the
   house line for its primary significator's REAL transit house; and the six
   rendered causes remain pairwise distinct (the per-day gate's contract,
   held on the adjusted slice too).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from engine.content import SEED_PATH
from engine.daily import build_daily_sky
from engine.scoring import (
    _clamp,
    _score_band,
    apply_ascendant,
    guidance_for_nakshatra,
    house_terms,
    load_rules_from_json,
    transit_houses,
)

SEED_DIR = Path(__file__).resolve().parent.parent / "db" / "seed"

RULES_V4 = load_rules_from_json()
RULES_V32 = load_rules_from_json(SEED_DIR / "score_rules_content_v3_2.json")

DAYS = [date(2026, 7, 21) + timedelta(days=7 * i) for i in range(5)]
SKIES = {d: build_daily_sky(d) for d in DAYS}
SAMPLE_NATALS = (0, 7, 13, 20, 26)
SAMPLE_ASCS = (0, 3, 6, 11)


def test_active_seed_is_v4_with_house_tables():
    data = json.loads(SEED_PATH.read_text())
    assert data["version"] == "content_v4"
    for key in ("house_significators", "gochara_fav", "gochara_extra_bad",
                "gochara_weights", "occupancy_mod", "upachaya_houses",
                "why_cause_house"):
        assert key in data["rules"], f"v4 seed missing {key}"
    # 6 areas × 12 houses, every cell authored.
    for area in data["rules"]["areas"]["order"]:
        cells = data["rules"]["why_cause_house"][area]
        assert set(cells) == {str(h) for h in range(1, 13)}, area


def test_v4_without_ascendant_is_v32_plus_compose_only():
    """The additive contract: same sky, both rule sets — the v4 payload minus
    its compose bundle is byte-identical to the v3_2 payload. This is what
    makes v4 safe for every shipped app build (none of which send an asc) and
    what makes the marker repoint a real rollback."""
    for d in DAYS:
        sky = SKIES[d]
        for nak in SAMPLE_NATALS:
            old = guidance_for_nakshatra(nak, sky, RULES_V32)
            new = guidance_for_nakshatra(nak, sky, RULES_V4)
            assert "compose" not in old
            trimmed = {k: v for k, v in new.items() if k != "compose"}
            assert trimmed == old, f"v4-no-asc drifted from v3_2 on {d} nak {nak}"


def test_compose_bundle_carries_the_unclamped_base_and_raw_templates():
    sky = SKIES[DAYS[0]]
    row = guidance_for_nakshatra(4, sky, RULES_V4)
    compose = row["compose"]
    labels = RULES_V4["areas"]["labels"]
    for a in RULES_V4["areas"]["order"]:
        # clamped compose base reproduces the served score exactly
        assert _clamp(compose["score_base"][labels[a]]) == row["scores"][labels[a]]
    assert "{best}" in compose["narrative_closer"]
    assert "{area}" in compose["opportunity"]
    assert "{area}" in compose["warning"]


def test_transit_houses_counts_from_the_lagna():
    signs = {"Sun": 0, "Moon": 11, "Saturn": 6}
    assert transit_houses(0, signs) == {"Sun": 1, "Moon": 12, "Saturn": 7}
    assert transit_houses(11, signs) == {"Sun": 2, "Moon": 1, "Saturn": 8}


def test_house_terms_hand_computed_cases():
    # Every graha in the lagna sign (house 1 for asc 0): no occupancy fires
    # (house 1 belongs to no area), so T is pure significator condition.
    all_in_1 = {p: 0 for p in ("Sun", "Moon", "Mars", "Mercury", "Jupiter",
                               "Venus", "Saturn", "Rahu", "Ketu")}
    t = house_terms(0, all_in_1, RULES_V4)
    assert t == {
        "career": -13,  # Saturn extra-bad in 1 (-2×5) + Sun unfav (-1×3)
        "money": -2,    # Jupiter unfav (-5) + Venus fav in 1 (+3)
        "love": 8,      # Venus fav (+5) + Moon fav (+3)
        "mind": -6,     # Mercury unfav in 1
        "health": -8,   # Mars unfav (-4) + Sun unfav (-4)
        "mood": 6,      # Moon fav in 1
    }

    # Every graha nine signs on (house 10, an upachaya): career's own house is
    # occupied by all nine, malefic occupancy flips positive.
    all_in_10 = {p: 9 for p in all_in_1}
    t10 = house_terms(0, all_in_10, RULES_V4)
    # occupancy sum: Jup 3 + Ven 2 + Mer 1 + Moon 1 + Sun 1 + Mars 2 + Sat 3
    #              + Rahu 2 + Ketu 1 = 16; Saturn unfav (-5) + Sun fav 10 (+3)
    assert t10["career"] == -5 + 3 + 16


@pytest.mark.parametrize("day", DAYS)
def test_apply_ascendant_is_coherent(day):
    sky = SKIES[day]
    rules = RULES_V4
    order = rules["areas"]["order"]
    labels = rules["areas"]["labels"]
    focus = rules["narrative"]["focus"]
    moon_group = rules["moon_groups"][str(sky["day_nakshatra_index"])]

    for nak in SAMPLE_NATALS:
        row = guidance_for_nakshatra(nak, sky, rules)
        for asc in SAMPLE_ASCS:
            adj = apply_ascendant(row, sky, asc, rules)
            terms = house_terms(asc, sky["planet_signs"], rules)

            # scores: clamp(unclamped base + T), never double-clamped
            for a in order:
                expected = _clamp(row["compose"]["score_base"][labels[a]] + terms[a])
                assert adj["scores"][labels[a]] == expected

            best = max(order, key=lambda a: (adj["scores"][labels[a]], -order.index(a)))
            worst = min(order, key=lambda a: (adj["scores"][labels[a]], order.index(a)))
            assert labels[best] in adj["opportunity"]
            assert labels[worst] in adj["warning"]
            assert focus[best] in adj["narrative"]
            assert focus[worst] in adj["narrative"]

            # every label + recognition matches the band of the SHOWN score
            for a in order:
                band = _score_band(adj["scores"][labels[a]], rules["score_bands"])
                assert adj["band_labels"][labels[a]] == rules["band_labels"][a][band]
                recognition = rules["why_recognition"][a][band][moon_group]
                assert adj["score_why"][labels[a]].startswith(recognition)

            # the biggest mover explains itself through its significator's
            # ACTUAL transit house
            top = max(order, key=lambda a: (abs(terms[a]), -order.index(a)))
            primary = rules["house_significators"][top]["primary"]
            h = transit_houses(asc, sky["planet_signs"])[primary]
            house_line = rules["why_cause_house"][top][str(h)]
            assert adj["score_why"][labels[top]].endswith(house_line)

            # the six rendered causes stay pairwise distinct
            causes = []
            for a in order:
                recognition = rules["why_recognition"][
                    a][_score_band(adj["scores"][labels[a]], rules["score_bands"])][moon_group]
                causes.append(adj["score_why"][labels[a]][len(recognition):].strip())
            non_empty = [c for c in causes if c]
            assert len(non_empty) == len(set(non_empty)), (day, nak, asc, causes)

            # untouched ground passes through
            for key in ("energy", "tara", "area_lines", "why", "lucky",
                        "good_for", "avoid", "opportunity_detail", "warning_detail"):
                assert adj[key] == row[key]
            assert adj["ascendant"] == {"sign_index": asc, "applied": True}
            # the input row is not mutated
            assert "ascendant" not in row


def test_unknown_time_row_is_served_verbatim():
    """A5 §4: no ascendant → the 27-row payload IS the reading. There is no
    partial adjustment path; apply_ascendant simply never runs. This pins that
    the base payload needs nothing from the asc tables to render."""
    sky = SKIES[DAYS[0]]
    row = guidance_for_nakshatra(9, sky, RULES_V4)
    assert "ascendant" not in row
    for field in ("scores", "band_labels", "score_why", "narrative",
                  "opportunity", "warning"):
        assert field in row
