"""AT-S0-12/13 — الترحيلات والنسخ الاحتياطي والامتدادات."""
import pathlib

import pytest
from sqlalchemy import text

from athera_api.db import tenant_session

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
MIGRATIONS = REPO_ROOT / "infra" / "db" / "migrations" / "versions"


@pytest.mark.asyncio
async def test_pgvector_extension_is_installed(db_ready):
    async with tenant_session(None) as session:
        row = (
            await session.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))
        ).scalar_one_or_none()
    assert row == "vector", "pgvector is required by §31.3"


def test_every_migration_has_a_real_downgrade():
    """AT-S0-13 — ترحيل بلا تراجع نظيف يعني بيئة لا يمكن إصلاحها."""
    offenders = []
    for path in sorted(MIGRATIONS.glob("[0-9]*.py")):
        source = path.read_text(encoding="utf-8")
        body = source.split("def downgrade()")[-1]
        if body.strip().endswith("pass") or "pass" == body.split(":", 1)[-1].strip():
            offenders.append(path.name)
    assert not offenders, f"migrations without a downgrade: {offenders}"


def test_migrations_form_a_single_chain():
    revisions, downs = {}, {}
    for path in sorted(MIGRATIONS.glob("[0-9]*.py")):
        source = path.read_text(encoding="utf-8")
        rev = source.split('revision = "')[1].split('"')[0]
        down_raw = source.split("down_revision = ")[1].split("\n")[0].strip()
        revisions[rev] = path.name
        downs[rev] = None if down_raw == "None" else down_raw.strip('"')
    roots = [rev for rev, down in downs.items() if down is None]
    assert len(roots) == 1, f"expected exactly one root migration, found {roots}"
    for rev, down in downs.items():
        assert down is None or down in revisions, f"{revisions[rev]} points at unknown revision {down}"


def test_backup_restore_drill_is_documented():
    """§38.2 — الاستعادة غير المختبرة ليست نسخة احتياطية."""
    runbook = REPO_ROOT / "docs" / "runbooks" / "backup-restore.md"
    assert runbook.exists(), "AT-S0-12 requires a documented and executed restore drill"
    text_content = runbook.read_text(encoding="utf-8")
    assert "pg_restore" in text_content or "pg_dump" in text_content
