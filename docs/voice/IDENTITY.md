# Identity — voice spec

The corpus behind **"About your star"**: 27 nakshatra profiles + 12 moon-sign
trait entries. This is the AstroSage-parity lever — the copy that has to make
the app feel like it *knows* the reader.

**Status: AUTHORED AND COMPLETE** as `identity_content_v2` (2026-07-20) — all
27 + 12 entries, every gate in §6 running with none skipped. `identity_content_v1`
was the 3 + 4 pilot that proved the pipeline and the gates; its rows remain in the
table, and all 7 of its entries are carried into v2 byte-identical. This document
was written before any entry existed, because `dasha_content_v1` was authored
before its spec and had to be thrown away; the same mistake at 27 + 12 entries
would have been a bigger write-off.

**Two things this spec got right, confirmed by what actually happened at full
size**, recorded here because both were contested while writing it:

* **§6a's insistence on re-deriving the share cap rather than reusing 0.06.** The
  gate necessarily slept through the pilot and woke at 27/12. Its first real run
  caught `whoever` in **13 of 27** entries — a tic the author had introduced
  precisely by dodging the cap on `people`, and which was invisible while writing
  any single entry. The backstop earned its place on its first firing.
* **§6c's refusal to automate the Barnum check.** Nothing mechanical here would
  have caught that tic's *meaning*; the share cap caught its *shape*. The division
  of labour the section argues for — CI enforces carriers and structure, a human
  enforces the claim — is still the honest one, and the human review of the
  Swap Test across all 27 remains outstanding.

**Still outstanding (a human, per §6c):** the Swap Test on every line, the
wince-or-forward test on every `cost`, and whether each `contrast` pair names a
real difference or a synonym. CI cannot answer any of the three.

## Why the existing voice docs don't cover this

`career.md`, `mood.md` and the rest are area-scoped around a **good ↔ careful**
axis, because daily guidance values a *day*. `dasha_content_v2` runs
**demanding ↔ generous**, because a dasha values a *period*. Both axes are
valuations of a transient thing the reader is passing through.

Identity has no such axis. A person is not "good today". A nakshatra is not a
better or worse nakshatra to be born under, and any copy that lets one read as
better than another is a defect, not a nuance — it tells 1 in 27 readers the app
thinks they drew a bad hand.

---

## 1. The axis: one root, two outputs

**The organising tension of identity copy is internal to the entry, not spread
across the corpus.**

Every entry names **one governing disposition** — the thing this person reaches
for by default, before deciding to. Then it shows that same disposition paying
off, and shows it costing. Not two traits, a good one and a bad one. **One
trait, read twice.**

> Krittika's precision is why the work is right and why nobody wants to hand you
> a draft.

The strength and the cost share a grammatical root. If an author can remove the
cost without touching the strength, they have written two traits and failed the
rule.

**Why this axis and not another.** It is the only framing that satisfies both
constraints at once:

* **27 distinct entries** — the axis carries no scale, so distinctness comes
  entirely from *which disposition* is named. 27 different engines, not 27
  positions on one line. A scale would force near-neighbours to collide.
* **None reads as worse** — every entry is structurally symmetric: one root, one
  payoff, one price. There is no entry with more cost than another, because
  every entry has exactly one cost, and it is the flip side of its own strength.
  Nobody is *given* a defect; everybody is shown the bill for what they are good
  at.

This also inherits the binding rule already applied to Saturn, Rahu, Ketu and
Mars in `dasha_content_v2`: traditionally difficult placements read as
**demanding and useful**, never doomed.

---

## 2. The Barnum problem — the central risk

Identity copy fails by being true of everyone. *"You are sometimes outgoing and
sometimes reserved."* *"Deep down you want to be understood."* Every reader
nods, nobody learns anything, and the app has just proved it does not know them.
This is the exact opposite of the provable-accuracy promise, and it is the
single most likely way this corpus fails.

### The Swap Test (per line, mechanical for the author)

> Replace the nakshatra name with a different nakshatra. Does the line still
> read as plausible?
>
> **If yes, it is not identity copy. Delete it.**

Applied honestly this kills most first-draft sentences, which is the point.

### Making it checkable, not aspirational

A test an author can talk themselves out of is not a test. So the Swap Test is
converted into a **structural obligation that ships in the data**:

Every entry carries a **`contrast`** field: **two named nakshatras whose readers
would NOT recognise themselves in this entry's core claim**, each with a
one-clause reason.

```json
"contrast": [
  {"nakshatra": "Revati",  "because": "finishes gently; you finish exactly"},
  {"nakshatra": "Ardra",   "because": "wants the mess; you want it resolved"}
]
```

This does three things a prose rule cannot:

1. **It forces the author to locate the claim.** You cannot name who a sentence
   excludes until you know what it actually asserts. Vague copy has no
   contrast partner — the field cannot be filled, and the entry is rewritten.
