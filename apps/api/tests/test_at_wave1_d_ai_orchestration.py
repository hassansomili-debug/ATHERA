"""Wave1-D — تنسيقُ أثيرا AI وحقيقةُ الأدبيات (PUBRIVA).

**العطب الذي يحرسه هذا الملف عطبُ صدقٍ لا عطبُ شكل.**

كانت الطبقة تطوي ثلاث قدراتٍ في منطقٍ واحد:

    literature_online = os.getenv("LITERATURE_REGISTRY", "offline") != "offline"

فتقول للباحث — وللنموذج معه — إنّ «البحث الخارجي في الأدبيات غير مفعّل»
ما دام سجلُّ الرصد المجدول مطفأً. والإنتاج يعمل بـ`offline`، واكتشافُ
المراجع ينادي Crossref وOpenAlex في كل بحثٍ في الشاشة المجاورة. فكان
المنتج **ينفي قدرةً قائمة**، ويعتذر عن بحثٍ يستطيع إجراءه، ويردّ طلبًا
صريحًا بإحالةٍ إلى شاشةٍ أخرى.

فيُثبت هنا تسعة:

١) **ثلاثُ قدراتٍ لا واحدة**، وكلٌّ مشتقّةٌ من سجلّها لا مكتوبةٌ بجانبه.
٢) **الطلبُ الصريح يُنفَّذ**: من طلب بحثًا في الأدبيات نُفِّذ له، بلا إذنٍ
   يُستأذن عليه ثانيةً.
٣) **النطاق Crossref وOpenAlex وحدهما**، ولا جمعَ من Scholar ولا
   ResearchGate ولا Academia — والأخيران رابطا وصولٍ لا قاعدتا بيانات.
٤) **النسبة محفوظة**: عدّاد كل فهرسٍ باسمه، ولا رقم مدموج، ولا حقل يُملأ
   استنتاجًا.
٥) **جملةُ النطاق تُقال مرّة**، ولا تُكدَّس ثلاثة تحذيراتٍ دفاعية.
٦) **ما لم يُبحَث يُقال «لم يُبحَث»**، لا «البحث معطّل» والبحثُ يعمل.
٧) **العزل**: مشروعُ مستأجرٍ آخر ٤٠٤، لا سياقٌ فارغ.
٨) **الملخّصُ ليس الورقة**: سؤالٌ يحتاج نصًّا كاملًا يُردّ عن التجاوز ويُقال لماذا.
٩) **العقد العلمي لا ينحدر**: الرفضُ قبل الإذن، وبعده جوابٌ **جديد** مسنود.
"""
from __future__ import annotations

import datetime as dt
import inspect
import pathlib
import uuid

import pytest

from tests.conftest import requires_db
from tests.discovery_boundary import no_indexes, stub_indexes

API = pathlib.Path(__file__).resolve().parents[1] / "athera_api"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# ═════════════════ ١. القدرات الثلاث ═════════════════

def test_the_three_capabilities_are_three_not_one():
    """**العقدُ نفسه يفصلها.** حقلٌ واحد اسمه `literature_online` كان يجعل
    الخلط ممكنًا في كل قارئ؛ وثلاثةُ حقولٍ تجعله مستحيلًا."""
    from athera_api.schemas.ai import AiCapabilities

    fields = set(AiCapabilities.model_fields)
    assert {"reference_discovery_available", "literature_registry_available",
            "full_text_retrieval_available"} <= fields
    assert "literature_online" not in fields


def _code_lines(path: pathlib.Path) -> str:
    """الشفرة المنفَّذة وحدها — بلا تعليقاتٍ ولا سلاسل توثيق.

    والتعليق الذي **يصف** العطب المُصلَح لا يجوز أن يُحاسَب عليه أحد؛
    وحارسٌ يقرأ التعليقات يمنع كتابة السبب، فيُصلَح العطب ويُنسى لماذا.
    """
    text = path.read_text(encoding="utf-8")
    body = text.split('"""', 2)[2] if text.startswith('"""') else text
    return "\n".join(line for line in body.splitlines()
                     if not line.lstrip().startswith("#"))


def test_the_router_no_longer_reads_the_registry_env_to_decide_search():
    """**القيمةُ تُشتقّ من سجلّها ولا تُكتب بجانبه.**

    وهو الخطأ المتكرّر في هذا المستودع؛ وأثرُه هنا أنّ متغيّر بيئةٍ لا علاقة
    له بالاكتشاف كان يحكم على الاكتشاف.
    """
    code = _code_lines(API / "routers" / "ai.py")
    assert "LITERATURE_REGISTRY" not in code, \
        "الموجّه ما زال يقرأ سجلّ الرصد ليقرّر البحث"
    assert "literature_online" not in code
    # ولا في السياسة: الإعلان الذي يصل النموذج كان يحمل الكذبة نفسها.
    assert "literature_online" not in _code_lines(API / "services" / "ai_policy.py")


def test_reference_discovery_is_derived_from_the_providers_themselves(monkeypatch):
    from athera_api.services import ai_capabilities, reference_discovery

    monkeypatch.setattr(reference_discovery, "enabled_providers", list)
    off = ai_capabilities.current()
    assert off.reference_discovery_available is False
    assert off.reference_discovery_providers == ()

    stub_indexes(monkeypatch)
    on = ai_capabilities.current()
    assert on.reference_discovery_available is True
    # الأسماء من المزوّدين أنفسهم — فإن أُضيف فهرسٌ ظهر، وإن أُزيل اختفى.
    assert on.reference_discovery_providers == tuple(
        p.name for p in reference_discovery.enabled_providers())


