"""مساحة عمل البحث | The project workspace (PUBRIVA).

**المشروع ليس مجلَّدًا.** هو علاقاتٌ بين أدلةٍ وبياناتٍ وادعاءاتٍ ومخرجات.
فحذفُ شيءٍ منه ليس إزالةَ صفٍّ بل قطعُ سندٍ لما بُني عليه — وقد يكون قسمًا
معتمَدًا في ورقة.

فيُقال للباحث **ماذا يترتب** قبل أن يقرّر، لا بعد.
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from ..models.analysis import AnalysisOutputRow, AnalysisRun, Dataset
from ..models.files import File
from ..models.literature import Claim, ClaimEvidenceLink, EvidenceExcerpt
from ..models.portfolio import ProjectFile, ResearchProject
from ..models.publishing import (
    ClaimMemoryLink,
    Manuscript,
    ManuscriptSection,
    ManuscriptSectionClaim,
    ManuscriptVersion,
)
from ..models.research import FactCandidate, ResearcherMemory
from ..models.thesis import PublicationOpportunity


@dataclass(slots=True)
class Consequence:
    """أثرٌ واحد لإزالةٍ مقترحة — بعدده واسمه، لا بتحذيرٍ عامّ."""

    kind: str
    count: int
    label_ar: str
    label_en: str
    # هل يقطع السند عن شيءٍ اعتمده الباحث؟
    breaks_approved_work: bool = False


@dataclass(slots=True)
class Impact:
    """ما يترتب على إزالة أصلٍ من بحث."""

    consequences: list[Consequence] = field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        return not self.consequences

    @property
    def breaks_approved_work(self) -> bool:
        return any(c.breaks_approved_work for c in self.consequences)

    def summary_ar(self) -> str:
        if not self.consequences:
            return "لا يعتمد على هذا الأصل شيء في هذا البحث."
        parts = [f"{c.count} {c.label_ar}" for c in self.consequences]
        return "يسند هذا الأصل: " + " · ".join(parts) + "."

    def summary_en(self) -> str:
        if not self.consequences:
            return "Nothing in this project depends on this asset."
        parts = [f"{c.count} {c.label_en}" for c in self.consequences]
        return "This asset supports: " + " · ".join(parts) + "."


async def file_impact(session: AsyncSession, *, tenant_id: uuid.UUID,
                      project_id: uuid.UUID, file_id: uuid.UUID) -> Impact:
    """ماذا يسند هذا الملف في هذا البحث؟

    السلسلة: ملف ← مرشّحون ← ذاكرة موثقة ← ادعاءات ← أقسام مخطوطة. وكل
    حلقةٍ تُعدّ باسمها، فيعرف الباحث أن الإزالة تقطع **قسمًا معتمَدًا** لا
    «بعض البيانات».
    """
    impact = Impact()

    approved = (await session.execute(
        select(func.count(FactCandidate.id)).where(
            FactCandidate.tenant_id == tenant_id, FactCandidate.file_id == file_id,
            FactCandidate.status == "approved")
    )).scalar_one()
    if approved:
        impact.consequences.append(Consequence(
            "approved_facts", approved, "معلومة اعتمدتَها", "facts you approved"))

    memory_ids = (await session.execute(
        select(FactCandidate.resulting_memory_id).where(
            FactCandidate.tenant_id == tenant_id, FactCandidate.file_id == file_id,
            FactCandidate.resulting_memory_id.is_not(None))
    )).scalars().all()

    if memory_ids:
        claim_ids = (await session.execute(
            select(ClaimMemoryLink.claim_id).where(
                ClaimMemoryLink.tenant_id == tenant_id,
                ClaimMemoryLink.memory_id.in_(memory_ids))
        )).scalars().all()
        # **والأثر يُقاس في هذا البحث لا في المستأجر كله.** فادعاءٌ في ورقةٍ
        # لبحثٍ آخر لا يمنع إزالة الملف من هنا؛ ومنعُه بحجّة عملٍ في مكانٍ
        # ثالث حارسٌ يعاقب على ما لم يقع — ومثله يُعطَّل ثم لا يحرس شيئًا.
        project_claims = (await session.execute(
            select(Claim.id).where(Claim.tenant_id == tenant_id,
                                   Claim.project_id == project_id,
                                   Claim.id.in_(claim_ids))
        )).scalars().all()
        if project_claims:
            sections = (await session.execute(
                select(func.count(func.distinct(ManuscriptSection.id)))
                .select_from(ManuscriptSectionClaim)
                .join(ManuscriptSection,
                      ManuscriptSection.id == ManuscriptSectionClaim.section_id)
                .join(ManuscriptVersion,
                      ManuscriptVersion.id == ManuscriptSection.version_id)
                .join(Manuscript, Manuscript.id == ManuscriptVersion.manuscript_id)
                .where(ManuscriptSectionClaim.tenant_id == tenant_id,
                       Manuscript.project_id == project_id,
                       ManuscriptSectionClaim.claim_id.in_(project_claims))
            )).scalar_one()
            impact.consequences.append(Consequence(
                "manuscript_claims", len(set(project_claims)),
                "ادعاءً في مخطوطتك", "manuscript claims", breaks_approved_work=True))
            if sections:
                impact.consequences.append(Consequence(
                    "manuscript_sections", sections,
                    "قسمًا من الورقة", "manuscript sections",
                    breaks_approved_work=True))

    return impact


# ── حال المعالجة: تعريفٌ واحد، ودورةُ ذهابٍ واحدة ──────────────────────
#
# **والعدد هو الزمن.** الـAPI في سنغافورة والقاعدة في مومباي، فكل عبارة
# تدفع ذهابًا وإيابًا عبر البحر — نحو ستين مللي ثانية قبل أن تبدأ القاعدة
# عملها أصلًا. فلا يُقاس هنا عدد الصفوف بل عدد **العبارات**.
PROCESSED_MARK = "unverified"


def file_processing_state_columns(
    tenant_id: uuid.UUID, file_id: ColumnElement[uuid.UUID]
) -> tuple[ColumnElement, ColumnElement, ColumnElement, ColumnElement]:
    """أعمدة حال المعالجة **مرتبطةً بعمود الملف** — تُركَّب في استعلام الصفحة.

    وهي أربعة استعلامات فرعية في عبارةٍ واحدة، لا أربع عبارات: القاعدة
    تنفّذها كلها في زيارةٍ واحدة، والشبكة تُعبَر مرّة.
    """
    from ..models.research import ExtractionRun
    from ..models.thesis import Thesis

    # `limit(1)` على الرسالة أيضًا: الصياغة السابقة كانت `scalar_one_or_none`
    # فترمي لو حمل ملفٌ رسالتين — والانفجار ليس حالًا يُعرض في مكتبة.
    thesis_id = (
        select(Thesis.id)
        .where(Thesis.tenant_id == tenant_id, Thesis.file_id == file_id)
        .order_by(Thesis.created_at.desc(), Thesis.id.desc())
        .limit(1).scalar_subquery()
    )
    # **والترتيب يُحسم إلى آخره.** `created_at` وحده يترك تشغيلتين وُلدتا في
    # المعاملة نفسها بلا ترتيب، فتُقرأ حالٌ مرّة وأخرى مرّة — والمعرّف يحسم.
    run_status = (
        select(ExtractionRun.status)
        .where(ExtractionRun.tenant_id == tenant_id, ExtractionRun.file_id == file_id)
        .order_by(ExtractionRun.created_at.desc(), ExtractionRun.id.desc())
        .limit(1).scalar_subquery()
    )
    candidates = (
        select(func.count(FactCandidate.id))
        .where(FactCandidate.tenant_id == tenant_id, FactCandidate.file_id == file_id)
        .scalar_subquery()
    )
    reviewed = (
        select(func.count(FactCandidate.id))
        .where(FactCandidate.tenant_id == tenant_id, FactCandidate.file_id == file_id,
               FactCandidate.status != PROCESSED_MARK)
        .scalar_subquery()
    )
    return thesis_id, run_status, candidates, reviewed


def file_processing_state_of_row(
    thesis_id: uuid.UUID | None, run_status: str | None,
    candidates: int | None, reviewed: int | None,
) -> tuple[str, int, int, uuid.UUID | None]:
    """تحويلُ ما قرأته القاعدة إلى الحال المعروضة — **بموضعٍ واحد**.

    وملفٌ بلا رسالة لم يُقرأ أصلًا، فلا مرشّحين له ولا حال: يُقال
    `not_processed` صريحًا، ولا يُترك رقمٌ عالق من صفٍّ يتيم.
    """
    if thesis_id is None:
        return "not_processed", 0, 0, None
    return (run_status or "not_processed", candidates or 0, reviewed or 0, thesis_id)


async def files_processing_state(
    session: AsyncSession, *, tenant_id: uuid.UUID, file_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, tuple[str, int, int, uuid.UUID | None]]:
    """حال معالجة **صفحةٍ كاملة** من الملفات — بعبارةٍ واحدة لا بعبارةٍ لكل ملف.

    **وهذا هو العطب الذي جعل المكتبة لا تتحمّل كتبًا.** كانت الشاشة تُشتقّ
    حال كل ملف على حدة (`file_processing_state`): ثلاث عبارات للملف الذي
    عُولج، وواحدة لما لم يُعالَج. فمكتبةٌ فيها أربعون ملفًا تُصدر مئةً
    وعشرين عبارة متتابعة، كلٌّ منها رحلةٌ بين سنغافورة ومومباي — سبع ثوانٍ
    من الشبكة وحدها قبل أن تعمل القاعدة، **وتزيد طردًا مع كل ملفٍ يرفعه
    الباحث**. فمن رفع كتبه صارت مكتبته أبطأ كلما ملأها، وذلك عين الشكوى.

    والآن عبارةٌ واحدة مهما بلغ عدد الملفات.
    """
    if not file_ids:
        return {}  # لا ملفات ← لا عبارة أصلًا؛ زيارةٌ لا تُنفَق بلا سؤال.

    thesis_id, run_status, candidates, reviewed = file_processing_state_columns(
        tenant_id, File.id)
    rows = (await session.execute(
        select(File.id, thesis_id, run_status, candidates, reviewed)
        .where(File.tenant_id == tenant_id, File.id.in_(file_ids))
    )).all()
    return {row[0]: file_processing_state_of_row(row[1], row[2], row[3], row[4]) for row in rows}


async def file_processing_state(
    session: AsyncSession, *, tenant_id: uuid.UUID, file_id: uuid.UUID
) -> tuple[str, int, int, uuid.UUID | None]:
    """حال معالجة ملف — **تعريفٌ واحد يقرأه كل من يعرضها**.

    وكانت المكتبة تحسبها في `routers/files.py` ومساحة العمل ستحسبها ثانية.
    وحسابان لشيء واحد يفترقان بأول تعديل، فيرى الباحث الملف «مُراجَعًا» في
    شاشة و«قيد المعالجة» في أخرى — وهو ملفٌ واحد. فتُشتقّ من موضع واحد.

    وتُقال كما هي: `not_processed` لملفٍ لم يُقرأ، وحالُ التشغيلة نفسها لما
    قُرئ — ولا يُقال «حُلِّل» لملفٍ لم يمرّ باستخراج.

    **وهذه الصياغة ملفٌ واحد بثلاث عبارات** — تبقى لمن يعرض ملفًا مفردًا،
    وهي المرجع الذي يقيس عليه اختبارُ التكافؤ صحّةَ الصياغة المجمَّعة. فإن
    افترقتا سقط الاختبار، ولا تفترقان بصمت كما افترق حسابان من قبل.
    """
    from ..models.research import ExtractionRun
    from ..models.thesis import Thesis

    thesis = (await session.execute(
        select(Thesis).where(Thesis.tenant_id == tenant_id,
                             Thesis.file_id == file_id)
        .order_by(Thesis.created_at.desc(), Thesis.id.desc()).limit(1)
    )).scalar_one_or_none()
    if thesis is None:
        return "not_processed", 0, 0, None

    run = (await session.execute(
        select(ExtractionRun)
        .where(ExtractionRun.tenant_id == tenant_id,
               ExtractionRun.file_id == file_id)
        .order_by(ExtractionRun.created_at.desc(), ExtractionRun.id.desc()).limit(1)
    )).scalar_one_or_none()

    decided = (await session.execute(
        select(FactCandidate.status).where(
            FactCandidate.tenant_id == tenant_id,
            FactCandidate.file_id == file_id)
    )).scalars().all()
    candidates = len(decided)
    reviewed = sum(1 for value in decided if value != PROCESSED_MARK)
    status = run.status if run is not None else "not_processed"
    return status, candidates, reviewed, thesis.id


async def source_impact(session: AsyncSession, *, tenant_id: uuid.UUID,
                        project_id: uuid.UUID, source_id: uuid.UUID) -> Impact:
    """ماذا يسند هذا المرجع في هذا البحث؟"""
    impact = Impact()

    excerpt_ids = (await session.execute(
        select(EvidenceExcerpt.id).where(
            EvidenceExcerpt.tenant_id == tenant_id,
            EvidenceExcerpt.source_id == source_id)
    )).scalars().all()

    claims = 0
    if excerpt_ids:
        claims = (await session.execute(
            select(func.count(func.distinct(ClaimEvidenceLink.claim_id)))
            .join(Claim, Claim.id == ClaimEvidenceLink.claim_id)
            .where(ClaimEvidenceLink.tenant_id == tenant_id,
                   ClaimEvidenceLink.excerpt_id.in_(excerpt_ids),
                   Claim.project_id == project_id)
        )).scalar_one()
    if claims:
        impact.consequences.append(Consequence(
            "cited_claims", claims, "ادعاءً يستشهد به", "claims that cite it",
            breaks_approved_work=True))
    return impact


async def dataset_impact(session: AsyncSession, *, tenant_id: uuid.UUID,
                         dataset_id: uuid.UUID) -> Impact:
    """ماذا يسند هذا الملف من البيانات؟ — تشغيلاتٌ ومخرجاتٌ وادعاءات."""
    impact = Impact()
    runs = (await session.execute(
        select(AnalysisRun.id)
        .join(Dataset, Dataset.id == dataset_id)
        .where(AnalysisRun.tenant_id == tenant_id)
    )).scalars().all()
    outputs = 0
    if runs:
        outputs = (await session.execute(
            select(func.count(AnalysisOutputRow.id)).where(
                AnalysisOutputRow.tenant_id == tenant_id,
                AnalysisOutputRow.run_id.in_(runs))
        )).scalar_one()
    if outputs:
        impact.consequences.append(Consequence(
            "analysis_outputs", outputs, "مخرَج تحليل", "analysis outputs",
            breaks_approved_work=True))
    return impact


@dataclass(slots=True)
class BrainEntry:
    """ما تعرفه المنصّة عن عنصرٍ من عناصر البحث — بحالٍ يفهمها الباحث."""

    key: str
    label_ar: str
    label_en: str
    # `known` | `needs_review` | `missing` | `conflicting`
    state: str
    value_ar: str | None = None
    sources: int = 0


# عناصر «دماغ البحث» — بلغة الباحث لا بمفردات المحرّك.
#
# **والدور يُشتقّ من مفرداته لا يُكتب بجانبها.** فأول صياغة أدرجت «الفجوة
# البحثية» و«أداة القياس» بدورَي `gap` و`instrument`، وليس لهما وجود في
# `ROLE_BY_FIELD`. فكان العنصران يظهران «ناقصَين» أبدًا مهما وثّق الباحث —
# لا لأن المعرفة غائبة، بل لأن الاسم المكتوب لا يقابل شيئًا. وهو الخطأ
# نفسه المتكرر: معرّفٌ يُكتب بجانب سجلّه بدل أن يُشتقّ منه. فيُتحقَّق أدناه.
BRAIN_FIELDS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("problem", "مشكلة البحث", "Research problem", ("problem",)),
    ("question", "سؤال البحث", "Research question", ("question",)),
    ("objective", "الأهداف", "Objectives", ("objective",)),
    ("theory", "الإطار النظري", "Theory", ("theory",)),
    ("method", "المنهج وأداة القياس", "Method and instrument", ("methodology",)),
    ("sample", "العيّنة", "Sample", ("sample",)),
    ("data", "التحليل", "Analysis", ("analysis",)),
    ("results", "النتائج", "Results", ("result",)),
    ("limitations", "حدود الدراسة", "Limitations", ("limitation",)),
)


def _assert_roles_exist() -> None:
    """كل دورٍ مذكور أعلاه موجودٌ في مفردات الحقول — وإلا فالعنصر ميت."""
    from ..services.planning.context import ROLE_BY_FIELD

    known = set(ROLE_BY_FIELD.values())
    named = {role for _, _, _, roles in BRAIN_FIELDS for role in roles}
    unknown = named - known
    if unknown:  # pragma: no cover — يُمسك في الاختبار قبل النشر
        raise RuntimeError(
            f"research brain names roles absent from ROLE_BY_FIELD: {sorted(unknown)}")


async def research_brain(session: AsyncSession, *, tenant_id: uuid.UUID,
                         project_id: uuid.UUID) -> list[BrainEntry]:
    """ما تعرفه المنصّة عن هذا البحث — **بحالٍ صادقة لا بنسبة**.

    و`missing` حالٌ مشروعة تُعرض كما هي: بحثٌ في أوله لا يعرف نتائجه، وقول
    ذلك أصدق من شريطٍ يقول «٤٠٪».
    """
    from ..services.planning.context import ROLE_BY_FIELD

    # **ولا يُبحث في بحثٍ آخر بصمت.** `researcher_memories` لا تحمل
    # `project_id`، فأول صياغة قرأت ذاكرة المستأجر كلها — فكان دماغ بحثٍ
    # يعرض معرفةً استُخرجت من بحثٍ غيره، والباحث لا يرى الفرق. فيُقيَّد
    # بالسلسلة التي تثبت الانتماء: ملفات هذا البحث ← مرشّحوها ← ذاكرتها.
    #
    # **وحدُّ هذا الاشتقاق يُقال:** من مسارات §٧.٤ الأربعة، `upload` وحده
    # يمرّ بملف. فذاكرةٌ رُقّيت من تشغيلة تحليل أو من قول الباحث لا تظهر
    # هنا بعد، ويُعرض عنصرها `missing`. وهو نقصٌ يُرى فيُسدّ — أهون من
    # عرض معرفةٍ من بحثٍ آخر يُبنى عليها وهي ليست منه.
    rows = (await session.execute(
        select(ResearcherMemory, FactCandidate.field_key, FactCandidate.status)
        .join(FactCandidate,
              FactCandidate.resulting_memory_id == ResearcherMemory.id)
        .join(ProjectFile, ProjectFile.file_id == FactCandidate.file_id)
        .where(ResearcherMemory.tenant_id == tenant_id,
               FactCandidate.tenant_id == tenant_id,
               ProjectFile.tenant_id == tenant_id,
               ProjectFile.project_id == project_id,
               ProjectFile.state == ProjectFile.ACTIVE)
    )).all()

    by_role: dict[str, list[tuple[str, str]]] = {}
    for memory, field_key, _status in rows:
        role = ROLE_BY_FIELD.get(field_key or "", "other")
        by_role.setdefault(role, []).append(
            (memory.statement_ar, memory.verification_status))

    entries: list[BrainEntry] = []
    for key, label_ar, label_en, roles in BRAIN_FIELDS:
        found = [item for role in roles for item in by_role.get(role, ())]
        verified = [text for text, status in found if status == "verified"]
        pending = [text for text, status in found if status != "verified"]

        if verified:
            state = "known"
            value = verified[0][:200]
        elif pending:
            state = "needs_review"
            value = None
        else:
            state = "missing"
            value = None
        entries.append(BrainEntry(key=key, label_ar=label_ar, label_en=label_en,
                                  state=state, value_ar=value, sources=len(verified)))
    return entries


async def next_action(session: AsyncSession, *, tenant_id: uuid.UUID,
                      project_id: uuid.UUID) -> tuple[str, str, str] | None:
    """فعلٌ واحد عالي القيمة — **لا قائمةُ أمنيات**.

    والترتيب هو الحكم: ما لا يمكن بناء شيء عليه أولًا. فاقتراحُ «اكتب
    المناقشة» لبحثٍ بلا أدلة نصيحةٌ لا تُنفَّذ.
    """
    files = (await session.execute(
        select(func.count(ProjectFile.id)).where(
            ProjectFile.tenant_id == tenant_id, ProjectFile.project_id == project_id,
            ProjectFile.state == ProjectFile.ACTIVE)
    )).scalar_one()
    if not files:
        return ("add_document", "أضف مستند بحثك لتبدأ",
                "Add your research document to begin")

    pending = (await session.execute(
        select(func.count(FactCandidate.id))
        .join(ProjectFile, ProjectFile.file_id == FactCandidate.file_id)
        .where(FactCandidate.tenant_id == tenant_id,
               ProjectFile.project_id == project_id,
               FactCandidate.status == "unverified")
    )).scalar_one()
    if pending:
        return ("review_facts", f"راجع {pending} معلومة استخرجتها أثيرا",
                f"Review {pending} extracted facts")

    opportunities = (await session.execute(
        select(func.count(PublicationOpportunity.id)).where(
            PublicationOpportunity.tenant_id == tenant_id,
            PublicationOpportunity.project_id == project_id)
    )).scalar_one()
    if not opportunities:
        return ("plan_publication", "خطّط فرص النشر من معرفتك الموثقة",
                "Plan publication opportunities from your verified knowledge")

    manuscripts = (await session.execute(
        select(func.count(Manuscript.id)).where(
            Manuscript.tenant_id == tenant_id, Manuscript.project_id == project_id)
    )).scalar_one()
    if not manuscripts:
        return ("open_manuscript", "افتح ورقتك من الفرصة التي اخترتها",
                "Open your paper from the opportunity you selected")

    unreviewed = (await session.execute(
        select(func.count(ManuscriptSection.id))
        .join(ManuscriptVersion, ManuscriptVersion.id == ManuscriptSection.version_id)
        .join(Manuscript, Manuscript.id == ManuscriptVersion.manuscript_id)
        .where(ManuscriptSection.tenant_id == tenant_id,
               Manuscript.project_id == project_id,
               ManuscriptSection.review_status == "needs_review")
    )).scalar_one()
    if unreviewed:
        return ("review_sections", f"راجع {unreviewed} قسمًا ينتظر اعتمادك",
                f"Review {unreviewed} sections awaiting your approval")
    return None


async def live_project(session: AsyncSession, *, tenant_id: uuid.UUID,
                       project_id: uuid.UUID) -> ResearchProject | None:
    """بحثٌ قائم — **وما في السلّة ليس قائمًا**."""
    return (await session.execute(
        select(ResearchProject).where(
            ResearchProject.id == project_id,
            ResearchProject.tenant_id == tenant_id,
            ResearchProject.deleted_at.is_(None))
    )).scalar_one_or_none()


__all__ = ["BRAIN_FIELDS", "BrainEntry", "Consequence", "Impact", "dataset_impact",
           "file_impact", "file_processing_state", "file_processing_state_columns",
           "file_processing_state_of_row", "files_processing_state", "live_project",
           "next_action", "research_brain", "source_impact"]
