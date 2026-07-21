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
- **`engine/panchang.py`** — full panchang for a date + location: sunrise/sunset
  (Swiss rise/set), tithi, nakshatra, yoga, karana — every boundary root-found
  on the driving angle (never sampled), so kshaya/adhika cases fall out
  naturally — plus vaar, paksha and moon phase.
- **`engine/choghadiya.py`** — day/night choghadiya (8 splits each) and rahu
  kaal / gulika kaal / yamaganda, pure arithmetic on sunrise/sunset.
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

## Install & run

Uses [uv](https://docs.astral.sh/uv/):

```bash
uv sync

# Vimshottari maha + antar table, AstroSage layout:
uv run python -m engine dasha --dob 23/09/1989 --time 04:47 --lat 19.99 --lon 73.79

# Sidereal graha longitudes:
uv run python -m engine positions --dob 23/09/1989 --time 04:47

# Full delta report vs the golden chart (auditable):
uv run python scripts/compare.py

# DrikPanchang-style day card (panchang + kaals + choghadiya):
uv run python -m engine panchang --date 2026-07-18 --lat 18.5204 --lon 73.8567
```

`--dob` is `dd/mm/yyyy`, `--time` is 24-hour `HH:MM`, both interpreted as **IST**
(India has been a fixed UTC+05:30 since 1945). `--lat`/`--lon` are optional —
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

**Maximum deviation vs AstroSage: ±2 days, at the antar level only.** Balance,
nakshatra and maha boundaries match (see table above). Analysis trail:

1. *Ayanamsa* — resolved: `lahiri_vp285` (above). Wrong flavour costs ~3–4 days
   everywhere; this is not the residual.
2. *Year length* — resolved: 365.25 real days. Tropical/sidereal/360-day years
   are all measurably worse.
3. *Cascading day-rounding* (Prompt A.1) — **partially confirmed**. AstroSage
   rounds maha boundaries to whole days (round-half makes 9/10 maha ends exact),
   and deriving antar dates from the rounded parent then rounding again cuts the
   two-day offenders from 8 to 4. It does **not** close them, so the rounding is
   an opt-in presentation mode (`format_astrosage(..., astrosage_rounding=True)`,
   CLI `--astrosage-rounding`), while exact float datetimes stay the canonical
   internal representation.
4. *Residual* — the remaining 4 two-day antar dates are consistent with a
   sub-arcsecond difference between Swiss VP285 and AstroSage's exact internal
   Lahiri constant. **Accepted**; reported, not fudged — see the `xfail` test
   `test_antar_strict_one_day_is_the_open_question` and `scripts/compare.py`.

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
  Inside tolerance; **accepted, not tuned away**.

### Historical timezones and India's war-time DST (1941–45)

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
  panchang.py      sunrise/sunset, tithi/nakshatra/yoga/karana solvers
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
