"""Falsification suite: proof that every identity gate actually FIRES.

A gate nobody has watched go red is not a gate — it is a comment that happens to
be executable. `content_v3_2` shipped green past three verified steps because
nothing tested the *joins* between them, and `/v1/health`'s drift alarm was only
trusted once it had been made to fire on purpose. This file is that discipline
applied to the identity corpus, before the corpus is large enough for a silent
hole to be expensive.

## Method

Every test here mutates an in-memory copy of the real seed and monkeypatches
`_load`, then calls **the actual gate function** from
`test_identity_content_seed.py` — never a reimplementation of it. A
reimplementation would prove that a copy of the logic works, which is precisely
the thing that is not in question. `_expect_red` asserts the gate raises;
`_expect_green` re-asserts it passes on the unmutated corpus immediately after,
so a gate that has been accidentally broken into always-failing cannot be
mistaken for a gate that discriminates.

## Multiple signatures where a violation could short-circuit

The prior task's lesson: a gate can stay green under a *fallback-shaped*
violation, one that removes the thing being checked instead of corrupting it.
Two gates here have that shape and are falsified twice each:

* **The cross-corpus collision gate** derives its work-list from
  `seeded_pairs()`. A corpus that misspells a key does not fail the gate — it
  shrinks the gate's input to nothing and passes vacuously. So it is falsified
  with (1) a genuine shared word, and (2) a shrunk pair set, which must be
  caught by the coverage gate instead.
* **The contrast-graph gate** skips targets outside the authored set. A violation
  that points every contrast at an unauthored nakshatra leaves the authored graph
  empty rather than corrupt. Falsified with (1) a self-contrast, (2) both targets
  aimed outside the authored set.

## The word-share gate, which cannot be falsified on the pilot

It skips at n=3/n=4 by design (see the seed test's docstring). Skipping it here
too would leave the corpus's only lexical backstop entirely unproven, so it is
falsified against a **synthetic full-size corpus** — 27 and 12 generated entries
— which is the only way to see it fire at the denominator the spec derives it
against.
"""

from __future__ import annotations

import copy
import json

import pytest

from tests import test_identity_content_seed as G


def _corpus() -> dict:
    return copy.deepcopy(json.loads(G.SEED_PATH.read_text()))


def _expect_red(monkeypatch, data: dict, gate, *args) -> str:
    """Run a gate against a mutated corpus and require it to fail."""
    monkeypatch.setattr(G, "_load", lambda: data)
    with pytest.raises(AssertionError) as exc:
        gate(*args)
    return str(exc.value)


def _expect_green(monkeypatch, gate, *args) -> None:
    """Restore the real corpus and require the same gate to pass."""
    monkeypatch.setattr(G, "_load", lambda: json.loads(G.SEED_PATH.read_text()))
    gate(*args)


# ── Structure ────────────────────────────────────────────────────────────────


def test_falsify_word_count_bounds(monkeypatch) -> None:
    data = _corpus()
    data["nakshatra"]["Krittika"]["core"] = "You are precise. You notice things."
    msg = _expect_red(monkeypatch, data, G.test_nakshatra_entries_well_formed)
    assert "spec says 35-55" in msg
    _expect_green(monkeypatch, G.test_nakshatra_entries_well_formed)


def test_falsify_shipped_length_target(monkeypatch) -> None:
    data = _corpus()
    entry = data["moon_sign"]["Taurus"]
    entry["need"] = entry["need"] + " " + entry["need"]
    msg = _expect_red(monkeypatch, data, G.test_moon_sign_entries_well_formed)
    assert "sentences" in msg or "words" in msg
    _expect_green(monkeypatch, G.test_moon_sign_entries_well_formed)


def test_falsify_unknown_key(monkeypatch) -> None:
    data = _corpus()
    data["nakshatra"]["Krittica"] = data["nakshatra"].pop("Krittika")
    msg = _expect_red(monkeypatch, data, G.test_keys_are_canonical_names)
    assert "unknown nakshatra key" in msg
    _expect_green(monkeypatch, G.test_keys_are_canonical_names)


