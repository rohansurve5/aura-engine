# Period reports — design, audit, and the weekly prototype

Block 3 of the screen plan lists ten report types. This document answers four
questions before any of them get a screen: what a report structurally *is*,
which of the ten we can actually compute, how a report stays non-repetitive, and
where the paid line sits. The weekly report is built end to end as the proof.

---

## 1 · What a report actually is

The three composition systems already shipped each have a different unit:

| System | Unit | Question it answers |
|---|---|---|
| `daily_guidance` | one **date** | what is today like? |
| `dasha_content` | one **period** | what is this era about? |
| `identity_content` | one **person** | what are you like? |

A report is none of these. It spans a **range**, and the naive reading —
compose each day, concatenate — produces N readings rather than one report.

**What makes it a report is that every claim it makes is a second-order feature
that does not exist in any single day in the range.**

    distribution   where inside the window do the strong days fall?
    spread         is this a dramatic span or an even one?
    position       is the high early, middle, or late?
    aggregate      which life-area leads across the whole span, which lags?
    adjacency      are the best and worst days next to each other?

None of these can be read off one day's payload. They exist only once you hold
seven rows at once. That is the structural definition, and it is why a report is
a distinct artefact rather than a longer card.

### The arc

Range features alone would still be a list — of statistics instead of days. A
report also needs an ordering with a beginning, a turn and a close. Four
movements, always in this order:

1. **Shape** — what this week *is* as a whole (from the distribution)
2. **Turn** — the moment inside it that changes (from peak/trough position)
3. **Standing** — which area leads, which lags, which holds (from aggregates)
4. **Close** — what to carry out of it (from the shape)

plus **anchors**: specific dated days the reader can act on.

### The gate no previous corpus needed

Anchors are what make a report *checkable*. Daily copy makes no verifiable claim
about anything outside itself. A report names a peak day — and if that day is
not the highest-energy day in the window, the report is not merely repetitive,
it is **wrong**, in a way the user can verify against the calendar screen we
already ship.

`tests/test_report_composition.py::test_anchors_name_the_actual_extremes` is
that gate, and it is a genuinely new class of check for this codebase:
**a report may not contradict its own data.**

---

## 2 · Which of the ten we can actually compute

### What the engine has today

Verified by reading the source, not by assumption:

* `engine/positions.py` — sidereal longitudes and retrograde state for all nine
  grahas at **any instant**, Swiss Ephemeris, Lahiri VP285.
* `engine/vimshottari.py` — full three-level dasha (maha / antar / pratyantar),
  cross-validation-gated against AstroSage.
* `engine/daily.py` — panchang, moon phase, tithi/nakshatra/yoga/karana,
  choghadiya, kaals. **Moon nakshatra only** — no other planet is stored per day.
* `daily_guidance` — 27 rows/day (one per natal nakshatra): energy + six area
  scores + authored copy. Precompute window is **14 days**.

### What the engine does NOT have

`grep -rniE "ascendant|lagna|house|cusp|bhava|sub_lord"` over the whole repo
returns **two hits, both comments describing future work.** Concretely, we have:

* **no ascendant / lagna** — `positions.py` accepts lat/lon "for API symmetry
  and future topocentric/ascendant work" and does nothing with them;
* **no houses / bhavas**, therefore no house lords and no house-based reading;
* **no divisional charts** — in particular no D9 navamsa;
* **no cusps, no sub-lords**, and no KP ayanamsa;
* **no aspect (drishti) computation**;
* **no transit-to-natal comparison layer** (though the raw positions exist).

This single absence decides most of the audit. Career, marriage, finance and
business are, classically, **house readings** — 10th for career, 7th plus D9
plus Venus for marriage, 2nd and 11th for finance. Without an ascendant there
are no houses, and none of those four can be computed as claimed.

### The verdict

| # | Report | Verdict | What it needs |
|---|---|---|---|
| 1 | **Weekly** | ✅ **Buildable now** | Built — this document's prototype |
| 2 | **Monthly** | ✅ **Built** | Done — see § the monthly report. Window widened 14 → 40, thresholds re-derived at month scale |
| 3 | **Yearly** | ❌ **Cut** | Reframe attempted and measured in § the yearly audit. Not from daily aggregates (no signal); not from Vimshottari either (N ≈ 1.7 periods/year — no second-order feature exists, and the dasha timeline already ships every claim) |
| 4 | **Career** | ❌ **Cut** | No 10th house. The "period outlook" reframe was measured in § the area-outlook audit and does not survive: an area score is a deterministic function of (energy, weekday) |
| 5 | **Marriage** | ❌ **Cut for launch** | No 7th house, no D9, no Venus analysis — *and* highest reputational liability of the ten |
| 6 | **Finance** | ❌ **Cut** | No 2nd/11th house. Same measurement, and it is the 94.4% Barnum leader on top of it. `docs/voice/money.md` already bans instrument advice — the report's own name overpromises |
| 7 | **Business** | ❌ **Cut** | Same as career, and weaker: there is **no scored `business` area at all**, so the reframe has no input whatsoever |
| 8 | **Transit** | ✅ **Buildable — but NOT as a report** | Confirmed: no new maths. Audited in full in § the transit audit, where the "report" framing is withdrawn |
| 9 | **KP** | ❌ **Cut** | Ascendant + 12 Placidus cusps + 249 sub-divisions + the Krishnamurti ayanamsa. Nothing exists |
| 10 | **PDF** | ⏸ **Not a content problem** | A rendering concern. Defer until there is content worth exporting |

### Three findings worth Rohan's attention

**Transit is more buildable than the four life-area reports.** That inverts the
screen plan's implied ordering. Vedic *gochara* is classically reckoned **from
the Moon sign**, not from the ascendant — and the Moon sign is exactly what we
compute accurately and gate. So Saturn's sade sati, Jupiter's sign transits, and
the Rahu/Ketu axis are all computable today with no ascendant at all. It needs a
new precompute job storing sign-ingress dates and a transit corpus, but **no new
astrology maths**. If a second report ships after weekly, this is the candidate.

**A yearly report from daily aggregates is statistically empty.** Tara is a
9-fold cycle counted over a 27-nakshatra Moon transit, so it completes roughly
13.5 times a year. Averaging 365 days of it yields the same middling number for
every user in every year. There is no yearly signal in the daily data. What we
*do* have that genuinely varies over years is **Vimshottari dasha**, which is
already computed, already gated, and already has an authored corpus
(`dasha_content_v2`) — so this section originally recommended rebuilding yearly
on that.

> **Superseded 2026-07-21.** The rebuild was measured before it was authored and
> **the recommendation is withdrawn**: a calendar year holds a mean of 1.67 antar
> periods, so there is no second-order feature to compute, and every claim such a
> report could make is already shipped by `astro-dasha-current` and
> `astro-dasha-detail`. Yearly is **cut**. See § the yearly audit.

**Marriage should be cut on liability, not only on maths.** Even with houses and
D9, a wrong marriage prediction is the single most damaging thing this product
could ship. The voice specs already forbid outcome guarantees. The maths gap
makes the decision easy; it would be the right call regardless.

---

## 3 · Determinism and non-repetition

No runtime LLM, same as every other corpus: composed deterministically from
authored fragments plus computed data. Same `(week_start, natal_index, rules,
content)` → byte-identical report.

