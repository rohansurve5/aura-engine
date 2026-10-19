"""Falsification suite: proof that every knowledge gate actually FIRES.

A gate nobody has watched go red is not a gate — it is a comment that happens to
be executable. This file is `test_identity_gates_falsify.py`'s discipline applied
to the significations corpus, and it matters more here than it did there, because
this corpus's central gates are **comparative** (§7d) rather than per-entry. A
comparative gate has a failure mode a per-entry gate does not: it can be satisfied
by making the *baseline* worse instead of the subject better. Every §7d gate below
is therefore falsified in BOTH directions.

## Method

Every test mutates an in-memory copy of the real seed, monkeypatches `_load`, and
calls **the actual gate function** from `test_knowledge_content_seed.py` — never a
reimplementation. `_expect_red` asserts the gate raises; `_expect_green` re-runs it
on the unmutated corpus immediately after, so a gate accidentally broken into
always-failing cannot be mistaken for a gate that discriminates.

## Where more than one signature is required, and why

Per the task's rule that each gate be falsified with more than one signature. The
signatures are not two flavours of the same mutation — each pair is chosen so that
the second would slip past a plausible weaker implementation of the same gate:

* **Fear symmetry (§7d.1, §7d.2)** — (1) make the hard entry heavier, the obvious
  direction; (2) make the EASY entries lighter, which is the direction that
  reproduces the malefic hierarchy while every individual entry still looks fine.
  A gate that only compared entries to a fixed constant would pass (2).
* **Inverse floor (§7d.3)** — (1) strip Jupiter's demand of weight, (2) strip
  Saturn's. Both must be red. A gate that only policed the easy half would pass
  the second and would have quietly become a one-sided rule.
* **Cross-corpus collision (§6)** — (1) a genuine shared content word; (2) a
  VACUOUS PASS: rename a key so the pair-list shrinks and the gate has nothing to
  compare. This is the fallback-shaped violation that broke the identity suite's
  first version, and it is caught here by the surface-size gate rather than by the
  collision gate itself, which is the honest division.
* **Source citation** — (1) an uncitable ref, (2) a ref that names a real text but
  no locus (`BPHS — the planets`), which is the shape a lazy citation actually
  takes and which a bare "is it non-empty" check would pass.
* **§8 review** — (1) shippable flipped true without a checkpoint, (2) checkpoint_b
  approved by a stated NON-astrologer, which is the failure that matters: it is
  what a well-meaning product owner would do.
* **Second person (§4.1)** — (1) in `governs`, (2) in a `distinct_from.because`,
  which is authoring scaffolding and is deliberately outside the prose gates. It
  must not be outside this one.
"""

from __future__ import annotations

import copy
import json

import pytest

from tests import test_knowledge_content_seed as G


def _corpus() -> dict:
    return copy.deepcopy(json.loads(G.SEED_PATH.read_text()))


def _expect_red(monkeypatch, data: dict, gate, *args) -> str:
    monkeypatch.setattr(G, "_load", lambda: data)
    with pytest.raises(AssertionError) as exc:
        gate(*args)
    return str(exc.value)


def _expect_green(monkeypatch, gate, *args) -> None:
    monkeypatch.setattr(G, "_load", lambda: json.loads(G.SEED_PATH.read_text()))
    gate(*args)


# ── Structure (§7b) ──────────────────────────────────────────────────────────


def test_falsify_missing_entry(monkeypatch) -> None:
    data = _corpus()
    data["house"].pop("house_8")
    msg = _expect_red(monkeypatch, data, G.test_all_48_entries_present_and_canonically_keyed)
    assert "house_8" in msg
    _expect_green(monkeypatch, G.test_all_48_entries_present_and_canonically_keyed)


def test_falsify_non_canonical_key(monkeypatch) -> None:
    """Second signature: the count is still 27, so a length check alone passes."""
    data = _corpus()
    data["nakshatra"]["Krittica"] = data["nakshatra"].pop("Krittika")
    msg = _expect_red(monkeypatch, data, G.test_all_48_entries_present_and_canonically_keyed)
    assert "Krittica" in msg or "Krittika" in msg
    _expect_green(monkeypatch, G.test_all_48_entries_present_and_canonically_keyed)


def test_falsify_governs_word_band(monkeypatch) -> None:
    data = _corpus()
    data["planet"]["Jupiter"]["governs"] = "Jupiter is counsel."
    msg = _expect_red(monkeypatch, data, G.test_field_lengths_inside_the_spec_bands)
    assert "spec says 25-40" in msg
    _expect_green(monkeypatch, G.test_field_lengths_inside_the_spec_bands)


