"""The gate for the `content_v3_2` class of failure: seeded != served.

`content_v3_2` was seeded into Neon, gated by CI, pushed — and never reached a
user, because `precompute` took its version from a hand-typed constant that
still said `content_v3_1`. Every individual step was green. Nothing compared the
steps to each other.

These tests are that comparison, at the earliest point it can be made: in CI,
against the repo, with no database. They fail on the *repo-level* half of the
drift (a version constant that disagrees with the seed file). The *runtime* half
— rules seeded but guidance rows never re-written with them — is not visible
here at all, and is covered by `/v1/health` in aura-api. Neither check subsumes
the other; the incident needed both.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from engine.content import (
    ACTIVE_DASHA_CONTENT_VERSION,
    ACTIVE_SCORE_RULES_VERSION,
    DASHA_SEED_PATH,
    SEED_PATH,
    declared_version,
)
from engine.scoring import SCORE_RULES_VERSION

SEED_DIR = Path(__file__).resolve().parent.parent / "db" / "seed"


def test_active_seed_file_exists():
    assert SEED_PATH.is_file(), f"active seed file is missing: {SEED_PATH}"


def test_scoring_version_is_the_seed_files_own_version():
    """The exact assertion that would have caught the incident on day one."""
    assert SCORE_RULES_VERSION == declared_version(SEED_PATH), (
        f"engine.scoring.SCORE_RULES_VERSION is {SCORE_RULES_VERSION!r} but the "
        f"active seed file {SEED_PATH.name} declares {declared_version(SEED_PATH)!r}. "
        "These cannot differ — precompute would stamp guidance with a version "
        "whose corpus is not the one being seeded."
    )


def test_active_version_matches_seed_filename():
    """Filename and declared version agree, so the seed dir is readable at a glance."""
    expected = f"score_rules_{ACTIVE_SCORE_RULES_VERSION}.json"
    assert SEED_PATH.name == expected, (
        f"seed file {SEED_PATH.name} declares version "
        f"{ACTIVE_SCORE_RULES_VERSION!r}; expected the file to be named {expected}"
    )


def test_migrate_seeds_the_exact_file_content_py_activates():
    """db/migrate.py must seed the active file — same object, not a copy of the path."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_migrate", Path(__file__).resolve().parent.parent / "db" / "migrate.py"
    )
    migrate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migrate)
    assert migrate.SEED == SEED_PATH, (
        f"db/migrate.py seeds {migrate.SEED} but engine/content.py activates "
        f"{SEED_PATH}. Two declarations of the seed path is how seeded and "
        "served diverge."
    )


def test_migrate_runs_as_a_script():
    """`python db/migrate.py` must import cleanly — the way CI actually calls it.

    Importing db/migrate.py from pytest succeeds trivially (the repo root is
    already on sys.path), which masked a real ModuleNotFoundError the first time
    this change reached the nightly job. Only a subprocess reproduces the real
    invocation, where sys.path[0] is db/ and `engine` is not importable.
    """
    import subprocess

    root = Path(__file__).resolve().parent.parent
    env = {k: v for k, v in os.environ.items() if k != "NEON_DATABASE_URL"}
    proc = subprocess.run(
        [sys.executable, "db/migrate.py", "--no-seed"],
        cwd=root, env=env, capture_output=True, text=True,
    )
    combined = proc.stdout + proc.stderr
    assert "ModuleNotFoundError" not in combined, (
        f"db/migrate.py cannot be run as a script:\n{combined}"
    )
    # Reaching the credentials check proves every import resolved.
    assert "NEON_DATABASE_URL is not set" in combined, combined


def test_precompute_takes_no_rules_version_override():
    """A CLI flag would be a second place to set the active version.

    Asserted through argparse rather than by grepping the source, so the test
    is about behaviour and cannot be tripped by a comment that names the flag.
    """
    from engine.jobs import precompute as job

    with pytest.raises(SystemExit) as exc:
        job.main(["--rules-version", "content_v3_1"])
    assert exc.value.code == 2, (
        "precompute accepted --rules-version. That is a second source of truth "
        "for the active version; remove it."
    )


def test_every_seed_file_declares_a_version_matching_its_name():
    """Guards the whole seed dir, so a future corpus starts coherent."""
    for path in sorted(SEED_DIR.glob("score_rules_*.json")):
        version = json.loads(path.read_text()).get("version")
        assert path.name == f"score_rules_{version}.json", (
            f"{path.name} declares version {version!r}; name and version disagree"
        )