Non-repetition is a **harder** problem here than in the daily system, for two
reasons that compound:

* a reader sees only ~52 reports a year, but each is long, so repetition is far
  more visible per sample than in a two-sentence daily card; and
* aggregates **regress to the mean** — the longer the range, the more every span
  averages to the same middling numbers. The underlying data really is more
  similar week-to-week than day-to-day, and it gets worse monthly and yearly.

### The trap that would have caught us

The daily system uses a 12-row rotation coprime with the 7-day week. Copying
that shape naively is a disaster at report cadence: **any rotation whose period
shares a factor with the report cadence collapses.** A 12-row table indexed by
month hands every January the same row, forever. That is the exact failure mode,
and it is pinned in a test:

```python
assert gcd(12, 52) == 4, "12 is the trap: a monthly table would lock"
```

### The three layers

**1 · Shape is data-driven.** A front-loaded week genuinely should not read like
a scattered one. This is honest variety rather than decorative variety — the
copy differs because the week differs.

**2 · Variant rotation on mutually coprime primes.** 17 openings, 7 turn lines,
5 closes. None shares a factor with 52. The opening index is

```
variant = (week_index * 1 + natal_index * 3) % 17
```

`week_index` advances by exactly 1 per week, so over any **17 consecutive weeks**
the index takes 17 distinct values. If those weeks share a shape, the 17
openings drawn are distinct by that arithmetic; if they do not share a shape,
they come from disjoint corpora and are distinct anyway. **Either way a reader
cannot see a repeated opening inside 17 weeks** — and the same argument gives 7
for turns and 5 for closes. Combined period: `lcm(17,7,5) = 595` weeks, over
eleven years of continuous reading before the triple can recur.

Openings started at 11, which guaranteed only 11 distinct consecutive reports —
reports #1 and #12 could draw the same opening cell, visible whenever both weeks
shared a shape (common: `scattered` is half of real weeks). The step up was NOT
13, and the reason is worth pinning: **13 is prime yet divides 52**, so a
13-slot rotation advances `52 ≡ 0 (mod 13)` across a 52-week year and hands
every anniversary week the same opening — the 12-row trap one door down, and
the coprimality gate (`gcd(OPENING_VARIANTS, 52) == 1`) would have rejected it.
17 is the smallest count above 12 coprime with 52, 7 and 5 at once.

The `natal_index * 3` term de-syncs readers, so two people comparing phones in
the same week never see the same skeleton.

**3 · Anchors carry specificity.** The report names real dates, real weekdays
and real areas — "Thursday the 24th", "Money leads". These differ every single
time regardless of which cells were drawn. A two-sentence daily card has no room
for this; a report does, so specificity carries more of the load here than
rotation does.

### The reading unit is a *sequence*, not a screen

This is the third instance of the denominator lesson from `CONTENT_KEYS.md`, and
the unit is different again:

* copying the **per-day** gate would prove the four movements of one report do
  not collide — true by construction, since they come from four disjoint
  corpora. It would assert nothing.
* copying the **dasha screen** gate proves the same nothing.

What a reader of reports actually experiences is *one report per week, in
sequence*. The visible failure is not "these paragraphs rhyme", it is "this is
the fourth week running that opened the same way". So the gate is a **sliding
window over consecutive weeks**, at the exact widths the arithmetic guarantees.

---

## 4 · The weekly prototype

Built end to end. Everything below is green.

| Piece | Where |
|---|---|
| Schema | `db/migrations/009_report_content.sql` + `010_report_kind.sql` |
| Seed | `db/seed/report_content_v2.json` — 257 weekly lines |
| Composition | `engine/reports.py` |
| Seeder + marker | `db/migrate.py::seed_report_content` |
| Corpus gate | `tests/test_report_content_seed.py` — 27 tests |
| Composition gate | `tests/test_report_composition.py` — 57 tests |
| Falsification | `tests/test_report_gates_falsify.py` — 26 tests |
| Worker composition | `aura-api/src/report.ts` |
| Endpoints | `GET /v1/report/content`, `GET /v1/report/weekly` |
| Cross-validation | `aura-api/test/report.crossval.test.ts` — 72-case golden, generated by `scripts/crossval_report.py` |

Corpus shape (weekly): 6 shapes × 17 openings = 102; 5 turn kinds × 7 = 35;
6 areas × 3 roles × 5 = 90; 6 shapes × 5 closes = 30. **257 authored lines.**
The six new openings per shape (v2) are **appended** after the original 11, so
v1-indexed code — including a not-yet-redeployed Worker — draws the same line
for the same index.

Versioning uses the `active_content` marker from version one — no `max(version)`
anywhere, enforced as a property of the source by
`test_no_kind_selects_its_version_by_inference`, which now covers all four
seeders.

### One table, one marker, every report kind (migration 010)

`report_content` rows are discriminated by **`report_kind`** (`weekly` |
`monthly`) because the monthly report reuses the same four movement names at
month scale — without the column the two corpora would collide on the same
primary key. The activation marker stays **singular**: one seed file carries
every kind, one version spans them, and `seed_report_content` writes all kinds
and the marker in one transaction. That is 008's identity reasoning applied one
level up — the corpus gates run over the whole seed file, so "weekly v2 beside
monthly v1" would be a pairing no gate ever saw, and with a single marker it is
not a state the database can hold. The backfill default (`'weekly'`) is dropped
immediately after the column lands: a seeder that forgets to state the kind
errors instead of silently authoring weekly rows.

### Scope: this is the weekly/monthly engine, not "reports"

`engine/reports.py`, `src/report.ts` and the `report_content` corpus are the
engine for **range-aggregate** reports — claims computed by holding N
consecutive `daily_guidance` rows at once. Weekly ships; monthly is the same
engine at month scale (pending its corpus and re-derived thresholds). The
**yearly** report never flows through this engine: § the audit shows a year of
tara sawtooth averages to the same middling number for every user. The proposed
alternative — a **Vimshottari composition over `dasha_content`**, structurally a
sibling of the dasha timeline rather than of this pipeline — was then measured
and **cut**, because at year scale that sibling holds too few periods to make a
claim the timeline does not already make. See § the yearly audit.

### The design error the gates caught

Worth recording, because it is the most valuable thing this task produced.

The first taxonomy classified weeks as **rising / falling / cresting / dipping /
volatile / flat** — the vocabulary anyone reaches for when asked to describe a
span. The corpus was authored, and every distinctness gate passed. Then:

```
test_all_six_shapes_occur_across_a_realistic_span
    AssertionError: classifier looks degenerate on real data: {'volatile', 'cresting'}
```

Across 26 weeks × 6 natal stars, real sky data produced **two of the six
classes**. Four sixths of the corpus was unreachable copy that every quality
gate still passed.

The cause is in `score_rules`, not the classifier. Tara's nine energies are
`55, 88, 32, 78, 42, 82, 30, 80, 90` — deliberately alternating — and tara
advances one step per day as the Moon crosses one nakshatra per day. **The daily
energy series is a sawtooth** with a ~50-point day-to-day swing and a measured
weekly spread of 48–70 in every week sampled. There is no weekly trend in this
data at all. A report claiming one would have been describing an artefact of
smoothing — precisely the unfalsifiable claim this product is positioned
against.

