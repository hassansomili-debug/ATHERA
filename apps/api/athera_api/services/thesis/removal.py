"""أرشفةُ رسالةٍ من مركز الرسائل | Safe thesis archiving (Wave 1.1).

**القاعدة الأولى: لا حذفٌ فيزيائيّ، ولا حذفٌ متسلسلٌ صامت.**

وأوّلُ علاجٍ لغياب المخرج كتب `DELETE FROM theses` على رسالةٍ لا تبعات
علميّة لها. والصفُّ أصلُ سلسلةٍ: منه الأقسام والنتائج ومرشّحاتُ الوقائع
والفرص واتفاقاتُ التأليف واعتماداتُ الحقوق والمشاريع المحوَّلة، و
`ON DELETE CASCADE` قائمٌ على خمسة جداول. و«لا تبعات **اليوم**» ليست «لن
تكون»، والحذفُ لا يُستعاد.

فلا تُحذف رسالة. تُؤرشَف: وسمٌ بوقتٍ وفاعل (ترحيل 0030)، تخرج به من
القائمة الافتراضية، **ويبقى كلُّ ما تحتها كما هو** — والاسترجاع يمحو الوسم
فتعود حرفًا بحرف.

## والمعاينةُ بقيت، ومعناها تغيّر

كانت تقول «هذا يمنع الحذف». والحذفُ ذهب، فما عادت تمنع شيئًا: صارت تقول
**«هذا ما سيُخفى معها»** — ويبقى موجودًا، ويعود بالاسترجاع.

**لكنّها لا تُهمَل.** إخفاءُ رسالةٍ تتدلّى منها فرصُ نشرٍ ومشاريعُ محوَّلة
واعتماداتُ حقوق قرارٌ يُتّخذ بعلمٍ لا بغفلة. فما فيه حكمُ إنسانٍ يستوجب
**إقرارًا صريحًا** (`acknowledge`)، ويردّ الخادمُ الطلبَ بلا إقرارٍ بـ409
ومعه المعاينة. وهو حدٌّ يقف على الخادم لا في الشاشة وحدها.

**والأرشفةُ غيرُ نقل الملفّ إلى السلّة.** الأولى تُخفي سجلَّ مركز الرسائل،
والثاني يُخفي ملفَّ المكتبة — فعلان لصاحبين، ونقطتان مختلفتان، ولا يُنفَّذ
أحدهما بأثرٍ جانبيّ للآخر. **ولا يُمحى كائنُ تخزينٍ نهائيًّا في أيٍّ منهما.**
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

#: **التبعاتُ التي تستوجب إقرارًا صريحًا.** كلُّ واحدةٍ منها أثرُ حكمٍ
#: بشريٍّ أو أصلٌ علميٌّ قائمٌ على الرسالة؛ وإخفاؤها يُخفيه معها — **ولا
#: يُتلفه**، والاسترجاع يعيده. فالإقرار شرطُ علمٍ لا حاجزُ منع. والأقسامُ
#: والنتائجُ ليست منها: آلةٌ كتبتها، وقراءةٌ ثانية تُعيدها كما هي.
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

_NEEDS_ACK_AR: Final = (
    "تقوم على هذه الرسالة نتائجُ عملٍ حسمتَه بنفسك. الأرشفة **لا تحذف شيئًا**: "
    "تُخفي السجلّ من مركز الرسائل ويبقى كلُّ ما تحته كما هو، ويعود بالاسترجاع. "
    "لكنّ إخفاءَ ما يتدلّى منه عملٌ قائم قرارٌ يُتّخذ بعلم — فيُطلب إقرارُك صراحةً."
)
_NEEDS_ACK_EN: Final = (
    "Work you decided on yourself rests on this thesis. Archiving deletes nothing: it "
    "hides the record from the Thesis Center, everything under it stays exactly as it "
    "is, and restoring brings it all back. But hiding a record that live work hangs "
    "from is a decision to take knowingly, so your explicit acknowledgement is required."
)

_DISPOSABLE_AR: Final = (
    "لا شيء علميٌّ قائمٌ على هذه الرسالة. الأرشفة تُخفي سجلَّها من مركز الرسائل "
    "ولا تحذف شيئًا، ويبقى سجلُّ التدقيق كاملًا. **ولا يُمسّ ملفُّ المكتبة**: "
    "نقلُه إلى السلّة فعلٌ آخر تطلبه وحدك."
)
_DISPOSABLE_EN: Final = (
    "Nothing scientific rests on this thesis. Archiving hides its Thesis Center record "
    "and deletes nothing; the audit history stays complete. The library file is "
    "untouched: moving it to the trash is a separate action you ask for yourself."
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
    def needs_acknowledgement(self) -> bool:
        """**هل يستوجب الإخفاءُ إقرارًا صريحًا؟** — لا «هل يُمنع».

        الأرشفة لا تُمنع: هي فعلٌ يُستعاد. والمطلوب أن يقع بعلمٍ لا بغفلة.
        """
        return bool(self.blocking)

    def counts(self) -> dict[str, int]:
        return {d.key: d.count for d in self.dependencies}

    def acknowledged_counts(self) -> dict[str, int]:
        return {d.key: d.count for d in self.blocking}

    def explanation(self, locale: str) -> str:
        if self.needs_acknowledgement:
            return _NEEDS_ACK_EN if locale == "en" else _NEEDS_ACK_AR
        return _DISPOSABLE_EN if locale == "en" else _DISPOSABLE_AR


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