# ── Voice ────────────────────────────────────────────────────────────────────


def test_falsify_banned_vocabulary(monkeypatch) -> None:
    data = _corpus()
    data["nakshatra"]["Krittika"]["misread"] = (
        "Read as harshness, when it is destiny that you cannot unsee the wrong part."
    )
    msg = _expect_red(monkeypatch, data, G.test_no_banned_vocabulary)
    assert "destiny" in msg
    _expect_green(monkeypatch, G.test_no_banned_vocabulary)


def test_falsify_banned_vocabulary_reaches_contrast_reasons(monkeypatch) -> None:
    """Second signature: contrast is excluded from the prose gates, so this
    confirms it is NOT excluded from the safety gate."""
    data = _corpus()
    data["nakshatra"]["Krittika"]["contrast"][0]["because"] = "a fated difference"
    msg = _expect_red(monkeypatch, data, G.test_no_banned_vocabulary)
    assert "fated" in msg and "contrast" in msg
    _expect_green(monkeypatch, G.test_no_banned_vocabulary)


def test_falsify_astrological_jargon(monkeypatch) -> None:
    data = _corpus()
    data["moon_sign"]["Aries"]["unsettles"] = (
        "An open week with nothing in it, and a debilitated sense that you should enjoy it."
    )
    msg = _expect_red(monkeypatch, data, G.test_no_astrological_jargon)
    assert "debilitated" in msg
    _expect_green(monkeypatch, G.test_no_astrological_jargon)


@pytest.mark.parametrize("carrier", [
    "Deep down, you see the flaw first.",
    "Part of you sees the flaw before the whole.",
    "At times you see the flaw before the whole.",
    "You have a tendency to see the flaw first.",
    "Sometimes you cut, and sometimes you let it stand.",
    "Secretly you would rather remove than add.",
])
def test_falsify_every_barnum_carrier_class(monkeypatch, carrier: str) -> None:
    """§2's carriers are the single most likely way this corpus fails, so each
    class is fired individually rather than trusting one representative."""
    data = _corpus()
    data["nakshatra"]["Krittika"]["misread"] = carrier
    msg = _expect_red(monkeypatch, data, G.test_no_barnum_carriers)
    assert "Barnum carrier" in msg
    _expect_green(monkeypatch, G.test_no_barnum_carriers)


@pytest.mark.parametrize("shape", [
    "Your only flaw is that the work matters to you.",
    "You care too much about getting it right.",
    "You hold yourself to a higher standard than the room does.",
    "You are too loyal to the people who bring you drafts.",
])
def test_falsify_every_humblebrag_shape(monkeypatch, shape: str) -> None:
    data = _corpus()
    data["nakshatra"]["Krittika"]["cost"] = shape
    msg = _expect_red(monkeypatch, data, G.test_no_humblebrag_shapes)
    assert "humblebrag" in msg
    _expect_green(monkeypatch, G.test_no_humblebrag_shapes)


def test_falsify_hedge_cap(monkeypatch) -> None:
    """One hedge is allowed; two is the violation. Fired at exactly the boundary,
    because a cap that only fires at five would pass hedged copy all day."""
    data = _corpus()
    data["nakshatra"]["Krittika"]["misread"] = (
        "You may often be read as harsh, when you might simply be unable to unsee it."
    )
    msg = _expect_red(monkeypatch, data, G.test_hedge_density_per_entry)
    assert "hedges" in msg
    _expect_green(monkeypatch, G.test_hedge_density_per_entry)


def test_hedge_cap_permits_exactly_one(monkeypatch) -> None:
    """The other half of the boundary: the gate must not be so eager it bans
    hedging outright. Uttara Ashadha ships one `usually` and must stay green."""
    data = _corpus()
    joined = " ".join(data["nakshatra"]["Uttara Ashadha"][f] for f in G.NAKSHATRA_PROSE)
    assert len(G.HEDGE_RE.findall(joined)) == 1
    monkeypatch.setattr(G, "_load", lambda: data)
    G.test_hedge_density_per_entry()


