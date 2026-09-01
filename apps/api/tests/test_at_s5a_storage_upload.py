"""S5A — التخزين والرفع: يعمل فعلًا، وخاص فعلًا، ومعزول فعلًا.

الاختبارات تعمل على `MemoryObjectStore`: سلوك تخزين حقيقي بلا بيانات اعتماد
إنتاج، فلا يعتمد CI على سرّ ولا يلمس دلوًا حيًّا.

وأثقلها ثلاثة: أن ملفًا نزل مطابقًا للذي رُفع **بايتًا ببايت** لا برمز 200،
وأن مستأجرًا لا يبلغ ملف آخر بتخمين معرّفه، وأن فشل القاعدة بعد نجاح
التخزين لا يترك كائنًا يتيمًا.
"""
import io
import uuid

import pytest
import pytest_asyncio

from athera_api.errors import AtheraError
from athera_api.services import storage

pytestmark = pytest.mark.asyncio

PDF = b"%PDF-1.7\n" + b"x" * 400
DOCX = b"PK\x03\x04" + b"d" * 400
XLSX = b"PK\x03\x04" + b"s" * 400
CSV = b"a,b,c\n1,2,3\n"
SAV = b"$FL2@(#) SPSS DATA FILE" + b"\x00" * 200

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture(autouse=True)
def memory_store(monkeypatch):
    """تخزين معزول لكل اختبار — بلا حالة متسرّبة وبلا شبكة."""
    from athera_api.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "storage_provider", "memory", raising=False)
    storage.reset_store_cache()
    yield storage.get_store()
    storage.reset_store_cache()


# ══════════ التحقق: ما يُقبل وما يُرفض ══════════

@pytest.mark.parametrize(
    ("content_type", "filename"),
    [
        ("application/pdf", "paper.pdf"),
        (DOCX_TYPE, "thesis.docx"),
        ("text/csv", "data.csv"),
        (XLSX_TYPE, "sheet.xlsx"),
        ("application/x-spss-sav", "survey.sav"),
        ("text/plain", "refs.ris"),
        ("text/plain", "refs.bib"),
    ],
)
def test_supported_types_are_accepted(content_type, filename):
    storage.validate_upload(content_type, 1024, filename=filename)


def test_unsupported_extension_is_rejected():
    with pytest.raises(AtheraError) as err:
        storage.validate_upload("application/x-msdownload", 1024, filename="virus.exe")
    assert err.value.status_code == 415


def test_declared_type_must_match_extension():
    """نوع معلَن لا يطابق الامتداد يُرفض — أبسط تحايل يُمنع."""
    with pytest.raises(AtheraError) as err:
        storage.validate_upload("application/pdf", 1024, filename="payload.exe")
    assert err.value.status_code == 415


def test_content_magic_bytes_must_match_declared_type():
    """النوع من المتصفح ادعاء، وأول البايتات دليل."""
    storage.validate_content("application/pdf", PDF[:8])
    with pytest.raises(AtheraError) as err:
        storage.validate_content("application/pdf", b"MZ\x90\x00fake")
    assert err.value.status_code == 415


def test_empty_file_is_rejected():
    with pytest.raises(AtheraError) as err:
        storage.validate_upload("application/pdf", 0, filename="empty.pdf")
    assert err.value.status_code == 422


def test_oversized_file_is_rejected_per_category():
    with pytest.raises(AtheraError) as err:
        storage.validate_upload("text/csv", storage.MAX_DATASET_BYTES + 1, filename="huge.csv")
    assert err.value.status_code == 413
    # والمستند سقفه أعلى: القاعدة القائمة محفوظة لا مضيَّقة.
    storage.validate_upload("application/pdf", storage.MAX_DATASET_BYTES + 1, filename="big.pdf")


# ══════════ المفاتيح: لا تسلّق ولا تصادم ══════════

