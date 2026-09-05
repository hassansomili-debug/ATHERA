"""فريق المشروع وقراراته | Project team and decisions (§12، §24).

قاعدتان تُفرضان هنا لأنهما تُنتهكان بسهولة في الواجهة:
  • دور CRediT يُسجَّل ولا يُستنتج، ولا يُسند تأليف لغير إنسان أو جهة (§24).
  • القرار لا يُعدَّل: يُنسخ ويُشار إلى ما نسخه (`supersedes_id`).
"""
from typing import Final

# §24 — أدوار CRediT الأربعة عشر.
CREDIT_ROLES: Final[dict[str, tuple[str, str]]] = {
    "conceptualization": ("بلورة الفكرة", "Conceptualization"),
    "data_curation": ("تنظيم البيانات", "Data curation"),
    "formal_analysis": ("التحليل الشكلي", "Formal analysis"),
    "funding_acquisition": ("الحصول على التمويل", "Funding acquisition"),
    "investigation": ("التقصّي", "Investigation"),
    "methodology": ("المنهجية", "Methodology"),
    "project_administration": ("إدارة المشروع", "Project administration"),
    "resources": ("الموارد", "Resources"),
    "software": ("البرمجيات", "Software"),
    "supervision": ("الإشراف", "Supervision"),
    "validation": ("التحقق", "Validation"),
    "visualization": ("العرض المرئي", "Visualization"),
    "writing_original_draft": ("كتابة المسودة الأولى", "Writing — original draft"),
    "writing_review_editing": ("المراجعة والتحرير", "Writing — review & editing"),
}

MEMBER_ROLES: Final[dict[str, tuple[str, str]]] = {
    "principal_investigator": ("الباحث الرئيس", "Principal investigator"),
    "co_author": ("باحث مشارك", "Co-author"),
    "supervisor": ("مشرف", "Supervisor"),
    "student": ("طالب", "Student"),
    "statistician": ("محلل إحصائي", "Statistician"),
    "acknowledged": ("شكر وتقدير", "Acknowledged contributor"),
}

DECISION_KINDS: Final[dict[str, tuple[str, str]]] = {
    "problem": ("المشكلة البحثية", "Research problem"),
    "gap": ("الفجوة", "Gap"),
    "question": ("سؤال البحث", "Research question"),
    "objective": ("الهدف", "Objective"),
    "theory": ("الإطار النظري", "Theoretical framework"),
    "method": ("المنهجية", "Methodology"),
    "sample": ("العينة", "Sample"),
    "instrument": ("الأداة", "Instrument"),
    "target_journal": ("المجلة المستهدفة", "Target journal"),
    "authorship_order": ("ترتيب التأليف", "Authorship order"),
    "scope_change": ("تغيير النطاق", "Scope change"),
}

# §24 — أسماء تُرفض في خانة المؤلف. التأليف مسؤولية، ولا يتحملها نموذج.
_NON_HUMAN_MARKERS: Final[tuple[str, ...]] = (
    "chatgpt", "gpt-", "gpt4", "gpt5", "claude", "gemini", "copilot", "llama",
    "midjourney", "athera", "ai assistant", "language model", "شات جي بي تي",
    "الذكاء الاصطناعي", "نموذج لغوي", "مساعد ذكي",
)


class TeamError(Exception):
    pass


def validate_credit_roles(roles: list[str]) -> None:
    unknown = [role for role in roles if role not in CREDIT_ROLES]
    if unknown:
        raise TeamError(f"unknown CRediT roles: {', '.join(sorted(unknown))}")


def validate_author_name(display_name: str) -> None:
    """§24 — لا يُسند تأليف لنموذج ولا لأداة.

    الفحص على الاسم المعروض لأنه ما يُطبع في قائمة المؤلفين. أداة ساهمت
    تُذكر في المنهجية أو الشكر، لا في خانة يتحمل صاحبها المسؤولية.
    """
    name = display_name.strip()
    if not name:
        raise TeamError("an author needs a name")
    lowered = name.lower()
    for marker in _NON_HUMAN_MARKERS:
        if marker in lowered:
            raise TeamError(
                f"§24 — authorship cannot be assigned to a non-human agent: {display_name}"
            )


# ══════════════ فرق البحث ٢ — المفردات المغلقة (الترحيل 0028) ══════════════
#
# **الصلاحيةُ ليست الدور.** والدورُ يقول أين يقف الشريك في الفريق؛
# والصلاحيةُ تقول ما الذي يستطيع أن يفعله بيده. وطيُّ الثاني في الأول يعني
# أن كلَّ «مشرف» يحرّر البيانات لأنه مشرف — وهو ما لا يقبله باحث.
PROJECT_PERMISSIONS: Final[dict[str, tuple[str, str]]] = {
    "view_project": ("الاطّلاع على البحث", "View project"),
    "edit_research_content": ("تحرير المحتوى البحثي", "Edit research content"),
    "manage_sources": ("إدارة المصادر", "Manage sources"),
    "manage_data": ("إدارة البيانات", "Manage data"),
    "manage_tasks": ("إدارة المهام", "Manage tasks"),
    "review_scientific_candidates": ("مراجعة المرشَّحات العلمية",
                                     "Review scientific candidates"),
    "approve_scientific_candidates": ("اعتماد المرشَّحات العلمية",
                                      "Approve scientific candidates"),
    "manage_team": ("إدارة الفريق", "Manage team"),
    "manage_submission": ("إدارة التقديم", "Manage submission"),
}

