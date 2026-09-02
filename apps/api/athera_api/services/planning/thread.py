"""الخيط الذهبي من فرصة مختارة | Golden Thread assembly (S5D §22–§26).

**إعادة استعمال لا نظامٌ ثانٍ.** `thread_elements` و`thread_links` قائمان،
والمدقّق التسعي في `services/golden_thread/checks.py` يفحص السببية والتعميم
والمتغيرات — وهي بالضبط ما يطلبه §24 و§25. فهذه الوحدة تبني الخيط من الأدلة
وتسلّمه إليه، ولا تكتب مدقّقًا ثانيًا.

**والتمييز محفوظ:** عنصرٌ له رابط دليل = حقيقة مصدر. وعنصرٌ بلا رابط —
كالفجوة المرشحة والمساهمة المقترحة — **اقتراح**، ويُعلَن كذلك في مخرجه.
"""
from __future__ import annotations

import re
import uuid
from typing import Final

from sqlalchemy import select

from ...models.golden_thread import ThreadElement, ThreadLink
from ...models.planning import ThreadElementEvidence
from ...models.research import ResearcherMemory
from ..golden_thread import checks
from ..golden_thread.graph import Element, Link, MethodSpec, ThreadGraph
from .context import ResearchContext

# دور الدليل → نوع عنصر الخيط. والأنواع من مفردات المستودع القائمة (§22):
# لا نوع جديد يُخترع لمعنى يمثّله نوعٌ موجود.
ELEMENT_BY_ROLE: Final[dict[str, str]] = {
    "problem": "problem",
    "question": "question",
    "objective": "objective",
    "theory": "theory",
    "methodology": "method",
    "sample": "method",
    "analysis": "analysis",
    "result": "result",
    "limitation": "discussion",
}

# عناصر لا دليل لها بطبيعتها — تبقى **اقتراحات** ولا تُعرض حقائق مصدر.
PROPOSAL_ELEMENTS: Final = frozenset({"gap", "recommendation"})

_SAMPLE_SIZE = re.compile(r"(\d{2,6})")
_DESIGN_HINTS: Final[dict[str, str]] = {
    "شبه التجريبي": "quasi_experimental",
    "التجريبي": "experimental",
    "الوصفي": "descriptive",
    "الارتباطي": "correlational",
    "المسحي": "survey",
    "quasi": "quasi_experimental",
    "experimental": "experimental",
    "correlational": "correlational",
    "descriptive": "descriptive",
}
_SAMPLING_HINTS: Final[dict[str, str]] = {
    "العشوائية العنقودية": "cluster_random",
    "العشوائية البسيطة": "simple_random",
    "الطبقية": "stratified_random",
    "المتاحة": "convenience",
    "القصدية": "purposive",
    "cluster": "cluster_random",
    "convenience": "convenience",
    "purposive": "purposive",
}


def _hint(text: str, table: dict[str, str]) -> str | None:
    lowered = text.lower()
    for needle, value in table.items():
        if needle in text or needle.lower() in lowered:
            return value
    return None


def method_from_evidence(context: ResearchContext) -> MethodSpec:
    """يقرأ التصميم والمعاينة وحجم العينة **من الأدلة الموثقة**.

    وما لا يرد فيها يبقى `None` — ولا يُخمَّن. وهذا ما يجعل حارس السببية
    يعمل: تصميمٌ غير معروف لا يُعدّ سببيًّا، فلا تمرّ لغة سببية بحجّة أننا
    لا نعرف.
    """
    method_text = " ".join(i.statement for i in context.by_role("methodology"))
    sample_text = " ".join(i.statement for i in context.by_role("sample"))
    joined = f"{method_text} {sample_text}"

    size = None
    for item in context.by_role("sample"):
        found = _SAMPLE_SIZE.search(item.statement)
        if found:
            size = int(found.group(1))
            break
    design = _hint(joined, _DESIGN_HINTS)
    return MethodSpec(
        study_type="quantitative" if design else "quantitative",
        design_family=design,
        sampling_strategy=_hint(joined, _SAMPLING_HINTS),
        sample_size=size,
        population=(context.by_role("sample")[0].statement[:200]
                    if context.by_role("sample") else None),
    )