def test_falsify_demand_must_be_one_sentence(monkeypatch) -> None:
    """Second signature on the same gate: §5 fixes `demand` at ONE sentence, and
    two short sentences can sit inside the word band while breaking the shape the
    §7d length comparison depends on."""
    data = _corpus()
    data["house"]["house_5"]["demand"] = (
        "Whatever issues from here carries a name for good. "
        "What is put out under one cannot ever be taken back unsigned again."
    )
    msg = _expect_red(monkeypatch, data, G.test_field_lengths_inside_the_spec_bands)
    assert "1 sentence" in msg
    _expect_green(monkeypatch, G.test_field_lengths_inside_the_spec_bands)


def test_falsify_shipped_length_target(monkeypatch) -> None:
    data = _corpus()
    entry = data["nakshatra"]["Hasta"]
    entry["governs"] = entry["governs"] + " " + entry["governs"]
    msg = _expect_red(monkeypatch, data, G.test_shipped_length_target)
    assert "target 65" in msg
    _expect_green(monkeypatch, G.test_shipped_length_target)


def test_falsify_title_is_the_bare_name(monkeypatch) -> None:
    data = _corpus()
    data["planet"]["Saturn"]["title"] = "Saturn"
    msg = _expect_red(monkeypatch, data, G.test_field_lengths_inside_the_spec_bands)
    assert "3-6" in msg or "bare name" in msg
    _expect_green(monkeypatch, G.test_field_lengths_inside_the_spec_bands)


# ── distinct_from (§7c.4) ────────────────────────────────────────────────────


def test_falsify_self_contrast(monkeypatch) -> None:
    data = _corpus()
    data["nakshatra"]["Mula"]["distinct_from"]["entry"] = "Mula"
    msg = _expect_red(monkeypatch, data, G.test_distinct_from_is_well_formed)
    assert "itself" in msg
    _expect_green(monkeypatch, G.test_distinct_from_is_well_formed)


def test_falsify_orphaned_jurisdiction(monkeypatch) -> None:
    """Second signature, and the one that matters: every entry stays individually
    well-formed while one jurisdiction is left contrasted with by nobody. This is
    a SPARSE graph, not a malformed one, and per-entry validation cannot see it."""
    data = _corpus()
    orphan = "house_7"
    for key, entry in data["house"].items():
        if entry["distinct_from"]["entry"] == orphan:
            entry["distinct_from"]["entry"] = "house_1" if key != "house_1" else "house_2"
    msg = _expect_red(monkeypatch, data, G.test_distinct_from_coverage)
    assert orphan in msg
    _expect_green(monkeypatch, G.test_distinct_from_coverage)


# ── Voice (§7e) ──────────────────────────────────────────────────────────────


def test_falsify_banned_vocabulary(monkeypatch) -> None:
    data = _corpus()
    data["house"]["house_8"]["governs"] = (
        "The eighth house is read for what arrives without being chosen, and for "
        "the destiny that nobody selected, inheritance, upheaval and hidden things."
    )
    msg = _expect_red(monkeypatch, data, G.test_no_banned_vocabulary)
    assert "destiny" in msg
    _expect_green(monkeypatch, G.test_no_banned_vocabulary)


def test_falsify_the_benefic_half_of_the_hierarchy(monkeypatch) -> None:
    """Second signature, and the reason §3 exists. `malefic` was already banned
    before this corpus; `benefic` was NOT, and banning only the bad half of a
    two-sided hierarchy leaves the hierarchy standing. A vocabulary gate inherited
    unchanged from the dasha corpus would pass this."""
    data = _corpus()
    data["planet"]["Jupiter"]["source"] = "The great benefic; Thursday's planet."
    msg = _expect_red(monkeypatch, data, G.test_no_banned_vocabulary)
    assert "benefic" in msg
    _expect_green(monkeypatch, G.test_no_banned_vocabulary)


def test_falsify_second_person_in_prose(monkeypatch) -> None:
    data = _corpus()
    data["nakshatra"]["Hasta"]["demand"] = (
        "The grip cannot be selective: what is strong enough to shape your work "
        "is strong enough to refuse to let it go."
    )
    msg = _expect_red(monkeypatch, data, G.test_second_person_is_absent_everywhere)
    assert "your" in msg
    _expect_green(monkeypatch, G.test_second_person_is_absent_everywhere)


