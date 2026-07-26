# Knowledge — voice spec (the interpretive significations corpus)

The corpus behind **what the system means**: 27 nakshatra significations, 9
planet meanings, 12 house meanings. This is the layer three consecutive blocks
flagged as *"gated content, not a screens task"* and deferred — the mantra and
affirmation screens, the planet-detail screen, and the interpretive half of the
Block 7 knowledge hub all stopped at this boundary.

**Status: SPEC ONLY. Zero entries authored.** This document exists so the
DESIGN is approved before a word is written — the same order that
`IDENTITY.md` established and that `dasha_content_v1` proved necessary by
being authored first, failing its own spec, and being thrown away at 90
entries. The write-off here would be 48 entries plus, uniquely in this
pipeline, an astrologer's review time.

**One thing this spec does that no previous voice spec did:** it makes a human
review gate **mechanically un-skippable** (§8). Every other corpus in this repo
ships with "astrologer review pending" recorded honestly in the launch plan and
never resolved. That works for copy about a *day*. It does not work for a
corpus whose entire claim is *this is what the tradition says*, because no test
that could be written distinguishes a well-written correct signification from a
well-written wrong one.

---

## 0. What this is NOT — the Block 7 line

Block 7 (`93aa31f`) shipped a **definitional** knowledge base in the app:
`astro-knowledge-hub`, four expandable cards, static kit content, no corpus, no
endpoint. Its content decision is on the record and stands: *what a nakshatra /
dasha / house / panchang term IS* is pure fact — 27 names, 13°20′ segments,
nine dasha lengths summing to 120 years, five panchang limbs. It forecasts
nothing, prescribes nothing, and frightens no one, so it needed no gate.

This corpus is the other half, and it is a different kind of thing:

| | Block 7 definitional | This corpus |
|---|---|---|
| Claim type | verifiable fact | traditional interpretation |
| Example | "The 8th house is one of twelve divisions of the chart." | "The 8th house is read for what arrives without being chosen." |
| Can be wrong how | factually | doctrinally |
| Checkable by | anyone with a reference | an astrologer, and only an astrologer |
| Gate | none needed | this document |

The definitional layer is the **floor** this corpus builds on and may not
restate (§6c). A reader who taps through both must not read the same sentence
twice in two registers.

---

## 1. Scope

### The entry set: 48 entries in three categories

| Category | n | What it interprets | The data it attaches to |
|---|---|---|---|
| **nakshatra** | 27 | What each of the 27 stars is traditionally read for — the domain, not the person born under it | `natalNakshatraIndex` on `UserProfile`, from `/v1/natal`. Also the day-Moon's star, already used by `why_cause_nakshatra`. |
| **planet** | 9 | What each graha is traditionally read for | The nine grahas from `/v1/chart` (sidereal sign + Whole Sign house each), the dasha lord from `/v1/dasha`, and the weekday day-lord already used by `why_cause`. |
| **house** | 12 | What each of the twelve houses is traditionally read for | The 12 Whole Sign houses counted from the lagna (`/v1/chart`, `/v1/natal` `ascendant`). Also the transit house named by `why_cause_house` in `score_rules_content_v4`. |

Every category attaches to data **already computed and already gated**. Nothing
in this corpus requires a new engine capability, a new crossval suite, or a new
number. That is deliberate: the copy is the whole risk here, and mixing it with
a compute change would mean two unproven things landing at once.

### Hard exclusions — boundaries, not preferences

**1. Nothing the engine cannot compute.**
No KP sub-lords and no D9/navamsa. `docs/CHART.md` is explicit that Placidus
cusps, MC and KP are not ported and serve KP only, which is out of scope; the
product chart is Whole Sign. A corpus entry that reads a sub-lord or a
divisional chart is describing a system Aura does not have, so it can never be
connected to a real reader's data — it would be decoration claiming to be
personalisation. Also excluded for the same reason: aspects (`drishti`),
combustion, retrogradation beyond the direction flag `/v1/chart` already
returns, yogas, and any planetary-strength scheme (shadbala, avastha).

**2. Nothing predictive.**
No `you will`, no "brings", no "results in", no timing claims, no outcomes. The
corpus states what a domain *is read for*, never what happens in it. This is a
harder line than it looks: significations in traditional texts are usually
written as predictions about a class of people, and translating them without
carrying the prediction across is most of the authoring work.

**3. Nothing remedial.**
No gemstone, mantra, chant, donation, fast, puja, yantra, rudraksha, temple,
ritual, propitiation, or `dosha`/`parihara` framing. Block 5B (`0a46c32`)
measured the spiritual-and-remedies surface and cut **all of it** — that
decision is upstream of this spec and this corpus does not reopen it. A
signification that names a problem and a remedy in the same breath is the exact
fear-sell-then-charge shape Aura refuses.

**4. Nothing commercial.**
The standing `tender` ban across every voice doc. No entry may create a need
the app then sells against. This corpus ships **free**, alongside the
definitional layer.

**5. Nothing about a specific reader.** — see §4, which is large enough to be
its own section.

---

## 2. The axis: one jurisdiction, one demand