The taxonomy was replaced with a **distribution** claim — where the strong days
fall — which is true of the data and more actionable anyway. "Your two best days
are Thursday and Friday" goes in a calendar; "the week rises" does not.

Observed distribution over 27 natals × 26 weeks after the fix:

| shape | share |
|---|---|
| `scattered` | 50.0% |
| `centre` | 38.9% |
| `front` | 7.3% |
| `back` | 2.6% |
| `split` | 1.3% |
| `even` | **0% — unreachable** |

Two honest caveats recorded rather than hidden:

* **`even` is dead copy under `content_v3_2`.** It requires a weekly spread
  under 12; the observed minimum is 48. It is kept because `shape_of` must be
  total and because `score_rules` is tunable without a code change, so a retune
  that flattens tara makes it live immediately with copy already gated.
  `test_even_is_currently_unreachable_and_that_is_recorded_not_hidden` states
  this as a fact and tells the next person to delete it when it starts failing.
* **The shape axis carries less variety than designed.** Half of all weeks are
  `scattered`. The rotation still guarantees no repeated opening inside 17
  weeks, so the reader does not see repeated *copy* — but the *claim* repeats
  more than intended, and anchors carry more of the felt variety than the shape
  does.

### The bug the cross-validation caught

`src/report.ts` computed `week_index` from days-since-Unix-epoch. It advanced by
exactly 1 per week, exactly as Python's `toordinal() // 7` does, so every
self-consistency property held on both sides — but it started from a **different
origin**, so the two implementations selected different cells mod 11 and
produced different copy for the same week. Only agreement on an *absolute* value
catches that, which is why the golden carries `week_index` per case.

---

## 5 · The monthly report

The second report, built on the same range-aggregate engine. The design
question it had to answer first: **what is second-order at month scale that is
not second-order at week scale?** Running the weekly arithmetic over 30 days
would produce the same kind of claim over a longer list — a longer report, not
a different one.

### What monthly claims are made of: weeks

The weekly report's unit of claim is the day. The monthly report's unit of
claim is the **week** — the features below exist only once you hold 4–5 weeks
at once, and none of them exists inside any single week:

    carrier    which ISO week carries the month (shape: level / twin /
               opening / closing / core)
    hinge      whether the best and worst WEEKS are adjacent — a hard
               mid-month pivot (turn: hinge)
    halves     whether the month's two calendar halves genuinely differ
               (turn: lifts / settles / steady)
    standing   which area leads/lags/steadies across the whole month

Candidates measured on real sky (144 months × 6 natals) and **rejected**:

* **Week-over-week trajectory** ("the month rises"). The weekly means of a
  month are the tara sawtooth aliased through a 7-day window (9 and 7 are
  coprime; the phase slides two days per week). A monotone run of 4–5 such
  means describes the aliasing, not the month — the same smoothing artefact
  the weekly taxonomy already rejected at day scale. Same trap, same verdict.
* **Recurring weekday patterns** ("your Thursdays run strong"). Real in 46%
  of sampled months, but each weekday has only 4–5 samples against a 9-day
  cycle: true this month, false as the generalisation a reader will
  inevitably take from it. Recorded, not authored.

### Cross-kind collision — the central risk, and the division of labour

A subscriber reads BOTH reports, often in one sitting. If the weekly and the
monthly say "scattered, with a whiplash turn" in similar words, the pair reads
as one claim padded into two — the failure IDENTITY.md §5 solved for
nakshatra vs moon sign, one level up. The division of labour:

> **Weekly owns DAYS. Monthly owns WEEKS.**

Weekly names dated days and weekday names. Monthly names ISO weeks and
month-halves and **never names a day** — its anchors (`carrier_week`,
`thin_week`) are the weekly report's own keys, so the two kinds corroborate
instead of repeating: the monthly names the carrier week, the weekly for that
week names its days.

`tests/test_report_cross_kind.py` makes this mechanical, over the pairs that
can actually co-occur (same-movement slots; 6,630 opening pairs, 980 turn,
750 close, 450 same-key standing):

* no weekly/monthly pair in the same movement slot may share a frame or a
  skeleton;
* monthly copy may not contain a day-scale token, weekly copy may not contain
  a month-scale token (the v2 weekly corpus already satisfied this untouched);
* every monthly opening and turn line must NAME the month — both kinds speak
  of "halves", so a bare "the first half holds the better ground" could sit
  in either report, which is exactly the padding ambiguity;
* same-key standing pairs (weekly money.leads vs monthly money.leads — the
  sharpest surface) may share at most 3 content words beyond stopwords,
  frame words and the area noun.

Falsified in `tests/test_report_gates_falsify.py` with multiple signatures,
including the **vacuous pass**: an emptied monthly corpus fails the
declared-size pin AND each comparison gate's own non-empty assert — an empty
work-list has no path to a green.

### Rotation — derived from 12, not copied from 52

A monthly rotation locks to the **calendar year**: the reader's natural
comparison is this July vs last July, twelve reports apart. So the cycle to
clear is 12 — and the weekly answer inverts: **13, the one prime that could
not work at week scale (13 | 52), is the monthly optimum** — gcd(13, 12) = 1
and it is the smallest count above 12, so 13 consecutive monthly openings are
distinct (outlasting a full year) and an anniversary month repeats an opening
only every 13 years (12 ≡ −1 mod 13). Counts: 13 openings / 7 turns / 5
standings / 5 closes — pairwise coprime, each coprime with 12; the full
skeleton recurs every lcm(13,7,5) = 455 months (~38 years). One honest
pigeonhole, pinned in a docstring: 27 natal stars into 13 slots means natal
pairs congruent mod 13 share the rotation offset; they are separated by the
data instead (shape is computed per natal), exactly as weekly pairs congruent
mod 17 are.

### Thresholds — re-derived on real data

Aggregates regress to the mean: daily energies inside a week spread 48–70,
but the weekly means inside a month spread only 1.4–30.3 (median 13.7).
`LEVEL_SPREAD = 6`, `TWIN_MARGIN = 2`, `HALF_MARGIN = 4`, qualifying week =
≥ 4 in-month days. Measured distribution over 144 months: core 62%, closing
15%, opening 11%, twin 7%, level 4%; turns hinge 33%, steady 25%, lifts 23%,
settles 19%. **Every class is reachable** — unlike the weekly corpus's dead
`even` cell — and `test_all_five_shapes_occur_across_a_realistic_span` keeps
a score_rules retune from silently killing one.

### The pieces

| Piece | Where |
|---|---|
| Corpus | `db/seed/report_content_v3.json` — weekly byte-identical to v2, + 208 monthly lines (65 openings, 28 turns, 90 standings, 25 closes; 465 total) |
| Composition | `engine/reports.py` (`build_monthly_report`, `month_shape_of`, `month_turn_of`, `month_index`, `month_weeks`) |
| Corpus gates | `tests/test_report_content_seed.py` — monthly battery with its own share denominator (208 → cap 12) and frame words |
| Cross-kind gates | `tests/test_report_cross_kind.py` — 13 tests |
| Composition gates | `tests/test_report_monthly_composition.py` — 42 tests |
| Falsification | `tests/test_report_gates_falsify.py` — +15 monthly/cross-kind reds |
| Worker | `aura-api/src/report.ts` (`buildMonthlyReport`), `GET /v1/report/monthly?nakshatra=N&month=YYYY-MM` |
| Cross-validation | `aura-api/test/reportMonthly.crossval.test.ts` — 72-case golden spanning a Dec→Jan boundary, so `month_index` is checked as an absolute value (the monthly analogue of the week_index origin bug) |

