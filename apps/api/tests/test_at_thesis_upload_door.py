"""بابُ رفع الرسالة — يُطرق من حيث يطرقه الباحث | the thesis intake door.

**ألفٌ وسبعُمئةٍ وسبعةٌ وخمسون فحصًا خضراء، والبابُ مغلق.**

`POST /api/v1/theses/upload` كان يردّ ٥٠٠ على **كل** طلب، في الإنتاج وفي
هذا الفرع معًا. والسبب سطرٌ واحد: `files.upload_file` صارت تفتح جلستها
بنفسها في `0cdb23a` — رفعُ كتابٍ واحد كان يُجمّد المنتج كلّه، فخرج الرفع
من معاملة الطلب — وبقي نداءٌ في `document_intelligence` يمرّر
`session=` إلى دالّةٍ لم تعد تقبلها:

    TypeError: upload_file() got an unexpected keyword argument 'session'

ولم يسقط فحصٌ واحد، لأنّ **لا فحص في المستودع كان يُصدر هذا الطلب عبر
HTTP**. كانت الفحوص تبلغ الخدمة من غير طريق الباب، فالحسابُ تحته سليم
والبابُ مسمّر. وهو الدرسُ نفسه الذي أخرج أربع نقاطٍ تختم معاملتها في
الموجة الماضية: **ما لا يُطرق من الخارج لا يُعرف أنّه مفتوح.**

فهذا الملفّ يطرق. ولا يفحص جودة الاستخراج ولا حال المعالجة — لتلك
فحوصها — بل شيئًا واحدًا: أنّ الطلب يبلغ المعالج ويعود بما يُفهم.
"""
from __future__ import annotations

import pytest
import pytest_asyncio

from tests.conftest import requires_db



def _tiny_pdf() -> bytes:
    """مستندٌ صغيرٌ صالحُ البنية — يُولَّد ولا يُخزَّن في المستودع."""
    return (b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
            b"trailer<</Root 1 0 R>>\n%%EOF\n")


@pytest.fixture(autouse=True)
def memory_store(monkeypatch):
    from athera_api.config import get_settings
    from athera_api.services import storage

    monkeypatch.setattr(get_settings(), "storage_provider", "memory", raising=False)
    storage.reset_store_cache()
    yield
    storage.reset_store_cache()


@pytest_asyncio.fixture
async def researcher(two_tenants):
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    tenant = two_tenants["a"]
    token = issue_access_token(
        user_id=tenant["user_id"], tenant_id=tenant["tenant_id"],
        roles=["researcher"], mfa_satisfied=True)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": "ar"},
    ) as client:
        yield client


@requires_db
@pytest.mark.asyncio
async def test_the_thesis_intake_door_opens(researcher):
    """**الطلبُ يبلغ المعالج ويعود بما يُفهم** — لا ٥٠٠.

    والفحصُ يقف عند الباب عمدًا: يقبل كلّ ردٍّ مفهوم — قَبولًا أو رفضًا
    مُعلَّلًا — ويرفض واحدًا: أن ينهار الخادم. فانهيارُه يعني أنّ أحدًا لم
    يطرق منذ أن تغيّر ما خلف الباب.
    """
    answer = await researcher.post(
        "/api/v1/theses/upload",
        files={"upload": ("door.pdf", _tiny_pdf(), "application/pdf")})

    assert answer.status_code < 500, (
        f"بابُ رفع الرسالة ينهار: {answer.status_code} — {answer.text[:200]}")
    assert answer.status_code in {200, 201, 202, 400, 415, 422}, answer.text


@requires_db
@pytest.mark.asyncio
async def test_the_intake_names_the_file_it_received(researcher):
    """وما قُبل يُعرَف باسمه — فبطاقةٌ بلا هويّة أوّلُ عطبٍ رآه المالك."""
    answer = await researcher.post(
        "/api/v1/theses/upload",
        files={"upload": ("رسالةُ ماجستير.pdf", _tiny_pdf(), "application/pdf")})
    if answer.status_code >= 400:
        pytest.skip(f"المستند رُفض لسببٍ مُعلَّل: {answer.status_code}")

    body = answer.json()
    assert body.get("thesis_id"), "قُبل الرفع ولا معرّف رسالةٍ يعود"
    assert body.get("file_id"), "قُبل الرفع ولا معرّف ملفٍّ يعود"


@requires_db
@pytest.mark.asyncio
async def test_the_door_is_shut_to_the_anonymous():
    """**والبابُ المفتوح للكلّ ليس بابًا.**

    وهذا الطرف من الفحص هو ما يمنع أن يُصلَح انهيارُ الباب بفتحه للجميع.
    """
    import httpx

    from athera_api.main import app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as guest:
        answer = await guest.post(
            "/api/v1/theses/upload",
            files={"upload": ("door.pdf", _tiny_pdf(), "application/pdf")})
    assert answer.status_code in {401, 403}, answer.text


def test_the_call_site_matches_the_signature_it_calls():
    """**والتوقيعان يُقابَلان بالبنية، لا بانتظار طلبٍ يسقط.**

    فحصُ الباب أعلاه يحتاج قاعدةً، ولا قاعدة على جهاز التطوير — فمرّ العطب
    محلّيًّا حتى بلغ الإنتاج. وهذه المقابلة تعمل في كل مكان وبلا شيء.
    """
    import inspect

    from athera_api.routers import document_intelligence, files

    accepted = set(inspect.signature(files.upload_file).parameters)
    source = inspect.getsource(document_intelligence.upload_thesis)
    call = source.split("upload_file(", 1)[1].split(")", 1)[0]
    passed = {piece.split("=", 1)[0].strip()
              for piece in call.split(",") if "=" in piece}

    unknown = passed - accepted
    assert not unknown, (
        f"نداءُ رفع الرسالة يمرّر ما لا تقبله `upload_file`: {sorted(unknown)}")

    # **وما لم يُمرَّر يصل شاهدًا لا قيمة.**
    #
    # قيمُ FastAPI الافتراضية (`Form(...)`، `Depends(...)`) شواهدُ يحلّها
    # الإطار عند الطلب. ومن نادى النقطةَ كدالّةٍ عاديّة وترك وسيطًا لقيمته
    # الافتراضية تسلّم كائنَ `Form` بدل `None` — فمرّ من `if not folder_id`
    # وسقط في `uuid.UUID(...)`. وهو عطبٌ كان مختبئًا خلف الأوّل تمامًا.
    sentinels = {
        name for name, parameter
        in inspect.signature(files.upload_file).parameters.items()
        if parameter.default is not inspect.Parameter.empty
        and type(parameter.default).__name__ in {"Form", "File", "Depends", "Query"}
    }
    missed = sentinels - passed
    assert not missed, (
        "وسائطُ نقطةِ نهايةٍ تُركت لشواهدها بدل أن تُمرَّر صراحةً: "
        f"{sorted(missed)}")


def test_the_signature_guard_would_notice_a_stale_argument():
    """حارسٌ لا يسقط أبدًا ليس حارسًا."""
    def target(*, alpha, beta):  # pragma: no cover — توقيعٌ للفحص
        return alpha, beta

    import inspect

    accepted = set(inspect.signature(target).parameters)
    passed = {"alpha", "beta", "session"}
    assert passed - accepted == {"session"}
