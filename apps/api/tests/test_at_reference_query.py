"""فهم الاستعلام وصمود الفهارس | Query intelligence and provider resilience.

**الخطّ الفاصل الذي تحرسه هذه الاختبارات**: أن تُفهَم نيّة الباحث شيء، وأن
تُعاد كتابتها شيء آخر. الاقتراح يُعرض ولا يُطبَّق؛ ولا يدخل مصطلحٌ في
الطلب حتى يعود من الواجهة مقبولًا باسمه.

وبلا شبكة، عن قصد: طبقة الإعادة تأخذ نداءً وتعيد قاموسًا، فتُختبر
بنداءاتٍ مزوّرة تعدّ نفسها — ولا تنتظر ثانيةً واحدة.
"""
from __future__ import annotations

import asyncio

import pytest

from athera_api.discovery import ProviderUnavailable, fetch_json, parse_query
from athera_api.discovery import throttle
from athera_api.discovery.resilience import RETRYABLE_STATUS, backoff_delay


class _Recorder:
    """نداءٌ مزوَّر يعيد ردودًا مرتَّبة ويحصي كم مرّة نودي."""

    def __init__(self, *outcomes: object) -> None:
        self._outcomes = list(outcomes)
        self.calls = 0

    async def __call__(self) -> tuple[int, dict | None]:
        self.calls += 1
        outcome = self._outcomes[min(self.calls - 1, len(self._outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome  # type: ignore[return-value]


class _Clock:
    """ساعةٌ تتقدّم بالنوم وحده — فتُختبر الميزانية بلا انتظارٍ حقيقي."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    def __call__(self) -> float:
        return self.now


def _run(**kwargs: object) -> dict:
    return asyncio.run(fetch_json(**kwargs))  # type: ignore[arg-type]


# ─────────────────── ما يُقرأ من نصّ الباحث ───────────────────

def test_plain_keywords_stay_exactly_as_the_researcher_wrote_them():
    parsed = parse_query("digital transformation in higher education")
    assert parsed.raw == parsed.sent == "digital transformation in higher education"
    # وألفاظ الربط تُسقط من المصطلحات وحدها — لا من نصّه المعروض.
    assert parsed.keywords == ("digital", "transformation", "higher", "education")


def test_a_doi_is_recognised_wherever_it_sits_and_stops_word_matching():
    """المعرّف يُحلّ بذاته: أجزاؤه ليست مصطلحات بحث.

    ولو حُسبت لَصارت ورقةٌ أخرى في الدوريّة نفسها «مطابِقة» لمعرّفٍ لا يخصّها.
    """
    parsed = parse_query("https://doi.org/10.1016/j.jbusres.2020.06.008")
    assert parsed.doi == "10.1016/j.jbusres.2020.06.008"
    assert parsed.is_identifier_lookup is True
    assert parsed.keywords == ()


def test_an_author_operator_is_a_constraint_not_a_topic_word():
    """اسم المؤلّف يُرسَل إلى الفهرس ولا يُحسب مصطلحًا موضوعيًّا.

    ولو حُسب لظهر «لا يذكر: أوكافور» تحت كل ورقةٍ كتبها — وهو عبثٌ يُعلّم
    الباحث تجاهل التحذيرات كلها.
    """
    parsed = parse_query("author:Okafor digital transformation")
    assert parsed.authors == ("Okafor",)
    assert parsed.keywords == ("digital", "transformation")
    # البادئة وحدها تُنزع من النصّ المُرسَل، والاسم يبقى: الفهرس يبحث به.
    assert parsed.sent == "Okafor digital transformation"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("machine learning year:2019", (2019, None, None)),
        ("machine learning سنة:2019", (2019, None, None)),
        ("machine learning year:2015-2020", (None, 2015, 2020)),
    ],
)
def test_a_year_is_read_in_both_languages_and_as_a_range(text, expected):
    parsed = parse_query(text)
    assert (parsed.year, parsed.year_from, parsed.year_to) == expected
    # والسنة قيدٌ لا موضوع: لا تصير مصطلحًا غائبًا في كل ورقة.
    assert "2019" not in parsed.keywords and "2015" not in parsed.keywords


def test_an_arabic_word_is_displayed_as_written_not_as_normalised():
    """**التسوية أداةُ مقارنة لا صورةَ عرض.**

    «إدارة» تُسوَّى «اداره» للمطابقة؛ ولو عُرضت مسوّاةً في «لا يذكر: اداره»
    لقرأها الباحث خطأً إملائيًّا منّا، فشكّ في بقيّة ما نقول.
    """
    parsed = parse_query("إدارة التغيير في الجامعات")
    assert "اداره" in parsed.keywords
    assert parsed.display("اداره") == "إدارة"
    # وما لا صورة له يُعاد كما هو، ولا يسقط النصّ.
    assert parsed.display("غير موجودة") == "غير موجودة"


def test_a_quoted_phrase_is_kept_as_a_phrase():
    parsed = parse_query('"technology acceptance model" in nursing')
    assert parsed.phrase == "technology acceptance model"
    assert "acceptance" in parsed.keywords


def test_a_title_operator_points_the_match_at_the_title():
    parsed = parse_query('title:"digital transformation"')
    assert parsed.title_hint == "digital transformation"


# ─────────────────── الاقتراح لا يُطبَّق ───────────────────

def test_a_suggested_term_is_offered_and_never_applied_on_its_own():
    """**هذا هو الحارس الأهمّ في هذا الملف.**

    الاقتراح يظهر، والنصّ المُرسَل يبقى نصّ الباحث حرفًا بحرف. ومن وسّع
    البحث نيابةً عنه بدّل سؤاله البحثي ثم أراه نتائج سؤالٍ آخر.
    """
    parsed = parse_query("AI in higher education")
    assert [one.term for one in parsed.suggestions] == ["artificial intelligence"]
    assert parsed.suggestions[0].accepted is False
    assert parsed.sent == "AI in higher education"
    assert parsed.was_expanded is False


def test_an_accepted_term_enters_the_query_and_the_original_stays_visible():
    """القبول يُضيف ولا يستبدل: نصّه باقٍ في `raw` ليُقارَن بما أُرسل."""
    parsed = parse_query(
        "AI in higher education", accepted_terms=["artificial intelligence"],
    )
    assert parsed.raw == "AI in higher education"
    assert parsed.sent == "AI in higher education artificial intelligence"
    assert parsed.accepted_terms == ("artificial intelligence",)
    assert parsed.was_expanded is True


def test_an_arabic_query_is_offered_its_english_counterpart_not_a_neighbour():
    """المقترَح مقابلٌ للمصطلح نفسه، لا بناءٌ مجاورٌ له في الأدبيات."""
    parsed = parse_query("التحول الرقمي في التعليم العالي")
    terms = {one.term for one in parsed.suggestions}
    assert terms == {"digital transformation", "higher education"}
    assert all(one.kind == "translation" for one in parsed.suggestions)


def test_suggestions_are_deterministic_and_never_repeat_what_is_already_written():
    """اقتراحُ ما عند الباحث ضجيجٌ يُعلّمه تجاهل الاقتراحات كلها."""
    assert parse_query("ML models").suggestions == parse_query("ML models").suggestions
    assert parse_query("machine learning ML").suggestions == ()


def test_accepted_terms_from_the_wire_are_bounded_and_deduplicated():
    """المدخل من الشبكة لا يُصدَّق: يُنقّى ويُسقَّف قبل أن يمسّ الاستعلام."""
    parsed = parse_query("x y", accepted_terms=["a", "A", "", None, "b" * 500, *"cdefghijk"])
    assert len(parsed.accepted_terms) <= 8
    assert parsed.accepted_terms[0] == "a"
    assert all(len(term) <= 120 for term in parsed.accepted_terms)


def test_a_non_list_of_accepted_terms_is_ignored_rather_than_trusted():
    assert parse_query("x y", accepted_terms="artificial intelligence").accepted_terms == ()


# ─────────────────── صمود الفهارس ───────────────────

def test_a_transient_failure_is_retried_and_then_succeeds():
    """ارتعاشةٌ واحدة لا تُعلَن «الفهرس لم يجب» — وإلا ضاع نصف ما يُعرف."""
    clock = _Clock()
    send = _Recorder(ConnectionError("reset"), (200, {"ok": True}))
    payload = _run(send=send, provider="crossref", sleep=clock.sleep, clock=clock)
    assert payload == {"ok": True}
    assert send.calls == 2


@pytest.mark.parametrize("status", sorted(RETRYABLE_STATUS))
def test_load_and_outage_codes_are_retried(status):
    clock = _Clock()
    send = _Recorder((status, None), (200, {"ok": True}))
    assert _run(send=send, provider="openalex", sleep=clock.sleep, clock=clock) == {"ok": True}
    assert send.calls == 2


def test_a_verdict_that_will_not_change_is_never_repeated():
    """٤٠٠ و٤٠١ أحكامٌ لا تتبدّل بالتكرار — وإعادتها إسرافٌ في مرورٍ لن ينفع."""
    clock = _Clock()
    send = _Recorder((400, None))
    with pytest.raises(ProviderUnavailable) as failure:
        _run(send=send, provider="crossref", sleep=clock.sleep, clock=clock)
    assert send.calls == 1
    assert failure.value.detail == "HTTP 400"


def test_a_404_is_an_answer_not_an_outage():
    """«لا أعرف هذا المعرّف» جوابٌ يُنقل، لا عطبٌ يُعاد السؤال عنه."""
    send = _Recorder((404, None))
    assert _run(send=send, provider="crossref") == {}
    assert send.calls == 1


def test_retries_are_bounded_and_the_failure_is_named_at_the_end():
    """السقف حقيقي: ثلاث محاولات ثم يُعلَن التعذّر باسم المزوّد وسببه."""
    clock = _Clock()
    send = _Recorder((503, None))
    with pytest.raises(ProviderUnavailable) as failure:
        _run(send=send, provider="openalex", sleep=clock.sleep, clock=clock)
    assert send.calls == 3
    assert failure.value.provider == "openalex"
    assert "503" in failure.value.detail


def test_the_backoff_grows_and_is_capped():
    delays = [backoff_delay(attempt) for attempt in range(1, 8)]
    assert delays == sorted(delays)
    assert max(delays) <= 2.0


def test_the_total_time_budget_ends_the_attempts_even_with_retries_left():
    """ثلاثُ محاولاتٍ بمهلة ثمانٍ لكلٍّ منها انقطاعٌ عمليّ، لا صمود.

    فالميزانية تُنهي الأمر ولو بقيت محاولات، ويُعلَن التعذّر بدل أن يُنتظر
    ما لن يُنتظر.
    """
    clock = _Clock()
    send = _Recorder((503, None))
    with pytest.raises(ProviderUnavailable) as failure:
        _run(send=send, provider="crossref", budget=0.1, sleep=clock.sleep, clock=clock)
    assert send.calls == 1
    assert clock.slept == []
    assert "budget" in failure.value.detail


def test_an_empty_body_on_success_is_an_empty_answer_not_a_crash():
    assert _run(send=_Recorder((200, None)), provider="crossref") == {}


# ─────────────────── حدُّ المعدّل ───────────────────

def test_a_normal_researchers_pace_is_never_throttled():
    """الحدّ حمايةٌ من حلقةٍ معطوبة، لا تقنينٌ لباحثٍ يفكّر ويعيد صياغة سؤاله."""
    throttle.reset()
    assert all(throttle.check(("tenant", "user"), clock=lambda: 0.0) == 0 for _ in range(29))


def test_a_runaway_client_is_told_how_long_to_wait_not_just_refused():
    """«حاول لاحقًا» بلا رقمٍ تجعل العميل يعيد فورًا فيطيل حبسه بنفسه."""
    throttle.reset()
    for _ in range(throttle.MAX_SEARCHES_PER_WINDOW):
        throttle.check(("tenant", "user"), clock=lambda: 0.0)
    wait = throttle.check(("tenant", "user"), clock=lambda: 0.0)
    assert 0 < wait <= int(throttle.WINDOW_SECONDS) + 1


def test_one_runaway_tenant_does_not_throttle_another():
    """الحدّ بمفتاح (مستأجر، مستخدم): حلقةُ واحدٍ لا تحبس جاره."""
    throttle.reset()
    for _ in range(throttle.MAX_SEARCHES_PER_WINDOW + 5):
        throttle.check(("noisy", "user"), clock=lambda: 0.0)
    assert throttle.check(("quiet", "user"), clock=lambda: 0.0) == 0


def test_the_window_slides_so_the_limit_is_never_permanent():
    throttle.reset()
    for _ in range(throttle.MAX_SEARCHES_PER_WINDOW):
        throttle.check(("tenant", "user"), clock=lambda: 0.0)
    later = throttle.WINDOW_SECONDS + 1
    assert throttle.check(("tenant", "user"), clock=lambda: later) == 0