def test_falsify_second_person(monkeypatch) -> None:
    data = _corpus()
    data["nakshatra"]["Krittika"]["cost"] = (
        "People stop showing work before it is finished, so the room goes careful."
    )
    msg = _expect_red(monkeypatch, data, G.test_core_and_cost_are_second_person)
    assert "not second person" in msg
    _expect_green(monkeypatch, G.test_core_and_cost_are_second_person)


# ── Vocabulary lanes ─────────────────────────────────────────────────────────


def test_falsify_nakshatra_lane(monkeypatch) -> None:
    data = _corpus()
    data["nakshatra"]["Krittika"]["core"] = (
        "You need the work to be right, and you need to say so before anyone else "
        "does. Handed something half-built, your instinct is subtraction rather "
        "than addition, every single time you are asked."
    )
    msg = _expect_red(
        monkeypatch, data, G.test_nakshatra_copy_never_names_an_emotional_need
    )
    assert "moon-sign lane" in msg
    _expect_green(monkeypatch, G.test_nakshatra_copy_never_names_an_emotional_need)


def test_falsify_moon_sign_lane(monkeypatch) -> None:
    data = _corpus()
    data["moon_sign"]["Taurus"]["unsettles"] = (
        "Being asked to decide quickly by someone who assumed you would not mind."
    )
    msg = _expect_red(
        monkeypatch, data, G.test_moon_sign_copy_never_names_a_behaviour_under_pressure
    )
    assert "nakshatra lane" in msg
    _expect_green(
        monkeypatch, G.test_moon_sign_copy_never_names_a_behaviour_under_pressure
    )


# ── Contrast: well-formedness ────────────────────────────────────────────────


def test_falsify_contrast_target_not_a_nakshatra(monkeypatch) -> None:
    data = _corpus()
    data["nakshatra"]["Krittika"]["contrast"][0]["nakshatra"] = "Taurus"
    msg = _expect_red(monkeypatch, data, G.test_contrast_fields_well_formed)
    assert "not a nakshatra" in msg
    _expect_green(monkeypatch, G.test_contrast_fields_well_formed)


def test_falsify_contrast_wrong_cardinality(monkeypatch) -> None:
    data = _corpus()
    data["nakshatra"]["Krittika"]["contrast"] = data["nakshatra"]["Krittika"]["contrast"][:1]
    msg = _expect_red(monkeypatch, data, G.test_contrast_fields_well_formed)
    assert "exactly 2 contrast targets" in msg
    _expect_green(monkeypatch, G.test_contrast_fields_well_formed)


def test_falsify_contrast_duplicate_targets(monkeypatch) -> None:
    data = _corpus()
    c = data["nakshatra"]["Krittika"]["contrast"]
    c[1]["nakshatra"] = c[0]["nakshatra"]
    msg = _expect_red(monkeypatch, data, G.test_contrast_fields_well_formed)
    assert "same contrast twice" in msg
    _expect_green(monkeypatch, G.test_contrast_fields_well_formed)


# ── Contrast graph: TWO signatures (fallback-shaped violation risk) ──────────


def test_falsify_contrast_graph_signature_1_self_contrast(monkeypatch) -> None:
    data = _corpus()
    data["nakshatra"]["Krittika"]["contrast"][0]["nakshatra"] = "Krittika"
    msg = _expect_red(monkeypatch, data, G.test_contrast_fields_well_formed)
    assert "contrasts with itself" in msg
    _expect_green(monkeypatch, G.test_contrast_fields_well_formed)


