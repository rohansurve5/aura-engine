# Ascendant (lagna) & houses — the A3 record

`engine/chart.py` computes the sidereal ascendant, house cusps and full graha
placements. This document records the decisions, the reference cross-validation
(with two site-side discoveries), the tolerances and their defence, the
birth-time sensitivity numbers that justify the work, and the unknown-birth-time
policy. Golden tests: `tests/test_chart.py` + `tests/golden/lagna_reference.json`.

## What is computed

* **Ascendant**: sidereal longitude of the ecliptic's eastern-horizon
  intersection, via `swe.houses_ex(..., FLG_SIDEREAL)`; exposed with sign,
  degree-in-sign, nakshatra and pada.
* **Houses**: **Whole Sign** is what we ship — house 1 is the lagna's whole
  sign, house 2 the next sign, and so on. This is the convention of Indian
  parlour astrology and of the rashi-chart kundlis on AstroSage/DrikPanchang
  (the references users check us against), and it is defined at every latitude.
  **Placidus cusps** are also exposed (`placidus_cusps`) because KP astrology
  needs them (cusp sub-lords — post-A3 backlog) and Swiss Ephemeris returns
  them from the same call; they are `None` above ~66° latitude where Placidus
  is mathematically undefined (swisseph raises). KP work must additionally pass
  `ayanamsa="krishnamurti"`. Both systems are needed eventually; Whole Sign is
  the product default, Placidus exists solely to feed KP later.
* **All 9 grahas** in signs AND Whole Sign houses, with retrogradation, via the
  proven `engine.positions` (mean node; Ketu = Rahu + 180°).
* **Ayanamsa**: `lahiri_vp285` (the library default). The lagna must live in
  the SAME zodiac as the natal/dasha stack, which is proven against AstroSage
  with vp285. The vp285↔plain-lahiri gap at the ascendant is ~23″ ≈ 1–2 s of
  birth time — invisible at any reference site's display precision.
* **Sidereal-houses NONUT note** (sibling of the natal-port discovery):
  planetary sidereal longitudes are mean-of-date (SIDEREAL forces NONUT), but
  house cusps derive from the APPARENT sidereal time and are then reduced by
  the same ayanamsa. That asymmetry is Swiss Ephemeris' convention and matches
  the reference sites; do not "fix" it.
* **Timezone**: `chart_from_local` takes a mandatory tz spec ("+HH:MM" or
  IANA). IANA resolves the offset AT the birth instant, so a 1943 Calcutta
  birth computes at UTC+06:30 (war-time DST). No default, no fallback.

## Reference cross-validation (12 charts, lat −41.3°…69.6°, years 1943–2026)

Sources, fetched 2026-07-21: DrikPanchang `muhurat/lagna.html` per-city lagna
tables (8 cities/dates, 96 sign-ingress times, minute display) and AstroSage
`panchang.astrosage.com/panchang/lagna-table` (4 dates, second display +
exact "Lagna at Sunrise" degrees). AstroSage city is fixed (New Delhi); date
is settable. Coordinates: geonames values, cross-checked by sunrise agreement
(< 30 s everywhere, including London/Wellington/Anchorage).

**Discovery 1 — the reference sites run house math in the TT frame.** Our
engine (correctly, per the astronomical definition) evaluates sidereal time at
UT. Evaluating our ascendant at *(displayed instant + ΔT)* reproduces
AstroSage's exact sunrise-lagna degrees to +10″ (2026) and +65″ (1989) —
i.e. their lagna runs ~ΔT (57–69 s) ahead of the astronomical one, and the
offset GREW from 1989 to 2026 exactly as ΔT does. Pre-1972 anchors carry a
further unexplained site-side shift (≤ +36 s ≈ 8′ at 1943). The same ~ΔT
offset explains most of the DrikPanchang table deltas below and is the likely
cause of the long-documented "+1 min residual" on their tithi/karana ends
(README > Known deviations).