The share gate fired on the first authored draft — 12 words over the cap
(`across` ×22, `work` ×21, `first` ×19, …) — and the cross-kind gate caught 4
frame collisions plus 1 content-overlap pair against the weekly corpus. All
fixed in copy (49 rewrites); no threshold, stopword or frame list was touched.

### The precompute window: 14 → 40 days

The monthly route serves only when EVERY day of the month has rows, so the
window had to cover the worst case (asked on the 1st of a 31-day month, 31
days) plus the missed-night headroom the old 14 gave `/v1/today`. Measured
before widening: +0.13 s compute, ~3 MB/night of writes. First widened run
(2026-07-21): 1,120 rows upserted (40 sky + 1,080 guidance — exact
projection), 8.7 s wall / 0.33 s CPU; `latest_sky_date` advanced 2026-08-03 →
2026-08-29; `/v1/today` and `/v1/range` unaffected. July 1–17 (before the
DB's first nightly) were backfilled with an explicit `--start`, so the current
month is complete. **Rollback** is `LOOKAHEAD_DAYS` back to 14 plus the
workflow step name: widened dates are a strict superset and upserts are
idempotent, so a failed widened run cannot leave the 14-day buffer worse than
it started.

### Premium boundary

Identical to weekly, deliberately: `/v1/report/monthly` is a paid artefact on
an open route, flagged in the route comment and here, enforced by nothing
until billing (Block 11) brings an identity the Worker can verify. Do not
ship a paid report screen against it as it stands.

---

## 6 · The transit audit — and why it is not a third report

Transit was flagged in § the audit as the surprise: more buildable than the four
life-area reports, because *gochara* is reckoned from the **Moon sign**, which we
compute and gate, rather than from the ascendant, which we do not have. That
holds. **The maths verdict is confirmed. The framing is withdrawn.**

`engine/transits.py` ships the computation layer;
`tests/test_transits.py` (27 gates) pins every measurement quoted below.

> **BUILT 2026-07-21.** Everything below was the audit; it is now implemented as
> specified, with the two decisions in § 6.9 and § 6.5 resolved by Rohan. What
> shipped:
>
> | Piece | Where |
> |---|---|
> | Schema | `db/migrations/011_report_kind_transit.sql` (widened `key_type` + `report_kind` CHECKs) · `012_transit_ingress.sql` (the ingress table) |
> | Corpus | `db/seed/report_content_v4.json` — weekly + monthly **byte-identical to v3**, + **71 transit lines** (21 weather, 36 passage, 9 phase, 5 sade_sati) |
> | Composition | `engine/transits.py` — `build_transit_reading`, `ingress_index`, `sade_sati_state`, `next_change` |
> | Seeder | `db/migrate.py::seed_report_content` (now `KEY_TYPES`-driven, all three kinds, one marker) + `seed_transit_ingress` |
> | Corpus + fear gates | `tests/test_transit_content_seed.py` — 32 tests |
> | Composition + Sade Sati cross-check | `tests/test_transit_composition.py` — 20 tests |
> | Cross-kind, three ways + within-reading | `tests/test_report_cross_kind.py` — 25 tests (was 13) |
> | Falsification | `tests/test_report_gates_falsify.py` — 68 tests (was 41) |
> | Worker | `aura-api/src/transit.ts`, `GET /v1/report/transit?moon_sign=&date=` |
> | Cross-validation | `aura-api/test/transit.crossval.test.ts` — **199-case golden** generated by `scripts/crossval_transit.py`, carrying the ingress runs as input |
>
> Two numbers below were corrected against the code in the same commit — see
> the note in § 6.5.

### 6.1 · What claim class this is

The three shipped systems and the two report kinds each have a unit:

| System | Unit | Question |
|---|---|---|
| `daily_guidance` | one **date** | what is today like? |
| weekly report | a **range** | where did the strong days fall? |
| monthly report | a **range** | which week carried the month? |
| `dasha_content` | one **period** | what is this era about? |
| **transit** | one **passage** | which slow mover stands where, and for how long? |

Weekly aggregates days. Monthly aggregates weeks. **Transit aggregates nothing.**
It reads no `daily_guidance` row at all — it has no energy series, no peak day,
no shape, no distribution. Its claim is a *standing configuration with a
duration*: Saturn is in your 12th, it has been since March, it holds until
October.

That is structurally **`dasha_content`, not a report**: keyed by a (mover,
relative-position) pair, static per key, dated by an externally computed
timeline. The task asked whether transit is "a period reading dressed as a
report". It is. Recorded as a finding, not worked around.

Two things distinguish it from dasha and are worth naming, because they are what
a transit artefact would own that nothing else does:

* **Concurrency.** Dasha has one period active per level. Transit has three
  independent movers running at once on unrelated clocks. Their *mix* is a
  claim no single passage carries — the only second-order feature here (§ 6.4).
* **It is the product's first cohort-level artefact.** Daily guidance varies by
  27 natal stars and by date. A transit reading varies by **12 Moon signs** and
  changes only a few times a year, so everyone with the same Moon sign reads the
  same thing at the same time.

### 6.2 · The measurement that settled it

For one Moon sign, the tuple of slow-mover houses (Saturn / Jupiter / Rahu),
daily scan, 2026–2036:

| | |
|---|---|
| distinct states in 10 years | **37** |
| median state length | **89 days** |
| mean | 99 days |
| longest unchanged | **375 days** |

Against a weekly report's new range every 7 days and a monthly's every ~30.

**A transit report on a calendar cadence would ship a byte-identical payload to
the previous issue for months at a stretch** — a reader on a weekly cadence
receives the same claim a dozen times running. And no rotation can rescue that:
rotating the words while the claim stands still is *decorative variety*, which
§ 3 rejects by name ("the copy differs because the week differs"). Pinned by
`test_the_transit_state_changes_far_too_slowly_to_be_a_periodic_report`, which
also states the condition under which the verdict should be revisited.

**Consequence: the natural cadence is the INGRESS, not the calendar.** A transit
artefact should be refreshed when the sky changes and notified on, not issued
weekly or monthly.

### 6.3 · What is actually computable — audited against the engine

Verified by computation, not by reading:

| | Verdict | Evidence |
|---|---|---|
| **Saturn** sign, any date | ✅ exact | Swiss Ephemeris, Lahiri VP285 |
| **Jupiter** sign | ✅ exact | " |
| **Rahu / Ketu** axis | ✅ exact, and *cleanest* | mean node: 6 crossings in 10 years, **all** retrograde, **zero** boundaries re-crossed |
| **Sade Sati** | ✅ exact — *as runs* | § 6.5 |
| **Dhaiya** (Saturn 4th/8th) | ✅ exact | `dhaiya_runs` |
| **Retrograde state** | ✅ for Saturn/Jupiter · ❌ *meaningless* for Rahu/Ketu | the mean node is retrograde by construction — always. A "Rahu is retrograde" line is true in every reading ever composed: Barnum in its purest mechanical form. Pinned. |
| **Mars, and everything faster** | ❌ **cut** | 66 sign crossings in 10 years (~1 per 55 days). At that rate a "transit reading" is a daily card wearing a longer name — and Mars is the Mangal Dosha fear vector. |
| Ascendant, houses, aspects, D9 | ❌ absent | unchanged from § the audit |

**Ketu carries no independent information.** Ketu is always exactly six houses
from Rahu — asserted across all 360 measured states. It is a position to render,
never a claim to author, so the corpus is **3 movers × 12 houses = 36 cells**,
not 48.

**The delivery constraint nobody had written down.** Gochara needs the Moon
**sign**. It is *not* derivable from the natal nakshatra index the rest of the
product is keyed by: a nakshatra is 13°20′ against a 30° sign, so **9 of the 27
straddle a boundary** — Krittika, Mrigashira, Punarvasu, Uttara Phalguni,
Chitra, Vishakha, Uttara Ashadha, Dhanishtha, Purva Bhadrapada. **A third of
readers cannot have their sign inferred.** `/v1/natal` already returns
`moon_sign` and `UserProfile.natalMoonSign` already stores it, so the input
exists — but anything transit-shaped must key on the **sign** and **404 rather
than guess** when it is absent. Pinned by
`test_nakshatra_index_cannot_determine_the_moon_sign` so it cannot be
"optimised" back to the nakshatra index later.

### 6.4 · The only second-order feature: weather

`weather()` counts how many movers stand in classically supportive houses and
returns `supported` | `mixed` | `demanding`. It is a **count over the set**, not
a synthesis of it: with no aspect computation and no yoga logic the engine
cannot say what Saturn-in-the-12th *means together with* Jupiter-in-the-5th, and
authoring pair copy would invent a claim the maths does not support.

**It votes on Saturn and Jupiter only, and that is a measurement.** Over 12 signs
× 6 years:

| voters | result |
|---|---|
| Saturn + Jupiter, unanimous | demanding 43.5% / mixed 46.4% / supported 10.1% — **all live** |
| + Rahu, unanimous | `supported` collapses to **1.8%** — dead copy |
| + Rahu, majority | `mixed` becomes **unreachable** (3 voters cannot tie) |

Adding a third voter destroys a class either way. That is the weekly corpus's
dead `even` cell arriving a second time — and this time it was caught **before**
authoring rather than after. Rahu still renders as a standing passage; it does
not vote. Pinned by `test_adding_rahu_as_a_third_voter_would_kill_a_class_either_way`.

### 6.5 · Sade Sati — the highest-liability computation in the product

The single most asked-about transit in the Indian market, and the one most
likely to be got wrong. **It is computable exactly — but only as a set of runs.**

Every consumer app that publishes "your Sade Sati runs from X to X+7.5 years" is
wrong for a meaningful share of users, for three measured reasons:

1. **Episodes detach.** Moon in Sagittarius: the main episode ends **2022-04-29**
   — and Saturn **returns** for a further 189 days, 2022-07-13 to 2023-01-17. An
   app publishing a single end date tells that reader the hard period is over
   and then goes silent when it resumes ten weeks later. That is the failure
   mode that destroys trust permanently.
2. **Phases are not monotone.** The classical 12th → 1st → 2nd progression does
   not hold in real sky. Moon in Virgo measures **seven** phase runs in one
   episode — `12, 1, 12, 1, 2, 1, 2` — because Saturn retrogrades back across
   each boundary. Copy saying "you have entered the setting phase" must survive
   saying it twice without contradicting itself.
3. **Short dips are not Sade Sati.** Moon in Pisces has a **74-day** episode,
   2022-04-30 to 2022-07-12, that satisfies the naive predicate eight months
   before the real 6.5-year passage. Calling that Sade Sati would frighten
   someone about a fortnight of sky. `SadeSatiEpisode.is_full_passage`
   separates them.

> **Correction, 2026-07-21.** This paragraph originally read "73-day,
> 2022-04-29 to 2022-07-11". Those were pre-boundary-convention numbers; at the
> 00:00 IST boundary `engine/transits.py` actually reads by, the episode is 74
> days from 2022-04-30. Corrected against the code rather than the other way
> round, and pinned exactly in
> `test_transit_composition.py::test_the_pisces_dip_is_not_called_a_sade_sati`.
> The same +1 convention applies throughout — see the cross-check below.

**Cross-checked against a published reference.** The engine's Saturn ingresses
were compared against the sidereal (Lahiri) dates published by **Drik Panchang
and AstroSage** — the two sources an Indian reader is most likely to have
checked before opening the app — over ten crossings from 2014 to 2027,
retrograde re-entries included. Sade Sati episode bounds were then checked for
**four Moon signs**: Sagittarius (the detaching episode), Pisces (the short
dip), and Capricorn and Aquarius as ordinary controls.

**One deviation, systematic, with no exceptions:** every engine run starts
**exactly one day after** the published ingress date, and every run *ends* on
the published next-ingress date exactly. That is the 00:00 IST day boundary,
not an accuracy gap — a published "Saturn enters Aquarius on 2022-04-29" means
the ingress *instant* falls during that date, so at 00:00 IST Saturn is still in
the old sign. A reader comparing our dates to Drik Panchang sees at most a
one-day difference on a passage measured in years. Pinned by
`test_saturn_ingresses_match_the_published_lahiri_reference` and
`test_the_published_offset_is_exactly_one_day_with_no_exceptions`, so a future
ayanamsa or boundary change that made the offset *vary* would fail rather than
drift.

So nothing in `engine/transits.py` merges across a gap or interpolates a nominal
duration. `sign_runs` emits one run per contiguous occupancy and is the
primitive everything else is built from. This is also a genuine accuracy
differentiator: done properly it is *more correct than the market*.

The same retrograde trap applies generally — Saturn re-crosses Pisces→Aries
twice in 2027–28; Jupiter re-crosses **seven of its twelve** boundaries within a
decade.

### 6.6 · The fear problem, and the gate for it

Transit content is where astrology apps fear-sell hardest. The binding rules
already forbid fatalism and fear-selling, and `BANNED_WORDS` already carries
`doom`, `curse`, `malefic`, `inauspicious`, `fate`, `disaster`. **That is not
enough: fear is constructible entirely from permitted words.**

> *"This is a demanding stretch. Old patterns surface. What you built may be
> tested in ways that are not immediately obvious."*

Zero banned words. Reads as dread. The rule the copy must hold instead:

> **A hard transit is named, bounded, and actionable — in that order.** The
> reader must finish knowing *what* is demanding, *how long* it lasts, and *what
> to do about it*. Remove any one and it becomes either a threat or a
> platitude.

Five gates, of which the last is the one that cannot be gamed:

1. **No planet may act on the reader.** The fatalism signature is grammatical:
   the planet as agent, the reader as patient. `Saturn tests you`, `Rahu pulls
   you`, `Jupiter brings you`. Matched as a pattern, not a word list.
2. **Every demanding line must carry an action** — an actionable second-person
   clause from the voice specs' vocabulary. IDENTITY.md §7: *never a warning the
   reader must pay to resolve.* A difficulty with no action **is** that warning.
3. **Every demanding line must be bounded** — it names its scope (a life domain)
   or its horizon (the phase, the passage, "while this lasts"). An unbounded
   negative is the definition of dread.
4. **Intensifier ban**, separate from `BANNED_WORDS`: `severe`, `intense`,
   `brutal`, `harsh`, `crushing`, `relentless`, `overwhelming`, `devastating`,
   `dire`, `grim`, `ordeal`, `suffering`, `torment`, `misfortune`, `calamity`.
5. **The symmetry gate.** For each mover, the `demanding` cells and the
   `supportive` cells must be **statistically comparable** — mean line length
   and mean content-word density within tolerance. *You cannot write dread
   without spending more words on it.* Fear-selling shows up as the hard copy
   being longer and more vivid than the easy copy, and this fires on copy that
   passes gates 1–4 completely. It is the transit analogue of the share cap:
   a measurement over the corpus that no individual line reveals.

Falsification must use **more than one signature** (per the existing suite's
standard): a planet-subject line, an actionless demanding line, an unbounded
one, an intensifier, and — the decisive one — **inflating every demanding line
by 40% with entirely permitted words**, which must fire gate 5 while 1–4 stay
green. Plus the vacuous-pass signature: an emptied demanding corpus must fail
the declared-size pin.

### 6.7 · Cross-kind, with a third term

Weekly and monthly divide by unit. Transit needs a third term that is not a
subdivision of calendar time at all:

> **Weekly owns DAYS. Monthly owns WEEKS. Transit owns PASSAGES.**

| kind | names | never names |
|---|---|---|
| weekly | dated days, weekday names | months |
| monthly | ISO weeks, month-halves | days, weekdays |
| **transit** | movers, houses, phases, multi-month spans | days, weekdays, weeks, month-halves, calendar months |

Transit is the **only** kind that may name a planet, and it may never name a
calendar unit — which makes the division mechanically checkable in both
directions and is a cleaner separation than weekly/monthly have with each other.
The existing `DAY_TOKENS` / `MONTH_TOKENS` sets extend to a third,
`PASSAGE_TOKENS`, plus a `PLANET_TOKENS` set banned from weekly and monthly copy
and *required* in transit passage copy.

Slot correspondence, since the movements differ: transit's `weather` occupies
the "what is this whole thing" slot that weekly/monthly `shape` openings hold,
and transit's `passage` occupies the per-item judgment slot that `standing`
holds. Those are the pairs worth comparing; the rest do not co-occupy a slot in
the reader's attention, the same scoping argument as the existing gate's
36-not-324.

### 6.8 · Rotation — derived from transit's own cycle

The weekly cycle is 52 and the monthly is 12. **Transit's cycle is a planetary
period, and the answer that falls out is that no rotation is needed at all.**

A reader returns to a given (mover, house) cell once per that mover's sidereal
period: **Saturn 29.5 years, Rahu 18.6, Jupiter 11.9.** Jupiter's is the
shortest, so the soonest any cell can recur is **twelve years** — against the
weekly corpus's 17-week guarantee and the monthly's 13 months. Consecutive
distinctness is free. And adding a rotation would be *actively wrong*: the claim
holds for a median 89 days, so rotating copy inside a passage changes the words
while the fact stands still.

The real repetition risk is a different one, and it needs its own gate:
**collision across movers inside one sitting.** The reader sees Saturn, Jupiter
and Rahu simultaneously, so if two share a house, two lines about the same house
arrive together. The gate is therefore a **within-reading** cross product over
(mover A, house) × (mover B, house) for A ≠ B — the transit analogue of the
cross-kind same-slot rule, applied inside one payload.

The only legitimate within-passage variation is **phase** (`early`/`middle`/
`late`, computed from the real run length, not a nominal one). That is
data-driven variety in the § 3 sense: the copy changes because the reader's
position in the passage changed.

### 6.9 · Where it should live — DECIDED

> **Rohan's call, 2026-07-21: `report_content` with the widened CHECK**
> (migration 011), one `active_content` marker across all three kinds.
> Rationale as recorded: the cross-kind gate must compare transit against
> weekly *and* monthly, and a `dasha_content` sibling would put that comparison
> across two tables behind two markers — which is exactly the "pairing no gate
> ever saw" state migration 010 exists to prevent. **Transit's dasha-like
> structure governs its composition code, not its storage**, and § 6.1's
> finding stands unchanged as a finding.

The brief specified `report_kind='transit'` in `report_content`. Given § 6.1 that
was a genuine question rather than a given:

* **`report_content`, `report_kind='transit'`.** Keeps ONE activation marker
  across all long-form copy, which is the property 010's reasoning actually
  cares about — a half-rolled-back state stays inexpressible. Costs a widened
  `key_type` CHECK (migration 011), since transit's key types (`passage`,
  `phase`, `weather`, `sade_sati`) are disjoint from `shape|turn|standing|close`.
