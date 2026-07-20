# content_v3 — the multi-variable content key scheme

## The problem this fixes

content_v2 keyed every piece of per-area copy on **tara alone** (9 values,
identical for all six areas on a given day, since tara is a property of the
*day*, not the area). Result: all six area cards inherited one mood per day,
and the score-detail "why" fell through to a single swap-the-area-name
template. Testers read every card as the same card.

## The v3 key

Every score-detail card is composed from **two authored sentences**, each
resolved by its own key. No runtime LLM, no randomness — the key is a pure
function of (area, that area's score, the day's sky):

```
score_why[area] = RECOGNITION + " " + CAUSE

RECOGNITION = why_recognition[area][band][moon_group]
CAUSE       = why_cause[area][weekday_index][paksha]
band_label[area] = band_labels[area][band]
```

| Variable | Values | Source | Changes |
|---|---|---|---|
| `area` | 6 (love, money, career, mind, health, mood) | — | per card |
| `band` | 5 (peak ≥85, high ≥70, mid ≥55, low ≥40, deep <40) | that **area's own score** (tara base + weekday area mod + paksha) | per area per day |
| `moon_group` | 3 (gentle, steady, sharp) | the day's Moon-nakshatra gana (deva → gentle, manushya → steady, rakshasa → sharp), seeded as `moon_groups` | roughly daily |
| `weekday_index` | 7 (Mon=0 … Sun=6, day lord Moon…Sun) | calendar | daily |
| `paksha` | 2 (waxing, waning) | sky | fortnightly |

Cell counts: recognition 6×5×3 = **90**, cause 6×7×2 = **84**, band labels
6×5 = **30**. All live in `db/seed/score_rules_content_v3.json` → the
`score_rules` table — tunable without a code change.

## Why two areas can never read the same

1. **Disjoint corpora.** Every cell is authored per-area against that area's
   voice spec (`docs/voice/*.md`). The CI diversity gate
   (`tests/test_content_diversity.py`) *fails the build* if any two areas
   share a band label, share a line, or share a sentence skeleton — so the
   guarantee is enforced, not hoped for.
2. **Independent band resolution.** Each area's band comes from its own
   score, so Money can sit `deep` while Love sits `mid` on the same date.
3. **Sentence roles are separated.** RECOGNITION names what the person may
   be feeling in that domain (varies with band + the Moon's texture); CAUSE
   gives one plain-language reason from the sky (day lord + waxing/waning).
   Actions live in the chips below the card and are never repeated in the
   why-copy.

CAUSE lines are deliberately **band-neutral** (they describe the day's
flavour, not its favourability) so any recognition + cause pairing reads
coherently.

## Determinism

Same date + same natal nakshatra + same rules version → byte-identical
output (`test_precompute.py` asserts this). No `now()`, no unseeded RNG.
The v2 `area_lines` (area × tara, date-rotated variants) carry over
unchanged for the calendar day view.