def test_falsify_second_person_in_scaffolding(monkeypatch) -> None:
    """Second signature: `distinct_from` is authoring scaffolding and is excluded
    from the prose, share and skeleton gates. §4.1 says ZERO occurrences ANYWHERE,
    so it must not be excluded from this one."""
    data = _corpus()
    data["planet"]["Ketu"]["distinct_from"]["because"] = (
        "Ketu has finished with what you still want"
    )
    msg = _expect_red(monkeypatch, data, G.test_second_person_is_absent_everywhere)
    assert "distinct_from" in msg
    _expect_green(monkeypatch, G.test_second_person_is_absent_everywhere)


def test_falsify_reader_class_third_person(monkeypatch) -> None:
    """§4.2 — second person wearing a coat, and it clears the §4.1 regex."""
    data = _corpus()
    data["nakshatra"]["Ashwini"]["governs"] = (
        "Ashwini is onset, and those born under it move before the others do, "
        "which is the swift relief that arrives ahead of any full account at all."
    )
    msg = _expect_red(monkeypatch, data, G.test_no_reader_class_third_person)
    assert "those born under" in msg
    _expect_green(monkeypatch, G.test_no_reader_class_third_person)


def test_falsify_prediction_phrase(monkeypatch) -> None:
    data = _corpus()
    data["planet"]["Saturn"]["demand"] = (
        "It will bring the same object late that another graha brings early."
    )
    msg = _expect_red(monkeypatch, data, G.test_no_prediction_shapes)
    assert "will bring" in msg
    _expect_green(monkeypatch, G.test_no_prediction_shapes)


def test_falsify_bare_will_outside_source(monkeypatch) -> None:
    """Second signature: `will` alone is permitted in `source` and banned in the
    three prose fields. A phrase-list-only gate passes this."""
    data = _corpus()
    data["house"]["house_10"]["demand"] = (
        "A record will stay public once it is public, and the version others hold "
        "is the one that counts."
    )
    msg = _expect_red(monkeypatch, data, G.test_no_prediction_shapes)
    assert "bare `will`" in msg
    _expect_green(monkeypatch, G.test_no_prediction_shapes)


def test_falsify_remedy_vocabulary(monkeypatch) -> None:
    data = _corpus()
    data["planet"]["Saturn"]["source"] = "Age, long labour; Saturday's blue sapphire."
    msg = _expect_red(monkeypatch, data, G.test_no_remedies)
    assert "sapphire" in msg
    _expect_green(monkeypatch, G.test_no_remedies)


def test_falsify_remedy_reaches_the_ritual_half(monkeypatch) -> None:
    """Second signature: Block 5B cut the whole surface, not only the shop half."""
    data = _corpus()
    data["nakshatra"]["Pushya"]["demand"] = (
        "It cannot be drawn on faster than a mantra can replenish it, and a source "
        "only drawn from runs dry."
    )
    msg = _expect_red(monkeypatch, data, G.test_no_remedies)
    assert "mantra" in msg
    _expect_green(monkeypatch, G.test_no_remedies)


def test_falsify_attribution_word_in_prose(monkeypatch) -> None:
    """§4.4 — attribution lives in the `source` FIELD, never sprinkled in prose."""
    data = _corpus()
    data["house"]["house_9"]["governs"] = (
        "The ninth house is traditionally the frame reasoning happens inside, with "
        "teachers, doctrine, law, distant travel and luck nobody can account for."
    )
    msg = _expect_red(monkeypatch, data, G.test_no_attribution_words_in_prose)
    assert "traditionally" in msg
    _expect_green(monkeypatch, G.test_no_attribution_words_in_prose)


def test_falsify_lordship_jargon_outside_source(monkeypatch) -> None:
    """The carve-out is for `source` ONLY. Proving the carve-out has an edge is
    the whole point of carving it out narrowly."""
    data = _corpus()
    data["planet"]["Mars"]["governs"] = (
        "Mars is the lord of force applied deliberately, the boundary defended, "
        "the contest entered, surgery, machinery, and land held by whoever can."
    )
    msg = _expect_red(monkeypatch, data, G.test_no_astrological_jargon)
    assert "lord" in msg
    _expect_green(monkeypatch, G.test_no_astrological_jargon)