The existing corpora each value something transient the reader is passing
through. Daily guidance runs **good ↔ careful**, because it values a *day*.
`dasha_content_v2` runs **demanding ↔ generous**, because it values a *period*.
`IDENTITY.md` has no axis across the corpus at all, because a person is not a
position on a line; its tension is internal — **one root, two outputs**.

This corpus values neither a state nor a person. It describes **standing
meaning**: what a thing in the system is *for*, independent of any date and any
chart. So it takes the internal-tension shape from identity, with a different
pair of terms:

> **Every entry names one JURISDICTION and one DEMAND.**
>
> The **jurisdiction** is the part of life the tradition reads this thing for.
> The **demand** is the one thing that jurisdiction will not let anyone do.

> The 8th house is read for what arrives without being chosen — inheritance,
> upheaval, the things other people decide for you. Its demand: nothing in it
> can be arranged in advance, which is why planning is the wrong tool there.

Not a domain and a difficulty attached to it. **One domain, and the condition
of entry that follows from what the domain is.** If an author can delete the
demand without touching the jurisdiction, they have written a domain and a
warning, and failed the rule — the identical test `IDENTITY.md` §1 applies to
`core` and `cost`.

### Why this axis and not another

It is the only framing found that satisfies all three constraints at once:

* **48 distinct entries.** The axis carries no scale, so distinctness comes
  entirely from *which jurisdiction* is named. 48 different jurisdictions, not
  48 positions on one line. Any scale — auspicious↔difficult, strong↔weak,
  fast↔slow — would force near-neighbours to collide and would reimport the
  hierarchy the next constraint forbids.

* **None reads as a worse thing to have.** Every entry is structurally
  symmetric: one jurisdiction, one demand, exactly one of each. There is no
  entry with *more* demand than another, because every entry has exactly one.
  This is the mechanism that flattens the benefic/malefic hierarchy, and it
  **cuts both ways** — which is the part authors forget:

  > Saturn may not read as doomed. **And Jupiter may not read as free.**
  >
  > A corpus where Jupiter's demand is absent, or three words long, has
  > reproduced the malefic hierarchy in tone while passing every banned-word
  > check. The gate for this is in §7d and it is symmetric by construction.

* **It enforces §4 grammatically.** A jurisdiction is a property of the thing.
  "Saturn is read for X" has no slot for a reader in it; "Saturn gives you X"
  does. Choosing the axis this way means the reader-vs-system boundary is not a
  rule authors must remember — it is the sentence shape they are already
  writing.

This inherits, unchanged, the binding rule already applied to Saturn, Rahu,
Ketu and Mars in `dasha_content_v2` and re-applied in `IDENTITY.md` §1:
traditionally difficult placements read as **demanding and useful, never
doomed**.

---

## 3. The fear problem — the central risk

This corpus is significations, so it is the exact place where *"Saturn brings
suffering"*, *"Ketu is malefic"*, *"the 8th house is death"* and *"the 6th
house is enemies and disease"* live in the source material. Those sentences are
not a fringe reading — they are how the tradition is most commonly written down
and most commonly sold. Every other Aura corpus could avoid fear-selling by
simply not raising the subject. This one cannot: it has to say something about
Saturn.

### How a traditionally-difficult signification reads

The rule is one move, applied everywhere:

> **State the demand as a condition of the domain, never as a threat to a
> person.**

A condition describes what the territory is like. A threat describes what will
be done to the reader. They can use the same nouns and land completely
differently.

| Not this | This |
|---|---|
| Saturn brings delay, obstacles and suffering. | Saturn is read for what only time can produce — the things that cannot be finished early because finishing early would not be the same thing. Its demand: it does not accept substitutes for elapsed time. |
| Ketu causes loss and separation. | Ketu is read for the places where interest has already gone out — what a person is done with before they notice. Its demand: nothing there can be held by wanting to hold it. |
| Rahu is the shadow planet of illusion and sudden downfall. | Rahu is read for appetite without precedent — the pull toward what a life has no experience of. Its demand: it offers no sense of proportion, because there is nothing to measure against yet. |
| The 6th house is enemies, debt and disease. | The 6th house is read for the daily grind of maintenance — work, routine, obligation, the body's upkeep. Its demand: it is never finished, only kept up with. |
| Mars is the malefic of anger, accidents and conflict. | Mars is read for the moment a thing must be cut, pushed or defended. Its demand: it is a poor instrument for anything that needs to be negotiated instead. |

The pattern in every right-hand cell: the difficulty is **structural to the
domain**, applies to everyone equally, arrives with something the domain is
good for, and asks for a change in method rather than a change in expectation.
No reader is told what is coming for them, because no reader is addressed at
all (§4).

### The floor and the ceiling

* **Floor** — a demand is not a warning. The reader must finish an entry able
  to *use* it. Nothing here is a verdict, a limit, or a caution about a future.
* **Ceiling** — a jurisdiction is not a promise. The traditionally-easy entries
  are not exempt from having a demand (§2), and they may not be written as
  reassurance. Venus does not "bring love".

### The fear-gate battery — reused, plus what is new

