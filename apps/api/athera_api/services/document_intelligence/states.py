"""حالات المعالجة | The processing state machine (§3، §7).

**الحالة تسكن `extraction_runs` لا `files`.** الأول يصف تشغيلة والثاني يصف
تخزينًا: ملفٌ محفوظ يبقى محفوظًا وإن فشل استخراجه، ورفعه لا يُلغى بفشل
قراءة. وخلطهما يجعل فشل النموذج يبدو فقدانًا للملف.

وكل فشل يُسمّى بسببه: `parse_failed` غير `extraction_failed`. الأولى تعني
«لم يُقرأ الملف» والثانية «قُرئ ولم يُفهم» — ومعالجتهما مختلفة.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Final


class Status(StrEnum):
    PARSING = "parsing"
    PARSED = "parsed"
    EXTRACTING = "extracting"
    AWAITING_REVIEW = "awaiting_review"
    VERIFIED = "verified"
    PARSE_FAILED = "parse_failed"
    EXTRACTION_FAILED = "extraction_failed"


# الانتقالات المسموحة. `verified` لا تُبلَغ إلا بقرار إنسان (§19).
STATE_FLOW: Final[dict[Status, tuple[Status, ...]]] = {
    Status.PARSING: (Status.PARSED, Status.PARSE_FAILED),
    Status.PARSED: (Status.EXTRACTING,),
    Status.EXTRACTING: (Status.AWAITING_REVIEW, Status.EXTRACTION_FAILED),
    Status.AWAITING_REVIEW: (Status.VERIFIED, Status.EXTRACTING),
    Status.VERIFIED: (Status.EXTRACTING,),
    Status.PARSE_FAILED: (Status.PARSING,),
    Status.EXTRACTION_FAILED: (Status.EXTRACTING,),
}

TERMINAL_FAILURES: Final = (Status.PARSE_FAILED, Status.EXTRACTION_FAILED)


def can_transition(current: Status, target: Status) -> bool:
    return target in STATE_FLOW.get(current, ())
