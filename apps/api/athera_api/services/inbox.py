"""صندوق القرارات | Decision inbox rules (§9، §25).

منطق خالص بلا نماذج: ما هي البوابات، وأيّ التنبيهات يحجب، وكيف يُقرأ
الاعتماد. الفصل مقصود — القواعد تُختبر بلا قاعدة بيانات.
"""
from typing import Final

# §9 — البوابات كبيانات لا كسلاسل متناثرة في الموجّهات.
GATES: Final[dict[str, tuple[str, str]]] = {
    "G0": ("اعتماد حقيقة مستخرَجة", "Approve an extracted fact"),
    "G1": ("اعتماد الملف الأكاديمي للباحث", "Approve the researcher profile"),
    "G2": ("اعتماد المشكلة والفجوة", "Approve problem and gap"),
    "G3": ("اعتماد السؤال والهدف", "Approve question and objective"),
    "G4": ("اعتماد الإطار النظري", "Approve theoretical framework"),
    "G5": ("اعتماد المنهجية", "Approve methodology"),
    "G6": ("تجميد نسخة البيانات", "Freeze the dataset version"),
    "G7": ("قفل خطة التحليل", "Lock the analysis plan"),
    "G8": ("اعتماد التفسير", "Approve the interpretation"),
    "G9": ("جاهزية المخطوطة للتقديم", "Manuscript readiness for submission"),
    "G10": ("اعتماد المجلة المستهدفة", "Approve the target journal"),
    "G11": ("اعتماد حزمة التقديم", "Approve the submission package"),
    "G12": ("اعتماد الرد على المحكّمين", "Approve the response to reviewers"),
    "GT1": ("اعتماد الحقوق والتأليف", "Approve rights and authorship"),
}

APPROVAL_STATUSES: Final[tuple[str, ...]] = ("pending", "approved", "rejected")

# §25 — الشدّة تحدد أثرًا لا لونًا: `blocking` يمنع بوابة، وغيره يُعرض.
ALERT_SEVERITIES: Final[dict[str, tuple[str, str, bool]]] = {
    "info": ("للعلم", "Informational", False),
    "warning": ("تحذير", "Warning", False),
    "blocking": ("حاجب", "Blocking", True),
}

ALERT_TYPES: Final[dict[str, tuple[str, str]]] = {
    "fabricated_reference": ("مرجع لا وجود له في مصدره", "Reference absent from its source"),
    "retracted_citation": ("استشهاد بمصدر مسحوب", "Citation of a retracted source"),
    "duplicate_publication": ("نشر مكرر محتمل", "Possible duplicate publication"),
    "salami_slicing": ("تجزئة غير مبررة", "Unjustified salami slicing"),
    "authorship_dispute": ("خلاف على التأليف", "Authorship dispute"),
    "undisclosed_conflict": ("تضارب مصالح غير معلن", "Undisclosed conflict of interest"),
    "unsupported_claim": ("ادعاء بلا سند", "Unsupported claim"),
    "stale_indexing": ("فهرسة انتهت صلاحية التحقق منها", "Indexing verification expired"),
    "data_not_frozen": ("تحليل على بيانات غير مجمَّدة", "Analysis on unfrozen data"),
}


class InboxError(Exception):
    pass


def is_blocking(severity: str) -> bool:
    """تنبيه بشدّة مجهولة يُعامل معاملة الحاجب.

    الافتراض المعاكس أخطر: شدّة لم نتعرّف عليها تمرّ صامتة، فيمرّ معها
    ما كان يجب أن يوقف بوابة.
    """
    if severity not in ALERT_SEVERITIES:
        return True
    return ALERT_SEVERITIES[severity][2]


def check_decidable(status: str) -> None:
    """§9 — لا يُبتّ في اعتماد محسوم مرتين.

    السماح بذلك يجعل «من اعتمد ومتى» قابلًا لإعادة الكتابة، وهو بالضبط ما
    يُفترض بسجل الاعتمادات أن يمنعه.
    """
    if status not in APPROVAL_STATUSES:
        raise InboxError(f"unknown approval status: {status}")
    if status != "pending":
        raise InboxError(f"approval already settled as {status}")


def gate_label(gate: str, locale: str) -> str:
    if gate not in GATES:
        return gate
    arabic, english = GATES[gate]
    return english if locale == "en" else arabic