def test_the_registry_flag_is_derived_from_the_registry_object(monkeypatch):
    """لا من نصّ البيئة: المصنع هو من يعرف ماذا بنى."""
    from athera_api.services import ai_capabilities
    from athera_api.services.literature import registry_factory

    registry_factory.get_registry.cache_clear()
    monkeypatch.setenv("LITERATURE_REGISTRY", "offline")
    assert ai_capabilities.current().literature_registry_available is False

    registry_factory.get_registry.cache_clear()
    monkeypatch.setenv("LITERATURE_REGISTRY", "crossref")
    live = ai_capabilities.current()
    assert live.literature_registry_available is True
    assert live.literature_registry == "crossref"

    # واسمٌ مجهول يُعلَن حالًا ثالثة، ولا يسقط بصمت إلى «متاح».
    registry_factory.get_registry.cache_clear()
    monkeypatch.setenv("LITERATURE_REGISTRY", "not-a-registry")
    unknown = ai_capabilities.current()
    assert unknown.literature_registry_available is False
    assert unknown.literature_registry == "unknown"
    registry_factory.get_registry.cache_clear()


def test_the_registry_being_offline_never_disables_reference_discovery(monkeypatch):
    """**حالُ الإنتاج بعينها** — وهي الحال التي كانت تُقرأ كذبًا."""
    from athera_api.services import ai_capabilities
    from athera_api.services.literature import registry_factory

    registry_factory.get_registry.cache_clear()
    monkeypatch.setenv("LITERATURE_REGISTRY", "offline")
    stub_indexes(monkeypatch)
    caps = ai_capabilities.current()
    assert caps.literature_registry_available is False
    assert caps.reference_discovery_available is True
    registry_factory.get_registry.cache_clear()


def test_full_text_availability_comes_from_the_storage_layer(monkeypatch):
    """**والنصّ الكامل لا يأتي من فهرس.** فهرسٌ يعلن ورقةً «مفتوحة الوصول»
    يعلن حقًّا لا يمنح نصًّا؛ والنصّ في هذا المنتج ملفٌّ رفعه الباحث."""
    from athera_api.services import ai_capabilities, storage

    monkeypatch.setattr(storage, "is_configured", lambda: False)
    assert ai_capabilities.current().full_text_retrieval_available is False
    monkeypatch.setattr(storage, "is_configured", lambda: True)
    assert ai_capabilities.current().full_text_retrieval_available is True


def test_the_provider_gate_has_exactly_one_source(monkeypatch):
    """موجّهُ المراجع والمحادثةُ يقرآن القرار نفسه.

    ونسخُه كان يجعل البحث يعمل في شاشةٍ ولا يعمل في أخرى بعد أوّل تعديل
    يمسّ إحدى النسختين — بلا سببٍ يفهمه الباحث.
    """
    from athera_api.routers import literature
    from athera_api.services import reference_discovery

    sentinel = [object()]
    monkeypatch.setattr(reference_discovery, "enabled_providers", lambda: sentinel)
    assert literature._discovery_providers() is sentinel


# ═════════════════ ٢. النيّة: الطلبُ الصريح يُقرأ ═════════════════

@pytest.mark.parametrize("question", [
    "ابحث لي في الأدبيات الحديثة عن التحول الرقمي",
    "ابحث عن دراسات حول التعليم الإلكتروني في السعودية",
    "أعطني مراجع عن نظرية السلوك المخطط",
    "ما هي الدراسات السابقة عن رضا المستفيدين؟",
    "أحدث الأدبيات في القيادة التحويلية",
    "find papers on digital transformation in higher education",
    "search literature about transformational leadership",
])
def test_an_explicit_literature_request_is_recognised(question):
    from athera_api.services import ai_intent

    intent = ai_intent.classify(question)
    assert intent.wants_literature_search, question
    assert intent.matched, "قرارٌ بلا كلمةٍ تفسّره"


@pytest.mark.parametrize("question", [
    "أريد دراسة أثر الذكاء الاصطناعي في الاتصال التسويقي",
    "راجع منهجيتي من فضلك",
    "كيف أصوغ سؤال البحث؟",
    "حلّل بياناتي الوصفية",
    "help me structure my study design",
])
def test_a_general_question_never_triggers_an_external_call(question):
    """**والبحثُ في غير موضعه إنفاقُ نداءٍ خارجيّ بلا سبب** — ويحرق ائتماننا
    عند فهرسٍ يمنحنا الاستعمال بأدبٍ لا بعقد."""
    from athera_api.services import ai_intent

    assert not ai_intent.classify(question).wants_literature_search, question


@pytest.mark.parametrize("question", [
    "اقتبس لي نصًّا حرفيًّا من قسم النتائج",
    "في أي صفحة ورد هذا؟",
    "quote the methods section for me",
])
def test_a_full_text_question_is_flagged(question):
    from athera_api.services import ai_intent

    assert ai_intent.classify(question).needs_full_text, question


def test_a_literature_request_that_also_wants_a_quote_still_searches():
    """العلمان مستقلّان عمدًا: لو كان «يحتاج نصًّا كاملًا» نيّةً مانعة لسقط
    البحثُ الذي طُلب صراحةً."""
    from athera_api.services import ai_intent

    intent = ai_intent.classify("ابحث عن دراسات واقتبس منها نصًّا حرفيًّا")
    assert intent.wants_literature_search and intent.needs_full_text


# ═════════════════ ٣. النطاق: فهرسان لا أكثر ═════════════════

def test_only_crossref_and_openalex_are_ever_called():
    from athera_api.discovery.service import default_providers

    assert {p.name for p in default_providers()} == {"crossref", "openalex"}


def test_no_scraping_host_appears_anywhere_in_the_discovery_path():
    """**ResearchGate وAcademia رابطا وصولٍ لا قاعدتا بيانات**، وScholar لا
    يُجمع منه شيء. والحدّ يُفحص في الشفرة لا يُوعد به في وثيقة."""
    banned = ("scholar.google", "researchgate.com/search", "academia.edu/search",
              "www.researchgate.net/profile")
    for path in list((API / "discovery").glob("*.py")) + [
        API / "services" / "reference_discovery.py", API / "routers" / "ai.py",
    ]:
        text = path.read_text(encoding="utf-8")
        for host in banned:
            assert host not in text, f"{path.name}: {host}"