2. **It is auditable by a human reviewer in seconds.** Read the core claim, read
   the two contrasts, ask "is that actually a difference?" No re-reading of 27
   entries to detect sameness.
3. **It is partly enforceable in CI** (see §6).

`contrast` is **authoring scaffolding, seeded but not rendered** at v1. It costs
nothing to carry and it is the audit trail for every claim in the corpus. A
later screen may surface it as "unlike…" copy; that is not a v1 decision.

### Banned Barnum carriers

These constructions are how universal statements disguise themselves. Gate them
as vocabulary (§6):

`sometimes … sometimes` · `part of you` · `deep down` · `more than people
realise` · `a side of you that few see` · `you may find that` · `at times` ·
`there are moments when` · `you have a tendency to` · `like everyone` ·
`whether you admit it or not` · `secretly`

---

## 3. No flattery, no horoscope-positive

**Every entry must contain something genuinely uncomfortable to read.** Not
difficult-sounding — uncomfortable. A cost the reader would rather not have had
named.

### The humblebrag ban (explicit)

The failure shape is *"your only flaw is that you care too much"* — a cost
phrased so it flatters. It is banned outright. Concrete instances:

* caring too much / feeling too deeply / loving too hard
* being *too* honest, *too* loyal, *too* generous, *too* driven
* "you hold yourself to a higher standard than others"
* "people don't always deserve your effort"
* anything where the cost lands on **other people's** shortcomings rather than
  on the reader

### The test for a real cost

> Would the reader wince, or forward it to a friend?
>
> A cost you'd forward is a compliment. Rewrite it.

A real cost is one the reader has been criticised for, or has quietly noticed in
themselves and not enjoyed noticing. It names something they *do*, with a
consequence that lands on them or on people who put up with them.

Not: *"you set high standards."*
But: *"people stop bringing you unfinished things, which is lonelier than it
sounds."*

### The floor

Uncomfortable is not the same as doomed. The reader must finish the entry able
to *use* it. Every cost is a bill for a real capability, and the reader always
keeps agency — nothing here is a verdict, a limit, or a warning about their
future.

---

## 4. Structure

The read pattern is the design constraint: this is seen **once or twice, ever**,
not daily. So it can be longer than a guidance line. But the product's
30-second promise still holds, and a wall of text in a profile screen is a wall
of text nobody finishes.

### Nakshatra entry — 5 fields, ~100 words shipped

| Field | Length | What it is for |
|---|---|---|
| `title` | 4–7 words | Plain-language name for the disposition. Never the bare nakshatra name. Parallel set — 27 of these are scannable together in a picker or a share card. |
| `core` | 2 sentences, 35–55 words | **The engine.** What this person reaches for by default. Second person, present tense, concrete behaviour — not an adjective list. This is the sentence that has to make them sit up. |
| `cost` | 1–2 sentences, 25–40 words | **The price**, from the same root as `core` (§1). Contains the uncomfortable line (§3). |
| `misread` | 1 sentence, 15–25 words | **How others get them wrong.** Structurally anti-Barnum: a misreading is only possible if the trait is specific enough to be mistaken for something in particular. |
| `contrast` | 2 objects | Authoring scaffolding + audit trail (§2). Not rendered at v1. |

**Target: 100 words of shipped prose, ±20.**

Defence of the number: sustained silent reading runs ~200 wpm, so 100 words is
**~30 seconds** — the product's own promise, spent once, on the screen where
spending it is most justified. Below ~80 words there is not room for a root, a
payoff and a real cost without one of them becoming a clause. Above ~130 the
entry stops being glanceable and starts needing a scroll, and the third
paragraph is where authors reliably drift into Barnum filler.

**Order is fixed: `core` → `cost` → `misread`.** Recognition first — the same
RECOGNITION-then-CAUSE discipline that `content_v3` and `dasha_content_v2` are
built on. The reader must feel seen before they are billed, or the cost reads as
an accusation from a stranger.

### Moon-sign entry — 3 fields, ~60 words shipped

| Field | Length | What it is for |
|---|---|---|
| `title` | 3–6 words | Parallel set of 12. |
| `need` | 2 sentences, 30–45 words | What this reader needs in order to feel steady. |
| `unsettles` | 1 sentence, 15–25 words | What reliably knocks that out from under them. |

Deliberately shorter. The moon sign is the **supporting** half of the screen
(§5); at equal length the two corpora compete, and the reader reads the second
one less carefully than the first regardless of which is which.

---

## 5. Cross-corpus collision — nakshatra vs moon sign

A reader has **both**, and sees both on the same screen. Krittika and Taurus
must not be two paragraphs saying the same thing in different words — that is
worse than saying it once, because it advertises that the app is padding.

### The division of labour

> **Nakshatra copy owns what you DO. Moon-sign copy owns what you NEED.**

