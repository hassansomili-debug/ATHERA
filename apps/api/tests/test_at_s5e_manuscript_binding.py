"""S5E-A — أساس ربط المخطوطة بأدلتها.

**السؤال الذي يحرسه هذا الملف:** هل يبقى في المنظومة **مفردةٌ واحدة** لأقسام
المخطوطة، وهل يستطيع كل ادعاء أن يقول من أين جاء؟

فالخطر هنا ليس عطبًا وظيفيًّا بل انحرافَ معرّفات: مفتاحٌ يُكتب بجانب سجلّه
بدل أن يُشتقّ منه. وقد كلّفنا هذا الصنف ثلاثة عوائق في S5D — وكان رابعًا
ينتظر: `outline.py` يُصدر `methods` و`literature`، والمفردات القانونية تقول
`method` و`literature_review`، و`manuscript_sections.section_key` عليه قيدٌ
بالثانية. فأول تحويل لهيكل إلى أقسام مخطوطة كانت القاعدة سترفضه.
"""
from __future__ import annotations

import pathlib
import uuid

import pytest

from athera_api.services.publishing import vocab
from tests.conftest import requires_db

REPO = pathlib.Path(__file__).resolve().parents[3]
MIGRATION = REPO / "infra" / "db" / "migrations" / "versions" / "0019_manuscript_evidence_binding.py"


