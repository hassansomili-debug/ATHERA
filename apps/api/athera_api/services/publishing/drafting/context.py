"""سياق صياغة قسم واحد | Section drafting context (S5E-B).

**أقلّ ما يلزم لكتابة هذا القسم — لا كل ما نعرفه.**

الرسالة كاملةً لا تُرسل لأن الصياغة تحتاج سياقًا؛ يُرسل ما يخصّ القسم
المطلوب وحده. فالمنهجية تُكتب من أدلة التصميم والعينة والتحليل، ولا شأن لها
بالنتائج ولا بالفرص الأخرى ولا بأقسامٍ لم تُطلب.

**والأدوار تُشتقّ من هيكل S5D لا تُكتب بجانبه.** `outline.DEFAULT_SECTIONS`
هو من يقرّر أي دور دليل يخدم أي قسم، وهو المرجع نفسه الذي يقرأه الباحث في
الهيكل. ونسخُ الخريطة هنا يخلق مصدرَي حقيقة يفترقان — وهو صنف العطب الذي
كلّف S5D ثلاثة عوائق.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Final

from sqlalchemy import select

from ....models.analysis import AnalysisOutputRow, AnalysisPlanRow, AnalysisRun
from ....models.golden_thread import ThreadElement
from ....models.portfolio import ResearchProject
from ...planning import outline as outline_service
from ...planning.context import EvidenceItem, ResearchContext
from . import numbers
from .policy import POLICIES

# **القواعد كلها من `policy.py`.** كانت موزّعة هنا وفي المسار وفي المدقّق،
# فكان قارئٌ يسأل «ما الذي يجوز في المناقشة؟» يجمع الجواب من ثلاثة أمكنة.
# والأسماء تبقى للتوافق، وتُشتقّ من السجلّ لا تُعاد كتابتها.
ROLES_BY_SECTION: Final[dict[str, tuple[str, ...]]] = {
    key: policy.roles for key, policy in POLICIES.items()
}
DRAFTING_EXTRA_ROLES: Final[dict[str, tuple[str, ...]]] = {
    key: policy.extra_roles for key, policy in POLICIES.items() if policy.extra_roles
}
THREAD_TYPES_BY_SECTION: Final[dict[str, tuple[str, ...]]] = {
    key: policy.thread_types for key, policy in POLICIES.items() if policy.thread_types
}
REQUIRED_ANY_BY_SECTION: Final[dict[str, tuple[str, ...]]] = {
    key: policy.required_any for key, policy in POLICIES.items() if policy.required_any
}
REDACT_STATISTICS_IN: Final[frozenset[str]] = frozenset(
    key for key, policy in POLICIES.items() if policy.redact_statistics)


def roles_for(section_key: str) -> tuple[str, ...]:
    """أدوار الأدلة التي تخدم قسمًا — من سياسته."""
    policy = POLICIES.get(section_key)
    return policy.roles if policy else ()


def purpose_of(section_key: str) -> str:
    """غرض القسم — من سياسته، وإلا من هيكل S5D."""
    policy = POLICIES.get(section_key)
    if policy and policy.purpose_note_ar:
        return policy.purpose_note_ar
    for spec in outline_service.DEFAULT_SECTIONS:
        if spec.key == section_key:
            return spec.purpose_ar
    return ""


@dataclass(frozen=True, slots=True)
class AnalysisOutput:
    """مخرَج تحليل **مؤهَّل للنشر** — يعبر حدود المعاملات بلا ORM.

    والتأهيل ليس وجودًا: تشغيلةٌ مكتملة، وبيانٌ كامل لإعادة الإنتاج، وسلسلة
    ملكية مثبَتة إلى مشروع المستأجر. وما نقص عنها يبقى مرئيًّا في «البيانات
    والتحليل» ولا يسند رقمًا في ورقة.
    """

    output_id: uuid.UUID
    run_id: uuid.UUID
    test_key: str | None
    label_ar: str
    payload: dict


@dataclass(frozen=True, slots=True)
class DraftingContext:
    """لقطة صياغة قسم واحد — تعبر حدود المعاملات، فلا ORM فيها ولا جلسة."""

    tenant_id: uuid.UUID
    project_id: uuid.UUID
    manuscript_id: uuid.UUID
    opportunity_id: uuid.UUID
    outline_id: uuid.UUID | None
    section_key: str
    language: str
    purpose_ar: str
    items: tuple[EvidenceItem, ...]
    thread_labels: tuple[str, ...]
    missing_roles: tuple[str, ...]
    fingerprint: str
    outputs: tuple[AnalysisOutput, ...] = ()
    redacted_statistics: tuple[str, ...] = ()

    @property
    def sufficient(self) -> bool:
        """يكفي متى وُجد دليلٌ من الأدوار اللازمة — وإلا بقي الناقص ناقصًا."""
        return not self.missing_roles and bool(self.items)

    @property
    def output_ids(self) -> frozenset[str]:
        """مخرجات التحليل المسموح للنموذج أن يشير إليها — ولا واحد غيرها."""
        return frozenset(str(o.output_id) for o in self.outputs)

    def output(self, output_id: str) -> "AnalysisOutput | None":
        return next((o for o in self.outputs if str(o.output_id) == output_id), None)

    @property
    def memory_ids(self) -> frozenset[str]:
        """المعرّفات المسموح للنموذج أن يشير إليها — ولا واحد غيرها (§16)."""
        return frozenset(str(i.memory_id) for i in self.items)

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        for item in self.items:
            counts[item.role] = counts.get(item.role, 0) + 1
        return {"roles": counts, "total": len(self.items),
                "thread_elements": len(self.thread_labels),
                "analysis_outputs": len(self.outputs)}

    def model_context(self) -> list[dict]:
        """ما يُرسل فعلًا — مرتَّبًا بالدور، وبلا معرّف ملف ولا رابط تخزين.

        وفي الأقسام التي تُحجب فيها الأرقام، يُرسل النصّ **بعد الحجب**: فما
        يقرؤه النموذج هو ما يجوز أن يعيده.
        """
        order = roles_for(self.section_key)
        redacting = self.section_key in REDACT_STATISTICS_IN
        rows: list[dict] = []
        for role in order:
            for item in self.items:
                if item.role != role:
                    continue
                statement = item.statement
                quote = item.quote
                if redacting:
                    statement = numbers.redact(statement)[0]
                    quote = numbers.redact(quote)[0] if quote else quote
                rows.append({"memory_id": str(item.memory_id), "role": role,
                             "statement_ar": statement, "locator": item.locator,
                             "quote": quote})
        return rows

    def model_outputs(self) -> list[dict]:
        """مخرجات التحليل المتاحة — بقيمها كما خُزّنت، وبمعرّفاتها."""
        return [
            {"analysis_output_id": str(o.output_id), "test_key": o.test_key,
             "label_ar": o.label_ar, "payload": o.payload}
            for o in self.outputs
        ]


async def eligible_outputs(session, *, tenant_id: uuid.UUID,
                           project_id: uuid.UUID) -> tuple[AnalysisOutput, ...]:
    """مخرجات التحليل التي يجوز أن تسند رقمًا في ورقة (§9، §10).

    **والملكية تُثبَت بالسلسلة لا بالمعرّف:**

        analysis_output → analysis_run → analysis_plan → research_project
                                                          └── tenant_id

    فربطٌ بمعرّف وحده يقبل مخرَج مشروعٍ آخر — ومشروعِ مستأجرٍ آخر إن سقطت
    RLS. والفلترة هنا صريحة على كل حلقة، طبقةً ثانية فوق العزل.

    **والتأهيل يفشل مغلقًا:** تشغيلة غير مكتملة أو غير قابلة لإعادة الإنتاج
    لا تسند نشرًا. ونتيجتها تبقى مرئية في «البيانات والتحليل» — لكن ورقةً
    محكَّمة لا تُبنى على رقمٍ لا يستطيع صاحبه إعادة إنتاجه.
    """
    rows = (await session.execute(
        select(AnalysisOutputRow, AnalysisRun)
        .join(AnalysisRun, AnalysisRun.id == AnalysisOutputRow.run_id)
        .join(AnalysisPlanRow, AnalysisPlanRow.id == AnalysisRun.plan_id)
        .join(ResearchProject, ResearchProject.id == AnalysisPlanRow.project_id)
        .where(
            AnalysisOutputRow.tenant_id == tenant_id,
            AnalysisRun.tenant_id == tenant_id,
            AnalysisPlanRow.tenant_id == tenant_id,
            ResearchProject.tenant_id == tenant_id,
            AnalysisPlanRow.project_id == project_id,
            AnalysisRun.status == "completed",
            AnalysisRun.is_reproducible.is_(True),
        )
        .order_by(AnalysisOutputRow.created_at)
    )).all()
    return tuple(
        AnalysisOutput(output_id=output.id, run_id=run.id, test_key=output.test_key,
                       label_ar=output.label_ar, payload=output.payload or {})
        for output, run in rows
    )


def fingerprint(
    *, capability: str, tenant_id: uuid.UUID, project_id: uuid.UUID,
    manuscript_id: uuid.UUID, opportunity_id: uuid.UUID, outline_id: uuid.UUID | None,
    section_key: str, items, thread_labels, prior_text: str | None,
    outputs=(),
) -> str:
    """بصمة السياق الواقعي **بالضبط** — لا وقت فيها ولا ترتيب عابر.

    فالإذن يُعطى لإرسال هذه الوقائع بعينها لصياغة هذا القسم بعينه. وأي تغيّر
    في الوقائع — دليلٌ يُضاف أو نصٌّ يُعدَّل — يُنتج بصمةً أخرى فيصير الإذن
    قديمًا. وأي شيء **لا يُرسل** لا يدخل البصمة: بصمةٌ تحرس ما لم يُرسَل
    تُبطل الإذن بلا سبب.
    """
    canonical = json.dumps(
        {
            "capability": capability,
            "tenant": str(tenant_id),
            "project": str(project_id),
            "manuscript": str(manuscript_id),
            "opportunity": str(opportunity_id),
            "outline": str(outline_id) if outline_id else None,
            "section": section_key,
            "memories": sorted(str(i.memory_id) for i in items),
            # المحتوى لا المعرّف وحده: تعديلُ نصّ ذاكرةٍ يُبقي معرّفها.
            "contents": sorted(f"{i.role}:{i.statement}" for i in items),
            "thread": sorted(thread_labels),
            # المخرجات بمعرّفاتها **وقيمها**: رقمٌ يُصحَّح في التحليل يُبطل
            # إذنًا أُعطي على قيمته السابقة.
            "outputs": sorted(str(o.output_id) for o in outputs),
            "output_values": sorted(
                json.dumps(o.payload, ensure_ascii=False, sort_keys=True)
                for o in outputs),
            "prior_text": hashlib.sha256((prior_text or "").encode("utf-8")).hexdigest(),
        },
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def build(
    session, *, research: ResearchContext, manuscript_id: uuid.UUID,
    opportunity_id: uuid.UUID, outline_id: uuid.UUID | None, section_key: str,
    language: str, capability: str, prior_text: str | None = None,
) -> DraftingContext:
    """يبني سياق القسم من لقطة المشروع — **ترشيحًا لا استعلامًا جديدًا**.

    فالأدلة الموثقة تُقرأ مرة واحدة بمسار S5D نفسه (الموثق وحده، بدوره
    المشتقّ من فهرس الحقول)، ثم يُؤخذ منها ما يخدم هذا القسم.
    """
    wanted = set(roles_for(section_key))
    items = tuple(i for i in research.items if i.role in wanted)

    required = REQUIRED_ANY_BY_SECTION.get(section_key, ())
    present = {i.role for i in items}
    missing = tuple(r for r in required if r not in present) if required else ()
    # ناقصٌ يعني: لا يُكتب القسم — لا يُملأ الفراغ بنثرٍ معقول.
    if required and present & set(required):
        missing = ()

    labels: tuple[str, ...] = ()
    types = THREAD_TYPES_BY_SECTION.get(section_key, ())
    if types:
        rows = (await session.execute(
            select(ThreadElement).where(
                ThreadElement.tenant_id == research.tenant_id,
                ThreadElement.project_id == research.project_id,
                ThreadElement.element_type.in_(types),
            ).order_by(ThreadElement.ordinal)
        )).scalars().all()
        labels = tuple(
            row.label_ar for row in rows
            if (row.metadata_json or {}).get("opportunity_id") == str(opportunity_id)
        )

    # **مخرجات التحليل تتبع سياسة الإحصاء، لا سياسة الحجب.**
    #
    # كانت تُحمَّل حيثما يقع الحجب — وهما سؤالان مختلفان. فوصلت «الخاتمة»
    # مخرَجٌ يحمل `t = 3.738`، وسياستها تمنع الإحصاء أصلًا؛ فاستنتج النموذج
    # الدلالة من قيمة (ت) بنفسه، ورفضها المدقّق في كل محاولة. وهو ممنوعٌ
    # صراحةً: النموذج لا يحسب الدلالة.
    #
    # فالقسم الذي لا يجوز أن يحمل إحصاءً لا تُرسل إليه أرقام يستنتج منها.
    spec = POLICIES.get(section_key)
    outputs = ()
    if spec is not None and spec.allows_statistics:
        outputs = await eligible_outputs(session, tenant_id=research.tenant_id,
                                         project_id=research.project_id)

    redacted: list[str] = []
    if section_key in REDACT_STATISTICS_IN:
        for item in items:
            redacted.extend(numbers.redact(item.statement)[1])

    return DraftingContext(
        tenant_id=research.tenant_id, project_id=research.project_id,
        manuscript_id=manuscript_id, opportunity_id=opportunity_id,
        outline_id=outline_id, section_key=section_key, language=language,
        purpose_ar=purpose_of(section_key), items=items, thread_labels=labels,
        missing_roles=missing, outputs=outputs,
        redacted_statistics=tuple(dict.fromkeys(redacted)),
        fingerprint=fingerprint(
            capability=capability, tenant_id=research.tenant_id,
            project_id=research.project_id, manuscript_id=manuscript_id,
            opportunity_id=opportunity_id, outline_id=outline_id,
            section_key=section_key, items=items, thread_labels=labels,
            prior_text=prior_text, outputs=outputs),
    )


__all__ = ["DRAFTING_EXTRA_ROLES", "REDACT_STATISTICS_IN", "REQUIRED_ANY_BY_SECTION",
           "ROLES_BY_SECTION", "THREAD_TYPES_BY_SECTION", "AnalysisOutput",
           "DraftingContext", "build", "eligible_outputs", "fingerprint",
           "purpose_of", "roles_for"]
