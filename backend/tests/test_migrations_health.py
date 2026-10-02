"""Unit tests for migration health probe statuses: ok / behind / unknown."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.health_checks import check_migrations


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


@pytest.mark.asyncio
async def test_migrations_status_ok(monkeypatch):
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_FakeResult([("q1r2s3t4u5v6",)]))

    fake_script = MagicMock()
    fake_script.get_heads.return_value = ["q1r2s3t4u5v6"]
    monkeypatch.setattr(
        "alembic.script.ScriptDirectory.from_config",
        lambda *_a, **_k: fake_script,
    )
    monkeypatch.setattr(
        "alembic.config.Config",
        lambda *_a, **_k: SimpleNamespace(),
    )

    result = await check_migrations(db)
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_migrations_status_behind(monkeypatch):
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_FakeResult([("p0q1r2s3t4u5",)]))

    fake_rev = SimpleNamespace(revision="p0q1r2s3t4u5")
    fake_script = MagicMock()
    fake_script.get_heads.return_value = ["q1r2s3t4u5v6"]
    fake_script.walk_revisions.return_value = [fake_rev]
    monkeypatch.setattr(
        "alembic.script.ScriptDirectory.from_config",
        lambda *_a, **_k: fake_script,
    )
    monkeypatch.setattr(
        "alembic.config.Config",
        lambda *_a, **_k: SimpleNamespace(),
    )

    result = await check_migrations(db)
    assert result["status"] == "behind"


@pytest.mark.asyncio
async def test_migrations_status_unknown_unreadable(monkeypatch):
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("no table"))

    fake_script = MagicMock()
    fake_script.get_heads.return_value = ["q1r2s3t4u5v6"]
    monkeypatch.setattr(
        "alembic.script.ScriptDirectory.from_config",
        lambda *_a, **_k: fake_script,
    )
    monkeypatch.setattr(
        "alembic.config.Config",
        lambda *_a, **_k: SimpleNamespace(),
    )

    result = await check_migrations(db)
    assert result["status"] == "unknown"
