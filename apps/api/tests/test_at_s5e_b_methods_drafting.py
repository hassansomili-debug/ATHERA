"""S5E-B — صياغة المنهجية من أدلتها.

**السؤال الذي يحرسه هذا الملف:** هل تبقى كل جملةٍ منهجية قادرةً على قول من
أين جاءت؟

فالخطر هنا أشدّ من S5D: هناك كانت المخرجات **مقترحات** يقرؤها الباحث ويختار،
وهنا نصٌّ سيحمل اسمه في ورقة محكَّمة. وجملةٌ منهجية مخترَعة — أداةٌ لم تُستعمل،
أو أسلوب معاينة لم يُطبَّق — لا يكشفها قارئ ولا محكِّم؛ تبدو صحيحة تمامًا.

ولا يكشفها اختبارٌ وظيفي: كلّه «يعمل».
"""
from __future__ import annotations

import uuid

import pytest

from tests.conftest import requires_db

FACTS = {
    "design": "استخدمت الدراسة المنهج شبه التجريبي بتصميم المجموعتين غير المتكافئتين",
    "sample_size": "بلغت عينة الدراسة 120 طالبًا وُزّعوا بالتساوي على مجموعتين",
    "sampling": "استُخدمت العينة العشوائية العنقودية في اختيار المدارس",
    "analysis_methods": "اختبار (ت) للعينات المستقلة وتحليل التباين الأحادي ومربع إيتا",
    "problem": "تدنّي مستوى مهارات التفكير الناقد لدى طلاب المرحلة الثانوية",
    "questions": "ما أثر استراتيجيات التعلّم النشط في تنمية مهارات التفكير الناقد؟",
    "objectives": "قياس أثر استراتيجيات التعلّم النشط في تنمية مهارات التفكير الناقد",
    "primary_findings": "بلغ حجم الأثر مربع إيتا 0.42 وهو حجم أثر كبير وفق معايير كوهين",
    "limitations": "اقتصرت الدراسة على طلاب المرحلة الثانوية في سياق واحد",
    "theoretical_framework": "النظرية البنائية الاجتماعية لفيجوتسكي",
}


def _principal(tenant):
    from athera_api.deps import Principal

    return Principal(user_id=tenant["user_id"], tenant_id=tenant["tenant_id"],
                     roles=["researcher"], mfa_satisfied=True, locale="ar")


# ══════════ 1. القسم المفعَّل وحده، وبمفردته القانونية ══════════

def test_the_router_reads_enabled_sections_from_the_policy_registry():
    """المفعَّل يُعلَن في **موضع واحد** — لا في المسار وحده.

    فقسمٌ يُفعَّل بتعديل سياسته، ولا يُنسى مدقّقه ولا أدواره ولا حجب أرقامه.
    """
    from athera_api.routers import manuscript_drafting as drafting
    from athera_api.services.publishing.drafting import policy

    assert drafting.ENABLED_SECTIONS is policy.ENABLED_SECTIONS
    # والمعلّق لبحث الأدبيات ليس مفعَّلًا — ولا يُكتب من ذاكرة نموذج.
    assert not (policy.ENABLED_SECTIONS & policy.PENDING_SECTIONS)
    assert "literature_review" in policy.PENDING_SECTIONS
    assert "references" in policy.PENDING_SECTIONS


def test_the_old_alias_is_refused_not_silently_accepted():
    """`methods` ليست مرادفًا مقبولًا — قبولها يعيد الانحراف الذي أُغلق."""
    from athera_api.errors import AtheraError
    from athera_api.routers import manuscript_drafting as drafting

    with pytest.raises(AtheraError) as err:
        drafting._require_enabled("methods")
    assert err.value.code == "drafting.unknown_section"


def test_a_canonical_but_disabled_section_is_refused_by_name():
    from athera_api.errors import AtheraError
    from athera_api.routers import manuscript_drafting as drafting

    with pytest.raises(AtheraError) as err:
        drafting._require_enabled("literature_review")
    assert err.value.code == "drafting.section_not_enabled"
    # ويُقال السبب: معلّقٌ لبحثٍ لم يُفعَّل، لا مرفوضٌ بلا بيان.
    assert err.value.context.get("reason")


def test_the_drafting_roles_are_derived_from_the_canonical_outline():
    """أدوار القسم تُشتقّ من الهيكل، وتوسيعها معلَن لا صامت."""
    from athera_api.services.planning import outline
    from athera_api.services.publishing.drafting import context as ctx
    from athera_api.services.publishing.drafting import policy

    outline_roles = {spec.key: spec.roles for spec in outline.DEFAULT_SECTIONS}
    for key, spec in policy.POLICIES.items():
        base = outline_roles.get(key, ())
        assert set(base) <= set(spec.roles), f"{key} فقد دورًا من الهيكل"

    roles = ctx.roles_for("method")
    assert set(outline_roles["method"]) <= set(roles)
    assert "result" not in roles, "أدلة النتائج لا تُرسل لصياغة المنهجية"


def test_no_extra_drafting_role_is_invented_outside_the_canonical_vocabulary():
    from athera_api.services.publishing.drafting import context as ctx

    canonical = set()
    for roles in ctx.ROLES_BY_SECTION.values():
        canonical.update(roles)
    canonical.update({"variable", "analysis", "result"})
    for section, extra in ctx.DRAFTING_EXTRA_ROLES.items():
        for role in extra:
            assert role in canonical, f"{section} invents the role {role!r}"


