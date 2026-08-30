"""التخزين | S3-compatible object storage (§29، §36).

بادئة المسار `tenants/{tenant_id}/` جزء من العزل (ADR-0002)، والروابط موقّعة
وقصيرة الأجل، وكل تنزيل يُسجَّل في `file_access_logs` (§36.2).
"""
import uuid
from functools import lru_cache
from typing import Final

import boto3
from botocore.config import Config

from ..config import get_settings
from ..errors import AtheraError

_settings = get_settings()

MAX_UPLOAD_BYTES: Final = 512 * 1024 * 1024  # 512MB — رسائل الدكتوراه الممسوحة ضوئيًا كبيرة.

ALLOWED_CONTENT_TYPES: Final = frozenset({
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "application/msword",
    "text/plain",
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
    "application/x-spss-sav",
    "application/octet-stream",  # .sav/.zsav تصل أحيانًا بهذا النوع
})


@lru_cache
def _client():
    return boto3.client(
        "s3",
        endpoint_url=_settings.s3_endpoint_url,
        region_name=_settings.s3_region,
        aws_access_key_id=_settings.s3_access_key_id,
        aws_secret_access_key=_settings.s3_secret_access_key,
        config=Config(signature_version="s3v4"),
    )


def build_storage_key(tenant_id: uuid.UUID, file_id: uuid.UUID, filename: str) -> str:
    safe = filename.replace("/", "_").replace("\\", "_")[-200:]
    return f"tenants/{tenant_id}/files/{file_id}/{safe}"


def validate_upload(content_type: str, size_bytes: int) -> None:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise AtheraError("file.type_rejected", status_code=415, content_type=content_type)
    if size_bytes > MAX_UPLOAD_BYTES:
        raise AtheraError("file.too_large", status_code=413, size_bytes=size_bytes)


def presign_put(storage_key: str, content_type: str) -> str:
    return _client().generate_presigned_url(
        "put_object",
        Params={"Bucket": _settings.s3_bucket, "Key": storage_key, "ContentType": content_type},
        ExpiresIn=_settings.s3_presign_ttl_seconds,
    )


def presign_get(storage_key: str) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": _settings.s3_bucket, "Key": storage_key},
        ExpiresIn=_settings.s3_presign_ttl_seconds,
    )


def head_object(storage_key: str) -> dict:
    return _client().head_object(Bucket=_settings.s3_bucket, Key=storage_key)