def test_falsify_contrast_graph_signature_2_aimed_outside(monkeypatch) -> None:
    """The fallback-shaped one. Pointing every contrast at an UNAUTHORED
    nakshatra is valid per-entry — each target is a real name and not itself —
    so the well-formedness gate stays green. Only the connectivity gate catches
    it, and only because it asserts over the authored set rather than skipping
    when the authored set has no inbound edges.
    """
    data = _corpus()
    for entry, targets in zip(
        data["nakshatra"].values(),
        [("Revati", "Ardra"), ("Rohini", "Pushya"), ("Magha", "Swati")],
    ):
        for c, target in zip(entry["contrast"], targets):
            c["nakshatra"] = target

    monkeypatch.setattr(G, "_load", lambda: data)
    G.test_contrast_fields_well_formed()  # still green — that is the point

    msg = _expect_red(monkeypatch, data, G.test_contrast_graph_is_connected)
    assert "named as a contrast by no other authored entry" in msg
    _expect_green(monkeypatch, G.test_contrast_graph_is_connected)


# ── Distinctness ─────────────────────────────────────────────────────────────


def test_falsify_duplicate_string(monkeypatch) -> None:
    data = _corpus()
    data["nakshatra"]["Purva Ashadha"]["misread"] = data["nakshatra"]["Krittika"]["misread"]
    msg = _expect_red(monkeypatch, data, G.test_every_shipped_string_is_unique)
    assert "duplicated string" in msg
    _expect_green(monkeypatch, G.test_every_shipped_string_is_unique)


def test_falsify_shared_opening_frame(monkeypatch) -> None:
    """The two Ashadhas are the corpus's closest pair, so they are the honest
    place to fire this: give them the same four opening words and the gate must
    refuse them even though the rest of the sentence differs."""
    data = _corpus()
    data["nakshatra"]["Uttara Ashadha"]["core"] = (
        "You decide you are the last one left in the room, and you let the others "
        "wear themselves out first. Where they arrive loud and go, you remain in "
        "month nine, which is when it finally moves."
    )
    msg = _expect_red(monkeypatch, data, G.test_no_two_entries_share_an_opening_frame)
    assert "open their core identically" in msg
    assert "you decide you are" in msg
    _expect_green(monkeypatch, G.test_no_two_entries_share_an_opening_frame)


def test_falsify_shared_skeleton(monkeypatch) -> None:
    """The dasha_content_v1 regression, in identity form: the same sentence with
    the name swapped in. Content words differ entirely; only the function-word
    scaffold is shared, and that is what must be caught."""
    data = _corpus()
    source = data["nakshatra"]["Krittika"]["misread"]
    # "Read as harshness, when what is actually happening is that you cannot
    #  unsee the one part that is wrong." -> same skeleton, new content words.
    data["nakshatra"]["Uttara Ashadha"]["misread"] = (
        "Judged as stubbornness, when what is really occurring is that you cannot "
        "abandon the one promise that is old."
    )
    assert G._skeleton(source) == G._skeleton(
        data["nakshatra"]["Uttara Ashadha"]["misread"]
    ), "the fixture must actually share a skeleton, or this proves nothing"
    msg = _expect_red(monkeypatch, data, G.test_no_two_entries_share_a_sentence_skeleton)
    assert "share a sentence skeleton" in msg
    _expect_green(monkeypatch, G.test_no_two_entries_share_a_sentence_skeleton)


def test_title_skeleton_carve_out_is_real(monkeypatch) -> None:
    """The carve-out must be load-bearing, not decorative: two titles sharing a
    skeleton must pass, while two identical titles must still fail on the
    exact-string gate. A carve-out that never matters is one that was never
    needed, and one that swallows duplicates is a hole."""
    data = _corpus()
    data["nakshatra"]["Krittika"]["title"] = "The eye that lands on the flaw"
    data["nakshatra"]["Purva Ashadha"]["title"] = "The hand that closes on the win"
    assert G._skeleton(data["nakshatra"]["Krittika"]["title"]) == G._skeleton(
        data["nakshatra"]["Purva Ashadha"]["title"]
    )
    monkeypatch.setattr(G, "_load", lambda: data)
    G.test_no_two_entries_share_a_sentence_skeleton()  # green: carved out

    data["nakshatra"]["Purva Ashadha"]["title"] = data["nakshatra"]["Krittika"]["title"]
    msg = _expect_red(monkeypatch, data, G.test_every_shipped_string_is_unique)
    assert "duplicated string" in msg
    _expect_green(monkeypatch, G.test_every_shipped_string_is_unique)