`BANNED_WORDS` carries over **wholesale** from
`tests/test_dasha_content_seed.py` (`death`, `die`, `disease`, `illness`,
`cancer`, `divorce`, `widow`, `curse`, `doom`, `destroyed`, `ruin`, `disaster`,
`tragedy`, `inauspicious`, `malefic`, `fate`, `fated`, `destiny`, `destined`,
…). It is the same battery `IDENTITY.md` §7 inherited, and it is not
re-litigated here.

Three additions specific to significations:

1. **The hierarchy lexicon** — `benefic` joins `malefic`; plus `auspicious`,
   `dusthana`, `evil`, `afflicted`, `affliction`, `exalted`, `debilitated`,
   `harsh`, `cruel`, `unfortunate`, `misfortune`. `malefic` was already banned;
   **`benefic` was not**, and its absence is exactly the asymmetry §2 warns
   about — banning only the bad half of a two-sided hierarchy leaves the
   hierarchy standing.
2. **Prediction shapes** — §7e.
3. **The symmetry check** — §7d, below, and the reason this section exists.

### The symmetry check — dread built from permitted words

The banned-word list is a floor and everybody clears it. The real failure is
tonal and uses nothing forbidden:

> *"Saturn is read for what only time can produce. It withholds. It does not
> hurry, it does not negotiate, and it does not give back the years it takes to
> teach what it teaches. What is built under it is built slowly, and what is
> not built is simply not built."*

Zero banned words. Four sentences where Jupiter got one. A heavy-token density
three times the corpus mean. It reads as dread, and no vocabulary gate on earth
catches it. So the gate is **comparative and group-level**:

* **Length symmetry** (§7d.1) — within a category, no `demand` may exceed
  **1.5× the category median** word count, nor fall below **0.6×**.
* **Heavy-token density parity** (§7d.2) — the traditionally-hard group's mean
  density of heavy tokens may not exceed **1.25×** the rest of its category.
  The hard groups are fixed in advance, from data that already exists:
  planets `{Saturn, Mars, Rahu, Ketu}`; houses `{6, 8, 12}`; nakshatras the
  nine already seeded as `ugra` or `tikshna` in `nakshatra_traits` (Bharani,
  Magha, Purva Phalguni, Purva Ashadha, Purva Bhadrapada, Ardra, Ashlesha,
  Jyeshtha, Mula). Reusing the seeded trait table rather than inventing a list
  means the grouping is not the author's opinion.
* **The inverse floor** (§7d.3) — **every** entry's `demand`, including
  Jupiter's and the 5th house's, must contain at least one heavy token and
  clear the length floor. This is the direction that gets forgotten, and it is
  what stops the easy entries from becoming reassurance.

Groups, not entries, because a single entry's density is noise at n=9.

### What a gate can enforce, and what it cannot

Stated plainly, because `IDENTITY.md` §6c is right that a weak gate that passes
is more dangerous than an admitted manual step:

| | Mechanical (CI) | Human (review) |
|---|---|---|
| Banned vocabulary, both halves of the hierarchy | ✅ | |
| Prediction / remedy / second-person shapes | ✅ | |
| Length symmetry, density parity, inverse floor | ✅ | |
| Structure: one jurisdiction, one demand, both present | ✅ | |
| **Whether a demand reads as a condition or a threat** | ❌ | ✅ |
| **Whether a jurisdiction is traditionally correct** | ❌ | ✅ (§8 — only an astrologer) |

The two ❌ rows are the two that matter most. That is the honest shape of this
corpus and the reason §8 is binding rather than advisory.

---

## 4. The reader-vs-system line

**This corpus explains the SYSTEM. It never addresses the READER.**

The knowledge base states what Saturn is read for. It does not state what
Saturn does to the person reading. The runtime AI explainer (`aura-api`
`src/explain/`) may connect a signification to the reader's actual chart when
they ask — that is a live, per-user, per-chart act with the reader's real data
in hand. The **corpus** is its source material and stays general.

This is the boundary that keeps an interpretive corpus factual *in framing*:
every sentence is a reportable claim about a tradition, which an astrologer can
mark right or wrong (§8), rather than a claim about a person, which nobody can.

### The rules

**1. Second person is banned outright.**
Zero occurrences of `you`, `your`, `yours`, `yourself`, anywhere in the corpus.

This is the exact inversion of `IDENTITY.md` §6c, which *requires* `you` in
every `core` and `cost`. The inversion is the point, and it is why the two
corpora can sit on adjacent screens without blurring: identity is written *to*
the reader, knowledge is written *about* the system. One regex enforces the
whole boundary.

**2. No reader-class third person either.**
`those born under`, `natives`, `people with`, `anyone with … in their`,
`if [X] is in your` are second person wearing a coat. They make a claim about a
class of readers, which is a prediction about people (§1, exclusion 2). Banned
as phrases.

**3. Subject discipline.**
The grammatical subject of every sentence in `governs` and `demand` is the
thing itself — Saturn, the 8th house, Ashlesha — or the domain it names. Never
a person, and never an implied one.

**4. Attribution is structural, not prose.**
Every claim here is *what the tradition says*, and the temptation is to write
"traditionally" into every sentence. Thirty entries in, that is a tic, and the
share cap would catch its shape without catching its cause. So attribution
lives in a **field** (`source`, §5) and the words `traditionally`,
`tradition`, `traditional`, `classically` are **banned from `governs` and
`demand` prose entirely**. The frame is rendered once, from the field. This
also keeps the hedge-density problem from `IDENTITY.md` §6c from reappearing:
attribution is not hedging, but sprinkled attribution is indistinguishable from
it.

