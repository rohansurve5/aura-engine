# Compatibility — Ashtakoota (Guna Milan) & Mangal Dosha — the Block-4 record

`engine/compatibility.py` computes the eight-koota tally and the Mangal (Kuja)
Dosha facts. This document records what is honestly computable, why this is a
*table lookup* and not an ephemeris cross-validation, where the references
genuinely disagree, the ethics position (the central risk of this whole block),
and what the product may truthfully claim. It is the compatibility sibling of
`docs/ASCENDANT.md`.

Scope note: this task built the **engine and the gates only**. No UI, no Worker
port, no Neon seed, no billing, no content authoring beyond the band-neutral
descriptor lines the gates guard. Muhurat is a separate task. Nothing here is
app-visible yet, so no deploy gate is wired (the binding condition for wiring
one is in §2).

## §1 — What is computable, honestly

**All eight kootas are computable *exactly* today**, because every one keys off
two quantities the engine already produces and already cross-validates to the
dasha standard:

* the **Moon nakshatra** (index 0–26), and
* the **Moon rashi** (sign 0–11).

Both are exact, geocentric, location-independent, and gate every aura-api deploy
(`crossval_natal.py`). So the *inputs* to guna milan are as trustworthy as
anything in the product.

| Koota | Max | Keys off | Exact today? |
|---|---|---|---|
| Varna | 1 | Moon rashi | ✅ exact |
| Vashya | 2 | Moon rashi | ✅ (whole-sign convention; see divergences) |
| Tara / Dina | 3 | Moon nakshatra | ✅ exact |
| Yoni | 4 | Moon nakshatra | ✅ (poles exact; middle values a soft spot) |
| Graha Maitri | 5 | Moon rashi lords | ✅ (poles exact; fractions a soft spot) |
| Gana | 6 | Moon nakshatra | ✅ exact |
| Bhakoot | 7 | Moon rashi | ✅ exact |
| Nadi | 8 | Moon nakshatra | ✅ exact |

**Computability is therefore NOT the binding constraint** — every koota is
computable. Two constraints that *are* binding, and that shape everything below:

1. **This is a deterministic table lookup, not an independent computation.**
   Unlike `positions`/`vimshottari`/`chart`, nothing here re-derives a number
   from the ephemeris; each koota is a classical constant table indexed by
   nakshatra/rashi plus trivial arithmetic (count mod 9, count mod 12). So the
   correctness question is not "does our math match a reference ephemeris" — it
   is "are our **tables** the canonical ones, and is our lookup the conventional
   one." See §2.

2. **The birth-time caveat is inherited, not new.** The koota math needs **no
   birth time** — it needs the Moon nakshatra/rashi, which the product already
   has (with the documented noon-assumption caveat when a birth time is
   unknown; the Moon crosses a nakshatra roughly daily, so a noon-assumed
   nakshatra is right ~76% of the time). Two people who both know their birth
   details get an exact tally. A guna milan built on an unknown birth time
   inherits exactly the same ~24% nakshatra-uncertainty the daily product
   already discloses — no better, no worse. **Mangal Dosha is the exception**
   (below).

### Mangal (Kuja / Manglik) Dosha

Mangal Dosha is "is Mars in one of the marked houses, counted from a reference
point." A3 made the lagna reference computable. We count from **three** classical
references and report each, because they degrade differently:

* **from the lagna** — needs a birth time (it is Mars's Whole-Sign house from
  the ascendant). Now computable exactly (A3). Absent a birth time there is **no
  lagna**, so this reference is simply unavailable — never fabricated from a noon
  chart (the `docs/ASCENDANT.md` rule).
* **from the Moon** and **from Venus** — need no birth time in principle, but
  both need Mars's *sign*, which comes from the same natal computation. The
  honest degradation is explicit in `mangal_dosha_from_moon`: with only a Moon
  and no chart, the assessment is **empty**, not a partial guess.

We report Mars's house from each available reference and **two** dosha sets:
the **strict** `{1,4,7,8,12}` and the **inclusive** set that adds the contested
**2nd house**. We never collapse to a single "manglik / not manglik" bit — the
2nd-house disagreement alone flips the answer for a large minority of charts, so
a single bit would be a false precision. The ethics position on Mangal is §3.

### Nothing was approximated. Nothing was cut for non-computability.