# ══════════ 2. البصمة: تتغيّر بالوقائع لا بالوقت ══════════

def _item(role, statement, memory_id=None):
    from athera_api.services.planning.context import EvidenceItem

    return EvidenceItem(memory_id or uuid.uuid4(), role, None, statement,
                        "project_decision", None, "§قسم ¶1", statement)


def _fingerprint(items, **kw):
    from athera_api.services.publishing.drafting import context as ctx

    base = dict(capability="manuscript_drafting_external_c2",
                tenant_id=uuid.UUID(int=1), project_id=uuid.UUID(int=2),
                manuscript_id=uuid.UUID(int=3), opportunity_id=uuid.UUID(int=4),
                outline_id=uuid.UUID(int=5), section_key="method",
                items=items, thread_labels=(), prior_text=None)
    base.update(kw)
    return ctx.fingerprint(**base)


def test_the_same_factual_context_yields_the_same_fingerprint():
    items = (_item("methodology", FACTS["design"]),)
    assert _fingerprint(items) == _fingerprint(items)


def test_the_fingerprint_carries_no_time():
    import inspect

    from athera_api.services.publishing.drafting import context as ctx

    source = inspect.getsource(ctx.fingerprint)
    for forbidden in ("now(", "utcnow", "time()", "datetime"):
        assert forbidden not in source, forbidden


def test_added_evidence_changes_the_fingerprint():
    one = (_item("methodology", FACTS["design"]),)
    two = one + (_item("sample", FACTS["sample_size"]),)
    assert _fingerprint(one) != _fingerprint(two)


def test_edited_evidence_changes_the_fingerprint_even_with_the_same_id():
    """تعديلُ نصّ ذاكرةٍ يُبقي معرّفها — والبصمة يجب أن ترى المحتوى."""
    memory_id = uuid.uuid4()
    before = (_item("methodology", FACTS["design"], memory_id),)
    after = (_item("methodology", FACTS["design"] + " مع مجموعة ضابطة", memory_id),)
    assert _fingerprint(before) != _fingerprint(after)


def test_a_different_section_yields_a_different_fingerprint():
    items = (_item("methodology", FACTS["design"]),)
    assert _fingerprint(items) != _fingerprint(items, section_key="results")


def test_evidence_order_does_not_change_the_fingerprint():
    a, b = _item("methodology", FACTS["design"]), _item("sample", FACTS["sample_size"])
    assert _fingerprint((a, b)) == _fingerprint((b, a))


# ══════════ 3. المخرَج لا يُصدَّق: كل معرّف يُقابل بالسياق ══════════

def _context(*items, section="method"):
    from athera_api.services.publishing.drafting.context import DraftingContext

    return DraftingContext(
        tenant_id=uuid.UUID(int=1), project_id=uuid.UUID(int=2),
        manuscript_id=uuid.UUID(int=3), opportunity_id=uuid.UUID(int=4),
        outline_id=None, section_key=section, language="ar",
        purpose_ar="المنهجية", items=tuple(items), thread_labels=(),
        missing_roles=(), fingerprint="a" * 64)


def _draft(text, claims=()):
    from athera_api.services.publishing.drafting.contracts import SectionDraft

    return SectionDraft(section_text_ar=text, claims=list(claims))


def _claim(text, *, origin="fact", memory_ids=(), claim_type="empirical"):
    from athera_api.services.publishing.drafting.contracts import DraftedClaim

    return DraftedClaim(text_ar=text, claim_type=claim_type, origin=origin,
                        memory_ids=list(memory_ids))


def test_an_invented_memory_id_is_dropped_not_repaired():
    """نموذجٌ يخترع معرّفًا يخترع سندًا — وتصحيحه يجعل الاختلاق إسنادًا."""
    from athera_api.services.publishing.drafting import generate

    item = _item("methodology", FACTS["design"])
    context = _context(item)
    invented = str(uuid.uuid4())
    draft = _draft("نصّ", [_claim("ادعاء", memory_ids=[str(item.memory_id), invented])])

    grounded, dropped = generate.ground(draft, context)
    assert grounded[0].memory_ids == [str(item.memory_id)]
    assert dropped == [invented]


def test_a_claim_referencing_only_unknown_evidence_is_flagged_blocking():
    from athera_api.services.publishing.drafting import checks

    item = _item("methodology", FACTS["design"])
    context = _context(item)
    draft = _draft(FACTS["design"], [_claim("ادعاء", memory_ids=[str(uuid.uuid4())])])
    issues = checks.run(draft, context, known_memory_ids=context.memory_ids,
                        known_output_ids=frozenset())
    keys = {i.issue_key for i in issues}
    assert "claim_references_unknown_evidence" in keys
    assert "factual_claim_without_verified_evidence" in keys


# ══════════ 4. حارس الاختلاق المنهجي ══════════