# ── Cross-corpus collision: TWO signatures ───────────────────────────────────


def test_falsify_cross_corpus_signature_1_shared_word(monkeypatch) -> None:
    """Krittika co-occurs with Taurus. Put one content word on both halves of
    that screen and the gate must refuse it — zero tolerance, per §6d.1."""
    data = _corpus()
    data["moon_sign"]["Taurus"]["unsettles"] = (
        "Being moved by someone who assumed you would not mind the harshness of it, "
        "because you rarely say so."
    )
    msg = _expect_red(
        monkeypatch, data, G.test_no_shared_content_word_across_a_co_occurring_pair
    )
    assert "harshness" in msg and "Krittika" in msg and "Taurus" in msg
    _expect_green(
        monkeypatch, G.test_no_shared_content_word_across_a_co_occurring_pair
    )


def test_falsify_cross_corpus_signature_2_vacuous_pass(monkeypatch) -> None:
    """The fallback-shaped violation, and the reason the coverage gate exists.

    Rename the moon-sign keys and the collision gate's work-list empties: it
    iterates zero pairs and passes, reporting nothing wrong, while the corpus it
    was supposed to protect is entirely unchecked. This is precisely the shape
    that let content_v3_2 stay green. The collision gate CANNOT catch it — so
    the coverage gate must, and this test proves the division of labour holds
    in both directions.
    """
    data = _corpus()
    data["moon_sign"] = {"Gemini": data["moon_sign"]["Taurus"]}
    assert G.seeded_pairs(data) == [], "fixture must actually empty the work-list"

    monkeypatch.setattr(G, "_load", lambda: data)
    G.test_no_shared_content_word_across_a_co_occurring_pair()  # vacuously GREEN

    msg = _expect_red(monkeypatch, data, G.test_seeded_pairs_cover_real_co_occurrences)
    assert "co-occurring pairs are seeded" in msg
    _expect_green(monkeypatch, G.test_seeded_pairs_cover_real_co_occurrences)


def test_falsify_cross_corpus_shared_skeleton(monkeypatch) -> None:
    data = _corpus()
    source = data["nakshatra"]["Uttara Ashadha"]["misread"]
    data["moon_sign"]["Capricorn"]["unsettles"] = (
        "Measured by progress, when it is nearer to a demand to be the one who counts."
    )
    if G._skeleton(source) != G._skeleton(data["moon_sign"]["Capricorn"]["unsettles"]):
        data["moon_sign"]["Capricorn"]["unsettles"] = source
    msg = _expect_red(
        monkeypatch, data, G.test_no_shared_skeleton_across_a_co_occurring_pair
    )
    assert "share a sentence skeleton on one screen" in msg
    _expect_green(monkeypatch, G.test_no_shared_skeleton_across_a_co_occurring_pair)


# ── The co-occurrence derivation itself ──────────────────────────────────────


def test_falsify_the_pair_derivation(monkeypatch) -> None:
    """The 36-pair claim underwrites the collision gate's affordability. If the
    arithmetic drifts, the gate silently changes scope, so the derivation is
    itself falsified: perturb the arc and the count must move off 36."""
    real = G.co_occurring_pairs()
    assert len(real) == 36

    monkeypatch.setattr(G, "NAKSHATRAS", G.NAKSHATRAS[:26])
    assert len(G.co_occurring_pairs()) != 36
    monkeypatch.undo()
    assert len(G.co_occurring_pairs()) == 36


# ── Word share: falsified against a SYNTHETIC FULL corpus ───────────────────