**Discovery 2 — AstroSage's lagna *table* is traditional arithmetic.** Its
boundary times drift −9.83 s/hour through the day (the solar/sidereal day
ratio) around exact anchors — the signature of fixed rasimana rising-times
added to a sunrise anchor. Their own table deviates from their own exact
sunrise-lagna degree by up to ~2.5 min. It is therefore NOT a fixture; only
their sunrise anchors are.

**DrikPanchang tables are root-found** (intraday spread ≈ display rounding
only) and were fixtures. Engine minus reference ingress time, seconds:

| table | lat | ΔT | mean | range |
|---|---|---|---|---|
| pune-1989 | 18.5 | 56.7 | +56.2 | +19…+76 |
| kolkata-1943 (war DST) | 22.6 | 26.2 | +56.9 | +38…+86 |
| chennai-1965 | 13.1 | 35.9 | +52.6 | +37…+76 |
| srinagar-1975 | 34.1 | 46.1 | +40.6 | +21…+62 |
| singapore-2000 | 1.3 | 63.9 | +58.9 | +37…+82 |
| london-2000 | 51.5 | 63.8 | +2.4 | −27…+25 |
| wellington-2010 | −41.3 | 66.3 | +109.7 | +90…+141 |
| anchorage-2015 | 61.2 | 67.9 | −89.8 | −123…−68 |