@pytest.mark.parametrize(("invention", "issue"), [
    ("استُخدمت العينة الطبقية في اختيار المدارس", "unsupported_sampling"),
    ("طُبّقت استبانة من إعداد الباحث", "unsupported_instrument"),
    ("بلغ معامل ألفا كرونباخ للأداة قيمة مرتفعة", "unsupported_reliability"),
    ("حُلّلت البيانات ببرنامج SPSS", "unsupported_software"),
    ("حصلت الدراسة على موافقة أخلاقية من لجنة الأخلاقيات", "unsupported_ethics"),
    ("اتّبعت الدراسة المنهج الوصفي المسحي", "unsupported_design"),
])
def test_a_method_detail_absent_from_the_evidence_is_refused(invention, issue):
    """الطلاقة الأكاديمية ليست إذنًا بملء الفراغ."""
    from athera_api.services.publishing.drafting import checks

    context = _context(_item("methodology", FACTS["design"]),
                       _item("sample", FACTS["sample_size"]))
    issues = checks.run(_draft(invention), context,
                        known_memory_ids=context.memory_ids,
                        known_output_ids=frozenset())
    assert issue in {i.issue_key for i in issues}, [i.issue_key for i in issues]


def test_a_method_detail_present_in_the_evidence_passes():
    """الحارس الذي يعاقب الصدق أسوأ من الحارس الذي يفوّت خطأ."""
    from athera_api.services.publishing.drafting import checks

    context = _context(_item("methodology", FACTS["design"]),
                       _item("sample", FACTS["sampling"]))
    issues = checks.run(_draft("استُخدمت العينة العشوائية العنقودية في اختيار المدارس"),
                        context, known_memory_ids=context.memory_ids,
                        known_output_ids=frozenset())
    assert [i.issue_key for i in issues] == []


def test_a_sample_number_absent_from_the_evidence_is_refused():
    from athera_api.services.publishing.drafting import checks

    context = _context(_item("sample", FACTS["sample_size"]))
    issues = checks.run(_draft("بلغت عينة الدراسة 240 طالبًا"), context,
                        known_memory_ids=context.memory_ids,
                        known_output_ids=frozenset())
    assert "unsupported_sample_number" in {i.issue_key for i in issues}


def test_the_verified_sample_number_passes():
    from athera_api.services.publishing.drafting import checks

    context = _context(_item("sample", FACTS["sample_size"]))
    issues = checks.run(_draft("بلغت عينة الدراسة 120 طالبًا"), context,
                        known_memory_ids=context.memory_ids,
                        known_output_ids=frozenset())
    assert "unsupported_sample_number" not in {i.issue_key for i in issues}


def test_a_statistic_without_an_analysis_output_is_refused():
    """المنهجية تصف الإجراء ولا تُبلّغ نتيجة — ورقمٌ هنا بلا مخرَج مرفوض."""
    from athera_api.services.publishing.drafting import checks

    context = _context(_item("methodology", FACTS["design"]))
    issues = checks.run(_draft("أظهرت النتائج فروقًا دالة (p = 0.03)"), context,
                        known_memory_ids=context.memory_ids,
                        known_output_ids=frozenset())
    assert "statistic_without_analysis_output" in {i.issue_key for i in issues}


def test_a_fabricated_citation_is_refused():
    from athera_api.services.publishing.drafting import checks

    context = _context(_item("methodology", FACTS["design"]))
    for fabricated in ("وفق ما أشار إليه (الزهراني، 2019)",
                       "as Smith et al. (2020) demonstrated",
                       "DOI: 10.1234/abcd.2021"):
        issues = checks.run(_draft(fabricated), context,
                            known_memory_ids=context.memory_ids,
                            known_output_ids=frozenset())
        assert "fabricated_citation" in {i.issue_key for i in issues}, fabricated


def test_causal_language_beyond_a_correlational_design_is_refused():
    from athera_api.services.publishing.drafting import checks

    context = _context(_item("methodology", "استخدمت الدراسة المنهج الارتباطي"))
    issues = checks.run(_draft("يؤدي التعلّم النشط إلى تحسّن التفكير الناقد"), context,
                        known_memory_ids=context.memory_ids,
                        known_output_ids=frozenset())
    assert "causal_language_beyond_design" in {i.issue_key for i in issues}


# ══════════ 5. الادعاء وحالته ══════════

def test_a_fact_without_evidence_becomes_an_evidence_gap_not_a_draft():
    """الحالة تقول الحقيقة عن واقعةٍ بلا سند بدل أن تُخفيها في «مسودة»."""
    from athera_api.services.publishing.drafting.generate import _claim_status

    assert _claim_status("fact", True) == "supported"
    assert _claim_status("fact", False) == "evidence_gap"
    assert _claim_status("inference", True) == "draft"
    assert _claim_status("proposal", False) == "draft"


def test_the_contract_makes_missing_evidence_a_first_class_answer():
    """«لا أعرف» مخرَجٌ صالح — فلا يُدفع النموذج إلى ملء الفراغ."""
    from athera_api.services.publishing.drafting.contracts import SectionDraft

    fields = SectionDraft.model_fields
    assert "missing_evidence" in fields
    assert "origin" in __import__(
        "athera_api.services.publishing.drafting.contracts",
        fromlist=["DraftedClaim"]).DraftedClaim.model_fields


def test_the_instruction_forbids_invention_by_name():
    from athera_api.services.publishing.drafting import generate

    for forbidden in ("تصميمًا", "معاينة", "أداة", "حجم عينة", "ثبات", "أخلاقية",
                      "مرجع", "سببية"):
        assert forbidden in generate.INSTRUCTION, forbidden


