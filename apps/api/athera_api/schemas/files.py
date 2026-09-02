"""عقود الملفات | File contracts."""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class FileInitRequest(BaseModel):
    filename: str = Field(max_length=512)
    content_type: str
    size_bytes: int = Field(gt=0)
    classification: str = Field(default="C2", pattern="^C[0-4]$")


class FileInitResponse(BaseModel):
    file_id: uuid.UUID
    upload_url: str
    storage_key: str
    expires_in: int


class FileCompleteRequest(BaseModel):
    checksum_sha256: str = Field(min_length=64, max_length=64)


class FileResponse(BaseModel):
    """ما يعرفه النظام عن الملف — لا أكثر.

    **لا حقل «مُحلَّل» ولا «مفهوم»:** التفكيك لم يقع بعد، ونمذجة حالته
    تحتاج عمودًا في القاعدة لا يوجد اليوم. الحالة الصادقة الوحيدة الآن
    `stored`.
    """

    id: uuid.UUID
    original_filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: str | None
    classification: str
    is_untrusted_content: bool
    status: str
    created_at: dt.datetime
    completed_at: dt.datetime | None


class FileDownloadResponse(BaseModel):
    download_url: str
    expires_in: int


class LibraryFile(BaseModel):
    """ملفٌ في مكتبة الباحث — بحالته الحقيقية لا بحالةٍ متفائلة.

    **و`processing` مشتقّةٌ لا مخزَّنة.** الرفعُ يُنشئ صفًّا حالته `stored`،
    والمعالجة تجري في مسار الرسائل (S5C) وتُسجَّل في `extraction_runs`. فتُقرأ
    الحالة من هناك — ولا يُخترع لها عمود، ولا يُقال «حُلِّل» لملفٍ لم يُقرأ.
    """

    id: uuid.UUID
    original_filename: str
    content_type: str
    size_bytes: int
    classification: str
    status: str
    created_at: dt.datetime
    # حال المعالجة: `not_processed` أو حالة تشغيلة الاستخراج الحقيقية.
    processing_status: str = "not_processed"
    # الرسالة المرتبطة إن وُجدت — فمنها تُفتح المراجعة.
    thesis_id: uuid.UUID | None = None
    candidates: int = 0
    reviewed: int = 0
