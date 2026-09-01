"""التخزين | S3-compatible object storage (§29، §33.3، §36).

**التجريد قبل المزوّد.** المنطق البحثي لا يعرف boto3 ولا اسم مزوّد: يتعامل
مع `ObjectStore` وحده، فينتقل التخزين من MinIO إلى R2 إلى Supabase بتغيير
إعداد لا بتغيير كود. ولذلك يوجد `MemoryObjectStore` أيضًا — الاختبارات
تحتاج تخزينًا حقيقي السلوك لا وهميًا، ولا تحتاج بيانات اعتماد إنتاج.

وبادئة المفتاح `tenants/{tenant_id}/` جزء من العزل (ADR-0002)، والروابط
موقّعة وقصيرة الأجل، وكل تنزيل يُسجَّل في `file_access_logs` (§36.2).
"""
from __future__ import annotations

import abc
import hashlib
import re
import uuid
from functools import lru_cache
from typing import BinaryIO, Final

from ..config import get_settings
from ..errors import AtheraError

# ── حدود الحجم ─────────────────────────────────────────────────────────
#
# فئتان لا رقم واحد: مستند بحثي ومجموعة بيانات. والسقف الأعلى بقي كما كان
# (512 ميجابايت) وسببه المكتوب باقٍ: رسائل الدكتوراه الممسوحة ضوئيًا كبيرة،
# وتضييقه يكسر حالة استعمال معلنة.
MAX_DOCUMENT_BYTES: Final = 512 * 1024 * 1024
MAX_DATASET_BYTES: Final = 256 * 1024 * 1024
MAX_UPLOAD_BYTES: Final = MAX_DOCUMENT_BYTES  # السقف المطلق

# ── الأنواع المقبولة ───────────────────────────────────────────────────
#
# `kind` يحدد أي سقف يُطبَّق. وRIS وBibTeX **تُخزَّن ولا تُفكَّك**: قبول
# الحفظ ليس ادعاء فهم، والتفكيك مرحلة لاحقة معلنة.
DOCUMENT_TYPES: Final[dict[str, tuple[str, ...]]] = {
    "application/pdf": (".pdf",),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (".docx",),
    "application/msword": (".doc",),
    "text/plain": (".txt", ".ris", ".bib"),
    "application/x-research-info-systems": (".ris",),
    "application/x-bibtex": (".bib",),
}
DATASET_TYPES: Final[dict[str, tuple[str, ...]]] = {
    "text/csv": (".csv",),
    "application/vnd.ms-excel": (".xls",),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (".xlsx",),
    "application/x-spss-sav": (".sav", ".zsav"),
    # ‏.sav وملفات ثنائية أخرى تصل أحيانًا بهذا النوع من المتصفح.
    "application/octet-stream": (".sav", ".zsav", ".xls", ".xlsx"),
}
ALLOWED_CONTENT_TYPES: Final = frozenset(DOCUMENT_TYPES) | frozenset(DATASET_TYPES)

# بصمات أول البايتات — النوع المعلَن من المتصفح ادعاء، لا دليل.
_MAGIC: Final[dict[str, bytes]] = {
    "application/pdf": b"%PDF-",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": b"PK\x03\x04",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": b"PK\x03\x04",
}

_SAFE_NAME = re.compile(r"[^A-Za-z0-9؀-ۿ._-]+")


class StorageNotConfigured(AtheraError):
    def __init__(self) -> None:
        super().__init__("storage.not_configured", status_code=503)


# ══════════════════════════════════════════════════════════════════════
# التجريد
# ══════════════════════════════════════════════════════════════════════
class ObjectStore(abc.ABC):
    """أربع عمليات. لا نوع خاص بمزود يعبر هذا الحد."""

    name: str = "abstract"

    @abc.abstractmethod
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    @abc.abstractmethod
    def put_stream(self, key: str, fileobj: BinaryIO, content_type: str) -> None:
        """رفع من كائن ملفّي بلا تحميل المحتوى في الذاكرة."""

    @abc.abstractmethod
    def get(self, key: str) -> bytes: ...

    @abc.abstractmethod
    def delete(self, key: str) -> None: ...

    @abc.abstractmethod
    def presign_get(self, key: str, *, expires_in: int) -> str: ...

    @abc.abstractmethod
    def presign_put(self, key: str, content_type: str, *, expires_in: int) -> str: ...


