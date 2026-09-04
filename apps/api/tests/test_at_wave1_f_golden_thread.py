"""الخيط الذهبي حيًّا، والعقل البحثي يقترح ولا يُلزم | Wave 1 — Track F.

**الخيط يبني نفسه من بيانات البحث، والدرجةُ لا تكذب، والكشفُ لا يُنشئ التزامًا.**

وهذا الملف يثبت ثمانية:

١) **الصفرُ الكاذب لا يخرج.** خيطٌ في أوّله تنقصه العناصر التسعة كان يُعرض
   «درجة الاتساق: ٠» — ويقرؤها الباحث «بحثُك في أقصى درجات التناقض»
   والحقيقةُ «لا نملك ما يكفي للحكم». فـ`presented_score` تصير `None`
   ويُقال السبب بنصّه.

٢) **ولا عددان متناقضان.** «تسعة عيوب حاجبة» فوق «لا توجد عيوب اتساق»
   تناقضٌ في عين الباحث: الأول يجمع المفقودات والعيوب، والثاني يعدّ
   العيوب وحدها. فالأعداد تُفصَل بأسمائها.

٣) **وبيانات البحث تظهر بلا إعادة إدخال.** ما سُجّل في جداول المشروع
   يُنسج خيطًا، ولا يُطلب من الباحث أن يكتبه مرّةً ثانية.

٤) **والمفقود يُعرض مفقودًا، والمرشّح يحتاج مراجعة، والمعتمد يُميَّز،
   والتعارض يُرى.** أربع حالاتٍ بمفردة المستودع نفسها.

٥) **والسندُ يصل مع كل خطّ**: اسمُ الصفّ الذي يشهد، أو تصريحٌ بأن لا صفَّ
   يشهد.

٦) **والإضافة اليدوية تبقى.** النسجُ التلقائي لا يُغلق باب الباحث.

٧) **والاقتراح يُعاين ولا يُنشئ.** ولا مسار كتابةٍ في السلسلة كلها.

٨) **والعزل يقع مرّتين**: بين مستأجرين، وبين بحثين في المستأجر الواحد —
   والثاني هو العطب الذي وقع في هذا المنتج من قبل.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import re
import uuid

import pytest

from tests.conftest import requires_db

REPO = pathlib.Path(__file__).resolve().parents[3]
WEB = REPO / "apps" / "web"
THREAD_LAB = WEB / "src" / "app" / "[locale]" / "thread" / "page.tsx"
THREAD_PAGE = (WEB / "src" / "app" / "[locale]" / "portfolio" / "[projectId]"
               / "thread" / "page.tsx")
BRAIN_PAGE = (WEB / "src" / "app" / "[locale]" / "portfolio" / "[projectId]"
              / "brain" / "page.tsx")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# ═══════════ ١. الدرجة: صفرٌ عن نقصٍ ليس حكمًا (بلا قاعدة بيانات) ═══════════


def _empty_graph():
    from athera_api.services.golden_thread.graph import MethodSpec, ThreadGraph

    return ThreadGraph(method=MethodSpec(study_type="quantitative"))


def _complete_graph():
    """أصغرُ خيطٍ يحمل العناصر التسعة كلها — فالاتساق يصير قابلًا للحساب."""
    from athera_api.services.golden_thread.graph import (
        Element,
        InstrumentSpec,
        Link,
        MethodSpec,
        ThreadGraph,
        VariableSpec,
    )

    return ThreadGraph(
        elements=[Element("p1", "problem", "م"), Element("g1", "gap", "ف"),
                  Element("q1", "question", "س"), Element("o1", "objective", "هـ"),
                  Element("t1", "theory", "نظرية السلوك المخطط"),
                  Element("a1", "analysis", "انحدار")],
        links=[Link("q1", "o1", "maps_to"), Link("q1", "a1", "analyzes")],
        variables=[VariableSpec("v1", "الثقة", "independent", True, True)],
        instruments=[InstrumentSpec("i1", "استبانة", ("v1",))],
        method=MethodSpec(study_type="quantitative", design_family="correlational",
                          sampling_strategy="stratified_random"),
        discussion_text="نوقشت النتائج وفق نظرية السلوك المخطط.",
        results_text="ظهر ارتباط موجب دال.",
    )


def test_an_incomplete_thread_presents_no_number_at_all():
    """**العيب الأصلي.** خيطٌ ناقص كان يُخرج صفرًا يُقرأ حكمًا بأسوأ حال.

    والشرط هنا على `presented_score is None` لا على قيمةٍ أخرى: أيُّ رقمٍ
    يخرج — صفرًا كان أو مئة — يُعرض درجةً، والدرجةُ على نقصٍ لم يُفحص دعوى.
    """
    from athera_api.services.golden_thread import score

    result = score.compute(_empty_graph())

    assert result.missing_elements, "الخيط الفارغ يجب أن تنقصه عناصر"
    assert result.is_computable is False
    assert result.presented_score is None
    assert result.not_computed_reason_ar == score.NOT_COMPUTED_AR
    assert result.not_computed_reason_en == score.NOT_COMPUTED_EN


def test_missing_elements_are_not_counted_as_consistency_defects():
    """**المفقود ليس عيبًا.** وخلطُهما هو ما أنتج «تسعة عيوب» فوق «لا عيوب».

    و`blocking_count` تبقى للبوابة تجمع الصنفين — وهو صحيحٌ لها — لكنّ
    الأعداد المعروضة تُفصَل، فلا يبقى في الشاشة رقمٌ يجمع صنفين.
    """
    from athera_api.services.golden_thread import score

    result = score.compute(_empty_graph())

    # لا عيب اتساقٍ واحد: لا علاقة تُفحص بين عنصرٍ وغياب.
    assert result.structural_count == 0
    assert result.linguistic_count == 0
    assert result.missing_count == len(result.missing_elements) > 0
    # والبوابة تبقى مغلقة كما كانت — العرض تغيّر لا الحكم.
    assert result.can_pass_gate is False
    assert result.blocking_count == result.structural_count + result.missing_count


def test_a_complete_thread_does_present_its_number():
    """**ولا يُبتلع الرقم حين يصحّ.** الإصلاح إخفاءُ الكاذب لا إلغاءُ الصادق."""
    from athera_api.services.golden_thread import score

    result = score.compute(_complete_graph())

    assert result.is_computable is True
    assert result.presented_score == result.score
    assert result.not_computed_reason_ar is None


def test_the_gate_contract_is_untouched_by_the_presentation_fix():
    """**البوابة قرارٌ آليّ، والعرضُ قراءةُ إنسان — ولا يُفسد أحدهما الآخر.**

    فحصٌ يثبّت أنّ الإصلاح لم يفتح بوابةً كانت مغلقة: لو صارت `can_pass_gate`
    تتبع `is_computable` لسقط هنا.
    """
    from athera_api.services.golden_thread import score

    assert score.compute(_empty_graph()).can_pass_gate is False
    assert score.compute(_complete_graph()).can_pass_gate is True


# ═══════════════ ٢. عنوان البحث: فراغٌ يُسمَّى ولا يُترك ═══════════════


def test_a_blank_title_falls_back_and_says_it_fell_back():
    from athera_api.services.golden_thread import project_title

    shown = project_title.present("   ", None, locale="ar")
    assert shown.title == project_title.UNTITLED_AR
    assert shown.is_fallback is True


def test_a_real_title_is_never_replaced():
    """**ولا يُخفى عنوانٌ مخزَّن.** إخفاءُ عنوانٍ صحيح يُفقد الباحثَ بحثه.

    وعنوانٌ فيه تاريخ عنوانٌ مشروع: كاشفُ «يشبه طابعًا زمنيًّا» كان سيبتلعه.
    """
    from athera_api.services.golden_thread import project_title

    for title in ("أثر التدريب على الأداء",
                  "مراجعة منهجية 2026",
                  "قياس الرضا — يناير 2026"):
        shown = project_title.present(title, None, locale="ar")
        assert shown.title == title
        assert shown.is_fallback is False


def test_the_created_date_is_a_separate_field_not_part_of_the_title():
    """**ودمجُ التاريخ في العنوان هو أصلُ العناوين المشوَّهة.**"""
    from athera_api.services.golden_thread import project_title

    when = _now()
    shown = project_title.present("بحثٌ له اسم", None, locale="ar", created_at=when)
    assert shown.created_at == when
    assert str(when.year) not in shown.title


# ═════════ ٣. الاقتراح يُعاين ولا يُنشئ (بلا قاعدة بيانات) ═════════


def _report_with(**bins):
    from athera_api.services.research_assessment.view import Item, ResearcherReport

    def items(rows):
        return tuple(
            Item(key=key, detail_ar=detail, detail_en=detail,
                 rule_id=rule_id, entity_ids=tuple(entities), excerpt=excerpt)
            for key, detail, rule_id, entities, excerpt in rows)

    return ResearcherReport(
        project_id=str(uuid.uuid4()), title_ar="بحث",
        **{name: items(rows) for name, rows in bins.items()})


def test_a_finding_becomes_a_suggestion_that_creates_nothing():
    """**الحارس بنيويّ.** `creates_obligation` لا تُمرَّر في البناء أصلًا."""
    from athera_api.services.research_assessment import suggestions

    report = _report_with(missing=[
        ("instrument_missing", "أداة قياس المتغيّر الوسيط غير مسجَّلة.",
         None, ["variable:1"], None)])

    actions = suggestions.suggest(report)
    assert len(actions) == 1
    assert actions[0].creates_obligation is False
    with pytest.raises(TypeError):
        # لا سبيل لبناء اقتراحٍ يدّعي أنّه أنشأ شيئًا.
        suggestions.SuggestedAction(
            key="k", finding_key="f", category="missing", state="missing",
            action_kind="a", title_ar="ع", title_en="e",
            detail_ar="ت", detail_en="d", creates_obligation=True)


def test_the_preview_says_plainly_that_nothing_was_created():
    from athera_api.services.research_assessment import suggestions

    report = _report_with(needs_review=[
        ("candidate", "معلومة مستخرَجة تنتظر قرارك.", None, [], "مقتطف")])
    shown = suggestions.preview(suggestions.suggest(report)[0])

    assert shown.is_preview is True
    assert shown.created is False
    # والشاهد ينتقل إلى المعاينة: مهمّةٌ بلا ما أثارها لا تُراجَع.
    assert shown.excerpt == "مقتطف"
    # وما لا يُعرف يُسمَّى ولا يُملأ باختراع.
    assert {key for key, _ar, _en in shown.undetermined_fields} == {
        "assignee", "due_date", "priority"}


def test_a_platform_limit_is_not_turned_into_a_researcher_obligation():
    """**«لا نخزّن هذا» ليست فجوةً في بحثك.**

    و`view.py` تضع ملاحظات القراءة في «ما ينقص» — وهي ناقصةٌ من المنصّة لا
    من البحث. واقتراحُ «سجّل ما ينقص» عليها يطلب تسجيلًا في حقلٍ غير موجود،
    ثمّ يلوم الباحث أنّه لم يفعل.
    """
    from athera_api.services.research_assessment import suggestions
    from athera_api.services.research_assessment.view import Item, ResearcherReport

    note = Item(key="no_such_table", detail_ar="لا تخزّن المنصّة هذا.",
                detail_en="The platform does not store this.")
    real = Item(key="instrument", detail_ar="أداةٌ غير مسجَّلة.",
                detail_en="Instrument not recorded.")
    report = ResearcherReport(project_id=str(uuid.uuid4()), title_ar="بحث",
                              missing=(note, real), read_notes=(note,))

    keys = {action.finding_key for action in suggestions.suggest(report)}
    assert keys == {"instrument"}


def test_what_is_already_known_produces_no_suggestion():
    """**قائمةٌ تقترح عملًا عن كل شيء لا تُقرأ**، فيسقط الصحيح مع الزائد."""
    from athera_api.services.research_assessment import suggestions

    report = _report_with(known=[("design", "التصميم المسجَّل: كمّي.", None, [], None)])
    assert suggestions.suggest(report) == []


def test_a_suggestion_carries_the_rank_of_its_rule_or_says_it_has_none():
    """**سطرٌ بمعرّفٍ مجرّد يُقرأ حكمًا معتمَدًا** — والقواعد كلها مسوّدة."""
    from athera_api.research_brain import BY_ID
    from athera_api.services.research_assessment import suggestions

    rule_id = "RB-CAUSALITY-01"
    report = _report_with(methodological_alerts=[
        ("alert", "لغة سببية في دراسة ارتباطية.", rule_id, ["claim:1"], "يسبب")])

    action = suggestions.suggest(report, dict(BY_ID))[0]
    assert action.rule_id == rule_id
    assert action.rule_status == "DRAFT"
    assert action.rule_is_enforceable is False
    assert action.provenance
    assert action.state == "needs_review"


def test_suggestion_keys_separate_two_places_of_one_rule():
    """**القاعدة الواحدة تقع على مواضع، ولكلِّ موضعٍ فعلُه.**

    ومفتاحٌ لا يميّزهما يجعل معاينةَ المتغيّر الوسيط تُفتح على التابع.
    """
    from athera_api.services.research_assessment import suggestions

    report = _report_with(conflicts=[
        ("clash", "تعارضٌ في الوسيط.", None, ["variable:mediator"], None),
        ("clash", "تعارضٌ في التابع.", None, ["variable:outcome"], None)])

    keys = {action.key for action in suggestions.suggest(report)}
    assert len(keys) == 2


def test_no_write_path_exists_in_the_suggestion_module():
    """**الفعلُ الذي لا يملك مسارَ كتابةٍ لا يكتب** — والحارس يُقرأ من المصدر.

    وحارسٌ يقوم على نيّة الكاتب يسقط في أوّل تعديل؛ فيُثبَّت غيابُ الجلسة
    والنموذج من الوحدة نفسها.
    """
    source = (pathlib.Path(__file__).resolve().parents[1] / "athera_api" / "services"
              / "research_assessment" / "suggestions.py").read_text(encoding="utf-8")

    assert "AsyncSession" not in source
    assert "session" not in source.lower().replace("assessment", "")
    for forbidden in ("session.add", "commit(", "insert(", "update(", "delete("):
        assert forbidden not in source


# ═════════════════ ٤. الشاشات: لا صفرٌ كاذب ولا وعدٌ بزرّ ═════════════════


def test_the_lab_screen_no_longer_renders_the_raw_score():
    """**`data.score` كانت تُرسم مباشرةً** — وهي الدرجة الآلية للبوابة."""
    text = THREAD_LAB.read_text(encoding="utf-8")

    assert "presented_score" in text
    assert "scoreNotComputed" in text or "not_computed_reason" in text
    # الحقل الخام لا يُرسم: يبقى في العقد ولا يبلغ الشاشة.
    assert "{data.score}" not in text


def test_the_lab_screen_names_its_four_categories_separately():
    """**عناصر مفقودة · عيوب بنيوية · تنبيهات منهجية · تعارضات.**"""
    text = THREAD_LAB.read_text(encoding="utf-8")

    for testid in ("thread-missing-count", "thread-structural-count",
                   "thread-linguistic-count", "thread-conflict-count"):
        assert f'data-testid="{testid}"' in text
    # ولا يُرسم العدّاد الجامع الذي أنتج التناقض.
    assert "{data.blocking_count}" not in text


def test_the_lab_screen_keeps_manual_add():
    """**النسجُ التلقائي لا يُغلق باب الباحث.**"""
    text = THREAD_LAB.read_text(encoding="utf-8")
    assert "thread.addSubmit" in text
    assert "thread/elements" in text


def test_the_thread_screen_shows_the_project_title_and_flags_a_fallback():
    text = THREAD_PAGE.read_text(encoding="utf-8")
    assert "thread-project-title" in text
    assert "title_is_fallback" in text
    assert "created_at" in text


def test_the_brain_screen_previews_without_promising_creation():
    """**زرٌّ يَعِد بما لا يقع أسوأ من غيابه.**"""
    text = BRAIN_PAGE.read_text(encoding="utf-8")

    assert "brain-preview" in text
    assert "brain-preview-not-created" in text
    assert "brain-accept-disabled" in text
    assert "disabled" in text


def test_no_screen_shows_a_readiness_percentage():
    """**ولا نسبة جاهزية بأي صيغة** — القرار متّخذ ولا يُنقض من بابٍ ثالث."""
    banned = re.compile(r"جاهزية|readiness|نسبة الاكتمال|percent_complete")
    for page in (THREAD_LAB, THREAD_PAGE, BRAIN_PAGE):
        text = page.read_text(encoding="utf-8")
        assert not banned.search(text), f"{page.name} يعرض نسبة جاهزية"


# ═════════════ ٥. قبولٌ عبر HTTP بهويّةٍ حقيقية، وعزلٌ مرّتين ═════════════
#
# **الخدمةُ تُستدعى مباشرةً أعلاه، والباحث لا يستدعيها.** بينه وبينها موجّهٌ
# ومصادقةٌ وجلسةُ مستأجرٍ وصلاحية. وفحصٌ يبلغ الخدمة من غير هذا الطريق يثبت
# أنّ الحساب صحيح، ولا يثبت أنّ أحدًا يستطيع بلوغه.


def _client(tenant_id: uuid.UUID, user_id: uuid.UUID):
    """عميلٌ يحمل رمزًا حقيقيًّا — لا تجاوزَ للمصادقة في فحصٍ يدّعي إثباتها."""
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    token = issue_access_token(user_id=user_id, tenant_id=tenant_id,
                               roles=["researcher"], mfa_satisfied=True)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": "ar"})


async def _seed_project(tid: uuid.UUID, uid: uuid.UUID, title: str) -> uuid.UUID:
    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ResearchProject

    async with tenant_session(tid, uid) as session:
        project = ResearchProject(tenant_id=tid, working_title_ar=title,
                                  study_type="quantitative", status="active")
        session.add(project)
        await session.flush()
        return project.id


async def _seed_woven_project(tid: uuid.UUID, uid: uuid.UUID,
                              title: str = "أثر التدريب على الأداء") -> uuid.UUID:
    """بحثٌ ببياناتٍ مسجَّلة في جداوله — **بلا أن يُكتب في الخيط سطرٌ يدويّ**.

    وهذا هو محلّ الإثبات: النسج يقرأ ما سجّله الباحث في المنهج والبناءات
    والمتغيّرات والأدوات، فيظهر في الخيط بلا إعادة إدخال.
    """
    from athera_api.db import tenant_session
    from athera_api.models.golden_thread import (
        Construct,
        Instrument,
        InstrumentItem,
        Method,
        Theory,
        ThreadElement,
        Variable,
    )

    project_id = await _seed_project(tid, uid, title)
    async with tenant_session(tid, uid) as session:
        theory = Theory(tenant_id=tid, project_id=project_id,
                        name_ar="نظرية السلوك المخطط")
        session.add(theory)
        await session.flush()

        # بناءان: الأول تقيسه أداة، والثاني لا — فيظهر التعارض.
        measured = Construct(tenant_id=tid, project_id=project_id,
                             name_ar="الدافعية", theory_id=theory.id)
        unmeasured = Construct(tenant_id=tid, project_id=project_id,
                               name_ar="الالتزام التنظيمي", theory_id=theory.id)
        session.add_all([measured, unmeasured])
        await session.flush()

        variable = Variable(tenant_id=tid, project_id=project_id,
                            construct_id=measured.id, name_ar="الدافعية الذاتية",
                            role="independent",
                            operational_definition_ar="مجموع درجات المقياس",
                            appears_in_title=True)
        # متغيّر البناء الثاني بلا تعريف إجرائي ولا أداة.
        other = Variable(tenant_id=tid, project_id=project_id,
                         construct_id=unmeasured.id, name_ar="الالتزام",
                         role="dependent")
        session.add_all([variable, other])
        await session.flush()

        instrument = Instrument(tenant_id=tid, project_id=project_id,
                                name_ar="استبانة الدافعية",
                                instrument_type="questionnaire")
        session.add(instrument)
        await session.flush()
        session.add(InstrumentItem(tenant_id=tid, instrument_id=instrument.id,
                                   variable_id=variable.id,
                                   item_text_ar="أشعر بالحماس لعملي", ordinal=1))

        session.add(Method(tenant_id=tid, project_id=project_id,
                           study_type="quantitative", design_label_ar="ارتباطي مقطعي",
                           design_family="correlational",
                           sampling_strategy="stratified_random", sample_size=300))

        # سؤالٌ **معتمَد** — فالمعتمد يجب أن يُميَّز عن غيره.
        session.add(ThreadElement(
            tenant_id=tid, project_id=project_id, element_type="question",
            label_ar="ما أثر الدافعية على الأداء؟", ordinal=1,
            approved_at=_now()))
        await session.flush()
    return project_id


@requires_db
@pytest.mark.asyncio
async def test_the_thread_assembles_itself_from_recorded_project_data(two_tenants):
    """**بيانات البحث تظهر بلا إعادة إدخال** — وهذا غرض المسار كلّه.

    ولم يُكتب في الخيط عنصرٌ عن النظرية ولا البناء ولا المنهج: كلُّها
    صفوفٌ في جداولها، والخيط يقرؤها.
    """
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project_id = await _seed_woven_project(tid, uid)

    async with _client(tid, uid) as client:
        response = await client.get(f"/api/v1/projects/{project_id}/thread/golden-view")
    assert response.status_code == 200, response.text
    view = response.json()

    labels = {node["label"]
              for stage in view["stages"] for node in stage["nodes"]}
    # نظريةٌ وبناءٌ ومنهجٌ وأداة — لم يكتب الباحث واحدًا منها في الخيط.
    assert "نظرية السلوك المخطط" in labels
    assert "الدافعية" in labels
    assert "ارتباطي مقطعي" in labels
    assert "استبانة الدافعية" in labels

    # وأصلُ كل عقدة يُقال: «نتيجة» كتبها الباحث ليست «نتيجة» أخرجها تحليل.
    origins = {node["origin"]
               for stage in view["stages"] for node in stage["nodes"]}
    assert "theories" in origins and "methods" in origins


@requires_db
@pytest.mark.asyncio
async def test_the_thread_shows_missing_needs_review_and_conflicting_states(two_tenants):
    """**أربع حالاتٍ بمفردة المستودع نفسها، ولا مفردة ثانية للرسم.**"""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project_id = await _seed_woven_project(tid, uid)

    async with _client(tid, uid) as client:
        view = (await client.get(
            f"/api/v1/projects/{project_id}/thread/golden-view")).json()

    states = {connection["state"] for connection in view["connections"]}
    assert states <= {"known", "needs_review", "missing", "conflicting"}
    # البناء الذي لا تقيسه أداةٌ بينما تقيس غيره — تعارضٌ مرئيّ لا مطويّ.
    assert "conflicting" in states, view["counts"]
    assert "missing" in states or "needs_review" in states

    # **والسندُ يصل مع كل خطّ**، أو يُقال إنّه لا صفَّ يشهد.
    for connection in view["connections"]:
        assert "basis" in connection
        if connection["state"] == "known":
            assert connection["basis"], connection


@requires_db
@pytest.mark.asyncio
async def test_the_consistency_endpoint_never_returns_a_presented_zero(two_tenants):
    """**العيب الأصلي من طرف الشبكة.** ولو عاد الصفر لسقط هنا."""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project_id = await _seed_project(tid, uid, "بحثٌ في أوّله")

    async with _client(tid, uid) as client:
        body = (await client.get(
            f"/api/v1/projects/{project_id}/thread/consistency")).json()

    assert body["presented_score"] is None
    assert body["is_computable"] is False
    assert body["not_computed_reason"]
    # ولا عددان متناقضان: العيوب صفر لأنّه لا علاقة تُفحص، والمفقود مسمًّى.
    assert body["structural_count"] == 0
    assert body["missing_count"] > 0
    assert body["conflict_count"] == 0
    # وصفرُ التعارضات يُقال لماذا، فلا يُقرأ شهادةَ سلامة.
    assert body["conflict_note"]


@requires_db
@pytest.mark.asyncio
async def test_a_blank_project_title_never_reaches_the_screen_raw(two_tenants):
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project_id = await _seed_project(tid, uid, "   ")

    async with _client(tid, uid) as client:
        view = (await client.get(
            f"/api/v1/projects/{project_id}/thread/golden-view")).json()

    assert view["title"] == "مشروع بدون عنوان"
    assert view["title_is_fallback"] is True
    assert view["created_at"], "تاريخ الإنشاء حقلٌ مستقلّ يُعرض بجانب الاسم"


@requires_db
@pytest.mark.asyncio
async def test_manual_element_add_still_works_over_http(two_tenants):
    """**الإضافة اليدوية تبقى ثانويةً لا ممنوعة.**"""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project_id = await _seed_project(tid, uid, "بحثٌ يدويّ")

    async with _client(tid, uid) as client:
        created = await client.post(
            f"/api/v1/projects/{project_id}/thread/elements",
            json={"element_type": "problem", "label_ar": "مشكلةٌ كتبها الباحث",
                  "ordinal": 1})
        assert created.status_code == 201, created.text

        view = (await client.get(
            f"/api/v1/projects/{project_id}/thread/golden-view")).json()

    labels = {node["label"] for stage in view["stages"] for node in stage["nodes"]}
    assert "مشكلةٌ كتبها الباحث" in labels


@requires_db
@pytest.mark.asyncio
async def test_an_advisory_action_previews_a_task_without_creating_one(two_tenants):
    """**السلسلة كاملةً من طرف الشبكة: كشف ← اقتراح ← معاينة — ولا التزام.**"""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project_id = await _seed_woven_project(tid, uid)

    async with _client(tid, uid) as client:
        base = f"/api/v1/projects/{project_id}/brain/suggested-actions"
        listing = await client.get(base)
        assert listing.status_code == 200, listing.text
        body = listing.json()
        assert body["actions"], "بحثٌ ناقصُ الأداة يجب أن يُنتج اقتراحًا"
        assert all(action["creates_obligation"] is False for action in body["actions"])
        assert body["advisory_note"]

        action = body["actions"][0]
        preview = await client.get(base + "/preview",
                                   params={"action_key": action["key"]})
        assert preview.status_code == 200, preview.text
        shown = preview.json()

    assert shown["is_preview"] is True
    assert shown["created"] is False
    assert shown["not_created_note"]
    # والعقد الغائب يُسمَّى، فلا تُقرأ المعاينة وعدًا بزرٍّ موجود.
    assert shown["pending_contract_note"]
    assert {field["key"] for field in shown["undetermined_fields"]} == {
        "assignee", "due_date", "priority"}


@requires_db
@pytest.mark.asyncio
async def test_the_preview_route_is_read_only(two_tenants):
    """**ولا مسار كتابةٍ في السلسلة.** والحارس يسأل الشبكة لا المصدر."""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project_id = await _seed_woven_project(tid, uid)

    async with _client(tid, uid) as client:
        base = f"/api/v1/projects/{project_id}/brain/suggested-actions"
        key = (await client.get(base)).json()["actions"][0]["key"]
        # لا مسار إنشاءٍ يقبل هذا المفتاح — لا على القائمة ولا على المعاينة.
        assert (await client.post(base, json={"action_key": key})).status_code == 405
        assert (await client.post(base + "/preview",
                                  json={"action_key": key})).status_code == 405

        # والمعاينة لا تُغيّر شيئًا: القائمة نفسها قبلها وبعدها.
        before = (await client.get(base)).json()["actions"]
        await client.get(base + "/preview", params={"action_key": key})
        after = (await client.get(base)).json()["actions"]
    assert before == after


@requires_db
@pytest.mark.asyncio
async def test_one_project_never_reads_another_in_the_same_tenant(two_tenants):
    """**العزل داخل المستأجر الواحد** — وهو العطب الذي وقع في هذا المنتج."""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    mine = await _seed_woven_project(tid, uid, "بحثي")
    other = await _seed_woven_project(tid, uid, "بحثٌ آخر لي")

    async with _client(tid, uid) as client:
        my_view = (await client.get(
            f"/api/v1/projects/{mine}/thread/golden-view")).json()
        assert my_view["title"] == "بحثي"

        my_keys = {action["key"] for action in (await client.get(
            f"/api/v1/projects/{mine}/brain/suggested-actions")).json()["actions"]}
        other_keys = {action["key"] for action in (await client.get(
            f"/api/v1/projects/{other}/brain/suggested-actions")).json()["actions"]}

        # ومفتاحُ اقتراحٍ في بحثٍ لا يُعاين في بحثٍ آخر، ولو كان لصاحبه.
        stray = next(iter(other_keys - my_keys), None)
        if stray is not None:
            leaked = await client.get(
                f"/api/v1/projects/{mine}/brain/suggested-actions/preview",
                params={"action_key": stray})
            assert leaked.status_code == 404, leaked.text


@requires_db
@pytest.mark.asyncio
async def test_a_tenant_never_reads_another_tenants_thread_or_actions(two_tenants):
    """**العزل بين مستأجرين** — وجوابُه «غير موجود» لا قائمةٌ فارغة.

    وقائمةٌ فارغة تقول «فُحص فلم يوجد» عمّا لم يُفحص أصلًا، وتؤكّد للسائل
    أنّ المعرّف قائم.
    """
    a, b = two_tenants["a"], two_tenants["b"]
    theirs = await _seed_woven_project(a["tenant_id"], a["user_id"], "سرٌّ لا يخرج")

    async with _client(b["tenant_id"], b["user_id"]) as client:
        for path in (f"/api/v1/projects/{theirs}/thread/golden-view",
                     f"/api/v1/projects/{theirs}/brain/suggested-actions"):
            response = await client.get(path)
            assert response.status_code == 404, (path, response.text)
            assert "سرٌّ لا يخرج" not in response.text