@pytest.mark.parametrize(
    "hostile",
    ["../../../etc/passwd", "..\\..\\windows\\system32", "a/b/c.pdf", "file\x00.pdf"],
)
def test_path_traversal_cannot_escape_the_key(hostile):
    safe = storage.safe_filename(hostile)
    assert "/" not in safe and "\\" not in safe and "\x00" not in safe
    assert ".." not in safe

    key = storage.build_storage_key(uuid.uuid4(), uuid.uuid4(), hostile, user_id=uuid.uuid4())
    assert key.count("/") == 6, key
    assert "/.." not in key


def test_key_is_server_generated_and_scoped_to_tenant_and_user():
    tenant, user, file_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    key = storage.build_storage_key(tenant, file_id, "paper.pdf", user_id=user)
    assert key.startswith(f"tenants/{tenant}/users/{user}/files/{file_id}/")


def test_two_uploads_of_the_same_name_never_collide():
    tenant, user = uuid.uuid4(), uuid.uuid4()
    a = storage.build_storage_key(tenant, uuid.uuid4(), "report.pdf", user_id=user)
    b = storage.build_storage_key(tenant, uuid.uuid4(), "report.pdf", user_id=user)
    assert a != b


# ══════════ الروابط: لا رابط دائم ولا عام ══════════

def test_signed_urls_always_carry_an_expiry():
    store = storage.get_store()
    assert "expires_in" in store.presign_get("k", expires_in=300)
    assert "expires_in" in store.presign_put("k", "application/pdf", expires_in=300)


def test_unconfigured_storage_fails_loudly_and_never_silently_accepts():
    store = storage.UnconfiguredStore()
    for call in (
        lambda: store.put("k", b"x", "application/pdf"),
        lambda: store.get("k"),
        lambda: store.presign_get("k", expires_in=60),
    ):
        with pytest.raises(AtheraError) as err:
            call()
        assert err.value.status_code == 503


# ══════════ من طرف إلى طرف عبر HTTP ══════════

@pytest_asyncio.fixture
async def clients(two_tenants):
    """عميلان مصادقان لمستأجرين مختلفين — لاختبار المنع العابر."""
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    transport = httpx.ASGITransport(app=app)
    made = {}
    for slot in ("a", "b"):
        tenant = two_tenants[slot]
        token = issue_access_token(
            user_id=tenant["user_id"], tenant_id=tenant["tenant_id"],
            roles=["researcher"], mfa_satisfied=True,
        )
        made[slot] = httpx.AsyncClient(
            transport=transport, base_url="http://test",
            headers={"Authorization": f"Bearer {token}", "Accept-Language": "ar"},
        )
    yield made
    for http in made.values():
        await http.aclose()
    from athera_api.db import engine
    await engine.dispose()


async def _upload(http, data: bytes, name: str, ctype: str):
    return await http.post(
        "/api/v1/files/upload",
        files={"upload": (name, io.BytesIO(data), ctype)},
    )


async def test_upload_then_retrieve_returns_identical_bytes(clients):
    """الاختبار الحقيقي ليس رمز 200 — بل أن ما نزل هو ما رُفع."""
    http = clients["a"]
    response = await _upload(http, PDF, "paper.pdf", "application/pdf")
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["status"] == "stored"
    assert body["size_bytes"] == len(PDF)
    assert body["checksum_sha256"] == storage.sha256_of(PDF)
    assert body["is_untrusted_content"] is True
    assert "storage_key" not in body  # لا كشف لموضع الكائن

    got = await http.get(f"/api/v1/files/{body['id']}/content")
    assert got.status_code == 200
    assert got.content == PDF
    assert storage.sha256_of(got.content) == body["checksum_sha256"]


async def test_cross_tenant_retrieval_is_denied(clients):
    """تخمين معرّف ملف لا يعطي شيئًا — RLS قبل RBAC قبل الواجهة."""
    uploaded = await _upload(clients["a"], PDF, "private.pdf", "application/pdf")
    file_id = uploaded.json()["id"]

    for path in (f"/api/v1/files/{file_id}", f"/api/v1/files/{file_id}/content",
                 f"/api/v1/files/{file_id}/download"):
        blocked = await clients["b"].get(path)
        assert blocked.status_code in (403, 404), f"{path} → {blocked.status_code}"