def test_the_prompt_carries_only_the_section_context():
    """أقلّ سياق لازم — ولا معرّف ملف ولا رابط تخزين ولا أدلة أقسام أخرى."""
    import json

    from athera_api.services.publishing.drafting import generate

    context = _context(_item("methodology", FACTS["design"]))
    payload = json.loads(generate.build_prompt(context))
    assert set(payload) == {"section_key", "section_purpose_ar", "language",
                            "evidence", "thread_elements_ar", "allowed_memory_ids",
                            "analysis_outputs", "allowed_analysis_output_ids"}
    # والمنهجية بلا مخرجات: القائمة موجودة وفارغة، فلا يظنّها النموذج محجوبة.
    assert payload["analysis_outputs"] == []
    blob = json.dumps(payload, ensure_ascii=False)
    for leaked in ("source_file_id", "storage_key", "https://", "Bearer", "sk-"):
        assert leaked not in blob, leaked


# ══════════ 6. الإذن: قدرة S5D لا تأذن لـS5E ══════════

@requires_db
@pytest.mark.asyncio
async def test_planning_consent_does_not_authorize_drafting(two_tenants):
    """أخطر التباس في هذه المرحلة: إذنٌ يُقرأ لغير ما أُعطي له."""
    from athera_api.db import tenant_session
    from athera_api.services import consent

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    project_id, manuscript_id, _ = await _seed_manuscript(tid, uid)
    fingerprint = "b" * 64

    async with tenant_session(tid, uid) as session:
        await consent.record_planning_decision(
            session, tenant_id=tid, project_id=project_id, actor_user_id=uid,
            granted=True, provider="anthropic", model="m",
            context_fingerprint=fingerprint, evidence_count=4)

    async with tenant_session(tid, uid) as session:
        assert await consent.drafting_authorization(
            session, tenant_id=tid, manuscript_id=manuscript_id,
            context_fingerprint=fingerprint) is None
        assert await consent.drafting_state(
            session, tenant_id=tid, manuscript_id=manuscript_id,
            context_fingerprint=fingerprint) == consent.ABSENT


@requires_db
@pytest.mark.asyncio
async def test_changed_evidence_makes_drafting_consent_stale(two_tenants):
    from athera_api.db import tenant_session
    from athera_api.services import consent

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    _project, manuscript_id, _ = await _seed_manuscript(tid, uid)

    async with tenant_session(tid, uid) as session:
        await consent.record_drafting_decision(
            session, tenant_id=tid, manuscript_id=manuscript_id, section_key="method",
            actor_user_id=uid, granted=True, provider="anthropic", model="m",
            context_fingerprint="c" * 64, evidence_count=3)

    async with tenant_session(tid, uid) as session:
        assert await consent.drafting_state(
            session, tenant_id=tid, manuscript_id=manuscript_id,
            context_fingerprint="c" * 64) == consent.GRANTED
        # أدلةٌ تغيّرت ⇒ بصمةٌ أخرى ⇒ ليست رفضًا وليست إذنًا.
        assert await consent.drafting_state(
            session, tenant_id=tid, manuscript_id=manuscript_id,
            context_fingerprint="d" * 64) == consent.STALE
        assert await consent.drafting_authorization(
            session, tenant_id=tid, manuscript_id=manuscript_id,
            context_fingerprint="d" * 64) is None


# ══════════ 7. المسار الحقيقي ══════════

async def _seed_manuscript(tid, uid, *, facts=None):
    """مشروع بأدلة موثقة، وفرصة مختارة، ومخطوطة مربوطة بها."""
    import datetime as dt

    from athera_api.db import tenant_session
    from athera_api.models.publishing import Manuscript, ManuscriptVersion
    from athera_api.models.thesis import PublicationOpportunity
    from tests.test_at_s5d_publication_planning import _seed_project_with_memory

    project_id, _memory, _file = await _seed_project_with_memory(
        tid, uid, facts=facts or FACTS)
    async with tenant_session(tid, uid) as session:
        opportunity = PublicationOpportunity(
            tenant_id=tid, project_id=project_id,
            opportunity_kind="independent_question", paper_kind="extraction",
            working_title_ar="أثر التعلّم النشط في التفكير الناقد",
            research_question_ar="ما أثر استراتيجيات التعلّم النشط؟",
            status="discovered", planning_status="selected",
            planning_decided_by=uid, planning_decided_at=dt.datetime.now(dt.UTC),
            readiness_components={"proposal": {"contribution_ar": "مساهمة"}})
        session.add(opportunity)
        await session.flush()
        record = Manuscript(
            tenant_id=tid, project_id=project_id, title_ar="مخطوطة",
            language="ar", status="draft", opportunity_id=opportunity.id)
        session.add(record)
        await session.flush()
        version = ManuscriptVersion(
            tenant_id=tid, manuscript_id=record.id, version_label="v1",
            created_by=uid, change_reason_ar="النسخة الأولى")
        session.add(version)
        await session.flush()
        record.current_version_id = version.id
        return project_id, record.id, opportunity.id


