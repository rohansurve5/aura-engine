"""Single source of truth for the ACTIVE content version.

There is exactly **one** place a human sets which score_rules corpus is live:
`SEED_PATH` below. Everything else *derives* from it —

  • `db/migrate.py` seeds that file into `score_rules` and stamps its declared
    version into the `active_content` marker table, in one transaction;
  • `engine/scoring.py` re-exports the same version as `SCORE_RULES_VERSION`;
  • `engine/jobs/precompute.py` reads rules for that version and writes it into
    `daily_guidance.rules_version`.

Because the version is read out of the seed file's own ``version`` field rather
than typed a second time, **seeding a corpus and activating it are the same
act**. The `content_v3_2` incident — a new corpus seeded into Neon while
precompute kept reading `content_v3_1` from a hand-typed constant — is not
expressible in this design: there is no second constant to forget.

To change the active version: point `SEED_PATH` at a different seed file. That
is the whole procedure. To roll back: point it at the previous file. Old
versions keep their `score_rules` rows (seeding is additive), so a rollback
needs no data restore — only the nightly job re-running.
"""

from __future__ import annotations

import json
from pathlib import Path

# ── THE ONE LINE THAT SETS THE ACTIVE CONTENT VERSION ────────────────────────
SEED_PATH = (
    Path(__file__).resolve().parent.parent
    / "db" / "seed" / "score_rules_content_v3_2.json"
)
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
