"""Single source of truth for the ACTIVE content versions.

There is exactly **one** place a human sets which corpus is live, per content
kind: the `*_SEED_PATH` constants below. Everything else *derives* from them —

  • `db/migrate.py` seeds that file into `score_rules` and stamps its declared
    version into the `active_content` marker table, in one transaction;
  • `engine/scoring.py` re-exports the same version as `SCORE_RULES_VERSION`;
  • `engine/jobs/precompute.py` reads rules for that version and writes it into
    `daily_guidance.rules_version`.

and, for the dasha interpretation library —

  • `db/migrate.py` seeds `DASHA_SEED_PATH` into `dasha_content` and stamps its
    declared version into `active_content` under kind `'dasha_content'`;
  • `/v1/dasha/content` serves the version that marker names.

Because the version is read out of the seed file's own ``version`` field rather
than typed a second time, **seeding a corpus and activating it are the same
act**. The `content_v3_2` incident — a new corpus seeded into Neon while
precompute kept reading `content_v3_1` from a hand-typed constant — is not
expressible in this design: there is no second constant to forget.

To change an active version: point the relevant `*_SEED_PATH` at a different
seed file. That is the whole procedure. To roll back: point it at the previous
file. Old versions keep their rows (seeding is additive), so a rollback needs
no data restore — only migrate + the nightly job re-running.

Why a marker table rather than asking the data. Both tables are additive, so
neither can answer "which version is live?" on its own: `max(version)` is a
**lexical** max over TEXT, and `'dasha_content_v10' < 'dasha_content_v2'` in
Postgres — reaching v10 would silently serve v2 again. Intent has to be
recorded, not inferred.
"""

from __future__ import annotations

import json
from pathlib import Path

_SEED_DIR = Path(__file__).resolve().parent.parent / "db" / "seed"

# ── THE ONE LINE THAT SETS THE ACTIVE score_rules VERSION ────────────────────
SEED_PATH = _SEED_DIR / "score_rules_content_v3_2.json"
# ── THE ONE LINE THAT SETS THE ACTIVE dasha_content VERSION ──────────────────
DASHA_SEED_PATH = _SEED_DIR / "dasha_content_v2.json"
# ── THE ONE LINE THAT SETS THE ACTIVE identity_content VERSION ───────────────
IDENTITY_SEED_PATH = _SEED_DIR / "identity_content_v1.json"
# ─────────────────────────────────────────────────────────────────────────────


def declared_version(path: Path) -> str:
    """The ``version`` a seed file declares for itself."""
    data = json.loads(path.read_text())
    version = data.get("version")
    if not isinstance(version, str) or not version:
        raise SystemExit(f"seed file {path} declares no string 'version'")
    return version


#: The active version — derived, never typed. Read by migrate + scoring +
#: precompute so all three can only ever agree.
ACTIVE_SCORE_RULES_VERSION = declared_version(SEED_PATH)

#: The active dasha interpretation library version — derived, never typed.
#: Written to `active_content` by migrate; served by /v1/dasha/content.
ACTIVE_DASHA_CONTENT_VERSION = declared_version(DASHA_SEED_PATH)

#: The active "About your star" corpus version — derived, never typed.
#: Written to `active_content` by migrate; served by /v1/identity/content.
#: Uses the marker from its FIRST version rather than retrofitting one later:
#: score_rules and dasha_content both had to be migrated off max(version) after
#: the fact, and the second of those was a lexical-sort bug that would have
#: silently rolled the library back eight versions at v10. Starting here costs
#: nothing and makes that class of bug unreachable for this corpus.
ACTIVE_IDENTITY_CONTENT_VERSION = declared_version(IDENTITY_SEED_PATH)