**5. What the explainer may do, and what it may not.**
The explainer may say "Saturn is in your 10th house, and the 10th is read for
public standing" — corpus content plus the reader's data, joined at runtime.
It may not be given corpus text that already contains the join, because then
the personalisation is fake and the astrologer signed off on something that is
no longer what ships.

---

## 5. Structure

All three categories share **one spine**. This is a design decision, not
convenience: the symmetry gates in §7d compare word counts and densities across
entries, and they are only meaningful if the entries are the same shape.

| Field | Length | What it is for |
|---|---|---|
| `title` | 3–6 words | Plain-language name for the jurisdiction. Never the bare name of the thing. Read as a parallel set (12 houses appear in one list). |
| `governs` | 1–2 sentences, 25–40 words | **The jurisdiction.** What part of life this is read for. Concrete domains and situations, not adjectives. |
| `demand` | 1 sentence, 15–30 words | **The demand.** The one thing this jurisdiction will not let anyone do. Same root as `governs` (§2). Carries the §3 discipline. |
| `source` | 1 clause, ≤15 words | The traditional basis in plain English — the symbol, the classical association, the weekday, the presiding figure. Carries all attribution (§4.4). The **only** field where `lord`, `ruled by`, `sign` may appear. |
| `distinct_from` | 1 object | `{"entry": "<same-category id>", "because": "<one clause>"}`. Authoring scaffolding + audit trail. Not rendered at v1. |

**Target: ~65 words of shipped prose, ±15** (`title` + `governs` + `demand` +
`source`).

Defence of the number. `IDENTITY.md` argues 100 words for a nakshatra profile
because it is read **once or twice, ever**, alone, on the screen where spending
30 seconds is most justified. This corpus has the opposite read pattern: a
reader browsing the houses reads **twelve entries in one sitting**, and the
explainer may cite three in one answer. At 100 words that is 1,200 words in a
knowledge screen, which nobody finishes. At ~65 words twelve entries is ~4
minutes of reading available in glanceable units, and each single entry is
~20 seconds. Below ~50 there is not room for a jurisdiction and a real demand
without one becoming a clause.

**Order is fixed: `governs` → `demand`.** Domain before condition — the same
RECOGNITION-then-CAUSE discipline `content_v3`, `dasha_content_v2` and
`IDENTITY.md` are all built on. A demand read before its jurisdiction is a
warning with no context, which is precisely the fear shape §3 exists to
prevent.

**Why `distinct_from` carries one target, not identity's two.** `contrast` in
`IDENTITY.md` needs two targets and a connected graph because 27 human
dispositions can collide anywhere in the space. Significations collide
**predictably and locally**: Mars/Sun both read for drive, the 2nd/11th both
for money, the 4th/12th both for withdrawal, Ashwini/Bharani adjacent by
construction. One nearest-neighbour, named deliberately, is the honest unit —
plus a **coverage** requirement (§7c.4) so no entry escapes being contrasted
with.

---

## 6. Cross-corpus collision — three surfaces, all 1:1

This is the largest structural risk in the corpus and the thing that most
distinguishes it from every predecessor. `IDENTITY.md` §5 had one collision
surface (nakshatra vs moon sign, 36 co-occurring pairs). **This corpus has
three, and every one of them is a perfect 1:1 mapping** — the same 27
nakshatras identity already covers, the same 9 planets dasha already covers,
the same 12 houses Block 7 already defines.

48 pairs total. Small, cheap to gate, and strict per-pair — the same reasoning
that let `IDENTITY.md` afford zero tolerance over 36 pairs.

### 6a. vs `identity_content_v2.nakshatra` — 27 pairs

Both corpora have an entry for Ashwini. They appear on adjacent screens: the
Block 7 follow-up (`3de3a53`) wired **About your star → "What is a nakshatra?"**
precisely so a reader looking at interpretive copy about themselves can reach
the definitional counterweight. That link now leads here too.

> **Identity owns the PERSON. Knowledge owns the SYMBOL.**

| | `identity_content_v2` | this corpus |
|---|---|---|
| Subject | the reader born under the star | the star as an object in the system |
| Voice | second person, required | second person, banned |
| Answers | what this person does by default, and what it costs them | what this star is read for, and what that domain will not permit |
| Example subject matter | "you are already underway while the others are still reading the brief" | the horse's head, the physicians, onset and first motion |

A knowledge entry may **not** be identity's `core` claim rewritten in the third
person. That is the specific failure mode — it is the easiest entry to write
and it makes the app say the same thing twice with a grammar change, which
advertises padding exactly as `IDENTITY.md` §5 warns.

### 6b. vs `dasha_content_v2` mahadasha — 9 pairs

Both corpora have an entry for Saturn. Same division, different terms:

> **Dasha owns the PERIOD. Knowledge owns the PLANET.**

Dasha's Saturn essence is what living through those years may feel like —
transient, experienced, second person. Knowledge's Saturn is what the planet is
read for at all — standing, general, third person. `dasha_content_v2` already
carries `test_essence_never_opens_with_the_lord`, so the two corpora are
already grammatically opposed at the opening: dasha may *not* open with the
planet as subject, knowledge *must*.

