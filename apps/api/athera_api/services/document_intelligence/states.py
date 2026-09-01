"""حالات المعالجة | The processing state machine (§3، §7).

**الحالة تسكن `extraction_runs` لا `files`.** الأول يصف تشغيلة والثاني يصف
تخزينًا: ملفٌ محفوظ يبقى محفوظًا وإن فشل استخراجه، ورفعه لا يُلغى بفشل
قراءة. وخلطهما يجعل فشل النموذج يبدو فقدانًا للملف.

وكل فشل يُسمّى بسببه: `parse_failed` غير `extract_failed`. الأولى تعني
«لم يُقرأ الملف» والثانية «قُرئ ولم يُستخرَج منه» — ومعالجتهما مختلفة.

**والأسماء تسع في `extraction_runs.status` وهو `VARCHAR(16)`.** لم يكن
`extraction_failed` يسع (سبعة عشر حرفًا)، فكانت حالة الفشل الوحيدة التي
تصف انهيار الاستخراج **غير قابلة للكتابة أصلًا**: تُرفض عند الحفظ فيُبتلع
الفشل مرة أخرى. ولم يظهر ذلك في الاختبارات لأن الاستخراج الحتمي يُنتج
مرشّحًا دائمًا فلا يُبلَغ الفرع. `test_every_status_fits_its_column` يمنع
تكرار هذا الصنف من العيوب.
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
    EXTRACTION_FAILED = "extract_failed"


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
