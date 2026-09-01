"""لقطة سياق البحث | The ResearchContext snapshot (S5D §2–§5, §10).

**المشروع هو الحدّ، لا الرسالة.** `research_projects` كيانٌ حقيقي مقيَّد
بالمستأجر، وهو أصلًا أبو عناصر الخيط. فالتخطيط يُبنى عليه، والرسالة تبقى
مصدرًا من مصادره.

**والأدلة موثقةٌ وحدها.** المرشّح المرفوض حكمٌ بالبطلان، و«لا أعرف» امتناعٌ
عن الحكم، وغير المراجَع لم يُعرض بعد. ثلاثتها **ليست أدلة**، ولا يدخل منها
شيء هنا. والمسار الوحيد إلى `verified` هو `services/memory.py` — ولا يُلتفّ
عليه.

**واللقطة تُبنى حتميًّا قبل أي نداء.** فإن لم تكفِ الأدلة لم يُستدعَ نموذج
أصلًا: لا مقترحات تُخترع من فراغ، ولا رموز تُنفَق على سؤالٍ لا جواب له.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.research import ResearcherMemory

# ── تصنيف الأدلة ──
#
# مفاتيح حقول S5C تُقابَل بأدوارها في التخطيط. والمقابلة صريحة لا مخمَّنة:
# حقلٌ لا يُعرف دوره يدخل «أخرى» ولا يُدَّعى له معنى.
ROLE_BY_FIELD: Final[dict[str, str]] = {
    "research_problem": "problem",
    "background": "problem",
    "research_gap": "problem",
    "objectives": "objective",
    "research_questions": "question",
    "hypotheses": "question",
    "theoretical_framework": "theory",
    "constructs": "theory",
    "design": "methodology",
    "study_type": "methodology",
    "population": "sample",
    "sample_size": "sample",
    "sampling": "sample",
    "instruments": "methodology",
    "validity": "methodology",
    "reliability": "methodology",
    "analysis_methods": "analysis",
    "software": "analysis",
    "main_findings": "result",
    "hypothesis_outcomes": "result",
    "qualitative_themes": "result",
    "limitations": "limitation",
    "recommendations": "limitation",
    "future_research": "limitation",
}

# ── عتبة الكفاية ──
#
# فرصة نشر تحتاج على الأقل: ما الذي دُرس (مشكلة أو سؤال)، وكيف (منهج أو
# عينة)، وماذا وُجد (نتيجة). وبأقل من ذلك يكون ما يُقترح إنشاءً لا تخطيطًا.
REQUIRED_ROLE_GROUPS: Final[tuple[tuple[str, ...], ...]] = (
    ("problem", "question", "objective"),
    ("methodology", "sample", "analysis"),
    ("result",),
)
MIN_EVIDENCE_ITEMS: Final = 4


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """دليل واحد — قيمةٌ موثقة بموضعها.

    يعبر حدود المعاملات، فلا يحمل كائن ORM ولا جلسة.
    """

    memory_id: uuid.UUID
    role: str
    field_key: str | None
    statement: str
    category: str
    source_file_id: uuid.UUID | None
    locator: str | None
    quote: str | None

    def as_model_view(self) -> dict:
        """ما يراه النموذج — **بلا معرّفات داخلية ولا أسرار**.

        الموضع يُرسَل لأنه يجعل المقترح قابلًا للتتبّع، والاقتباس يُقصّ لأن
        الغرض إسنادٌ لا نقلُ مستند.
        """
        return {
            "role": self.role,
            "fact": self.statement[:600],
            "locator": self.locator,
            "quote": (self.quote or "")[:300] or None,
        }


@dataclass(frozen=True, slots=True)
class ResearchContext:
    """لقطة أدلة تشغيلة تخطيط واحدة."""

    project_id: uuid.UUID
    tenant_id: uuid.UUID
    items: tuple[EvidenceItem, ...]
    fingerprint: str
    missing_roles: tuple[str, ...] = ()
    constraints: dict = field(default_factory=dict)

    @property
    def sufficient(self) -> bool:
        return not self.missing_roles and len(self.items) >= MIN_EVIDENCE_ITEMS

    @property
    def memory_ids(self) -> list[str]:
        return [str(i.memory_id) for i in self.items]

    def by_role(self, role: str) -> tuple[EvidenceItem, ...]:
        return tuple(i for i in self.items if i.role == role)

    def summary(self) -> dict:
        """عددٌ لكل دور — للتدقيق وللواجهة، بلا نصّ."""
        counts: dict[str, int] = {}
        for item in self.items:
            counts[item.role] = counts.get(item.role, 0) + 1
        return {"roles": counts, "total": len(self.items)}

    def model_context(self) -> list[dict]:
        """أقلّ ما يلزم النموذج — مرتَّبًا بالدور فيقرأ بنيةً لا كومة."""
        order = ["problem", "question", "objective", "theory", "methodology",
                 "sample", "variable", "analysis", "result", "limitation"]
        return [i.as_model_view()
                for role in order for i in self.items if i.role == role]


def _role_for(memory: ResearcherMemory) -> str:
    """دور الدليل — من حقله إن عُرف، وإلا من فئة ذاكرته."""
    value = memory.value if isinstance(memory.value, dict) else {}
    field_key = value.get("field_key")
    if field_key and field_key in ROLE_BY_FIELD:
        return ROLE_BY_FIELD[field_key]
    # الاحتياطي بفئة الذاكرة — و`verified_evidence` نتائج بحكم §S5C.
    return {"verified_evidence": "result", "analysis_result": "analysis"}.get(
        memory.memory_category, "other")


def fingerprint_of(memory_ids, *, capability: str, project_id: uuid.UUID,
                   contents=()) -> str:
    """بصمة ثابتة للقطة (§5).

    تُشتقّ من **مدخلات قانونية**: معرّفات الذاكرات مرتَّبة، ومحتوياتها،
    والقدرة، والمشروع. ولا وقت فيها: بصمةٌ تتغيّر بمجرد مرور الثانية لا
    تثبت شيئًا، وتُبطل كل موافقة بلا سبب.
    """
    canonical = json.dumps(
        {
            "capability": capability,
            "project": str(project_id),
            "memories": sorted(str(m) for m in memory_ids),
            "contents": sorted(contents),
        },
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def build(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    capability: str,
    constraints: dict | None = None,
) -> ResearchContext:
    """يبني اللقطة من الذاكرة الموثقة وحدها — حتميًّا، وبلا نداء خارجي.

    **ولا استعلام يقرأ `fact_candidates` هنا.** المرشّح ليس دليلًا مهما كانت
    ثقته؛ ما لم يمرّ بمسار الاعتماد البشري لا يدخل التخطيط.
    """
    rows = (
        await session.execute(
            select(ResearcherMemory).where(
                ResearcherMemory.tenant_id == tenant_id,
                # الحارس الأول: الموثق وحده.
                ResearcherMemory.verification_status == "verified",
            ).order_by(ResearcherMemory.created_at.asc())
        )
    ).scalars().all()

    items: list[EvidenceItem] = []
    for memory in rows:
        role = _role_for(memory)
        if role == "other":
            continue
        value = memory.value if isinstance(memory.value, dict) else {}
        items.append(EvidenceItem(
            memory_id=memory.id, role=role, field_key=value.get("field_key"),
            statement=(memory.statement_ar or memory.statement_en or "").strip(),
            category=memory.memory_category,
            source_file_id=memory.source_file_id,
            locator=memory.source_locator, quote=memory.source_quote,
        ))

    present = {i.role for i in items}
    missing = tuple(
        "/".join(group) for group in REQUIRED_ROLE_GROUPS if not (present & set(group))
    )
    return ResearchContext(
        project_id=project_id, tenant_id=tenant_id, items=tuple(items),
        fingerprint=fingerprint_of([i.memory_id for i in items], capability=capability,
                                   project_id=project_id,
                                   contents=[i.statement[:200] for i in items]),
        missing_roles=missing,
        constraints=constraints or {},
    )