* **A sibling of `dasha_content`.** Matches the structure honestly, and matches
  the cadence (both are period readings dated by a computed timeline). Costs a
  second marker and a second rollback path.

**Recommendation: `report_content` with the widened CHECK.** The structural
finding changes the *cadence, the rotation and the gates* — all of which are
recorded above — but not the *versioning mechanics*, which are the only thing
the table choice actually governs. One marker is worth more than taxonomic
tidiness.

### 6.10 · Data delivery

Slow-mover positions should reach the Worker as a **precomputed ingress table**
seeded by this engine — not recomputed in-Worker with astronomy-engine as
`/v1/natal` does. Sign runs for three movers over a wide span are a few hundred
rows that change never; a lookup needs no second implementation, so there is no
drift surface and no crossval burden for the maths (only for the composition).
That is a strictly better trade than the one `/v1/natal` had to take.

---

## 7 · The yearly audit — and why it is CUT

§ 2 gave yearly a **reframe** verdict: not from daily aggregates, because a year
of tara sawtooth averages to the same middling number for every user, but
rebuilt on **Vimshottari**, which genuinely varies over years and already has a
gated corpus. This section measures that reframing. **It does not survive.**

`tests/test_yearly_verdict.py` (4 gates) pins every number below.

> **VERDICT: CUT.** Not deferred, not blocked on maths we lack — cut, because
> the measurement says a yearly report re-renders rows the app already renders.
> No corpus was authored, no migration written, no route added. Authoring ~200
> lines against a structure the measurement argues against would be the
> expensive way to learn this, which is the § 6 lesson applied a second time.