def test_a_blocked_platform_link_is_returned_as_a_link_and_never_fetched():
    from athera_api.discovery.normalize import external_access_link

    found = external_access_link("https://www.researchgate.net/publication/123_Some_Paper")
    assert found is not None
    assert "researchgate" in found[1]


# ═════════════════ ٤. حقيقةُ النتيجة ═════════════════

def test_a_reference_keeps_every_field_its_index_stated_and_invents_none():
    from athera_api.discovery import crossref as crossref_module
    from athera_api.discovery.contracts import ReferenceCandidate
    from athera_api.services import reference_discovery

    item = load_first_crossref()
    claim = crossref_module.to_claim(item)
    found = reference_discovery.to_reference(ReferenceCandidate(claims=(claim,)))

    assert found.title == claim.title
    assert found.authors == claim.authors and found.authors
    assert found.year == claim.year
    assert found.venue == claim.venue
    assert found.doi == claim.doi
    assert found.providers == ("crossref",)
    # ولا حقل يُملأ استنتاجًا: ما لم يقله الفهرس يبقى غيابًا.
    assert found.open_access is claim.open_access


def test_two_indexes_keep_two_counts_and_are_never_merged():
    """**رقمٌ مدموج رقمٌ لا يقوله أحد.** جمعُ عدّادَي فهرسين يضاعف الاستشهاد
    الواحد، والمتوسّطُ لا يمكن التحقّق منه في أيّ فهرس."""
    from athera_api.discovery.contracts import ProviderClaim, ReferenceCandidate
    from athera_api.services import reference_discovery

    doi = "10.1000/xyz"
    candidate = ReferenceCandidate(claims=(
        ProviderClaim(provider="crossref", provider_id=doi, title="T", doi=doi,
                      citation_count=120),
        ProviderClaim(provider="openalex", provider_id="W1", title="T", doi=doi,
                      citation_count=134),
    ), match_basis="doi")
    found = reference_discovery.to_reference(candidate)
    assert found.citation_counts == {"crossref": 120, "openalex": 134}
    assert 254 not in found.citation_counts.values()
    assert 127 not in found.citation_counts.values()


def test_a_reference_scope_is_never_full_text_from_an_index():
    """فهرسٌ يرسل ملخّصًا يعطي `abstract_only`، وما عداه `metadata_only`.
    ولا يصير `full_text` بحالٍ من نداءٍ ببليوغرافي."""
    from athera_api.discovery.contracts import ProviderClaim, ReferenceCandidate
    from athera_api.services import reference_discovery

    bare = ReferenceCandidate(claims=(ProviderClaim(
        provider="crossref", provider_id="a", title="T"),))
    with_abstract = ReferenceCandidate(claims=(ProviderClaim(
        provider="crossref", provider_id="b", title="T", abstract="ملخّص"),))
    assert reference_discovery.to_reference(bare).scope == "metadata_only"
    assert reference_discovery.to_reference(with_abstract).scope == "abstract_only"


def test_the_prompt_writes_a_missing_field_as_missing_not_as_blank():
    """**فراغٌ في قائمةٍ يُقرأ قيمة.** والنموذج يملؤه من عنده."""
    from athera_api.routers.ai import _evidence_rows, _rendered
    from athera_api.services.reference_discovery import DiscoveredReference

    bare = DiscoveredReference(
        title="عنوانٌ بلا شيءٍ آخر", authors=(), year=None, venue=None, doi=None,
        url=None, providers=("crossref",), citation_counts={}, open_access=None,
        retraction_status="unknown", scope="metadata_only")
    rendered = _rendered(bare)
    assert rendered.count("غير مذكور") >= 3
    assert "DOI: غير مذكور" in rendered

    # وكلُّ مرجعٍ يصير كتلةَ سياقٍ يعرفها المنسّق — فلا يحجب الحاجزُ ما
    # جلبناه بأنفسنا، ولا يُسند إليها معرّفٌ داخليّ يوحي بصفٍّ محفوظ.
    rows = _evidence_rows([bare])
    assert rows and rows[0]["doi"] is None
    assert rows[0]["source_locator"] == "crossref"
    assert "غير مذكور" in rows[0]["statement_ar"]


def test_the_scope_sentence_names_the_indexes_it_was_given():
    from athera_api.services import ai_policy

    text = ai_policy.literature_scope_notice("ar", ("crossref", "openalex"))
    assert "crossref" in text and "openalex" in text
    assert "لا يعني" in text, "الجملة لا تقول إنّ الغياب ليس نفيًا"
    # والأسماء مشتقّة: فهرسٌ ثالث يظهر بلا سطرٍ يُحدَّث باليد.
    assert "zenodo" in ai_policy.literature_scope_notice("ar", ("zenodo",))


def load_first_crossref() -> dict:
    from tests.discovery_boundary import load

    return load("crossref_search.json")["message"]["items"][0]


# ═════════════════ العقد على السلك ═════════════════

def test_the_ask_contract_carries_the_state_the_screen_needs():
    from athera_api.schemas.ai import AiAskResponse

    fields = set(AiAskResponse.model_fields)
    assert {"intent", "search_performed", "capabilities", "references",
            "provider_statuses", "project"} <= fields


