"""صدق شاشة الرفع | The upload screen must not say what did not happen.

ثلاثة أشياء كانت الشاشة تقولها وليست صحيحة:

**«تم الحفظ» قبل أن يُحفظ.** جلسة القاعدة كانت تبعيةً مولِّدة، وFastAPI
يُنهي تلك التبعيات **بعد** إرسال جسم الاستجابة. فالإيداع يقع بعد أن يقرأ
المتصفح ٢٠١؛ والواجهة تقرأ المكتبة فور وصوله على اتصالٍ آخر، فقد تسبق
الإيداع فلا ترى الصفّ — «تم الحفظ» ومكتبةٌ خالية.

**«لم ترفع ملفًا بعد» لقائمةٍ لم تصل.** قائمةٌ فارغة قبل أول ردّ كانت
تُعرض مكتبةً خالية. وهما حالان مختلفتان، وخلطهما كذبٌ يراه المستخدم كذبًا.

**«جارٍ الرفع…» بلا رقم.** كتابٌ بمئة ميجابايت يستغرق دقائق، وزرٌّ لا
يتحرّك يقول للباحث إن الشاشة ماتت.
"""
from __future__ import annotations

import io
import pathlib
import uuid

import pytest

from tests.conftest import requires_db
from tests.tsscan import code_lines

WEB = pathlib.Path(__file__).resolve().parents[3] / "apps" / "web"

PDF = b"%PDF-1.7\n" + b"x" * 400


def _code(*parts: str) -> str:
    """شيفرةٌ بلا تعليقات — فالحارس لا يُصدَّق بشرحٍ مكتوب بجانبه."""
    text = (WEB.joinpath(*parts)).read_text(encoding="utf-8")
    return "\n".join(line for _, line in code_lines(text))


# ══════════ الخادم: الإيداع قبل الردّ ══════════

@pytest.mark.asyncio
@requires_db
async def test_the_row_is_committed_before_the_client_is_told_it_was_stored(two_tenants):
    """**«تم» لا تُقال قبل أن يقع.**

    والفحص يقع في اللحظة نفسها: عند إرسال جسم الاستجابة يُسأل اتصالٌ آخر
    «أترى الصفّ؟». فإن كان الإيداع بعد الردّ لم يره — وهو ما كان.
    """
    import httpx
    from sqlalchemy import select

    from athera_api.config import get_settings
    from athera_api.db import tenant_session
    from athera_api.main import app
    from athera_api.models.files import File
    from athera_api.security import issue_access_token
    from athera_api.services import storage

    settings = get_settings()
    previous_provider = settings.storage_provider
    settings.storage_provider = "memory"
    storage.reset_store_cache()

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    visible_when_sent: list[int] = []

    class CommitWatch:
        """يلتقط لحظة خروج جسم الاستجابة، ويسأل القاعدة عندها لا بعدها."""

        def __init__(self, inner):
            self.inner = inner

        async def __call__(self, scope, receive, send):
            async def spy(message):
                if message["type"] == "http.response.body" and not message.get("more_body"):
                    async with tenant_session(tid, uid) as probe:
                        rows = (await probe.execute(
                            select(File.id).where(File.tenant_id == tid))).scalars().all()
                    visible_when_sent.append(len(rows))
                await send(message)

            await self.inner(scope, receive, spy)

    token = issue_access_token(user_id=uid, tenant_id=tid,
                               roles=["researcher"], mfa_satisfied=True)
    transport = httpx.ASGITransport(app=CommitWatch(app))
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test",
            headers={"Authorization": f"Bearer {token}", "Accept-Language": "ar"},
        ) as http:
            response = await http.post(
                "/api/v1/files/upload",
                files={"upload": (f"{uuid.uuid4().hex}.pdf", io.BytesIO(PDF), "application/pdf")},
            )
    finally:
        settings.storage_provider = previous_provider
        storage.reset_store_cache()
        from athera_api.db import engine
        await engine.dispose()

    assert response.status_code == 201, response.text
    assert visible_when_sent, "لم تُلتقط لحظة إرسال الاستجابة"
    assert visible_when_sent[-1] >= 1, (
        "الردّ قال «تم الحفظ» وصفّ الملف غير مُودَع بعد — "
        "قراءةٌ تالية على اتصالٍ آخر لن تراه")


# ══════════ الواجهة: ما تقوله الشاشة وما لا تقوله ══════════