async def assemble(
    session, *, tenant_id: uuid.UUID, project_id: uuid.UUID, opportunity,
    context: ResearchContext, actor_user_id: uuid.UUID,
) -> list[uuid.UUID]:
    """يبني عناصر الخيط من الأدلة ويربط كلًّا بدليله.

    ويُشغَّل في معاملة قصيرة — بلا نداء خارجي فيها.
    """
    proposal = (opportunity.readiness_components or {}).get("proposal", {})
    created: list[uuid.UUID] = []
    ordinal = 0

    async def add(element_type: str, label: str, detail: str | None,
                  memory_ids=()) -> None:
        nonlocal ordinal
        ordinal += 1
        element = ThreadElement(
            tenant_id=tenant_id, project_id=project_id, element_type=element_type,
            label_ar=label[:2000], detail_ar=(detail or None), ordinal=ordinal,
            metadata_json={
                "opportunity_id": str(opportunity.id),
                # يُعلَن في البيانات: أهو حقيقة مصدر أم اقتراح نموذج؟
                "origin": "model_proposal" if not memory_ids else "verified_evidence",
            },
        )
        session.add(element)
        await session.flush()
        created.append(element.id)
        for memory_id in memory_ids:
            session.add(ThreadElementEvidence(
                tenant_id=tenant_id, element_id=element.id, memory_id=memory_id))

    # ── عناصر مؤصَّلة: كلٌّ بدليله ──
    for role, element_type in ELEMENT_BY_ROLE.items():
        items = context.by_role(role)
        if not items:
            continue
        label = items[0].statement
        await add(element_type, label, None, [i.memory_id for i in items])

    # ── عناصر مقترحة: بلا دليل، ومعلَنة كذلك ──
    if opportunity.research_question_ar:
        await add("question", opportunity.research_question_ar, None)
    if proposal.get("contribution_ar"):
        await add("recommendation", proposal["contribution_ar"], None)
    # §14 — فجوةٌ **مرشحة**، ولفظها يقول ذلك.
    await add("gap", "فجوة بحثية مرشحة — تحتاج إلى تحقق من الأدبيات",
              "candidate gap; literature registry offline")
    return created


async def to_graph(session, *, tenant_id: uuid.UUID, project_id: uuid.UUID,
                   opportunity, context: ResearchContext) -> ThreadGraph:
    """يحوّل الصفوف إلى `ThreadGraph` الذي يفهمه المدقّق القائم.

    و`tenant_id` يُمرَّر صراحةً ولا يُترك لـRLS وحدها: الحادثة أثبتت أن
    طبقةً واحدة قد تسقط بسطرٍ في سرّ نشر، فتبقى الثانية.
    """
    rows = (await session.execute(
        select(ThreadElement).where(ThreadElement.project_id == project_id,
                                    ThreadElement.tenant_id == tenant_id)
        .order_by(ThreadElement.ordinal)
    )).scalars().all()
    mine = [r for r in rows
            if (r.metadata_json or {}).get("opportunity_id") == str(opportunity.id)]
    links = (await session.execute(
        select(ThreadLink).where(ThreadLink.project_id == project_id,
                                 ThreadLink.tenant_id == tenant_id))).scalars().all()

    proposal = (opportunity.readiness_components or {}).get("proposal", {})
    return ThreadGraph(
        elements=[Element(str(r.id), r.element_type, r.label_ar, r.detail_ar)
                  for r in mine],
        links=[Link(str(link.source_element_id), str(link.target_element_id),
                    link.link_type)
               for link in links
               if str(link.source_element_id) in {str(r.id) for r in mine}],
        method=method_from_evidence(context),
        title=opportunity.working_title_ar or "",
        # النصّ الذي يفحصه حارس السببية: العنوان والسؤال والمساهمة المقترحة.
        discussion_text=" ".join(filter(None, (
            opportunity.research_question_ar,
            proposal.get("contribution_ar"), proposal.get("analysis_ar")))),
        results_text=" ".join(i.statement for i in context.by_role("result")),
    )


def validate(graph: ThreadGraph):
    """المدقّق القائم — تسعة كشوفات، بلا واحد يُكتب من جديد (§24)."""
    return checks.run_all(graph)


async def evidence_map(session, *, tenant_id: uuid.UUID, project_id: uuid.UUID,
                       opportunity_id: uuid.UUID):
    """خريطة الأدلة (§26): كل عنصر بأدلته وإسنادها.

    ولا نسخ للإسناد: الموضع والاقتباس يُقرآن من `researcher_memories` نفسها.

    **والاستعلام كان بلا شرط `WHERE` بتاتًا** — يقرأ كل عناصر الخيط في
    القاعدة ثم يرشّح بالبايثون على `opportunity_id`. وذلك يصحّ ما دامت RLS
    ترشّح قبله؛ وحين سقطت صار الاستعلام يمسح الجدول كاملًا. فالشروط الآن
    في القاعدة: المستأجر والمشروع، ثم الفرصة.
    """
    rows = (await session.execute(
        select(ThreadElement, ThreadElementEvidence, ResearcherMemory)
        .join(ThreadElementEvidence, ThreadElementEvidence.element_id == ThreadElement.id)
        .join(ResearcherMemory, ResearcherMemory.id == ThreadElementEvidence.memory_id)
        .where(ThreadElement.tenant_id == tenant_id,
               ThreadElement.project_id == project_id,
               ThreadElementEvidence.tenant_id == tenant_id,
               ResearcherMemory.tenant_id == tenant_id)
    )).all()
    mapped: dict[str, dict] = {}
    for element, _link, memory in rows:
        if (element.metadata_json or {}).get("opportunity_id") != str(opportunity_id):
            continue
        entry = mapped.setdefault(str(element.id), {
            "element_id": str(element.id), "element_type": element.element_type,
            "claim_ar": element.label_ar, "origin": "verified_evidence", "evidence": [],
        })
        entry["evidence"].append({
            "memory_id": str(memory.id),
            "statement_ar": memory.statement_ar,
            "source_file_id": str(memory.source_file_id) if memory.source_file_id else None,
            "locator": memory.source_locator,
            "quote": memory.source_quote,
        })
    return list(mapped.values())
