"""ROADMAP STAGE 6 — **الطبقة ب**: المفتاحُ الذي يولّده المتصفّح، في الخادم.

## لماذا طبقتان

فحصُ المتصفّح (الطبقة أ) يثبت أن **المفتاحَ يُعاد كما هو** عبر إعادةِ
المحاولة وتجديدِ الرمز وتبديلِ النقل. ولا يستطيع أن يثبت ما وراء الردّ:
المتصفّحُ لا يرى المزوّد، والجهازُ هنا بلا مزوّدٍ عمدًا (`MODEL_PROVIDER=null`)
— وتفعيلُ مزوّدٍ حقيقيٍّ لأجل فحصٍ إنفاقٌ لا برهان.

فهذا الملفّ يأخذ **نمطَ المتصفّح حرفيًّا** — مفتاحٌ بصيغته هو، يُرسَل
مرّتين على النيّة الواحدة — ويسأل الخادمَ السؤالَ الذي يعنينا:

    **كم مرّةً نُودي المزوّدُ لتوليدٍ واحد؟**

ولا شبكةَ في هذا الملفّ: `build_provider` يُستبدل بعدّادٍ محلّيّ.

## والدعوى محدودةٌ عمدًا

لا يُدَّعى «مرّةً واحدةً بالضبط». يُدَّعى: **لا نداءَ ثانيًا تلقائيًّا
للتوليدِ المُمفتَح نفسِه** — وهو بالضبط ما يشتريه المفتاحُ من المتصفّح.
"""
from __future__ import annotations

import re
import uuid

import pytest

from tests.conftest import requires_db
from tests.test_at_rc_t1_h2b4_model_ambiguity import _activate, _rows
from tests.test_at_rc_t1_h3_ai_long_transactions import _client

pytestmark = pytest.mark.asyncio

# صيغةُ ما يولّده `newIdempotencyKey` في الوِب: `randomUUID` بلا شُرَط.
WEB_KEY = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def browser_key() -> str:
    """مفتاحٌ بالصيغة التي يولّدها المتصفّح — لا صيغةً أخرى تُجامِل الخادم."""
    key = uuid.uuid4().hex
    assert WEB_KEY.match(key), key
    assert "-" not in key, "الوِب يحذف الشُّرَط؛ فحصٌ بمفتاحٍ فيها لا يمثّله"
    return key


@pytest.fixture(autouse=True)
def _memory_storage(monkeypatch):
    from athera_api.config import get_settings
    from athera_api.services import storage

    monkeypatch.setattr(get_settings(), "storage_provider", "memory", raising=False)
    storage.reset_store_cache()
    yield
    storage.reset_store_cache()


class _Counter:
    """مزوّدٌ يعدّ ولا يتّصل — وكلُّ منفذٍ يمرّ به يزيد العدّاد."""

    name = "fake"

    def __init__(self, structured: dict) -> None:
        self.calls = 0
        self._structured = structured

    async def generate_structured(self, request):
        from athera_api.providers.base import ModelResponse, ModelUsage

        self.calls += 1
        return ModelResponse(
            content="", provider="fake", model="m",
            usage=ModelUsage(input_tokens=1, output_tokens=1, cost_usd=0.0,
                             latency_ms=1),
            structured=self._structured)

    async def generate(self, request):  # pragma: no cover - منفذٌ آخرُ يُعدّ أيضًا
        return await self.generate_structured(request)


AI_STRUCTURED = {
    "answer_ar": "جوابٌ مقترَح", "answer_en": "A proposal",
    "citations": [], "unsupported_claims": [], "evidence_gaps": [],
}


@requires_db
async def test_01_the_browser_key_format_is_accepted_by_the_server(
    two_tenants, monkeypatch,
):
    """**الصيغةُ نفسُها تعبر** — ولا يُردّ مفتاحُ المتصفّح لشكله.

    وهذا أوّلُ ما ينكسر لو ضُيِّق التحقّقُ في الخادم يومًا: يصير كلُّ طلبٍ
    محميٍّ من الوِب ٤٠٠، ولا فحصَ في الوِب وحده يراه.
    """
    provider = _activate(monkeypatch, _Counter(AI_STRUCTURED))
    slot = two_tenants["a"]
    key = browser_key()

    async with _client(slot) as http:
        answer = await http.post(
            "/api/v1/ai/ask",
            json={"question": "سؤالٌ بحثيٌّ كافي الطول للفحص."},
            headers={"Idempotency-Key": key})

    assert answer.status_code == 200, answer.text
    assert provider.calls == 1, provider.calls


@requires_db
async def test_02_a_repeated_browser_intent_calls_the_provider_once(
    two_tenants, monkeypatch,
):
    """نيّةٌ واحدة، إرسالان، **نداءٌ واحد** — وهذا هو ما يشتريه المفتاح.

    ويُحاكى هنا ما يفعله المتصفّح حرفيًّا عند إعادةِ المحاولة: الجسمُ نفسُه
    والمفتاحُ نفسُه. ولو وُلِّد مفتاحٌ ثانٍ لصار العدّادُ اثنين — وهو
    بالضبط ما كانت عليه الحال قبل هذه المرحلة.
    """
    provider = _activate(monkeypatch, _Counter(AI_STRUCTURED))
    slot = two_tenants["a"]
    key = browser_key()
    body = {"question": "سؤالٌ بحثيٌّ كافي الطول للفحص."}

    async with _client(slot) as http:
        first = await http.post("/api/v1/ai/ask", json=body,
                                headers={"Idempotency-Key": key})
        retry = await http.post("/api/v1/ai/ask", json=body,
                                headers={"Idempotency-Key": key})

    assert first.status_code == 200, first.text
    assert retry.status_code == 200, retry.text
    assert retry.headers.get("Idempotency-Replayed") == "true"
    assert retry.json() == first.json(), "الإعادةُ ليست الجوابَ الأوّل"
    assert provider.calls == 1, \
        f"التوليدُ الواحدُ نادى المزوّدَ {provider.calls} مرّة"