### 6c. vs the Block 7 definitional house card — 12 pairs

`astrology_knowledge_hub_screen.dart` already ships "What each house is
traditionally linked to" — twelve one-line area lists. A knowledge-corpus house
entry that restates that list has added nothing and made the app repeat itself
in the one place a reader is most likely to tap both.

**This gate cannot statically import the Flutter source.** Three crossval
suites in `aura-api` already broke CI for ten consecutive runs by importing
`../../aura-engine/db/seed/…`, a sibling path that exists on this machine and
not in a runner (recorded in `CLAUDE.md`). Repeating that mistake across the
Aura repo boundary would be worse. So: the twelve definitional lines are
**copied into the seed** as `_about.definitional_baseline`, the gate runs
against that copy, and keeping it in sync is a named review-checklist item
(§8) rather than a pretend-mechanical one.

### The gate shape, identical on all three surfaces

Per pair, over the substantive prose only (`governs` + `demand` here, against
`core` + `cost` / `essence` / the definitional line there):

1. **No shared content word**, outside stopwords and the §7a frame exemptions.
   Zero tolerance, as in `IDENTITY.md` §6d.
2. **No shared sentence skeleton** (`_skeleton()`).
3. **Vocabulary lanes** — knowledge entries may not contain second person at
   all (§4.1, which subsumes most of identity's lane), nor the dasha lane's
   period vocabulary (`period`, `years`, `era`, `stretch`, `now`, `these
   years`) outside `source`.

Rule 1 is the gate most likely to need an allowlist under real authoring
pressure — "money", "work", "home" are genuinely the right word in both
corpora. That is stated here rather than discovered later: if an exemption
becomes necessary it is **added to this document with its justification**, not
silently added to the test file.

---

## 7. Gates — what CI must enforce in the authoring task

New: `tests/test_knowledge_content_seed.py`, over
`db/seed/knowledge_content_v1.json`. Runs in CI **and** gates the nightly
pre-seed, like the four existing content gates.

### 7a. Word-share cap — re-derived per category

Following the method `IDENTITY.md` §6a established and defended: **count
entries, not lines** (a word twice in one entry is style; a word across many
entries is a template), and **separate denominators per category** (a shared
denominator lets the largest corpus's headroom mask repetition in the
smallest — the `content_v3_1` lesson: *the right denominator is the unit that
matters, not the biggest one available*).

| Category | n entries | `MAX_ENTRY_SHARE` | `round(n × share)` | Fails at | Meaning |
|---|---|---|---|---|---|
| nakshatra | 27 | **0.185** | 5 | 6 entries | >1 in 5 stars share the word |
| house | 12 | **0.25** | 3 | 4 entries | a third of the houses share it |
| planet | 9 | **0.30** | 3 | 4 entries | ~4 in 9 planets share it |

The nakshatra and house numbers land on identity's 0.185 and 0.25 because the
denominators are identical (27 and 12) and the counting unit is the same. That
is a re-derivation arriving at the same answer, not a copy — the derivation is
what makes them defensible.

**The planet number is looser and the reason should be stated rather than
dressed up.** At n=9 the difference between the thresholds 0.25 and 0.30 is a
single entry, and lexical share is close to meaningless at that size. 0.30 is
set where a word appearing in nearly half the planets is still caught, and no
tighter, because the real distinctness work for the nine planets is done by the
skeleton gate (§7c.2) and `distinct_from` (§7c.4), not by counting words.

**Frame-word exemption — narrow.** Exempt: `house`, `houses`, `planet`,
`planets`, `star`, `stars`, `nakshatra`, `nakshatras`, `sign`, `signs`,
`chart`. These name the unit each category is *about*, so their frequency
measures what the library is.

**Explicitly NOT exempt**, and these are the words this corpus will drift
toward: `life`, `time`, `work`, `people`, `things`, `matters`, `area`,
`areas`, `domain`, `governs`, `read`, `place`, `placed`. `governs` deserves a
special note — it is the field name, and it will become the verb of all 48
entries unless the cap is allowed to catch it.

`traditionally` and its family are not exempt either, because they are **banned
from prose outright** (§4.4) — the exemption question does not arise.

### 7b. Structure

* All 48 entries present: 27 named nakshatras, 9 named planets, 12 numbered
  houses. No extras, no gaps.
* Every entry has all five fields, non-empty.
* Field lengths inside the §5 bands.
* `source` present and ≤15 words.
* `distinct_from.entry` is a valid id in the **same** category and is not the
  entry itself.

### 7c. Distinctness within a category

The reading unit is **the category**, not a screen: a reader browses all twelve
houses, and the explainer may cite several planets in one answer. So the gate
runs per category, per field. For any two entries in a category, in each of
`title`, `governs`, `demand`:

1. **Opening frame** — first four words differ. Reuse `_frame()`.
2. **Sentence skeleton** — content words blanked, function words kept, differ.
   Reuse `_skeleton()`. This is the gate that caught `dasha_content_v1`'s
   "one template, name swapped in", and this corpus is unusually exposed to it:
   48 entries all answering the same question in the same shape.
3. **Exact string** — no duplicates.
4. **The claim** — no two entries in a category may name the same jurisdiction.
   Implemented via `distinct_from`: valid, same-category, not self, and
   **corpus-wide coverage** — every entry in a category must be named as at
   least one other entry's `distinct_from` target. A jurisdiction nobody
   contrasts with is one nobody can be distinguished from.

**Title carve-out, as in dasha and identity.** Titles are gated on exact
distinctness and distinct opening frame but **not** on skeleton — they are
short parallel labels read as one family, and a skeleton gate there fails
correct design while catching nothing.

### 7d. Fear symmetry — the §3 battery

1. **Length symmetry.** Within each category, `len(demand.words)` between
   **0.6× and 1.5×** the category median.
2. **Heavy-token density parity.** `HEAVY` is an explicit lexicon of
   permitted-but-weighted words (`slow`, `delay`, `wait`, `withhold`, `refuse`,
   `deny`, `cost`, `loss`, `lose`, `end`, `ends`, `break`, `strip`, `hard`,
   `alone`, `pain`, `undo`, `take`, `taken`, `cannot`, `never`, `nothing`).
   Mean density (heavy tokens ÷ total words over `governs` + `demand`) of the
   fixed hard group ≤ **1.25×** the mean of the rest of its category. Hard
   groups per §3, with the nakshatra group read from the seeded
   `nakshatra_traits` `ugra`/`tikshna` sets rather than authored by hand.
3. **Inverse floor.** Every `demand` in every category contains ≥1 `HEAVY`
   token and clears the 0.6× length floor. No entry gets a costless demand.

Any change to `HEAVY` is a change to this document, not to the test file — the
lexicon is the gate, and a lexicon quietly trimmed to make a draft pass is the
same failure as an allowlist quietly added.

### 7e. No-prediction / no-remedy / no-second-person scan

All mechanical, all absolute, all whole-word or whole-phrase, case-insensitive:

* **Second person** — `\b(you|your|yours|yourself)\b` → **zero**, anywhere.
* **Reader-class third person** — `those born under`, `natives`, `people with`,
  `anyone with`, `individuals born`.
* **Prediction** — `will bring`, `will give`, `will cause`, `results in`,
  `leads to`, `is likely to`, `can expect`, `promises`, `guarantees`,
  `predict*`, `forecast*`, plus bare `will` outside `source`.
* **Remedy** — `wear`, `gemstone`, `gem`, `stone`, `ruby`, `sapphire`,
  `emerald`, `coral`, `pearl`, `topaz`, `diamond`, `cat's eye`, `hessonite`,
  `chant`, `mantra`, `japa`, `donate`, `donation`, `charity`, `fast`,
  `fasting`, `puja`, `pooja`, `yantra`, `rudraksha`, `temple`, `ritual`,
  `propitiate`, `remedy`, `remedial`, `dosha`, `parihara`.
* **Hierarchy** — the §3 lexicon, `benefic` included.
* **Attribution words** — `traditionally`, `tradition`, `traditional`,
  `classically` banned from `governs` and `demand` (§4.4).
* **Jargon** — `IDENTITY.md` §7's list (`gana`, `guna`, `yoni`, `nadi`,
  `lord`, `ruler`, `exalted`, `debilitated`) stays banned in prose, with the
  single documented carve-out that `lord` / `ruled by` are permitted **inside
  `source`**, whose entire job is naming the traditional basis. That carve-out
  exists so authors are not forced into "the planet the tradition assigns to
  Saturday" in a field designed to say "Saturn's day".
