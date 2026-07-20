# content_v3_1 — the multi-variable content key scheme

## The problem v3 fixed

content_v2 keyed every piece of per-area copy on **tara alone** (9 values,
identical for all six areas on a given day, since tara is a property of the
*day*, not the area). Result: all six area cards inherited one mood per day,
and the score-detail "why" fell through to a single swap-the-area-name
template. Testers read every card as the same card.

## The problem v3_1 fixes

content_v3 separated the RECOGNITION halves properly, but every area's CAUSE
half resolved from **one source**: `(day lord × paksha)`. So on 2026-07-20 all
six cards explained themselves through the weekday's planet, in six near-identical
framings — *"Monday belongs to the Moon" / "Monday is the Moon's own day" /
"Monday opens the week under the Moon" / "Monday is governed by the Moon" /
"Monday's Moon pulls thought towards feeling" / "The Moon rules both Monday and
your inner weather."* A tester tapping three cards sees the seam immediately.

The corpus-wide diversity gate could not catch this, and no threshold tightening
would have: its denominator is the whole ~700-line seed, while the unit that
matters is **what one person reads in one day** — six lines, of which six shared
a source. See *Two gates, two denominators* below.

## The v3_1 key

Every score-detail card is composed from **authored sentences**, each resolved by
its own key. No runtime LLM, no randomness — the key is a pure function of
(area, that area's score, the day's sky, the reader's birth star):

```
score_why[area] = RECOGNITION + " " + CAUSE       (CAUSE may be empty)

RECOGNITION = why_recognition[area][band][moon_group]
CAUSE       = resolved from the source cause_rotation gives this area today
band_label[area] = band_labels[area][band]
```

### The six CAUSE sources

`CAUSE` answers "why does today feel like that?" — and there is no single right
answer, so v3_1 draws from six genuinely different explanations, each with its
own natural framing and its own corpus:

| Source | Key | Cells | The framing it speaks in |
|---|---|---|---|
| `daylord` | `why_cause[area][weekday][paksha]` | 6×7×2 = 84 | the weekday's planet (v3's corpus, now one voice among six) |
| `nakshatra` | `why_cause_nakshatra[area][trait]`, `{nakshatra}` interpolated | 6×7 = 42 | the day-Moon's star and its character |
| `paksha` | `why_cause_paksha[area][paksha][variant]` | 6×2×3 = 36 | the fortnight's direction, standing alone |
| `tara` | `why_cause_tara[area][tara]` | 6×9 = 54 | the count from **the reader's own birth star** — the most personal source we have |
| `phase` | `why_cause_phase[area][phase_name]` | 6×8 = 48 | the Moon's visible shape tonight (how much light, not which direction) |
| `none` | — | — | **no cause at all**: the recognition stands alone. Not every line needs explaining, and one short card among longer ones is texture, not a gap. |

`nakshatra_traits` maps each of the 27 nakshatras to its classical activity
nature — `chara` (movable), `sthira` (fixed), `ugra` (fierce), `mridu` (soft),
`kshipra` (swift), `tikshna` (sharp), `mishra` (mixed).

`tara` lines are written as **texture, not verdict** — they describe tempo and
what the day asks, never whether outcomes will be good or bad — because an
area's band comes from its own score and can disagree with the tara's classical
reputation. All non-`tara` sources are band-neutral for the same reason: any
recognition must pair coherently with any cause.

### The rotation

`cause_rotation` is a **12-row table**, each row a permutation of the six sources
over the six areas in `areas.order`. The row for a date is
`cause_rotation[date.toordinal() % 12]`, so:

* **within a date** — the row is a permutation, so the six areas draw six
  *different* sources. Six-of-six can never recur, by construction;
* **across dates** — the row advances daily, and over the 12-row cycle **every
  area meets every source exactly twice**. No user can learn that Money is
  always explained one way;
* the rotation is **natal-independent**, so the day has one shared shape, while
  the `tara` source keeps the per-reader personalisation.

Rotation period is 12; the weekday period is 7 and coprime, so a given
(area, source, weekday) combination recurs only every **84 days**.

Cell counts overall: recognition 6×5×3 = **90**, cause **264** across five
corpora, band labels 6×5 = **30**. All live in
`db/seed/score_rules_content_v3_1.json` → the `score_rules` table — tunable
without a code change.

## Two gates, two denominators

Both run in CI *and* gate the nightly pre-seed (`.github/workflows/`):

* `tests/test_content_diversity.py` — the **corpus** gate. Protects the library:
  no signature word above a 6% share, no band label shared between areas, no
  sentence skeleton shared between areas, no banned vocabulary.
* `tests/test_per_day_distinctness.py` — the **per-day** gate. Protects the
  *reading*: for a fixed 120-day span (longer than the 84-day cycle) plus the
  live rolling 14-day precompute window, across six natal nakshatras, it asserts
  that no two areas on the same date share a cause source, an opening frame
  (first four words) or a sentence skeleton — for the cause halves and for the
  fully rendered cards.

The distinction is the lesson worth keeping: **a corpus can be perfectly diverse
and still render six identical-feeling cards**, because diversity measured over
the library says nothing about the slice one reader sees at once. Any future
content variable needs a gate at the rendering unit, not just the corpus.

## The variables

| Variable | Values | Source | Changes |
|---|---|---|---|
| `area` | 6 (love, money, career, mind, health, mood) | — | per card |
| `band` | 5 (peak ≥85, high ≥70, mid ≥55, low ≥40, deep <40) | that **area's own score** (tara base + weekday area mod + paksha) | per area per day |
| `moon_group` | 3 (gentle, steady, sharp) | the day's Moon-nakshatra gana (deva → gentle, manushya → steady, rakshasa → sharp), seeded as `moon_groups` | roughly daily |
| `cause_source` | 6 (see the table above) | `cause_rotation[ordinal % 12]` | per area per day |
| `trait` | 7 (chara, sthira, ugra, mridu, kshipra, tikshna, mishra) | the day-Moon nakshatra's activity nature, seeded as `nakshatra_traits` | roughly daily |
| `tara` | 9 | counted natal nakshatra → day-Moon nakshatra | per reader per day |
| `phase` | 8 (New Moon … Waning Crescent) | sky | every ~3.7 days |
| `weekday_index` | 7 (Mon=0 … Sun=6, day lord Moon…Sun) | calendar | daily |
| `paksha` | 2 (waxing, waning) | sky | fortnightly |

## Why two areas can never read the same

1. **Different explanation sources.** The rotation row for a date is a
   permutation, so the six areas never explain themselves from the same source
   on the same day — the v3 failure is now structurally impossible, not merely
   unlikely.
2. **Disjoint corpora.** Every cell is authored per-area against that area's
   voice spec (`docs/voice/*.md`). The corpus gate *fails the build* if any two
   areas share a band label, a line, or a sentence skeleton.
3. **Independent band resolution.** Each area's band comes from its own
   score, so Money can sit `deep` while Love sits `mid` on the same date.
4. **Sentence roles are separated.** RECOGNITION names what the person may
   be feeling in that domain (varies with band + the Moon's texture); CAUSE
   gives one plain-language reason from the sky. Actions live in the chips
   below the card and are never repeated in the why-copy.

## Determinism

Same date + same natal nakshatra + same rules version → byte-identical
output (`test_precompute.py` asserts this). No `now()`, no unseeded RNG.
Cause-source selection is a pure function of the date ordinal, and the
`paksha` source's variant rotation reuses the existing `_pick` scheme.
The v2 `area_lines` (area × tara, date-rotated variants) carry over
unchanged for the calendar day view.