def test_the_router_still_holds_every_scientific_guard_it_had():
    """**ولا حدٌّ قديم يسقط في تغييرٍ جديد.** الفحص هنا فحصُ انحدار."""
    from athera_api.routers import ai

    source = inspect.getsource(ai.ask)
    for guard in ('candidate.status == "approved"',
                  'memory.verification_status == "verified"',
                  "FactCandidate.file_id == record.id",
                  "File.tenant_id == principal.tenant_id",
                  "لم تُقرأ محتوياته بعد",
                  "معالجة المستند",
                  'classification = "C1"',
                  'classification = "C2"',
                  "input_classification=classification",
                  "consent.chat_authorization",
                  "document_context = []",
                  "strip_markup("):
        assert guard in source, guard
    # ولا مقاطع ولا نصّ خام — قبل الإذن ولا بعده.
    assert "DocumentChunk" not in source
    assert "storage.get" not in source


def test_the_router_never_commits_its_own_transaction():
    """`tenant_session` تفتح المعاملة وتختمها. و`session.commit()` في معالجٍ
    ثم قراءةٌ بالجلسة نفسها ترفع `InvalidRequestError` — خمسمئة صريحة."""
    source = (API / "routers" / "ai.py").read_text(encoding="utf-8")
    assert "session.commit()" not in source


# ═════════════════ ٨. شاشة أثيرا AI ═════════════════
#
# **والفحص على المصدر لا على المتصفّح** — كما تفعل بقيّة حرّاس الواجهة في
# هذا المستودع؛ يعمل في كل PR، ولا يُستبدل بفحص المتصفّح بل يسبقه.

WEB = pathlib.Path(__file__).resolve().parents[3] / "apps" / "web"


def _ts(rel: str) -> str:
    from tests.tsscan import code_lines

    raw = (WEB / "src" / rel).read_text(encoding="utf-8")
    return "\n".join(text for _, text in code_lines(raw))


def test_the_ai_screen_shows_no_infrastructure_diagnostics():
    """**سطحُ عمل الباحث ليس لوحةَ عمليات.**

    كانت الصفحة تُنهي نفسها بشبكةِ بطاقات `settings/posture`: اسمُ مزوّد
    النموذج، وحالُ تخزين S3، وسقفُ تصنيف البيانات C1، والرصدُ المجدول.
    وذلك شأنُ من ينشر الخادم — ومكانه شاشةُ الإعدادات. والباحثُ يقرؤه
    فيظنّ أنّ عليه ضبط شيءٍ قبل أن يسأل سؤاله.
    """
    code = _ts("app/[locale]/ai/page.tsx")
    assert "items.map" not in code, "بطاقاتُ وضع التشغيل ما زالت في وجه الباحث"
    assert 'item.value === "null"' not in code
    assert "gateCheck" not in code, "عنوانُ «حالة التشغيل الحيّة» ما زال معروضًا"
    # والبوابة نفسها تبقى مقروءة من الخادم — أُزيل العرض لا القراءة.
    assert "modelEnabled" in code


def test_the_ai_screen_reads_its_capabilities_from_the_ai_route():
    """قدرةٌ تُقرأ من مصدرها لا تُستنتج من بطاقةِ بنيةٍ تحتية."""
    code = _ts("app/[locale]/ai/page.tsx")
    assert "useAiCapabilities" in code
    assert "/api/v1/ai/capabilities" in _ts("lib/aiCapabilities.ts")
    # والثلاثيةُ تُقرأ بأطرافها الثلاثة: «جارٍ» و«جاهز» و«تعذّر السؤال».
    for state in ('phase === "loading"', 'phase === "failed"', 'phase === "ready"'):
        assert state in code, state


def test_the_ai_screen_carries_the_project_it_was_handed():
    code = _ts("app/[locale]/ai/page.tsx")
    assert 'get("project")' in code, "سياقُ البحث لا يُقرأ من الرابط"
    assert "projectId={projectId}" in code
    assert "project_id: projectId" in _ts("components/AtheraAiInput.tsx")
    # ويُعرض للباحث: سياقٌ يُرسل ولا يُرى سياقٌ لا يعرفه صاحبه.
    assert 'data-testid="ai-project-context"' in _ts("components/AiAnswer.tsx")


def test_the_search_results_are_actionable_and_keep_their_attribution():
    """**نتيجةٌ لا يُفعل بها شيء ليست نتيجة.** والحفظُ بمعرّفٍ شرعي وحده."""
    card = _ts("components/AiAnswer.tsx")
    assert 'data-testid="ai-references"' in card
    assert "citation_counts" in card, "العدّاد لا يُعرض منسوبًا"
    assert "one.providers.join" in card, "الفهرسُ القائل لا يُذكر"
    # الرابط يُقرأ من النصّ الخام: ماسحُ التعليقات يقصّ عند `//`، وهو جزءٌ
    # من العنوان لا تعليقٌ فيه.
    raw_card = (WEB / "src" / "components" / "AiAnswer.tsx").read_text(encoding="utf-8")
    assert "doi.org/" in raw_card, "المعرّف يُعرض بلا رابطٍ يُفتح"
    assert "one.can_be_saved && doi && onSave" in card, \
        "زرُّ حفظٍ يُعرض لمرجعٍ لا يُحفظ"
    assert "/api/v1/sources/import" in _ts("components/AtheraAiInput.tsx"), \
        "زرُّ الحفظ لا ينادي شيئًا"


def test_a_search_result_is_never_labelled_verified_on_the_screen():
    card = _ts("components/AiAnswer.tsx")
    assert 'evidence_state === "search_results" ? t("ai.evidenceSearch")' in card
    ar = (WEB / "messages" / "ar.json").read_text(encoding="utf-8")
    assert "نتائج بحث في الفهارس — لا دليل موثّق" in ar


# ═════════════════ القبول عبر HTTP بهويّةٍ حقيقية ═════════════════
#
# **الخدمةُ تُستدعى مباشرةً في الفحوص أعلاه، والباحث لا يستدعيها.** بينه
# وبينها موجّهٌ ومصادقةٌ وجلسةُ مستأجرٍ وصلاحية.


