"""عقود الملفات | File contracts."""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class FileInitRequest(BaseModel):
    """نيّةُ رفعٍ عبر رابطٍ موقّع — **وفيها موضعُ الملف من أوّلها**.

    والمسار الموقّع كان ينزل بالملف في الجذر دائمًا: `POST /files/upload`
    يقبل `folder_id` ولا يقبله هذا. فمن رفع وهو واقفٌ في مجلَّدٍ بعميلٍ
    يستعمل الرابط الموقّع وجد ملفه في غير موضعه، ولا شيء يقول له لماذا —
    والفرق بين مسارَي رفعٍ ليس فرقًا يفهمه صاحب المكتبة.
    """

    filename: str = Field(max_length=512)
    content_type: str
    size_bytes: int = Field(gt=0)
    classification: str = Field(default="C2", pattern="^C[0-4]$")
    # `None` هو الجذر — قيمةٌ مقصودة لا حقلٌ منسيّ (كما في `FileMoveRequest`).
    folder_id: uuid.UUID | None = None


class FileInitResponse(BaseModel):
    """ما يحتاجه العميل ليرفع — **ومعه أين سينزل الملف**.

    وردُّ الموضع ليس زينة: العميل يقول «الرفع إلى: كتب المنهج» قبل أن يبدأ
    البثّ، ولو أضمره الخادمُ لصار على العميل أن يخمّن ما قرّره غيره.

    **ولا يذكر `storage_key` مجلَّدًا ولا يتغيّر بتغيّره.** المفتاح يُبنى
    من المستأجر والمستخدم ومعرّف الملف وحدها؛ فلو حُشر فيه مسارُ المجلَّد
    لصار نقلُ ملفٍ بين رفَّين نسخًا لكائنٍ في المخزن، ولانكسر معه كلُّ
    رابطٍ موقّع وكلُّ سجلّ إسنادٍ يشير إلى الموضع القديم.
    """

    file_id: uuid.UUID
    upload_url: str
    storage_key: str
    expires_in: int
    folder_id: uuid.UUID | None = None


class FileCompleteRequest(BaseModel):
    """ختمُ الرفع ببصمته — و`folder_id` هنا **قولٌ أخير لا تكرار**.

    الموضع يُثبَّت عند النيّة، فحذفُ الحقل من الجسم يُبقيه كما هو. وذكرُه —
    ولو بـ`null` — يعني أن الباحث غيّر وجهته بين النيّة والختم، فيُفحص
    المجلَّد الجديد كما فُحص الأول ثم يُكتب.

    والفرق بين «لم يُذكر» و«ذُكر فارغًا» يُقرأ من `model_fields_set`: لو
    عومل الغياب معاملة `null` لسحب كلُّ عميلٍ قديم — وهو لا يعرف الحقل
    أصلًا — ملفَّه إلى الجذر عند الختم، وهو بعينه العطب الذي يعالجه هذا
    التغيير.
    """

    checksum_sha256: str = Field(min_length=64, max_length=64)
    folder_id: uuid.UUID | None = None

    @property
    def folder_named(self) -> bool:
        """أذُكر الحقل صراحةً في الجسم؟ — لا «أقيمتُه ليست فارغة»."""
        return "folder_id" in self.model_fields_set


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
    # موضعُ الملف في المكتبة — `None` هو الجذر (الترحيل 0022).
    folder_id: uuid.UUID | None = None


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
    # **موضعٌ لا حال.** `folder_id` يقول أين وضع الباحث الملف في مكتبته،
    # ولا يقول شيئًا عن كونه دليلًا ولا عن ربطه ببحث. و`None` هو الجذر.
    folder_id: uuid.UUID | None = None
    trashed_at: dt.datetime | None = None