def test_falsify_excluded_system(monkeypatch) -> None:
    """§1.1 — a sub-lord reading can never be connected to a reader's real data,
    because the engine does not compute one."""
    data = _corpus()
    data["nakshatra"]["Swati"]["governs"] = (
        "Swati is unattached motion read through its navamsa — wind, trade, the "
        "going to and fro that moves value, and the give of anything not pinned."
    )
    msg = _expect_red(monkeypatch, data, G.test_no_systems_the_engine_cannot_compute)
    assert "navamsa" in msg
    _expect_green(monkeypatch, G.test_no_systems_the_engine_cannot_compute)


def test_falsify_subject_discipline(monkeypatch) -> None:
    """§4.3 — `governs` must open on the thing itself, not on a subjectless
    generality that the second-person ban alone would happily admit."""
    data = _corpus()
    data["nakshatra"]["Rohini"]["governs"] = (
        "Growth from a seed is the whole matter here — sowing, the founding of a "
        "settlement, cattle and increase, and value that comes from being left."
    )
    msg = _expect_red(monkeypatch, data, G.test_subject_discipline_governs_opens_with_the_thing)
    assert "Rohini" in msg
    _expect_green(monkeypatch, G.test_subject_discipline_governs_opens_with_the_thing)


def test_falsify_dasha_period_lane(monkeypatch) -> None:
    """§6b's vocabulary lane: Dasha owns the PERIOD."""
    data = _corpus()
    data["planet"]["Ketu"]["governs"] = (
        "Ketu is the finished business of a period — a skill retained long after "
        "the wish to use it faded, and the part of a chart where searching ended."
    )
    msg = _expect_red(monkeypatch, data, G.test_knowledge_prose_avoids_the_dasha_period_lane)
    assert "period" in msg
    _expect_green(monkeypatch, G.test_knowledge_prose_avoids_the_dasha_period_lane)


# ── Fear symmetry (§7d) — falsified in BOTH directions ───────────────────────


def test_falsify_demand_length_symmetry_by_lengthening_a_hard_entry(monkeypatch) -> None:
    """Direction 1: Saturn gets the four-sentence treatment §3 describes."""
    data = _corpus()
    data["planet"]["Saturn"]["demand"] = (
        "It accepts no substitute for elapsed duration, it does not hurry, it does "
        "not negotiate, and what is bought early under it is never the same object "
        "as the one waited for, nor is it ever going to become that object later on."
    )
    msg = _expect_red(monkeypatch, data, G.test_demand_length_symmetry, "planet")
    assert "Saturn" in msg
    _expect_green(monkeypatch, G.test_demand_length_symmetry, "planet")


def test_falsify_demand_length_symmetry_by_shortening_the_easy_ones(monkeypatch) -> None:
    """Direction 2, and the one a per-entry gate cannot see: nothing is added to
    Saturn at all. Every EASY planet's demand is cut to a clause, which drags the
    median down until Saturn's untouched demand breaks the 1.5x ceiling. This is
    how the malefic hierarchy gets reproduced by an author who thinks they are
    only tightening prose."""
    data = _corpus()
    for name in ("Sun", "Moon", "Mercury", "Jupiter", "Venus"):
        data["planet"][name]["demand"] = "It cannot be had for nothing at all."
    msg = _expect_red(monkeypatch, data, G.test_demand_length_symmetry, "planet")
    assert "planet" in msg
    _expect_green(monkeypatch, G.test_demand_length_symmetry, "planet")


def test_falsify_density_parity_by_weighting_the_hard_group(monkeypatch) -> None:
    """Direction 1: dread built entirely from PERMITTED words. Zero banned
    vocabulary, second person absent, every length inside its band — and it reads
    as a sentence about suffering. No vocabulary gate on earth catches this one."""
    data = _corpus()
    data["house"]["house_8"]["demand"] = (
        "Nothing here can be taken back, nothing waits, and what it costs cannot "
        "be undone by whoever loses it."
    )
    data["house"]["house_6"]["demand"] = (
        "It never ends, it takes hard and costs hard, and nothing kept up ever "
        "stays up for long at all."
    )
    msg = _expect_red(monkeypatch, data, G.test_heavy_token_density_parity, "house")
    assert "over the 1.25x cap" in msg
    _expect_green(monkeypatch, G.test_heavy_token_density_parity, "house")


