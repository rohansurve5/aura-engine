# Muhurat — auspicious timing, and the honest limit of "personal" — the Block-4 record

`engine/muhurat.py` composes the pieces the engine already owns (panchang
sunrise/sunset, `engine.choghadiya`, the A3 ascendant) into a ranked list of
auspicious windows for a purpose. This document answers the one question the
task was set to answer: **"Personal muhurat" was removed from the paywall in A2
as not computable without houses. A3 built the houses. Is it now honestly
computable — and can it come back?** It is the muhurat sibling of
`docs/ASCENDANT.md` and `docs/COMPATIBILITY.md`.

Scope: **engine + gates + measurement + crossval only.** No UI, no Worker port,
no Neon seed, no billing (the choghadiya/kaal port already exists in
`aura-api/src/window.ts` and is gated by `scripts/crossval_window.py`; nothing
in this task is app-visible). The binding condition for wiring a deploy gate is
in §5.

---

## §1 — What muhurat requires, and what the engine has EXACTLY today

Traditional muhurat (electional) selection uses six ingredients. Here is what
the engine holds for each, precisely:

| Ingredient | In the engine today? | Where |
|---|---|---|
| **Panchang** (tithi, nakshatra, yoga, karana), root-found | ✅ exact, DrikPanchang-gated | `engine/panchang.py`, `test_panchang.py` |
| **Choghadiya** (16 day/night slots) | ✅ exact, DrikPanchang-gated + Worker-crossval'd | `engine/choghadiya.py`, `crossval_window.py` |
| **Rahu / Gulika / Yamaganda kaal** | ✅ exact, same gates | same |
| **Lagna at a candidate moment** | ✅ exact (A3), any instant | `engine/chart.py::ascendant_sidereal` |
| **Purpose-specific rules** | ⚠️ partial — see below | `engine/muhurat.py` |
| **Personal (user-chart) filter** | ⚠️ birth-time-gated, 12-way — see §2 | `engine/muhurat.py` |

**Purpose rules — kept the classical, cut the arbitrary.** The
**choghadiya→purpose** association is well-defined and agrees across B. V.
Raman, DrikPanchang and Prokerala (Amrit = all works; Labh = gain/purchase;
Shubh = ceremony/auspicious rite; Chal = movement/travel), and so is the
**movable/fixed/dual rising-sign class** rule (chara for travel, sthira for
things meant to last). Both are encoded. **Purpose-specific *nakshatra* menus
were deliberately CUT**: they vary so much between traditions (Muhurta
Chintamani vs regional almanacs vs the many online tabulations) that any single
list would be false precision — exactly the "cut the arbitrary" instruction, and
the same stance `docs/COMPATIBILITY.md` takes on the contested Nadi-lord
parihar.

**Is "personal" muhurat — filtered by the USER's chart — computable?** This is
the word A2 removed. The answer is measured in §2 and is nuanced:

* **Without a birth time: no.** The candidate window list is a pure function of
  (place, day, purpose). The only classical personal factors that need no birth
  time — **tarabala** (day Moon-nakshatra from the natal nakshatra) and
  **chandrabala** (day Moon-rashi from the natal rashi) — are **day-constant**,
  so they cannot re-rank the windows within a day (measured: **0%**). A2 was
  right: with no houses (and no birth time), "personal muhurat" is impossible.
* **With a birth time: yes, at the A5 altitude.** The A3 lagna makes one factor
  live — the rising sign at each window taken as a Whole-Sign house from the
  user's natal lagna — and it **genuinely re-ranks** the windows. But it keys
  **only on the natal lagna sign**, so it is a **12-way** personalisation, not a
  per-individual one. This is real (§2), not a relabelling.

---

## §2 — Measured before building (`scripts/measure_muhurat.py`)

Same discipline as yearly/area outlooks and the A3/A5 sensitivity numbers:
seeded RNG, no wall-clock reads, India/IST (the launch market; wall clock =
instant, no DST — non-IST window accuracy is gated separately by
`crossval_window.py`). 6 cities × 90 days from 2026-07-21, 300 seeded synthetic
births, 20,000 sampled user-pairs.

### §2.1 — the purpose search is selective, not decorative

Qualifying windows per day (of 16 choghadiya slots, kaals removed):

| purpose | mean/16 | range | daytime coverage |
|---|---|---|---|
| start | 5.7 | 4–7 | 28.3% |
| business | 5.7 | 4–7 | 28.3% |
| travel | 7.7 | 5–9 | 39.2% |
| ceremony | 3.7 | 2–5 | 17.6% |

Roughly a **fifth to two-fifths of the day** qualifies — never "every hour"
(decorative), never "almost none" (useless). A meaningful, selective answer.