class S3ObjectStore(ObjectStore):
    """أي تخزين متوافق مع S3: AWS · R2 · Supabase · MinIO — بالإعداد وحده."""

    name = "s3"

    def __init__(self) -> None:
        import boto3  # noqa: PLC0415 — يبقى المزوّد خارج مسار الاستيراد العام
        from botocore.config import Config  # noqa: PLC0415

        settings = get_settings()
        self._bucket = settings.s3_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            config=Config(signature_version="s3v4"),
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        # لا ACL عامة إطلاقًا: الدلو خاص، والوصول بروابط موقّعة أو ببثّ مصادق.
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def put_stream(self, key: str, fileobj: BinaryIO, content_type: str) -> None:
        """`upload_fileobj` تحميل مُدار: يقسّم تلقائيًا إلى أجزاء ويبثّ.

        الذاكرة تتناسب مع حجم الجزء لا حجم الملف — وهذا الفرق بين ملف بحجم
        نصف جيجابايت يمرّ، وآلة بنصف جيجابايت ذاكرة تسقط.
        """
        self._client.upload_fileobj(
            fileobj, self._bucket, key, ExtraArgs={"ContentType": content_type}
        )

    def get(self, key: str) -> bytes:
        return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def presign_get(self, key: str, *, expires_in: int) -> str:
        return self._client.generate_presigned_url(
            "get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=expires_in
        )

    def presign_put(self, key: str, content_type: str, *, expires_in: int) -> str:
        return self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )


class MemoryObjectStore(ObjectStore):
    """تخزين في الذاكرة للاختبار — سلوك حقيقي بلا بيانات اعتماد."""

    name = "memory"

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str]] = {}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._objects[key] = (data, content_type)

    def put_stream(self, key: str, fileobj: BinaryIO, content_type: str) -> None:
        self._objects[key] = (fileobj.read(), content_type)

    def get(self, key: str) -> bytes:
        if key not in self._objects:
            raise AtheraError("file.not_found", status_code=404)
        return self._objects[key][0]

    def delete(self, key: str) -> None:
        self._objects.pop(key, None)

    def presign_get(self, key: str, *, expires_in: int) -> str:
        return f"memory://{key}?expires_in={expires_in}"

    def presign_put(self, key: str, content_type: str, *, expires_in: int) -> str:
        return f"memory://{key}?expires_in={expires_in}&content_type={content_type}"


class UnconfiguredStore(ObjectStore):
    """لا تخزين مضبوط: يفشل بوضوح ولا يقبل بصمت.

    السقوط الصامت أخطر من الفشل — رفعٌ يبدو ناجحًا وملفٌ لا وجود له أسوأ من
    رسالة تقول إن التخزين غير مُهيّأ.
    """

    name = "none"

    def put(self, key: str, data: bytes, content_type: str) -> None: raise StorageNotConfigured()
    def put_stream(self, key: str, fileobj: BinaryIO, content_type: str) -> None: raise StorageNotConfigured()
    def get(self, key: str) -> bytes: raise StorageNotConfigured()
    def delete(self, key: str) -> None: raise StorageNotConfigured()
    def presign_get(self, key: str, *, expires_in: int) -> str: raise StorageNotConfigured()
    def presign_put(self, key: str, content_type: str, *, expires_in: int) -> str: raise StorageNotConfigured()


@lru_cache
def get_store() -> ObjectStore:
    provider = get_settings().storage_provider
    if provider == "s3":
        return S3ObjectStore()
    if provider == "memory":
        return MemoryObjectStore()
    if provider == "none":
        return UnconfiguredStore()
    raise AtheraError("storage.unknown_provider", status_code=500, provider=provider)


def reset_store_cache() -> None:
    """للاختبار: يُبطل الذاكرة المؤقتة بعد تبديل الإعداد."""
    get_store.cache_clear()


# ══════════════════════════════════════════════════════════════════════
# المفاتيح والتحقق
# ══════════════════════════════════════════════════════════════════════
def safe_filename(filename: str) -> str:
    """اسم صالح للتخزين والعرض — لا مسار ولا تسلّق.

    يؤخذ الاسم الأساسي وحده، وتُستبدل كل محرف خارج المسموح. والاسم الأصلي
    يُحفظ في `original_filename` كما جاء، فلا يضيع على المستخدم.
    """
    base = filename.replace("\\", "/").split("/")[-1]
    base = base.replace("\x00", "")
    cleaned = _SAFE_NAME.sub("_", base).strip("._") or "file"
    return cleaned[-200:]