async def test_unauthenticated_upload_is_denied(clients):
    import httpx

    from athera_api.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as anon:
        response = await _upload(anon, PDF, "paper.pdf", "application/pdf")
    assert response.status_code == 401


async def test_rejected_upload_leaves_no_object_and_no_row(clients, memory_store):
    before = len(memory_store._objects)
    response = await _upload(clients["a"], b"MZ\x90\x00", "trojan.exe", "application/x-msdownload")
    assert response.status_code == 415
    assert len(memory_store._objects) == before


async def test_empty_upload_is_rejected_over_http(clients):
    response = await _upload(clients["a"], b"", "empty.pdf", "application/pdf")
    assert response.status_code == 422


@pytest_asyncio.fixture
async def tolerant_client(two_tenants):
    """عميل يحوّل استثناء الخادم إلى رمز 500 بدل إعادة رفعه.

    الناقل الافتراضي في httpx يعيد رفع استثناء التطبيق، فيصعب تأكيد أن
    الخادم **لم يُبلّغ نجاحًا**. وهذا العميل يجعل الشرط قابلًا للتأكيد كما
    يراه عميل حقيقي.
    """
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    tenant = two_tenants["a"]
    token = issue_access_token(
        user_id=tenant["user_id"], tenant_id=tenant["tenant_id"],
        roles=["researcher"], mfa_satisfied=True,
    )
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": "ar"},
    ) as http:
        yield http


async def test_storage_failure_is_never_reported_as_success(tolerant_client, monkeypatch):
    """التخزين يسقط ← لا 201، ولا سجل يدّعي ملفًا لا وجود له."""
    store = storage.get_store()

    def explode(*args, **kwargs):
        raise RuntimeError("storage down")

    # المسار يبثّ، فالحقن على العملية التي يستعملها فعلًا.
    monkeypatch.setattr(store, "put_stream", explode)
    response = await _upload(tolerant_client, PDF, "paper.pdf", "application/pdf")
    assert response.status_code >= 500

    listing = await tolerant_client.get("/api/v1/files/00000000-0000-0000-0000-000000000000")
    assert listing.status_code == 404