Per the task's stop-condition: every koota is computed exactly where the
tradition is unambiguous, and where the tradition is *ambiguous* we encode a
cited default and **surface enough detail that the number is transparent** —
we did not approximate a koota into existence, and we did not need to cut one
for being incomputable. What we constrain is not the *computation* but the
*presentation* (§3).

## §2 — Proving it: a table-encoding pin, and why that is the right proof

**We could not obtain live per-couple AstroSage / DrikPanchang outputs
headlessly** — both are POST-only form calculators; a GET fetch returns the
input form, not a result. State this plainly rather than implying a live
cross-validation that did not happen.

This matters far less than it would for the ephemeris, and here is the argument.
The dasha/panchang goldens prove that *our Swiss-Ephemeris math reproduces a
reference site's ephemeris*. Ashtakoota has **no ephemeris step** — it is a
lookup into fixed classical tables. The only thing that can differ between two
correct implementations is the **choice of table where the tradition itself
disagrees**. So the proof that fits the artefact is:

1. **Table-encoding pins** (`tests/test_compatibility.py`) — assert each table
   by the *structural invariant a wrong table would break*, not by re-comparing
   a copy of the same constant:
   * Nadi and Gana each split the 27 nakshatras exactly **9/9/9**;
   * the 14 Yoni animals form the multiset **13×2 + 1×1** (Mongoose the lone
     singleton, Uttara Ashadha);
   * the **seven sworn-enemy Yoni pairs are a perfect matching** over all 14
     animals (every animal has exactly one bitter enemy) — a dropped or
     duplicated animal breaks the partition;
   * Varna and the rashi lords are the canonical rashi tables;
   * plus five **independently-memorable per-nakshatra anchors** (Ashwini =
     Deva/Aadi/Horse, Rohini = Manushya/Antya/Serpent, …) so an anchor breaking
     flags a real transcription error.
2. **Hand-verified koota math** where the tradition is unambiguous (same
   nakshatra → Nadi dosha; 6/8 signs → Bhakoot dosha; same Yoni → 4, sworn enemy
   → 0; the Gana asymmetry; the Varna groom≥bride rule).
3. **A frozen full-breakdown golden** (`scripts/crossval_compatibility.py` →
   `tests/golden/compatibility_couples.json`, sha256-pinned) over **14 couples
   engineered to hit every contested case**: Nadi dosha with *and* without the
   pada/rashi parihar; Bhakoot 6/8 with the same-lord parihar; Bhakoot 5/9 with
   the friendly-lord parihar; a Yoni sworn-enemy pair; both directions of the
   Gana asymmetry; a same-nakshatra pair; and a high/low tally. A table edit
   that silently moves any score fails the pin.

Provenance of the tables: Brihat Parashara Hora Shastra; B. V. Raman,
*Muhurtha*; cross-checked against the published tabulations at Prokerala,
RoxyAPI's Gun-Milan guide, Steve Hora's marriage-compatibility tables, and
freehoroscopesonline (all cited in-code where the specific table was taken).

### Where the two references genuinely disagree — reported, not smoothed