def build_storage_key(
    tenant_id: uuid.UUID,
    file_id: uuid.UUID,
    filename: str,
    *,
    user_id: uuid.UUID | None = None,
) -> str:
    """مفتاح مبنيّ على الخادم: المستأجر ثم المستخدم ثم معرّف الملف.

    اسم المستخدم لا يُستعمل معرّفًا وحده — المعرّف من الخادم، والاسم زينة
    تسبقها أربعة مقاطع تمنع التصادم والتخمين.
    """
    safe = safe_filename(filename)
    if user_id is not None:
        return f"tenants/{tenant_id}/users/{user_id}/files/{file_id}/{safe}"
    return f"tenants/{tenant_id}/files/{file_id}/{safe}"


def kind_for(content_type: str) -> str:
    return "dataset" if content_type in DATASET_TYPES else "document"


def max_bytes_for(content_type: str) -> int:
    return MAX_DATASET_BYTES if kind_for(content_type) == "dataset" else MAX_DOCUMENT_BYTES


def validate_type(content_type: str, filename: str | None = None) -> None:
    """النوع والامتداد — يُفحصان **قبل** قراءة بايت واحد.

    الرفض المبكر يمنع بثّ نصف جيجابايت من ملف مرفوض أصلًا.
    """
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise AtheraError("file.type_rejected", status_code=415, content_type=content_type)
    if filename is not None:
        allowed = DOCUMENT_TYPES.get(content_type) or DATASET_TYPES.get(content_type) or ()
        lowered = safe_filename(filename).lower()
        if not any(lowered.endswith(ext) for ext in allowed):
            raise AtheraError("file.extension_mismatch", status_code=415,
                              content_type=content_type)


def validate_size(content_type: str, size_bytes: int) -> None:
    if size_bytes <= 0:
        raise AtheraError("file.empty", status_code=422)
    limit = max_bytes_for(content_type)
    if size_bytes > limit:
        raise AtheraError("file.too_large", status_code=413,
                          size_bytes=size_bytes, max_bytes=limit)


def validate_upload(content_type: str, size_bytes: int, *, filename: str | None = None) -> None:
    """تحقق من النوع والامتداد والحجم — والامتداد يُقابَل بالنوع المعلَن.

    النوع الذي يرسله المتصفح ادعاء. مقابلته بالامتداد يمنع أبسط تحايل:
    ملف تنفيذي يُعلن نفسه PDF.
    """
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise AtheraError("file.type_rejected", status_code=415, content_type=content_type)

    if size_bytes <= 0:
        raise AtheraError("file.empty", status_code=422)

    limit = max_bytes_for(content_type)
    if size_bytes > limit:
        raise AtheraError("file.too_large", status_code=413,
                          size_bytes=size_bytes, max_bytes=limit)

    if filename is not None:
        allowed = DOCUMENT_TYPES.get(content_type) or DATASET_TYPES.get(content_type) or ()
        lowered = safe_filename(filename).lower()
        if not any(lowered.endswith(ext) for ext in allowed):
            raise AtheraError("file.extension_mismatch", status_code=415,
                              content_type=content_type)


def validate_content(content_type: str, head: bytes) -> None:
    """بصمة أول البايتات حيث تكون معروفة — دليل لا ادعاء."""
    magic = _MAGIC.get(content_type)
    if magic and not head.startswith(magic):
        raise AtheraError("file.content_mismatch", status_code=415, content_type=content_type)


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ══════════════════════════════════════════════════════════════════════
# توافقية: الواجهة القديمة تبقى عاملة
# ══════════════════════════════════════════════════════════════════════
def presign_put(storage_key: str, content_type: str) -> str:
    return get_store().presign_put(
        storage_key, content_type, expires_in=get_settings().s3_presign_ttl_seconds
    )


def presign_get(storage_key: str) -> str:
    return get_store().presign_get(storage_key, expires_in=get_settings().s3_presign_ttl_seconds)