| | Nakshatra | Moon sign |
|---|---|---|
| Subject | disposition in action | emotional baseline at rest |
| Answers | how you engage, push, decide, finish | what makes you feel safe or unsettled |
| Verbs | act, reach, push, finish, cut, hold out, take on | need, want, settle, rest, brace, feel steady |
| Consequence lands on | the work, and the people around you | you |
| Length | ~100 words | ~60 words |

### The keeping-them-apart rule

**Nakshatra copy may not name an emotional need. Moon-sign copy may not name a
behaviour under pressure.**

If a nakshatra line can be rewritten as *"you need…"* without loss, it belongs
to the moon sign. If a moon-sign line describes what the reader *does* about a
feeling rather than what the feeling *is*, it belongs to the nakshatra.

### The pairs that actually collide

This is smaller than it looks and the gate should exploit it. A nakshatra spans
13°20'; a sign spans 30°. **18 nakshatras sit entirely inside one sign; 9
straddle a boundary** — Krittika, Mrigashira, Punarvasu, Uttara Phalguni,
Chitra, Vishakha, Uttara Ashadha, Dhanishta, Purva Bhadrapada.

So there are **36 co-occurring (nakshatra, sign) pairs**, not 324. Only those 36
can ever appear on one screen. The collision gate runs over 36 real pairs — cheap,
and far stricter per-pair than a blanket corpus check could afford to be.

---

## 6. Gates — what CI must enforce in C2

New: `tests/test_identity_content_seed.py`, over
`db/seed/identity_content_v1.json`. Runs in CI **and** gates the nightly
pre-seed, like the three existing gates.

### 6a. Word-share cap — re-derived, do not reuse 0.06

`MAX_WORD_SHARE = 0.06` was set against ~234 lines in the dasha corpus, where 6%
= 14 lines and a word must recur **15 times** to fail. That is real headroom.
Reused naively here it becomes nonsense: the identity corpora are far smaller,
and `int(n × 0.06)` floors hard.

| Corpus | Unit | n | at 0.06 | Verdict |
|---|---|---|---|---|
| dasha | lines | ~234 | 14 | works |
| nakshatra | lines (27×4) | 108 | 6 | too tight — noise |
| moon sign | lines (12×3) | 36 | 2 | absurd |

**Two changes.**

**Count entries, not lines.** A word counted once per *entry* is the right unit:
these are profiles, and a word appearing twice inside one profile is style, while
a word appearing in many profiles is a template. Line-counting also punishes the
nakshatra corpus for having 4 fields to the moon sign's 3, which is irrelevant to
repetitiveness.

**Separate denominators.** The two corpora are different sizes (27 vs 12, a
2.25× gap), on different subject matter, with disjoint vocabulary by §5. A shared
denominator would let the larger corpus's headroom mask repetition in the
smaller one — which is exactly the failure `content_v3_1` documents: *the right
denominator is the unit that matters, not the biggest one available.*

| Corpus | n entries | `MAX_ENTRY_SHARE` | Fails at | Meaning |
|---|---|---|---|---|
| nakshatra | 27 | **0.185** | 6 entries | >1 in 5 profiles share the word |
| moon sign | 12 | **0.25** | 4 entries | a third of the corpus shares the word |

Both thresholds are set where recurrence stops being coincidence and starts
being a visible pattern to a reader browsing several entries. They are *looser*
per-word than 0.06 was, and that is correct — the real distinctness work here is
done by 6b and 6c, not by lexical share. Share-capping is the backstop that
caught `stretch` in 26 of 237 dasha lines; it is not the primary gate.

**Frame-word exemption (narrow, as established).** Exempt: `star`, `stars`,
`born`, `nakshatra`, `sign`, `moon`. These name the unit every entry is *about*,
so their frequency measures what the library is, not how repetitive the writing
is. **Nothing else is exempt** — and specifically not `work`, `people`,
`others`, `notice`, `hold`, which are the words this corpus will drift toward.

### 6b. Distinctness — what must differ between any two entries

The reading unit is **the whole corpus**, not a screen: readers browse other
nakshatras (their partner's, their friend's) and share them. So the gate runs
corpus-wide, per field.

For any two entries, in each of `title`, `core`, `cost`, `misread`
(and `title`, `need`, `unsettles`) all four must hold:

1. **Opening frame** — first four words differ. Reuse `_frame()` from
   `test_dasha_content_seed.py`.
2. **Sentence skeleton** — content words blanked, function words kept, differ.
   Reuse `_skeleton()`. This is the "same sentence, name swapped in" gate that
   caught `dasha_content_v1`.