class _FakeModel:
    """مزوّد نموذجٍ وهميّ — بلا شبكة وبلا مفتاح."""

    name = "fake"

    def __init__(self, text="اقتراح منهجي."):
        self._text = text
        self.seen: list = []

    async def generate_structured(self, request):
        from athera_api.providers.base import ModelResponse, ModelUsage

        self.seen.append(request)
        return ModelResponse(
            content=self._text, provider="fake", model="fake-1",
            structured={"answer_ar": self._text, "citations": [],
                        "unsupported_claims": [], "evidence_gaps": []},
            usage=ModelUsage(input_tokens=10, output_tokens=10, latency_ms=1),
        )

    async def embed(self, texts, *, model=None): return [[0.0] * 4 for _ in texts]
    async def stream(self, request): yield self._text
    async def tool_call(self, request): return await self.generate_structured(request)


def _use_model(monkeypatch, model):
    import importlib.util

    from athera_api.config import get_settings
    from athera_api.providers import gateway

    settings = get_settings()
    monkeypatch.setattr(settings, "model_provider", "openai", raising=False)
    monkeypatch.setattr(settings, "openai_api_key", "test-only-not-a-real-key",
                        raising=False)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(gateway, "build_provider", lambda: model)
    return model


def _client(tenant_id, user_id):
    """عميلٌ يحمل رمزًا حقيقيًّا — لا تجاوزَ للمصادقة في فحصٍ يدّعي إثباتها."""
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    token = issue_access_token(user_id=user_id, tenant_id=tenant_id,
                               roles=["researcher"], mfa_satisfied=True)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": "ar"})


@pytest.fixture(autouse=True)
def _clean_limits():
    from athera_api.discovery import throttle
    from athera_api.services import ai_rate_limit

    ai_rate_limit.reset()
    throttle.reset()
    yield
    ai_rate_limit.reset()
    throttle.reset()


async def _seed_project(tenant_id, user_id, *, title="أثر التدريب في الأداء"):
    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ResearchProject

    async with tenant_session(tenant_id, user_id) as session:
        project = ResearchProject(tenant_id=tenant_id, working_title_ar=title,
                                  status="planned")
        session.add(project)
        await session.flush()
        return project.id


async def _seed_approved_document(tenant_id, user_id, *, statement):
    """ملفٌّ عولج، ومعرفةٌ اعتمدها الباحث وتحقّق منها — بلا إذن محادثة بعد."""
    from athera_api.db import tenant_session
    from athera_api.models.files import File
    from athera_api.models.research import (
        DocumentChunk,
        ExtractionRun,
        FactCandidate,
        ResearcherMemory,
    )

    now = _now()
    async with tenant_session(tenant_id, user_id) as session:
        record = File(tenant_id=tenant_id, storage_key=f"t/{uuid.uuid4()}",
                      original_filename="study.pdf", content_type="application/pdf",
                      size_bytes=2048, checksum_sha256="0" * 64, classification="C2",
                      status="stored", uploaded_by=user_id)
        session.add(record)
        await session.flush()

        run = ExtractionRun(tenant_id=tenant_id, file_id=record.id, extractor="rules",
                            status="completed", started_at=now)
        chunk = DocumentChunk(tenant_id=tenant_id, file_id=record.id, seq=1,
                              text=statement, locator="ص1 §1 ¶1",
                              char_count=len(statement))
        memory = ResearcherMemory(
            tenant_id=tenant_id, memory_category="project_decision",
            statement_ar=statement, source_type="upload", source_file_id=record.id,
            source_locator="ص1 §1 ¶1", source_quote=statement,
            verification_status="verified", verified_by=user_id, verified_at=now)
        session.add_all([run, chunk, memory])
        await session.flush()

        session.add(FactCandidate(
            tenant_id=tenant_id, extraction_run_id=run.id, file_id=record.id,
            chunk_id=chunk.id, memory_category="project_decision",
            field_key="design", statement_ar=statement, quote=statement,
            locator="ص1 §1 ¶1", status="approved", decided_by=user_id,
            decided_at=now, resulting_memory_id=memory.id))
        await session.flush()
        return record.id


@requires_db
@pytest.mark.asyncio
async def test_an_explicit_literature_request_reaches_a_real_provider(
    two_tenants, monkeypatch,
):
    """**أثرٌ حقيقي، لا تأكيدٌ غير مباشر.** الدليل أنّ الفهرسين نُوديا فعلًا،
    وأنّ ما عاد يحمل نسبته."""
    _use_model(monkeypatch, _FakeModel())
    calls = stub_indexes(monkeypatch)
    a = two_tenants["a"]

    async with _client(a["tenant_id"], a["user_id"]) as http:
        response = await http.post("/api/v1/ai/ask", json={
            "question": "ابحث لي في الأدبيات عن التحول الرقمي في التعليم العالي",
        })
    assert response.status_code == 200, response.text
    body = response.json()

    # ① النداء وقع — على الفهرسين معًا لا على أوّل من ردّ.
    assert calls["crossref"] and calls["openalex"], calls
    assert body["search_performed"] is True
    assert body["intent"] == "literature_search"

    # ② والنتائج مسوّاة ونسبتها محفوظة.
    assert body["references"], "لم تعد أي مراجع"
    for found in body["references"]:
        assert found["title"] and found["providers"], found
        # ولا حقلَ يُملأ استنتاجًا: «يُحفظ» مشتقّةٌ من وجود معرّفٍ شرعي.
        assert found["can_be_saved"] is bool(found["doi"])
        assert set(found["citation_counts"]) <= {"crossref", "openalex"}
        # ولا `full_text` من نداءٍ ببليوغرافي بحال.
        assert found["scope"] in ("metadata_only", "abstract_only")
    assert any(found["doi"] for found in body["references"]), "لا معرّف شرعي في أي نتيجة"
    assert {status["provider"] for status in body["provider_statuses"]} == \
        {"crossref", "openalex"}

    # ③ ونتيجةُ بحثٍ ليست دليلًا موثّقًا.
    assert body["evidence_state"] == "search_results"

    # ④ ولا يُطلب إذنٌ لفعلٍ طُلب صراحةً.
    everything = " ".join(body["limitations"] + body["recommended_next_actions"])
    assert "هل تريد" not in everything and "أتريد" not in everything


