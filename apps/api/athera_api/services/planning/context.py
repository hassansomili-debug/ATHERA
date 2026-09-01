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

from ...models.research import FactCandidate, ResearcherMemory
from ..document_intelligence.fields import BY_KEY, FIELD_CATALOGUE, Section

# ── تصنيف الأدلة ──
#
# **يُشتقّ من فهرس S5C، ولا يُكتب بجانبه.**
#
# كانت هنا خريطة مكتوبة يدويًّا بأسماء حقول — فانحرفت عن الفهرس بلا أن ينبّه
# أحد: ستة أسماء لا وجود لها (`main_findings` و`research_problem` وأخواتهما)،
# وثمانية عشر مفتاحًا حقيقيًّا بلا دور. وأخطرها أن دور `result` صار غير قابل
# للبلوغ، وهو مجموعة تشترطها بوابة الكفاية — فتسقط دائمًا مهما كانت الأدلة.
#
# والقسم في `FieldSpec` معلومة بنيوية موجودة أصلًا، فهو الأساس. والاستثناءات
# وحدها تُكتب: قسمٌ واحد يضمّ حقولًا بأدوار مختلفة (المنهجية تضمّ التصميم
# والعينة والتحليل معًا). ولا قائمة ثانية كاملة.

_ROLE_BY_SECTION: Final[dict[Section, str]] = {
    Section.PROBLEM: "problem",
    Section.QUESTIONS: "question",
    Section.THEORY: "theory",
    Section.METHODOLOGY: "methodology",
    Section.FINDINGS: "result",
    Section.LIMITS: "limitation",
    # بيانات الرسالة تعريفٌ لا دليل تخطيط: العنوان والجامعة والمشرفون لا
    # تُبنى عليها فرصة نشر. تبقى «أخرى» **قصدًا**، ولا تُستبعَد خطأً.
    Section.METADATA: "other",
}

# استثناءات داخل القسم الواحد — ولا شيء غيرها.
#
# وكل مفتاح هنا **يجب أن يوجد في الفهرس**؛ اختبارٌ يفشل إن لم يوجد، فلا
# يعود ممكنًا أن يحمل هذا الجدول اسمًا مخترعًا كما حمل من قبل.
_ROLE_OVERRIDES: Final[dict[str, str]] = {
    # المنهجية تضمّ ثلاثة أدوار: التصميم، والعينة، والتحليل.
    "population": "sample",
    "sample_size": "sample",
    "sampling": "sample",
    "analysis_methods": "analysis",
    "software": "analysis",
    # ومشكلة الدراسة تضمّ الهدف، وهو دور مستقل في التخطيط.
    "objectives": "objective",
}


def role_for_field(field_key: str | None) -> str | None:
    """دور حقلٍ من فهرس S5C — أو `None` إن لم يكن منه."""
    if not field_key:
        return None
    spec = BY_KEY.get(field_key)
    if spec is None:
        return None
    return _ROLE_OVERRIDES.get(field_key, _ROLE_BY_SECTION[spec.section])


#: خريطة كاملة مشتقّة — تُبنى من الفهرس فلا تنحرف عنه أبدًا.
ROLE_BY_FIELD: Final[dict[str, str]] = {
    spec.key: role_for_field(spec.key) or "other" for spec in FIELD_CATALOGUE
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


def _role_for(memory: ResearcherMemory, field_key: str | None = None) -> str:
    """دور الدليل — من حقله إن عُرف، وإلا من فئة ذاكرته.

    **و`field_key` يأتي من المرشّح لا من `value`.**

    كان يُقرأ من `memory.value`، وهو خطأ كشفه الإنتاج: `field_key` عمودٌ في
    `fact_candidates` ولا يُنسخ إلى `value` عند الاعتماد — فيقرأ هذا عدمًا،
    ويسقط كل دليل إلى «أخرى» فيُستبعَد. أي أن S5D لم يكن يستطيع استهلاك
    مخرجات S5C إطلاقًا.

    والرابط القائم `fact_candidates.resulting_memory_id` هو الطريق الصحيح:
    يوجد منذ §7.4، ويصل الذاكرة بالمرشّح الذي أنتجها. فلا يُنسخ حقلٌ ولا
    يُخترع عمود.
    """
    derived = role_for_field(field_key)
    if derived and derived != "other":
        return derived
    # الاحتياطي بفئة الذاكرة — و`verified_evidence` نتائج بحكم §S5C.
    value = memory.value if isinstance(memory.value, dict) else {}
    inline = role_for_field(value.get("field_key"))
    if inline and inline != "other":
        return inline
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
    # الذاكرة الموثقة، ومعها حقلُ المرشّح الذي أنتجها عبر الرابط القائم.
    #
    # و`outerjoin` لا `join`: ذاكرةٌ لا مرشّح لها (أُدخلت بمسار آخر من مسارات
    # §7.4) تبقى مؤهَّلة، ويُحدَّد دورها بفئتها.
    rows = (
        await session.execute(
            select(ResearcherMemory, FactCandidate.field_key)
            .outerjoin(FactCandidate,
                       FactCandidate.resulting_memory_id == ResearcherMemory.id)
            .where(
                ResearcherMemory.tenant_id == tenant_id,
                # الحارس الأول: الموثق وحده.
                ResearcherMemory.verification_status == "verified",
            ).order_by(ResearcherMemory.created_at.asc())
        )
    ).all()

    items: list[EvidenceItem] = []
    for memory, field_key in rows:
        role = _role_for(memory, field_key)
        if role == "other":
            continue
        items.append(EvidenceItem(
            memory_id=memory.id, role=role, field_key=field_key,
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