def test_falsify_density_parity_by_lightening_the_easy_group(monkeypatch) -> None:
    """Direction 2: the hard entries are untouched. The EASY houses are rewritten
    into reassurance — every heavy token removed — and the ratio breaks anyway.
    §3's warning is symmetric by construction and this is the half authors forget:
    Saturn may not read as doomed, AND Jupiter may not read as free."""
    data = _corpus()
    for key in ("house_1", "house_2", "house_3", "house_4", "house_5",
                "house_7", "house_9", "house_10", "house_11"):
        entry = data["house"][key]
        entry["governs"] = (
            f"The {key} sits among the twelve divisions and is read for its own "
            "settled area of ordinary living, which it holds open in a plain way."
        )
        entry["demand"] = "It asks only for an even and unhurried sort of attention."
    msg = _expect_red(monkeypatch, data, G.test_heavy_token_density_parity, "house")
    assert "NO heavy tokens at all" in msg
    _expect_green(monkeypatch, G.test_heavy_token_density_parity, "house")


def test_falsify_inverse_floor_on_the_easy_half(monkeypatch) -> None:
    """§7d.3's whole reason for existing: a costless Jupiter."""
    data = _corpus()
    data["planet"]["Jupiter"]["demand"] = (
        "Enlargement is simply not selective in how it works upon a chart."
    )
    msg = _expect_red(monkeypatch, data, G.test_inverse_floor_every_demand_has_weight, "planet")
    assert "Jupiter" in msg or "costless" in msg
    _expect_green(monkeypatch, G.test_inverse_floor_every_demand_has_weight, "planet")


def test_falsify_inverse_floor_on_the_hard_half(monkeypatch) -> None:
    """Second signature: the floor is not a rule about easy entries that happens
    to be worded generally. A gate that only policed the traditionally-easy half
    would pass this, and would have silently become one-sided."""
    data = _corpus()
    data["planet"]["Saturn"]["demand"] = (
        "It accepts one substitute for elapsed duration and asks for no other."
    )
    msg = _expect_red(monkeypatch, data, G.test_inverse_floor_every_demand_has_weight, "planet")
    assert "Saturn" in msg
    _expect_green(monkeypatch, G.test_inverse_floor_every_demand_has_weight, "planet")


def test_heavy_lexicon_cannot_be_trimmed_to_make_a_draft_pass(monkeypatch) -> None:
    """§7d.2's closing rule, falsified: removing a stem from HEAVY is how the
    density gates get defeated without a single line of copy changing."""
    trimmed = set(G.HEAVY) - {"cost", "never", "nothing"}
    monkeypatch.setattr(G, "HEAVY", trimmed)
    with pytest.raises(AssertionError) as exc:
        G.test_heavy_lexicon_is_the_spec_lexicon()
    assert "lost spec stems" in str(exc.value)


# ── Distinctness (§7c) and share (§7a) ───────────────────────────────────────


def test_falsify_shared_opening_frame(monkeypatch) -> None:
    data = _corpus()
    data["house"]["house_3"]["demand"] = (
        "A record cannot be borrowed for the occasion, and a reach never used "
        "shortens to the length actually practised by anybody."
    )
    data["house"]["house_10"]["demand"] = (
        "A record cannot be edited once it is public, and the version others hold "
        "is the one that counts."
    )
    msg = _expect_red(monkeypatch, data, G.test_no_two_entries_share_an_opening_frame, "house")
    assert "identically" in msg
    _expect_green(monkeypatch, G.test_no_two_entries_share_an_opening_frame, "house")


def test_falsify_shared_skeleton_with_the_name_swapped_in(monkeypatch) -> None:
    """Second signature, and the gate that caught dasha_content_v1: the two
    sentences share NO opening frame and no duplicate string. Only the skeleton
    reveals that one template is being filled in twice."""
    data = _corpus()
    data["planet"]["Venus"]["governs"] = (
        "Venus is attraction and its arrangements, marriage, refinement of "
        "surroundings, and the apparatus by which people are made agreeable."
    )
    data["planet"]["Mercury"]["governs"] = (
        "Mercury is exchange and its reckonings, commerce, translation of "
        "terms, and the discipline by which symbols are handled well."
    )
    shared = G._skeleton(data["planet"]["Venus"]["governs"]) == G._skeleton(
        data["planet"]["Mercury"]["governs"]
    )
    assert shared, "fixture no longer produces a shared skeleton"
    msg = _expect_red(monkeypatch, data, G.test_no_two_entries_share_a_sentence_skeleton, "planet")
    assert "skeleton" in msg
    _expect_green(monkeypatch, G.test_no_two_entries_share_a_sentence_skeleton, "planet")


