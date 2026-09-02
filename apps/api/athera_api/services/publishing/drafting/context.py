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

from ....models.golden_thread import ThreadElement
from ...planning import outline as outline_service
from ...planning.context import EvidenceItem, ResearchContext

# الأدوار التي يخدمها كل قسم — **من الهيكل القانوني**.
ROLES_BY_SECTION: Final[dict[str, tuple[str, ...]]] = {
    spec.key: spec.roles for spec in outline_service.DEFAULT_SECTIONS
}

# توسيعٌ **مُعلَن** لأدوار الصياغة، لا انحرافٌ صامت.
#
# الهيكل يضع `analysis` تحت «النتائج» لأن الهيكل يسأل: أي دليلٍ يُعرَض في أي
# قسم. والصياغة تسأل سؤالًا آخر: أي دليلٍ يُذكر في أي قسم. وخطة التحليل
# تُوصف في المنهجية ويُبلَّغ عن ناتجها في النتائج — فذكرها هنا وصفُ إجراء لا
# عرضُ نتيجة. و`variable` كذلك: المتغيّرات تُعرَّف في المنهجية.
#
# ولا يُضاف دورٌ خارج مفردات الأدوار القائمة — يحرس ذلك اختبار.
DRAFTING_EXTRA_ROLES: Final[dict[str, tuple[str, ...]]] = {
    "method": ("analysis", "variable"),
}

# عناصر الخيط الذهبي التي تخصّ كل قسم — ومفرداتها من `thread.ELEMENT_BY_ROLE`.
THREAD_TYPES_BY_SECTION: Final[dict[str, tuple[str, ...]]] = {
    "method": ("method", "analysis"),
}

# أدوارٌ لا يُكتب القسم بدون واحدٍ منها على الأقل.
REQUIRED_ANY_BY_SECTION: Final[dict[str, tuple[str, ...]]] = {
    "method": ("methodology", "sample"),
}


def roles_for(section_key: str) -> tuple[str, ...]:
    """أدوار الأدلة التي تخدم قسمًا — مشتقّةً ومعلَنة."""
    return tuple(dict.fromkeys(
        ROLES_BY_SECTION.get(section_key, ()) + DRAFTING_EXTRA_ROLES.get(section_key, ())
    ))


def purpose_of(section_key: str) -> str:
    for spec in outline_service.DEFAULT_SECTIONS:
        if spec.key == section_key:
            return spec.purpose_ar
    return ""


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

    @property
    def sufficient(self) -> bool:
        """يكفي متى وُجد دليلٌ من الأدوار اللازمة — وإلا بقي الناقص ناقصًا."""
        return not self.missing_roles and bool(self.items)

    @property
    def memory_ids(self) -> frozenset[str]:
        """المعرّفات المسموح للنموذج أن يشير إليها — ولا واحد غيرها (§16)."""
        return frozenset(str(i.memory_id) for i in self.items)

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        for item in self.items:
            counts[item.role] = counts.get(item.role, 0) + 1
        return {"roles": counts, "total": len(self.items),
                "thread_elements": len(self.thread_labels)}

    def model_context(self) -> list[dict]:
        """ما يُرسل فعلًا — مرتَّبًا بالدور، وبلا معرّف ملف ولا رابط تخزين."""
        order = roles_for(self.section_key)
        return [
            {"memory_id": str(i.memory_id), "role": i.role,
             "statement_ar": i.statement, "locator": i.locator, "quote": i.quote}
            for role in order for i in self.items if i.role == role
        ]


def fingerprint(
    *, capability: str, tenant_id: uuid.UUID, project_id: uuid.UUID,
    manuscript_id: uuid.UUID, opportunity_id: uuid.UUID, outline_id: uuid.UUID | None,
    section_key: str, items, thread_labels, prior_text: str | None,
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

    return DraftingContext(
        tenant_id=research.tenant_id, project_id=research.project_id,
        manuscript_id=manuscript_id, opportunity_id=opportunity_id,
        outline_id=outline_id, section_key=section_key, language=language,
        purpose_ar=purpose_of(section_key), items=items, thread_labels=labels,
        missing_roles=missing,
        fingerprint=fingerprint(
            capability=capability, tenant_id=research.tenant_id,
            project_id=research.project_id, manuscript_id=manuscript_id,
            opportunity_id=opportunity_id, outline_id=outline_id,
            section_key=section_key, items=items, thread_labels=labels,
            prior_text=prior_text),
    )


__all__ = ["DRAFTING_EXTRA_ROLES", "REQUIRED_ANY_BY_SECTION", "ROLES_BY_SECTION",
           "THREAD_TYPES_BY_SECTION", "DraftingContext", "build", "fingerprint",
           "purpose_of", "roles_for"]
