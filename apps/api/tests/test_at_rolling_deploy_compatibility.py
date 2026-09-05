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

# **وقاعدةُ نافذة 0028 لم تعد تُبنى، فذهب فحصُها معها.**
#
# كان هنا فحصٌ يشغّل كتابةَ v88 على قاعدةٍ عند 0028 بعينها. وقد أُغلقت تلك
# النافذة: الإنتاج عند 0029، والموجةُ 1.1 تُرحَّل قبل أن تُنشر — فلا طورَ
# يخدم فيه جديدٌ مخطَّطًا أقدم. **وفحصٌ لا يُشغَّل أسوأ من فحصٍ غائب**:
# الغائبُ يُطلب، والموجودُ المتخطَّى يُحسب حراسةً قائمة. فحُذف، وحلّ محلَّه
# برهانُ النافذة الباقية في القسم الثالث: v88 على مخطَّط 0030.

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
    # **وسياقُ المستأجر يُضبط في كل معاملة.** `set_config(..., true)` محلّيٌّ
    # بالمعاملة؛ فمن ضبطه في معاملة الزرع وحدها كتب في التاليات بلا سياق،
    # فرشّحت RLS كلَّ شيء — **بلا خطأ**. تُحدَّث صفرُ صفوف، ولا يُفحص قيدٌ
    # واحد، ويخضرّ الفحصُ على لا شيء. وهو العطبُ الذي أسقط عشرة فحوصٍ في
    # المسار «هـ» من قبل.
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
        # فرصةٌ حقيقيّة: المفتاحُ الأجنبيّ يطلب صفًّا قائمًا، و**لا فرصةَ بلا
        # مصدر** (`ck_publication_opportunities_has_source`) — فتُنسب إلى
        # المشروع المزروع أعلاه لا إلى العدم.
        opportunity = uuid.uuid4()
        await conn.execute(text(
            "INSERT INTO publication_opportunities (id, tenant_id, project_id, "
            "opportunity_kind, paper_kind, working_title_ar) "
            "VALUES (:i, :t, :p, 'independent_question', 'extraction', "
            "'فرصةُ النافذة')"),
            {"i": opportunity, "t": tenant, "p": project})
        # وطرفُ التأليف صفٌّ قائم كذلك — و`party_kind` من مفرداته
        # المسجَّلة (`person`/`organization`) لا من عندي.
        party = uuid.uuid4()
        await conn.execute(text(
            "INSERT INTO authorship_parties (id, tenant_id, party_kind, "
            "display_name) VALUES (:i, :t, 'person', 'د. فلان')"),
            {"i": party, "t": tenant})
        await conn.execute(text(
            "INSERT INTO authorship_agreements (id, tenant_id, opportunity_id, "
            "party_id, author_position, consent_status) "
            "VALUES (:i, :t, :o, :y, 1, 'pending')"),
            {"i": agreement, "t": tenant, "o": opportunity, "y": party})
    return tenant, member, agreement


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
    # **والشرطُ «بلغت 0029» لا «هي 0029» بعينها.**
    #
    # وكان `head != "0029"` — فأوّلُ ترحيلٍ بعده يحوّل هذين الفحصين إلى
    # تخطٍّ صامت، ويبقى العقدُ مفروضًا في القاعدة بلا حارسٍ يشهد له. وقد
    # وقع ذلك فعلًا عند 0030: القيدُ قائمٌ ولا يمسّه الترحيلُ الجديد، ولا
    # سببَ لإسقاط الشهادة عليه.
    if head < "0029":
        pytest.skip(f"قاعدةُ الاختبارات عند {head}، والعقدُ يُفرض في 0029")

    async with SessionFactory() as session:
        tenant, member, _ = await _one_member_and_agreement(session.bind)

    with pytest.raises(IntegrityError) as caught:
        async with SessionFactory() as session, session.begin():
            await session.execute(text(
                "SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)})
            await session.execute(text(OLD_MEMBER_CONSENT), {"member_id": member})
    assert "ck_project_members_consent_has_a_method" in str(caught.value), (
        "رُفضت الكتابةُ لسببٍ آخر — فالفحصُ لا يثبت العقد")


@requires_db
@pytest.mark.asyncio
async def test_the_old_authorship_write_is_also_refused_on_the_contract(db_ready):
    """**والمسارُ الثاني يُثبت وحده — لا يُستنتج من أخيه.**

    ولو جُمعا في معاملةٍ واحدة لأبطل أوّلُ `IntegrityError` ما بعده: تُجهض
    المعاملة، فيصير الفحصُ الثاني يقيس معاملةً ميّتة لا قيدًا. فلكلٍّ
    معاملتُه، ولكلٍّ زرعُه.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import SessionFactory, system_session

    async with system_session() as session:
        head = (await session.execute(text(
            "SELECT version_num FROM alembic_version"))).scalar_one()
    # **والشرطُ «بلغت 0029» لا «هي 0029» بعينها.**
    #
    # وكان `head != "0029"` — فأوّلُ ترحيلٍ بعده يحوّل هذين الفحصين إلى
    # تخطٍّ صامت، ويبقى العقدُ مفروضًا في القاعدة بلا حارسٍ يشهد له. وقد
    # وقع ذلك فعلًا عند 0030: القيدُ قائمٌ ولا يمسّه الترحيلُ الجديد، ولا
    # سببَ لإسقاط الشهادة عليه.
    if head < "0029":
        pytest.skip(f"قاعدةُ الاختبارات عند {head}، والعقدُ يُفرض في 0029")

    async with SessionFactory() as session:
        tenant, _, agreement = await _one_member_and_agreement(session.bind)

    with pytest.raises(IntegrityError) as caught:
        async with SessionFactory() as session, session.begin():
            await session.execute(text(
                "SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)})
            await session.execute(text(OLD_AGREEMENT_CONSENT),
                                  {"agreement_id": agreement})
    assert "ck_authorship_agreements_consent_has_a_method" in str(caught.value), (
        f"رُفض اتفاقُ التأليف لسببٍ آخر: {str(caught.value)[:160]}")


def test_the_contract_sits_directly_on_the_expand_migration():
    """**العقدُ يلي التوسعةَ مباشرةً** — ولا ترحيلَ بينهما.

    وترحيلٌ يُدسّ بين 0028 و0029 يفتح نافذةً ثالثة لا يصفها أحد. أمّا ما
    يأتي **بعد** 0029 فلا يعني هذا الفحص: السلسلة تنمو، والمهمّ أن يبقى
    العقدُ لاصقًا بتوسعته. (وكان اسمُ هذا الفحص يقول إنّ السلسلة تنتهي عند
    العقد، وقد صار ذلك غير صحيح عند 0030 — فيُقال ما يُفحَص لا ما كان.)
    """
    contract = (MIGRATIONS / "0029_research_teams_consent_contract.py").read_text(
        encoding="utf-8")
    assert re.search(r'^revision = "0029"', contract, re.M)
    assert re.search(r'^down_revision = "0028"', contract, re.M)


# ═════════════════ ٣. النافذةُ الجديدة: OLD API + 0030 ═════════════════
#
# **ترتيبُ هذه الموجة معكوسٌ عن سابقتها، فالخاصّيّةُ المطلوبة غيرُها.**
#
# الموجةُ الأولى نُشرت على مخطَّطٍ مُوسَّع ثمّ عُوقد عليه: تُرحَّل إلى 0028،
# ثمّ يُنشر الخادمُ الجديد وهو عليها، ثمّ 0029. فكانت النافذةُ **خادمٌ جديد
# على مخطَّطٍ أقدم**، وذاك ما أثبته `test_at_wave1_on_expand_window`.
#
# والموجةُ 1.1 لا تحتمل ذلك: `models/thesis.py` يُعلن `archived_at` و
# `archived_by`، فـSQLAlchemy تختارهما في كلّ قراءةٍ للرسائل. **فشيفرتُها
# لا تخدم مخطَّطًا دون 0030 إطلاقًا**، ولا يُصلح ذلك تأجيلُ قيد. فالترتيبُ
# **ترحيلٌ أوّلًا ثمّ نشر**: 0029 → 0030، ثمّ تُنشر.
#
# فالنافذةُ الباقية — وهي الحقيقيّة — بين الترحيل والنشر: **الخادمُ القديم
# (v88) على مخطَّط 0030**. وهي التي تُثبَت هنا.
#
# ولا تُستعمل نماذجُ الموجة 1.1 عمدًا — القاعدةُ نفسها المكتوبة في القسم
# الثاني: هي تحمل عمودين لم يكن v88 يعرفهما، فالكتابةُ بها ليست كتابته.
# والقائمةُ أدناه هي أعمدةُ `Thesis` في `origin/main` حرفًا بحرف.

#: أعمدةُ `theses` كما يعرفها خادمُ الموجة الأولى (v88) — لا أكثر.
V88_THESIS_COLUMNS = (
    "id", "tenant_id", "title_ar", "title_en", "degree", "defended_on",
    "data_collected_on", "institution_ar", "file_id", "rights_basis", "parsed_at",
    "existing_publications", "processing_state", "processing_state_changed_at",
    "processing_attempts", "failure_code", "failure_detail", "text_layer_state",
    "ocr_state", "opportunities_mined_at",
)

#: عبارةُ الرفع كما يُصدرها v88: قائمةُ أعمدةٍ صريحة يولّدها SQLAlchemy من
#: نموذجه — **ولا ذكرَ فيها للعمودين الجديدين**.
V88_INSERT_THESIS = (
    "INSERT INTO theses (id, tenant_id, title_ar, title_en, degree, file_id, "
    "rights_basis, processing_state, processing_attempts, text_layer_state, "
    "ocr_state, created_at, updated_at) "
    "VALUES (:id, :tenant, :title, NULL, 'masters', NULL, NULL, 'uploaded', 0, "
    "'not_checked', 'unavailable', now(), now())")

#: عبارةُ `processing.mark` كما يُصدرها v88.
V88_MARK_STATE = (
    "UPDATE theses SET processing_state = :state, processing_state_changed_at = now(), "
    "failure_code = :code, failure_detail = :detail, text_layer_state = :layer "
    "WHERE theses.tenant_id = :tenant AND theses.id = :id")

#: عبارةُ `claim_for_processing` كما يُصدرها v88 — الحجزُ شرطٌ في الكتابة.
V88_CLAIM = (
    "UPDATE theses SET processing_state = 'queued', processing_state_changed_at = now(), "
    "processing_attempts = theses.processing_attempts + 1, failure_code = NULL, "
    "failure_detail = NULL "
    "WHERE theses.id = :id AND theses.tenant_id = :tenant "
    "AND theses.processing_state IN ('uploaded', 'awaiting_consent', "
    "'ready_for_review', 'completed', 'failed')")


def test_the_v88_replay_uses_only_columns_that_v88_knows():
    """**حارسُ الحارس.** عبارةٌ تُعيد تشغيل كتابةَ v88 وتذكر عمودًا لا يعرفه
    ليست كتابته — وتخضرّ على شيءٍ لم يقع في الإنتاج قطّ.
    """
    for statement in (V88_INSERT_THESIS, V88_MARK_STATE, V88_CLAIM):
        assert "archived_at" not in statement, statement
        assert "archived_by" not in statement, statement
    # وقائمةُ الأعمدة هي قائمةُ `origin/main` — لا قائمةُ هذا الفرع.
    assert "archived_at" not in V88_THESIS_COLUMNS
    assert "archived_by" not in V88_THESIS_COLUMNS
    assert len(V88_THESIS_COLUMNS) == 20  # ١٩ عمودًا + `tenant_id` من الأساس


@requires_db
@pytest.mark.asyncio
async def test_the_old_api_can_still_write_a_thesis_on_the_archive_schema(db_ready):
    """**الخاصّيّةُ التي وُجد الترحيل 0030 محتاجًا إليها — OLD API + 0030.**

    بين ترحيل الإنتاج ونشر الموجة 1.1 يخدم خادمُ v88 مخطَّطًا يحمل عمودين
    لا يعرفهما. ولو كان أحدُهما إلزاميًّا أو ذا افتراضٍ كاتب، لسقط **كلُّ
    رفعِ رسالةٍ** في تلك النافذة بخمسمئة.

    **و`rowcount` هو الشاهد، لا غيابُ الاستثناء.** سياقُ المستأجر محلّيٌّ
    بالمعاملة؛ فمن نسيه رشّحت RLS كتابته إلى صفر صفوف **بلا خطأ** — فيخضرّ
    الفحصُ على لا شيء. وهو العطبُ الذي أسقط عشرة فحوصٍ في المسار «هـ»،
    ومكتوبٌ في القسم الثاني من هذا الملفّ.
    """
    from sqlalchemy import text

    from athera_api.db import SessionFactory, system_session

    async with system_session() as session:
        head = (await session.execute(
            text("SELECT version_num FROM alembic_version"))).scalar_one()
    if head < "0030":
        pytest.skip(f"قاعدةُ الاختبارات عند {head}، والعمودان يُضافان في 0030")

    tenant, thesis = uuid.uuid4(), uuid.uuid4()

    async with SessionFactory() as session, session.begin():
        await session.execute(text(
            "SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)})
        await session.execute(text(
            "INSERT INTO tenants (id, slug, name_ar, name_en) "
            "VALUES (:i, :s, 'نافذةُ الأرشفة', 'Archive window')"),
            {"i": tenant, "s": f"arch-{tenant.hex[:8]}"})

        # ١ — الرفع، بعبارة v88 حرفيًّا.
        inserted = await session.execute(
            text(V88_INSERT_THESIS),
            {"id": thesis, "tenant": tenant, "title": "رسالةٌ كتبها الخادمُ القديم"})
        assert inserted.rowcount == 1, "رفعُ v88 كُتب صفرَ صفوف — RLS رشّحته بصمت"

    # ٢ — تثبيتُ الحال، بعبارة v88 حرفيًّا. ومعاملةٌ جديدة: السياقُ يُضبط
    #     فيها من جديد، وهو بيتُ الدرس.
    async with SessionFactory() as session, session.begin():
        await session.execute(text(
            "SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)})
        marked = await session.execute(text(V88_MARK_STATE), {
            "state": "failed", "code": "parse_failed", "detail": "TimeoutError",
            "layer": "not_checked", "tenant": tenant, "id": thesis})
        assert marked.rowcount == 1, "تثبيتُ حالِ v88 كُتب صفرَ صفوف"

    # ٣ — والحجزُ للمعالجة، وهو الكتابةُ الثالثة التي يُصدرها v88.
    async with SessionFactory() as session, session.begin():
        await session.execute(text(
            "SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)})
        claimed = await session.execute(text(V88_CLAIM), {"id": thesis, "tenant": tenant})
        assert claimed.rowcount == 1, "حجزُ v88 كُتب صفرَ صفوف"

    # **والعمودان الجديدان بقيا فارغين** — ومعناهما «غير مؤرشَفة»، وهي
    # الحالُ الصحيحة لكلّ ما يكتبه خادمٌ لا يعرفهما.
    async with SessionFactory() as session, session.begin():
        await session.execute(text(
            "SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)})
        row = (await session.execute(text(
            "SELECT archived_at, archived_by, processing_state, processing_attempts "
            "FROM theses WHERE id = :i"), {"i": thesis})).one()

    assert row.archived_at is None, "عمودٌ جديد كُتب فيه ما لم يطلبه الخادمُ القديم"
    assert row.archived_by is None
    assert row.processing_state == "queued", "الحجزُ لم يقع فعلًا"
    assert row.processing_attempts == 1


@requires_db
@pytest.mark.asyncio
async def test_the_archive_constraint_never_refuses_an_old_api_write(db_ready):
    """**والقيدُ الجديد لا يقف في وجه كتابةٍ قديمة.**

    `ck_theses_archive_is_named` يقرن الوقتَ بالفاعل. وكتابةُ v88 لا تذكر
    أيًّا منهما، فيبقيان `NULL` معًا — ويتحقّق القيد. ولو كُتب أحدُهما
    وحده لسقطت الكتابة؛ وهذا يُثبت أنّ ذلك لا يقع من طريق v88.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import SessionFactory, system_session

    async with system_session() as session:
        head = (await session.execute(
            text("SELECT version_num FROM alembic_version"))).scalar_one()
    if head < "0030":
        pytest.skip(f"قاعدةُ الاختبارات عند {head}، والقيدُ يُضاف في 0030")

    tenant, thesis = uuid.uuid4(), uuid.uuid4()
    async with SessionFactory() as session, session.begin():
        await session.execute(text(
            "SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)})
        await session.execute(text(
            "INSERT INTO tenants (id, slug, name_ar, name_en) "
            "VALUES (:i, :s, 'قيدُ الأرشفة', 'Archive constraint')"),
            {"i": tenant, "s": f"ack-{tenant.hex[:8]}"})
        await session.execute(text(V88_INSERT_THESIS), {
            "id": thesis, "tenant": tenant, "title": "رسالةٌ للقيد"})

    # **والحارسُ يبين بطرفيه**: نصفُ وسمٍ يُرفض، فالقيد قائمٌ فعلًا وليس
    # الفحصُ يمرّ لأنّ لا قيدَ هناك.
    with pytest.raises(IntegrityError) as caught:
        async with SessionFactory() as session, session.begin():
            await session.execute(text(
                "SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)})
            await session.execute(text(
                "UPDATE theses SET archived_at = now() WHERE id = :i"), {"i": thesis})
    assert "ck_theses_archive_is_named" in str(caught.value), (
        f"رُفض نصفُ الوسم لسببٍ آخر: {str(caught.value)[:160]}")