### §2.2 — does the USER's chart change which windows are returned?

**THE NUMBER.** Three measurements, escalating:

* **(a) No birth time → impersonal, by construction.** The qualifying window
  list is a pure function of (place, day, purpose): **identical for every user.**
* **(b) + tarabala/chandrabala (birth-time-free personal factors).** These are
  day-constant, added equally to every window. Within-day order differs on
  **0/20,000** user-pairs = **0.00%**. They cannot personalise a *timing*.
* **(c) + lagna-house-from-natal (birth-time, the A3 unlock).** The **only**
  within-day-varying personal term. Sweeping its weight (choghadiya rank spans
  0–4):

  | weight | top window differs | full order differs |
  |---|---|---|
  | w=1 (choghadiya dominant) | 39.9% | 80.9% |
  | w=2 | 59.6% | 84.0% |
  | w=4 | 62.2% | 84.3% |

  Robust across weightings; **upper bound (lagna alone decides): 61.4%.** This
  is a genuine re-ranking, **not** a relabelling — because the favoured-house
  set (kendras 1/4/7/10 + trikonas 5/9) is not rotation-invariant, unlike the
  A4 daily-gochara case where the asc only rotated one stock line.

* **(c′′) THE ALTITUDE — it is a 12-WAY personalisation.** The within-day term
  depends **only on the natal lagna sign** (tarabala/chandrabala are
  day-constant and are not scored into the ranking). So **two users sharing a
  lagna sign get an identical ranking** — confirmed. Across the 12 lagna signs,
  per (place, day, purpose) with ≥2 windows (n=2,160): **mean 3.3 distinct top
  windows** (max 5), **mean 9.5 distinct orders** (max 12). This is exactly the
  altitude the **A5 area scores** ship at ("a 12-way personal ordering on top of
  a daily cycle"), claimed accordingly — a lagna-sign ordering, **not** a
  per-individual reading.

**The day-level go/no-go IS personal — but it already exists.** Tarabala +
chandrabala flip a day between favourable/unfavourable on **37.6%** of
user-pairs. That is real personalisation — but it is the **existing daily energy
score** (v1 scoring is Tarabala-based), a *whole-day* signal, **not** a
per-window muhurat. Muhurat must not re-sell it as timing.

**Verdict of §2: NOT a relabelling for birth-time users.** The task's
stop-condition ("if personalisation is a relabelling, STOP") is not triggered.
Personal muhurat is honestly computable — as a birth-time-gated, 12-way
(lagna-sign) re-ranking of impersonal day-quality windows.

---

## §3 — The fear problem: reporting a BAD window without implying harm

Muhurat's failure mode is superstition-selling — implying **harm** from acting
outside an auspicious window. **Rahu kaal is the single most weaponised timing
in this market.** The A5/transit/compatibility work proved dread is
**constructible from entirely permitted words**, so a vocabulary scan cannot see
it. `engine/muhurat.py` therefore constrains *presentation*, and
`tests/test_muhurat_gates_falsify.py` mutates the **real shipped corpus**
(`DESCRIPTORS`), calls the **real** gate, and pairs every red with a green —
identical in kind to the compatibility battery.

**How a bad window is reported.** A kaal is *"a period many traditions set
aside for beginnings, counted from sunrise by the weekday — a customary pause,
not a warning of harm, and plenty is done in these hours every day."* We name
the period and its derivation; we **never** state or imply a consequence, and
(the symmetry gate) the inauspicious line never reads heavier than the
auspicious one.

**The five gates (the transit/compatibility battery, re-scoped to timing):**

* **A — no harm-verdict vocabulary** ("cursed", "disaster", "will fail", "never
  begin", …). The ordinary scan.
* **B — every kaal line is FRAMED + AGENTIVE + promises no outcome.** Catches
  the fatalism a vocabulary scan misses: *"Rahu Kaal is a period that harms any
  venture begun in it"* carries no banned word yet is exactly what we must never
  ship. Gate B sees the stated consequence. *(A real gate-design finding surfaced
  here: the OUTCOME regex must match harm as a **transitive verb with an
  object** — "harms the venture" — so the corpus's own defusing clause, "not a
  warning of harm", is not a false positive. Fixed and tested both directions.)*
* **C — the inauspicious band is as agentive as the auspicious one.**
* **D — THE SYMMETRY GATE.** The inauspicious band may not read *heavier* than
  the auspicious band. Measured, not scanned: inflating it 40% with entirely
  permitted words (the transit gate-5 signature) leaves A–C green and is caught
  only by the length/density measurement — falsified two ways (length inflation
  **and** density-alone).
* **E — Rahu Kaal always carries the explicit 'not a warning of harm' clause.**
  The single most weaponised line gets a targeted check beyond A–D.

All falsified with more than one signature, including dread built from permitted
words only (`test_kaal_fatalism_gate_fires`, `test_symmetry_gate_fires_on_
permitted_word_inflation`).

---

## §4 — Proving it: rahu/choghadiya cross-checked against DrikPanchang, incl. non-IST

The Pune golden (`tests/golden/drik_panchang.json`, `test_panchang.py`) already
pins choghadiya **names + boundaries** and all three kaals in IST to ±2 min.
This task **extends it in kind to non-IST**
(`tests/golden/drik_choghadiya_intl.json`, `test_choghadiya_intl.py`).

**Finding: DrikPanchang's choghadiya page IS headlessly GET-fetchable** —
server-rendered, unlike the POST-only guna-milan calculator that
`docs/COMPATIBILITY.md` could not fetch. Three cities were fetched live
(2026-07-22) and verified against the engine:

| city | date | weekday | day+night names | Rahu Kaal |
|---|---|---|---|---|
| London (DST, +1) | 2026-08-07 | Friday | ✅ exact | ✅ slot 4, within tol |
| Sydney (S. hemisphere) | 2026-03-15 | Sunday | ✅ exact | (not shown that date) |
| New York (−lon, DST) | 2026-11-10 | Tuesday | ✅ exact | fetch mis-grabbed¹ |

Both hemispheres, two DST zones, three weekdays — engine day+night sequences
reproduce DrikPanchang **exactly**, sunrise/sunset within 180 s (minute-rounded
display), London Rahu within tolerance.

**Why names+parts hold everywhere.** Choghadiya sequences and kaal part-numbers
are **pure weekday arithmetic on sunrise/sunset** — no location-specific logic.
So non-IST correctness reduces to **rise/set** correctness, which is already
gated globally (14 places incl. Reykjavik) engine-vs-Worker by
`crossval_window.py` to ±90 s. There is no convention divergence to record here
beyond the ones already documented: the ±ΔT/TT-frame lagna offset
(`docs/ASCENDANT.md`) and the ~1-min panchang display residual (`README > Known
deviations`).

¹ The NY fetch's summariser reported Rahu at the last day slot (15:27) rather
than the correct Tuesday 7th part (14:11); the name tables it extracted in full
are correct. Only the hand-verified London Rahu is stored as a fixture — we do
not pin a value we did not verify.

---

## §5 — The paywall question, answered plainly

**Can "Personal muhurat" honestly return to the paywall?**

**Yes — but only for users with a known birth time, and only claimed at its true
altitude.** The honest split, which the engine bakes in
(`rank_windows` flags `impersonal` vs `personal_12way`):

* **Birth time known → "Personal muhurat".** The A3 lagna genuinely re-ranks the
  day's auspicious windows for the user's rising sign (§2: 40–62% of user-pairs
  get a different top window). Honest wording:
  > **"Personal muhurat — auspicious windows ranked for your rising sign."**

  It must be claimed as a **12-way (lagna-sign) ordering, one tradition's
  reckoning**, never as a per-individual verdict — the same honesty A5 ships
  with. And it must never re-sell the tarabala day-score as a per-window timing.

* **Birth time unknown → NOT "personal".** With no lagna the windows are
  day-and-place quality, identical for everyone. Never fabricate a noon lagna
  (the `docs/ASCENDANT.md` rule). Honest wording — the exact words the task
  offered:
  > **"Auspicious timings for your day and place."**

  with the low-pressure unlock: *"Add your birth time to see the windows that
  suit your own rising sign."*

So A2's removal was **correct for the product as it then was** (no houses ⇒ no
personal factor). A3 changed the fact on the ground. "Personal muhurat" can
return **behind the birth-time gate**, worded as above; the impersonal
day-quality version is a legitimate, honest free/fallback surface under its own
name.

**Binding condition (mirrors A3/compatibility).** If a *ranked, personalised*
muhurat becomes app-visible via the Worker, it must ship the lagna through the
**already-gated ascendant port** (`aura-api/src/ascendant.ts`) and add a
golden-parity gate over the ranking, engine-vs-Worker, identical in kind to
natal/dasha. The choghadiya/kaal half is already ported and gated. Until then
there is nothing in the runtime path to gate — this task is engine + gates only.

---

## Re-running

    uv run pytest tests/test_muhurat.py tests/test_muhurat_gates_falsify.py tests/test_choghadiya_intl.py -q
    uv run python scripts/measure_muhurat.py
