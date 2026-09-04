"""إدارة المشروع البحثي | Research project management (PUBRIVA, Wave1-B).

**المقياس هنا مقلوب أيضًا**: لا يُقاس هذا المسار بما يعرضه، بل بما يرفض
أن يقوله. فلوحُ مهامّ يقول «٧٣٪ مكتمل» ويقول «أنت في مرحلة التحليل» ويضع
في قائمتك عشر مهامّ لم تطلبها — وثلاثتها كذب في منصّةٍ علمية.

فيُثبت هنا عشرة:

١) **لا نسبة في أيّ عقدٍ يخرج من هذه الوحدة** — ولا حقلَ عشريّ فيها أصلًا.
٢) **المرحلة أربع حقائق لا واحدة**: حاليّة · تاريخ · مقترَح · اعتماد باحث.
٣) **المنصّة لا تستطيع ادّعاء مرحلة** — `confirmed_by` غير قابلٍ للفراغ.
٤) **الاقتراح يحمل سنده أو يمتنع**، ولا يُقترح فوق مَعْلَمٍ لم يقع.
٥) **دورة الحياة ليست خطًّا**: العودة إلى المنهجية بعد التحليل تُسجَّل.
٦) **الاقتراح لا يصير تكليفًا** — والقاعدة نفسها ترفضه بلا قبولٍ منسوب.
٧) **الإتمام فعلُ إنسان** لا أثرُ زيارةِ صفحة.
٨) **العزل مستأجرَين وبحثَين** — والثاني عطبٌ وقع في هذا المنتج من قبل.
٩) **عددُ العبارات ثابت** — والخدمة في سنغافورة والقاعدة في مومباي.
١٠) **الإتلاف الدائم يُعاين ثمّ يُوقَف**، ولا يُتلَف نسبٌ علميّ على تخمين.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import pathlib
import re
import uuid

import pytest

from tests.conftest import requires_db

REPO = pathlib.Path(__file__).resolve().parents[3]
API = REPO / "apps" / "api" / "athera_api"
WEB = REPO / "apps" / "web"
MIGRATION = (REPO / "infra" / "db" / "migrations" / "versions"
             / "0026_project_management.py")
SCREEN = WEB / "src" / "app" / "[locale]" / "portfolio" / "[projectId]"
PAGES = ("plan", "tasks", "timeline")
REQUESTS_DOC = REPO / "docs" / "integration" / "track-b-requests.md"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _migration_text() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _migration_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("_migration_0026", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ═════════════════════ ١. الترحيل ٠٠٢٦ ═════════════════════

def test_the_migration_owns_0026_and_follows_0025():
    """**رقمٌ واحد لا يحمله ترحيلان.** ولو حمله اثنان لصار لألمبيك رأسان."""
    module = _migration_module()
    assert module.revision == "0026"
    assert module.down_revision == "0025"


def test_the_migration_is_additive_and_destroys_nothing_on_the_way_up():
    text = _migration_text()
    upgrade = text.split("def upgrade()")[1].split("def downgrade()")[0]
    assert "drop_table" not in upgrade
    assert "drop_column" not in upgrade


def test_the_migration_forces_row_level_security_not_merely_enables_it():
    """`ENABLE` وحدها تترك مالك الجدول يتجاوز سياساته.

    و«جدول مهامّ» ليس استثناءً من ADR-0002: عناوين مهامّ الباحث تصف ما
    ينوي فعله بورقته، وهي من أخصّ ما في المنصّة.
    """
    text = _migration_text()
    module = _migration_module()
    assert len(module.NEW_TABLES) == 4
    assert "for table in NEW_TABLES:" in text
    assert "ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in text
    assert "ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in text
    assert "tenant_id = app_current_tenant()" in text
    assert "WITH CHECK (tenant_id = app_current_tenant())" in text
    assert "TO athera_app" in text

    # ولا جدولَ في النموذج خارج القائمة التي تُفعَّل عليها السياسة.
    from athera_api.models import project_management as model

    tables = {value.__tablename__ for value in vars(model).values()
              if hasattr(value, "__tablename__")}
    assert tables == set(module.NEW_TABLES)


def test_the_migration_indexes_the_reads_the_screens_actually_make():
    text = _migration_text()
    for index in ("ix_project_stage_events_project", "ix_project_tasks_project",
                  "ix_project_tasks_due", "ix_project_milestones_project"):
        assert index in text, f"قراءةٌ معروضة بلا فهرس: {index}"


def test_the_model_and_the_migration_share_one_vocabulary():
    """مفردةٌ تُكتب بجانب سجلّها تفترق عنه — وهو الخطأ المتكرر هنا."""
    module = _migration_module()
    from athera_api.models import project_management as model

    assert tuple(module.STAGES) == tuple(model.STAGES)
    assert tuple(module.TASK_STATUSES) == tuple(model.TASK_STATUSES)
    assert tuple(module.TASK_SOURCES) == tuple(model.TASK_SOURCES)
    assert tuple(module.TASK_PRIORITIES) == tuple(model.TASK_PRIORITIES)
    assert tuple(module.MILESTONES) == tuple(model.MILESTONES)
    assert tuple(module.SYSTEM_TASK_SOURCES) == tuple(model.SYSTEM_TASK_SOURCES)


def test_the_twelve_stages_and_eleven_milestones_are_exactly_the_agreed_ones():
    from athera_api.models.project_management import MILESTONES, STAGES

    assert STAGES == (
        "idea", "literature_discovery", "gap_problem", "design_methodology",
        "data_preparation_collection", "analysis", "scientific_writing",
        "scientific_review", "journal_selection", "submission",
        "peer_review_revision", "published")
    assert MILESTONES == (
        "idea_approved", "literature_review_completed", "gap_approved",
        "methodology_approved", "data_ready", "analysis_completed",
        "manuscript_ready", "journal_selected", "submitted",
        "review_response_completed", "published")


def test_the_task_statuses_are_six_and_not_twenty():
    """**حالٌ ثانيةٌ تعني ما لحالٍ اسمٌ** هي أول طريقٍ إلى تقريرين لا يتفقان."""
    from athera_api.models.project_management import TASK_STATUSES

    assert TASK_STATUSES == ("not_started", "in_progress", "awaiting_review",
                             "needs_decision", "blocked", "completed")


def test_the_migration_makes_same_tenant_cross_project_assignment_structural():
    """**RLS لا تحمي بين بحثين.** فالحارس مفتاحٌ مركّب لا شرطٌ في الخدمة."""
    text = _migration_text()
    assert 'uq_project_members_project_scoped' in text
    assert '["assignee_member_id", "project_id"]' in text
    assert '["project_members.id", "project_members.project_id"]' in text


def test_the_database_itself_forbids_a_suggestion_that_nobody_accepted():
    """الحارسُ في القاعدة لا في الخدمة — فلا يلتفّ عليه مسارٌ ثانٍ يُكتب لاحقًا.

    **والشرط يُقرأ من النموذج لا من نصّ الترحيل**: النصّ يُلفّ على أسطر،
    فيصير الفحص عليه فحصًا لتنسيقٍ لا لشرط. والنموذج يحمل القيد مُجمَّعًا.
    """
    from athera_api.models.project_management import ProjectTask

    # والاسمُ في النموذج مسبوقٌ باصطلاح التسمية (`ck_project_tasks_…`)،
    # فيُطابَق بالنهاية لا بالمساواة.
    clause = next(
        str(c.sqltext) for c in ProjectTask.__table__.constraints
        if str(getattr(c, "name", "")).endswith(
            "a_suggestion_becomes_a_task_only_when_accepted"))
    condensed = " ".join(clause.split())
    assert condensed == (
        "NOT suggested_by_system"
        " OR (accepted_by IS NOT NULL AND accepted_at IS NOT NULL)")
    # وهو نفسه في الترحيل — والاسم يكفي شاهدًا على وجوده هناك.
    assert "a_suggestion_becomes_a_task_only_when_accepted" in _migration_text()


def test_the_database_itself_forbids_a_milestone_completed_by_nobody():
    text = _migration_text()
    assert "(completed_at IS NULL) = (completed_by IS NULL)" in text


def test_the_stage_history_cannot_hold_a_row_the_platform_wrote_about_itself():
    """`confirmed_by NOT NULL` هو ما يمنع المنصّة من ادّعاء مرحلة.

    **ويُقرأ من الجدول لا من نصّ الترحيل**: النصّ يقول ما كُتب، والجدول
    يقول ما سيقع في القاعدة — وهو المقصود.
    """
    from athera_api.models.project_management import ProjectStageEvent

    column = ProjectStageEvent.__table__.columns["confirmed_by"]
    assert column.nullable is False, "سطرٌ في سجلّ المراحل بلا صاحب"
    # ولا قيمة افتراضية تملأ الفراغ عن الإنسان.
    assert column.default is None and column.server_default is None


def test_no_ordering_constraint_forces_the_lifecycle_to_be_a_straight_line():
    """**العودة إلى المنهجية بعد التحليل صوابٌ علميّ**، فلا قيد يمنعها."""
    from athera_api.models.project_management import ProjectStageEvent

    clauses = " ".join(
        str(getattr(c, "sqltext", "")) for c in ProjectStageEvent.__table__.constraints)
    for forbidden in ("from_stage <", "to_stage >", "position(", "array_position"):
        assert forbidden not in clauses, f"قيدٌ يفرض ترتيبًا: {forbidden}"


def test_the_downgrade_refuses_to_erase_a_human_confirmation():
    text = _migration_text()
    down = text.split("def downgrade()")[1]
    assert "downgrade refused" in down
    assert "project_stage_events" in down
    assert "completed_by IS NOT NULL" in down


def test_the_downgrade_drops_every_table_and_index_the_upgrade_created():
    text = _migration_text()
    module = _migration_module()
    down = text.split("def downgrade()")[1]
    for table in module.NEW_TABLES:
        assert f'op.drop_table("{table}")' in down, f"جدولٌ يُنشأ ولا يُسقَط: {table}"
    for index in ("ix_project_stage_events_project", "ix_project_tasks_project",
                  "ix_project_tasks_due", "ix_project_milestones_project"):
        assert index in down, f"فهرسٌ يُنشأ ولا يُسقَط: {index}"
    # والقيد المضاف على جدولٍ قائم يُسحب — وإلّا بقي أثرُ الترحيل بعد تنازله.
    assert 'op.drop_constraint("uq_project_members_project_scoped"' in down


def test_the_downgrade_drops_the_tasks_before_the_constraint_they_point_at():
    text = _migration_text()
    down = text.split("def downgrade()")[1]
    assert (down.index('op.drop_table("project_tasks")')
            < down.index('op.drop_constraint("uq_project_members_project_scoped"')), \
        "سحبُ المرجع قبل من يشير إليه يفشل"


def test_every_check_constraint_name_is_bare_not_already_prefixed():
    """اصطلاح `ck_%(table_name)s_%(constraint_name)s` يُطبَّق على ما نمرّره.

    ومن مرّر الاسم كاملًا بُني له اسمٌ ثانٍ فوقه — وسقط الترحيل في CI من قبل.
    """
    text = _migration_text()
    for name in re.findall(r'name="([^"]+)"', text):
        assert not name.startswith("ck_"), f"اسمُ قيدٍ مسبوقٌ مسبقًا: {name}"


# ═════════════════ ٢. لا نسبة، ولا جاهزيةٌ مخترَعة ═════════════════

# **الألفاظ التي لا يجوز أن تظهر حقلًا في أيّ عقد.** وكلٌّ منها يدّعي قياسًا
# لا عقد علميّ خلفه، ويُقرأ حكمًا على الورقة لا على البطاقات.
FORBIDDEN_FIELD_WORDS = ("percent", "percentage", "ratio", "score", "readiness",
                         "completion_rate", "progress")


def _contract_models():
    import inspect

    from pydantic import BaseModel

    from athera_api.schemas import project_management as schemas

    return [value for value in vars(schemas).values()
            if inspect.isclass(value) and issubclass(value, BaseModel)
            and value is not BaseModel]


def test_no_contract_field_in_this_module_claims_a_percentage_or_a_score():
    """**العطبُ يُمنع في العقد لا في الشاشة.**

    فحقلٌ اسمه `readiness_score` يجعل كل شاشةٍ تقرؤه تعرض رقمًا لا سند له،
    ولن يسأل أحدٌ بعد ذلك من أين جاء.
    """
    for model in _contract_models():
        for field in model.model_fields:
            lowered = field.lower()
            for word in FORBIDDEN_FIELD_WORDS:
                assert word not in lowered, \
                    f"{model.__name__}.{field} يدّعي قياسًا لا عقد له"


def test_no_contract_field_in_this_module_is_a_fraction_at_all():
    """**النوع نفسه هو الحارس.** ولا `float` في هذه العقود، فلا يتسلّل كسر."""
    for model in _contract_models():
        for name, field in model.model_fields.items():
            annotation = str(field.annotation)
            assert "float" not in annotation, \
                f"{model.__name__}.{name} كسرٌ في وحدةٍ لا تقيس شيئًا"
            assert "Decimal" not in annotation, \
                f"{model.__name__}.{name} كسرٌ في وحدةٍ لا تقيس شيئًا"


def test_no_line_in_the_module_computes_a_completion_percentage():
    """ولا حسابَ نسبةٍ في الخدمة ولا في الموجّه ولا في الشاشة."""
    sources = [
        API / "routers" / "project_management.py",
        API / "schemas" / "project_management.py",
        *(API / "services" / "project_management").glob("*.py"),
        *(WEB / "src" / "lib").glob("projectManagement.ts"),
        *(WEB / "src" / "lib").glob("projectTitle.ts"),
    ]
    for path in sources:
        text = path.read_text(encoding="utf-8")
        # `* 100` و`/ total` هما الشكلان اللذان تُصنع بهما النسبة.
        assert "* 100" not in text, f"نسبةٌ تُحسب في {path.name}"
        assert "/ total" not in text, f"نسبةٌ تُحسب في {path.name}"
        assert "Math.round(" not in text or "%" not in text, \
            f"نسبةٌ تُقرَّب في {path.name}"


def test_the_dashboard_answers_the_six_things_the_owner_asked_for():
    """المرحلة · التالي المقترح · المفتوحة · المتأخرة · تنتظر اعتمادك · المفقود."""
    from athera_api.schemas.project_management import ProjectDashboardView

    fields = set(ProjectDashboardView.model_fields)
    assert {"stage", "counts", "missing_scientific_items",
            "needs_your_attention", "team_members", "recent_activity"} <= fields

    from athera_api.schemas.project_management import TaskCountsView

    counts = set(TaskCountsView.model_fields)
    assert {"open", "overdue", "awaiting_your_decision"} <= counts


# ═════════════════ ٣. عنوان المشروع — العيب الحقيقي ═════════════════

def test_a_project_title_is_never_manufactured_from_audit_text_and_a_timestamp():
    """**العيب بعينه**: `قبول 2026-09-09T17:12:41.883012+00:00` عُرض عنوانًا.

    وهذه ليست عنوانًا: هي نصُّ حدثٍ في سجلّ التدقيق ووقتُه لُصقا معًا. فيقرأ
    الباحث قائمة بحوثه ولا يعرف أيّها بحثه.
    """
    from athera_api.services.project_management import project_title
    from athera_api.services.project_management.titles import PLACEHOLDER_AR

    created = _now()
    result = project_title("قبول 2026-09-09T17:12:41.883012+00:00",
                           created_at=created)
    assert result.is_placeholder
    assert result.display_ar == PLACEHOLDER_AR
    assert result.reason == "audit_timestamp"
    # **والتاريخ في حقلٍ منفصل**، لا مضمومًا إلى العنوان.
    assert result.created_at == created
    assert "2026" not in result.display_ar


def test_the_placeholder_carries_no_digit_at_all():
    """رقمٌ في عنوانٍ بديل هو أول خطوةٍ نحو تلفيقٍ يبدو معلومة."""
    from athera_api.services.project_management import project_title

    result = project_title("   ", created_at=_now())
    assert result.is_placeholder
    assert not any(ch.isdigit() for ch in result.display_ar)
    assert not any(ch.isdigit() for ch in result.display_en)


def test_a_blank_or_missing_title_says_so_and_stays_renameable():
    from athera_api.services.project_management import project_title

    for value in (None, "", "   ", "\n\t "):
        result = project_title(value, created_at=_now())
        assert result.is_placeholder
        assert result.reason == "blank"
        # **الإعلان بلا سبيلٍ إلى التصحيح يترك الباحث حيث هو.**
        assert result.can_rename is True


def test_a_date_only_title_is_not_a_title():
    from athera_api.services.project_management import project_title

    for value in ("2026-09-09", "17:12", "— —", "٢٠٢٦"):
        assert project_title(value).is_placeholder, value


def test_a_real_title_that_happens_to_contain_a_year_is_left_exactly_as_written():
    """**رفضُ عنوانٍ صحيح أسوأ من قبول عنوانٍ رديء.**

    باحثٌ سمّى بحثه «دراسة 2024» يجب أن يرى اسمه كما كتبه، لا بديلًا يمحو
    اختياره. والتضييق في `_is_manufactured` مقصودٌ لهذا.
    """
    from athera_api.services.project_management import project_title

    for value in ("دراسة 2024 عن التدريب", "أثر التدريب على الأداء",
                  "COVID-19 و التعليم عن بعد"):
        result = project_title(value)
        assert not result.is_placeholder, value
        assert result.display_ar == value


def test_the_title_contract_never_builds_a_title_out_of_anything():
    """**لا يُصنَع عنوانٌ من شيء** — لا من تاريخٍ ولا من وصفٍ ولا من ملفّ."""
    source = (API / "services" / "project_management" / "titles.py").read_text(
        encoding="utf-8")
    body = source.split("def project_title")[1]
    # لا استيفاء نصٍّ بالتاريخ، ولا ضمُّه إلى العنوان.
    assert "created_at}" not in body
    assert "+ str(created_at" not in body
    assert "strftime" not in body


def test_the_web_and_the_api_carry_the_very_same_title_rule():
    """قاعدةٌ منسوخة في شاشتين تعود إلى العطب في الثالثة."""
    web = (WEB / "src" / "lib" / "projectTitle.ts").read_text(encoding="utf-8")
    api = (API / "services" / "project_management" / "titles.py").read_text(
        encoding="utf-8")
    assert "مشروع بدون عنوان" in web and "مشروع بدون عنوان" in api
    assert r"\d{4}-\d{2}-\d{2}" in web and r"\d{4}-\d{2}-\d{2}" in api
    for reason in ("blank", "audit_timestamp", "no_letters"):
        assert reason in web and reason in api


# ═════════════════ ٤. المرحلة: اقتراحٌ لا ادّعاء ═════════════════

def test_a_suggestion_that_rests_on_an_approved_milestone_names_it():
    from athera_api.services.project_management import suggest_next_stage

    call = suggest_next_stage("literature_discovery",
                              {"literature_review_completed"})
    assert call.is_offered
    assert call.stage == "gap_problem"
    assert call.basis_kind == "milestone_completed"
    assert "اكتمال مراجعة الأدبيات" in call.basis_ar
    # **والقرار يبقى للباحث، ويُقال ذلك في نصّ السند نفسه.**
    assert "قرارك" in call.basis_ar


def test_nothing_is_suggested_on_top_of_a_milestone_that_has_not_happened():
    """**الامتناع هو الميزة.** ومنصّةٌ تدفع الباحث إلى الأمام بلا سندٍ تضرّه."""
    from athera_api.services.project_management import suggest_next_stage

    call = suggest_next_stage("literature_discovery", set())
    assert not call.is_offered
    assert call.stage is None
    assert call.basis_kind == "none"
    assert "لم يُعتمد بعد" in call.basis_ar


def test_a_stage_with_no_closing_milestone_is_suggested_by_convention_and_says_so():
    """**عُرفٌ يُعلَن بوصفه عُرفًا** — ولو صمت لقُرئ دليلًا."""
    from athera_api.services.project_management import suggest_next_stage

    call = suggest_next_stage("scientific_writing", set())
    assert call.is_offered
    assert call.stage == "scientific_review"
    assert call.basis_kind == "conventional_order"
    assert "عُرفٌ لا دليل" in call.basis_ar


def test_the_last_stage_suggests_nothing_after_it():
    from athera_api.services.project_management import suggest_next_stage

    call = suggest_next_stage("published", set(_migration_module().MILESTONES))
    assert not call.is_offered
    assert call.basis_kind == "none"


def test_the_only_two_bases_are_named_and_a_third_is_never_invented():
    from athera_api.models.project_management import MILESTONES, STAGES
    from athera_api.services.project_management import suggest_next_stage

    seen = set()
    for stage in STAGES:
        for done in (set(), set(MILESTONES)):
            seen.add(suggest_next_stage(stage, done).basis_kind)
    assert seen <= {"milestone_completed", "conventional_order", "none"}


def test_going_back_to_methodology_after_analysis_is_never_called_a_regression():
    """التحليلُ يكشف عيبًا في التصميم — والعودة صوابٌ لا تراجع.

    والاقتراح بعدها يُشتقّ من حال الباحث الآن، ولا يدفعه إلى الأمام لأنه
    «كان» أبعد.
    """
    from athera_api.services.project_management import suggest_next_stage

    # اعتُمد «اكتمال التحليل» يومًا، ثمّ عاد إلى المنهجية ولم يُعتمد مَعْلَمها.
    call = suggest_next_stage("design_methodology", {"analysis_completed"})
    assert not call.is_offered, "دُفع الباحث إلى الأمام فوق مَعْلَمٍ لم يقع"
    assert "اعتماد المنهجية" in call.basis_ar
    for word in ("تراجع", "تأخّر", "انتكاس"):
        assert word not in call.basis_ar


def test_an_unknown_stage_yields_no_suggestion_rather_than_a_guess():
    from athera_api.services.project_management import suggest_next_stage

    call = suggest_next_stage("whatever_this_is", {"idea_approved"})
    assert not call.is_offered


def test_the_stage_view_keeps_the_four_facts_apart():
    """حاليّة · اعتمادُ باحث · تاريخ · مقترَح — أربعةٌ لا تُطوى في واحدة."""
    from athera_api.schemas.project_management import (
        ProjectStageView,
        StageHistoryView,
    )

    fields = set(ProjectStageView.model_fields)
    assert {"current_stage", "is_researcher_confirmed", "confirmed_by",
            "confirmed_at", "suggestion", "disclaimer"} <= fields
    assert "events" in StageHistoryView.model_fields


def test_nothing_but_a_researcher_confirmation_ever_writes_the_current_stage():
    """**مسارٌ واحد يكتب المرحلة**، ولا استنتاج من ملفٍّ ولا من زيارةِ صفحة.

    **والشجر النحويّ لا النصّ**: `current_stage = plan.current_stage` قراءةٌ
    إلى متغيّرٍ محلّي، و`plan.current_stage = ...` كتابةٌ في صفّ. والنصّ
    يخلط الاثنين، والشجر يفرّق: الأولى `Name` والثانية `Attribute`.
    """
    import ast

    tree = ast.parse((API / "routers" / "project_management.py").read_text(
        encoding="utf-8"))
    writes: list[tuple[str, int]] = []

    class Walker(ast.NodeVisitor):
        def __init__(self) -> None:
            self.scope: list[str] = []

        def _enter(self, node) -> None:
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        visit_FunctionDef = _enter
        visit_AsyncFunctionDef = _enter

        def visit_Assign(self, node: ast.Assign) -> None:
            for target in node.targets:
                if isinstance(target, ast.Attribute) and target.attr == "current_stage":
                    writes.append((".".join(self.scope), node.lineno))
            self.generic_visit(node)

    Walker().visit(tree)
    assert len(writes) == 1, f"أكثر من مسارٍ يكتب المرحلة: {writes}"
    # **والمسار الوحيد هو اعتماد الباحث.**
    assert writes[0][0] == "confirm_stage", writes


def test_the_suggestion_is_never_stored_in_a_column_of_its_own():
    """قيمةٌ محفوظة تُقرأ بعد شهرٍ حالًا، لا اقتراحًا.

    والعمود الوحيد الذي يحمل اقتراحًا هو `system_suggested_stage` في سجلّ
    **الاعتمادات** — وهو أثرُ ما كان يُقترح لحظة قرارِ إنسان، لا حالٌ قائمة.
    """
    from athera_api.models.project_management import ProjectPlan

    assert not any("suggest" in column.name
                   for column in ProjectPlan.__table__.columns)


# ═════════════════ ٥. ما يحتاج انتباهك — بلا زينة ═════════════════

def test_what_stops_the_work_is_listed_before_what_merely_suggests():
    from athera_api.services.project_management import (
        attention_items,
        suggest_next_stage,
    )
    from athera_api.services.project_management.store import TaskCounts

    items = attention_items(
        current_stage="analysis", is_confirmed=True,
        counts=TaskCounts(open=5, overdue=3, awaiting_your_decision=2),
        missing=[], suggestion=suggest_next_stage("analysis", {"analysis_completed"}))
    keys = [item.key for item in items]
    assert keys.index("overdue_tasks") < keys.index("awaiting_your_decision")
    assert keys.index("awaiting_your_decision") < keys.index("suggested_next")


def test_an_unconfirmed_stage_is_surfaced_as_a_thing_to_do_not_hidden():
    from athera_api.services.project_management import (
        attention_items,
        suggest_next_stage,
    )
    from athera_api.services.project_management.store import TaskCounts

    items = attention_items(current_stage="idea", is_confirmed=False,
                            counts=TaskCounts(), missing=[],
                            suggestion=suggest_next_stage("idea", set()))
    keys = {item.key for item in items}
    assert "stage_unconfirmed" in keys


def test_no_attention_item_ever_carries_a_fraction():
    from athera_api.services.project_management.attention import AttentionItem

    annotation = AttentionItem.__annotations__["count"]
    assert "float" not in str(annotation)


def test_an_early_project_is_not_told_its_manuscript_is_missing():
    """«مخطوطة مفقودة» لكل بحثٍ جديد ضجيجٌ يُدرَّب الباحث على تجاهله."""
    from athera_api.services.project_management import missing_scientific_items
    from athera_api.services.project_management.store import ScientificState

    missing = missing_scientific_items("idea", ScientificState())
    assert [item.key for item in missing] == []


def test_a_project_that_says_it_is_analysing_with_no_dataset_is_told_so():
    from athera_api.services.project_management import missing_scientific_items
    from athera_api.services.project_management.store import ScientificState

    missing = missing_scientific_items("analysis", ScientificState(
        included_sources=4, approved_gaps=1, approved_decisions=1, datasets=0))
    assert [item.key for item in missing] == ["dataset"]


def test_a_missing_item_is_reported_as_an_absence_of_records_not_a_verdict():
    from athera_api.services.project_management import (
        attention_items,
        missing_scientific_items,
        suggest_next_stage,
    )
    from athera_api.services.project_management.store import ScientificState, TaskCounts

    missing = missing_scientific_items("analysis", ScientificState())
    items = attention_items(current_stage="analysis", is_confirmed=True,
                            counts=TaskCounts(), missing=missing,
                            suggestion=suggest_next_stage("analysis", set()))
    detail = next(i.detail_ar for i in items if i.key == "missing_scientific_items")
    assert "لا حكمٌ على عملك خارجها" in detail


# ═════════════════ ٦. الاقتراح معاينةٌ لا تكليف ═════════════════

def test_the_suggestion_layer_writes_absolutely_nothing():
    """**خاصيّةٌ مفحوصة لا اصطلاحٌ يُتّبع.**

    فلو أضاف أحدٌ يومًا `session.add` هنا سقط الفحص قبل أن يصل الإنتاج،
    ووجد عشر مهامّ في قائمة كل باحث لم يطلبها.
    """
    import ast

    tree = ast.parse((API / "services" / "project_management" / "suggestions.py")
                     .read_text(encoding="utf-8"))
    # **الشجر لا النصّ**: هذا الملفّ يشرح في توثيقه لماذا لا يكتب، فذِكرُ
    # `session.add` في جملةٍ عربية ليس كتابةً — والفحص النصّي يعدّه كذلك،
    # فيسقط على شرحٍ صحيح ويترك استدعاءً حقيقيًّا لو غُيّر اسمه قليلًا.
    writers = {"add", "add_all", "execute", "commit", "flush", "delete", "merge"}
    offenders = [f"{node.func.attr}:{node.lineno}"
                 for node in ast.walk(tree)
                 if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute)
                 and node.func.attr in writers]
    assert not offenders, f"طبقةُ المعاينة تكتب: {offenders}"
    # ولا تستورد جلسةً أصلًا — فلا شيء تكتب به.
    imported = {alias.name for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                for alias in node.names}
    assert "AsyncSession" not in imported


def test_a_suggestion_is_never_assigned_to_anybody():
    """الإسنادُ فعلُ الباحث بعد القبول — وهو ما يجعل المهمّة التزامًا حقيقيًّا."""
    from athera_api.services.project_management.suggestions import TaskSuggestion

    assert "assignee" not in str(TaskSuggestion.__annotations__)


def test_every_suggestion_says_why_by_pointing_at_a_number_in_the_database():
    from athera_api.services.project_management import propose_tasks
    from athera_api.services.project_management.store import ScientificState, TaskCounts

    proposals = propose_tasks(
        current_stage="analysis", state=ScientificState(), counts=TaskCounts(),
        completed_milestones=set(), existing_titles=set())
    assert proposals
    for item in proposals:
        assert item.why_ar.strip(), f"اقتراحٌ بلا سبب: {item.key}"
        assert item.source == "research_brain_suggestion"


def test_a_suggestion_already_accepted_does_not_come_back_as_noise():
    from athera_api.services.project_management import propose_tasks
    from athera_api.services.project_management.store import ScientificState, TaskCounts

    first = propose_tasks(current_stage="literature_discovery",
                          state=ScientificState(), counts=TaskCounts(),
                          completed_milestones=set(), existing_titles=set())
    titles = {item.title_ar for item in first}
    again = propose_tasks(current_stage="literature_discovery",
                          state=ScientificState(), counts=TaskCounts(),
                          completed_milestones=set(), existing_titles=titles)
    assert {item.title_ar for item in again} & titles == set()


def test_the_contract_refuses_to_create_a_system_task_without_an_acceptance():
    """**٤٢٢ لا إنشاءٌ صامت.** والقاعدة ترفضه أيضًا — وهذا حارسٌ قبلها."""
    import pydantic

    from athera_api.schemas.project_management import TaskCreateRequest

    with pytest.raises(pydantic.ValidationError):
        TaskCreateRequest(title="مهمّة", stage="analysis",
                          source="research_brain_suggestion")

    accepted = TaskCreateRequest(title="مهمّة", stage="analysis",
                                 source="research_brain_suggestion",
                                 accept_suggestion=True)
    assert accepted.accept_suggestion is True


def test_a_decision_gate_without_requiring_a_decision_is_refused():
    import pydantic

    from athera_api.schemas.project_management import TaskCreateRequest

    with pytest.raises(pydantic.ValidationError):
        TaskCreateRequest(title="مهمّة", stage="analysis", decision_gate="G4")


# ═════════════════ ٧. الاحتفاظ والإتلاف الدائم ═════════════════

def test_permanent_deletion_is_blocked_and_the_reason_is_a_read_policy_not_a_guess():
    """**الامتناع قرارٌ مدروس لا عطب.**

    وسياسةُ الاحتفاظ في هذا المستودع غير معرَّفةٍ تعريفًا صالحًا للتنفيذ،
    والمصادر التي قُرئت مذكورةٌ في الاستجابة نفسها.
    """
    from athera_api.services.project_management import retention

    call = retention.verdict()
    assert call.is_blocked
    assert call.reason == "retention_policy_undefined"
    assert call.requirement_ar.strip()
    assert call.policy_sources
    for source in call.policy_sources:
        assert (REPO / source).exists(), f"سياسةٌ يُستشهد بها ولا وجود لها: {source}"


def test_the_classification_matrix_really_does_leave_retention_undefined():
    """**الدعوى تُثبَت من المستند لا من الذاكرة.**

    فلو كُتبت السياسة يومًا وبقي الوقف، سقط هذا الفحص وطالب برفعه.
    """
    matrix = (REPO / "docs" / "data-classification.md").read_text(encoding="utf-8")
    assert "مدة المشروع + 5 سنوات" in matrix
    assert "Data Management Plan" in matrix
    assert "حسب الموافقة الأخلاقية فقط" in matrix
    # ولا جدولَ في القاعدة يمثّل خطّة إدارة البيانات ولا الموافقة الأخلاقية.
    from athera_api.models import Base

    tables = set(Base.metadata.tables)
    assert not {t for t in tables if "data_management_plan" in t}
    assert not {t for t in tables if "ethics_approval" in t}


def test_the_preview_counts_all_ten_kinds_the_owner_named():
    from athera_api.services.project_management import store

    source = pathlib.Path(store.__file__).read_text(encoding="utf-8")
    for kind in ("sources", "claims", "approved_knowledge", "files", "team",
                 "tasks", "decisions", "manuscript", "synthesis_objects",
                 "audit_dependencies"):
        assert f'"{kind}"' in source, f"تبعيةٌ لم تُعدّ: {kind}"


def test_no_line_in_this_module_deletes_a_project_row():
    """**لا سطرَ إتلافٍ مكتوب أصلًا** — فلا يُبلَغ بخطأ ولا بتعديلٍ عابر."""
    router = (API / "routers" / "project_management.py").read_text(encoding="utf-8")
    for destructive in ("session.delete(", "delete(ResearchProject)", "TRUNCATE"):
        assert destructive not in router, f"إتلافٌ مكتوب: {destructive}"


# ═════════════════ ٨. الترجمة والمفردات ═════════════════

def test_every_error_code_this_router_raises_has_both_locales():
    """**ما يُرفع خطأً وحده هو ما يُترجَم** — وأسماءُ أحداث التدقيق ليست منه.

    والفرق يُقرأ من الشجر: `NotFound("…")` رمزُ خطأٍ يصل الباحث، و
    `action="project_management.task_created"` اسمُ حدثٍ في سجلّ لا يراه.
    وفحصٌ نصّيّ يخلط الاثنين فيطالب بترجمةٍ لما لا يُعرض.
    """
    import ast

    from athera_api.i18n.catalog import CATALOG, SUPPORTED_LOCALES

    tree = ast.parse((API / "routers" / "project_management.py").read_text(
        encoding="utf-8"))
    raisers = {"NotFound", "AtheraError", "Forbidden", "Unauthorized"}
    codes = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name) and node.func.id in raisers
        and node.args and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    assert codes, "موجّهٌ بلا رموز خطأ؟"
    for code in codes:
        assert code in CATALOG, f"رمزٌ بلا ترجمة: {code}"
        for locale in SUPPORTED_LOCALES:
            assert CATALOG[code].get(locale, "").strip(), f"{code} ينقصه {locale}"

    # **ولا مفتاحَ ترجمةٍ ميّت**: رمزٌ في الكتالوج لا يرفعه أحد يتراكم
    # ويُقرأ عقدًا قائمًا، ثمّ يُبنى عليه في شاشة.
    catalogued = {key for key in CATALOG if key.startswith("project_management.")}
    assert catalogued == codes, f"مفاتيحُ بلا رافع: {sorted(catalogued - codes)}"


def test_every_researcher_facing_vocabulary_carries_both_locales():
    from athera_api.models.project_management import (
        MILESTONES,
        STAGES,
        TASK_PRIORITIES,
        TASK_SOURCES,
        TASK_STATUSES,
    )
    from athera_api.services.project_management import vocab

    pairs = (
        (vocab.STAGE_LABELS, STAGES),
        (vocab.MILESTONE_LABELS, MILESTONES),
        (vocab.TASK_STATUS_LABELS, TASK_STATUSES),
        (vocab.TASK_PRIORITY_LABELS, TASK_PRIORITIES),
        (vocab.TASK_SOURCE_LABELS, TASK_SOURCES),
    )
    for table, keys in pairs:
        assert set(table) == set(keys), "مفردةٌ بلا تسمية أو تسميةٌ بلا مفردة"
        for key, entry in table.items():
            for locale in ("ar", "en"):
                assert entry.get(locale, "").strip(), f"{key} ينقصه {locale}"


def test_every_stage_has_an_exit_milestone_entry_even_when_it_is_none():
    """**الفراغ يُعلَن ولا يُترك ثغرة.** ومرحلةٌ غائبةٌ عن الخريطة تُنتج KeyError."""
    from athera_api.models.project_management import MILESTONES, STAGES
    from athera_api.services.project_management.vocab import STAGE_EXIT_MILESTONE

    assert set(STAGE_EXIT_MILESTONE) == set(STAGES)
    for stage, milestone in STAGE_EXIT_MILESTONE.items():
        assert milestone is None or milestone in MILESTONES, stage


def test_the_layer_calls_no_model_provider():
    """**لا نموذج لغويّ في هذا المسار.** المرحلة والمهامّ قواعدُ حتمية."""
    for path in (API / "services" / "project_management").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for vendor in ("anthropic", "openai", "gateway", "model_run"):
            assert vendor not in text, f"{path.name} يمسّ مزوّد نموذج: {vendor}"


# ═════════════════ ٩. الشاشات ═════════════════

def test_the_three_researcher_facing_screens_exist():
    for page in PAGES:
        assert (SCREEN / page / "page.tsx").exists(), f"لا شاشة لـ{page}"
    assert (WEB / "src" / "app" / "[locale]" / "portfolio" / "trash"
            / "page.tsx").exists(), "لا شاشة لسلّة المهملات"


def test_each_screen_tells_loading_from_ready_from_empty_from_failed():
    """**أخطرها الأخيرة**: طلبٌ فشل يُعرض «لا مهامّ» يجعل الباحث يظنّ قائمته فارغة."""
    for page in (*PAGES, "../trash"):
        path = (SCREEN / page / "page.tsx") if not page.startswith("..") \
            else (WEB / "src" / "app" / "[locale]" / "portfolio" / "trash"
                  / "page.tsx")
        text = path.read_text(encoding="utf-8")
        for state in ('"loading"', '"ready"', '"failed"'):
            assert state in text, f"{page} لا يفرّق الحالات: {state}"
        assert "-empty" in text, f"{page} لا يميّز الفراغ"


def test_no_state_is_set_synchronously_inside_an_effect():
    for page in PAGES:
        text = (SCREEN / page / "page.tsx").read_text(encoding="utf-8")
        assert "useEffect" in text
        assert "let alive" in text, f"{page} تأثيرٌ بلا حارس"


def test_every_repeated_control_names_its_target():
    """زرٌّ مكرّرٌ بلا اسمِ هدفه لا يبلغه قارئُ شاشة، ولا يُميَّز في فحص."""
    for page in PAGES:
        text = (SCREEN / page / "page.tsx").read_text(encoding="utf-8")
        if ".map(" in text and "<button" in text:
            assert "aria-label" in text, f"{page} أزرارٌ مكرّرة بلا أسماء"


def test_no_screen_in_this_track_ever_prints_a_percentage():
    """ولا في الشاشة أيضًا — فالعقد يمنع الحقل، وهذا يمنع الحساب المحلّي."""
    paths = [SCREEN / page / "page.tsx" for page in PAGES]
    paths.append(WEB / "src" / "app" / "[locale]" / "portfolio" / "trash"
                 / "page.tsx")
    paths.append(WEB / "src" / "lib" / "projectManagement.ts")
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "%`" not in text, f"نسبةٌ تُعرض في {path.name}"
        assert "toFixed(" not in text, f"كسرٌ يُعرض في {path.name}"


def test_the_web_reads_the_title_through_the_shared_contract_not_the_raw_column():
    """قراءةُ العمود خامًا في شاشةٍ واحدة تُعيد العيب بعد أن أُصلح في أربع."""
    trash = (WEB / "src" / "app" / "[locale]" / "portfolio" / "trash"
             / "page.tsx").read_text(encoding="utf-8")
    assert "title.display" in trash or "displayTitle" in trash
    assert "working_title_ar" not in trash


# ═════════════════ ١٠. التركيب: مُعلَنٌ لا مخفيّ ═════════════════

def test_the_router_is_either_mounted_or_its_mount_is_formally_requested():
    """**نقصٌ يُقال صراحةً لا يُترك ليُكتشف.**

    `main.py` ملفُّ المُكامِل وحده، فلا يعدّله هذا المسار. وحتى يُضاف
    السطران لا يبلغ هذه النقاطَ طلبُ HTTP — ومن قرأ الموجّه قد يظنّ الميزة
    قائمة. فإمّا أن تكون مركَّبة، وإمّا أن يكون الطلب مكتوبًا بنصّه.
    """
    main = (API / "main.py").read_text(encoding="utf-8")
    if "project_management_router" in main:
        assert "app.include_router(project_management_router.router)" in main
        return
    assert REQUESTS_DOC.exists(), "لا موجّهٌ مركَّب ولا طلبُ تركيبٍ مكتوب"
    doc = REQUESTS_DOC.read_text(encoding="utf-8")
    assert "from .routers import project_management as project_management_router" in doc
    assert "app.include_router(project_management_router.router)" in doc


def test_the_integration_requests_document_records_the_shared_title_contract():
    """العقدُ المشترك يُوثَّق ليستهلكه غيرُ هذا المسار، لا ليُكتشف بالقراءة."""
    assert REQUESTS_DOC.exists()
    doc = REQUESTS_DOC.read_text(encoding="utf-8")
    assert "projectTitle" in doc
    assert "مشروع بدون عنوان" in doc


# ═══════════════════════════════════════════════════════════════
#                  ما يلي يحتاج PostgreSQL حيّة
# ═══════════════════════════════════════════════════════════════

@contextlib.contextmanager
def counting_statements():
    """يعدّ عبارات القاعدة الحقيقية — و`set_config` ليست منها.

    ضبطُ سياق المستأجر عبارتان في كل جلسة مهما كان المسار؛ عدُّهما يخلط
    ثمنًا ثابتًا بثمنٍ ينمو، وما يُقاس هنا هو الثاني.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    seen: list[str] = []
    original = AsyncSession.execute

    async def spy(self, statement, *args, **kwargs):
        rendered = str(statement)
        if "set_config" not in rendered:
            seen.append(rendered)
        return await original(self, statement, *args, **kwargs)

    AsyncSession.execute = spy
    try:
        yield seen
    finally:
        AsyncSession.execute = original