def _draft_json() -> dict:
    return {
        "section_text_ar": (
            "استخدمت الدراسة المنهج شبه التجريبي بتصميم المجموعتين غير المتكافئتين. "
            "وبلغت عينة الدراسة 120 طالبًا وُزّعوا بالتساوي على مجموعتين، "
            "واستُخدمت العينة العشوائية العنقودية في اختيار المدارس."
        ),
        "claims": [
            {"text_ar": "تصميم الدراسة شبه تجريبي بمجموعتين غير متكافئتين",
             "claim_type": "empirical", "origin": "fact",
             "memory_ids": ["__DESIGN__"], "analysis_output_ids": [],
             "support_level": "direct"},
        ],
        "missing_evidence": [
            {"topic_ar": "إجراءات الصدق والثبات للأداة", "why_ar": "لا ترد في المادة الموثقة"},
        ],
        "warnings_ar": [],
    }


@requires_db
@pytest.mark.asyncio
async def test_drafting_without_consent_makes_zero_provider_calls(two_tenants, monkeypatch):
    """الإذن يسبق النداء — ولا رمز يُنفق على طلبٍ غير مأذون."""
    from athera_api.errors import AtheraError
    from athera_api.providers import gateway as gateway_module
    from athera_api.routers import manuscript_drafting as drafting

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    _project, manuscript_id, _opp = await _seed_manuscript(tid, uid)

    calls: list = []
    monkeypatch.setattr(gateway_module, "build_provider",
                        lambda: calls.append(1) or (_ for _ in ()).throw(AssertionError))

    with pytest.raises(AtheraError) as err:
        await drafting.draft_section(manuscript_id, "method",
                                     principal=_principal(tenant))
    assert err.value.code == "drafting.consent_required"
    assert calls == [], "استُدعي المزوّد بلا إذن"


@requires_db
@pytest.mark.asyncio
async def test_the_whole_methods_path_runs_through_the_real_orchestrator(
        two_tenants, monkeypatch):
    """المسار الحقيقي حتى `get_agent` — والتزييف عند حدّ المزوّد وحده (§31)."""
    from athera_api.db import tenant_session
    from athera_api.providers import gateway as gateway_module
    from athera_api.providers.base import ModelResponse, ModelUsage
    from athera_api.routers import manuscript_drafting as drafting
    from athera_api.schemas.drafting import DraftingConsentDecision
    from athera_api.services import consent

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    _project, manuscript_id, _opp = await _seed_manuscript(tid, uid)
    principal = _principal(tenant)

    async with tenant_session(tid, uid) as session:
        view = await drafting.drafting_context_state(
            manuscript_id, "method", principal=principal, session=session)
    assert view.sufficient, view.missing_roles
    assert view.consent_state == consent.ABSENT
    design_id = next(str(e.memory_id) for e in view.evidence if e.role == "methodology")

    async with tenant_session(tid, uid) as session:
        await drafting.drafting_consent(
            manuscript_id, "method",
            DraftingConsentDecision(decision="grant",
                                    context_fingerprint=view.fingerprint),
            principal=principal, session=session)

    seen: dict = {}
    payload = _draft_json()
    payload["claims"][0]["memory_ids"] = [design_id]

    class _FakeProvider:
        name = "anthropic"

        async def generate_structured(self, request):
            seen["classification"] = request.classification
            # الرسائل كائنات `Message` لا قواميس — والنصّ في `content`.
            seen["prompt"] = " ".join(getattr(m, "content", "") or ""
                                      for m in request.messages)
            return ModelResponse(content="", provider="anthropic", model="fake-model",
                                 structured=payload,
                                 usage=ModelUsage(input_tokens=10, output_tokens=10,
                                                  latency_ms=1))

        async def embed(self, texts): ...
        async def stream(self, request): ...
        async def tool_call(self, request): ...

    monkeypatch.setattr(gateway_module, "build_provider", lambda: _FakeProvider())
    result = await drafting.draft_section(manuscript_id, "method", principal=principal)

    assert seen.get("classification") == "C2", "لم يبلغ الطلب المزوّد"
    # §10 — أدلة النتائج لم تُرسل لصياغة المنهجية.
    assert FACTS["primary_findings"] not in seen["prompt"]

    # §24 — التوليد ليس اعتمادًا.
    assert result.review_status == "needs_review"
    assert result.reviewed_at is None
    assert result.claims and result.claims[0].evidence, "ادعاء بلا رابط دليل"
    assert str(result.claims[0].evidence[0].memory_id) == design_id
    assert result.claims[0].evidence[0].locator, "الرابط بلا إسناد"

    # والأجنت المستعمل مسجَّل فعلًا.
    from athera_api.brain.agents import get_agent

    assert get_agent("scientific_writer").allowed_tools == frozenset()