async def test_db_failure_after_storage_removes_the_orphan_object(tolerant_client, memory_store, monkeypatch):
    """القاعدة تسقط بعد نجاح التخزين ← يُحذف الكائن، فلا يبقى بلا سجل."""
    from athera_api.services import audit as audit_service

    async def explode(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(audit_service, "record", explode)
    before = len(memory_store._objects)
    response = await _upload(tolerant_client, PDF, "paper.pdf", "application/pdf")
    assert response.status_code >= 500
    assert len(memory_store._objects) == before, "كائن يتيم بقي بعد فشل القاعدة"


async def test_download_url_expires_and_is_not_public(clients):
    uploaded = await _upload(clients["a"], CSV, "data.csv", "text/csv")
    presigned = await clients["a"].get(f"/api/v1/files/{uploaded.json()['id']}/download")
    assert presigned.status_code == 200
    body = presigned.json()
    assert body["expires_in"] > 0
    assert "expires_in" in body["download_url"]


@pytest.mark.parametrize(
    ("data", "name", "ctype"),
    [
        (DOCX, "thesis.docx", DOCX_TYPE),
        (CSV, "data.csv", "text/csv"),
        (XLSX, "sheet.xlsx", XLSX_TYPE),
        (SAV, "survey.sav", "application/x-spss-sav"),
    ],
)
async def test_each_supported_type_round_trips(clients, data, name, ctype):
    http = clients["a"]
    uploaded = await _upload(http, data, name, ctype)
    assert uploaded.status_code == 201, uploaded.text
    got = await http.get(f"/api/v1/files/{uploaded.json()['id']}/content")
    assert got.content == data


# ══════════ البثّ: الذاكرة لا تتناسب مع حجم الملف ══════════

async def test_upload_streams_in_chunks_and_never_reads_the_whole_file(clients, monkeypatch):
    """أكبر من مقطع واحد بكثير ← قراءات متعددة محدودة، لا قراءة واحدة كاملة.

    هذا هو الفرق بين ملف بنصف جيجابايت يمرّ، وآلة بنصف جيجابايت ذاكرة تسقط.
    """
    from starlette.datastructures import UploadFile as StarletteUploadFile

    from athera_api.routers import files as files_router

    payload = b"%PDF-1.7\n" + b"z" * (5 * 1024 * 1024)  # خمسة أضعاف المقطع
    sizes: list[int | None] = []
    original = StarletteUploadFile.read

    async def spy(self, size: int = -1):
        sizes.append(size)
        return await original(self, size)

    monkeypatch.setattr(StarletteUploadFile, "read", spy)
    response = await _upload(clients["a"], payload, "big.pdf", "application/pdf")
    assert response.status_code == 201, response.text

    assert sizes, "لم تُقرأ أي مقاطع"
    # لا قراءة بلا حدّ: كل استدعاء محدود بمقطع.
    assert all(s == files_router.CHUNK_BYTES for s in sizes), sizes
    # وعدد المقاطع يوازي الحجم — دليل أن القراءة تدريجية لا دفعة واحدة.
    assert len(sizes) >= 5

    body = response.json()
    assert body["size_bytes"] == len(payload)
    assert body["checksum_sha256"] == storage.sha256_of(payload)

    got = await clients["a"].get(f"/api/v1/files/{body['id']}/content")
    assert got.content == payload


async def test_oversize_is_rejected_mid_stream_not_after_full_receipt(clients, monkeypatch):
    """السقف يُفحص أثناء البثّ: يُوقَف عند تجاوزه لا بعد استقباله كاملًا."""
    monkeypatch.setattr(storage, "MAX_DATASET_BYTES", 64 * 1024)
    response = await _upload(clients["a"], b"a,b\n" + b"1,2\n" * 40_000, "big.csv", "text/csv")
    assert response.status_code == 413


# ══════════ صدق الإفصاح: اسم المزوّد ليس دليل تهيئة ══════════

@pytest.mark.parametrize(
    ("env", "provider", "endpoint", "key", "expected"),
    [
        # إنتاج بالقيم الافتراضية للتطوير = غير مُهيّأ، مهما قال اسم المزوّد.
        ("production", "s3", "http://localhost:9000", "minioadmin", False),
        ("production", "s3", "", "", False),
        ("production", "s3", "https://x.r2.cloudflarestorage.com", "AKIAREAL", True),
        ("production", "none", "https://x.r2.cloudflarestorage.com", "AKIAREAL", False),
        ("development", "s3", "http://localhost:9000", "minioadmin", True),
    ],
)
def test_posture_reports_real_configuration_not_the_provider_name(
    monkeypatch, env, provider, endpoint, key, expected
):
    """نشرٌ بلا أسرار كان يبدو «مُهيّأً» لأن الإعداد الافتراضي في الكود `s3`.

    وإعلان قدرة غير قائمة أسوأ من إعلان غيابها: المستخدم يرفع فيفشل بلا سبب
    مفهوم، بدل أن يُقال له إن التخزين لم يُضبط.
    """
    from athera_api.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", env, raising=False)
    monkeypatch.setattr(settings, "storage_provider", provider, raising=False)
    monkeypatch.setattr(settings, "s3_endpoint_url", endpoint, raising=False)
    monkeypatch.setattr(settings, "s3_access_key_id", key, raising=False)
    monkeypatch.setattr(settings, "s3_bucket", "athera", raising=False)
    monkeypatch.setattr(settings, "s3_secret_access_key", "secret", raising=False)

    assert storage.is_configured() is expected