@requires_db
@pytest.mark.asyncio
async def test_the_discovered_references_reach_the_model_and_bound_it(
    two_tenants, monkeypatch,
):
    """**والقيدُ يُقال للنموذج، لا يُصحَّح بعده.** منعُ الاختلاق عند مصدره
    أرخص من كشفه بعد أن يُكتب في ورقة."""
    model = _use_model(monkeypatch, _FakeModel())
    stub_indexes(monkeypatch)
    a = two_tenants["a"]

    async with _client(a["tenant_id"], a["user_id"]) as http:
        await http.post("/api/v1/ai/ask", json={
            "question": "ابحث لي عن دراسات في التحول الرقمي في التعليم",
        })

    request = model.seen[0]
    user_text = " ".join(m.content for m in request.messages if m.role == "user")
    system_text = " ".join(m.content for m in request.messages if m.role == "system")
    assert "10.1016/j.jbusres.2020.06.008" in user_text.lower(), "المراجع لم تصل النموذج"
    # وهي بياناتٌ لا تعليمات: نصُّ فهرسٍ خارجيّ لا يدخل دور `system` (§33.3).
    assert "10.1016" not in system_text
    # والقيدُ عليها قولُنا نحن، فمكانه `system`.
    assert "لا تخترع مرجعًا" in system_text
    assert "نتائجُ بحثٍ لا أدلّةٌ متحقَّقة" in system_text
    # والسقف لم يُرفع: بياناتٌ ببليوغرافية عامّة تبقى C1.
    assert request.classification == "C1"


@requires_db
@pytest.mark.asyncio
async def test_a_doi_we_supplied_is_not_blocked_as_a_fabrication(
    two_tenants, monkeypatch,
):
    """**العطبُ الذي كان سيشحن ٤٢٢ لكل طلب أدبيات.**

    `citations_must_be_grounded` يرفض كلّ DOI ليس في مجموعة الأدلة،
    ومجموعتُها كانت تُبنى من مخرَجات الأدوات وحدها. فالنموذج يذكر معرّفًا
    أعطيناه إيّاه قبل سطرين، فيُحجب مخرَجه كأنه اختلقه — والباحث يرى خطأً
    لا يفهمه بعد بحثٍ نجح.

    **ولا يُضعَف الحاجز**: معرّفٌ لم نجلبه يبقى محجوبًا.
    """
    from athera_api.brain.guardrails import GuardContext, citations_must_be_grounded
    from athera_api.routers.ai import _evidence_rows
    from athera_api.services.reference_discovery import DiscoveredReference

    supplied = "10.1016/j.jbusres.2020.06.008"
    model = _use_model(monkeypatch, _FakeModel(
        text=f"من نتائج البحث ورقةٌ بمعرّف {supplied} تناولت الموضوع."))
    stub_indexes(monkeypatch)
    a = two_tenants["a"]

    async with _client(a["tenant_id"], a["user_id"]) as http:
        response = await http.post("/api/v1/ai/ask", json={
            "question": "ابحث لي في الأدبيات عن التحول الرقمي في التعليم",
        })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok", body
    assert supplied in body["answer"]

    # ① الحاجز مرّ لأن المعرّف كان في مجموعة الأدلة المجلوبة.
    allowed = {row["doi"] for row in _evidence_rows([DiscoveredReference(
        title="T", authors=(), year=None, venue=None, doi=supplied, url=None,
        providers=("crossref",), citation_counts={}, open_access=None,
        retraction_status="unknown", scope="metadata_only")]) if row["doi"]}
    ctx = GuardContext(allowed_evidence_ids=frozenset(), allowed_dois=frozenset(allowed),
                       analysis_run_ids=frozenset())
    assert citations_must_be_grounded(f"ورقة {supplied}", ctx) is None
    # ② ومعرّفٌ لم نجلبه ما يزال محجوبًا — الحاجز لم يُضعَف.
    assert citations_must_be_grounded("ورقة 10.9999/invented.doi", ctx) is not None

    # ③ ومع ذلك: نتيجةُ بحثٍ ليست دليلًا موثّقًا مهما استشهد النموذج.
    assert body["evidence_state"] == "search_results"
    assert model.seen


@requires_db
@pytest.mark.asyncio
async def test_a_general_question_never_claims_the_search_is_disabled(
    two_tenants, monkeypatch,
):
    """**العطبُ الأصلي، من طرف الباحث.** كان يُقال «البحث الخارجي غير مفعّل»
    في كل رد، والبحثُ يعمل."""
    _use_model(monkeypatch, _FakeModel())
    calls = stub_indexes(monkeypatch)
    a = two_tenants["a"]

    async with _client(a["tenant_id"], a["user_id"]) as http:
        body = (await http.post("/api/v1/ai/ask", json={
            "question": "أريد دراسة أثر الذكاء الاصطناعي في الاتصال التسويقي.",
        })).json()

    assert body["search_performed"] is False
    assert not calls["crossref"] and not calls["openalex"], "نداءٌ خارجيّ بلا طلب"
    joined = " ".join(body["limitations"])
    # ① يُقال إنّ بحثًا لم يُجرَ…
    assert "لم يُجرَ بحثٌ خارجيّ عن المراجع" in joined
    # ② …ولا يُقال إنّ القدرة معطّلة وهي قائمة.
    assert "غير مفعّل" not in joined and "غير متاح" not in joined
    assert body["capabilities"]["reference_discovery_available"] is True


