"""سجل المراجع المنهجية | Methodology canon registry (أساس العقل البحثي).

**سجلٌ يصف مرجعًا، ولا يحمل نصَّه.** لا بايت واحد من متن أيّ كتاب هنا،
ولا مسار يجلبه. الغرض الوحيد أن يكون الوضع القانوني للمرجع **حقلًا أوّليًّا
إلزاميًّا** يُقرأ قبل أيّ استيعاب، لا حاشيةً تُراجَع بعده.

ولماذا هذا أوّل ما يُبنى: لأن استيعاب متن محميّ بحقوق نشر لا يُتراجَع عنه.
النموذج يقرأ ما أُدخل إليه، والمخرَج يحمل أثره، والحذف بعد ذلك لا يعيد شيئًا
إلى ما كان. فالبوابة تُبنى قبل الطريق لا بعده.

## الإذن ثلاث حالات لا حالتان

    unknown   لم يُفحص أحد — والغياب ليس إذنًا
    denied    فُحص، والجواب: لا
    granted   فُحص، والجواب: نعم، ومعه مستنده ومَن قاله

وهذا هو الدرس نفسه الذي سجّله ترحيل 0016 في قرار الباحث: «لا أعرف» ليست
«لا». وخلطهما هنا أخطر من خلطهما هناك: مرجعٌ وضعه مجهول يُقرأ ممنوعًا
فيُهمَل — خسارةٌ تُصلَح؛ ومرجعٌ ممنوع يُقرأ مجهولًا ثم يُقرأ مسموحًا
فيُستوعَب — خسارةٌ لا تُصلَح. فالدالة الوحيدة التي تأذن هي
`may_ingest`، ولا تُرجع `True` إلا للحالة الثالثة وحدها.

**ولا مرجع في هذا السجل مأذون اليوم.** كل ما فيه `unknown`، لأن أحدًا لم
يفحص بعد — وكتابة `granted` بلا فحصٍ جرى فعلًا هي بالضبط الاختلاق الذي
تقوم المنصّة على منعه.
"""
from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator


class IngestionPermission(str, Enum):
    """إذن الاستيعاب — والمجهول ليس ممنوعًا وليس مأذونًا."""

    UNKNOWN = "unknown"
    DENIED = "denied"
    GRANTED = "granted"


class LicenseStatus(str, Enum):
    """حال الترخيص كما هو معلَن على المرجع نفسه."""

    UNKNOWN = "unknown"
    PUBLIC_DOMAIN = "public_domain"
    OPEN_LICENCE = "open_licence"
    PROPRIETARY = "proprietary"


class CopyrightStatus(str, Enum):
    """حال حقوق النشر — منفصلٌ عن الترخيص عمدًا.

    كتابٌ في الملك العام لا ترخيص له أصلًا، وكتابٌ محميٌّ قد يُرخَّص لنا
    استعماله. فدمج الحقلين يجعل الجوابين المختلفين خانةً واحدة تكذب في
    أحدهما.
    """

    UNKNOWN = "unknown"
    IN_COPYRIGHT = "in_copyright"
    PUBLIC_DOMAIN = "public_domain"
    RIGHTS_CLEARED = "rights_cleared"


class SourceType(str, Enum):
    """نوع المرجع المنهجي."""

    TEXTBOOK = "textbook"
    HANDBOOK = "handbook"
    REPORTING_STANDARD = "reporting_standard"
    STYLE_MANUAL = "style_manual"
    GUIDELINE = "guideline"
    JOURNAL_ARTICLE = "journal_article"


# حالات التحقق الثلاث — **منقولة حرفيًّا** عن قيد `ck_source_status` في
# ترحيل 0008، لا مخترعة هنا. سجلٌ ثانٍ بمفردات ثانية للشيء نفسه هو أسرع
# طريق إلى حالةٍ تُقرأ في مكان وتُكتب في مكان آخر بمعنًى ثالث.
VERIFICATION_STATES: Final[tuple[str, ...]] = ("unverified", "verified", "rejected")


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"