@requires_db
@pytest.mark.asyncio
async def test_drafting_creates_no_verified_memory(two_tenants, monkeypatch):
    """§30 — المسودة لا تصير معرفةً موثقة، ولا ادعاءٌ يترقّى بلا مسار §7.4."""
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.research import ResearcherMemory
    from athera_api.providers import gateway as gateway_module
    from athera_api.providers.base import ModelResponse, ModelUsage
    from athera_api.routers import manuscript_drafting as drafting
    from athera_api.schemas.drafting import DraftingConsentDecision

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    _project, manuscript_id, _opp = await _seed_manuscript(tid, uid)
    principal = _principal(tenant)

    async def _verified() -> int:
        async with tenant_session(tid, uid) as session:
            return (await session.execute(
                select(func.count(ResearcherMemory.id)).where(
                    ResearcherMemory.tenant_id == tid,
                    ResearcherMemory.verification_status == "verified"))).scalar_one()

    before = await _verified()
    async with tenant_session(tid, uid) as session:
        view = await drafting.drafting_context_state(
            manuscript_id, "method", principal=principal, session=session)
        await drafting.drafting_consent(
            manuscript_id, "method",
            DraftingConsentDecision(decision="grant",
                                    context_fingerprint=view.fingerprint),
            principal=principal, session=session)

    payload = _draft_json()
    payload["claims"][0]["memory_ids"] = [
        str(next(e.memory_id for e in view.evidence if e.role == "methodology"))]

    class _FakeProvider:
        name = "anthropic"

        async def generate_structured(self, request):
            return ModelResponse(content="", provider="anthropic", model="fake",
                                 structured=payload,
                                 usage=ModelUsage(input_tokens=1, output_tokens=1,
                                                  latency_ms=1))

        async def embed(self, texts): ...
        async def stream(self, request): ...
        async def tool_call(self, request): ...

    monkeypatch.setattr(gateway_module, "build_provider", lambda: _FakeProvider())
    await drafting.draft_section(manuscript_id, "method", principal=principal)
    assert await _verified() == before, "ترقّت ذاكرة موثقة تلقائيًّا"