def test_a_list_that_has_not_arrived_is_not_an_empty_library():
    """«جارٍ القراءة» غير «لا ملفات» غير «تعذّرت القراءة» — ثلاثٌ لا واحدة.

    وترتيبها في التصيير شرط: لو فُحص الفراغ أولًا لظهرت «لم ترفع ملفًا
    بعد» في كل لحظةٍ قبل وصول الردّ.
    """
    code = _code("src", "app", "[locale]", "library", "page.tsx")
    assert 'useState<"loading" | "ready" | "failed">("loading")' in code, (
        "الشاشة لا تفرّق بين قائمةٍ لم تصل وقائمةٍ فارغة")
    assert 'library.loadingFiles' in code and 'library.filesFailed' in code

    loading_at = code.index('filesLoad === "loading"')
    empty_at = code.index("files.length === 0")
    assert loading_at < empty_at, "الفراغ يُفحص قبل الانتظار، فيُقال «لا ملفات» لقائمةٍ لم تصل"


def test_the_freshly_uploaded_file_is_shown_without_waiting_for_the_list():
    """رفعٌ نجح ومكتبةٌ خالية منه ليس عرضًا صادقًا — وقد سقط القبول عليه.

    ورقم الترتيب يُرفع مع الإدراج: بغيره يمحو ردٌّ صدر قبل الرفع الملفَ
    الذي أُدرج للتوّ.
    """
    page = _code("src", "app", "[locale]", "library", "page.tsx")
    assert "setFiles((previous) => [stored, ...previous" in page, (
        "الملف المرفوع لا يُعرض إلا بعد دورة كاملة إلى الخادم")
    insert_at = page.index("setFiles((previous) => [stored")
    bump_at = page.rindex("latest.current += 1", 0, insert_at)
    assert bump_at > page.index("const fileUploaded"), (
        "الإدراج الفوري بلا رقم ترتيب — يمحوه ردٌّ أقدم منه")

    upload = _code("src", "components", "FileUpload.tsx")
    assert "onUploaded?.(libraryFileFromUpload(stored))" in upload, (
        "المكوّن لا يسلّم الملف الذي أنشأه الخادم")


def test_stored_is_announced_only_after_the_server_answered():
    """«تم الحفظ» في `then` وحدها — لا قبل الطلب ولا بجانبه."""
    upload = _code("src", "components", "FileUpload.tsx")
    assert upload.count('setState("stored")') == 1
    started = upload.index(".then((stored) => {")
    ended = upload.index(".catch((err) => {")
    assert started < upload.index('setState("stored")') < ended, (
        "«تم الحفظ» تُعلَن خارج ردّ الخادم")


def test_the_upload_reports_real_bytes_not_a_spinner():
    """النسبة من `upload.onprogress` — و`fetch` لا يملك حدثًا لتقدّم الإرسال."""
    helper = _code("src", "lib", "upload.ts")
    assert "request.upload.onprogress" in helper, "لا تقدّم حقيقي"
    assert "new XMLHttpRequest()" in helper
    # ولا يُستنسخ عميل الـAPI: التجديد يبقى في موضعه الواحد.
    assert "apiFetch" in helper and "status === 401" in helper

    page = _code("src", "components", "FileUpload.tsx")
    assert "upload.progress" in page and "data-upload-percent" in page


def test_the_library_asks_for_a_bounded_page_and_a_cursor():
    """الواجهة تطلب صفحةً محدودة، وتتقدّم بمؤشّرٍ لا بإزاحة."""
    library = _code("src", "lib", "library.ts")
    assert "?limit=${limit}${cursor}" in library
    assert "&after=" in library

    page = _code("src", "app", "[locale]", "library", "page.tsx")
    assert "listLibraryFilePage" in page
    assert 'data-testid="library-load-more"' in page, "لا سبيل إلى ما بعد الصفحة الأولى"


def test_a_file_card_is_distinguishable_from_a_reference_card():
    """`article.card` يطابق البطاقتين، فعدُّها لا يفرّق بين مكتبةٍ بلا
    ملفات ومكتبةٍ لم تُقرأ — وقد أُبلغ ذلك `cards=2` وهي مراجع لا ملفات."""
    page = _code("src", "app", "[locale]", "library", "page.tsx")
    assert 'data-testid="library-file-card"' in page