@requires_db
@pytest.mark.asyncio
async def test_a_deployment_without_indexes_says_so_and_does_not_pretend(
    two_tenants, monkeypatch,
):
    """والحالُ الثالثة تُعلَن: لا فهارس ≠ لا نتائج ≠ تعذّر فهرس."""
    _use_model(monkeypatch, _FakeModel())
    no_indexes(monkeypatch)
    a = two_tenants["a"]

    async with _client(a["tenant_id"], a["user_id"]) as http:
        body = (await http.post("/api/v1/ai/ask", json={
            "question": "ابحث لي في الأدبيات عن القيادة التحويلية",
        })).json()

    assert body["search_performed"] is False
    assert body["capabilities"]["reference_discovery_available"] is False
    assert any("غير متاح" in line for line in body["limitations"])


@requires_db
@pytest.mark.asyncio
async def test_the_scope_sentence_is_said_once_not_stacked(two_tenants, monkeypatch):
    """**ثلاثةُ تحذيراتٍ متراكمة تُقرأ اعتذارًا عامًّا فتُتجاهل كلُّها** — بما
    فيها التحذير الذي كان يهمّ."""
    _use_model(monkeypatch, _FakeModel())
    stub_indexes(monkeypatch)
    a = two_tenants["a"]

    async with _client(a["tenant_id"], a["user_id"]) as http:
        body = (await http.post("/api/v1/ai/ask", json={
            "question": "ابحث لي في الأدبيات عن التحول الرقمي في التعليم",
        })).json()

    scope_lines = [line for line in body["limitations"] if "نطاقُ البحث" in line]
    assert len(scope_lines) == 1, body["limitations"]
    # ولا تُقال جملةُ «لم يُبحث» مع جملة «بُحث».
    assert not any("لم يُجرَ" in line for line in body["limitations"])
    assert "لا يعني أنها غير موجودة" in scope_lines[0]


@requires_db
@pytest.mark.asyncio
async def test_an_index_that_did_not_answer_is_named_not_read_as_absence(
    two_tenants, monkeypatch,
):
    """**فهرسٌ لم يُجب ليس فهرسًا قال «لا يوجد».** والخلطُ بينهما يجعل الشاشة
    تكذب في أسوأ لحظة: الشبكة معطوبة والباحث يظنّ موضوعه بكرًا."""
    _use_model(monkeypatch, _FakeModel())
    stub_indexes(monkeypatch, openalex_down=True)
    a = two_tenants["a"]

    async with _client(a["tenant_id"], a["user_id"]) as http:
        body = (await http.post("/api/v1/ai/ask", json={
            "question": "ابحث لي في الأدبيات عن التحول الرقمي في التعليم",
        })).json()

    failed = [s for s in body["provider_statuses"] if not s["ok"]]
    assert [s["provider"] for s in failed] == ["openalex"]
    assert any("openalex" in line for line in body["limitations"])
    assert any("ليس نفيًا" in line for line in body["limitations"])
    # والناجي ما يزال يعرض نتائجه.
    assert body["references"]


@requires_db
@pytest.mark.asyncio
async def test_a_project_question_keeps_its_project_and_its_tenant(
    two_tenants, monkeypatch,
):
    """**والعزلُ يُثبت من الطرفين**: سياقٌ صحيح لصاحبه، و٤٠٤ لغيره."""
    _use_model(monkeypatch, _FakeModel())
    a, b = two_tenants["a"], two_tenants["b"]
    project_id = await _seed_project(a["tenant_id"], a["user_id"],
                                     title="أثر التدريب في الأداء الوظيفي")

    async with _client(a["tenant_id"], a["user_id"]) as http:
        owned = await http.post("/api/v1/ai/ask", json={
            "question": "ما الخطوة التالية في مشروعي البحثي؟",
            "project_id": str(project_id),
        })
    assert owned.status_code == 200, owned.text
    body = owned.json()
    assert body["intent"] == "project"
    assert body["project"]["project_id"] == str(project_id)
    assert body["project"]["working_title"] == "أثر التدريب في الأداء الوظيفي"

    # ومستأجرٌ آخر لا يقرأ منه شيئًا — و٤٠٤ لا «سياقٌ فارغ»: الرد الفارغ
    # يقول للمهاجم إنّ المعرّف صحيح ولا يملكه.
    async with _client(b["tenant_id"], b["user_id"]) as other:
        blocked = await other.post("/api/v1/ai/ask", json={
            "question": "ما الخطوة التالية في مشروعي البحثي؟",
            "project_id": str(project_id),
        })
    assert blocked.status_code == 404, blocked.text
    assert "أثر التدريب" not in blocked.text


@requires_db
@pytest.mark.asyncio
async def test_the_project_title_never_reaches_the_model(two_tenants, monkeypatch):
    """عنوانُ بحثٍ غير منشور معرفةٌ للباحث، وسقفُ الإرسال العام C1."""
    model = _use_model(monkeypatch, _FakeModel())
    a = two_tenants["a"]
    marker = "عنوانٌ سرّيّ لا يغادر المستأجر ٩٩٣١"
    project_id = await _seed_project(a["tenant_id"], a["user_id"], title=marker)

    async with _client(a["tenant_id"], a["user_id"]) as http:
        body = (await http.post("/api/v1/ai/ask", json={
            "question": "ما الخطوة التالية في مشروعي البحثي؟",
            "project_id": str(project_id),
        })).json()

    assert body["project"]["working_title"] == marker, "السياق لم يصل صاحبه"
    everything = " ".join(m.content for m in model.seen[0].messages)
    assert marker not in everything, "عنوان البحث غادر إلى المزوّد"