* **Excluded systems** (§1.1) — `sub-lord`, `sublord`, `navamsa`, `D9`, `KP`,
  `shadbala`, `combust`, `drishti`.

### 7f. What is NOT automated, and why

Per `IDENTITY.md` §6c's division of labour, restated because this corpus adds a
second irreducibly-human column:

**Review, in the authoring-task checklist, not CI:**
* Does each `demand` read as a **condition of the domain** or as a **threat**?
  (§3 — the density gates catch shape, never meaning.)
* Does `distinct_from.because` name a real difference or a synonym?
* Is `_about.definitional_baseline` still in sync with the shipped Block 7 card?
* **Are the significations traditionally correct?** — §8, and only an
  astrologer.

---

## 8. The astrologer-review checkpoint — BINDING

Every heuristic and every corpus in this repo currently ships with some form of
*"astrologer-review-pending"* recorded honestly in `docs/LAUNCH_PLAN.md` — the
v1 score rules, `content_v4`'s tables, `dasha_content_v2`'s voice. That
deferral has been defensible because those corpora describe a *day* or a
*period*, and their claim is "here is a reading", which a careful writer can
own.

**This corpus's claim is "here is what the tradition says." A writer cannot own
that.** So the deferral stops here, and it stops as a gate rather than an
intention.

### The question only an astrologer can answer

> Is this signification traditionally correct?

Nothing in §7 touches it. CI can prove that the 6th-house entry is distinct,
unhedged, symmetric, fear-free, second-person-free and inside its word band —
and be entirely silent on whether the 6th house is actually read for service,
routine and maintenance. **A well-written wrong signification is worse than a
badly-written right one, because it is more believable**, and every gate in
this document makes the writing better without touching the truth.

