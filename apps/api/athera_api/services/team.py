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


def check_supersede(current_decided_at: object | None) -> None:
    """قرار محسوم لا يُعدَّل؛ يُنسَخ بقرار جديد يشير إليه.

    التعديل المباشر يمحو ما كان عليه الحال حين اتُّخذ القرار، فيصير سجل
    القرارات سردًا لما نظنه اليوم لا لما قرّرناه أمس.
    """
    if current_decided_at is not None:
        raise TeamError("a settled decision is superseded, never edited")