def test_active_version_is_the_newest_score_rules_seed():
    """Catches authoring a new corpus and forgetting to point content.py at it.

    Ordered by numeric version tuple, not lexically — `content_v3_10` must sort
    above `content_v3_2`, which a string comparison gets backwards.
    """
    def key(name: str) -> tuple[int, ...]:
        stem = name.removeprefix("score_rules_").removesuffix(".json")
        parts = stem.replace("content_v", "v").lstrip("v").split("_")
        return tuple(int(p) for p in parts if p.isdigit())

    names = [p.name for p in SEED_DIR.glob("score_rules_content_v*.json")]
    newest = max(names, key=key)
    assert SEED_PATH.name == newest, (
        f"the newest score_rules seed is {newest} but engine/content.py activates "
        f"{SEED_PATH.name}. If that is a deliberate rollback, update this test's "
        "expectation in the same commit so the rollback is a recorded decision."
    )


@pytest.mark.parametrize("required", ["why_cause_tara"])
def test_active_corpus_carries_the_keys_v3_2_reauthored(required):
    """Sanity: the activated corpus really is the one with the v3_2 work in it."""
    rules = json.loads(SEED_PATH.read_text())["rules"]
    assert required in rules, f"active corpus is missing rule key {required!r}"


# ── dasha_content: the same mechanism, the same gate ─────────────────────────
#
# `/v1/dasha/content` used to select `max(version)` — a lexical max, which ranks
# 'dasha_content_v10' below 'dasha_content_v2' and would have rolled the library
# back eight versions on the day someone authored v10. These tests hold the
# dasha library to the identical single-source-of-truth contract as score_rules,
# so the two kinds cannot drift apart in how they are activated.


def test_active_dasha_seed_file_exists():
    assert DASHA_SEED_PATH.is_file(), f"active dasha seed missing: {DASHA_SEED_PATH}"


def test_active_dasha_version_matches_seed_filename():
    expected = f"{ACTIVE_DASHA_CONTENT_VERSION}.json"
    assert DASHA_SEED_PATH.name == expected, (
        f"dasha seed {DASHA_SEED_PATH.name} declares version "
        f"{ACTIVE_DASHA_CONTENT_VERSION!r}; expected the file named {expected}"
    )


def test_migrate_seeds_the_exact_dasha_file_content_py_activates():
    """One declaration of the dasha seed path, not two."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_migrate_dasha", Path(__file__).resolve().parent.parent / "db" / "migrate.py"
    )
    migrate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migrate)
    assert migrate.DASHA_SEED == DASHA_SEED_PATH, (
        f"db/migrate.py seeds {migrate.DASHA_SEED} but engine/content.py activates "
        f"{DASHA_SEED_PATH}. Two declarations is how seeded and served diverge."
    )


def test_seeding_dasha_content_also_marks_it_active():
    """Seed-without-activate must not be expressible.

    Asserted on the source of `seed_dasha_content` because the write itself
    needs a database CI does not have. What is checked is the property that
    matters: the activation write lives *inside* the same function, and
    therefore the same transaction, as the corpus write.
    """
    import importlib.util
    import inspect

    spec = importlib.util.spec_from_file_location(
        "_migrate_active", Path(__file__).resolve().parent.parent / "db" / "migrate.py"
    )
    migrate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migrate)
    src = inspect.getsource(migrate.seed_dasha_content)
    assert "active_content" in src and "'dasha_content'" in src, (
        "seed_dasha_content does not stamp active_content. Seeding a corpus and "
        "activating it must be one act — otherwise /v1/dasha/content serves a "
        "version nobody activated, or 503s because no marker exists."
    )


def test_every_dasha_seed_file_declares_a_version_matching_its_name():
    for path in sorted(SEED_DIR.glob("dasha_content_v*.json")):
        version = json.loads(path.read_text()).get("version")
        assert path.name == f"{version}.json", (
            f"{path.name} declares version {version!r}; name and version disagree"
        )


def test_active_dasha_version_is_the_newest_seed():
    """Numeric ordering — the exact comparison the old max(version) got wrong."""
    def key(name: str) -> tuple[int, ...]:
        stem = name.removesuffix(".json").removeprefix("dasha_content_v")
        return tuple(int(p) for p in stem.split("_") if p.isdigit())

    names = [p.name for p in SEED_DIR.glob("dasha_content_v*.json")]
    newest = max(names, key=key)
    assert DASHA_SEED_PATH.name == newest, (
        f"the newest dasha seed is {newest} but engine/content.py activates "
        f"{DASHA_SEED_PATH.name}. If that is a deliberate rollback, update this "
        "test's expectation in the same commit so it is a recorded decision."
    )


def test_lexical_max_would_pick_the_wrong_dasha_version():
    """Guards the premise, so the fix is never 'simplified' back to max(version).

    If this ever fails, string ordering has changed and the whole argument for
    the marker table needs revisiting — it is not a test of our code so much as
    of the fact our code is defending against.
    """
    versions = ["dasha_content_v1", "dasha_content_v2", "dasha_content_v10"]
    assert max(versions) == "dasha_content_v2", (
        "lexical max no longer picks v2 over v10 — re-examine why active_content exists"
    )