def test_falsify_word_share_on_the_REAL_corpus(monkeypatch) -> None:
    """The share cap pushed one entry past its limit using an ordinary,
    natural-reading word — not a synthetic token. §7a caps a house content word
    at 3 of 12 entries, so a fourth is red."""
    data = _corpus()
    for key in ("house_1", "house_2", "house_3", "house_4"):
        data["house"][key]["source"] = data["house"][key]["source"].replace(
            "bhava —", "bhava — the settled matters,"
        )
    msg = _expect_red(monkeypatch, data, G.test_no_content_word_dominates, "house")
    assert "settled" in msg or "matters" in msg
    _expect_green(monkeypatch, G.test_no_content_word_dominates, "house")


def test_falsify_the_field_name_becoming_the_corpus_verb(monkeypatch) -> None:
    """Second signature on share: §7a singles out `governs` because it is the
    field name and will become the verb of all 48 entries. Asserted through the
    dedicated gate so the reason is legible at the point of failure."""
    data = _corpus()
    for key in ("Sun", "Moon", "Mars", "Mercury"):
        data["planet"][key]["governs"] = (
            f"{key} governs a wide field of ordinary matters, and it governs them "
            "in the plain sense that a reading looks there first of all for them."
        )
    msg = _expect_red(monkeypatch, data, G.test_governs_is_not_the_verb_of_every_entry)
    assert "corpus's verb" in msg
    _expect_green(monkeypatch, G.test_governs_is_not_the_verb_of_every_entry)


def test_share_thresholds_are_pinned_to_the_spec_table(monkeypatch) -> None:
    """A threshold loosened to make a draft pass must argue with §7a's table."""
    monkeypatch.setitem(G.MAX_ENTRY_SHARE, "house", 0.5)
    with pytest.raises(AssertionError):
        G.test_share_thresholds_match_the_spec_table()


# ── Cross-corpus collision (§6) — genuine violation AND vacuous pass ──────────


def test_falsify_identity_collision(monkeypatch) -> None:
    """§6a. Identity owns the PERSON; Knowledge owns the SYMBOL. The specific
    failure is identity's core claim rewritten in the third person."""
    data = _corpus()
    identity = json.loads(G.IDENTITY_SEED_PATH.read_text())["nakshatra"]
    borrowed = identity["Krittika"]["core"].split(".")[0]
    data["nakshatra"]["Krittika"]["governs"] = (
        "Krittika is separation by fire, and " + borrowed.lower() + " in materials."
    )
    msg = _expect_red(monkeypatch, data, G.test_no_shared_content_word_with_identity_content)
    assert "Krittika" in msg
    _expect_green(monkeypatch, G.test_no_shared_content_word_with_identity_content)


def test_falsify_identity_collision_cannot_pass_vacuously(monkeypatch) -> None:
    """Second signature — the FALLBACK-SHAPED violation. Rename a nakshatra key
    and the collision gate's work-list loses a pair; it would then pass by having
    nothing to check. That must be caught, and it is caught by the surface-size
    gate rather than by the collision gate, which is the honest division of
    labour: the collision gate compares, the surface gate proves there is
    something to compare."""
    data = _corpus()
    data["nakshatra"]["Krittica"] = data["nakshatra"].pop("Krittika")
    msg = _expect_red(monkeypatch, data, G.test_collision_surfaces_are_the_expected_size)
    assert "1:1" in msg
    _expect_green(monkeypatch, G.test_collision_surfaces_are_the_expected_size)


def test_falsify_dasha_collision(monkeypatch) -> None:
    """§6b. Dasha owns the PERIOD; Knowledge owns the PLANET."""
    data = _corpus()
    data["planet"]["Ketu"]["governs"] = (
        "Ketu is the finished business where enthusiasm has stopped, a skill "
        "retained after the wish to use it faded, and where searching concluded."
    )
    msg = _expect_red(monkeypatch, data, G.test_no_shared_content_word_with_dasha_content)
    assert "Ketu" in msg
    _expect_green(monkeypatch, G.test_no_shared_content_word_with_dasha_content)


def test_falsify_definitional_baseline_collision(monkeypatch) -> None:
    """§6c. A house entry that restates the shipped Block 7 card has added
    nothing and made the app repeat itself where a reader taps both."""
    data = _corpus()
    data["house"]["house_11"]["governs"] = (
        "The eleventh house is gains and networks and hopes, income from many "
        "directions at once, elder siblings, associations, and granted wishes."
    )
    gate = G.test_no_shared_content_word_with_the_definitional_house_card
    msg = _expect_red(monkeypatch, data, gate)
    assert "house_11" in msg
    _expect_green(monkeypatch, gate)


