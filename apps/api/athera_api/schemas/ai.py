"""عقد أثيرا AI | The ATHERA AI response contract.

الرد **مهيكل عمدًا** لا نصًّا حرًّا: الواجهة تحتاج أن تفصل الاقتراح عن
الدليل عن الحدّ عن الخطوة التالية، والنص الحرّ يخلطها فيقرأ المستخدم
اقتراحًا على أنه نتيجة.
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class AiAskRequest(BaseModel):
    question: str = Field(min_length=8, max_length=4000)
    # معرّف ملفٍ **يختاره الباحث بعينه**. ولا بحث تلقائي في ملفاته كلها:
    # المحادثة تقرأ ما أشار إليه، لا ما تستطيع الوصول إليه.
    attachment_file_id: uuid.UUID | None = None
    # الواجهة ترسله باسمه المختصر كذلك.
    file_id: uuid.UUID | None = None

    @property
    def selected_file(self) -> uuid.UUID | None:
        return self.attachment_file_id or self.file_id


class AttachmentState(BaseModel):
    """حال المستند المرفق — **بحقولٍ تقرؤها الواجهة، لا بنصٍّ تفسّره**.

    كانت الحدود تُقال بالعربية في `limitations` وحدها، فلم تستطع الواجهة أن
    تعرف **ماذا تعرض من زر**: أتطلب المعالجة؟ أم المراجعة؟ أم الإذن؟
    فتُترك الرسالة نصًّا يقرؤه الباحث ويُنفّذه بنفسه — أي بنداء API.

    و`needs` يقول الفعل التالي بكلمة واحدة، فتبنيه الواجهة زرًّا.
    """

    file_id: uuid.UUID
    filename: str
    # `not_processed` أو حالة تشغيلة الاستخراج الحقيقية.
    processing_status: str
    # `absent` | `granted` | `declined` — لقدرة السؤال عن المستند وحدها.
    consent_state: str
    approved_facts: int = 0
    pending_review: int = 0
    # الفعل التالي: `process` | `review` | `chat_consent` | `none`
    needs: str = "none"


class AiAskResponse(BaseModel):
    """ما تعيده أثيرا AI — بأربعة حقول تفصل ما لا يجوز خلطه."""

    answer: str
    status: str = Field(description="ok | provider_error | disabled")
    # `model_suggestion` = اقتراح نموذج لا دليل · `verified` = من طبقة الأدلة
    evidence_state: str = Field(description="model_suggestion | verified | none")
    capabilities_used: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    recommended_next_actions: list[str] = Field(default_factory=list)
    # للتتبّع الداخلي — لا يُعرض للباحث في المسار العادي.
    attachment: AttachmentState | None = None
    model_run_id: uuid.UUID | None = None