async def _seed_project(tenant_id, title="بحثُ قبولٍ لإدارة المشروع"):
    from athera_api.db import system_session
    from athera_api.models.portfolio import ResearchProject

    async with system_session() as session:
        project = ResearchProject(tenant_id=tenant_id, working_title_ar=title,
                                  status="planned")
        session.add(project)
        await session.flush()
        return project.id


async def _seed_member(tenant_id, project_id, name="زميلٌ في الفريق"):
    from athera_api.db import system_session
    from athera_api.models.portfolio import ProjectMember

    async with system_session() as session:
        member = ProjectMember(tenant_id=tenant_id, project_id=project_id,
                               display_name=name, role="co_author")
        session.add(member)
        await session.flush()
        return member.id


async def _trash_project(tenant_id, user_id, project_id):
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ResearchProject

    async with tenant_session(tenant_id, user_id) as session:
        row = (await session.execute(select(ResearchProject).where(
            ResearchProject.id == project_id))).scalar_one()
        row.deleted_at = _now()
        row.deleted_by = user_id
        await session.flush()


# ═════════════ ١١. القاعدة نفسها ترفض ما لا يجوز ═════════════

@requires_db
@pytest.mark.asyncio
async def test_the_database_refuses_a_task_assigned_to_another_projects_member(
        two_tenants):
    """**العطب الذي وقع في هذا المنتج من قبل**: RLS تحمي بين مستأجرين فقط.

    وبحثان لمستأجرٍ واحد يتسرّب أحدهما إلى الآخر ما لم يمنعه شيء. والمانع
    هنا مفتاحٌ مركّب في القاعدة، لا شرطٌ في خدمة يُنسى في المسار الثاني.
    """
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.project_management import ProjectTask

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    project_a = await _seed_project(tid, "بحثُ ألف")
    project_b = await _seed_project(tid, "بحثُ باء")
    member_of_b = await _seed_member(tid, project_b)

    with pytest.raises(IntegrityError):
        async with tenant_session(tid, uid) as session:
            session.add(ProjectTask(
                tenant_id=tid, project_id=project_a, title="مهمّة",
                stage="analysis", status="not_started", priority="normal",
                assignee_member_id=member_of_b, created_by=uid,
                source="researcher_created", suggested_by_system=False))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_the_database_refuses_a_system_suggestion_nobody_accepted(two_tenants):
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.project_management import ProjectTask

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    project_id = await _seed_project(tid)

    with pytest.raises(IntegrityError):
        async with tenant_session(tid, uid) as session:
            session.add(ProjectTask(
                tenant_id=tid, project_id=project_id, title="مهمّةٌ اقترحتها آلة",
                stage="analysis", status="not_started", priority="normal",
                created_by=uid, source="research_brain_suggestion",
                suggested_by_system=True))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_the_database_refuses_a_milestone_completed_by_nobody(two_tenants):
    """**الإتمام فعلُ إنسانٍ** — ولو قُبل بلا صاحبٍ لصار أثرَ زيارةِ صفحة."""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.project_management import ProjectMilestone

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    project_id = await _seed_project(tid)

    with pytest.raises(IntegrityError):
        async with tenant_session(tid, uid) as session:
            session.add(ProjectMilestone(
                tenant_id=tid, project_id=project_id,
                milestone_key="data_ready", completed_at=_now()))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_the_database_refuses_a_stage_event_with_no_human_behind_it(
        two_tenants):
    """لا صفَّ في سجلّ المراحل تكتبه المنصّة عن نفسها."""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.project_management import ProjectStageEvent

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    project_id = await _seed_project(tid)

    with pytest.raises(IntegrityError):
        async with tenant_session(tid, uid) as session:
            session.add(ProjectStageEvent(
                tenant_id=tid, project_id=project_id, to_stage="analysis",
                occurred_at=_now(), confirmed_by=None))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_a_completed_task_must_carry_the_time_it_was_completed(two_tenants):
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.project_management import ProjectTask

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    project_id = await _seed_project(tid)

    with pytest.raises(IntegrityError):
        async with tenant_session(tid, uid) as session:
            session.add(ProjectTask(
                tenant_id=tid, project_id=project_id, title="مهمّة",
                stage="analysis", status="completed", priority="normal",
                created_by=uid, source="researcher_created",
                suggested_by_system=False))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_row_level_security_hides_another_tenants_tasks_in_sql_itself(
        two_tenants):
    """العزلُ بين المستأجرين يُثبت في SQL قبل أن يُثبت في الموجّه."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.project_management import ProjectTask

    a, b = two_tenants["a"], two_tenants["b"]
    project_id = await _seed_project(a["tenant_id"])

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        session.add(ProjectTask(
            tenant_id=a["tenant_id"], project_id=project_id, title="سرُّ ألف",
            stage="idea", status="not_started", priority="normal",
            created_by=a["user_id"], source="researcher_created",
            suggested_by_system=False))
        await session.flush()

    async with tenant_session(b["tenant_id"], b["user_id"]) as session:
        rows = (await session.execute(select(ProjectTask))).scalars().all()
        assert rows == [], "مهامُّ مستأجرٍ ظهرت لغيره"


# ═════════════ ١٢. عددُ العبارات — وهو زمن الاستجابة ═════════════

@requires_db
@pytest.mark.asyncio
async def test_the_task_list_costs_the_same_for_one_task_and_for_forty(two_tenants):
    """**`N+1` سريعٌ في كل عبارةٍ منه** — ولا يظهر إلا بالعدّ.

    وأربعون مهمّة بعبارةٍ لكل واحدة تعني ثلاث عشرة ثانية على شبكة
    سنغافورة–مومباي، والشيفرة تبدو سليمة تمامًا.
    """
    from athera_api.db import tenant_session
    from athera_api.models.project_management import ProjectTask
    from athera_api.services.project_management import store

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    project_id = await _seed_project(tid)
    member_id = await _seed_member(tid, project_id)

    async def add_tasks(count: int):
        async with tenant_session(tid, uid) as session:
            for index in range(count):
                session.add(ProjectTask(
                    tenant_id=tid, project_id=project_id, title=f"مهمّة {index}",
                    stage="analysis", status="not_started", priority="normal",
                    assignee_member_id=member_id, created_by=uid,
                    source="researcher_created", suggested_by_system=False))
            await session.flush()

    await add_tasks(1)
    async with tenant_session(tid, uid) as session:
        with counting_statements() as few:
            rows = await store.list_tasks(session, tenant_id=tid,
                                          project_id=project_id)
    assert len(rows) == 1
    assert len(few) == 1, few
    # واسمُ المُسنَد إليه جاء في العبارة نفسها، لا بعبارةٍ ثانية.
    assert rows[0].assignee_name is not None

    await add_tasks(39)
    async with tenant_session(tid, uid) as session:
        with counting_statements() as many:
            rows = await store.list_tasks(session, tenant_id=tid,
                                          project_id=project_id)
    assert len(rows) == 40
    assert len(many) == len(few), f"الكلفة تتبع عدد الصفوف: {len(many)} مقابل {len(few)}"


@requires_db
@pytest.mark.asyncio
async def test_the_dashboard_costs_a_fixed_number_of_statements(two_tenants):
    """اللوحةُ تُفتح في كل مرّة — فكلفتها ثابتةٌ أو تصير هي البطء نفسه."""
    from athera_api.db import tenant_session
    from athera_api.models.project_management import ProjectMilestone, ProjectTask
    from athera_api.services.project_management import store

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    project_id = await _seed_project(tid)

    async def read_dashboard_reads(session):
        now = _now()
        await store.plan_for(session, tenant_id=tid, project_id=project_id)
        await store.milestone_rows(session, tenant_id=tid, project_id=project_id)
        await store.task_counts(session, tenant_id=tid, project_id=project_id, now=now)
        await store.scientific_state(session, tenant_id=tid, project_id=project_id)
        await store.recent_activity(session, tenant_id=tid, project_id=project_id)

    async with tenant_session(tid, uid) as session:
        with counting_statements() as empty:
            await read_dashboard_reads(session)

    async with tenant_session(tid, uid) as session:
        for index in range(25):
            session.add(ProjectTask(
                tenant_id=tid, project_id=project_id, title=f"مهمّة {index}",
                stage="analysis", status="not_started", priority="normal",
                created_by=uid, source="researcher_created",
                suggested_by_system=False))
        for key in ("idea_approved", "gap_approved", "data_ready"):
            session.add(ProjectMilestone(
                tenant_id=tid, project_id=project_id, milestone_key=key,
                completed_at=_now(), completed_by=uid))
        await session.flush()

    async with tenant_session(tid, uid) as session:
        with counting_statements() as full:
            await read_dashboard_reads(session)

    assert len(empty) == 5, empty
    assert len(full) == len(empty), \
        f"كلفةُ اللوحة تتبع البيانات: {len(full)} مقابل {len(empty)}"


@requires_db
@pytest.mark.asyncio
async def test_the_deletion_preview_counts_ten_kinds_in_one_statement(two_tenants):
    """المعاينةُ تسبق أخطر زرٍّ في المنتج — وتأخّرُها يجعلها تُتخطّى."""
    from athera_api.db import tenant_session
    from athera_api.services.project_management import store

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    project_id = await _seed_project(tid)

    async with tenant_session(tid, uid) as session:
        with counting_statements() as seen:
            counts = await store.dependency_counts(session, tenant_id=tid,
                                                   project_id=project_id)
    assert len(counts) == 10
    assert len(seen) == 1, seen


# ═════════════ ١٣. قبولٌ عبر HTTP بهويّةٍ حقيقية ═════════════
#
# **الخدمةُ تُستدعى مباشرةً فوق، والباحث لا يستدعيها.** بينه وبينها موجّهٌ
# ومصادقةٌ وجلسةُ مستأجرٍ وصلاحية. وفحصٌ يبلغ الخدمة من غير هذا الطريق يثبت
# أنّ الحساب صحيح، ولا يثبت أنّ أحدًا يستطيع بلوغه.


def _app():
    """التطبيقُ الحقيقي إن كان الموجّه مركَّبًا، وإلّا فتركيبٌ مكافئ للفحص.

    **ويُقال الفرق صراحةً**: `main.py` ملفُّ المُكامِل، ولم يُعدَّل. فحتى
    يُضاف السطران لا يبلغ المتصفّحُ هذه النقاط، ولو مرّ هذا الفحص. وهذا
    التركيب يحمل **الموجّه نفسه** وسلسلة التبعيات نفسها ومعالج الأخطاء
    نفسه — فما يُثبت هنا يُثبت للموجّه لا لنسخةٍ عنه.
    """
    from athera_api.main import app as real_app

    for route in real_app.routes:
        if getattr(route, "path", "").startswith("/api/v1/project-management"):
            return real_app

    from fastapi import FastAPI

    from athera_api.errors import AtheraError, athera_error_handler
    from athera_api.routers import project_management

    harness = FastAPI()
    harness.add_exception_handler(AtheraError, athera_error_handler)
    harness.include_router(project_management.router)
    return harness


def _client(tenant_id: uuid.UUID, user_id: uuid.UUID):
    """عميلٌ يحمل رمزًا حقيقيًّا — لا تجاوزَ للمصادقة في فحصٍ يدّعي إثباتها."""
    import httpx

    from athera_api.security import issue_access_token

    token = issue_access_token(user_id=user_id, tenant_id=tenant_id,
                               roles=["researcher"], mfa_satisfied=True)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()), base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": "ar"})


@requires_db
@pytest.mark.asyncio
async def test_a_signed_in_researcher_drives_the_whole_chain_over_http(two_tenants):
    """**السلسلةُ كاملةً من طرف الشبكة**: مهمّة، إسناد، حال، موعد، تأخّر،
    مَعْلَم، اقتراحٌ ثمّ اعتماد، وتاريخُ مراحل.
    """
    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    project_id = await _seed_project(tid, "أثرُ التدريب على الأداء")
    member_id = await _seed_member(tid, project_id, "د. سارة")
    base = f"/api/v1/project-management/projects/{project_id}"

    async with _client(tid, uid) as client:
        # ── اللوحة قبل أن يقع شيء ──
        board = await client.get(f"{base}/dashboard")
        assert board.status_code == 200, board.text
        view = board.json()
        assert view["stage"]["current_stage"] == "idea"
        # **ولم يقل أحدٌ إنها مرحلته.**
        assert view["stage"]["is_researcher_confirmed"] is False
        assert view["title"]["display_ar"] == "أثرُ التدريب على الأداء"
        # ولا نسبة في أيّ موضعٍ من الجواب.
        assert "percent" not in board.text and "readiness" not in board.text

        # ── مهمّةٌ تُنشأ وتُسنَد إلى عضوٍ في فريق هذا البحث ──
        due = _now() - dt.timedelta(days=2)   # موعدٌ فات — ليُحسب التأخّر
        made = await client.post(f"{base}/tasks", json={
            "title": "استخراج المتغيّرات من المصفوفة", "stage": "analysis",
            "priority": "high", "assignee_member_id": str(member_id),
            "due_at": due.isoformat()})
        assert made.status_code == 201, made.text
        task = made.json()
        task_id = task["id"]
        assert task["status"] == "not_started"
        assert task["suggested_by_system"] is False

        # ── القائمة: الإسناد والتأخّر يُقرآن معًا ──
        listed = (await client.get(f"{base}/tasks")).json()
        assert listed["tasks"], "مهمّةٌ أُنشئت ولا تظهر في قائمتها"
        row = next(t for t in listed["tasks"] if t["id"] == task_id)
        assert row["assignee_name"] == "د. سارة"
        assert row["is_overdue"] is True, "موعدٌ فات ولم يُحسب متأخّرًا"
        assert listed["counts"]["overdue"] == 1
        assert listed["counts"]["open"] == 1

        # ── انتقالُ حال ──
        moved = await client.patch(f"{base}/tasks/{task_id}",
                                   json={"status": "in_progress"})
        assert moved.status_code == 200, moved.text
        assert moved.json()["status"] == "in_progress"
        assert moved.json()["started_at"] is not None

        done = await client.patch(f"{base}/tasks/{task_id}",
                                  json={"status": "completed"})
        assert done.status_code == 200, done.text
        assert done.json()["completed_at"] is not None
        # **ومكتملةٌ لا تُعدّ متأخرة** مهما فات موعدها.
        assert done.json()["is_overdue"] is False

        # ── المرحلة: اقتراحٌ ممتنع، ثمّ مَعْلَمٌ، ثمّ اقتراحٌ مسنود ──
        stage = (await client.get(f"{base}/stage")).json()
        assert stage["suggestion"]["is_offered"] is False
        assert "لم يُعتمد بعد" in stage["suggestion"]["basis"]

        marked = await client.put(f"{base}/milestones/idea_approved",
                                  json={"completed": True,
                                        "evidence_note_ar": "اعتُمدت في اجتماع"})
        assert marked.status_code == 200, marked.text
        assert marked.json()["is_completed"] is True
        # **والإتمام منسوبٌ إلى صاحبه**، لا إلى النظام.
        assert marked.json()["completed_by"] == str(uid)

        stage = (await client.get(f"{base}/stage")).json()
        assert stage["suggestion"]["is_offered"] is True
        assert stage["suggestion"]["stage"] == "literature_discovery"
        assert stage["suggestion"]["basis_kind"] == "milestone_completed"
        # **والمرحلة الحالية لم تتغيّر باقتراح.**
        assert stage["current_stage"] == "idea"
        assert stage["is_researcher_confirmed"] is False

        # ── الاعتماد فعلُ الباحث ──
        confirmed = await client.post(f"{base}/stage/confirm", json={
            "stage": "literature_discovery", "note_ar": "بدأتُ المسح"})
        assert confirmed.status_code == 200, confirmed.text
        after = confirmed.json()
        assert after["current_stage"] == "literature_discovery"
        assert after["is_researcher_confirmed"] is True
        assert after["confirmed_by"] == str(uid)

        # ── التاريخ يحفظ ما كان يُقترح لحظتها ──
        history = (await client.get(f"{base}/stage/history")).json()
        assert len(history["events"]) == 1
        event = history["events"][0]
        assert event["to_stage"] == "literature_discovery"
        assert event["confirmed_by"] == str(uid)
        assert event["system_suggested_stage"] == "literature_discovery"
        assert event["followed_the_suggestion"] is True

        # ── والعودة إلى مرحلةٍ سابقة تُقبل وتُسمّى بما هي ──
        back = await client.post(f"{base}/stage/confirm", json={
            "stage": "idea", "note_ar": "أعدتُ صياغة الفكرة"})
        assert back.status_code == 200, back.text
        history = (await client.get(f"{base}/stage/history")).json()
        assert history["events"][-1]["is_return_to_earlier_stage"] is True
        assert history["events"][-1]["followed_the_suggestion"] is False

        # ── الخطُّ الزمني ──
        planned = await client.patch(f"{base}/plan", json={
            "start_date": "2026-01-05", "target_completion_date": "2026-12-01"})
        assert planned.status_code == 200, planned.text
        timeline = (await client.get(f"{base}/timeline")).json()
        assert timeline["start_date"] == "2026-01-05"
        assert timeline["target_completion_date"] == "2026-12-01"
        assert len(timeline["milestones"]) == 11
        assert len(timeline["stage_events"]) == 2

    # **والاعتماد يحمل اسم صاحبه في القاعدة**، لا في الاستجابة وحدها.
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.project_management import ProjectPlan

    async with tenant_session(tid, uid) as session:
        plan = (await session.execute(select(ProjectPlan).where(
            ProjectPlan.project_id == project_id))).scalar_one()
        assert plan.stage_confirmed_by == uid
        assert plan.stage_confirmed_at is not None


@requires_db
@pytest.mark.asyncio
async def test_a_research_brain_suggestion_never_becomes_a_task_by_itself(
        two_tenants):
    """المسارُ كاملًا: اقتراح ← معاينة ← قبولٌ صريح ← مهمّة.

    **ولا اختصار فيه.** والمعاينة لا تكتب شيئًا — يُثبت ذلك بأن القائمة
    تبقى فارغةً بعدها.
    """
    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    project_id = await _seed_project(tid)
    base = f"/api/v1/project-management/projects/{project_id}"

    async with _client(tid, uid) as client:
        await client.post(f"{base}/stage/confirm", json={"stage": "analysis"})

        preview = await client.get(f"{base}/task-suggestions")
        assert preview.status_code == 200, preview.text
        body = preview.json()
        assert body["suggestions"], "مشروعٌ بلا شيءٍ مسجَّل ولم يُقترح فيه شيء"
        assert "لم يُنشأ منها شيء" in body["note"]
        for item in body["suggestions"]:
            assert item["why_ar"].strip()

        # **والمعاينة لم تكتب**: القائمة ما زالت فارغة.
        assert (await client.get(f"{base}/tasks")).json()["tasks"] == []

        first = body["suggestions"][0]
        # ولا تُنشأ بلا قبولٍ صريح — والعقد يردّ ٤٢٢ لا ينشئ بصمت.
        refused = await client.post(f"{base}/tasks", json={
            "title": first["title_ar"], "stage": first["stage"],
            "source": "research_brain_suggestion"})
        assert refused.status_code == 422, refused.text
        assert (await client.get(f"{base}/tasks")).json()["tasks"] == []

        accepted = await client.post(f"{base}/tasks", json={
            "title": first["title_ar"], "stage": first["stage"],
            "source": "research_brain_suggestion", "accept_suggestion": True})
        assert accepted.status_code == 201, accepted.text
        made = accepted.json()
        assert made["suggested_by_system"] is True
        # **والقبول منسوبٌ إلى صاحبه ووقته.**
        assert made["accepted_by"] == str(uid)
        assert made["accepted_at"] is not None
        # ولم تُسنَد إلى أحدٍ من تلقائها.
        assert made["assignee_member_id"] is None


@requires_db
@pytest.mark.asyncio
async def test_a_project_with_no_meaningful_title_is_shown_as_untitled_over_http(
        two_tenants):
    """**العيبُ يُفحص من حيث ظهر**: قائمةُ بحوثٍ عناوينها نصُّ تدقيقٍ ووقت."""
    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    manufactured = await _seed_project(
        tid, "قبول 2026-09-09T17:12:41.883012+00:00")
    real = await _seed_project(tid, "دراسة 2024 عن التدريب")
    await _trash_project(tid, uid, manufactured)
    await _trash_project(tid, uid, real)

    async with _client(tid, uid) as client:
        trash = await client.get("/api/v1/project-management/trash")
        assert trash.status_code == 200, trash.text
        rows = {row["project_id"]: row for row in trash.json()["projects"]}

        broken = rows[str(manufactured)]
        assert broken["title"]["display_ar"] == "مشروع بدون عنوان"
        assert broken["title"]["is_placeholder"] is True
        assert broken["title"]["placeholder_reason"] == "audit_timestamp"
        # **والتاريخ في حقلٍ منفصل، لا في العنوان.**
        assert broken["title"]["created_at"] is not None
        assert "2026-09-09T17:12" not in broken["title"]["display_ar"]
        assert broken["title"]["can_rename"] is True

        kept = rows[str(real)]
        assert kept["title"]["display_ar"] == "دراسة 2024 عن التدريب"
        assert kept["title"]["is_placeholder"] is False


@requires_db
@pytest.mark.asyncio
async def test_permanent_deletion_previews_its_dependencies_then_refuses(
        two_tenants):
    """**لا إتلافَ صامت ولا نجاحٌ مدّعى.** ٤٠٩ ومعها المعاينة كاملة."""
    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    project_id = await _seed_project(tid, "بحثٌ له نسبٌ علميّ")
    await _seed_member(tid, project_id)

    async with _client(tid, uid) as client:
        base = f"/api/v1/project-management/trash/{project_id}"

        # بحثٌ ليس في السلّة لا يُسأل عن إتلافه أصلًا.
        assert (await client.get(f"{base}/deletion-preview")).status_code == 404

    await _trash_project(tid, uid, project_id)

    async with _client(tid, uid) as client:
        base = f"/api/v1/project-management/trash/{project_id}"
        preview = await client.get(f"{base}/deletion-preview")
        assert preview.status_code == 200, preview.text
        body = preview.json()
        kinds = {row["kind"] for row in body["dependencies"]}
        assert kinds == {"sources", "claims", "approved_knowledge", "files", "team",
                         "tasks", "decisions", "manuscript", "synthesis_objects",
                         "audit_dependencies"}
        assert any(row["kind"] == "team" and row["count"] == 1
                   for row in body["dependencies"])
        assert body["is_blocked"] is True
        assert body["unblock_requirement"].strip()

        refused = await client.post(f"{base}/permanent-delete")
        assert refused.status_code == 409, refused.text
        error = refused.json()["error"]
        assert error["code"] == "project_management.permanent_delete_blocked"
        assert error["messages"]["ar"].strip() and error["messages"]["en"].strip()

    # **والبحث باقٍ كما هو** — والوقف ليس إتلافًا مؤجَّلًا.
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ResearchProject

    async with tenant_session(tid, uid) as session:
        row = (await session.execute(select(ResearchProject).where(
            ResearchProject.id == project_id))).scalar_one_or_none()
        assert row is not None, "بحثٌ أُتلف رغم أن الإتلاف موقوف"


@requires_db
@pytest.mark.asyncio
async def test_another_tenant_is_refused_at_the_route_not_only_in_sql(two_tenants):
    """**العزل يُثبت من حيث يدخل المهاجم**: برمزٍ صحيحٍ لمستأجرٍ آخر."""
    a, b = two_tenants["a"], two_tenants["b"]
    project_id = await _seed_project(a["tenant_id"])

    async with _client(b["tenant_id"], b["user_id"]) as stranger:
        base = f"/api/v1/project-management/projects/{project_id}"
        for path in (f"{base}/dashboard", f"{base}/tasks", f"{base}/stage",
                     f"{base}/milestones", f"{base}/timeline",
                     f"{base}/stage/history", f"{base}/task-suggestions"):
            answer = await stranger.get(path)
            assert answer.status_code == 404, f"{path} سرّب وجودَ بحثِ غيره"
        assert (await stranger.post(f"{base}/stage/confirm",
                                    json={"stage": "analysis"})).status_code == 404


@requires_db
@pytest.mark.asyncio
async def test_one_project_cannot_reach_into_another_inside_the_same_tenant(
        two_tenants):
    """**RLS لا تحمي هنا** — والمستأجر واحد والبحثان اثنان.

    وثلاثةُ أبوابٍ تُجرَّب: إسنادٌ إلى عضو الآخر، وتعديلُ مهمّته من مساره،
    وقراءتُها في قائمته.
    """
    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    project_a = await _seed_project(tid, "بحثُ ألف")
    project_b = await _seed_project(tid, "بحثُ باء")
    member_of_b = await _seed_member(tid, project_b, "عضوُ باء")

    a_base = f"/api/v1/project-management/projects/{project_a}"
    b_base = f"/api/v1/project-management/projects/{project_b}"

    async with _client(tid, uid) as client:
        # ١ — إسنادٌ إلى عضوٍ في البحث الآخر يُرفض برسالةٍ مفهومة، لا بـ٥٠٠.
        refused = await client.post(f"{a_base}/tasks", json={
            "title": "مهمّة", "stage": "analysis",
            "assignee_member_id": str(member_of_b)})
        assert refused.status_code == 404, refused.text
        assert refused.json()["error"]["code"] == \
            "project_management.member_not_in_project"

        # ٢ — مهمّةُ باء لا تُقرأ ولا تُعدَّل من مسار ألف.
        made = await client.post(f"{b_base}/tasks", json={
            "title": "مهمّةُ باء", "stage": "analysis"})
        assert made.status_code == 201, made.text
        task_id = made.json()["id"]

        leaked = await client.patch(f"{a_base}/tasks/{task_id}",
                                    json={"status": "completed"})
        assert leaked.status_code == 404, "مهمّةُ بحثٍ عُدِّلت من مسار بحثٍ آخر"

        # ٣ — ولا تظهر في قائمته.
        listing = (await client.get(f"{a_base}/tasks")).json()
        assert task_id not in {row["id"] for row in listing["tasks"]}
        assert listing["counts"]["total"] == 0


@requires_db
@pytest.mark.asyncio
async def test_reading_the_dashboard_never_writes_a_row(two_tenants):
    """**نقطةُ قراءةٍ تكتب تُنشئ صفًّا عند كل تحديثٍ للصفحة.**

    ولا يظهر ذلك في الشاشة أبدًا — يظهر في نمو الجدول وفي كلفة الكتابة.
    """
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.project_management import ProjectPlan

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    project_id = await _seed_project(tid)

    async with _client(tid, uid) as client:
        base = f"/api/v1/project-management/projects/{project_id}"
        for _ in range(3):
            assert (await client.get(f"{base}/dashboard")).status_code == 200
            assert (await client.get(f"{base}/stage")).status_code == 200

    async with tenant_session(tid, uid) as session:
        rows = (await session.execute(select(func.count(ProjectPlan.id)).where(
            ProjectPlan.project_id == project_id))).scalar_one()
    assert rows == 0, "قراءةُ اللوحة كتبت صفًّا في القاعدة"