def test_falsify_baseline_shape(monkeypatch) -> None:
    """Second signature on §6c: the baseline is a COPY, and a copy that has
    drifted out of the shipped card's `N — a, b, c` shape is no longer a copy of
    anything. This is the mechanical half; sync is the human half (§7f)."""
    data = _corpus()
    data["_about"]["definitional_baseline"]["house_4"] = "home and mother and comfort"
    msg = _expect_red(monkeypatch, data, G.test_definitional_baseline_is_the_shipped_twelve_lines)
    assert "house_4" in msg
    _expect_green(monkeypatch, G.test_definitional_baseline_is_the_shipped_twelve_lines)


# ── SOURCE CITATION — the accuracy standard ──────────────────────────────────


def test_falsify_uncitable_source(monkeypatch) -> None:
    data = _corpus()
    data["nakshatra"]["Mula"]["source_ref"] = "Widely known in modern nakshatra writing"
    msg = _expect_red(monkeypatch, data, G.test_every_entry_cites_a_classical_source)
    assert "not parseable" in msg
    _expect_green(monkeypatch, G.test_every_entry_cites_a_classical_source)


def test_falsify_citation_with_a_real_text_but_no_locus(monkeypatch) -> None:
    """Second signature, and the shape a lazy citation actually takes: it names a
    real classical text and points at none of it. BPHS has 97 chapters; `BPHS —
    the planets` is a gesture, not a reference, and a non-empty check passes it."""
    data = _corpus()
    data["planet"]["Venus"]["source_ref"] = "BPHS — the planets and their natures"
    msg = _expect_red(monkeypatch, data, G.test_every_entry_cites_a_classical_source)
    assert "Venus" in msg
    _expect_green(monkeypatch, G.test_every_entry_cites_a_classical_source)


def test_falsify_a_category_resting_on_one_text(monkeypatch) -> None:
    """A corpus where every entry in a category cites one chapter has a citation
    habit, not a grounding."""
    data = _corpus()
    for entry in data["house"].values():
        entry["source_ref"] = "BPHS 11 — the bhava significations"
    msg = _expect_red(monkeypatch, data, G.test_no_category_rests_on_a_single_text)
    assert "house cites only" in msg
    _expect_green(monkeypatch, G.test_no_category_rests_on_a_single_text)


def test_falsify_citation_leaking_into_the_source_field(monkeypatch) -> None:
    """§5 keeps `source` plain-English and `source_ref` citable. Collapsing them
    is how the rendered field becomes unreadable and the audit trail becomes
    prose."""
    data = _corpus()
    data["house"]["house_6"]["source"] = "Ripu bhava, per BPHS 11 — service and debts."
    msg = _expect_red(monkeypatch, data, G.test_source_field_is_plain_english_not_a_citation)
    assert "house_6" in msg
    _expect_green(monkeypatch, G.test_source_field_is_plain_english_not_a_citation)


def test_falsify_an_unlogged_reframing(monkeypatch) -> None:
    """Binding editorial rule 2: every difficult signification's reframing is
    LOGGED. The log cannot quietly shrink to the entries someone remembered."""
    data = _corpus()
    data["_about"]["editorial_reframings"] = [
        r for r in data["_about"]["editorial_reframings"] if r["entry"] != "house_12"
    ]
    msg = _expect_red(monkeypatch, data, G.test_every_hard_entry_logs_its_reframing)
    assert "house_12" in msg
    _expect_green(monkeypatch, G.test_every_hard_entry_logs_its_reframing)


def test_falsify_a_reframing_log_with_no_rationale(monkeypatch) -> None:
    """Second signature: a log of sixteen entries each saying "softened" is a
    list, not a record of editorial choices."""
    data = _corpus()
    data["_about"]["editorial_reframings"][0]["why"] = "reads better"
    msg = _expect_red(monkeypatch, data, G.test_every_hard_entry_logs_its_reframing)
    assert "rationale too thin" in msg
    _expect_green(monkeypatch, G.test_every_hard_entry_logs_its_reframing)


def test_the_hard_nakshatra_group_is_not_the_authors_opinion(monkeypatch) -> None:
    """§3 requires the nakshatra hard group be READ from the seeded trait table,
    and this asserts that table against Brihat Samhita 98.7-8. Falsified by
    editing the trait table: if score_rules ever drifts, the density gate's claim
    to objectivity goes with it, and this fails rather than the gate silently
    grading a different nine."""
    original = G._seeded_nakshatra_traits
    monkeypatch.setattr(
        G, "_seeded_nakshatra_traits", lambda: {**original(), 3: "ugra"}
    )
    with pytest.raises(AssertionError):
        G.test_hard_nakshatras_match_brihat_samhita_98()


