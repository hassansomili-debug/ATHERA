"""صياغة قسم واحد من أدلته | Evidence-bound section drafting (S5E-B).

**التسلسل هو الضمان:** سياقٌ حتمي يُبنى من الأدلة الموثقة، ثم إذنٌ مقيَّد
ببصمته، ثم نداءٌ **بلا معاملة مفتوحة**، ثم ترشيحٌ يرفض كل معرّف لم يُرسَل،
ثم حفظٌ يربط كل ادعاء بدليله، ثم تحقّقٌ حتمي يراه الباحث.

ولا خطوة تقفز فوق سابقتها.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from dataclasses import dataclass
from typing import Final

from sqlalchemy import select

from ....models.literature import Claim
from ....models.publishing import (
    ClaimAnalysisLink,
    ClaimMemoryLink,
    ManuscriptSection,
    ManuscriptSectionClaim,
)
from . import numbers
from .contracts import DraftedClaim, SectionDraft

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


# تعليمات القسم الوصفي الصارم — تُضاف إلى العامة ولا تحلّ محلّها.
SECTION_RULES: Final[dict[str, str]] = {
    "results": (
        "\n\nوهذا قسم **النتائج**، وله قواعد أشدّ:\n"
        "٩. النتائج وصفٌ لما لوحظ. لا تفسير ولا تعليل ولا مقارنة بدراسات "
        "ولا توصيات — موضع ذلك المناقشة.\n"
        "١٠. لا تقل إن فرقًا «دالٌّ إحصائيًّا» ولا تذكر مستوى دلالة إلا إن "
        "أرفقت في `analysis_output_ids` معرّف مخرَج تحليل يحمل تلك القيمة. "
        "ووجودُ فرقٍ شيء، ودلالتُه الإحصائية شيء آخر يقرّره اختبار.\n"
        "١١. ما ورد في الأدلة بعلامة [غير متاح] **محجوبٌ عمدًا لأنه بلا سند "
        "بنيوي**. لا تعِد بناءه ولا تستنتجه ولا تذكر أن قيمةً كانت هناك.\n"
        "١٢. لا تشتقّ رقمًا بالحساب: «120 وُزّعوا بالتساوي» لا يعني أن تكتب "
        "«60 في كل مجموعة» ما لم يرد الرقم في دليل.\n"
        "١٣. وإن وُجد في `analysis_outputs` مخرَجٌ يحمل القيمة، فاذكرها "
        "كما هي حرفيًّا وأرفق معرّفه. ولا تقرّبها ولا تعيد تنسيقها.\n"
        "١٤. ولا تنسخ العلامة [غير متاح] في نصّك. قل بعبارتك إن القيمة "
        "الدقيقة غير متاحة في الأدلة.\n"
        "١٥. وإن لم تجد سندًا لقيمة، فاكتب القسم بما تسنده الأدلة، وقل في "
        "`missing_evidence` إن القيمة الدقيقة غير متاحة. **قسمٌ ناقص صادق "
        "مقبول، ورقمٌ مخترَع مرفوض.**"
    ),
}


def instruction_for(section_key: str) -> str:
    """التعليمات العامة، ثم قواعد القسم إن كانت له قواعد."""
    return INSTRUCTION + SECTION_RULES.get(section_key, "")


def build_prompt(context) -> str:
    """ما يُرسل فعلًا — وهو ما تحرسه البصمة، لا أكثر ولا أقل."""
    payload = {
        "section_key": context.section_key,
        "section_purpose_ar": context.purpose_ar,
        "language": context.language,
        "evidence": context.model_context(),
        "thread_elements_ar": list(context.thread_labels),
        "allowed_memory_ids": sorted(context.memory_ids),
        # **مخرجات التحليل المؤهَّلة بقيمها.** كانت تُحمَّل وتُبصَم ويُتحقَّق
        # منها — ولا تُرسل. فكان النموذج يُحاسَب على رقمٍ لم يُعطَ سبيلًا
        # إليه، ويكتب أن القيمة غير متاحة وهي بين يدي المنظومة.
        "analysis_outputs": context.model_outputs(),
        "allowed_analysis_output_ids": sorted(context.output_ids),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


@dataclass(slots=True)
class BoundClaim:
    """ادعاءٌ بعد الترشيح — بأدلته المقبولة ومخرجاته المقبولة.

    و`derived_from_section_span` يفصل ما كتبه النموذج عمّا استخرجه الخادم من
    نصّه: الثاني فهرسةُ نصٍّ قائم لا إنشاءُ ادعاء، والفرق يُسجَّل ولا يُطمس.
    """

    claim: DraftedClaim
    memory_ids: list[str]
    output_ids: list[str]
    derived_from_section_span: bool = False


def ground(draft: SectionDraft, context) -> tuple[list[BoundClaim], list[str]]:
    """يُسقط كل إسنادٍ إلى معرّف لم يُرسَل — **ولا يُصحَّح** (§16).

    نموذجٌ يخترع معرّفًا يخترع سندًا؛ وتصحيحه بأقرب معرّف يجعل الاختلاق
    يبدو إسنادًا. فيُحذف الرابط، ويُعلَن الحذف في الكشوفات.
    """
    known_memories = context.memory_ids
    known_outputs = context.output_ids
    grounded: list[BoundClaim] = []
    dropped: list[str] = []
    for claim in draft.claims:
        memories = [m for m in claim.memory_ids if m in known_memories]
        outputs = [o for o in claim.analysis_output_ids if o in known_outputs]
        dropped.extend(m for m in claim.memory_ids if m not in known_memories)
        dropped.extend(o for o in claim.analysis_output_ids if o not in known_outputs)
        grounded.append(BoundClaim(claim=claim, memory_ids=memories,
                                   output_ids=outputs))
    return grounded, dropped


_SENTENCE_BOUNDARY = re.compile(r"[.!?؟\n]")


def _span_around(text: str, start: int, end: int) -> str:
    """الجملة التي تحوي هذا الموضع — **من النصّ كما هو، بلا تعديل حرف**."""
    left = 0
    for match in _SENTENCE_BOUNDARY.finditer(text, 0, start):
        left = match.end()
    right = len(text)
    boundary = _SENTENCE_BOUNDARY.search(text, end)
    if boundary:
        right = boundary.end()
    return text[left:right].strip()


def bind_statistics(draft: SectionDraft, context, bound: list[BoundClaim]) -> int:
    """يربط كل قيمة إحصائية في النثر بمخرَجها **بعينه** (§6، §7).

    **المشكلة التي يحلّها:** النموذج قد يكتب الرقم في نصّ القسم ويعلّق معرّف
    المخرَج على ادعاءٍ آخر. فيصير رقمٌ حقيقي بلا إسناد بنيوي — لا لأنه
    مخترَع، بل لأن الربط وقع في المكان الخطأ.

    **وما لا يفعله:** لا يعيد صياغة نثر، ولا يخترع رقمًا، ولا يغيّر قيمة،
    ولا يستنتج دلالة. حين لا يجد ادعاءً يحمل القيمة، يقتطع **الجملة كما هي
    حرفًا بحرف** من نصّ القسم ويجعلها ادعاءً ذرّيًّا. وهي فهرسةُ نصٍّ قائم.

    **والغموض يفشل مغلقًا:** مخرَجان يحملان القيمة نفسها ⇒ لا يُختار أحدهما،
    ويبقى الكشف ظاهرًا.

    ويعيد عدد الادعاءات الذرّية التي أُنشئت.
    """
    text = draft.section_text_ar or ""
    normalised = numbers.normalise(text)
    created = 0

    for hit in numbers.find(text):
        if hit.value is None:
            continue
        carrying = [o for o in context.outputs
                    if any(numbers.fact_supports(hit, fact)
                           for fact in numbers.facts(o.payload))]
        if len(carrying) != 1:
            continue  # لا مخرَج، أو غموض — والكشوفات تقولها
        output_id = str(carrying[0].output_id)

        holder = next(
            (b for b in bound
             if hit.excerpt in numbers.normalise(b.claim.text_ar)), None)
        if holder is not None:
            if output_id not in holder.output_ids:
                holder.output_ids.append(output_id)
            continue

        # §7 — ادعاءٌ ذرّي لكل قيمة: مخرَجٌ واحد قد يحمل عدة نتائج، وجمعها
        # في ادعاء واحد يُضعف الإسناد أو يصطدم بقيد التفرّد.
        span = _span_around(text, hit.start, hit.end) or normalised[hit.start:hit.end]
        bound.append(BoundClaim(
            claim=DraftedClaim(text_ar=span, claim_type="empirical", origin="fact",
                               memory_ids=[], analysis_output_ids=[output_id]),
            memory_ids=[], output_ids=[output_id], derived_from_section_span=True))
        created += 1
    return created


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
    memory_links = analysis_links = derived = 0
    for ordinal, item in enumerate(grounded, start=1):
        drafted, memories = item.claim, item.memory_ids
        outputs = [o for o in item.output_ids if o in known_output_ids]
        derived += 1 if item.derived_from_section_span else 0
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
            # §8 — المقتطف يُستخرج من نصّ الادعاء لا يكتبه النموذج، ويكون
            # جزءًا منه فعلًا. فمقتطفٌ يخترعه النموذج يجعل السند غير قابل
            # للفحص: يبقى مطابقًا لنفسه مهما قال النصّ.
            hits = [h.excerpt for h in numbers.find(drafted.text_ar)
                    if h.excerpt in numbers.normalise(drafted.text_ar)]
            excerpt = hits[0] if hits else numbers.normalise(drafted.text_ar)[:500]
            session.add(ClaimAnalysisLink(
                tenant_id=tenant_id, claim_id=claim.id, output_id=uuid.UUID(output_id),
                statistic_excerpt=excerpt))
            analysis_links += 1

    # الموروث يُزامَن للتوافق مع بوابة G9 القائمة — **وليس مرجعًا**.
    section.claim_ids = claim_ids
    await session.flush()
    return {"claims": len(claim_ids), "memory_links": memory_links,
            "analysis_links": analysis_links,
            # §6 — يُسجَّل كم ادعاءً استُخرج من نصّ القسم لا من مخرَج النموذج.
            "claims_derived_from_section_spans": derived,
            "missing_evidence": len(draft.missing_evidence)}


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


__all__ = ["INSTRUCTION", "SECTION_RULES", "build_prompt", "ground",
           "instruction_for", "persist"]