3. **Exact string** — trivially, no duplicates.
4. **The claim** — no two entries may name the same governing disposition.
   Implemented via `contrast`: **every entry's two `contrast` targets must be
   valid nakshatra names, must not be itself, and the corpus-wide contrast graph
   must be connected** — every nakshatra named as a contrast by at least one
   other entry. A disposition nobody contrasts with is one nobody can be
   distinguished from.

**Title carve-out, as in dasha.** The 27 titles are gated on exact distinctness
and distinct opening frame, but **not on skeleton** — they are short parallel
labels read as one family, and a skeleton gate there fails correct design while
catching nothing.

### 6c. The Barnum gate — an honest answer

**Barnum cannot be detected mechanically.** No test can tell whether *"you feel
things deeply"* is true of everyone; that requires knowing what the sentence
means. Anyone who claims otherwise is proposing a proxy that will pass bad copy
and give false confidence — which is worse than no gate, because it converts
"we reviewed this" into "CI is green".

So: **CI enforces the carriers and the structure; a human enforces the claim.**

**Mechanical (CI):**
* Banned Barnum-carrier phrases from §2 — regex, whole-phrase, case-insensitive.
* Banned humblebrag shapes from §3 — `too (honest|loyal|generous|driven|kind|much)`,
  `car(e|ing) too much`, `only flaw`, `higher standard than`.
* Hedge density: `may`, `might`, `can be`, `tend to`, `often`, `usually` —
  **at most one per entry**. Barnum copy is hedged copy; specific copy asserts.
* Structural: `contrast` present, well-formed, 2 targets, graph connected (6b.4).
* Second person: every `core` and `cost` contains `you` or `your`.

**Review (a human, gated in the C2 checklist, not CI):**
* The Swap Test on every line.
* Is the `cost` one the reader would wince at, or forward?
* Do the two `contrast` reasons name an actual difference, or a synonym?

This is stated plainly rather than automated badly, per the same reasoning that
kept the score-detail "why" from falling through to a template: **a weak gate
that passes is more dangerous than an admitted manual step.**

### 6d. Cross-corpus collision gate (rule 5)

Over the **36 co-occurring pairs** only:

1. **No shared content word** between a nakshatra entry and a co-occurring
   moon-sign entry, outside stopwords and the §6a frame exemptions. Strict —
   36 pairs is a small enough surface to afford zero tolerance, and a shared
   content word across the two halves of one screen is exactly the "same thing
   twice" the rule exists to prevent.
2. **No shared sentence skeleton** across the pair.
3. **Vocabulary lanes** (§5): nakshatra entries may not contain
   `need`, `needs`, `safe`, `settled`, `unsettled`, `comfort`, `reassur*`.
   Moon-sign entries may not contain `push`, `finish`, `deliver`, `decide`,
   `take on`, `hold out`. This is the mechanical form of "does vs needs".

---

## 7. Inherited binding rules

Carried unchanged from `docs/voice/*.md` and `dasha_content_v2`'s `_about`:

* **Second person**, warm, direct.
* **Simple English** an Indian 25–40-year-old non-expert relates to. No Sanskrit
  beyond the nakshatra/sign names themselves, and no astrological jargon —
  no `gana`, `guna`, `yoni`, `nadi`, `lord`, `ruler`, `exalted`, `debilitated`.
* **Concrete, not mystical.** Observable behaviour and consequence. Nothing
  about cosmic energy, vibrations, karma, or past lives.
* **No fatalism.** Nothing is written, fixed, or sealed. `fate`, `fated`,
  `destiny`, `destined` remain in `BANNED_WORDS`.
* **No fear-selling.** Never a warning the reader must pay to resolve.
* **No death, illness or divorce** predictions. `BANNED_WORDS` carries over
  wholesale from `test_dasha_content_seed.py`.
* **No medical, financial or legal advice**, and no promised outcomes.
* **No tender** (the standing ban across every voice doc).
* **The reader always keeps agency.** An identity entry describes a starting
  disposition, never a limit. Nobody is told who they will remain.

---

## 8. Requirements for C2 — noted, not built

* **Table** `identity_content` + migration `db/migrations/00X_identity_content.sql`.
  Follows `dasha_content`: versioned rows, additive, old versions retained in the
  table for rollback by re-seed rather than by revert.
* **Seed** `db/seed/identity_content_v1.json` — `{version, _about, nakshatra{27}, moon_sign{12}}`.
* **Test** `tests/test_identity_content_seed.py` — §6.
* **Delivery.** The reader's `natalNakshatraIndex` is already on `UserProfile`
  from `/v1/natal`. Their **moon sign is not** — it is derivable from the same
  in-Worker computation, so `/v1/natal` must also return a moon-sign index, and
  `UserProfile` must carry it. Whether the copy ships bundled with the app or is
  fetched is a C2 decision; 39 short entries is small enough that bundling is
  viable and removes a network dependency from a profile screen.
* **Not in scope here or in C2:** rendering `contrast`, share cards, any
  compatibility/matching feature.