### 7.1 · The measurement

120 natals (moon longitude × birth date, deterministic spread) × the ten
calendar years 2026–2035 = 1,200 samples:

| | |
|---|---|
| antar boundaries per calendar year | **mean 0.67** — 40.9% of years have *none*, 51.5% have one |
| maha boundaries per calendar year | **mean 0.08** — 92.1% of years have none |
| antar periods *touching* a year | **mean 1.67** |
| median antar length | **404 days** — against a 365-day cadence |
| years with no boundary of any kind | **40.9%** |
| consecutive year pairs sharing (era, dominant sub-period) | **41.6%** |

### 7.2 · The structural kill: there is no shape over N = 1.7

§ 1 defines a report as an artefact whose every claim is a **second-order
feature** — distribution, spread, position, adjacency — that exists only once
you hold N units at once. That definition is what makes weekly and monthly
reports rather than longer cards.

Weekly holds **7 days**. Monthly holds **4–5 weeks**. A yearly report over
Vimshottari holds a mean of **1.67 antar periods**, and **exactly one, 41% of
the time**.

**There is no distribution over 1.7 items.** Every candidate second-order
feature — which period dominates, where the handover falls, whether the year is
split — collapses to a first-order restatement of the one period the reader is
already in. Yearly is squeezed from both sides, and this is the finding worth
carrying forward:

