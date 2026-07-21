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

## Cross-validating a TS port — deliberately deferred

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
* **Marriage / 7th house + D9** — 7th house is `house_signs[6]` today; D9
  (navamsa) is closed-form arithmetic on the longitudes we already have
  (~20 lines, add when consumed); needs astrologer-reviewed content.
* **KP** — Placidus cusps and the `krishnamurti` ayanamsa are in place; needs
  the 249 sub-lord table, KP rules, and content.

## Re-running

    uv run pytest tests/test_chart.py -q
    uv run python scripts/sensitivity_ascendant.py
