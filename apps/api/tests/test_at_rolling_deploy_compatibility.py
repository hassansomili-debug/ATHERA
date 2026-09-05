"""توافقُ النشر المتدحرج | the rolling-deployment compatibility contract.

**بين ترحيل القاعدة ونشر الخادم نافذةٌ يخدم فيها القديمُ الجديدَ.**

ولا مفرّ منها: نماذجُ الموجة الأولى تختار أعمدةً يضيفها 0027 و0028، فلا
يستطيع خادمُها أن يقرأ مخطَّط 0025. فالترتيبُ الوحيد الممكن أن يُرحَّل
المخطَّطُ أوّلًا ثمّ يُنشر الخادم — وبينهما لحظاتٌ يكتب فيها الخادمُ
القديم في مخطَّطٍ لا يعرفه.

وهذا الملفّ يثبت أنّ تلك اللحظات آمنة. يحاكي كتابةَ الخادم القديم حرفيًّا
— `consent_recorded_at` وحده، بلا `consent_method` ولا `consent_state` —
ويطلب من القاعدة أن تقبلها على مخطَّط 0028.

**ولو فُرض العقد في 0028 لسقط كلُّ تسجيل موافقةٍ في تلك النافذة بـ٥٠٠.**
ولذلك أُجِّل إلى 0029، ولذلك هذا الفحص موجود: هو الخاصّيّة التي وُجدت
التوسعةُ من أجلها، ولا يحرسها شيءٌ غيره.
"""
from __future__ import annotations

import os
import pathlib
import re
import uuid

import pytest

from tests.conftest import requires_db

MIGRATIONS = (pathlib.Path(__file__).resolve().parents[3]
              / "infra" / "db" / "migrations" / "versions")

#: القيودُ الثلاثة المؤجَّلة — تُفرض في 0029 وحدها.
DEFERRED = ("consent_has_a_method", "consent_has_a_time")


def _upgrade_of(name: str) -> str:
    path = next(MIGRATIONS.glob(f"{name}*.py"))
    src = path.read_text(encoding="utf-8")
    return src.split("def upgrade()", 1)[1].split("def downgrade()", 1)[0]


# ═════════════════ ١. شكلُ الترحيلين ═════════════════

def test_the_expand_migration_defers_the_contract_constraints():
    """**0028 توسعةٌ لا تفرض ما يعجز عنه الخادمُ القائم.**

    ويُقرأ من الترحيل نفسه: لو أعادها أحدٌ إلى 0028 لعادت النافذةُ قاتلة،
    ولا شيء آخر يشتكي — لأنّ فحوص المخطَّط كلَّها تعمل على الرأس الأخير.
    """
    expand = _upgrade_of("0028")
    for name in DEFERRED:
        assert f'"{name}"' not in expand, (
            f"القيد {name} عاد إلى ترحيل التوسعة — النافذةُ تصير قاتلة")


def test_the_contract_migration_adds_exactly_the_deferred_three():
    """الثلاثةُ المؤجَّلة — تُقرأ من سجلّ الترحيل لا من جسم الدالّة.

    و`upgrade()` يبنيها بـf-string من `DEFERRED`، فالبحثُ عن الاسم حرفيًّا
    في الجسم يقرأ قالبًا لا اسمًا.
    """
    source = next(MIGRATIONS.glob("0029*.py")).read_text(encoding="utf-8")
    registry = source.split("DEFERRED = (", 1)[1].split("\n)", 1)[0]
    for table, name in (("project_members", "consent_has_a_method"),
                        ("project_members", "consent_has_a_time"),
                        ("authorship_agreements", "consent_has_a_method")):
        assert f'"{table}", "{name}"' in " ".join(registry.split()), (
            f"العقد لا يفرض ck_{table}_{name}")
    assert "ADD CONSTRAINT" in _upgrade_of("0029"), "العقد لا يُفرض أصلًا"


def test_the_contract_repairs_before_it_enforces():
    """**ولا يُفرض قيدٌ على أمل.** الترميمُ أوّلًا، ثمّ برهانُ الخلوّ."""
    contract = _upgrade_of("0029")
    repair = contract.index("UPDATE project_members")
    proof = contract.index("RAISE EXCEPTION")
    enforce = contract.index("ADD CONSTRAINT")
    assert repair < proof < enforce, "الترتيب: ترميمٌ ثمّ برهانٌ ثمّ فرض"


def test_legacy_rows_are_never_called_self_consent():
    """**قاعدةٌ علميّة لا تفصيلُ ترحيل.**

    موافقةٌ كُتبت في النافذة لا يُعرف كاتبُها. ووصفُها «ذاتية» دعوى أنّ
    العضو نفسه أقرّ — ولا دليل. وتبقى مجهولةَ الإسناد باسمها.
    """
    contract = _upgrade_of("0029")
    repair = contract.split("ADD CONSTRAINT", 1)[0]
    assert "'legacy_unverified'" in repair, "الترميم لا يُسمّي المجهول"
    assert "'self'" not in repair, "الترميم يصف موافقةً مجهولةً بأنّها ذاتية"
    assert "consent_recorded_by" not in repair, "الترميم يختلق صاحبًا"
    assert "consent_evidence" not in repair, "الترميم يختلق سندًا"