Secondary, and also theirs: whether the §3 reframings are *legitimate*
translations of the tradition or Aura softening the source into something it
does not say. That charge — "you've sanded the tradition down to make it
sellable" — is the one criticism of this corpus that would be fair, and only a
practitioner can rule on it.

### Checkpoint A — the axis and a 9-entry sample. BLOCKS AUTHORING.

Before entry 10 exists. The astrologer receives:

* §2 (the axis) and §3 (the fear approach) — the two design decisions.
* **9 entries: 3 nakshatras, 3 planets, 3 houses**, chosen to be the *hardest*
  cases, not the easiest. Mandatory: **Ketu**, **the 8th house**, and one of
  **Ashlesha / Mula**. A sample of Jupiter, the 5th house and Rohini proves
  nothing about the only part that is hard.

This mirrors `identity_content_v1`, the 3+4 pilot that proved the pipeline
before 39 entries were committed — applied here to the *accuracy* question
instead of the *gate* question.

> **Authoring does not proceed past the sample until the axis is approved.**
> If the axis is rejected, 9 entries are rewritten. If it is discovered at 48,
> 48 are — plus a second round of the astrologer's time, which is the scarce
> resource in this pipeline and the one thing here that cannot be re-run
> cheaply.

### Checkpoint B — the full 48. BLOCKS SHIP.

Before any of it reaches a reader, through any surface — knowledge screen,
explainer context, or otherwise.

### The review artefact

A 48-row sheet: `id`, `title`, `governs`, `demand`, `source`, then three
columns the astrologer fills:

| `accurate?` | `what is wrong` | `demanding, not doomed?` |
|---|---|---|
| Y / N / partly | free text | Y / N |

Deliberately not a document to read and comment on. Forty-eight yes/no
judgements are reviewable in an hour; forty-eight paragraphs of prose are a
weekend nobody has, which is how every previous review deferral began.

### Making it un-skippable

Sign-off is recorded **in the seed**, and CI enforces its presence:

```json
"_about": {
  "spec": "docs/voice/KNOWLEDGE.md",
  "status": "COMPLETE",
  "astrologer_review": {
    "checkpoint_a": {"reviewer": "<name>", "date": "YYYY-MM-DD",
                     "verdict": "approved|approved-with-changes|rejected",
                     "sample": ["Ketu", "house_8", "Mula", "…"]},
    "checkpoint_b": {"reviewer": "<name>", "date": "YYYY-MM-DD",
                     "verdict": "approved|approved-with-changes",
                     "entries_marked_inaccurate": 0}
  }
}
```

Two gates in `test_knowledge_content_seed.py`:

* `test_sample_review_recorded_before_full_corpus` — if the seed carries more
  than 9 entries, `checkpoint_a` must be present and `approved*`.
* `test_full_review_recorded_before_complete` — if `status` is `COMPLETE`,
  `checkpoint_b` must be present, `approved*`, and
  `entries_marked_inaccurate == 0`.

This is the strongest available form of binding: the corpus is structurally
unable to be marked shippable without a named human and a date in the file.
It cannot verify that the review *happened well* — nothing can — but it makes
skipping it a deliberate false entry rather than an omission, which is exactly
the difference between the pushed-hash gate and "committed locally".

### The prerequisite nobody has done yet

**No astrologer is currently engaged.** Identifying and briefing one is a
separate task, it is not part of authoring, and per Checkpoint A it **blocks**
after the 9-entry sample. Recording this here rather than discovering it at
entry 10: the pipeline has a dependency on a person who does not yet exist in
it, and the earliest useful time to start looking is before authoring begins,
not when the sample is ready.

---

## 9. Inherited binding rules

Carried unchanged from `docs/voice/*.md`, `dasha_content_v2` and
`IDENTITY.md` §7, except where §4 inverts them:

* **Third person, warm, plain.** *(Inverts identity's second person — §4.1.)*
* **Simple English** an Indian 25–40-year-old non-expert relates to. No Sanskrit
  beyond the names of the things themselves; no astrological jargon (§7e).
* **Concrete, not mystical.** Observable domains and situations. Nothing about
  cosmic energy, vibrations, karma, or past lives.
* **No fatalism.** Nothing is written, fixed, or sealed.
* **No fear-selling.** Never a difficulty the reader must pay to resolve — and
  in this corpus, never a difficulty the reader must pay attention to resolve
  either, since there is nothing to sell and nothing to fix.
* **No death, illness or divorce.** `BANNED_WORDS` carries over wholesale.
* **No medical, financial or legal advice**, and no promised outcomes.
* **No tender.**
* **The reader always keeps agency** — trivially satisfied here, since the
  reader is never addressed, but it constrains the explainer that consumes this
  corpus and is restated for that reason.

---

## 10. Requirements for the authoring task — noted, not built

* **Table** `knowledge_content` + migration, following `identity_content`:
  versioned rows, additive, old versions retained for rollback by re-seed.
* **Seed** `db/seed/knowledge_content_v1.json` —
  `{version, _about, nakshatra{27}, planet{9}, house{12}}`, with
  `_about.definitional_baseline` per §6c.
* **Test** `tests/test_knowledge_content_seed.py` — §7 and §8.
* **Delivery.** Endpoint `/v1/knowledge/content` mirroring
  `/v1/identity/content` (which already reports `complete:true` against
  `identity_content_v2`), plus a `content_version_ok` line in `/v1/health`.
  Whether the app bundles or fetches is that task's decision; 48 short entries
  is small enough that bundling is viable.
* **Explainer wiring.** `src/explain/` consuming this corpus as context is a
  separate task with its own §4.5 boundary to enforce, and is **not** approved
  by this spec.
* **Not in scope here or in the authoring task:** any screen or UI, rendering
  `distinct_from`, the mantra/affirmation corpora (CUT in Block 5B and staying
  cut), compatibility, and anything remedial.

---

## 11. Amendments made by the authoring task (2026-07-26)

`knowledge_content_v1` is authored: 48 of 48 entries, `tests/test_knowledge_content_seed.py`
running every §7 and §8 gate with none skipped, and `tests/test_knowledge_gates_falsify.py`
proving each one fires. Four things changed against this document, and per §6's
standing rule they are recorded **here, with their justification**, rather than
added quietly to a test file.

### 11a. A sixth field: `source_ref`

§5's spine gains one field. `source` is unchanged and stays what §5 defines —
the traditional basis in plain English, ≤15 words, the field that renders.
`source_ref` is the **citation**: `<Text> <locator> — <gloss>`, clauses joined
by `; `, over a closed list of six texts (BPHS, Phaladeepika, Uttara Kalamrita,
Brihat Samhita, Brihat Jataka, Taittiriya Brahmana).

Why a field and not a longer `source`. The authoring task made grounding the
accuracy standard: *"correct" means "traceable to the tradition"*, the same way
the engine cites AstroSage and DrikPanchang for its numbers. That makes the
citation **auditable data**, not prose — Rohan spot-checks a 48-row table of
`entry → claim → locus`, and the app renders none of it. Collapsing the two into
one field would have made the rendered line unreadable and the audit trail
unqueryable at the same time. `test_source_field_is_plain_english_not_a_citation`
keeps them apart in both directions.

**What the citation gate proves, and what it does not.** It proves every entry
names a text and a place inside it, and that no category rests on a single
chapter. It does **not** prove the cited text says what the entry says. That
distance is §8's, and §11d below is explicit that the gate narrows it rather
than closing it.

### 11b. Two words added to the §7a frame exemption: `bhava`, `graha`

§7a's exemption list named `house`, `houses`, `planet`, `planets` and so on,
because those name the unit each category is about. Their Sanskrit counterparts
were omitted, and twelve house entries each naming their bhava in `source` put
the word in 12 of 12 entries against a cap of 3.

The exemption is the identical argument, and its scope is narrow: both words
appear only inside `source` and `source_ref`, never in `governs` or `demand`.
No other word was exempted, and no threshold was moved. `graha` is exempted on
the same basis for the nine planets.

### 11c. §7d's density gate needed a zero-baseline branch

`test_heavy_token_density_parity` compares the hard group's mean heavy-token
density against the rest of its category. Falsifying it in the **inverse**
direction — leave the hard entries untouched, rewrite the easy ones into
weightless reassurance — makes the denominator zero, and the gate raised
`ZeroDivisionError` from inside its own failure message. It still stopped CI,
but with a stack trace naming arithmetic instead of the defect. A zero baseline
is now its own assertion with its own sentence, because §7d.3's failure is the
one authors forget and it deserves to be legible when it fires.

### 11d. §8 is NOT satisfied, and the corpus is marked unshippable

This is the amendment that matters, and it is a deviation, not a clarification.

* **Checkpoint A was met by a non-astrologer** — Rohan, as product owner —
  reviewing the axis and the fear approach. That is a real approval of the
  **voice and the editorial rules**. It is not the approval §8 asks for.
* **Checkpoint A's sample missed two of its three mandatory slots.** §8 requires
  Ketu, the 8th house, and one of Ashlesha/Mula, chosen to be the hardest cases.
  The sample reviewed was Saturn, Hasta and the 8th house. Hasta is in no hard
  group, so the sample under-tested exactly what §8 says a sample is for.
* **Checkpoint B has not happened.** No astrologer is engaged. §8's prerequisite
  section predicted this and it is what happened.
* **The source-citation gate was substituted for the astrologer** as the accuracy
  mechanism. It is enforced and it is not equivalent.

None of that is left as a note. The seed carries `_about.shippable: false`, the
gate `test_corpus_is_not_marked_shippable_without_checkpoint_b` allows that flag
to be `true` **only** when `checkpoint_b` is approved by a reviewer explicitly
recorded as an astrologer with zero entries marked inaccurate, and
`/v1/knowledge/content` echoes the flag so a screen can refuse to render. The
falsification suite proves the flag cannot be flipped by hand, and proves that
an honest, complete sign-off by a stated non-astrologer still fails.

> **The knowledge-base screens are the next task and MUST honour
> `shippable: false`.** §8 Checkpoint B blocks ship "through any surface". The
> corpus existing and being gated is not the same as it being allowed in front
> of a reader, and this is the sentence that has to be argued with before it is.