@requires_db
@pytest.mark.asyncio
async def test_no_transaction_spans_the_provider_wait(two_tenants, monkeypatch):
    """الدرس المثبَت إنتاجيًّا: لا معاملة مفتوحة أثناء انتظار المزوّد."""
    import asyncio

    from sqlalchemy import text

    from athera_api.db import tenant_session
    from athera_api.providers import gateway as gateway_module
    from athera_api.providers.base import ModelResponse, ModelUsage
    from athera_api.routers import manuscript_drafting as drafting
    from athera_api.schemas.drafting import DraftingConsentDecision

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    _project, manuscript_id, _opp = await _seed_manuscript(tid, uid)
    principal = _principal(tenant)

    async with tenant_session(tid, uid) as session:
        view = await drafting.drafting_context_state(
            manuscript_id, "method", principal=principal, session=session)
        await drafting.drafting_consent(
            manuscript_id, "method",
            DraftingConsentDecision(decision="grant",
                                    context_fingerprint=view.fingerprint),
            principal=principal, session=session)

    payload = _draft_json()
    payload["claims"][0]["memory_ids"] = [
        str(next(e.memory_id for e in view.evidence if e.role == "methodology"))]
    observed: list[int] = []

    class _SlowProvider:
        name = "anthropic"

        async def generate_structured(self, request):
            # أثناء الانتظار: كم معاملة مفتوحة لهذا الدور؟
            async with tenant_session(tid, uid) as probe:
                observed.append((await probe.execute(text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE state = 'idle in transaction'"))).scalar_one())
            await asyncio.sleep(0.05)
            return ModelResponse(content="", provider="anthropic", model="fake",
                                 structured=payload,
                                 usage=ModelUsage(input_tokens=1, output_tokens=1,
                                                  latency_ms=50))

        async def embed(self, texts): ...
        async def stream(self, request): ...
        async def tool_call(self, request): ...

    monkeypatch.setattr(gateway_module, "build_provider", lambda: _SlowProvider())
    await drafting.draft_section(manuscript_id, "method", principal=principal)
    # المعاملة الوحيدة المفتوحة هي معاملة الفحص نفسها.
    assert observed and max(observed) <= 1, f"معاملة عالقة أثناء النداء: {observed}"


@requires_db
@pytest.mark.asyncio
async def test_an_approved_section_is_not_silently_overwritten(two_tenants, monkeypatch):
    """§26 — نصٌّ اعتمده الباحث لا يُستبدل بنداءٍ عادي."""
    from athera_api.db import tenant_session
    from athera_api.errors import AtheraError
    from athera_api.providers import gateway as gateway_module
    from athera_api.providers.base import ModelResponse, ModelUsage
    from athera_api.routers import manuscript_drafting as drafting
    from athera_api.schemas.drafting import DraftingConsentDecision, SectionReviewDecision

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    _project, manuscript_id, _opp = await _seed_manuscript(tid, uid)
    principal = _principal(tenant)

    async with tenant_session(tid, uid) as session:
        view = await drafting.drafting_context_state(
            manuscript_id, "method", principal=principal, session=session)
        await drafting.drafting_consent(
            manuscript_id, "method",
            DraftingConsentDecision(decision="grant",
                                    context_fingerprint=view.fingerprint),
            principal=principal, session=session)

    payload = _draft_json()
    payload["claims"][0]["memory_ids"] = [
        str(next(e.memory_id for e in view.evidence if e.role == "methodology"))]

    class _FakeProvider:
        name = "anthropic"

        async def generate_structured(self, request):
            return ModelResponse(content="", provider="anthropic", model="fake",
                                 structured=payload,
                                 usage=ModelUsage(input_tokens=1, output_tokens=1,
                                                  latency_ms=1))

        async def embed(self, texts): ...
        async def stream(self, request): ...
        async def tool_call(self, request): ...

    monkeypatch.setattr(gateway_module, "build_provider", lambda: _FakeProvider())
    first = await drafting.draft_section(manuscript_id, "method", principal=principal)
    assert first.review_status == "needs_review"

    async with tenant_session(tid, uid) as session:
        approved = await drafting.review_section(
            manuscript_id, "method", SectionReviewDecision(decision="approve"),
            principal=principal, session=session)
    assert approved.review_status == "approved"
    assert approved.reviewed_at is not None

    with pytest.raises(AtheraError) as err:
        await drafting.draft_section(manuscript_id, "method", principal=principal)
    assert err.value.code == "drafting.section_approved"

    # والنصّ المعتمد باقٍ كما هو.
    async with tenant_session(tid, uid) as session:
        still = await drafting.read_section(manuscript_id, "method",
                                            principal=principal, session=session)
    assert still.review_status == "approved"
    assert still.text_ar == approved.text_ar


@requires_db
@pytest.mark.asyncio
async def test_regeneration_creates_a_new_version_and_keeps_history(
        two_tenants, monkeypatch):
    """§27 — كل صياغة نسخةٌ في النظام القائم، ولا جدول مراجعات ثانٍ."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.publishing import ManuscriptVersion
    from athera_api.providers import gateway as gateway_module
    from athera_api.providers.base import ModelResponse, ModelUsage
    from athera_api.routers import manuscript_drafting as drafting
    from athera_api.schemas.drafting import DraftingConsentDecision

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    _project, manuscript_id, _opp = await _seed_manuscript(tid, uid)
    principal = _principal(tenant)

    async with tenant_session(tid, uid) as session:
        view = await drafting.drafting_context_state(
            manuscript_id, "method", principal=principal, session=session)
        await drafting.drafting_consent(
            manuscript_id, "method",
            DraftingConsentDecision(decision="grant",
                                    context_fingerprint=view.fingerprint),
            principal=principal, session=session)

    payload = _draft_json()
    payload["claims"][0]["memory_ids"] = [
        str(next(e.memory_id for e in view.evidence if e.role == "methodology"))]

    class _FakeProvider:
        name = "anthropic"

        async def generate_structured(self, request):
            return ModelResponse(content="", provider="anthropic", model="fake",
                                 structured=payload,
                                 usage=ModelUsage(input_tokens=1, output_tokens=1,
                                                  latency_ms=1))

        async def embed(self, texts): ...
        async def stream(self, request): ...
        async def tool_call(self, request): ...

    monkeypatch.setattr(gateway_module, "build_provider", lambda: _FakeProvider())
    first = await drafting.draft_section(manuscript_id, "method", principal=principal)
    second = await drafting.draft_section(manuscript_id, "method", principal=principal)

    assert first.version_label != second.version_label
    async with tenant_session(tid, uid) as session:
        versions = (await session.execute(
            select(ManuscriptVersion).where(
                ManuscriptVersion.manuscript_id == manuscript_id,
                ManuscriptVersion.tenant_id == tid)
            .order_by(ManuscriptVersion.created_at))).scalars().all()
    assert len(versions) >= 2
    assert versions[-1].supersedes_id == versions[-2].id, "سلسلة الخلافة انقطعت"
    assert versions[-1].change_reason_ar, "نسخة بلا سبب مكتوب"


# ══════════ 8. العزل ══════════

@requires_db
@pytest.mark.asyncio
async def test_tenant_b_cannot_draft_or_read_tenant_a_methods(two_tenants):
    from athera_api.db import tenant_session
    from athera_api.errors import NotFound
    from athera_api.routers import manuscript_drafting as drafting
    from athera_api.schemas.drafting import DraftingConsentDecision, SectionReviewDecision

    a, b = two_tenants["a"], two_tenants["b"]
    _project, manuscript_a, _opp = await _seed_manuscript(a["tenant_id"], a["user_id"])

    async with tenant_session(b["tenant_id"], b["user_id"]) as session:
        for call in (
            drafting.drafting_context_state(manuscript_a, "method",
                                            principal=_principal(b), session=session),
            drafting.read_section(manuscript_a, "method",
                                  principal=_principal(b), session=session),
            drafting.drafting_consent(
                manuscript_a, "method",
                DraftingConsentDecision(decision="grant", context_fingerprint="e" * 64),
                principal=_principal(b), session=session),
            drafting.review_section(
                manuscript_a, "method", SectionReviewDecision(decision="approve"),
                principal=_principal(b), session=session),
        ):
            with pytest.raises(NotFound):
                await call

    with pytest.raises(NotFound):
        await drafting.draft_section(manuscript_a, "method", principal=_principal(b))


# ══════════ 9. سجلّ واحد للسقوف — لا نسختان تفترقان ══════════

def test_the_consent_ceilings_are_derived_from_the_gateway_registry():
    """السلطة عند البوابة، وموافقاتُ الخدمات تقرأ منها ولا تعيد كتابتها.

    كانتا خريطتين للحقيقة نفسها، فأُضيفت قدرة الصياغة في إحداهما دون
    الأخرى: صار الإذن صحيحًا والبوابة ترفض `C2`، والرسالة تقول
    «disabled_for_classification» بينما الباحث أذن فعلًا.
    """
    import inspect

    from athera_api.providers import gateway
    from athera_api.services import consent

    assert consent.CAPABILITY_CEILING == dict(gateway._CAPABILITY_CEILINGS)
    # ومشتقّة فعلًا لا منسوخة: لا قيمة تصنيف مكتوبة بجانب اسم قدرة.
    source = inspect.getsource(consent)
    block = source[source.index("CAPABILITY_CEILING:"):source.index("GATE: Final")]
    assert "capability_ceiling(" in block
    assert '"C2"' not in block, "سقفٌ مكتوب بجانب اسمه بدل أن يُشتقّ"


def test_every_declared_capability_can_actually_leave_the_gateway():
    """كل قدرة معلَنة في الموافقات تعرفها البوابة — وإلا فالإذن بلا أثر."""
    from athera_api.providers.gateway import capability_ceiling
    from athera_api.services import consent

    for capability in (consent.CAPABILITY, consent.PLANNING_CAPABILITY,
                       consent.DRAFTING_CAPABILITY):
        assert capability_ceiling(capability) == "C2", capability


# ══════════ 10. ما كشفه أول نداء إنتاجي حقيقي ══════════

def test_a_transport_envelope_is_unwrapped_whatever_its_name():
    """نداءٌ إنتاجي أعاد `{"parameters": {...}}` ثم آخر أعاد `{"answer_ar": {...}}`.

    والقاعدة بنيوية لا بالاسم: قائمةُ أسماء تلاحق سلوكًا غير حتمي تخسر
    السباق. فالسؤال: هل الداخل هو العقد والخارج ليس كذلك؟
    """
    from athera_api.brain.contracts import parse_contract
    from athera_api.services.publishing.drafting.contracts import SectionDraft

    inner = {"section_text_ar": "نصّ المنهجية", "claims": [], "missing_evidence": []}
    for envelope in ("parameters", "arguments", "input", "answer_ar", "result", "خلاصة"):
        parsed = parse_contract(SectionDraft, {envelope: inner})
        assert parsed.section_text_ar == "نصّ المنهجية", envelope


def test_unwrapping_never_becomes_repair():
    """الترميم يخترع قيمة؛ وهذا يزيل غلافًا لا يحمل معلومة — ولا يتجاوز ذلك."""
    from athera_api.brain.contracts import ContractViolation, parse_contract
    from athera_api.services.publishing.drafting.contracts import SectionDraft

    # مفتاحان: ليس غلافًا.
    with pytest.raises(ContractViolation):
        parse_contract(SectionDraft, {"parameters": {"section_text_ar": "نصّ"},
                                      "extra": 1})
    # وغلافٌ فارغ لا يصير محتوى.
    with pytest.raises(ContractViolation):
        parse_contract(SectionDraft, {"parameters": {}})
    # وغلافٌ حول محتوى لا يطابق العقد يسقط، ورسالة الخطأ عن العقد.
    with pytest.raises(ContractViolation, match="does not match contract"):
        parse_contract(SectionDraft, {"parameters": {"wrong_field": 1}})


def test_an_envelope_name_that_is_a_real_field_is_never_stripped():
    """المحتوى يسبق الغلاف: عقدٌ يعلن الاسم يحتفظ به."""
    from pydantic import BaseModel

    from athera_api.brain.contracts import parse_contract

    class WithField(BaseModel):
        parameters: dict

    parsed = parse_contract(WithField, {"parameters": {"a": 1}})
    assert parsed.parameters == {"a": 1}


@requires_db
@pytest.mark.asyncio
async def test_a_contract_violation_survives_its_own_transaction(two_tenants, monkeypatch):
    """سجلّ الفشل كان يبتلع نفسه — والإنتاج أثبته: تشغيلة علِقت `running`.

    كل `raise` كان يقع داخل `async with`، فيُلغي المعاملة التي كتب فيها
    فشله للتوّ. وهو العطب الذي أصلحه S5C في مسار المستندات، عاد في المسار
    المنفصل.
    """
    from sqlalchemy import select

    from athera_api.brain.contracts import ContractViolation
    from athera_api.brain.orchestrator import Orchestrator
    from athera_api.db import tenant_session
    from athera_api.models.runs import AgentRun
    from athera_api.providers import gateway as gateway_module
    from athera_api.providers.base import ModelResponse, ModelUsage
    from athera_api.services.publishing.drafting.contracts import SectionDraft

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]

    class _BadProvider:
        name = "anthropic"

        async def generate_structured(self, request):
            # مخرَجٌ لا يطابق العقد ولا هو غلافٌ معروف.
            return ModelResponse(content="", provider="anthropic", model="fake",
                                 structured={"unexpected": {"shape": True}},
                                 usage=ModelUsage(input_tokens=1, output_tokens=1,
                                                  latency_ms=1))

        async def embed(self, texts): ...
        async def stream(self, request): ...
        async def tool_call(self, request): ...

    monkeypatch.setattr(gateway_module, "build_provider", lambda: _BadProvider())

    def _maker():
        return tenant_session(tid, uid)

    with pytest.raises(ContractViolation):
        await Orchestrator().run_structured_detached(
            _maker, tenant_id=tid, actor_user_id=uid, agent_key="scientific_writer",
            contract=SectionDraft, instruction="x", payload="{}",
            input_classification="C1", output_locale="ar")

    async with tenant_session(tid, uid) as session:
        run = (await session.execute(
            select(AgentRun).where(AgentRun.tenant_id == tid,
                                   AgentRun.agent_key == "scientific_writer")
            .order_by(AgentRun.started_at.desc()).limit(1))).scalar_one()
    assert run.status == "failed", "التشغيلة بقيت `running` — الفشل لم يُودَع"
    assert run.error and "ContractViolation" in run.error
    assert run.finished_at is not None