@requires_db
@pytest.mark.asyncio
async def test_a_full_text_question_refuses_to_over_reach_from_an_abstract(
    two_tenants, monkeypatch,
):
    """**والملخّصُ ليس الورقة.** واستخراجُ إجراءٍ إحصائيّ منه اختلاقٌ بلغةٍ
    واثقة — أخطر من الامتناع، لأنه يُكتب في ورقةٍ تُنشر."""
    model = _use_model(monkeypatch, _FakeModel())
    stub_indexes(monkeypatch)
    a = two_tenants["a"]

    async with _client(a["tenant_id"], a["user_id"]) as http:
        body = (await http.post("/api/v1/ai/ask", json={
            "question": "ابحث عن دراسات في التحول الرقمي واقتبس لي نصًّا حرفيًّا من قسم النتائج",
        })).json()

    assert any("الملخّصُ ليس الورقة" in line for line in body["limitations"])
    # والفعلُ التالي يُعطى، لا يُترك الباحث أمام «لا أستطيع».
    assert any("النصّ الكامل" in action
               for action in body["recommended_next_actions"])
    # والنموذج نفسه أُبلغ الحدّ، فلا يملأ الفراغ.
    system_text = " ".join(m.content for m in model.seen[0].messages
                           if m.role == "system")
    assert "النصّ الكامل" in system_text
    # ومع ذلك جرى البحث الذي طُلب صراحةً.
    assert body["search_performed"] is True


@requires_db
@pytest.mark.asyncio
async def test_the_consent_path_produces_a_new_grounded_answer_not_a_stale_one(
    two_tenants, monkeypatch,
):
    """**العقد العلمي، وأخطر انحدارٍ في هذا المستودع** (D9).

    كان يُقال «مسار الإذن يعمل» بدليل أنّ الرد الثاني ظهر — وهو قد يكون
    الرد الأول نفسه معادًا من ذاكرة. فالدليل هنا ثلاثة:

    ① قبل الإذن: رفضٌ صريح، ولا معلومةٌ من المستند تغادر.
    ② بعد الإذن: جوابٌ **جديد** يختلف عن الرفض نصًّا.
    ③ ومعه أثرُ دليل: معرفةُ الباحث المعتمَدة وصلت المزوّد، والحال `verified`.
    """
    from athera_api.services import storage

    monkeypatch.setattr(storage.get_settings(), "storage_provider", "memory",
                        raising=False)
    storage.reset_store_cache()
    secret = "تصميمُ الدراسة مقطعيٌّ على ٤١٢ مشاركًا في ثلاث جامعات."
    model = _use_model(monkeypatch, _FakeModel(text="جوابٌ مسنودٌ إلى ما اعتمدتَه."))
    a = two_tenants["a"]
    file_id = await _seed_approved_document(a["tenant_id"], a["user_id"],
                                            statement=secret)

    async with _client(a["tenant_id"], a["user_id"]) as http:
        before = (await http.post("/api/v1/ai/ask", json={
            "question": "ما تصميم الدراسة في هذا المستند؟",
            "attachment_file_id": str(file_id),
        })).json()

        # ① الرفضُ صريح، ولا بايت من المعرفة يغادر.
        assert before["attachment"]["needs"] == "chat_consent"
        assert any("إذنك الصريح" in line for line in before["limitations"])
        assert before["evidence_state"] != "verified"
        sent_before = " ".join(m.content for m in model.seen[0].messages)
        assert secret not in sent_before, "معرفةُ المستند غادرت قبل الإذن"

        granted = await http.post(
            f"/api/v1/theses/files/{file_id}/chat-consent?decision=grant")
        assert granted.status_code == 200, granted.text

        after = (await http.post("/api/v1/ai/ask", json={
            "question": "ما تصميم الدراسة في هذا المستند؟",
            "attachment_file_id": str(file_id),
        })).json()

    # ② جوابٌ جديد لا الرفضُ معادًا.
    assert after["answer"] != before["answer"]
    assert after["attachment"]["needs"] == "none"
    assert not any("إذنك الصريح" in line for line in after["limitations"])

    # ③ وأثرُ الدليل: نداءُ مزوّدٍ ثانٍ حمل المعرفة المعتمَدة، بسقفٍ مرفوع
    #    لهذا النداء وحده.
    assert len(model.seen) >= 2, "لم يقع نداءٌ ثانٍ — الرد الثاني مُعاد لا مُولَّد"
    last = model.seen[-1]
    assert secret in " ".join(m.content for m in last.messages)
    assert last.classification == "C2"
    assert after["evidence_state"] == "verified"
    assert after["model_run_id"], "لا أثر تشغيلٍ للجواب المسنود"
    storage.reset_store_cache()


@requires_db
@pytest.mark.asyncio
async def test_the_capabilities_screen_shows_no_infrastructure_internals(
    two_tenants, monkeypatch,
):
    """**شاشةُ الباحث ليست لوحةَ عمليات.** اسمُ المزوّد وحالُ S3 وسقفُ C1
    تشخيصُ بنيةٍ تحتية لمن ينشر الخادم، لا لمن جاء ليكتب ورقة."""
    _use_model(monkeypatch, _FakeModel())
    stub_indexes(monkeypatch)
    a = two_tenants["a"]

    async with _client(a["tenant_id"], a["user_id"]) as http:
        response = await http.get("/api/v1/ai/capabilities")
    assert response.status_code == 200, response.text
    raw = response.text
    body = response.json()

    assert body["assistant_available"] is True
    assert body["reference_discovery_available"] is True
    assert "crossref" in body["reference_discovery_providers"]
    for internal in ("anthropic", "openai", "s3", "storage_provider",
                     "C1", "C2", "api_key", "not_configured"):
        assert internal not in raw, internal


@requires_db
@pytest.mark.asyncio
async def test_the_ask_route_requires_a_real_bearer_token():
    import httpx

    from athera_api.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as anon:
        blocked = await anon.post("/api/v1/ai/ask",
                                  json={"question": "سؤال بحثي كافٍ الطول"})
        caps = await anon.get("/api/v1/ai/capabilities")
    assert blocked.status_code == 401
    assert caps.status_code == 401