def _migration_module():
    import importlib.util
    import sys
    import types

    sys.modules.setdefault("alembic", types.ModuleType("alembic")).op = None
    spec = importlib.util.spec_from_file_location("m0019", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ══════════ 1. مفردةٌ واحدة لأقسام المخطوطة ══════════

def test_every_outline_section_key_is_canonical():
    """الحارس المباشر للانحراف الذي وُجد قبل أن يقع."""
    from athera_api.services.planning import outline

    emitted = [spec.key for spec in outline.DEFAULT_SECTIONS]
    unknown = [key for key in emitted if key not in vocab.MANUSCRIPT_SECTIONS]
    assert unknown == [], f"outline emits section keys outside the vocabulary: {unknown}"


def test_the_old_aliases_are_gone_from_the_planning_package():
    """`methods` و`literature` لا يُكتبان مفتاحًا في مصدر التخطيط بعد اليوم."""
    import ast
    import inspect

    from athera_api.services.planning import outline

    tree = ast.parse(inspect.getsource(outline))
    literals = {node.value for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    for alias in ("methods", "literature"):
        assert alias not in literals, f"the alias {alias!r} survives in outline.py"


def test_a_non_canonical_section_key_cannot_be_constructed():
    """الصنف يُغلق عند الاستيراد لا عند الاستعمال — فينكسر البناء لا الإنتاج."""
    from athera_api.services.planning.outline import SectionSpec

    with pytest.raises(ValueError, match="MANUSCRIPT_SECTIONS"):
        SectionSpec("methods", "المنهجية", "Methods", "…", ())


def test_the_migration_and_the_vocabulary_never_drift():
    """الترحيل يحمل نسخته الحرفية عمدًا — والانحراف بينهما لا يُترك للحظّ.

    ترحيلٌ يستورد من التطبيق يكسر حين تتقدّم الشيفرة عليه؛ ونسخةٌ لا يحرسها
    شيء تفترق بأول تعديل. فالنسخة تبقى، ويحرسها هذا.
    """
    module = _migration_module()
    assert tuple(module.MANUSCRIPT_SECTIONS) == tuple(vocab.MANUSCRIPT_SECTIONS)
    assert tuple(module.SECTION_REVIEW_STATUSES) == tuple(vocab.SECTION_REVIEW_STATUSES)
    assert tuple(module.SUPPORT_LEVELS) == tuple(vocab.SUPPORT_LEVELS)


def test_every_rename_target_is_canonical_and_every_source_is_not():
    """خريطة التحويل تتّجه من خارج المفردات إلى داخلها — لا العكس ولا داخلها."""
    module = _migration_module()
    for old, new in module.OUTLINE_KEY_RENAMES.items():
        assert old not in vocab.MANUSCRIPT_SECTIONS, f"{old} is already canonical"
        assert new in vocab.MANUSCRIPT_SECTIONS, f"{new} is not canonical"


def test_the_decided_statuses_are_a_subset_of_the_review_statuses():
    assert vocab.SECTION_DECIDED_STATUSES <= set(vocab.SECTION_REVIEW_STATUSES)


def test_the_section_review_statuses_are_bilingual():
    for key, (ar, en) in vocab.SECTION_REVIEW_STATUSES.items():
        assert ar.strip() and en.strip(), key


# ══════════ 2. الكاتب العلمي: بلا أدوات، وسياقه يُمرَّر ══════════

def test_the_scientific_writer_is_registered_and_toolless():
    from athera_api.brain import agents

    spec = agents.get_agent("scientific_writer")
    assert spec.allowed_tools == frozenset(), "a free memory search escapes the consent fingerprint"
    assert spec.reads_memory == frozenset()
    assert "numbers_require_analysis_run" in spec.guards
    assert agents.BASE_GUARDS <= spec.guards


def test_the_writer_constraint_names_what_it_may_not_invent():
    from athera_api.brain import agents

    spec = agents.get_agent("scientific_writer")
    for forbidden in ("نتيجة", "رقم", "مرجع", "السببية"):
        assert forbidden in spec.constraint_ar, forbidden
    for forbidden in ("result", "reference", "causal"):
        assert forbidden in spec.constraint_en.lower(), forbidden


# ══════════ 3. القدرات الثلاث — ولا واحدة تأذن لأختها ══════════

def test_the_three_capabilities_are_distinct_and_all_capped_at_c2():
    from athera_api.services import consent

    capabilities = {consent.CAPABILITY, consent.PLANNING_CAPABILITY,
                    consent.DRAFTING_CAPABILITY}
    assert len(capabilities) == 3, "two capabilities collapsed into one name"
    assert set(consent.CAPABILITY_CEILING) == capabilities, "a capability has no declared ceiling"
    assert set(consent.CAPABILITY_CEILING.values()) == {"C2"}, "a capability exceeds C2"

    gates = {consent.GATE, consent.PLANNING_GATE, consent.DRAFTING_GATE}
    assert len(gates) == 3, "two capabilities share a gate code"

    kinds = {consent.OBJECT_TYPE, consent.PLANNING_OBJECT_TYPE,
             consent.DRAFTING_OBJECT_TYPE}
    assert len(kinds) == 3
    # الإذن يُعطى لصياغة **مخطوطة** بعينها لا لمشروع كامل.
    assert consent.DRAFTING_OBJECT_TYPE.startswith("manuscript.")


def test_the_global_ceiling_is_untouched():
    """السقف العام يبقى C1 — والاستثناءات مسمّاة لا مرفوعة."""
    from athera_api.config import Settings

    assert Settings().model_external_send_max_classification == "C1"


# ══════════ 4. السند بنيوي لا مصفوفة ══════════

def test_a_claim_binds_to_the_exact_analysis_output_not_merely_a_run():
    """«تشغيلةٌ في القسم» ليست سندًا لرقم؛ السند أن يكون الرقم في المخرَج."""
    from athera_api.models.publishing import ClaimAnalysisLink

    columns = set(ClaimAnalysisLink.__table__.columns.keys())
    assert "output_id" in columns
    assert "statistic_excerpt" in columns
    # ولا `run_id` مكرَّر: التشغيلة تُشتقّ من `analysis_outputs.run_id`.
    assert "run_id" not in columns, "a second source of truth for the run"

    target = ClaimAnalysisLink.__table__.c.output_id.foreign_keys.pop().target_fullname
    assert target == "analysis_outputs.id"


def test_the_evidence_behind_a_manuscript_claim_cannot_vanish_silently():
    from athera_api.models.publishing import ClaimMemoryLink

    fk = ClaimMemoryLink.__table__.c.memory_id.foreign_keys.pop()
    assert fk.target_fullname == "researcher_memories.id"
    assert fk.ondelete == "RESTRICT", "a memory backing a manuscript claim could disappear"


def test_the_section_claim_binding_is_relational():
    from athera_api.models.publishing import ManuscriptSectionClaim

    columns = ManuscriptSectionClaim.__table__.c
    assert columns.section_id.foreign_keys.pop().target_fullname == "manuscript_sections.id"
    assert columns.claim_id.foreign_keys.pop().target_fullname == "claims.id"


def test_no_parallel_draft_or_revision_domain_was_created():
    """الوعاء والتاريخ قائمان — ولا يُبنى بجانبهما ثانٍ."""
    from athera_api.models import publishing

    tables = {getattr(publishing, name).__tablename__
              for name in dir(publishing)
              if hasattr(getattr(publishing, name), "__tablename__")}
    for duplicate in ("manuscript_drafts", "manuscript_section_revisions"):
        assert duplicate not in tables, f"{duplicate} duplicates the existing domain"
    assert {"manuscripts", "manuscript_versions", "manuscript_sections"} <= tables


def test_the_manuscript_knows_its_opportunity_and_outline():
    from athera_api.models.publishing import Manuscript

    columns = Manuscript.__table__.c
    assert columns.opportunity_id.foreign_keys.pop().target_fullname == \
        "publication_opportunities.id"
    assert columns.outline_id.foreign_keys.pop().target_fullname == "manuscript_outlines.id"
    # قابلان للعدم: مخطوطات ما قبل S5E لا فرصة لها ولا هيكل.
    assert columns.opportunity_id.nullable and columns.outline_id.nullable


# ══════════ 5. القاعدة الحيّة ══════════

@requires_db
@pytest.mark.asyncio
async def test_the_live_schema_carries_one_section_vocabulary(db_ready):
    """القيد في القاعدة يقبل `method` ويرفض `methods` — والمصدر واحد."""
    from sqlalchemy import text

    from athera_api.db import system_session

    # يُبحث عنه **بجدوله ومحتواه لا باسمٍ يُخمَّن**: اسم القيد تفصيلُ ترحيل،
    # واختبارٌ يخمّنه يقيس اسمه لا سلوكه.
    async with system_session() as session:
        definitions = (await session.execute(text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = 'manuscript_sections'::regclass AND contype = 'c'"
        ))).scalars().all()
    matches = [d for d in definitions if "section_key" in d]
    assert matches, f"no CHECK constrains section_key: {definitions}"
    definition = matches[0]
    assert "'method'" in definition
    assert "'literature_review'" in definition
    assert "'methods'" not in definition
    for key in vocab.MANUSCRIPT_SECTIONS:
        assert f"'{key}'" in definition, key


@requires_db
@pytest.mark.asyncio
async def test_the_new_tables_are_isolated_and_forced(db_ready):
    from sqlalchemy import text

    from athera_api.db import system_session

    module = _migration_module()
    async with system_session() as session:
        rows = (await session.execute(text(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = ANY(:names)"
        ), {"names": list(module.NEW_TABLES)})).all()
    assert len(rows) == len(module.NEW_TABLES), "a table from 0019 is missing"
    for name, enabled, forced in rows:
        assert enabled and forced, f"{name} is not isolated"


@requires_db
@pytest.mark.asyncio
async def test_a_human_review_decision_cannot_exist_without_an_actor(two_tenants):
    """القاعدة ترفض «معتمَد» بلا مَن اعتمد ومتى — لا الكود وحده."""
    from sqlalchemy import text

    from athera_api.db import tenant_session

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    manuscript_id, version_id = await _seed_manuscript(tid, uid)

    async with tenant_session(tid, uid) as session:
        await session.execute(text(
            "INSERT INTO manuscript_sections (tenant_id, version_id, section_key, text_ar) "
            "VALUES (:t, :v, 'method', 'نصّ')"), {"t": str(tid), "v": str(version_id)})

    with pytest.raises(Exception):
        async with tenant_session(tid, uid) as session:
            await session.execute(text(
                "UPDATE manuscript_sections SET review_status = 'approved' "
                "WHERE version_id = :v"), {"v": str(version_id)})

    # وبفاعلٍ ووقت تمرّ.
    async with tenant_session(tid, uid) as session:
        await session.execute(text(
            "UPDATE manuscript_sections SET review_status = 'approved', "
            "reviewed_by = :u, reviewed_at = now() WHERE version_id = :v"),
            {"u": str(uid), "v": str(version_id)})
    assert manuscript_id


async def _seed_manuscript(tid, uid):
    """مخطوطة ونسخة — عبر النماذج القائمة لا بجدول جديد."""
    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ResearchProject
    from athera_api.models.publishing import Manuscript, ManuscriptVersion

    async with tenant_session(tid, uid) as session:
        project = ResearchProject(tenant_id=tid, working_title_ar="مشروع مخطوطة")
        session.add(project)
        await session.flush()
        row = Manuscript(tenant_id=tid, project_id=project.id,
                         title_ar="مخطوطة اختبار", language="ar", status="draft")
        session.add(row)
        await session.flush()
        version = ManuscriptVersion(
            tenant_id=tid, manuscript_id=row.id, version_label=f"v{uuid.uuid4().hex[:6]}",
            created_by=uid, change_reason_ar="إنشاء أولي")
        session.add(version)
        await session.flush()
        return row.id, version.id


# ══════════ 6. سلامة المراجعة عبر النسخ (§17) ══════════

def test_applying_a_patch_keeps_untouched_approvals_and_resets_the_rewritten_one():
    """نسخةٌ جديدة ليست بدايةً من الصفر — ولا ترحيلًا لاعتمادٍ على نصٍّ رُقّع."""
    import inspect

    from athera_api.routers import publishing

    source = inspect.getsource(publishing.apply_patch)
    assert 'review_status="needs_review" if rewritten else section.review_status' in source
    assert "reviewed_by=None if rewritten else section.reviewed_by" in source
    assert "reviewed_at=None if rewritten else section.reviewed_at" in source
    # وبصمة السياق لا تُنقل إلى نصٍّ آخر: الإذن كان على تلك الأدلة لذلك النص.
    assert "None if rewritten else section.drafting_context_fingerprint" in source


def test_the_revision_history_is_manuscript_versions_not_a_second_table():
    """`ManuscriptVersion` هو نظام المراجعات — ولا يُبنى بجانبه ثانٍ."""
    import inspect

    from athera_api.models.publishing import ManuscriptVersion
    from athera_api.routers import publishing

    columns = ManuscriptVersion.__table__.c
    for required in ("version_label", "created_by", "change_reason_ar", "supersedes_id"):
        assert required in columns, required

    # وتطبيق الرقعة يمرّ به: نسخةٌ جديدة تخلف سابقتها بسلسلة `supersedes`.
    source = inspect.getsource(publishing.apply_patch)
    assert "supersedes_id=old_version.id" in source


def test_the_manuscript_listing_reads_the_version_label_from_the_version():
    """`Manuscript` لا يحمل وسم النسخة — وقراءته منه ترفع خطأً على كل صفّ.

    كان المسار يقرأ `r.current_version_label`، وهي خاصية لا وجود لها؛ فكان
    يردّ 500 لكل مستأجر يملك مخطوطة. ولم يظهر لأن لا اختبار سرد مخطوطةً
    موجودة — والفحص هنا بنيوي كي لا يعود بصمت.
    """
    import inspect

    from athera_api.models.publishing import Manuscript
    from athera_api.routers import publishing

    import ast

    assert not hasattr(Manuscript, "current_version_label")
    # الشرح يذكر الخطأ ليقول إنه لا يقع — فيُفحص الكود لا التعليق.
    tree = ast.parse(inspect.getsource(publishing.list_manuscripts).strip())
    code = ast.unparse(tree)
    assert "r.current_version_label" not in code
    assert "ManuscriptVersion.version_label" in code