# **الافتراضُ اقتراحٌ عند الدعوة، لا قاعدةً تُشتقّ بعدها.** وبعد القبول
# تُقرأ الصلاحيات من صفوفها وحدها — فتغييرُ الدور لا يوسّعها ولا يضيّقها.
#
# ولاحظ الحالتين اللتين توجدان في كل فريق:
#   • `statistician` له `manage_data` ولا إدارةَ مشروعٍ له.
#   • `supervisor` يراجع ويعتمد ولا يحرّر البيانات ولا المحتوى.
# وأيُّ مجموعةٍ افتراضية تعطي التسعة لأحدٍ غير الباحث الرئيس عطبٌ لا اختصار.
ROLE_DEFAULT_PERMISSIONS: Final[dict[str, tuple[str, ...]]] = {
    "principal_investigator": tuple(PROJECT_PERMISSIONS),
    "co_author": ("view_project", "edit_research_content", "manage_sources"),
    "supervisor": ("view_project", "review_scientific_candidates",
                   "approve_scientific_candidates"),
    "student": ("view_project", "edit_research_content", "manage_sources",
                "manage_tasks"),
    "statistician": ("view_project", "manage_data", "review_scientific_candidates"),
    # شكرٌ وتقدير: يرى البحث ولا يمسّه. والعضويةُ وحدها لا تمنح شيئًا سواه.
    "acknowledged": ("view_project",),
}

INVITATION_STATES: Final[tuple[str, ...]] = (
    "invited", "accepted", "declined", "expired", "revoked")

MEMBER_ACCESS_STATES: Final[tuple[str, ...]] = (
    "invited", "active", "suspended", "removed")

CONSENT_STATES: Final[tuple[str, ...]] = (
    "not_requested", "pending", "granted", "declined")

# **`legacy_unverified` لا يكتبها التطبيق أبدًا.** هي وسمُ ما سُجِّل تحت
# المسار المعطوب قبل الترحيل 0028: موافقةٌ لا يُعرف مَن سجّلها. وترقيتُها
# صامتةً إلى `self` هي الكذبة التي أُصلحت، لا إصلاحها.
CONSENT_METHODS: Final[tuple[str, ...]] = (
    "self", "administrative", "legacy_unverified")

WRITABLE_CONSENT_METHODS: Final[frozenset[str]] = frozenset({"self", "administrative"})

MEMBER_EVENT_KINDS: Final[tuple[str, ...]] = (
    "invited", "accepted", "declined", "expired", "revoked",
    "role_changed", "permissions_changed", "credit_changed",
    "authorship_declared", "authorship_withdrawn",
    "consent_requested", "consent_granted", "consent_declined",
    "access_suspended", "access_restored", "removed", "left",
)

CONSENT_METHOD_LABELS: Final[dict[str, tuple[str, str]]] = {
    "self": ("وافق بنفسه", "Consented in person"),
    "administrative": ("موافقة إدارية موثَّقة", "Documented administrative consent"),
    "legacy_unverified": ("موافقة قديمة مجهولة المصدر",
                          "Legacy consent, recorder unknown"),
}

ACCESS_STATE_LABELS: Final[dict[str, tuple[str, str]]] = {
    "invited": ("مدعو", "Invited"),
    "active": ("نشِط", "Active"),
    "suspended": ("موقوف", "Suspended"),
    "removed": ("مُزال", "Removed"),
}

CONSENT_STATE_LABELS: Final[dict[str, tuple[str, str]]] = {
    "not_requested": ("لم تُطلب", "Not requested"),
    "pending": ("بانتظار المؤلف", "Awaiting the author"),
    "granted": ("مُنحت", "Granted"),
    "declined": ("رُفضت", "Declined"),
}

INVITATION_STATE_LABELS: Final[dict[str, tuple[str, str]]] = {
    "invited": ("دعوة قائمة", "Pending"),
    "accepted": ("قُبلت", "Accepted"),
    "declined": ("رُفضت", "Declined"),
    "expired": ("انتهت مهلتها", "Expired"),
    "revoked": ("سُحبت", "Revoked"),
}

INVITATION_TTL_HOURS: Final[int] = 14 * 24


def default_permissions(role: str) -> tuple[str, ...]:
    """صلاحياتُ دورٍ **مقترَحة**. ودورٌ لا نعرفه يأخذ الاطّلاع وحده.

    والافتراضُ الآمن ليس تفصيلًا: دورٌ يُضاف غدًا بلا مدخلٍ هنا كان
    سيأخذ إمّا كلَّ شيء وإمّا لا شيء. والأول تسريبُ صلاحيات صامت.
    """
    return ROLE_DEFAULT_PERMISSIONS.get(role, ("view_project",))


def validate_permissions(keys: list[str]) -> None:
    unknown = [key for key in keys if key not in PROJECT_PERMISSIONS]
    if unknown:
        raise TeamError(f"unknown project permissions: {', '.join(sorted(unknown))}")


def normalize_email(email: str) -> str:
    """البريدُ يُطابَق بحروفٍ صغيرة ومقلَّمًا — وإلّا صار للشخص دعوتان."""
    return email.strip().lower()


def check_supersede(current_decided_at: object | None) -> None:
    """قرار محسوم لا يُعدَّل؛ يُنسَخ بقرار جديد يشير إليه.

    التعديل المباشر يمحو ما كان عليه الحال حين اتُّخذ القرار، فيصير سجل
    القرارات سردًا لما نظنه اليوم لا لما قرّرناه أمس.
    """
    if current_decided_at is not None:
        raise TeamError("a settled decision is superseded, never edited")