@requires_db
async def test_03_a_new_deliberate_intent_calls_the_provider_again(
    two_tenants, monkeypatch,
):
    """**ومفتاحٌ جديدٌ عملٌ جديد** — فالحمايةُ ليست تجميدًا.

    الذراعُ الضابطة لـ٠٢: لو كان العدّادُ لا يزيد أبدًا لَما دلّ ثباتُه
    هناك على شيء.
    """
    provider = _activate(monkeypatch, _Counter(AI_STRUCTURED))
    slot = two_tenants["a"]
    body = {"question": "سؤالٌ بحثيٌّ كافي الطول للفحص."}

    async with _client(slot) as http:
        await http.post("/api/v1/ai/ask", json=body,
                        headers={"Idempotency-Key": browser_key()})
        after_first = provider.calls
        second = await http.post("/api/v1/ai/ask", json=body,
                                 headers={"Idempotency-Key": browser_key()})

    assert second.status_code == 200, second.text
    assert after_first == 1, after_first
    assert provider.calls == 2, \
        "نيّةٌ جديدةٌ بمفتاحٍ جديدٍ لم تصل إلى المزوّد"


@requires_db
async def test_04_an_unkeyed_request_is_unchanged_and_calls_each_time(
    two_tenants, monkeypatch,
):
    """وبلا ترويسةٍ يبقى السلوكُ القديمَ حرفيًّا — فالتبنّي لم يغيّر العقد.

    وهذا يحرس التوافقَ مع أيِّ عميلٍ لم يُحدَّث بعد.
    """
    provider = _activate(monkeypatch, _Counter(AI_STRUCTURED))
    slot = two_tenants["a"]
    body = {"question": "سؤالٌ بحثيٌّ كافي الطول للفحص."}

    async with _client(slot) as http:
        one = await http.post("/api/v1/ai/ask", json=body)
        two = await http.post("/api/v1/ai/ask", json=body)

    assert one.status_code == 200 and two.status_code == 200
    assert two.headers.get("Idempotency-Replayed") is None
    assert provider.calls == 2, provider.calls


@requires_db
async def test_05_the_replay_writes_no_second_model_run(two_tenants, monkeypatch):
    """ولا صفَّ تشغيلةٍ ثانٍ للإعادة — فالدفترُ يقول ما وقع لا ما طُلب.

    وعدّادُ المزوّدِ وحدَه لا يكفي: مسلكٌ قد يُعيد الجوابَ ويكتب تشغيلةً
    ثانية، فيقرأ المحاسبُ توليدَين حيث كان واحد.
    """
    provider = _activate(monkeypatch, _Counter(AI_STRUCTURED))
    slot = two_tenants["a"]
    key = browser_key()
    body = {"question": "سؤالٌ بحثيٌّ كافي الطول للفحص."}
    count = "SELECT count(*) FROM agent_runs WHERE tenant_id = :t"
    params = {"t": str(slot["tenant_id"])}

    before = await _rows(count, params)
    async with _client(slot) as http:
        await http.post("/api/v1/ai/ask", json=body, headers={"Idempotency-Key": key})
        after_first = await _rows(count, params)
        await http.post("/api/v1/ai/ask", json=body, headers={"Idempotency-Key": key})
    after_replay = await _rows(count, params)

    assert after_first != before, "لم تُسجَّل تشغيلةٌ للنجاح الأوّل"
    assert after_replay == after_first, "الإعادةُ أنشأت تشغيلةً ثانية"
    assert provider.calls == 1, provider.calls


@requires_db
async def test_06_a_changed_body_under_the_same_key_never_reaches_the_provider(
    two_tenants, monkeypatch,
):
    """ونيّةٌ تغيّرت تحت مفتاحٍ لم يتغيّر: تعارضٌ **قبل** المزوّد.

    والمتصفّحُ يمنع هذا من جهته (بصمةٌ تتغيّر ⇒ مفتاحٌ يتغيّر)، والخادمُ
    يمنعه من جهته. والحدّان معًا: لو أخطأ أحدهما يومًا لم يُنفَق شيء.
    """
    provider = _activate(monkeypatch, _Counter(AI_STRUCTURED))
    slot = two_tenants["a"]
    key = browser_key()

    async with _client(slot) as http:
        await http.post("/api/v1/ai/ask",
                        json={"question": "سؤالٌ بحثيٌّ كافي الطول للفحص."},
                        headers={"Idempotency-Key": key})
        after_first = provider.calls
        clash = await http.post("/api/v1/ai/ask",
                                json={"question": "سؤالٌ آخرُ مختلفٌ تمامًا هنا."},
                                headers={"Idempotency-Key": key})

    assert clash.status_code == 409, clash.text
    assert clash.json()["error"]["code"] == "idempotency.key_reused", clash.text
    assert provider.calls == after_first == 1, provider.calls
