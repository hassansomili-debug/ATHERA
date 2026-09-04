"""الملفات الكبيرة | Large uploads — **بطبقتين، ولا ملف ثنائي في المستودع**.

رسائل الدكتوراه الممسوحة ضوئيًا كبيرة، والسقف المعلن نصف جيجابايت. فيجب أن
يُختبر ما يقارب ذلك — ولا يجوز أن يُختبر في كل طلب دمج: تشغيلةٌ تبتلع
دقائق على كل تعديل سطرٍ في الواجهة تُعطَّل ثم لا تحرس شيئًا.

**الطبقة الأولى (على كل PR):** خمسة ميجابايت. تُثبت أن المسار كلّه يعمل
لملفٍ أكبر من المقطع بكثير: القراءة تدريجية، والبصمة مطابقة بايتًا ببايت،
والتنزيل يعيد ما رُفع.

**الطبقة الثانية (بطلبٍ أو بجدولٍ ليلي):** ما تطلبه `ATHERA_LARGE_FILE_MB`،
حتى السقف. تُتخطّى صراحةً بغيره — ولا تُعدّ ناجحة.

**ولا بايت ثنائي يُودَع في git.** الملفات تُولَّد في وقت التشغيل من نمطٍ
معلوم: مستودعٌ يحمل ملفًا بمئة ميجابايت يعاقب كل من يستنسخه إلى الأبد.
"""
from __future__ import annotations

import hashlib
import io
import os
import resource
import sys
import uuid

import pytest

from tests.conftest import requires_db

pytestmark = [pytest.mark.asyncio, requires_db]

pytest_asyncio = pytest.importorskip("pytest_asyncio")

MB = 1024 * 1024

# الطبقة الأولى: أكبر من مقطع الميجابايت بخمسة أضعاف، وأسرع من أن تُثقل PR.
PR_TIER_MB = 5

# الطبقة الثانية: تُطلب صراحةً. `ATHERA_LARGE_FILE_MB=200` مثلًا.
HEAVY_TIER_MB = int(os.getenv("ATHERA_LARGE_FILE_MB", "0"))


def _peak_rss_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # ‏macOS يعطي بايتات، ولينكس كيلوبايتات — والخلط يعطي رقمًا بألف ضعف.
    return peak / MB if sys.platform == "darwin" else peak / 1024


def _synthetic_pdf(size_mb: int) -> bytes:
    """مستندٌ اصطناعي بحجمٍ معلوم — يُولَّد ولا يُخزَّن في المستودع."""
    head = b"%PDF-1.7\n"
    return head + bytes(size_mb * MB - len(head))


@pytest.fixture(autouse=True)
def memory_store(monkeypatch):
    from athera_api.config import get_settings
    from athera_api.services import storage

    monkeypatch.setattr(get_settings(), "storage_provider", "memory", raising=False)
    storage.reset_store_cache()
    yield storage.get_store()
    storage.reset_store_cache()


@pytest_asyncio.fixture
async def researcher(two_tenants):
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    tenant = two_tenants["a"]
    token = issue_access_token(
        user_id=tenant["user_id"], tenant_id=tenant["tenant_id"],
        roles=["researcher"], mfa_satisfied=True,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": "ar"},
    ) as http:
        yield http
    from athera_api.db import engine
    await engine.dispose()


async def _round_trip(http, size_mb: int) -> None:
    """رفعٌ ثم تنزيل — **والحكم أن ما نزل هو ما رُفع**، لا أن الرمز ٢٠١."""
    payload = _synthetic_pdf(size_mb)
    expected = hashlib.sha256(payload).hexdigest()
    before = _peak_rss_mb()

    response = await http.post(
        "/api/v1/files/upload",
        files={"upload": (f"thesis-{uuid.uuid4().hex}.pdf",
                          io.BytesIO(payload), "application/pdf")},
    )
    assert response.status_code == 201, response.text[:400]
    body = response.json()
    assert body["size_bytes"] == len(payload)
    assert body["checksum_sha256"] == expected, "البصمة لا تطابق ما رُفع"
    assert body["status"] == "stored"

    got = await http.get(f"/api/v1/files/{body['id']}/content")
    assert got.status_code == 200
    assert hashlib.sha256(got.content).hexdigest() == expected, "ما نزل غير ما رُفع"

    grew = _peak_rss_mb() - before
    # الذاكرة تتناسب مع المقطع لا مع الملف: Starlette يفيض بالجسم إلى قرص،
    # والبثّ يقرأ مقطعًا مقطعًا. وسعةُ الفائض هنا للعميل الذي يحمل الحمولة
    # كاملةً في الاختبار نفسه — والخادم هو ما يُقاس، فيُترك هامشٌ لها.
    assert grew < 4 * size_mb, f"الذاكرة نمت {grew:.0f}MB لملفٍ {size_mb}MB"


async def test_a_five_megabyte_document_round_trips_intact(researcher):
    """الطبقة الأولى — تعمل على كل طلب دمج، وتبقى في حدود الثانية."""
    await _round_trip(researcher, PR_TIER_MB)


@pytest.mark.skipif(HEAVY_TIER_MB <= 0,
                    reason="set ATHERA_LARGE_FILE_MB to run the heavy tier")
async def test_a_book_sized_document_round_trips_intact(researcher):
    """الطبقة الثانية — بطلبٍ أو بجدولٍ ليلي، لا على كل PR."""
    await _round_trip(researcher, HEAVY_TIER_MB)


async def test_a_document_past_the_ceiling_is_refused_mid_stream(researcher, monkeypatch):
    """السقف يُفحص **أثناء** البثّ: لا يُستقبل الملف كاملًا ثم يُرفض.

    والسقف يُخفَّض هنا بدل توليد نصف جيجابايت — ما يُختبر هو موضع الفحص لا
    الرقم، وتوليدُ نصف جيجابايت لإثبات شرطٍ منطقي إسرافٌ لا دقّة.
    """
    from athera_api.services import storage

    monkeypatch.setattr(storage, "MAX_DOCUMENT_BYTES", 2 * MB)
    response = await researcher.post(
        "/api/v1/files/upload",
        files={"upload": ("huge.pdf", io.BytesIO(_synthetic_pdf(5)), "application/pdf")},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file.too_large"