def _token(*parts: int) -> str:
    """A unique LETTERS-ONLY token.

    `WORD_RE` is `[a-z'-]+`, so digits are separators, not characters: a naive
    fixture word like `alpha0beta0` tokenises to `alpha` + `beta` and collides in
    every entry, which makes the fixture — not the gate — fail. Encoding the
    indices as letters keeps each token a single word. (This cost one debugging
    round and is recorded so the next author does not repeat it.)
    """
    return "z" + "q".join("".join(chr(ord("a") + int(d)) for d in str(p)) for p in parts)


def _synthetic(kind: str, n: int, filler_word: str, repeat_in: int) -> dict:
    """A full-size corpus where `filler_word` appears in exactly `repeat_in`
    entries and every other content word is unique per entry."""
    fields = G.NAKSHATRA_PROSE if kind == "nakshatra" else G.MOON_SIGN_PROSE
    names = (G.NAKSHATRAS if kind == "nakshatra" else G.SIGNS)[:n]
    entries = {}
    for i, name in enumerate(names):
        body = " ".join(_token(i, j) for j in range(6))
        if i < repeat_in:
            body += f" {filler_word}"
        entries[name] = {f: f"{_token(i, 90 + k)} {body}" for k, f in enumerate(fields)}
    return {"version": "synthetic", kind: entries}


@pytest.mark.parametrize("kind,n,at_limit,over_limit", [
    # IDENTITY.md §6a: nakshatra fails at 6 entries, moon sign at 4.
    ("nakshatra", G.FULL_NAKSHATRA_N, 5, 6),
    ("moon_sign", G.FULL_MOON_SIGN_N, 3, 4),
])
def test_falsify_word_share_at_full_corpus_size(
    kind: str, n: int, at_limit: int, over_limit: int
) -> None:
    """Fired at BOTH sides of the spec's stated boundary — the only way to prove
    the threshold is the one IDENTITY.md's table describes, rather than merely
    some threshold. This is also the gate's only proof at all: it skips on the
    pilot corpus, so without this it would ship entirely unexercised."""
    fields = G.NAKSHATRA_PROSE if kind == "nakshatra" else G.MOON_SIGN_PROSE

    assert G._share_limit(kind, n) == at_limit

    ok = _synthetic(kind, n, "template", at_limit)
    assert not G.check_word_share(ok, kind, fields), (
        f"{kind}: a word in exactly {at_limit} entries is AT the limit and must pass"
    )

    bad = _synthetic(kind, n, "template", over_limit)
    offenders = G.check_word_share(bad, kind, fields)
    assert offenders == {"template": over_limit}, (
        f"{kind}: a word in {over_limit} entries must fail, got {offenders}"
    )


def test_falsify_word_share_frame_exemption_is_narrow() -> None:
    """The exemption must cover the frame words and nothing else. `star` in every
    entry passes; `work` in every entry does not — §6a names `work` specifically
    as a word this corpus will drift toward."""
    fields = G.NAKSHATRA_PROSE
    n = G.FULL_NAKSHATRA_N

    exempt = _synthetic("nakshatra", n, "star", n)
    assert not G.check_word_share(exempt, "nakshatra", fields), (
        "`star` is a frame word and must be exempt in all 27 entries"
    )

    drift = _synthetic("nakshatra", n, "work", n)
    assert G.check_word_share(drift, "nakshatra", fields) == {"work": n}, (
        "`work` is NOT exempt and must fail when it reaches every entry"
    )


def test_share_gate_skip_is_visible_not_silent() -> None:
    """The pilot skip is a known hole. It must be reachable only while the corpus
    is genuinely small, and must close on its own at full size — never require a
    human to remember to re-enable it."""
    for kind, full in (("nakshatra", G.FULL_NAKSHATRA_N), ("moon_sign", G.FULL_MOON_SIGN_N)):
        assert G._share_limit(kind, len(_corpus()[kind])) < 2  # skipping today
        assert G._share_limit(kind, full) >= 2  # runs at full size, automatically
