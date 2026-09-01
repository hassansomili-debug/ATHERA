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
    # معرّف ملف مرفق — يُذكر ولا يُقرأ محتواه في هذه المرحلة.
    attachment_file_id: uuid.UUID | None = None


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
    model_run_id: uuid.UUID | None = None
