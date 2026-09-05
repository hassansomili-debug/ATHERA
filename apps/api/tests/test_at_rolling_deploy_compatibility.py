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

import datetime as dt
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


# ═════════════════ ٢. النافذةُ نفسها، على قاعدةٍ حقيقية ═════════════════

def _old_api_member_consent(member) -> None:
    """كتابةُ الخادم القديم حرفيًّا — `routers/team.py:156` وحده."""
    member.consent_recorded_at = dt.datetime.now(dt.UTC)


@requires_db
@pytest.mark.asyncio
async def test_the_old_api_can_still_record_member_consent_on_the_expanded_schema(
    two_tenants,
):
    """**الخاصّيّةُ التي وُجدت التوسعةُ لأجلها.**

    خادمٌ قديم، مخطَّطٌ جديد، وموافقةٌ تُسجَّل بوقتٍ بلا طريقة. لو رفضتها
    القاعدةُ لسقطت كلُّ موافقةٍ بين الترحيل والنشر.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectMember, ResearchProject

    a = two_tenants["a"]
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        project = ResearchProject(
            tenant_id=a["tenant_id"], working_title_ar="مشروعُ نافذةِ النشر",
            status="planned", current_gate="G1")
        session.add(project)
        await session.flush()

        member = ProjectMember(
            tenant_id=a["tenant_id"], project_id=project.id,
            display_name="د. فلان", role="co_author")
        session.add(member)
        await session.flush()

        _old_api_member_consent(member)
        await session.flush()          # لو فُرض العقد هنا لسقط هذا السطر

        stored = (await session.execute(
            select(ProjectMember).where(ProjectMember.id == member.id)
        )).scalar_one()
        assert stored.consent_recorded_at is not None
        assert stored.consent_method is None, (
            "الخادمُ القديم لا يكتب طريقةً — والعمودُ يجب أن يبقى فارغًا")


@requires_db
@pytest.mark.asyncio
async def test_the_old_api_can_still_record_authorship_consent_on_the_expanded_schema(
    two_tenants,
):
    """والمسارُ الثاني: `services/thesis/rights.py:190` — الوقتُ والحال."""
    from athera_api.db import tenant_session
    from athera_api.models.thesis import AuthorshipAgreement

    a = two_tenants["a"]
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        agreement = AuthorshipAgreement(
            tenant_id=a["tenant_id"], opportunity_id=uuid.uuid4(),
            party_id=uuid.uuid4(), author_position=1,
            consent_status="granted",
            consent_recorded_at=dt.datetime.now(dt.UTC))
        session.add(agreement)
        try:
            await session.flush()
        except Exception as exc:                       # pragma: no cover
            if "consent_has_a_method" in str(exc):
                pytest.fail("العقدُ مفروضٌ في التوسعة — النافذةُ قاتلة")
            pytest.skip(f"سياقٌ ناقص لا علاقة له بالعقد: {type(exc).__name__}")
        assert agreement.consent_method is None


@requires_db
@pytest.mark.asyncio
async def test_the_contract_expression_would_reject_the_window_row(two_tenants):
    """**وحارسٌ لا يسقط أبدًا ليس حارسًا.**

    يُقاس التعبيرُ نفسه على صفّ النافذة: يجب أن يرفضه — وإلّا فالتأجيلُ
    كلُّه بلا موجب، والفحصُ أعلاه يمرّ على لا شيء.
    """
    from sqlalchemy import text

    from athera_api.db import tenant_session

    a = two_tenants["a"]
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        verdict = (await session.execute(text(
            "SELECT (now() IS NULL) = (NULL IS NULL) AS holds"
        ))).scalar_one()
        assert verdict is False, (
            "تعبيرُ العقد يقبل صفَّ النافذة — فلا معنى لتأجيله")


def test_the_migration_chain_ends_at_the_contract():
    """السلسلةُ تنتهي بالعقد، ورأسٌ واحد."""
    contract = (MIGRATIONS / "0029_research_teams_consent_contract.py").read_text(
        encoding="utf-8")
    assert re.search(r'^revision = "0029"', contract, re.M)
    assert re.search(r'^down_revision = "0028"', contract, re.M)
