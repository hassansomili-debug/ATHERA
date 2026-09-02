"""صياغة قسم واحد من أدلته | Evidence-bound section drafting (S5E-B).

**التسلسل هو الضمان:** سياقٌ حتمي يُبنى من الأدلة الموثقة، ثم إذنٌ مقيَّد
ببصمته، ثم نداءٌ **بلا معاملة مفتوحة**، ثم ترشيحٌ يرفض كل معرّف لم يُرسَل،
ثم حفظٌ يربط كل ادعاء بدليله، ثم تحقّقٌ حتمي يراه الباحث.

ولا خطوة تقفز فوق سابقتها.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from typing import Final

from sqlalchemy import select

from ....models.literature import Claim
from ....models.publishing import (
    ClaimAnalysisLink,
    ClaimMemoryLink,
    ManuscriptSection,
    ManuscriptSectionClaim,
)
from .contracts import SectionDraft

INSTRUCTION: Final = (
    "أنت كاتب علمي. اكتب قسمًا واحدًا من ورقة بحثية **من الأدلة الموثقة "
    "المرفقة وحدها**.\n\n"
    "قواعد لا استثناء لها:\n"
    "١. كل جملة تقرّر واقعة يجب أن يسندها دليل من القائمة، وتذكر معرّفه في "
    "`memory_ids`.\n"
    "٢. ما لا تجد له دليلًا **لا تكتبه**. ضعه في `missing_evidence` بدل أن "
    "تملأ الفراغ بصياغة معقولة. النقص المعلَن أصدق من نصّ كامل مخترَع.\n"
    "٣. لا تخترع تصميمًا ولا أسلوب معاينة ولا أداة ولا حجم عينة ولا معامل "
    "ثبات ولا برنامجًا إحصائيًّا ولا موافقة أخلاقية ولا تاريخًا ولا مكانًا.\n"
    "٤. لا رقم ولا نسبة ولا قيمة إحصائية إلا إن وردت حرفيًّا في دليل.\n"
    "٥. لا مرجع ولا مؤلف ولا سنة ولا DOI. سجل الأدبيات مغلق، والاستشهاد "
    "المطلوب يُذكر في `missing_evidence` بوصفه «بانتظار البحث العلمي».\n"
    "٦. لا لغة سببية إن لم يكن التصميم الموثق يسمح بها.\n"
    "٧. `origin` يقول أصل كل ادعاء: `fact` لما يسنده دليل، و`inference` "
    "لاستنتاج تبيّن أساسه، و`proposal` لصياغة مقترحة لا تُعرض حقيقة.\n"
    "٨. لا تكتب معرّفًا لم يرد في القائمة المرفقة."
)


def build_prompt(context) -> str:
    """ما يُرسل فعلًا — وهو ما تحرسه البصمة، لا أكثر ولا أقل."""
    payload = {
        "section_key": context.section_key,
        "section_purpose_ar": context.purpose_ar,
        "language": context.language,
        "evidence": context.model_context(),
        "thread_elements_ar": list(context.thread_labels),
        "allowed_memory_ids": sorted(context.memory_ids),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def ground(draft: SectionDraft, context) -> tuple[list, list[str]]:
    """يُسقط كل إسنادٍ إلى معرّف لم يُرسَل — **ولا يُصحَّح** (§16).

    نموذجٌ يخترع معرّفًا يخترع سندًا؛ وتصحيحه بأقرب معرّف يجعل الاختلاق
    يبدو إسنادًا. فيُحذف الرابط، ويُعلَن الحذف في الكشوفات.
    """
    known = context.memory_ids
    grounded: list = []
    dropped: list[str] = []
    for claim in draft.claims:
        memories = [m for m in claim.memory_ids if m in known]
        dropped.extend(m for m in claim.memory_ids if m not in known)
        grounded.append((claim, memories))
    return grounded, dropped


def _claim_status(origin: str, has_evidence: bool) -> str:
    """حالة الادعاء من مفردات `claims.status` القائمة — لا مفردات ثانية.

    `supported` لا تُمنح إلا بربط فعلي؛ و`evidence_gap` تقول الحقيقة عن
    واقعةٍ بلا سند بدل أن تُخفيها في «مسودة».
    """
    if origin == "fact":
        return "supported" if has_evidence else "evidence_gap"
    if origin == "inference":
        return "draft"
    return "draft"


async def persist(
    session, *, tenant_id: uuid.UUID, project_id: uuid.UUID, section: ManuscriptSection,
    draft: SectionDraft, grounded, agent_run_id: uuid.UUID | None,
    fingerprint: str, known_output_ids: frozenset[str],
) -> dict:
    """يحفظ النصّ وادعاءاته وروابط أدلتها — في معاملة قصيرة بعد النداء."""
    section.text_ar = draft.section_text_ar
    section.text_en = draft.section_text_en
    # §24 — التوليد ليس اعتمادًا. ولا يُكتب `reviewed_by` هنا بحال.
    section.review_status = "needs_review"
    section.reviewed_by = None
    section.reviewed_at = None
    section.drafting_context_fingerprint = fingerprint
    section.generation_run_id = agent_run_id

    # الروابط القديمة تُطرح مع النصّ الذي وُلدت منه.
    existing = (await session.execute(
        select(ManuscriptSectionClaim).where(
            ManuscriptSectionClaim.tenant_id == tenant_id,
            ManuscriptSectionClaim.section_id == section.id)
    )).scalars().all()
    for link in existing:
        await session.delete(link)
    await session.flush()

    claim_ids: list[str] = []
    memory_links = analysis_links = 0
    for ordinal, (drafted, memories) in enumerate(grounded, start=1):
        outputs = [o for o in drafted.analysis_output_ids if o in known_output_ids]
        claim = Claim(
            tenant_id=tenant_id, project_id=project_id, text_ar=drafted.text_ar,
            claim_type=drafted.claim_type,
            status=_claim_status(drafted.origin, bool(memories or outputs)),
            verification_status="unverified",
            # §5 — الاستنتاج يُعلَن استنتاجًا في البيانات لا في الأسلوب.
            is_labelled_inference=drafted.origin == "inference",
        )
        session.add(claim)
        await session.flush()
        claim_ids.append(str(claim.id))

        session.add(ManuscriptSectionClaim(
            tenant_id=tenant_id, section_id=section.id, claim_id=claim.id,
            ordinal=ordinal))
        for memory_id in memories:
            session.add(ClaimMemoryLink(
                tenant_id=tenant_id, claim_id=claim.id, memory_id=uuid.UUID(memory_id),
                support_level=drafted.support_level))
            memory_links += 1
        for output_id in outputs:
            session.add(ClaimAnalysisLink(
                tenant_id=tenant_id, claim_id=claim.id, output_id=uuid.UUID(output_id),
                statistic_excerpt=drafted.text_ar[:500]))
            analysis_links += 1

    # الموروث يُزامَن للتوافق مع بوابة G9 القائمة — **وليس مرجعًا**.
    section.claim_ids = claim_ids
    await session.flush()
    return {"claims": len(claim_ids), "memory_links": memory_links,
            "analysis_links": analysis_links,
            "missing_evidence": len(draft.missing_evidence)}


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


__all__ = ["INSTRUCTION", "build_prompt", "ground", "persist"]