This is a real finding, exactly as the task frames it ("if the two references
disagree, say so and state which we follow and why"):

* **Nadi parihar (cancellation).** Both sites agree on the two BPHS-lineage
  exceptions — **same rashi + different nakshatra**, and **same nakshatra +
  different pada**. Beyond those, a contested "same nakshatra-lord" exception
  circulates; **we deliberately do not encode it.** We compute the raw Nadi
  dosha and surface any well-agreed parihar as a *fact* (`nadi_parihar`) —
  never using it to silently zero the warning.
* **Bhakoot parihar.** Well-agreed: cancelled when the two rashi lords are the
  **same planet** or **mutual natural friends**. AstroSage often still shows the
  deduction while noting the cancellation in prose; DrikPanchang applies it more
  readily. We surface it as a fact and let the reading name it (`bhakoot_parihar`).
* **Graha Maitri fractions.** The 0 and 5 poles are universal; the middle
  (0.5 / 1 / 3 / 4) varies by source. We use the common Prokerala/Raman table
  and treat "same lord → 5" explicitly.
* **Vashya matrix.** The most implementation-variant koota: the half-sign splits
  of Sagittarius/Capricorn are degree-dependent, and the 5×5 group matrix has
  several published variants. We use the whole-sign majority convention and the
  widely-published matrix. Worth only 2 points, so its variance never moves a
  dosha.
* **Yoni middle values.** Same animal (4) and sworn enemy (0) are stable
  everywhere; the 1/2/3 gradations vary. We encode Raman's friend/neutral/enemy
  groupings and flag the middle as a soft spot.
* **Gana asymmetry.** The Deva/Manushya/Rakshasa cross-scores are directionally
  asymmetric (Deva-groom + Rakshasa-bride ≠ the reverse); the exact cross values
  differ by source. Ours is a common table and the asymmetry is tested.
* **Mangal 2nd house.** Included in the North-Indian set, often dropped in the
  South. We report **both** the strict and inclusive counts rather than pick.
* **Whole different traditions exist.** The 36-point *Ashtakoota* is North
  Indian. South India uses the *Dashakoota / ten-porutham* system (Dina, Gana,
  Yoni, Rashi, Rasyadhipati, Rajju, Vedha, Vashya, Mahendra, Stree-Deergha) —
  also scored differently. We implement Ashtakoota and say so (§4).

**Binding condition (mirrors A3's deferred-port rule):** if compatibility ever
becomes app-visible via the Worker, it must ship a TS port with a golden-parity
gate identical in kind to natal/dasha (the golden JSON here is already in the
engine-vs-worker shape), asserting the full breakdown deep-equal. Until then
there is nothing in the runtime path to gate.

### §2.1 — The Worker port (Block 4 wiring task) — the condition is now DISCHARGED

`aura-api` now serves `GET /v1/compatibility` (`src/compatibility.ts`), and the
gate above exists and blocks deploys. How divergence is made impossible:

* **Single source of truth for the tables.** The Worker never retypes a table:
  `aura-api/src/compatibilityTables.gen.ts` is machine-generated from THIS
  module by `scripts/crossval_compatibility_worker.py` (which also regenerates
  the golden). The Python constants stay the only hand-maintained encoding,
  still pinned structurally by `tests/test_compatibility.py`.
* **Exhaustive functional parity.** Because every koota is a finite lookup,
  the gate does not sample — it enumerates: all 108×108 (nakshatra, pada)
  midpoint couples (11,664), exercising every cell of every table, every
  parihar branch and both directions of every asymmetry, deep-equal
  engine-vs-Worker; plus the 14 curated couples byte-equal including the
  composed voice lines. Replayed on every CI run / deploy by
  `aura-api/test/compatibility.crossval.test.ts`.
* **Mangal births.** Mars/Venus/Moon/lagna are real ephemeris quantities, so
  240 seeded births are resolved by `compute_chart` (Swiss Ephemeris) and by
  the Worker (astronomy-engine, `src/planets.ts`): every longitude within 1′
  (measured max ≈ 19″), every sign/house/flag equal, with the
  `crossval_ascendant.py` boundary-honesty policy for bodies within 1′ of an
  ingress.
* **Honest degradation over HTTP.** No birth time → the koota tally computes
  (with `time_assumed` carried per partner) and `mangal.available: false`
  states the lagna reference is unavailable — never a noon fabrication, and
  never a bare "manglik" bit anywhere in the payload (route-tested). The
  directional-role convention (§3) is stated in the payload (`roles`), not
  hidden.
* **Ethics gates cross the port (see §3).** The falsification battery runs at
  AUTHORING time in this repo, against `DESCRIPTORS`. The export ships those
  exact bytes, the golden embeds them, and the vitest gate asserts the
  Worker's corpus is byte-equal — so copy that has not passed the gates
  cannot reach users without failing the deploy gate. The Worker composes no
  free text.

## §3 — The ethics problem (the central risk)

Compatibility is where astrology does the most real-world harm: weddings called
off over Nadi dosha, people told they are "manglik" and unmarriageable. The
binding voice rules (`docs/voice/love.md`, and the transit fear gates) forbid
fatalism and fear-selling. The A5/transit work proved **dread is constructible
from entirely permitted words** — a vocabulary scan cannot see it. So the
engine constrains *presentation*, and a falsification battery
(`tests/test_compatibility_gates_falsify.py`) proves the constraints fire.

**How a low score is reported truthfully.** The band lines are band-*neutral*
and the low band says the quiet part out loud: *"A low traditional tally …
It is one tradition's count rather than a verdict, and many close bonds score
low here."* We describe a tally; we never decree a relationship. The reader
keeps agency: we do not tell two people they should not be together, ever.

**The position on Mangal Dosha.** We take the descriptive position, not the
fatalist one. Mangal is *"Mars sits in one of the houses this tradition marks,
counted from your chart — a widely discussed marker, not a ruling on anyone's
future, and several traditional conditions set it aside."* We compute the fact
from all three references, report strict-vs-inclusive so the reader sees the
disagreement, and **never emit a bare "manglik" verdict.** If a future content
surface cannot hold that framing, Mangal should be **cut from the product
surface even though it is computable** — the engine may know the fact without
the app weaponising it.

**The gate battery (beyond banned vocabulary).** Five gates, escalating like the
transit battery, each falsified by mutating the real corpus and calling the real
gate:

* **A — no verdict vocabulary** ("incompatible", "should not marry", "avoid",
  "unmarriageable", …). The ordinary scan.
* **B — every dosha line is FRAMED + AGENTIVE + promises no outcome.** Catches
  the fatalism a vocabulary scan misses: *"Both charts share the same nadi,
  which harms health and the children"* carries no banned word yet is exactly
  what we must never ship. Gate B sees the stated consequence.
* **C — the low tally is reported as honestly as the high one** (the non-verdict
  signal is present).
* **D — THE SYMMETRY GATE.** The bad-news band may not read *heavier* than the
  good-news band. Measured, not scanned: inflating the low band 40% with
  entirely permitted words (the transit gate-5 signature) leaves gates A–C green
  and is caught only by the length/density measurement. This is the length/
  density symmetry pattern the task names, scoped to the same-kind comparison
  (low band vs high band) so reassurance-heavy copy is not penalised while dread
  inflation is.
* **E — Nadi and Mangal always carry the explicit non-verdict clause.** The two
  most weaponised lines in this market get a targeted check beyond A–D.

**The gender / directional problem (flagged, not silently encoded).** Several
kootas (Varna, Vashya, Gana, Bhakoot) are directionally asymmetric in a way the
tradition frames as "groom" vs "bride." The paywall promises *"Compatibility
for any relationship"* (§4). The engine names the two roles `groom`/`bride` for
fidelity to the asymmetric tables **and documents that this is a
heteronormative, gendered assumption the product must not silently inherit** —
the caller may assign the roles either way, and any app surface for
non-marital / same-gender / any-relationship compatibility must either state the
role convention honestly or drop the asymmetric kootas. This is a product-copy
decision, recorded here so it is not lost.

## §4 — What the product should truthfully claim

* **Claim:** "A traditional guna-milan compatibility reading — the classical
  36-point Ashtakoota, computed transparently from both people's Moon
  placements, shown koota-by-koota with the reasoning visible."
* **Do NOT claim** it is a verdict on a relationship, a prediction of marital
  success/failure, or "scientific." It is **one tradition among several**
  (North-Indian Ashtakoota; South India uses the ten-porutham Dashakoota; and a
  36-point tally is a heuristic, not a measurement).
* **Transparency is the honest differentiator**, exactly as for the rest of the
  engine: show every koota, its points, and the raw fact (which animals, which
  nadi, which count) — never a bare number or a bare "manglik."

### Existing copy that overstates — flag for the wiring task

Found by grep across the app; none is wrong to *offer*, but each needs the
framing above before it ships a real reading behind it:

* `astrology_paywall_hero_screen.dart` — **"Compatibility for any
  relationship"**: collides directly with the gendered/directional koota
  problem (§3). Either state the role convention or restrict the asymmetric
  kootas for non-marital use.
* `astrology_paywall_success_screen.dart`, `astrology_paywall_compare_screen.dart`
  — **"Compatibility readings"**: fine as a feature name; the reading behind it
  must carry the non-verdict framing.
* `astrology_premium_home_screen.dart` — the **"Compatibility"** tile
  (`PremiumGlyph.compatibility`) and `astrology_home_dashboard_screen.dart`'s
  **"Deep reports, compatibility and your dasha"**: feature names, acceptable;
  same binding on the reading.

None of these were changed by this task (engine-only). They are recorded for the
Phase-13 wiring / Block-4 UI task so the claim and the computation land together.

## Re-running

    uv run pytest tests/test_compatibility.py tests/test_compatibility_gates_falsify.py -q
    uv run python scripts/crossval_compatibility.py   # regenerates the golden