* **from daily data** — 365 samples, but § 2 already established there is no
  signal in them at year scale;
* **from Vimshottari** — real signal, but N ≈ 1.7, too few items for any
  second-order feature to exist at all.

A range-aggregate engine needs enough samples to have a shape. A period system
needs the period to turn over faster than the cadence. Yearly satisfies
neither, and there is no third source.

### 7.3 · The transit failure mode, one cadence up

§ 6.2 withdrew the transit *report* framing because the state held for a median
89 days against a 7-day cadence. The identical test at year scale: the median
antar runs **404 days against a 365-day cadence**, so the state **still**
outlives the report that would describe it. 40.9% of years contain no boundary
at all — that year's report is a verbatim reissue of the previous one — and
41.6% of consecutive year pairs open on the same (era, dominant sub-period)
headline.

And rotation cannot rescue it, for the reason § 3 states by name: rotating the
words while the claim stands still is **decorative variety**. That argument
killed a 7-day cadence in § 6.8; it applies with more force at 365 days, where
a repeat costs the reader a year rather than a week.

### 7.4 · Cross-kind, the fourth way — where it actually fails

The brief asked for the cross-kind gate extended to four kinds. Extending it
was not necessary, because the collision is not a *copy* collision that a gate
could referee. It is total:

> **Weekly owns DAYS. Monthly owns WEEKS. Transit owns PASSAGES.
> Yearly owns NOTHING that the dasha timeline does not already own.**

Every candidate yearly claim, against what ships today:

| candidate yearly claim | already shipped by |
|---|---|
| which era you are in | `astro-dasha-current` (lord, title, essence, favours/watch) · `astro-dasha-timeline` |
| which sub-period dominates the year | `astro-dasha-current` — the running antar, which *is* the dominant one in 51% of years at >90% coverage |
| when the sub-period hands over | `astro-dasha-current` (`untilLabel`, `remainingLabel`) · `astro-dasha-detail`, which dates **all nine** antars |
| what the incoming sub-period asks | `astro-dasha-detail` — tap the next sub-period, it expands its `line` + `now` |
| whether a new era begins this year | `astro-dasha-timeline` — proportional bars with the running era marked (and available in only 8% of years) |

Weekly vs monthly needed a mechanical gate because they were *adjacent* claims
that could be worded into each other. Yearly is not adjacent to the dasha
timeline — **it is a subset of it with a twelve-month date filter applied**,
composed from the *same* `dasha_content` rows (`maha`, `maha_antar`) the two
shipped screens already render. There is no division of labour to write down,
because there is no labour left to divide.

### 7.5 · What would change this verdict

Stated so the cut is revisitable rather than permanent, and so the gates have a
meaning when they fail:

* **A yearly artefact keyed on something other than Vimshottari** — the four
  life-area outlooks, if the Block 8 houses engine lands, would give a year
  scale real content (house lords, annual profections). That is a different
  report with a different input, not this one.
* **`test_a_year_holds_too_few_dasha_periods_to_have_a_second_order_feature`
  failing** — if a year ever held enough periods to have a distribution.
* **A pratyantar-level year.** Level 3 turns over far faster and *would* give N
  in the tens. Not pursued: `dasha_content` authors copy at maha and maha_antar
  only, so this needs 729 new cells, and § 6.3's Mars verdict applies — at that
  rate it is a daily card wearing a longer name.

### 7.6 · What this leaves in Block 3

Of the ten: weekly ✅ · monthly ✅ · transit ✅ (as a passage reading, not a
report) · **yearly ❌ cut** · marriage ❌ cut · KP ❌ cut · PDF ⏸ · career /
finance / business ⚠️ blocked on the Block 8 houses engine. **Every report that
can be built without houses is now built.** Block 3 is closed on content; what
remains in it is gated on an engine capability, not on authoring.

> **Superseded 2026-07-21 for the three ⚠️ rows.** "Blocked on the Block 8
> houses engine" was the right verdict for a *house reading*, but it left open
> the reframe § 2 offered — an honest per-area **period outlook** built on the
> six daily area scores we already ship. That reframe was measured before it was
> authored and it is **CUT**. See § the area-outlook audit.

---

## 7A · The area-outlook audit — and why career / finance / business are CUT

§ 2 gave career, finance and business a **reframe or defer** verdict: without an
ascendant they cannot be house readings, but they might survive as honest
"period outlook for Career" artefacts built on the six life-area scores
`daily_guidance` already carries. This section measures that reframing. **It
does not survive**, and for a sharper reason than yearly's.

`tests/test_area_outlook_verdict.py` (6 gates) pins every number below.

> **VERDICT: CUT** — as *period outlooks*. The daily area lines, the six scores
> on the score-detail screen, and the Block 6 Life hub are untouched and remain
> the right home for area content. What is cut is the periodic artefact.
> No corpus was authored, no migration written, no route added.

### 7A.1 · The measurement — and the structural fact behind it

Read off `engine/scoring.py` rather than inferred:

    score(area, date) = clamp(base(natal, date) + weekday_area_mod[wd][area])
    energy(date)      = clamp(base(natal, date) + weekday_energy_mod[wd])

`base` is the tara + paksha term. **It is identical for all six areas** — it
*is* the energy series the weekly and monthly reports are already built on. The
only area-dependent term is `weekday_area_mod`, a fixed 7 × 6 integer table:
the same for every user, every month, every year, forever.

27 natals × 24 months of real sky (2026–2027):

| | |
|---|---|
| area scores reproduced **exactly** from (energy, weekday) alone | **59,130 / 59,130 = 100.00%** |
| corr(area daily series, energy daily series), worst of 6 areas | **+0.978** |
| corr(area monthly mean, energy monthly mean), worst of 6 | **+0.984** |
| distinct areas that ever **lead** a month, across all 648 months | **2 of 6** |
| share of months led by `money` | **94.4%** |
| consecutive month pairs with an identical (leader, per-area band) headline | **63.3%** |

The first row is the kill shot, and it is worth stating precisely: this is not
"highly correlated". An area score is a **deterministic function of the energy
value and the day of the week** — it carries zero independent information. An
outlook composed from these scores cannot make a claim that the energy series
plus a lookup table does not already make.

### 7A.2 · It is the aliasing artefact, promoted to the headline

The brief asked whether this is the 9-day tara sawtooth aliased again. It is
worse than aliasing — it is a **7-periodic constant**, which the monthly audit
already rejected twice under different names:

* **week-over-week trajectory** — rejected in § the monthly report as the tara
  sawtooth aliased through a 7-day window;
* **recurring weekday patterns** ("your Thursdays run strong") — measured real
  in 46% of months, recorded but **not authored**, because each weekday has 4–5
  samples against a 9-day cycle: true this month, false as the generalisation.

