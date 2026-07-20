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

from engine.content import ACTIVE_SCORE_RULES_VERSION, SEED_PATH, declared_version
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