# ── §8 — the review checkpoints ──────────────────────────────────────────────


def test_falsify_shippable_without_checkpoint_b(monkeypatch) -> None:
    """The gate that stops this corpus reaching a reader. §8 Checkpoint B BLOCKS
    SHIP, and the flag the Worker echoes may not be flipped by hand."""
    data = _corpus()
    data["_about"]["shippable"] = True
    msg = _expect_red(monkeypatch, data, G.test_corpus_is_not_marked_shippable_without_checkpoint_b)
    assert "a writer cannot own that" in msg
    _expect_green(monkeypatch, G.test_corpus_is_not_marked_shippable_without_checkpoint_b)


def test_falsify_shippable_signed_off_by_a_non_astrologer(monkeypatch) -> None:
    """Second signature, and the failure that would actually happen: checkpoint_b
    is filled in completely, honestly, with a real name and a real date and zero
    entries marked inaccurate — by somebody who is not an astrologer. §8 is
    explicit that this is the one question only a practitioner can answer, so an
    honest non-astrologer sign-off must still not make the corpus shippable."""
    data = _corpus()
    data["_about"]["astrologer_review"]["checkpoint_b"] = {
        "reviewer": "The product owner",
        "reviewer_is_astrologer": False,
        "date": "2026-07-26",
        "verdict": "approved",
        "entries_marked_inaccurate": 0,
        "scope": "read all 48 and they seem right",
    }
    data["_about"]["shippable"] = True
    msg = _expect_red(monkeypatch, data, G.test_corpus_is_not_marked_shippable_without_checkpoint_b)
    assert "checkpoint_b approval is False" in msg
    _expect_green(monkeypatch, G.test_corpus_is_not_marked_shippable_without_checkpoint_b)


def test_falsify_full_corpus_without_a_sample_review(monkeypatch) -> None:
    """§8: authoring does not proceed past nine entries until the axis is
    approved."""
    data = _corpus()
    data["_about"]["astrologer_review"]["checkpoint_a"]["verdict"] = "pending"
    msg = _expect_red(monkeypatch, data, G.test_sample_review_recorded_before_full_corpus)
    assert "authoring does not proceed" in msg
    _expect_green(monkeypatch, G.test_sample_review_recorded_before_full_corpus)


def test_falsify_an_unrecorded_sample_shortfall(monkeypatch) -> None:
    """The deviation gate. §8 mandates Ketu, house_8 and one of Ashlesha/Mula.
    The real sample misses two of three and SAYS SO in spec_deviations. Delete
    that record and the corpus is claiming a compliance it does not have — which
    is the exact difference §8 draws between a false entry and a forgotten one."""
    data = _corpus()
    data["_about"]["astrologer_review"]["spec_deviations"] = [
        "A sixth field, source_ref, was added to the five-field spine."
    ]
    gate = G.test_checkpoint_a_sample_deviation_is_recorded_not_omitted
    msg = _expect_red(monkeypatch, data, gate)
    assert "spec_deviations does not say so" in msg
    _expect_green(monkeypatch, gate)


def test_falsify_an_implied_reviewer_qualification(monkeypatch) -> None:
    """A review record that names a reviewer without stating whether they are an
    astrologer lets a product sign-off be read later as a practitioner's."""
    data = _corpus()
    del data["_about"]["astrologer_review"]["checkpoint_a"]["reviewer_is_astrologer"]
    msg = _expect_red(monkeypatch, data, G.test_reviewer_qualification_is_stated_not_implied)
    assert "explicit boolean" in msg
    _expect_green(monkeypatch, G.test_reviewer_qualification_is_stated_not_implied)


def test_falsify_complete_without_checkpoint_b(monkeypatch) -> None:
    """§8's second gate: `status` COMPLETE requires checkpoint_b approved with
    zero entries marked inaccurate."""
    data = _corpus()
    data["_about"]["status"] = "COMPLETE — 48 of 48 entries, all gates green."
    msg = _expect_red(monkeypatch, data, G.test_full_review_recorded_before_complete)
    assert "pending" in msg
    _expect_green(monkeypatch, G.test_full_review_recorded_before_complete)
