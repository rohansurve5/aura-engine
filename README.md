# aura-engine

**Verifiable Vedic astrology calculations** for [Aura](../Aura). A small,
isolated Python service built on the [Swiss Ephemeris](https://www.astro.com/swisseph/)
whose every output is checked against a known-good reference chart before
anything is built on top of it.

Accuracy is Aura's differentiator, so this engine is **open source (AGPL-3.0)**:
the calculations that decide what a user is told should be auditable by anyone.

> Status: **Prompts A + B** — sidereal positions + Vimshottari dasha
> (golden-tested vs AstroSage) and Panchang + Choghadiya (golden-tested vs
> DrikPanchang, 10 dates, Pune). **Prompt B2** — Neon schema, nightly precompute
> job (daily_sky + 27 daily_guidance rows/day) and the v1 heuristic scoring.
> **Prompt C** — the natal-lookup service (`engine/jobs/natal_service.py`), now
> **reference-only**: the app's natal call moved into the `aura-api` Worker,
> cross-validated against this engine (`scripts/crossval_natal.py`).

## Why it's open

Astrology apps are black boxes: you cannot tell whether the dasha you are shown
is computed correctly or invented. Aura's engine ships its math, its ephemeris
data, and its golden tests in the open so the numbers can be independently
reproduced. AGPL keeps that true for anyone who runs a modified copy as a
service.

## The AGPL boundary (architecture rule)

**The AGPL boundary is this repo.** The nightly precompute job (`db/`,
`engine/jobs/`) *lives here* — it is just a seeding script that reads the engine
and writes rows to Neon, with secrets supplied via environment variables. The
future **private** API reads Neon **only** and **never links Swiss Ephemeris**.
So the copyleft surface stays permanently contained to the open engine, and the
product API can be closed without ever touching AGPL-covered code.

## What it does today

- **`engine/positions.py`** — geocentric **sidereal** longitudes (Lahiri VP285
  by default; see "Ayanamsa discovery") for Sun → Ketu at a UTC instant. Ketu = Rahu + 180°; mean lunar node
  by default, true-node optional. Longitudes are geocentric, hence
  location-independent.
- **`engine/vimshottari.py`** — from the natal Moon: birth nakshatra + pada +
  lord, the **balance** of the first maha-dasha, and the full **maha → antar →
  pratyantar** tables with start/end dates. Two year-length conventions
  (`solar` = 365.25 days, default; `savana` = 360 days). Pratyantar is
  structured but marked **experimental**.
- **`engine/chart.py`** — the natal chart: sidereal **ascendant (lagna)** with
  nakshatra/pada, **Whole Sign houses** (shipped) + Placidus cusps (for future
  KP; `None` above the polar circles), and all 9 grahas placed in signs AND
  houses with retrogradation. Birth time and place are load-bearing here — the
  asc moves ~1°/4 min. Golden-tested against DrikPanchang + AstroSage across
  8 latitudes and 83 years, incl. war-time DST; the full record — two
  reference-site discoveries (TT-frame houses, AstroSage's arithmetic lagna
  table), tolerances, birth-time sensitivity numbers, unknown-birth-time
  policy — is in **`docs/ASCENDANT.md`**.
- **`engine/panchang.py`** — full panchang for a date + location: sunrise/sunset
  (Swiss rise/set), tithi, nakshatra, yoga, karana — every boundary root-found
  on the driving angle (never sampled), so kshaya/adhika cases fall out
  naturally — plus vaar, paksha and moon phase.
- **`engine/chart_file.py`** (reshape B) — the **chart file's facts**, the
  source of truth behind aura-api `POST /v1/chart-file`: every graha's
  nakshatra/pada, **D9 navamsa** (sign + house + vargottama), **dignity**
  (BPHS exaltation / moolatrikona / own / debilitated), **combustion**
  (classical orbs), the **birth panchang** (`panchang.panchang_at` +
  `panchang.vara_at`, sunrise-to-sunrise vara), every **dasha date on
  AstroSage's dasha calendar** (`vimshottari.calendar_dasha`) with
  pratyantar for the running and next antar, today's **transit snapshot**,
  the next 365 days of exact **Saturn/Jupiter/Rahu ingresses**, the **Saturn
  cycles** and **Mangal dosha**.
  Golden-tested against AstroSage (planets at sunrise, panchang boundaries)
  and DrikPanchang (ingress instants, the golden birth's panchang); the Worker
  port is gated by `scripts/crossval_chart_file.py` (see "Chart file" below).
- **`engine/choghadiya.py`** — day/night choghadiya (8 splits each) and rahu
  kaal / gulika kaal / yamaganda, pure arithmetic on sunrise/sunset.
- **`engine/compatibility.py`** — Ashtakoota (Guna Milan): the classical
  eight-koota tally out of 36, plus Nadi/Bhakoot parihar and Mangal (Kuja)
  Dosha facts, from two people's Moon placements. A deterministic classical
  **table lookup** over the already-cross-validated Moon nakshatra/rashi — not
  an independent computation — so it is proven by table-encoding pins + a frozen
  breakdown golden, and its band-neutral voice is guarded by a fatalism/fear
  gate battery. Full record (computability, reference divergences, the ethics
  position on Nadi/Mangal): **`docs/COMPATIBILITY.md`**.
- **`engine/ephemeris.py`** — the single place that configures Swiss Ephemeris
  (data path, ayanamsa registry, IST↔UTC).
- **`engine/daily.py` + `engine/scoring.py`** — the precompute payload builders:
  a deterministic `daily_sky` blob per date, and the **v1 heuristic** daily
  guidance (energy %, six life-area scores, lucky colour/number/direction,
  good-for/avoid, opportunity/warning) for each of the 27 natal nakshatras.
- **`engine/jobs/precompute.py`** — the nightly seeding job that writes those
  payloads to Neon.

## Data pipeline (Neon)

The app never runs the ephemeris. A nightly job precomputes everything into
Neon (Postgres) and the app/API just read cached rows.

**Schema** (`db/migrations/`, applied by `db/migrate.py` — plain SQL, no ORM):

| table | key | holds |
| --- | --- | --- |
| `daily_sky` | `date` | one JSONB payload per day: panchang, sunrise/sunset, day+night choghadiya, the three kaals, moon phase, planet-of-day |
| `daily_guidance` | `(date, nakshatra_index 0-26)` | 27 JSONB payloads per day — the v1 guidance for each natal nakshatra |
| `score_rules` | `(version, rule_key)` | the tunable v1 rule set (`params` JSONB); **every scoring number lives here**, not in code |
| `app_events` | `id` | analytics sink the app posts to later |

**v1 scoring** is a documented *heuristic, subject to astrologer review*. Its
basis is **Tarabala** — the 9-fold auspiciousness cycle counted from the natal
(janma) nakshatra to the day's Moon nakshatra — which sets the base energy; the
weekday (hora) lord and paksha modulate it per life-area, and lucky
colour/number/direction come from the day lord. All of those numbers are seeded
from `db/seed/score_rules_v1.json` into `score_rules`, so they can be retuned in
the table with **no code change** — the job reads its rules from the DB and
holds no scoring constants of its own.

**MVP limitation:** `daily_sky` is computed for **one canonical location**
(Pune, IST — `engine.daily.CANONICAL_LOCATION`). Per-user city-level solar times
are deferred; the app reads this single canonical set for now.

```bash
# apply migrations + seed the v1 rules (secrets via env, never committed):
NEON_DATABASE_URL="postgres://…"  uv run python db/migrate.py

# precompute today .. today+13 (14-day lookahead), idempotent upserts:
NEON_DATABASE_URL="postgres://…"  uv run python -m engine.jobs.precompute
```

The job is deterministic (same date + same rules version → byte-identical
payloads) and runs nightly at **01:00 IST** via
`.github/workflows/precompute.yml`.

## Natal lookup: computed in the Worker, cross-validated here

The app's natal-nakshatra call (once, at onboarding completion) is served by
the `aura-api` Cloudflare Worker's `/v1/natal`, implemented with
[astronomy-engine](https://github.com/cosinekitty/astronomy) (MIT) and the same
Lahiri VP285 ayanamsa convention as this engine. **This repo remains the source
of truth**: `scripts/crossval_natal.py` resolves 1,000 seeded-random births
(1930–2025) with both this engine (Swiss Ephemeris) and the Worker's actual
TypeScript (run via node — no reimplementation), requires **100% agreement** on
`nakshatra_index` and `moon_sign`, logs the max Moon-longitude delta (measured:
3.6″ ≈ 0.06 arc-min), and writes the golden set that gates every aura-api
deploy. If the two ever disagree, this side is correct — fix the Worker, never
tune the golden.

```bash
PYTHONPATH=. uv run python scripts/crossval_natal.py
```

`engine/jobs/natal_service.py` (FastAPI) is kept as the **reference-only**
golden implementation — runnable locally for spot checks, **not deployed**.
The natal nakshatra, Moon sign and Sun sign are **geocentric** — no birth
lat/lon needed, only date + time (noon IST assumed when unknown,
surfaced as `time_assumed`).

```bash
uv sync --extra api
uv run uvicorn engine.jobs.natal_service:app --port 8000
curl "http://localhost:8000/v1/natal?dob=1989-09-23&time=04:47"
# {"nakshatra_index":5,"nakshatra":"Ardra","pada":4,"lord":"Rahu",
#  "moon_sign":"Gemini","sun_sign":"Virgo","time_assumed":false}
```

## Chart file: facts here, text in the Worker (reshape B)

The product is one plain-text file a user shares into ChatGPT / Claude. The
Worker (`aura-api/src/chartFacts.ts`) computes its values with astronomy-engine
and renders the text; **this repo decides the values** (`engine/chart_file.py`).
`scripts/crossval_chart_file.py` runs both over 300 births (India-weighted,
world panel, seeded stations, the golden chart at Thane, the B1 births abroad)
and 51 India-time skies (incl. the real 8–27-day sign stays an over-stepping
ingress search would miss), compares every value the file states — now also
Mangal dosha, Saturn's 42-year sign-change list and the Saturn cycles for all
12 Moon signs on every sky — and writes the golden that gates every aura-api
deploy. Measured (2026-10-20): **108,903 values, 0 disagreements, 4 contested
boundary cases** (a value within 1′ of the edge that decides it — recorded,
never adjudicated); worst longitude 20″, sunrise 26 s, dasha dates ±1 day on
the dasha calendar, ingress and Saturn-change instants 10.6″ of motion. The endpoint itself takes
births in India only (reshape B review); the world and abroad births exercise
the same shared functions.

```bash
uv run python scripts/crossval_chart_file.py
```

Conventions the file states to its reader (and the tests pin): lahiri_vp285,
mean node, Whole Sign houses, **AstroSage's dasha calendar** (360-day years of
30-day months — Known deviations 4; the balance is birth date → the birth
maha's printed end, so the two never disagree); the **birth panchang uses
the chart's vp285 zodiac** (not DrikPanchang's plain Lahiri, as the daily
panchang does) so its nakshatra can never contradict the Moon's row; "today"
is **India's date** and transits are read at **12:00 IST**; every dasha level
**tiles its parent exactly** (lengths are whole units of 1/120³ year).
**Saturn cycles** (Sade Sati 12/1/2,
Kantaka 4, Ashtama 8 from the Moon sign) run from Saturn's first entry to its
final exit, retrograde pauses inside one cycle, each stretch dated by the IST
day of the sign change. **Mangal dosha**: AstroSage's rule — houses
1/4/7/8/12 from the lagna and from the Moon — plus one line on what counting
the 2nd house too would change; cancellations only where they are exact sign facts (own
sign, exalted, with Jupiter, Jupiter's 5/7/9 aspect). The assistant reading
the file may interpret aspects, yogas and house lords from these values,
labelled as its own interpretation; it may never change one.

## Install & run

Uses [uv](https://docs.astral.sh/uv/):

```bash
uv sync

# Vimshottari maha + antar table, AstroSage layout:
uv run python -m engine dasha --dob 23/09/1989 --time 04:47 --lat 19.99 --lon 73.79

# A birth outside India — the zone is resolved at the birth instant (DST applies):
uv run python -m engine dasha --dob 04/07/1990 --time 10:00 --zone America/New_York

# Sidereal graha longitudes:
uv run python -m engine positions --dob 23/09/1989 --time 04:47

# Full delta report vs the golden chart (auditable):
uv run python scripts/compare.py

# DrikPanchang-style day card (panchang + kaals + choghadiya):
uv run python -m engine panchang --date 2026-07-18 --lat 18.5204 --lon 73.8567
```

`--dob` is `dd/mm/yyyy`, `--time` is 24-hour `HH:MM`, both the birth place's
wall clock. `--zone` says which clock: an IANA id (`America/New_York`,
`Asia/Kolkata` — historical DST and offset changes applied at the birth instant)
or a fixed `+HH:MM`. It defaults to `+05:30` (IST), which is wrong for anyone born
outside India — a New York birth read as IST samples the Moon 9½ hours early and
can move the dasha balance by years. `--lat`/`--lon` are optional —
Vimshottari depends only on the geocentric Moon and is unaffected by them.

## Ephemeris data range

The vendored Swiss files `ephe/sepl_18.se1` (planets) and `ephe/semo_18.se1`
(Moon) cover **1800–2399**, so Aura's supported birth range **1900–2100** is
fully inside the high-precision data (no Moshier fallback). Files are from the
[aloistr/swisseph](https://github.com/aloistr/swisseph) mirror.

## Ayanamsa discovery (important)

The brief assumed AstroSage uses "Lahiri". It does — but a specific *flavour*.
Sweeping the Swiss Lahiri variants against the golden chart:

| ayanamsa           | balance        | maha avg Δ | verdict                  |
| ------------------ | -------------- | ---------- | ------------------------ |
| `lahiri` (plain)   | 3Y 10M **20D** | ~3.6 days  | **off** across the board |
| **`lahiri_vp285`** | 3Y 10M **24D** | **≤1 day** | **matches AstroSage**    |
| `lahiri_icrc`      | 3Y 10M 20D     | ~3.8 days  | off                      |
| `true_citra`       | 3Y 10M 10D     | ~14 days   | off                      |

So **AstroSage uses Lahiri VP285**, and the dasha-year is **365.25 days**.

**And the twist (Prompt B): DrikPanchang uses *plain* Lahiri.** Against the
10-date panchang golden set, plain `lahiri` matches yoga ends to ±0.8 min and
nakshatra to ±1.0 min, while `lahiri_vp285` drifts a further ~+0.7 min on both.
The two reference sites use *different* Lahiri flavours, so the engine carries
one compat constant per source:

| constant | value | used by |
| --- | --- | --- |
| `ASTROSAGE_AYANAMSA` | `lahiri_vp285` | dasha / natal chart (AstroSage parity) |
| `DRIKPANCHANG_AYANAMSA` | `lahiri` | panchang (DrikPanchang parity) |
| `DEFAULT_AYANAMSA` | `lahiri_vp285` | library default for natal work |

`compute_panchang()` and the `panchang` CLI default to `DRIKPANCHANG_AYANAMSA`;
everything stays overridable via `ayanamsa=` / `--ayanamsa`.

## Match status vs the golden chart

Against the AstroSage `Vimshottari Dasha.docx` export
(`tests/golden/astrosage_dasha.json`), using `lahiri_vp285` + 365.25-day years:

| level     | exact floats                       | + `astrosage_rounding`            |
| --------- | ---------------------------------- | --------------------------------- |
| balance   | **exact** — `RAHU 3Y 10M 24D`      | —                                 |
| nakshatra | **exact** — Ardra pada 4 (Rahu)    | —                                 |
| maha      | all 10 boundaries within ±1 day    | **9/10 exact**, worst 1 day       |
| antar     | 77/85 within ±1 day; 8 at 2 days   | 81/85 within ±1 day; 4 at 2 days  |

## Known deviations

**Maximum deviation vs AstroSage (`compute_dasha`, /v1/dasha): ±2 days, at the
antar level only** — the chart file's calendar has none there (4 below). Balance,
nakshatra and maha boundaries match (see table above). Analysis trail:

1. *Ayanamsa* — resolved: `lahiri_vp285` (above). Wrong flavour costs ~3–4 days
   everywhere; this is not the residual.
2. *Year length* — 365.25 real days is the best REAL-DAY year (tropical,
   sidereal and a 360-real-day year are all measurably worse). But see 4:
   AstroSage does not count in real days at all.
3. *Cascading day-rounding* (Prompt A.1) — **partially confirmed**. AstroSage
   rounds maha boundaries to whole days (round-half makes 9/10 maha ends exact),
   and deriving antar dates from the rounded parent then rounding again cuts the
   two-day offenders from 8 to 4. It does **not** close them, so the rounding is
   an opt-in presentation mode (`format_astrosage(..., astrosage_rounding=True)`,
   CLI `--astrosage-rounding`), while exact float datetimes stay the canonical
   internal representation.
4. *Residual* — **cause found (reshape B review, 2026-10-20)**; the earlier
   guess ("a sub-arcsecond ayanamsa residue") was wrong. AstroSage places
   dasha time on a **360-day calendar of twelve 30-day months**: every
   boundary is a label `360·y + 30·(m−1) + (d−1) + h/24` = epoch + dasha years
   × 360, read back as a date with every month treated as 30 days long (so no
   AstroSage dasha date is ever the 31st, and a "29/30 February" rolls into
   March as if February had 28 days). A sub-period of 5.6 dasha months is
   therefore 5 calendar months + 18 days whatever the months' real lengths —
   which is exactly where 365.25 real days drifts ±1–2 days inside a year.
   Proof, from AstroSage's own printouts for the golden chart
   (`tests/golden/astrosage_dasha_tables.json`): ONE epoch, fitted to a
   window under a minute wide, reproduces **all 942 Lahiri dates** (76 antar
   ends, 434 pratyantar ends, 432 sookshma ends to the hour) and, separately,
   **all 434 KP dates** — 0 misses. The epoch implies AstroSage's own printed
   Moon (Lahiri 17-06-43, KP 077-12-06) when the birth is placed on the
   timeline at the start of the day after its date label, the clock time
   dropped. Pinned by `test_astrosage_dasha_is_a_360_day_calendar`.
   **Adopted for the chart file (reshape B decisions, 2026-10-20)** as
   `vimshottari.calendar_dasha`: with this engine's own Moon, antar ends
   76/76 exact (365.25 real days: 42/76), pratyantar 298/434 (194/434),
   sookshma 293/432, none more than 2 calendar days off; the rest is our Moon
   sitting 2.4″ from AstroSage's (7.9 hours of dasha time). Fed the Moon
   AstroSage's dates imply (17-06-42.9, printed rounded as 43″), the
   production code reproduces all 942. The birth anchor is fitted on ONE
   birth (04:47 IST); an AstroSage table for an evening birth is still owed to
   confirm it. `compute_dasha` (365.25 real days) stays the default and still
   drives /v1/dasha for the live app, unchanged.

### Panchang vs DrikPanchang (Prompt B)

Golden set: 10 days (1989–2026) for Pune, 2 full choghadiya tables, fetched
from drikpanchang.com (`tests/golden/drik_panchang.json`). Results:

| category | result |
| --- | --- |
| sunrise / sunset | max **0.63 / 0.50 min** (tolerance ±1 min) |
| tithi / nakshatra / yoga / karana names | **all exact** (55 entries) |
| element end times | max **1.7 min** (tolerance ±2 min) |
| choghadiya | **32/32 slots** exact names, times ≤ ±1 min |
| rahu / gulika / yamaganda | **30/30 windows** ≤ 0.63 min |

Conventions proven by the golden set:

* **Sunrise = upper limb + refraction** (standard astronomical). The
  "Hindu-udaya" flavour (disc centre, no refraction) is ~4 min off
  DrikPanchang; centre-with-refraction ~1.5 min off.
* **Panchang ayanamsa = plain Lahiri** (see the table above).
* Residual systematic ~**+1 min late** on tithi/karana end times
  (ayanamsa-independent — visible in the elongation-driven categories, so it
  is a small Moon-theory/ΔT/display-truncation difference on their side).
  Inside tolerance; **accepted, not tuned away**. *A3 postscript*: the
  ascendant cross-validation identified the likely cause — the reference
  sites evaluate time-driven quantities in the **TT frame** (~ΔT ≈ 57–69 s
  ahead of UT); see `docs/ASCENDANT.md` > Discovery 1.

### Chart file vs AstroSage / DrikPanchang (reshape B4, B review)

* **The golden chart at Thane (AstroSage Kundli + 56-page report, Lahiri,
  19:11 N 72:58 E — `tests/golden/chart_file_golden_1.json`):** every sign,
  nakshatra, pada, D9 sign, D1 and D9 house, R/C mark, BPHS dignity AstroSage
  states, the birth panchang (Krishna Navami, Variyana, Taitila, Friday
  before the 06:27 sunrise — ours 06:26:55), the dasha balance, all 9 maha
  and all 76 antar dates and the Manglik verdicts agree exactly. Degrees: lagna 6.0″, Moon 2.3″, Rahu/Ketu 10.4″, the MC 3.5″.
* **Planets (AstroSage, sunrise, New Delhi, 2026-10-19):** sign, nakshatra and
  pada agree for all nine. The Moon (−6″) and mean Rahu (−3.5″) pin the
  convention; the other planets sit within 2′ (Jupiter +106″, Saturn +74″).
* **AstroSage's planet degrees** (the golden chart's 1–2′ gaps: 1989 Sun +63″,
  Mars +112″, Mercury +33″, Jupiter −49″, Venus +57″, Saturn +7″, AstroSage
  minus engine) are AstroSage's planetary ephemeris, not a setting. Tested
  against both datasets: a different ayanamsa moves every body by the same
  amount (these differ per planet and change sign between 1989 and 2026 —
  Mars +112″ → −10″, Saturn +7″ → −74″); geometric instead of apparent
  positions, no aberration, no light deflection, no nutation, the Moshier
  ephemeris, plain Lahiri, true Citra and the ecliptic-of-t0 projection all
  leave the planet RMS between 49″ and 131″ (ours: 62″ in 1989, 57″ in
  2026); and of the ayanamsas only vp285 keeps the Moon, the node and the
  lagna within 10″ (plain Lahiri: 13–25″). Their Uranus is 265″ off. AstroSage prints the
  plain-Lahiri MEAN ayanamsa (023-42-47 at birth, 024-13-47 at the 2026 solar
  return — within 2″ of Swiss plain Lahiri) and the mean obliquity. No single
  setting change makes this engine match AstroSage's planets; DrikPanchang
  (Swiss Ephemeris) agrees with this engine to ~1″ (ingress instants above).
* **Sade Sati / Dhaiya (AstroSage's 45-row Sadesati report, 1990–2108):**
  every row through 2099 (43) is one of our Saturn stays — same sign, order
  and phase; 28 entry and 27 exit dates identical, every other one exactly a
  day off (AstroSage's Saturn sits up to ~1′ from Swiss; near a station that
  is hours). `tests/golden/astrosage_sadesati_golden_1.json`.
* **Mangal dosha:** same houses (Mars 2nd from the lagna, 4th from the Moon)
  and, under AstroSage's 1/4/7/8/12 rule the file now uses, the same verdicts:
  dosha in the Moon chart, not in the lagna chart. The file's note says that
  counting the 2nd as well would add the lagna placement and leave the result
  "present".
* **Ingresses (DrikPanchang, Oct 2026 – Nov 2027):** same seven events, order,
  directions and IST dates. DrikPanchang's Lahiri is neither of ours: its
  Jupiter/Saturn instants fall between our plain-lahiri and vp285 instants (up
  to ~50 min from vp285); the slow mean node lands 10 min (~1.3″) past vp285.
  Asserted in arc: within 40″ of the boundary at DrikPanchang's minute. The
  file therefore prints ingress **dates**, not times.
* **Pratyantar dates** (AstroSage's docx): on the chart file's calendar, the
  two tables it prints for the golden chart are 13/18 exact, the other 5 one
  calendar day early — our Moon, 2.4″ further on (Known deviations 4).

### KP section vs AstroSage (reshape E.3, `engine/kp.py`)

Golden: AstroSage's KP page for Golden-1 (`tests/golden/astrosage_kp_golden_1.json`,
`tests/test_kp.py`). The KP zodiac is **KP New** (Balachandran: 22°22′12.54″ at
1900.0 + Newcomb's 5025.64″T + 1.11″T² — reproduces AstroSage's printed KP New on
three dates within 0.8″) **plus the constant 23.0″ VP285 − plain-Lahiri gap**:
AstroSage prints plain-Lahiri and KP New values, but its positions follow VP285
and its KP page is its Lahiri page moved by their printed gap (5′23″ on all 10
points). Houses: Placidus (Swiss), moved onto the KP zodiac like the planets.

* **Exact:** all 12 cusps' sign, star, sub **and sub-sub** lords; all 9 grahas'
  sign, star, sub and sub-sub lords; the ruling planets (day lord Venus — the
  birth is before sunrise, Friday's vara); the KP dasha balance (3 Y 9 M 10 D;
  the page's header "3 Y 10 M 24 D" is the Lahiri balance) and all 9 maha + 76
  antar dates. KP pratyantars (not printed in the file): 228/434 exact, all
  within a calendar day.
* **Degrees:** lagna 2.9″, MC 0.4″, intermediate cusps ≤ 15.4″ (AstroSage's
  Placidus); Moon 5.5″, Rahu/Ketu 7.3″, Saturn 3.7″; the other planets as on the
  Lahiri page (AstroSage's ephemeris, up to 109″ for Mars).
* **One deviation — Mercury's house.** Swiss puts Mercury 13″ before cusp 2
  (house 1); AstroSage's Mercury, 30″ further on, sits 19″ past it (house 2). So
  Mercury signifies 1, 2, 11, 12 here (AstroSage 2, 11, 12) and house 1 lists
  Mercury. With Mercury in AstroSage's house, the same code gives all 21 of its
  significator rows. Reported, not tuned.
* **Engine vs Worker** (`scripts/crossval_chart_file.py`, 300 births): cusps
  agree to 0.09″ (the Worker solves Placidus itself), planets to 18″; 3 planet
  sub/sub-sub lords within that arc of an edge are recorded as contested.

### Historical timezones and India's war-time DST (1941–45)

**Births before 1955 in Bombay, before 1948 in Calcutta.** Those cities kept
their own clocks after IST began (Bombay Time UTC+4:51 until 1955, Calcutta
Time UTC+5:53:20 until 1948). The tz database's `Asia/Kolkata`, which the
chart file requires, reads every Indian birth from 1906 on as IST (+05:30,
war time below aside), so a 1950 Mumbai birth recorded at 10:00 is placed at
04:30 UTC; read as Bombay Time it would be 05:09 UTC — 39 minutes, about 10°
of ascendant. Which one AstroSage applies is NOT yet known: its report for
such a birth was requested on 2026-10-20 and has not arrived; until then the
engine follows the tz database and nothing here claims AstroSage agrees.

Two timezone spec forms exist, and the distinction is deliberate
(`engine/timezones.py`, mirrored in `aura-api/src/natal.ts`):

* **`"+05:30"` — a fixed offset.** Means exactly that offset at *every* date,
  forever. DST is never applied.
* **`"Asia/Kolkata"` — an IANA zone id.** The offset is resolved **at the birth
  instant**, so India's war-time DST applies: **+06:30** during
  1941-10-01 → 1942-05-15 and 1942-09-01 → 1945-10-15, +05:30 otherwise.

**Why both.** A 1943 Calcutta birth genuinely happened at +06:30, so the IANA
path is the correct one and is what the app now sends. But the 1,001-case natal
cross-validation goldens were all generated as `"+05:30"`, and `/v1/natal`
responses are served `immutable, max-age=31536000` — so reinterpreting the
existing spelling would both invalidate the goldens and leave CDN POPs serving a
year-old answer alongside the new one. The fixed-offset form is therefore frozen
and IANA was added as a separate input class with its own golden set
(`scripts/crossval_natal_zone.py` → `aura-api/test/golden/natal_zone_crossval.json`).

**Measured blast radius.** Of the 1,001 golden births, **40 (4.0%)** fall inside
a war-time window. Applying the correct +06:30 moves the Moon by **−0.4934° to
−0.6274° (mean −0.5549°, ≈33 arc-min)** — far outside the 1 arc-min
cross-validation tolerance, which is why the two paths must be kept separate
rather than merged. User-visible effect on those 40:

| field | changes |
| --- | --- |
| nakshatra | 2 / 40 |
| pada | 9 / 40 |
| moon sign | 1 / 40 |
| any visible field | 9 / 40 |

The other 31 shift longitude only. Examples: `1945-09-18 06:05` and
`1944-07-07 17:56` both move Shravana → Uttara Ashadha; `1945-01-18 14:46` moves
Pisces → Aquarius.

**Reference behaviour — this is a convergence, not a divergence.**

* **DrikPanchang APPLIES war-time DST.** Verified empirically, not from docs:
  Delhi sunrise on 15 June **1944 is 06:23**, on 15 June **1946 it is 05:23**.
  Astronomy cannot move sunrise an hour between two mid-June dates; they are
  computing 1944 at +06:30. Their Kundali form also exposes an explicit
  "Olson Time Zone for DST Rules?" selector. Note the trap: their 1944 page
  *labels* itself "Timezone Offset: +05:30" while computing in +06:30.
* **AstroSage: UNDETERMINED — an open question, not a settled one.** Their birth
  form has **no DST field at all** (no occurrence of "dst"/"daylight" in the
  served HTML), and the timezone box is pre-filled from the *place* lookup,
  which never sees the birth date — so it cannot encode war-time DST at that
  stage. A hidden `timezoneid=Asia/Kolkata` field suggests server-side historical
  resolution is *available*, but that is inference, not observation. The chart
  generator requires a JS-driven POST with session validation, so it could not be
  driven by URL fetching. **To settle it:** open
  `astrosage.com/atlas/birthdetail.asp` in a browser, enter 15 June 1943 10:30
  Kolkata, and read the Vimshottari balance — a one-hour shift moves it by
  ~9 months on an 18-year maha, so the answer is unmistakable. Worth doing before
  relying on the 1941-45 window commercially; it does **not** block launch,
  because AstroSage is our dasha reference and no war-time case is in the dasha
  golden set.
* Wider practice is inconsistent: the correction is explicitly taught ("enter
  6:30 E"), but applied by hand, and astro.com was observed returning +05:30 for
  New Delhi yet +06:30 for Calcutta on the same 1947 date.

**Verdict: apply it.** The IANA path matches DrikPanchang, the reference our
panchang is already validated against, and matches what the clocks actually
read. Unlike the 00:00 IST transit boundary (`docs/REPORTS.md`), this is not a
deliberate deviation from a reference — it is a correction toward one.

**Two edge cases worth knowing**, both pinned by tests:

* A fall-back makes a wall-clock time **ambiguous**. Asia/Kolkata ended war-time
  at 1945-10-15 00:00 by rewinding to 23:00, so every wall time in
  1945-10-14 23:00–23:59 happened *twice*. Both sides resolve to the **first**
  occurrence (Python `fold=0`); an early two-pass draft of the Worker silently
  took the second, and the golden case `1945-10-14 23:30` is what caught it.
* Britain ran **Double Summer Time (+02:00)** in 1943, not ordinary BST. Any
  hardcoded "+01:00 in summer" assumption is wrong for the war years too.

## Tests

```bash
uv run pytest        # golden match + invariants
uv run ruff check .  # lint
```

Regenerate the golden JSON from the source doc:

```bash
uv run python scripts/parse_golden.py
```

## Layout

```
engine/
  ephemeris.py     swe config, ayanamsa registry, IST<->UTC
  positions.py     sidereal longitudes Sun..Ketu
  vimshottari.py   nakshatra, balance, maha/antar/pratyantar, rendering
  panchang.py      sunrise/sunset, tithi/nakshatra/yoga/karana solvers, panchang/vara at an instant
  chart_file.py    the chart file's facts: D9, dignity, combustion, transits, ingresses
  choghadiya.py    choghadiya windows + rahu/gulika/yamaganda kaals
  daily.py         deterministic daily_sky payload builder
  scoring.py       v1 heuristic guidance (Tarabala + weekday/paksha), rules-driven
  jobs/            precompute.py (nightly seed) + db.py (Neon connect)
  __main__.py      CLI (dasha / positions / panchang)
db/
  migrations/      plain-SQL schema (daily_sky, daily_guidance, score_rules, app_events)
  seed/            score_rules_v1.json — the tunable v1 rule set
  migrate.py       tiny migration + seed runner (no ORM)
.github/workflows/
  precompute.yml   nightly precompute at 01:00 IST
ephe/              vendored Swiss Ephemeris data (1800-2399)
scripts/
  parse_golden.py  AstroSage .docx -> tests/golden/astrosage_dasha.json
  compare.py       full delta report vs golden
tests/
  golden/          AstroSage dasha + DrikPanchang panchang references
  test_positions.py, test_vimshottari.py, test_panchang.py, test_precompute.py
```

## License

[AGPL-3.0-or-later](LICENSE). If you run a modified version as a network
service, you must offer users its source.