"Career runs strong over the next month" is that second rejected claim with the
weekday name deleted and a period cadence attached. The generalisation the
reader takes from it is *more* wrong than the weekday version, not less,
because it drops the one qualifier that made it checkable.

### 7A.3 · Standing is Barnum, mechanically

Standing — which area leads, lags, steadies — is the one genuinely second-order
area feature, and it is the one weekly and monthly reports already carry. At
month scale it collapses: **only two of six areas ever lead, and `money` leads
94.4% of months**. Every user is told the same thing in the same month, and
nearly the same thing every month.

This is § 6.3's Rahu-retrograde finding in another key. There, "Rahu is
retrograde" was cut because the mean node is retrograde by construction, so the
line is true in every reading ever composed — Barnum in its purest mechanical
form. "Money leads your month" is true in 94% of them. Same verdict, same
reason.

The 63.3% consecutive-repeat rate is the § 6.2 / § 7.3 test one more time: the
state outlives the report that would describe it, and rotation cannot rescue it
because rotating words while the claim stands still is decorative variety.

### 7A.4 · Cross-kind, the fourth way — the collision is with the DAILY lines

The brief flagged the daily area lines as the real collision risk. Correct, and
it is where the gate would have to sit — but there is no gate to write, because
the collision is total rather than adjacent:

> **Weekly owns DAYS. Monthly owns WEEKS. Transit owns PASSAGES.
> An area outlook owns NOTHING that the daily area lines, weekly standing and
> the Life hub do not already own.**

| candidate area-outlook claim | already shipped by |
|---|---|
| what Career is like today, and why | `score_why` (RECOGNITION + CAUSE, six different sources per date) · `area_lines` |
| where Career sits on a scale | `band_labels` — a 6 × 5 vocabulary, no label shared between areas |
| which area leads / lags this week | weekly report **standing** movement |
| which area leads / lags this month | monthly report **standing** movement |
| Career's shape over a period | the energy shape — measured above at r > 0.98, so this is the weekly/monthly report with one noun swapped |
| a durable, per-area home to browse | Block 6 **Life hub** + the ten area screens |

Weekly vs monthly needed a mechanical referee because they were adjacent claims
that could be worded into each other. An area outlook is not adjacent to the
daily lines — it is **the same scores, summed**. There is no division of labour
to write down because there is no labour left to divide.

### 7A.5 · It does not differ by area — and two have no input at all

The brief asked whether the answer is uniform across the ten. It is not, but
not in the direction that would help:

* **career** → the `career` score exists. Emptied by 7A.1.
* **finance** → maps to `money`. Emptied by 7A.1, and it is the 94.4% Barnum
  leader on top of that — the *worst* of the six, not the best.
* **business** → **no scored area exists.** There is no input whatsoever.
* **marriage** → **no scored area exists.** `love` is not marriage, and
  conflating them is precisely the reputational liability § 2 cut marriage for.

So the reframe could at most have covered two of the four, and the measurement
empties exactly those two.

### 7A.6 · What would change this verdict

Stated so the cut is revisitable rather than permanent:

* **`test_an_area_score_is_fully_determined_by_energy_and_weekday` failing** —
  if an area ever gains an input that energy does not have. The Block 8 houses
  engine is that input: a 10th-lord term would make career genuinely
  area-specific, and this audit would be re-run rather than assumed.
* **A retune of `weekday_area_mod`** that made standing vary by natal — but note
  that a fixed table *cannot* do this by construction, so this needs a new term,
  not new numbers.
* **Areas keyed on something other than the daily scores** — a house-based
  reading is a different artefact with a different input, not this one.

### 7A.7 · What this leaves in Block 3 — final

Of the ten: weekly ✅ · monthly ✅ · transit ✅ (passage reading) · yearly ❌ ·
**career ❌ · finance ❌ · business ❌** (as period outlooks; revisitable on the
Block 8 houses engine) · marriage ❌ · KP ❌ · PDF ⏸.

**Block 3 is closed.** Three reports ship. Nothing in it is waiting on
authoring; what remains is waiting on an engine capability that is not in the
launch sequence.

---

## 8 · The premium boundary

**Recommendation, not implementation** — billing is Block 11.

### Where the line sits

Daily guidance stays **free**. It is the habit loop, notifications depend on it,
and it is what makes the app worth opening. Reports are the **paid** surface:
they are the artefact a user would pay for precisely because they are periodic
rather than daily.

### Who should enforce it

**The API, not the app.** A client-side paywall in front of an open Worker route
is not a boundary; it is a suggestion. Anyone can call
`/v1/report/weekly?nakshatra=7&week=2026-07-20` directly.

### The gap, stated plainly

Neither route shipped here enforces anything.

* `/v1/report/content` serves only the **corpus** — authored sentences with no
  user data. Leaving it open costs the copy, not a customer's reading. Low risk.
* `/v1/report/weekly` serves the **composed report**. This is the paid artefact
  and it is currently fetchable by anyone who can guess an integer 0–26.

**Do not ship a paid report screen against the current route.** That is recorded
in the route comment as well as here.

### Why it cannot be closed yet

The Worker has no identity it can verify. The app is guest-first by binding
decision, and `/v1/events` accepts an unauthenticated `device_id`. Enforcement
needs either Neon Auth (Phase 2, deferred sign-in) or store-receipt validation —
both of which land with billing. The clean shape when it does: validate the
receipt server-side, mint a short-lived signed entitlement token, and require it
on `/v1/report/weekly` only.

### One structural risk worth knowing

A weekly report has **only 27 distinct payloads per week** — one per natal
nakshatra. Even with perfect authentication, the entire week's report set is 27
requests. Reports are therefore not a *secret*; they are a *convenience*. The
paywall protects the experience — delivery, history, notifications, the screen —
not the underlying text. Worth knowing before anyone invests heavily in
hardening the route.

---

## What is deliberately not here

Any UI or screens · PDF rendering · billing · language work.

**The life-area outlooks specifically.** § the area-outlook audit ships the
*measurement and its gates* (`tests/test_area_outlook_verdict.py`) and the
design record. It deliberately ships **no** corpus, migration, composition code
or route, because the measurement argued against the structure before authoring
began — the § 6 lesson applied a third time. The daily area lines, the six
score-detail areas and the Block 6 Life hub are untouched; what is cut is the
periodic artefact, not area content.

**Yearly specifically.** § the yearly audit ships the *measurement and its
gates* (`tests/test_yearly_verdict.py`) and the design record. It deliberately
ships **no** corpus, migration, composition code or route, because the
measurement argued against the structure before authoring began — the § 6
lesson applied a second time, and the cheaper end of it.

**Transit — no longer pending.** This paragraph previously listed the corpus,
the fear gates, migration 011, the ingress table, `/v1/report/transit` and the
crossval golden as *not* shipped, held on the § 6.9 storage decision. Rohan
decided 6.9 on 2026-07-21 and **all of it shipped the same day** — see the BUILT
block in § 6. Delivery is done too, verified against production the same day:
`/v1/report/transit` returns a composed reading carrying real ingress runs, so
the Worker is deployed and `transit_ingress` is seeded. **Nothing for transit is
pending.**
