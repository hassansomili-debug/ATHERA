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