India/low latitude sits at ~ΔT-consistent +40…+59 s means. At |lat| > 40 the
per-city constant wanders (+110 s Wellington, −90 s Anchorage, +2 s London);
coordinates and clocks are exonerated (sunrise < 30 s), the residual is an
unresolved site-side systematic — bounded, documented, and irrelevant at sign
level. DrikPanchang refuses |lat| ≳ 62 outright ("High Latitudes are not
entertained", Tromsø); our engine computes the Whole Sign chart there.

**Hard cases covered in the golden tests**: birth 4 min either side of a
boundary (sign flips exactly as the reference table says); 1943 war-time-DST
Kolkata (resolves at +06:30, and +05:30 provably wrecks the lagna); Anchorage
61.2°N with 24-minute sign windows; Tromsø 69.6°N (Whole Sign fine, Placidus
None); southern hemisphere (Wellington); births at reference sunrise instants.

## Tolerances, defended

* **Sign agreement** (what the product consumes): asserted at every reference
  window sampled at its midpoint and 4 min inside each edge — 250+ samples,
  100% agreement.
* **Boundary times**: ≤ 120 s (India/low-lat), ≤ 180 s (global). Defence: the
  references are only defined to this level — ±30 s display rounding, the
  ~ΔT (26–69 s) TT-frame convention, unexplained per-city constants ≤ 158 s,
  and AstroSage's own table disagreeing with its own exact anchor by up to
  2.5 min. No public reference pins a lagna boundary tighter; our side is the
  only one with a stated astronomical definition (Swiss, UT frame). A 180 s
  ambiguity affects the lagna SIGN only for the ~2.5% of births within 3 min
  of an ingress — and for those, the truth is genuinely contested between the
  sites themselves.
* **Degrees**: AstroSage exact anchors, TT-corrected: ≤ 90″ modern (measured
  +10″/+65″), ≤ 10′ historical. 90″ ≈ 6 s of birth time — far below the
  1-minute granularity users can state their birth time with.
* **We ship the UT-frame (astronomically correct) ascendant.** We do NOT copy
  the sites' TT quirk: it is a bug on their side, the difference (≤ 0.3°)
  changes the sign only within ~1 min of an ingress, and matching it would
  poison every future house-derived quantity to preserve agreement with a
  defect. This is unlike the vp285 ayanamsa decision, where the choice was
  between equally-valid conventions.

## Cross-validating a TS port — deliberately deferred *(landed with A5, § below)*

Natal and dasha have a 1,000+-birth engine-vs-Worker crossval gating every
aura-api deploy. The ascendant has NO Worker port yet, deliberately: no Worker
endpoint consumes an ascendant until A4 rewires daily guidance, so there is
nothing to gate — a port today would be dead code validated against a moving
target. **Binding condition**: A4 must not ship any app-visible ascendant
without first porting it (astronomy-engine already has everything needed —
`natal.ts` contains the Vondrák precession/obliquity stack; the ascendant adds
only sidereal time + one closed formula) and wiring a 1,001-birth
`crossval_ascendant.py` gate identical in kind to the natal one, asserting
sign agreement 100% and longitude ≤ 1′.

## Birth-time sensitivity — the number that justifies A3

`scripts/sensitivity_ascendant.py`, seeded (285), 40,000 births 1961–2008,
population-weighted over the 20 largest Indian cities:

1. **Birth shifted 4 minutes → ascendant sign changes 3.33%** of the time
   (the asc moves ~1°/4 min; a sign spans ~2 h).
2. **Birth shifted 2 hours → asc sign changes 94.2%** (all 12 Whole Sign house
   assignments shift with it); Moon nakshatra changes 8.1%, Moon sign 3.9%.
   Before A3, a 2-hour birth-time error changed nothing 92% of the time.
3. **Same instant, different Indian city → asc sign differs 17.3%** (median
   |Δasc| 4.6°, max 21°). Birth place is now load-bearing too.
4. **THE NUMBER — random user pairs with an identical personalisation key**
   (200,000 pairs):
   * Moon nakshatra only (the pre-A3 reality): **3.74% — 1 in 27**.
   * Nakshatra + ascendant sign (the minimal A4 key): **0.35% — 1 in 286**.
   * Fully identical sign-level chart (asc + all 9 grahas): **0.002% — 1 in
     50,000**.

   A3 shrinks byte-identical readings from 1-in-27 to 1-in-286 with the
   smallest possible A4 key, and to 1-in-50,000 if guidance ever keys on the
   full chart.

## Unknown birth time — the policy

Without a time there is NO ascendant: it sweeps all 12 signs every day, so
date+place constrain it not at all. Binding, in the spirit of "absent > wrong":

* **Never** compute a noon (or any assumed-time) ascendant and present it as
  the user's. A fabricated lagna is wrong 11 times out of 12 at sign level.
* What the app CAN still offer: Moon-nakshatra-keyed daily guidance (today's
  product — with the existing noon assumption the nakshatra itself is right
  ~76% of the time, since the Moon crosses a nakshatra boundary roughly daily;
  the existing `time_assumed` flag already surfaces this), Sun sign, dasha
  timeline (nakshatra-derived, same caveat), panchang.
* What it CANNOT offer: lagna, houses, house-based life-area readings, KP,
  D9/marriage — anything downstream of the ascendant.
* **Product recommendation (no UI built in A3)**: profiles without a birth
  time stay on nakshatra-keyed guidance and show an honest, low-pressure
  unlock — "Add your birth time to unlock your rising sign and house-level
  guidance" — instead of a fabricated chart. A4's guidance selection must
  branch on `birth_time_known`. Birth-time rectification is a post-launch
  idea, never a silent default.

## What A3 unlocks (and what each still needs)

* **Birth-chart screens** — chart math done; needs an API surface (Worker port
  + crossval gate, per above), payload/profile storage, and the screens.
* **Real life-area readings (A4/A5)** — the asc-relative house of each transit
  is now computable; needs the A4 guidance rewiring + content, then A5 scoring.
  **A4 §1 verdict (below): the daily reading stays 27 rows; the asc enters the
  daily product through A5 scoring arithmetic, not through content keying.**
* **Marriage / 7th house + D9** — 7th house is `house_signs[6]` today; D9
  (navamsa) is closed-form arithmetic on the longitudes we already have
  (~20 lines, add when consumed); needs astrologer-reviewed content.
* **KP** — Placidus cusps and the `krishnamurti` ayanamsa are in place; needs
  the 249 sub-lord table, KP rules, and content.

## A4 §1 — does the ascendant change the DAILY claim? Measured: NO

`scripts/measure_gochara_daily.py`, 366 days from 2026-07-21, real sky sampled
at the 00:00 IST day boundary (the same convention `engine/transits.py` reads
by). The question: is (nakshatra × asc-sign) keying real gochara, or 27
readings repeated 12 times under a bigger cache key? Four measurements:

1. **Structure.** On every one of 366 days, the 12 ascendants' Whole Sign
   house-configurations are 12 labeled vectors that reduce to **exactly 1
   configuration up to rotation**. The asc axis holds one degree of freedom:
   the shared sky, rotated. Whole Sign guarantees this by construction —
   `house = (sign − asc) mod 12` — so it is true forever, not just this year.
2. **Cadence.** Sign changes at the day boundary, 366 days (and inside the
   live 40-day precompute window): Moon **161/yr, 2.3-day dwell** (17 in the
   window) · Sun 12 · Mercury 14 · Venus 12 (1–2 in the window) · Mars 6 ·
   Jupiter 3 · Saturn/Rahu/Ketu 1 (0 in the window). **Only the Moon moves on
   a daily-reading cadence.** Everything else is standing configuration — the
   claim class the transit report already owns (keyed on Moon sign, ingress
   cadence), and it deliberately CUT Mars-and-faster as "a daily card wearing
   a longer name". A lagna-keyed daily line for slow movers would restate the
   transit report's claim with the count-from point renamed.
3. **The Moon line** — the only asc-keyed daily-cadence claim ("the Moon
   crosses your Nth"). For a fixed user it changes on **44.0%** of days —
   runs of 2 days ×115 and 3 days ×45 across the year, so most days it
   repeats yesterday's line verbatim. And on **44.0%** of days the Moon
   changes sign *inside* the civil day, making the line partly false that day
   for every keying scheme. It also occupies the slot the six daily area
   lines already own (which life area matters today) — a cross-corpus
   collision, not an addition.
4. **Information.** `row(day, nak, asc) = row27(day, nak) + f((moon_sign −
   asc) mod 12)`. The asc-dependent fragment takes 12 values per day from a
   pool of **12 values total across the entire year**. 324 rows/day =
   118,584 rows/yr containing the same 9,882 nakshatra readings plus a
   **static 12-entry house-line table**. The 1-in-286 collision prize would
   be bought by appending one of 12 stock lines — byte-distinctness without
   claim-distinctness. That is the yearly/area-outlook failure with a bigger
   cache key.

Doctrinal footnote: traditional *daily* gochara (chandrashtama, murti
nirnaya) is reckoned from **janma rashi (Moon sign)** — which the product
already has without a birth time, and which the transit report already keys
on. Lagna-reckoned analysis earns its keep on standing configurations and
scoring, not on the daily card.

**Verdict (binding for A4): the daily reading keeps 27 rows/day.** The
precompute, cache key, and `/v1/today` contract do not change. The ascendant's
honest routes into the product, in order:

* **A5 scoring** — house-based area scores and per-user rank order (the
  audit's "single biggest win"). There the asc changes the *numbers and their
  order* — a claim genuinely different in kind — and it enters as **read/score
  time arithmetic over the 27-row corpus** (base + house offsets), never as
  row multiplication. Any A5 design that proposes 324 precomputed rows should
  be rejected on the measurements above.
* **Identity / birth-chart surfaces** — rising sign, houses, chart: real
  per-user standing facts. Gated by the binding TS-port + 1,001-birth
  crossval condition above, which A4 does **not** trigger (nothing app-visible
  ships from this decision).
* **Transit report re-keying** (lagna-first, Moon-sign fallback) — a separate
  decision for the transit surface with its own crossval implications; not a
  daily-guidance question.

The unknown-birth-time policy and the boundary-honesty design (±2 min
ingress detection, payload field) move with the asc-visible surface —
they land when the first app-visible ascendant lands, not before.

## A5 — house-based area scores (content_v4). Measured GO, shipped

The last Phase 0 task: make the six life-area scores carry real per-user
information. A1 measured the v3_2 scores as a pure function of (energy,
weekday) — 59,130/59,130 exact predictions, identical rank order for every
user in the country. A4's verdict bound the fix to score-time arithmetic over
the 27-row corpus. This section records the formula, the measurements that
gated the build, the coherence design, the architecture, and the gates.

### The formula (all tables tunable in score_rules `content_v4`)

    h(p)     = ((sign(p, day) − asc_sign) mod 12) + 1     # transit Whole Sign
                                                          # house from the lagna
    T[area]  = Σ_(p ∈ significators[area]) w_p · G[p][h(p)]
             + Σ_(q occupying the area's own house(s)) occ(q)
    score[a] = clamp(tara_energy + paksha + weekday_area_mod + T[a])
    energy   = UNCHANGED (27-row; the personal claim lives in the areas)

Significators/houses (subject to astrologer review, like the v1 heuristic):
Career → Saturn·5 + Sun·3, 10th · Money → Jupiter·5 + Venus·3, 2nd/11th ·
Love → Venus·5 + Moon·3, 7th · Mind → Mercury·6, 5th · Health → Mars·4 +
Sun·4, 6th · Mood → Moon·6, 4th. G is the classical gochara favourability
table per planet (fav +1 / unfav −1 / extra-bad −2: Sade-Sati houses 1/8/12
for Saturn, chandrashtama 8 for Moon, 8 for Mars); occupancy is
benefic-positive (Jup +3 … Sat −3) with malefics flipped positive in the
upachaya houses 3/6/10/11. Inputs at read time: the user's lagna sign (from
/v1/natal, stored once) and the day's nine graha sign indices
(`daily_sky.planet_signs`, precomputed at the 00:00 IST boundary).

### Measured before building (scripts/measure_a5_scores.py — 20,000 seeded
### births, 20 Indian cities pop-weighted, 90 days from 2026-07-21)

* **A1's own prediction test collapses: 100.0% → 2.7%** (48,743/1,800,000
  exact vector predictions from (energy, weekday); adding the asc to the
  predictor key still only reaches 18.3% — the rest is the day's actual
  planet configuration).
* **Rank order across users, same day: 1 → mean 15.0 distinct orders**
  (min 11, max 24), mean 4.6 distinct leading areas per day. Leader share of
  user-days: Money 31.6%, Love 22.9%, Career 15.3%, Mind 15.2%, Mood 8.2%,
  Health 6.8% (was: one leader for everyone, Money 94.4% of months).
* **Birth sensitivity on the scores**: 4 min apart → differ on 3.6% of
  user-days; 2 h apart → 95.1% (rank order 94.4%); same instant different
  city → 17.6%. Birth time and birth place are now load-bearing in the
  daily product.
* **Fixed user across 90 days**: their most common leader holds 53.3% of
  days; the leader changes on 54.6% of day-pairs — the Moon-speed terms keep
  the ordering alive without churning it daily.
* **Structure, disclosed honestly**: before clamping the score is additive —
  f(nak, day) + g(asc, day), no nak × asc interaction term — so users
  sharing a lagna sign mostly share a rank order (clamping at 0/100, hit by
  5.4% of scores, is the only interaction). The 12 per-day T vectors are all
  distinct every measured day. This is a 12-way personal ordering on top of
  a 9-way daily cycle, not a 324-way reading — claimed accordingly.

### Coherence (§2 of the task, binding): a number is never explained by a
### cause that did not move it

The 27 precomputed rows now carry a `compose` bundle — every
(date, nakshatra)-determined piece: UNCLAMPED per-area base scores, the six
rotated cause strings, the raw narrative opener/closer and
opportunity/warning templates. At read time `apply_ascendant`
(engine/scoring.py, reference) / `applyAscendant` (aura-api src/scores.ts,
production) recomputes scores from the unclamped base + T, re-selects band
labels and score-why RECOGNITION for the band actually shown, re-formats
narrative/opportunity/warning from the actual best/worst, and swaps the CAUSE
of the single area with the largest |T| to a `why_cause_house` line naming
the primary significator's REAL transit house (72 authored lines, 6 frames ×
12 houses, band-neutral, gated by the same diversity + per-day gates as every
other corpus). The base half (tara/weekday/paksha) keeps its rotated cause —
it did move the score; the house half is voiced where it mattered most.

### Architecture (§3): option (b) with (a)'s cache shape

The Worker computes per request — pure integer arithmetic + dictionary
lookups over the row's compose bundle and the memoized score_rules tables
(one Neon query per version per isolate). The `asc` query param joins the
CDN cache key, so fan-out is bounded at 27 × 12 = **324 cache entries** per
day (27 for the no-asc population), still until-IST-midnight. NOT (c): app
local compute would be a third scoring implementation to cross-validate and
would pin content changes to app releases. Offline behaviour is unchanged —
the app caches the full merged payload once per day and repaints from cache.
Content version changes behave exactly as before (rows are stamped; rollback
is the marker repoint; degraded inputs — pre-v4 row or sky — serve the
honest unadjusted reading flagged `ascendant.applied: false`, never a 500).
The weekly/monthly/transit reports still aggregate the 27-row base scores —
re-keying them is a recorded post-launch decision, not an accident.

### Unknown birth time (§4)

No time ⇒ no `asc` param ⇒ the 27-row reading served verbatim — same bytes
as v3_2, no partial adjustment path, no noon lagna anywhere. /v1/natal with
`lat`/`lon` but no `time` returns `ascendant: null` explicitly. The app-side
unlock copy remains the A3 product recommendation (app work is post-launch).

### The gates (§5): the deferred TS port landed here

* **src/ascendant.ts** — GAST (astronomy-engine) + true obliquity (Vondrák
  mean + 4-term nutation) + the closed horizon-intersection formula, reduced
  by the same VP285 ayanamsa as natal. The mean/apparent asymmetry matches
  Swiss' sidereal-houses convention deliberately.
* **scripts/crossval_ascendant.py → test/ascendant.crossval.test.ts**:
  1,001 births (1930–2025, 20 Indian cities pop-weighted + 8 world cities,
  IANA zones at the birth instant incl. 1943 war-time Kolkata). Result:
  **1000/1001 exact sign agreement, max Δ 18.79″** (≈1.2 s of birth time;
  tolerance 60″), and **1 boundary birth** — both sides within 1′ of the
  same Aries/Taurus ingress (0.6 s of clock time from it), flagged
  `boundary: true` in the golden and asserted as such rather than
  adjudicated: at sub-second precision the sign is genuinely contested
  (the reference sites disagree by minutes there). The boundary-honesty
  payload field ships with it: /v1/natal `ascendant.near_boundary` = within
  0.5° (±2 min of birth time) of an ingress.
* **scripts/crossval_scores.py → test/scores.crossval.test.ts**: 162
  (date × nakshatra × asc) real composed readings, engine vs Worker,
  **deep-equal on the whole adjusted payload** — numbers AND copy, because
  numbers agreeing while sentences drift is exactly the §2 incoherence.
* Both gates run in aura-api CI on every deploy, identical in kind to natal
  and dasha. Every pre-existing golden regenerated sha256-identical (the two
  report goldens' `rules_version` stamp moved to content_v4; all 144 case
  bodies byte-identical — the v4 rules change no aggregate).

### Rollback (§6)

`content_v4` is additive: v3_2 keeps its rows, `tests/test_ascendant_scores.py::
test_v4_without_ascendant_is_v32_plus_compose_only` proves a v4 no-asc payload
is byte-identical to v3_2 plus the compose bundle, and rollback is repointing
`engine/content.py` at the v3_2 seed + re-running migrate + precompute. An
app that sends `asc` against a rolled-back database degrades to the honest
unadjusted reading (`applied: false`) by the same guard that handles pre-v4
rows.

## Re-running

    uv run pytest tests/test_chart.py tests/test_ascendant_scores.py -q
    uv run python scripts/sensitivity_ascendant.py
    uv run python scripts/measure_a5_scores.py
    uv run python scripts/crossval_ascendant.py
    uv run python scripts/crossval_scores.py