class MethodologySource(BaseModel):
    """مرجع منهجي مسجَّل — **وصفه لا متنه**.

    ولا حقل هنا لنصّ المرجع ولا لمقتطف منه، وهذا غيابٌ مقصود: عقدٌ لا موضع
    فيه للمتن لا يستطيع أحد أن يملأه سهوًا.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=3, max_length=64)
    title: str = Field(min_length=3)
    author: str = Field(min_length=2)
    edition: str | None = None
    year: int | None = Field(default=None, ge=1500, le=2100)
    language: str = Field(pattern="^(ar|en)$")
    domain: str = Field(min_length=2)
    source_type: SourceType

    license_status: LicenseStatus = LicenseStatus.UNKNOWN
    copyright_status: CopyrightStatus = CopyrightStatus.UNKNOWN
    ingestion_permission: IngestionPermission = IngestionPermission.UNKNOWN
    # مستند الإذن: عقدٌ أو ترخيصٌ أو رسالةُ ناشر. مطلوبٌ عند `granted` وحده.
    permission_basis: str | None = None

    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    reviewed_by: str | None = None
    reviewed_at: dt.datetime | None = None
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _permission_needs_a_basis(self) -> MethodologySource:
        """إذنٌ بلا مستندٍ مسمّى ليس إذنًا.

        القاعدة نفسها التي تفرضها القاعدةُ في `ck_project_source_decision_actor`:
        قرارٌ لا يُعرف مستنده ولا قائله يُعامَل بعد شهور كأنه واقعٌ قديم لا
        قرارٌ يُراجَع. وهنا الأثر أكبر: «مأذون» مكتوبةً بلا مستند تفتح باب
        الاستيعاب على مصراعيه بكلمةٍ لا يملك أحد أن يدافع عنها.
        """
        if self.ingestion_permission is IngestionPermission.GRANTED:
            if not (self.permission_basis or "").strip():
                raise ValueError("granted ingestion needs a named permission basis")
        elif self.permission_basis is not None:
            raise ValueError("permission_basis belongs to a granted permission only")
        return self

    @model_validator(mode="after")
    def _verified_needs_a_reviewer(self) -> MethodologySource:
        """«متحقَّق» يلزمه مُراجِعٌ وتاريخ — كما في `ck_source_verified_requires_registry_or_upload`.

        حالةٌ ترفع رتبة المعلومة ولا تُنسب إلى إنسان هي مصدرُ ثقةٍ بلا
        صاحب: لا يُسأل أحد عنها، ولا تُراجَع، ولا تسقط حين يتبيّن خطؤها.
        """
        if self.verification_status is VerificationStatus.VERIFIED:
            if self.reviewed_by is None or self.reviewed_at is None:
                raise ValueError("a verified source needs both reviewed_by and reviewed_at")
        return self

    @model_validator(mode="after")
    def _granted_needs_verification(self) -> MethodologySource:
        """لا استيعاب من مرجعٍ لم يُتحقَّق منه بعد.

        الشرطان مستقلّان في المعنى ومتلازمان في الأثر: الإذن يقول «يجوز
        قانونًا»، والتحقق يقول «وهذا هو المرجع فعلًا لا نسخةٌ مجهولة
        المصدر». وإذنٌ على مرجعٍ لم يُتحقَّق منه يأذن لشيءٍ لا يُعرف ما هو.
        """
        if (self.ingestion_permission is IngestionPermission.GRANTED
                and self.verification_status is not VerificationStatus.VERIFIED):
            raise ValueError("ingestion may be granted only for a verified source")
        return self


def may_ingest(source: MethodologySource) -> bool:
    """البوابة الوحيدة. `granted` صراحةً، وما عداها لا.

    الصياغة إيجابية عمدًا (`is GRANTED`) لا سلبية (`is not DENIED`): الصيغة
    السلبية تجعل كلَّ حالةٍ تُضاف مستقبلًا مأذونةً افتراضًا، وهو انفتاحٌ
    صامت لا يلاحظه أحد حتى يقع.
    """
    return source.ingestion_permission is IngestionPermission.GRANTED


def ingestion_reason(source: MethodologySource) -> tuple[str, str]:
    """سبب المنع بلغتين — ولا يُقال «ممنوع» عن مرجعٍ لم يُفحص.

    الرسالة تفرّق بين الحالتين لأن العمل المطلوب مختلف: المجهول يحتاج
    فحصًا، والممنوع يحتاج قرارًا آخر أو مرجعًا آخر. ورسالةٌ واحدة لهما
    ترسل الباحث إلى الطريق الخطأ.
    """
    if may_ingest(source):
        return ("الاستيعاب مأذون بمستندٍ مسجَّل.", "Ingestion is permitted by a recorded basis.")
    if source.ingestion_permission is IngestionPermission.DENIED:
        return (
            "الاستيعاب ممنوع لهذا المرجع — وهذا حكمٌ مسجَّل لا غيابُ فحص.",
            "Ingestion is denied for this source — a recorded decision, not an unchecked gap.",
        )
    return (
        "الوضع القانوني لهذا المرجع لم يُفحص بعد، والمجهول ليس إذنًا.",
        "The legal status of this source has not been checked; unknown is not permission.",
    )


def _draft(
    id: str, title: str, author: str, domain: str, source_type: SourceType,
    *, year: int | None = None, edition: str | None = None, language: str = "en",
) -> MethodologySource:
    """مُدخَلٌ في السجل بحالته الصادقة: مجهول الوضع، غير متحقَّق منه.

    ولا معامل هنا لتمرير `granted`: الإذن يُكتب بيدٍ تعرف مستنده، لا يُمرَّر
    وسيطًا في دالةٍ مساعدة تُستدعى في سطرٍ واحد.
    """
    return MethodologySource(
        id=id, title=title, author=author, edition=edition, year=year,
        language=language, domain=domain, source_type=source_type,
    )


# ── السجل ──
#
# مراجع منهجية معروفة تُذكر **بأسمائها** ليكون واضحًا أيّها لم يُفحص بعد.
# وكلها `unknown`، وكلها `unverified`، ولا واحد منها قابل للاستيعاب اليوم.
# القائمة تنمو بالفحص لا بالإضافة.
CANON: Final[tuple[MethodologySource, ...]] = (
    _draft("creswell-research-design", "Research Design: Qualitative, Quantitative, and Mixed Methods Approaches",
           "Creswell, J. W.; Creswell, J. D.", "research_design", SourceType.TEXTBOOK,
           year=2022, edition="6th"),
    _draft("hair-multivariate", "Multivariate Data Analysis",
           "Hair, J. F.; Black, W. C.; Babin, B. J.; Anderson, R. E.",
           "multivariate_statistics", SourceType.TEXTBOOK, year=2018, edition="8th"),
    _draft("field-discovering-statistics", "Discovering Statistics Using IBM SPSS Statistics",
           "Field, A.", "applied_statistics", SourceType.TEXTBOOK, year=2024, edition="6th"),
    _draft("shadish-quasi-experimentation",
           "Experimental and Quasi-Experimental Designs for Generalized Causal Inference",
           "Shadish, W. R.; Cook, T. D.; Campbell, D. T.", "causal_inference",
           SourceType.TEXTBOOK, year=2002),
    _draft("miles-huberman-qualitative", "Qualitative Data Analysis: A Methods Sourcebook",
           "Miles, M. B.; Huberman, A. M.; Saldaña, J.", "qualitative_analysis",
           SourceType.HANDBOOK, year=2019, edition="4th"),
    _draft("apa-publication-manual", "Publication Manual of the American Psychological Association",
           "American Psychological Association", "reporting_style", SourceType.STYLE_MANUAL,
           year=2019, edition="7th"),
    _draft("prisma-2020", "PRISMA 2020 Statement", "Page, M. J. et al.",
           "systematic_review", SourceType.REPORTING_STANDARD, year=2021),
    _draft("consort-2010", "CONSORT 2010 Statement", "Schulz, K. F. et al.",
           "randomized_trial", SourceType.REPORTING_STANDARD, year=2010),
    _draft("strobe-statement", "STROBE Statement", "von Elm, E. et al.",
           "observational_study", SourceType.REPORTING_STANDARD, year=2007),
    _draft("coreq-checklist", "COREQ: Consolidated Criteria for Reporting Qualitative Research",
           "Tong, A.; Sainsbury, P.; Craig, J.", "qualitative_reporting",
           SourceType.REPORTING_STANDARD, year=2007),
    _draft("srqr-standards", "SRQR: Standards for Reporting Qualitative Research",
           "O'Brien, B. C. et al.", "qualitative_reporting",
           SourceType.REPORTING_STANDARD, year=2014),
    _draft("cochrane-handbook", "Cochrane Handbook for Systematic Reviews of Interventions",
           "Higgins, J. P. T. et al.", "systematic_review", SourceType.HANDBOOK, year=2023),
)

BY_ID: Final[dict[str, MethodologySource]] = {source.id: source for source in CANON}


def get(source_id: str) -> MethodologySource | None:
    return BY_ID.get(source_id)


def ingestible() -> tuple[MethodologySource, ...]:
    """المراجع المأذون استيعابها — فارغةٌ اليوم، وصدقُها في فراغها."""
    return tuple(source for source in CANON if may_ingest(source))
