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
    ACTIVE_IDENTITY_CONTENT_VERSION,
    ACTIVE_REPORT_CONTENT_VERSION,
    ACTIVE_SCORE_RULES_VERSION,
    DASHA_SEED_PATH,
    IDENTITY_SEED_PATH,
    REPORT_SEED_PATH,
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


# ── identity_content: the same mechanism again, from version ONE ─────────────
#
# score_rules and dasha_content both reached the marker table by incident —
# each shipped on an inferred version first and had to be migrated off it. This
# corpus starts on the marker, so there is no max(version) phase to remove
# later. These tests exist to keep it that way: the cheapest moment to hold a
# new corpus to the contract is before anything depends on it.


def test_active_identity_seed_file_exists():
    assert IDENTITY_SEED_PATH.is_file(), f"active identity seed missing: {IDENTITY_SEED_PATH}"


def test_active_identity_version_matches_seed_filename():
    expected = f"{ACTIVE_IDENTITY_CONTENT_VERSION}.json"
    assert IDENTITY_SEED_PATH.name == expected, (
        f"identity seed {IDENTITY_SEED_PATH.name} declares version "
        f"{ACTIVE_IDENTITY_CONTENT_VERSION!r}; expected the file named {expected}"
    )


def test_migrate_seeds_the_exact_identity_file_content_py_activates():
    """One declaration of the identity seed path, not two."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_migrate_identity", Path(__file__).resolve().parent.parent / "db" / "migrate.py"
    )
    migrate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migrate)
    assert migrate.IDENTITY_SEED == IDENTITY_SEED_PATH, (
        f"db/migrate.py seeds {migrate.IDENTITY_SEED} but engine/content.py "
        f"activates {IDENTITY_SEED_PATH}. Two declarations is how seeded and "
        "served diverge."
    )


def test_seeding_identity_content_also_marks_it_active():
    """Seed-without-activate must not be expressible for this corpus either."""
    import importlib.util
    import inspect

    spec = importlib.util.spec_from_file_location(
        "_migrate_identity_active",
        Path(__file__).resolve().parent.parent / "db" / "migrate.py",
    )
    migrate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migrate)
    src = inspect.getsource(migrate.seed_identity_content)
    assert "active_content" in src and "'identity_content'" in src, (
        "seed_identity_content does not stamp active_content. Seeding and "
        "activating must be one act."
    )


def _code_only(fn) -> str:
    """A function's source with its docstring and comment lines removed.

    These seeders are heavily commented, and the comments necessarily *name* the
    things the tests below forbid — `seed_dasha_content`'s docstring explains the
    `max(version)` bug at length. A naive substring check over the raw source
    therefore fails on the explanation rather than on the code, which is the same
    trap `test_precompute_takes_no_rules_version_override` avoids by asserting
    through argparse. Same discipline, different mechanism: strip the prose, then
    look at what the function actually does.
    """
    import ast
    import inspect
    import textwrap

    src = textwrap.dedent(inspect.getsource(fn))
    tree = ast.parse(src)
    node = tree.body[0]
    if (
        node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    ):
        node.body = node.body[1:]  # drop the docstring
    return ast.unparse(node)


def _migrate_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_migrate_probe", Path(__file__).resolve().parent.parent / "db" / "migrate.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_identity_seeds_both_halves_in_one_transaction():
    """The cross-corpus collision gate is only meaningful over a MATCHED pair of
    halves. A seeder that wrote nakshatra and moon_sign under different versions
    would produce a screen whose two paragraphs were never gated against each
    other — so both key types must be written by the one function that stamps
    the one marker."""
    code = _code_only(_migrate_module().seed_identity_content)
    assert "'nakshatra', 'moon_sign'" in code, (
        "seed_identity_content must write both key types in the same transaction "
        "as the marker"
    )
    assert code.count("active_content") == 1, (
        "exactly one activation write, covering both halves"
    )


def test_every_identity_seed_file_declares_a_version_matching_its_name():
    for path in sorted(SEED_DIR.glob("identity_content_v*.json")):
        version = json.loads(path.read_text()).get("version")
        assert path.name == f"{version}.json", (
            f"{path.name} declares version {version!r}; name and version disagree"
        )


def test_active_identity_version_is_the_newest_seed():
    """Numeric ordering, as for the other two kinds."""
    def key(name: str) -> tuple[int, ...]:
        stem = name.removesuffix(".json").removeprefix("identity_content_v")
        return tuple(int(p) for p in stem.split("_") if p.isdigit())

    names = [p.name for p in SEED_DIR.glob("identity_content_v*.json")]
    newest = max(names, key=key)
    assert IDENTITY_SEED_PATH.name == newest, (
        f"the newest identity seed is {newest} but engine/content.py activates "
        f"{IDENTITY_SEED_PATH.name}. If that is a deliberate rollback, update "
        "this test's expectation in the same commit."
    )


def test_no_kind_selects_its_version_by_inference():
    """The regression that has now been closed twice, asserted as a property of
    the source rather than of any one route: no seeder may derive a version from
    the data. `max(version)` and `ORDER BY version` are both lexical over TEXT.
    """
    migrate = _migrate_module()
    for fn in (
        migrate.seed,
        migrate.seed_dasha_content,
        migrate.seed_identity_content,
        migrate.seed_report_content,
    ):
        code = _code_only(fn).lower()
        assert "max(version)" not in code, f"{fn.__name__} infers a version via max()"
        assert "order by version" not in code, (
            f"{fn.__name__} infers a version by sorting"
        )
        # The positive half: each seeder must READ its version from the seed
        # file's own declaration. Banning the bad shapes is not the same as
        # requiring the good one — a seeder with neither would pass the checks
        # above while activating nothing.
        # `ast.unparse` normalises string quoting, so this is the canonical form
        # regardless of how the seeder was written.
        assert "data['version']" in code, (
            f"{fn.__name__} does not take its version from the seed file"
        )


# ── report_content: the fourth corpus, on the marker from version ONE ────────
#
# Same contract as identity_content, and for the same reason: this corpus has
# never had a max(version) phase and never will. The lexical-sort bug
# ('..._v10' < '..._v2' in Postgres) has been closed by retrofit twice in this
# repo; the cheapest place to close it a third time is before anything reads it.


def test_active_report_seed_file_exists():
    assert REPORT_SEED_PATH.is_file(), f"active report seed missing: {REPORT_SEED_PATH}"


def test_active_report_version_matches_seed_filename():
    expected = f"{ACTIVE_REPORT_CONTENT_VERSION}.json"
    assert REPORT_SEED_PATH.name == expected, (
        f"report seed {REPORT_SEED_PATH.name} declares version "
        f"{ACTIVE_REPORT_CONTENT_VERSION!r}; expected the file named {expected}"
    )
    assert ACTIVE_REPORT_CONTENT_VERSION == declared_version(REPORT_SEED_PATH)


def test_migrate_seeds_the_exact_report_file_content_py_activates():
    """One declaration of the report seed path, not two."""
    migrate = _migrate_module()
    assert migrate.REPORT_SEED == REPORT_SEED_PATH, (
        f"db/migrate.py seeds {migrate.REPORT_SEED} but engine/content.py "
        f"activates {REPORT_SEED_PATH}. Two declarations is how seeded and "
        "served diverge."
    )


def test_seeding_report_content_also_marks_it_active():
    """Seed-without-activate must not be expressible for this corpus either."""
    import inspect

    src = inspect.getsource(_migrate_module().seed_report_content)
    assert "active_content" in src and "'report_content'" in src, (
        "seed_report_content does not stamp active_content. Seeding and "
        "activating must be one act."
    )


def test_report_seeds_every_movement_of_every_kind_in_one_transaction():
    """The consecutive-report distinctness gate spans all of a kind's
    movements, so it is only meaningful over a matched SET of them. A seeder
    that wrote `shape` and `close` under different versions would produce a
    report whose movements were never gated against each other — made
    unreachable, not merely detected.

    The key types are no longer a literal here: transit's movements differ
    from the range reports' (`weather`/`passage`/`phase`/`sade_sati` against
    `shape`/`turn`/`standing`/`close`), so the seeder iterates
    `engine.reports.KEY_TYPES`. That indirection is CHECKED rather than
    trusted — the assertion below reads the real mapping and confirms it
    covers every kind the seed file carries, which is strictly stronger than
    the old substring match: a new kind added to the seed file with no
    KEY_TYPES entry now fails here instead of seeding nothing.
    """
    from engine.reports import KEY_TYPES

    code = _code_only(_migrate_module().seed_report_content)
    assert "KEY_TYPES[report_kind]" in code, (
        "seed_report_content must iterate every key type of every kind in the "
        "same transaction as the marker"
    )
    assert code.count("active_content") == 1, (
        "exactly one activation write, covering every kind and every movement"
    )

    seeded = json.loads(REPORT_SEED_PATH.read_text())
    kinds = set(seeded) - {"version", "_about"}
    unknown = kinds - set(KEY_TYPES)
    assert not unknown, f"seed file has kinds KEY_TYPES does not know: {unknown}"
    assert kinds == {"weekly", "monthly", "transit"}, kinds
    for kind in kinds:
        assert set(seeded[kind]) == set(KEY_TYPES[kind]), (
            f"{kind}: seed file movements {sorted(seeded[kind])} do not match "
            f"KEY_TYPES {sorted(KEY_TYPES[kind])}"
        )


def test_every_report_seed_file_declares_a_version_matching_its_name():
    for path in sorted(SEED_DIR.glob("report_content_v*.json")):
        version = json.loads(path.read_text()).get("version")
        assert path.name == f"{version}.json", (
            f"{path.name} declares version {version!r}; name and version disagree"
        )


def test_active_report_version_is_the_newest_seed():
    """Numeric ordering, as for the other three kinds."""

    def key(name: str) -> tuple[int, ...]:
        stem = name.removesuffix(".json").removeprefix("report_content_v")
        return tuple(int(p) for p in stem.split("_") if p.isdigit())

    names = [p.name for p in SEED_DIR.glob("report_content_v*.json")]
    newest = max(names, key=key)
    assert REPORT_SEED_PATH.name == newest, (
        f"the newest report seed is {newest} but engine/content.py activates "
        f"{REPORT_SEED_PATH.name}. If that is a deliberate rollback, update "
        "this test's expectation in the same commit."
    )
