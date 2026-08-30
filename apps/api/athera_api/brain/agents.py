"""سجل الأجنتات | Agent registry (§8).

جدول §8 يعطي كل أجنت مسؤولية **وقيدًا**. القيد هو ما يحمي المنتج، والقيد
المكتوب في تعليمات النموذج ليس قيدًا بل رجاء. لذلك كل أجنت هنا يعلن:

  • الأدوات المسموح له باستدعائها — وما ليس في القائمة لا يُستدعى.
  • الحواجز المطبَّقة على مخرجاته — فحوص حتمية بعد التوليد.
  • فئات الذاكرة التي يقرأها — والذاكرة الموثقة فقط تدخل السياق.

ولا أجنت واحد يملك صلاحية كتابة ذاكرة موثقة أو البت في اعتماد. تلك
صلاحية إنسان (§4 Human-in-the-Loop).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final


@dataclass(frozen=True, slots=True)
class AgentSpec:
    key: str
    name_ar: str
    name_en: str
    responsibility_ar: str
    responsibility_en: str
    # القيد كما ورد نصًا في §8 — يبقى مرئيًا في السجل وفي واجهة التفتيش.
    constraint_ar: str
    constraint_en: str
    allowed_tools: frozenset[str] = field(default_factory=frozenset)
    guards: frozenset[str] = field(default_factory=frozenset)
    reads_memory: frozenset[str] = field(default_factory=frozenset)
    # البوابة التي يحتاجها عمل هذا الأجنت قبل أن يُعتمد مخرجه (§9).
    gate: str | None = None


# حواجز تنطبق على كل أجنت بلا استثناء.
BASE_GUARDS: Final = frozenset({
    "citations_must_be_grounded",
    "no_self_verification",
    "no_acceptance_guarantee",
})

_VERIFIED_MEMORY: Final = frozenset({
    "researcher_fact", "promotion_policy", "verified_evidence",
    "project_decision", "journal_fact", "analysis_result",
})

AGENTS: Final[dict[str, AgentSpec]] = {
    spec.key: spec
    for spec in (
        AgentSpec(
            key="research_manager",
            name_ar="مدير البحث", name_en="Research Manager",
            responsibility_ar="إدارة المشروع والحالة والخطوات",
            responsibility_en="Manage the project, its state and next steps",
            constraint_ar="لا يتجاوز الاعتمادات",
            constraint_en="Never bypasses approvals",
            allowed_tools=frozenset({"memory.search_verified", "profile.read", "facts.list_pending"}),
            guards=BASE_GUARDS,
            reads_memory=_VERIFIED_MEMORY,
        ),
        AgentSpec(
            key="promotion_auditor",
            name_ar="مدقق الترقية", name_en="Promotion Auditor",
            responsibility_ar="تحليل اللائحة وحساب الفجوة",
            responsibility_en="Analyse the policy and compute the gap",
            constraint_ar="لا يفترض قاعدة غير موثقة",
            constraint_en="Never assumes an undocumented rule",
            allowed_tools=frozenset({"memory.search_verified", "profile.read"}),
            guards=BASE_GUARDS | {"numbers_require_analysis_run"},
            reads_memory=frozenset({"promotion_policy", "researcher_fact", "verified_evidence"}),
            gate="G0",
        ),
        AgentSpec(
            key="opportunity_scout",
            name_ar="مستكشف الفرص", name_en="Opportunity Scout",
            responsibility_ar="اكتشاف الأفكار والفجوات",
            responsibility_en="Discover ideas and research gaps",
            constraint_ar="لا يختلق اتجاهات أو دراسات",
            constraint_en="Never invents trends or studies",
            allowed_tools=frozenset({"memory.search_verified", "profile.read"}),
            guards=BASE_GUARDS,
            reads_memory=_VERIFIED_MEMORY,
            gate="G1",
        ),
        AgentSpec(
            key="literature_agent",
            name_ar="أجنت الأدبيات", name_en="Literature Agent",
            responsibility_ar="البحث والاسترجاع",
            responsibility_en="Search and retrieval",
            constraint_ar="يميز Metadata عن Full Text",
            constraint_en="Distinguishes metadata from full text",
            allowed_tools=frozenset({"memory.search_verified"}),
            guards=BASE_GUARDS,
            reads_memory=frozenset({"verified_evidence", "journal_fact"}),
        ),
        AgentSpec(
            key="evidence_curator",
            name_ar="أمين الأدلة", name_en="Evidence Curator",
            responsibility_ar="التحقق من المراجع والأدلة",
            responsibility_en="Verify references and evidence",
            constraint_ar="لا يعتمد مصدرًا غير متحقق",
            constraint_en="Never relies on an unverified source",
            allowed_tools=frozenset({"memory.search_verified"}),
            guards=BASE_GUARDS,
            reads_memory=frozenset({"verified_evidence"}),
        ),
        AgentSpec(
            key="golden_thread_agent",
            name_ar="أجنت الخيط الذهبي", name_en="Golden Thread Agent",
            responsibility_ar="ربط المشكلة والأسئلة والمنهج والنتائج",
            responsibility_en="Link problem, questions, method and results",
            constraint_ar="لا يغير عناصر معتمدة صامتًا",
            constraint_en="Never silently alters approved elements",
            allowed_tools=frozenset({"memory.search_verified"}),
            guards=BASE_GUARDS | {"numbers_require_analysis_run"},
            reads_memory=frozenset({"project_decision", "analysis_result", "verified_evidence"}),
        ),
        AgentSpec(
            key="theory_agent",
            name_ar="أجنت النظرية", name_en="Theory Agent",
            responsibility_ar="اقتراح الإطار النظري",
            responsibility_en="Propose the theoretical framework",
            constraint_ar="يوضح البدائل والقيود",
            constraint_en="States alternatives and limitations",
            allowed_tools=frozenset({"memory.search_verified"}),
            guards=BASE_GUARDS,
            reads_memory=frozenset({"verified_evidence", "project_decision"}),
            gate="G3",
        ),
        AgentSpec(
            key="methodology_agent",
            name_ar="أجنت المنهجية", name_en="Methodology Agent",
            responsibility_ar="التصميم والعينة والأداة",
            responsibility_en="Design, sampling and instrument",
            constraint_ar="لا يفرض منهجًا لا يجيب عن السؤال",
            constraint_en="Never imposes a method that does not answer the question",
            allowed_tools=frozenset({"memory.search_verified"}),
            guards=BASE_GUARDS | {"numbers_require_analysis_run"},
            reads_memory=frozenset({"project_decision", "verified_evidence"}),
            gate="G4",
        ),
        AgentSpec(
            key="ethics_agent",
            name_ar="أجنت الأخلاقيات", name_en="Ethics Agent",
            responsibility_ar="الأخلاقيات والموافقات والخصوصية",
            responsibility_en="Ethics, consent and privacy",
            constraint_ar="يمنع تجاوز الموافقات",
            constraint_en="Prevents bypassing approvals",
            allowed_tools=frozenset({"memory.search_verified"}),
            guards=BASE_GUARDS,
            reads_memory=frozenset({"project_decision"}),
            gate="G4",
        ),
        AgentSpec(
            key="data_agent",
            name_ar="أجنت البيانات", name_en="Data Agent",
            responsibility_ar="جودة البيانات وإصداراتها",
            responsibility_en="Data quality and versioning",
            constraint_ar="لا يعدل Raw Data",
            constraint_en="Never modifies raw data",
            # لا توجد في سجل الأدوات أصلًا أداة تعدّل بيانات خامًا (AT-S2-03).
            allowed_tools=frozenset({"memory.search_verified"}),
            guards=BASE_GUARDS | {"numbers_require_analysis_run"},
            reads_memory=frozenset({"analysis_result"}),
            gate="G6",
        ),
        AgentSpec(
            key="analysis_agent",
            name_ar="أجنت التحليل", name_en="Analysis Agent",
            responsibility_ar="تنفيذ التحليل الموثق",
            responsibility_en="Execute documented analysis",
            constraint_ar="لا ينشئ أرقامًا تخمينية",
            constraint_en="Never produces guessed numbers",
            allowed_tools=frozenset({"memory.search_verified"}),
            guards=BASE_GUARDS | {"numbers_require_analysis_run"},
            reads_memory=frozenset({"analysis_result"}),
            gate="G7",
        ),
        AgentSpec(
            key="scientific_writer",
            name_ar="الكاتب العلمي", name_en="Scientific Writer",
            responsibility_ar="صياغة الورقة من مصادر معتمدة",
            responsibility_en="Draft the paper from approved sources",
            constraint_ar="لا يكتب نتائج غير موجودة",
            constraint_en="Never writes results that do not exist",
            allowed_tools=frozenset({"memory.search_verified"}),
            guards=BASE_GUARDS | {"numbers_require_analysis_run"},
            reads_memory=_VERIFIED_MEMORY,
            gate="G9",
        ),
        AgentSpec(
            key="journal_matcher",
            name_ar="مطابق المجلات", name_en="Journal Matcher",
            responsibility_ar="مطابقة المجلات",
            responsibility_en="Match journals",
            constraint_ar="لا يضمن القبول",
            constraint_en="Never guarantees acceptance",
            allowed_tools=frozenset({"memory.search_verified"}),
            guards=BASE_GUARDS,
            reads_memory=frozenset({"journal_fact", "project_decision"}),
            gate="G10",
        ),
        AgentSpec(
            key="peer_review_council",
            name_ar="مجلس المحكّمين", name_en="Peer Review Council",
            responsibility_ar="مراجعة نظرية ومنهجية وإحصائية وتحريرية",
            responsibility_en="Theoretical, methodological, statistical and editorial review",
            constraint_ar="لا يعدل النسخة النهائية دون قرار",
            constraint_en="Never edits the final version without a decision",
            allowed_tools=frozenset({"memory.search_verified"}),
            guards=BASE_GUARDS | {"numbers_require_analysis_run"},
            reads_memory=_VERIFIED_MEMORY,
        ),
        AgentSpec(
            key="revision_agent",
            name_ar="أجنت التعديلات", name_en="Revision Agent",
            responsibility_ar="إدارة ردود المحكمين",
            responsibility_en="Manage reviewer responses",
            constraint_ar="لا يدعي تنفيذ تعديل غير منفذ",
            constraint_en="Never claims a revision that was not applied",
            allowed_tools=frozenset({"memory.search_verified"}),
            guards=BASE_GUARDS,
            reads_memory=frozenset({"project_decision"}),
            gate="G12",
        ),
        AgentSpec(
            key="thesis_miner",
            name_ar="منقّب الرسائل", name_en="Thesis Miner",
            responsibility_ar="استخراج فرص النشر من الرسائل",
            responsibility_en="Mine publication opportunities from theses",
            constraint_ar="يمنع النشر المكرر والتجزئة المفرطة",
            constraint_en="Prevents duplicate publication and salami slicing",
            allowed_tools=frozenset({"memory.search_verified"}),
            guards=BASE_GUARDS,
            reads_memory=_VERIFIED_MEMORY,
            gate="GT1",
        ),
        AgentSpec(
            key="authorship_agent",
            name_ar="أجنت التأليف", name_en="Authorship Agent",
            responsibility_ar="إدارة المساهمات والموافقات",
            responsibility_en="Manage contributions and consents",
            constraint_ar="لا يمنح التأليف تلقائيًا",
            constraint_en="Never assigns authorship automatically",
            allowed_tools=frozenset({"memory.search_verified"}),
            guards=BASE_GUARDS | {"authorship_needs_human"},
            reads_memory=frozenset({"project_decision"}),
            gate="GT1",
        ),
    )
}


class UnknownAgent(KeyError):
    pass


def get_agent(key: str) -> AgentSpec:
    try:
        return AGENTS[key]
    except KeyError as exc:
        raise UnknownAgent(key) from exc
