"""إزالةُ رسالةٍ من مركز الرسائل | Safe thesis removal (Wave 1.1).

**القاعدة: لا حذفٌ متسلسلٌ صامت.** الرسالة أصلُ سلسلةٍ علميّة — منها تُشتقّ
الفرص، ومن الفرص تُبنى اتفاقاتُ التأليف واعتماداتُ الحقوق، ومنها تُحوَّل
مشاريع. و`ON DELETE CASCADE` في القاعدة سيمحو الأوّل ويترك الباقي معلَّقًا
أو يمحوه معه — وكلاهما فقدٌ لقرارٍ بشريّ وقع.

فالإزالة تسبقها **معاينةُ تبعات** تُحسب في القاعدة وتُعرض على الباحث:

  • **ما يُعاد إنتاجه بقراءةٍ ثانية لا يمنع** — أقسامٌ ونتائجُ استخرجتها
    الآلة ولم يحكم عليها إنسان.
  • **وما فيه حكمُ إنسانٍ يمنع** — مرشّحٌ اعتُمد أو رُفض أو قيل فيه «لا
    أعرف»، وقسمٌ صار «متحقَّقًا»، وفرصةُ نشرٍ قائمة، ومشروعٌ حُوِّل عنها،
    واتفاقُ تأليفٍ أو اعتمادُ حقوق.

**والإزالة غيرُ نقل الملفّ إلى السلّة.** الأولى تُسقط سجلَّ مركز الرسائل،
والثاني يُخفي ملفَّ المكتبة — فعلان لصاحبين، ونقطتان مختلفتان، ولا يُنفَّذ
أحدهما بأثرٍ جانبيّ للآخر. **ولا يُمحى كائنُ التخزين نهائيًّا في أيٍّ منهما.**

**والتاريخ يبقى.** `audit_log.object_id` عمودٌ بلا مفتاحٍ أجنبيّ إلى
`theses` — قصدًا — فسجلُّ ما جرى على الرسالة يبقى مقروءًا بعد إسقاط صفّها.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.research import FactCandidate
from ...models.thesis import (
    AuthorshipAgreement,
    PublicationOpportunity,
    ThesisResult,
    ThesisSection,
)

# ═════════════════════ ١. مفردةُ التبعة ═════════════════════

DEP_SECTIONS: Final = "sections"
DEP_RESULTS: Final = "results"
DEP_VERIFIED_SECTIONS: Final = "verified_sections"
DEP_REVIEWED_CANDIDATES: Final = "reviewed_candidates"
DEP_OPPORTUNITIES: Final = "publication_opportunities"
DEP_CONVERTED_PROJECTS: Final = "converted_projects"
DEP_AUTHORSHIP_RECORDS: Final = "authorship_records"
DEP_RIGHTS_APPROVALS: Final = "rights_approvals"

DEPENDENCY_KEYS: Final[tuple[str, ...]] = (
    DEP_SECTIONS, DEP_RESULTS, DEP_VERIFIED_SECTIONS, DEP_REVIEWED_CANDIDATES,
    DEP_OPPORTUNITIES, DEP_CONVERTED_PROJECTS, DEP_AUTHORSHIP_RECORDS,
    DEP_RIGHTS_APPROVALS,
)

#: **التبعاتُ التي تمنع.** كلُّ واحدةٍ منها أثرُ حكمٍ بشريٍّ أو أصلٌ علميٌّ
#: قائمٌ عليها؛ وإسقاطُ الرسالة يُسقطها أو يقطع صلتها بأصلها. والأقسامُ
#: والنتائجُ **ليست** منها: آلةٌ كتبتها، وقراءةٌ ثانية تُعيدها كما هي.
BLOCKING_KEYS: Final[frozenset[str]] = frozenset({
    DEP_VERIFIED_SECTIONS, DEP_REVIEWED_CANDIDATES, DEP_OPPORTUNITIES,
    DEP_CONVERTED_PROJECTS, DEP_AUTHORSHIP_RECORDS, DEP_RIGHTS_APPROVALS,
})

DEPENDENCY_LABELS: Final[dict[str, tuple[str, str]]] = {
    DEP_SECTIONS: ("أقسام مستخرجة", "Extracted sections"),
    DEP_RESULTS: ("نتائج مستخرجة", "Extracted results"),
    DEP_VERIFIED_SECTIONS: ("أقسام راجعتَها بنفسك", "Sections you reviewed yourself"),
    DEP_REVIEWED_CANDIDATES: ("مرشّحاتٌ حسمتَها بقرار", "Candidates you decided on"),
    DEP_OPPORTUNITIES: ("فرص نشرٍ مرشَّحة", "Candidate publication opportunities"),
    DEP_CONVERTED_PROJECTS: ("مشاريع بحثية حُوِّلت عن فرصها",
                             "Research projects converted from its opportunities"),
    DEP_AUTHORSHIP_RECORDS: ("اتفاقات تأليف", "Authorship agreements"),
    DEP_RIGHTS_APPROVALS: ("اعتمادات حقوق", "Rights approvals"),
}

#: قرارات الإنسان على مرشَّح — و«لا أعرف» قرارٌ مثل «معتمَد» تمامًا (§7).
REVIEWED_CANDIDATE_STATES: Final[tuple[str, ...]] = ("approved", "rejected", "unknown")

_REFUSAL_AR: Final = (
    "لا تُزال هذه الرسالة: يقوم عليها عملٌ علميٌّ حسمتَه بنفسك. إزالتُها تُسقط "
    "ما بُني عليها أو تقطع صلتَه بأصله، وكلاهما فقدٌ لا يُستعاد. أزِل ما بُني "
    "عليها أوّلًا إن أردت — أو اترك السجلّ كما هو."
)
_REFUSAL_EN: Final = (
    "This thesis cannot be removed: scientific work you decided on rests on it. Removing "
    "it would drop what was built on it or sever that work from its source, and neither "
    "can be undone. Remove what was built on it first if that is what you want, or leave "
    "the record as it is."
)

_DISPOSABLE_AR: Final = (
    "لا شيء علميٌّ قائمٌ على هذه الرسالة. إزالتُها تُسقط سجلَّها من مركز الرسائل "
    "وما استخرجته الآلة منه، ويبقى سجلُّ التدقيق كاملًا. **ولا يُمسّ ملفُّ "
    "المكتبة**: نقلُه إلى السلّة فعلٌ آخر تطلبه وحدك."
)
_DISPOSABLE_EN: Final = (
    "Nothing scientific rests on this thesis. Removing it drops its Thesis Center record "
    "and what the machine extracted into it; the audit history stays complete. The library "
    "file is untouched: moving it to the trash is a separate action you ask for yourself."
)


# ═════════════════════ ٢. المعاينة ═════════════════════

@dataclass(frozen=True, slots=True)
class Dependency:
    key: str
    count: int
    blocking: bool


@dataclass(frozen=True, slots=True)
class RemovalPreview:
    """ما يقوم على الرسالة — **قبل الإزالة، لا بعدها**."""

    thesis_id: uuid.UUID
    dependencies: tuple[Dependency, ...]

    @property
    def blocking(self) -> tuple[Dependency, ...]:
        return tuple(d for d in self.dependencies if d.blocking and d.count > 0)

    @property
    def removable(self) -> bool:
        return not self.blocking

    def counts(self) -> dict[str, int]:
        return {d.key: d.count for d in self.dependencies}

    def blocking_counts(self) -> dict[str, int]:
        return {d.key: d.count for d in self.blocking}

    def explanation(self, locale: str) -> str:
        if self.removable:
            return _DISPOSABLE_EN if locale == "en" else _DISPOSABLE_AR
        return _REFUSAL_EN if locale == "en" else _REFUSAL_AR


def label(key: str, locale: str) -> str:
    arabic, english = DEPENDENCY_LABELS[key]
    return english if locale == "en" else arabic


async def preview(
    session: AsyncSession, *, tenant_id: uuid.UUID, thesis_id: uuid.UUID,
    file_id: uuid.UUID | None,
) -> RemovalPreview:
    """يحسب التبعات — **بعبارةٍ واحدة، لا ثمانِ رحلاتٍ إلى مومباي**.

    ثمانيةُ أعدادٍ في `SELECT` واحد: القاعدة في مومباي والخادم في سنغافورة،
    وكلُّ رحلةٍ ستّون جزءًا من الثانية. وثمانِ رحلاتٍ لسؤالٍ واحد نصفُ ثانية
    يدفعها الباحث قبل أن يُعرض عليه سؤالُ «أمتأكّد؟».

    **والعزل مكتوبٌ في كلّ شرط.** RLS تحمي بين المستأجرين ولا تحمي بين
    رسالتين في المستأجر الواحد؛ فكلُّ عدٍّ مشروطٌ بـ`thesis_id` وبالمستأجر
    معًا.
    """
    sections = (
        select(func.count(ThesisSection.id))
        .where(ThesisSection.tenant_id == tenant_id,
               ThesisSection.thesis_id == thesis_id)
        .scalar_subquery()
    )
    verified_sections = (
        select(func.count(ThesisSection.id))
        .where(ThesisSection.tenant_id == tenant_id,
               ThesisSection.thesis_id == thesis_id,
               ThesisSection.verification_status != "unverified")
        .scalar_subquery()
    )
    results = (
        select(func.count(ThesisResult.id))
        .where(ThesisResult.tenant_id == tenant_id,
               ThesisResult.thesis_id == thesis_id)
        .scalar_subquery()
    )
    opportunities = (
        select(func.count(PublicationOpportunity.id))
        .where(PublicationOpportunity.tenant_id == tenant_id,
               PublicationOpportunity.thesis_id == thesis_id)
        .scalar_subquery()
    )
    converted = (
        select(func.count(PublicationOpportunity.id))
        .where(PublicationOpportunity.tenant_id == tenant_id,
               PublicationOpportunity.thesis_id == thesis_id,
               PublicationOpportunity.converted_project_id.is_not(None))
        .scalar_subquery()
    )
    rights = (
        select(func.count(PublicationOpportunity.id))
        .where(PublicationOpportunity.tenant_id == tenant_id,
               PublicationOpportunity.thesis_id == thesis_id,
               PublicationOpportunity.rights_approved_at.is_not(None))
        .scalar_subquery()
    )
    authorship = (
        select(func.count(AuthorshipAgreement.id))
        .where(
            AuthorshipAgreement.tenant_id == tenant_id,
            AuthorshipAgreement.opportunity_id.in_(
                select(PublicationOpportunity.id).where(
                    PublicationOpportunity.tenant_id == tenant_id,
                    PublicationOpportunity.thesis_id == thesis_id)
            ),
        )
        .scalar_subquery()
    )
    # **المرشّحات معلَّقةٌ بالملفّ لا بالرسالة** (`fact_candidates.file_id`)،
    # فرسالةٌ بلا ملفّ لا مرشّحات لها — و`0` هنا حقيقةٌ لا تخمين، ولا يُرسَل
    # عمودٌ يقارن معرّفًا بـ`NULL` فيردّ صفرًا لسببٍ آخر.
    reviewed_expr = (
        select(func.count(FactCandidate.id))
        .where(FactCandidate.tenant_id == tenant_id,
               FactCandidate.file_id == file_id,
               FactCandidate.status.in_(REVIEWED_CANDIDATE_STATES))
        .scalar_subquery()
    ) if file_id is not None else None

    columns = [
        sections.label(DEP_SECTIONS),
        results.label(DEP_RESULTS),
        verified_sections.label(DEP_VERIFIED_SECTIONS),
        opportunities.label(DEP_OPPORTUNITIES),
        converted.label(DEP_CONVERTED_PROJECTS),
        rights.label(DEP_RIGHTS_APPROVALS),
        authorship.label(DEP_AUTHORSHIP_RECORDS),
    ]
    if reviewed_expr is not None:
        columns.append(reviewed_expr.label(DEP_REVIEWED_CANDIDATES))

    row = (await session.execute(select(*columns))).mappings().one()
    counts = {key: int(row[key] or 0) for key in row}
    counts.setdefault(DEP_REVIEWED_CANDIDATES, 0)

    return RemovalPreview(
        thesis_id=thesis_id,
        dependencies=tuple(
            Dependency(key=key, count=counts.get(key, 0), blocking=key in BLOCKING_KEYS)
            for key in DEPENDENCY_KEYS
        ),
    )
