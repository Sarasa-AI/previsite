"""Postgres-only Alembic vs ORM metadata drift check (CI / TEST_DATABASE_URL)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]

# Documented unavoidable differences between Alembic migrations and ORM metadata.
# Each entry must be commented with why it cannot be closed in this phase.
METADATA_DRIFT_ALLOWLIST: set[tuple[str, str]] = {
    # pgvector HNSW index is created in migration SQL; ORM Vector column does not
    # emit the same reflected index shape under compare_metadata.
    ("medical_knowledge", "remove_index"),
    # Intelligence tables: migration uses UniqueConstraint; ORM uses unique=True
    # on the index. Autogenerate reports remove_constraint + add_index churn.
    ("clinical_findings", "remove_constraint"),
    ("clinical_findings", "remove_index"),
    ("clinical_findings", "add_index"),
    ("recommendations", "remove_constraint"),
    ("recommendations", "remove_index"),
    ("recommendations", "add_index"),
    ("risk_signals", "remove_constraint"),
    ("risk_signals", "remove_index"),
    ("risk_signals", "add_index"),
}


def _in_ci() -> bool:
    return bool(os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"))


def _require_test_database_url() -> str:
    """Return TEST_DATABASE_URL or fail hard in CI / skip locally."""
    url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if url:
        return url
    if _in_ci():
        pytest.fail(
            "TEST_DATABASE_URL must be set in CI so alembic integrity tests "
            "cannot be silently skipped"
        )
    pytest.skip("Requires TEST_DATABASE_URL (Postgres CI service)")
    raise AssertionError("unreachable")


def _sync_url() -> str | None:
    url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not url:
        return None
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    return url


def test_alembic_upgrade_head_matches_models_allowlist() -> None:
    _require_test_database_url()
    sync_url = _sync_url()
    assert sync_url

    # Use a dedicated database name to avoid clobbering the shared test DB
    # when possible; fall back to upgrading the provided URL in-place after
    # documenting that CI truncates between tests.
    env = os.environ.copy()
    env["DATABASE_URL"] = sync_url.replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    )
    if not env["DATABASE_URL"].startswith("postgresql"):
        env["DATABASE_URL"] = sync_url

    # Ensure schema is at head via alembic
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND_ROOT),
        env={**env, "PYTHONPATH": str(BACKEND_ROOT)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    # Import metadata after upgrade
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from app.db.database import Base
    import app.models  # noqa: F401
    import app.modules.intelligence.infrastructure.models  # noqa: F401
    import app.modules.workspace.infrastructure.models  # noqa: F401

    engine = create_engine(sync_url)
    with engine.connect() as conn:
        context = MigrationContext.configure(
            conn,
            opts={"compare_type": True},
        )
        diffs = compare_metadata(context, Base.metadata)

    remaining = []
    for diff in diffs:
        # diff tuples vary; normalize to (table, kind) when possible
        kind = diff[0] if isinstance(diff, tuple) else str(diff)
        table = None
        if isinstance(diff, tuple) and len(diff) > 1:
            target = diff[1]
            table = getattr(target, "table", None)
            if table is not None:
                table = getattr(table, "name", str(table))
            elif hasattr(target, "name"):
                table = target.name
        key = (str(table), str(kind))
        if key in METADATA_DRIFT_ALLOWLIST:
            continue
        # Also allowlist by kind alone when table unknown
        if ( "*", str(kind)) in METADATA_DRIFT_ALLOWLIST:
            continue
        remaining.append(diff)

    assert remaining == [], f"Unexpected model/migration diffs: {remaining!r}"


def test_reconciliation_revision_downgrade_upgrade_smoke() -> None:
    _require_test_database_url()
    sync_url = _sync_url()
    assert sync_url
    env = {
        **os.environ,
        "DATABASE_URL": sync_url.replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://"
        ),
        "PYTHONPATH": str(BACKEND_ROOT),
    }

    up = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert up.returncode == 0, up.stdout + up.stderr

    # Downgrade one revision then re-upgrade (enum ADD VALUE is not reversible;
    # downgrade still drops indexes/column which is enough for a smoke test).
    down = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "-1"],
        cwd=str(BACKEND_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert down.returncode == 0, down.stdout + down.stderr

    up2 = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert up2.returncode == 0, up2.stdout + up2.stderr

    # Idempotent second upgrade
    up3 = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert up3.returncode == 0, up3.stdout + up3.stderr
