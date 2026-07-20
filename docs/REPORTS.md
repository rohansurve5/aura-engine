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
| 2 | **Monthly** | ✅ **Buildable** | Extend the precompute window 14 → ~40 days; re-derive the shape thresholds at month scale |
| 3 | **Yearly** | ⚠️ **Reframe** | Not from daily aggregates — see below. Rebuild on Vimshottari, which we already have and have gated |
| 4 | **Career** | ⚠️ **Reframe or defer** | No 10th house. Shippable only as an honest "period outlook for Career", never as a natal career reading |
| 5 | **Marriage** | ❌ **Cut for launch** | No 7th house, no D9, no Venus analysis — *and* highest reputational liability of the ten |
| 6 | **Finance** | ⚠️ **Reframe or defer** | No 2nd/11th house. `docs/voice/money.md` already bans instrument advice and outcome guarantees — the report's own name overpromises |
| 7 | **Business** | ⚠️ **Reframe or defer** | Same as career; the weakest distinct case of the four |
| 8 | **Transit** | ✅ **Buildable — the surprise** | See below. No new maths |
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
(`dasha_content_v2`). A yearly report should be built on that.

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

**2 · Variant rotation on mutually coprime primes.** 11 openings, 7 turn lines,
5 closes. None shares a factor with 52. The opening index is

```
variant = (week_index * 1 + natal_index * 3) % 11
```

`week_index` advances by exactly 1 per week, so over any **11 consecutive weeks**
the index takes 11 distinct values. If those weeks share a shape, the 11
openings drawn are distinct by that arithmetic; if they do not share a shape,
they come from disjoint corpora and are distinct anyway. **Either way a reader
cannot see a repeated opening inside 11 weeks** — and the same argument gives 7
for turns and 5 for closes. Combined period: `lcm(11,7,5) = 385` weeks, over
seven years of continuous reading before the triple can recur.

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
| Schema | `db/migrations/009_report_content.sql` |
| Seed | `db/seed/report_content_v1.json` — 221 lines |
| Composition | `engine/reports.py` |
| Seeder + marker | `db/migrate.py::seed_report_content` |
| Corpus gate | `tests/test_report_content_seed.py` — 27 tests |
| Composition gate | `tests/test_report_composition.py` — 57 tests |
| Falsification | `tests/test_report_gates_falsify.py` — 26 tests |
| Worker composition | `aura-api/src/report.ts` |
| Endpoints | `GET /v1/report/content`, `GET /v1/report/weekly` |
| Cross-validation | `aura-api/test/report.crossval.test.ts` — 72-case golden |

Corpus shape: 6 shapes × 11 openings = 66; 5 turn kinds × 7 = 35; 6 areas × 3
roles × 5 = 90; 6 shapes × 5 closes = 30. **221 authored lines.**

Versioning uses the `active_content` marker from version one — no `max(version)`
anywhere, enforced as a property of the source by
`test_no_kind_selects_its_version_by_inference`, which now covers all four
seeders.

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
  `scattered`. The rotation still guarantees no repeated opening inside 11
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

## 5 · The premium boundary

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

The other nine reports · any UI or screens · PDF rendering · billing ·
language work. The weekly report is one report proven, which is the point.