# ═════════════════ ٢. النافذةُ نفسها، على قاعدتين ═════════════════
#
# **ولا تُقاس النافذةُ على رأس السلسلة.** قاعدةُ الاختبارات تُرحَّل إلى
# `0029` حيث العقدُ مفروض، فالكتابةُ القديمة تُرفض فيها — وذاك صوابٌ لا
# عطب. فتُبنى قاعدةٌ ثالثة تقف عند `0028` بعينها، وتُقاس عليها.
#
# والعبارةُ المستعملة هي عبارةُ الخادم القديم حرفيًّا كما التقطها المشغّل:
#
#     UPDATE project_members SET consent_recorded_at=$1, updated_at=now()
#      WHERE project_members.id = $2
#
# ولا تُستعمل نماذجُ الموجة هنا عمدًا: هي تحمل أعمدةً لم يكن الخادمُ
# القديم يعرفها، فالكتابةُ بها ليست كتابته.

EXPAND_URL = os.environ.get("ATHERA_EXPAND_SCHEMA_URL", "")
requires_expand_db = pytest.mark.skipif(
    not EXPAND_URL, reason="قاعدةُ نافذة النشر (0028) غير مهيّأة")

OLD_MEMBER_CONSENT = (
    "UPDATE project_members SET consent_recorded_at = now(), updated_at = now() "
    "WHERE id = :member_id")
OLD_AGREEMENT_CONSENT = (
    "UPDATE authorship_agreements SET consent_status = 'granted', "
    "consent_recorded_at = now(), updated_at = now() WHERE id = :agreement_id")


async def _one_member_and_agreement(engine):
    """يزرع صفَّين بالحدّ الأدنى، بـSQL خام — لا نموذجَ موجةٍ في الطريق."""
    from sqlalchemy import text

    tenant, project = uuid.uuid4(), uuid.uuid4()
    member, agreement = uuid.uuid4(), uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(text(
            "SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)})
        await conn.execute(text(
            "INSERT INTO tenants (id, slug, name_ar, name_en) "
            "VALUES (:i, :s, 'نافذة', 'Window')"),
            {"i": tenant, "s": f"window-{tenant.hex[:8]}"})
        await conn.execute(text(
            "INSERT INTO research_projects (id, tenant_id, working_title_ar, "
            "status, current_gate) VALUES (:i, :t, 'مشروع النافذة', 'planned', 'G1')"),
            {"i": project, "t": tenant})
        await conn.execute(text(
            "INSERT INTO project_members (id, tenant_id, project_id, display_name, role) "
            "VALUES (:i, :t, :p, 'د. فلان', 'co_author')"),
            {"i": member, "t": tenant, "p": project})
        await conn.execute(text(
            "INSERT INTO authorship_agreements (id, tenant_id, opportunity_id, "
            "party_id, author_position, consent_status) "
            "VALUES (:i, :t, :o, :y, 1, 'pending')"),
            {"i": agreement, "t": tenant, "o": uuid.uuid4(), "y": uuid.uuid4()})
    return member, agreement


@requires_expand_db
@pytest.mark.asyncio
async def test_the_old_api_can_still_write_consent_on_the_expanded_schema():
    """**الخاصّيّةُ التي وُجدت التوسعةُ لأجلها — OLD API + 0028.**

    لو سقطت هذه، لسقط كلُّ تسجيل موافقةٍ بين ترحيل الإنتاج ونشر الموجة.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(EXPAND_URL, poolclass=None)
    try:
        member, agreement = await _one_member_and_agreement(engine)
        async with engine.begin() as conn:
            await conn.execute(text(OLD_MEMBER_CONSENT), {"member_id": member})
            await conn.execute(text(OLD_AGREEMENT_CONSENT),
                               {"agreement_id": agreement})
        async with engine.connect() as conn:
            method = (await conn.execute(text(
                "SELECT consent_method FROM project_members WHERE id = :i"),
                {"i": member})).scalar_one()
            assert method is None, "الخادمُ القديم لا يكتب طريقة"
    finally:
        await engine.dispose()


@requires_db
@pytest.mark.asyncio
async def test_the_same_write_is_refused_once_the_contract_lands(db_ready):
    """**والحارسُ يبين بطرفيه.** ما يُقبل على 0028 يُرفض على 0029.

    ولولا هذا الطرف لكان الفحصُ أعلاه يمرّ على قاعدةٍ بلا عقدٍ أصلًا، ولا
    يثبت أنّ التأجيل كان له موجب.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import SessionFactory, system_session

    async with system_session() as session:
        head = (await session.execute(text(
            "SELECT version_num FROM alembic_version"))).scalar_one()
    if head != "0029":
        pytest.skip(f"قاعدةُ الاختبارات عند {head}، والعقدُ يُفرض في 0029")

    async with SessionFactory() as session:
        member, _ = await _one_member_and_agreement(session.bind)

    with pytest.raises(IntegrityError) as caught:
        async with SessionFactory() as session, session.begin():
            await session.execute(text(OLD_MEMBER_CONSENT), {"member_id": member})
    assert "consent_has_a_method" in str(caught.value), (
        "رُفضت الكتابةُ لسببٍ آخر — فالفحصُ لا يثبت العقد")


def test_the_migration_chain_ends_at_the_contract():
    """السلسلةُ تنتهي بالعقد، ورأسٌ واحد."""
    contract = (MIGRATIONS / "0029_research_teams_consent_contract.py").read_text(
        encoding="utf-8")
    assert re.search(r'^revision = "0029"', contract, re.M)
    assert re.search(r'^down_revision = "0028"', contract, re.M)
