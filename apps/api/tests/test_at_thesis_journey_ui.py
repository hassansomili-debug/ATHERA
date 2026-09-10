"""واجهةُ الرحلة | Thesis journey UI — مثبَّتةٌ إلى العقد لا مكتوبةٌ بيد.

**والدرسُ من `NO_EVIDENCE_AR`.** تجهيزةٌ تحمل نسخةً ثانية من نصٍّ أو مفردةٍ
تنجرف عن الأصل بلا أن يسقط شيء: أربعُ مرّاتٍ وقع ذلك في هذا المستودع، ونجت
مرّتان من كنسٍ سالب. فما يُفحص هنا **يُستخرَج من المصدر** ويُقارَن به، ولا
يُعاد كتابتُه.

وTypeScript لا يُصرَّف على هذا الجهاز — لا Node ولا typecheck. فهذه الفحوصُ
حدُّ ما يمكن إثباتُه: تطابقُ المفردات، واكتمالُ الترجمة، وخلوُّ النصّ من
مفردات النظام. **وما عداها غيرُ مُتحقَّق منه، ويُقال كذلك.**
"""
from __future__ import annotations

import ast
import inspect
import json
import pathlib
import re

from athera_api.services.thesis import journey


def _web() -> pathlib.Path:
    return pathlib.Path(inspect.getfile(journey)).resolve().parents[5] / "apps/web"


def _component() -> str:
    return (_web() / "src/components/ThesisJourney.tsx").read_text(encoding="utf-8")


def _messages(locale: str) -> dict:
    return json.loads((_web() / f"messages/{locale}.json").read_text(encoding="utf-8"))


# ══════════ ١. الخريطةُ مثبَّتةٌ إلى مفردات الخادم ══════════


def test_every_server_state_is_mapped_to_a_step():
    """**الدعوى الأهمّ في هذه الشريحة.**

    حالٌ يُصدرها الخادمُ ولا تعرفها الشاشةُ تُعرض في غير موضعها؛ وحالٌ
    تعرفها الشاشةُ ولا يُصدرها الخادمُ خريطةٌ ميّتة. فالمجموعتان تتطابقان،
    والمفرداتُ تُقرأ من الخدمة لا تُكتب هنا.
    """
    source = _component()
    mapped = set(re.findall(r"^\s{2}([a-z_]+):\s*\d,\s*$", source, re.M))
    assert mapped, "لم يُعثر على خريطة الحالات في المكوّن — تغيّر الشكل"

    declared = set(journey.STATES)
    assert declared - mapped == set(), (
        f"حالاتٌ يُصدرها الخادمُ ولا تعرفها الشاشة: {sorted(declared - mapped)}")
    assert mapped - declared == set(), (
        f"حالاتٌ في الشاشة لا يُصدرها الخادم: {sorted(mapped - declared)}")


def test_the_six_steps_are_declared_once():
    source = _component()
    block = source[source.index("const STEP_KEYS"):source.index("] as const")]
    keys = re.findall(r'"([a-z]+)"', block)
    assert keys == ["analysis", "opportunities", "rights", "build",
                    "literature", "studio"], keys


def test_every_blocking_reason_has_researcher_facing_copy():
    """رمزٌ بلا ترجمةٍ يُعرض للباحث كما هو — وهو مفردةُ نظام."""
    declared = {
        journey.BLOCK_NO_CONSENT, journey.BLOCK_STALE_CONSENT,
        journey.BLOCK_NO_SELECTION, journey.BLOCK_OVERLAP,
        journey.BLOCK_RIGHTS, journey.BLOCK_NO_OPPORTUNITY,
        journey.BLOCK_EXTRACTION_FAILED,
    }
    for locale in ("ar", "en"):
        blocked = _messages(locale)["journey"]["blocked"]
        missing = declared - set(blocked)
        assert not missing, f"{locale}: أسبابٌ بلا ترجمة — {sorted(missing)}"


# ══════════ ٢. الترجمةُ كاملةٌ في اللغتين ══════════


def _flatten(node, prefix=""):
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            yield from _flatten(value, path)
        else:
            yield path


def test_arabic_and_english_journey_copy_have_the_same_shape():
    arabic = set(_flatten(_messages("ar")["journey"]))
    english = set(_flatten(_messages("en")["journey"]))
    assert arabic == english, (
        f"ar-only={sorted(arabic - english)} en-only={sorted(english - arabic)}")


def test_every_message_key_the_component_uses_exists():
    """**ومفتاحٌ مفقود يُعرض مسارَه للباحث** — `translator` يعيد المسار."""
    source = _component()
    literal = set(re.findall(r't\("([a-z][A-Za-z.]+)"\)', source))
    templated = {m for m in re.findall(r't\(`journey\.([a-z]+)\.\$\{', source)}

    for locale in ("ar", "en"):
        messages = _messages(locale)
        available = set(_flatten(messages))
        for key in literal:
            assert key in available, f"{locale}: مفتاحٌ مفقود — {key}"
        for group in templated:
            assert group in messages["journey"], f"{locale}: مجموعةٌ مفقودة — {group}"


# ══════════ ٣. لا مفرداتِ نظام، ولا تقدّمٌ مختلَق ══════════


def test_the_researcher_never_reads_system_vocabulary():
    """الباحثُ يقرأ عن رسالته وورقته — لا عن آلةٍ تعمل خلفها."""
    internal = ("FactCandidate", "canonical", "mining", "extraction_run",
                "المنقّب", "استخراج الفرص", "مرشّح واقعة")
    for locale in ("ar", "en"):
        block = json.dumps(_messages(locale)["journey"], ensure_ascii=False)
        for term in internal:
            assert term not in block, f"{locale}: مفردةُ نظامٍ في نصٍّ معروض — {term}"


def test_no_percentage_or_progress_is_ever_rendered():
    """**«٦٠٪ مكتمل» رقمٌ بلا قياسٍ خلفه** — ولا وجود له في المكوّن."""
    source = _component()
    for token in ("percent", "progress", "%\"", "Math.round", "/ STEP_KEYS.length"):
        assert token not in source, f"تقدّمٌ مختلَق في الشاشة: {token}"
    for locale in ("ar", "en"):
        block = json.dumps(_messages(locale)["journey"], ensure_ascii=False)
        assert "%" not in block, f"{locale}: نسبةٌ مئوية في النصّ المعروض"


def test_the_component_states_the_proposal_is_machine_made():
    """**ومقترحُ آلةٍ يُعلن أنّه كذلك** — فلا يُقرأ حكمًا علميًّا."""
    source = _component()
    assert 'data-testid="opportunity-ai-notice"' in source
    for locale, needle in (("ar", "الذكاء الاصطناعي"), ("en", "AI proposal")):
        assert needle in _messages(locale)["journey"]["aiNotice"]


def test_both_ctas_carry_the_required_wording():
    assert _messages("ar")["journey"]["buildCta"] == "بناء هذه الورقة بالذكاء الاصطناعي"
    assert _messages("en")["journey"]["buildCta"] == "Build this paper with AI"
    assert _messages("ar")["journey"]["openStudio"] == "فتح في استوديو الورقة"
    assert _messages("en")["journey"]["openStudio"] == "Open in Paper Studio"


def test_the_first_scientific_decision_has_a_control_of_its_own():
    """**والرحلةُ كانت تطلب فعلًا لا زرَّ له.**

    تقف عند «اختر الورقة التي تريد بناءها»، ولا شيءَ في الشاشة يختار —
    وزرُّ البناء معطَّلٌ أبدًا لأنّ الخادمَ لن يأذن قبل الاختيار.
    """
    source = _component()
    assert 'data-testid="journey-select-opportunity"' in source
    assert "/select`" in source, "الزرُّ لا ينادي نقطةَ الاختيار"
    assert 'opportunity.planning_status !== "selected"' in source, (
        "الشاشةُ لا تقرأ قرارَ الباحث من عموده")
    for locale in ("ar", "en"):
        journey_copy = _messages(locale)["journey"]
        assert journey_copy["selectCta"], f"{locale}: نصُّ الاختيار مفقود"
        assert journey_copy["selecting"], f"{locale}: نصُّ الانتظار مفقود"


def test_the_api_exposes_the_selection_the_card_reads():
    """وحقلٌ تقرؤه الشاشةُ ولا يُصدره الخادمُ عمودٌ فارغٌ في البطاقة."""
    from athera_api.schemas.thesis import OpportunityResponse

    assert "planning_status" in OpportunityResponse.model_fields

    from athera_api.routers import thesis as thesis_router

    builder = inspect.getsource(thesis_router._opportunity_response)  # noqa: SLF001
    assert "planning_status=row.planning_status" in builder


def test_the_studio_link_belongs_to_its_own_card():
    """**ما يخصّ بطاقةً يُعرض في بطاقتها** — درسُ مركز الرسائل نفسه.

    كانت `manuscriptId` حالًا واحدةً للمكوّن، فبناءُ ورقةٍ من بطاقةٍ يجعل
    **كلَّ** البطاقات تعرض «افتح في استوديو الورقة» مشيرةً إلى تلك
    المخطوطة بعينها — فيفتح الباحثُ ورقةً غيرَ التي ضغط عليها.
    """
    source = _component()
    assert "const [manuscripts, setManuscripts]" in source, (
        "المخطوطةُ ما زالت حالًا واحدةً للصفحة")
    assert "manuscriptOf(opportunity.id)" in source
    assert "manuscripts[opportunityId]" in source


def test_the_card_shows_a_real_count_not_a_score():
    """عددُ المُسنَد يُعرض كما هو — ولا يُحوَّل إلى درجةٍ أو نسبة."""
    source = _component()
    assert "opportunity.provenance_count" in source
    assert 'data-testid="opportunity-provenance"' in source


def test_the_build_cta_is_disabled_until_the_server_allows_it():
    """**والزرُّ يتبع الخادم** — لا تجتهد الشاشةُ في البوّابات."""
    source = _component()
    assert "journey?.can_build_paper === true" in source
    assert "disabled={!canBuild" in source
    for gate in ("overlap_unresolved", "rights_passed", "ai_consent_granted"):
        assert gate not in source, f"منطقُ بوّابةٍ أُعيد في الشاشة: {gate}"


def test_the_component_parses_as_balanced_source():
    """TypeScript لا يُصرَّف هنا؛ فهذا أضعفُ ما يمكن قوله — ويُقال بضعفه."""
    source = _component()
    for opener, closer in (("{", "}"), ("(", ")"), ("[", "]")):
        stripped = re.sub(r'"(?:[^"\\]|\\.)*"', '""', source)
        stripped = re.sub(r"`(?:[^`\\]|\\.)*`", "``", stripped)
        stripped = re.sub(r"//[^\n]*", "", stripped)
        stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.S)
        assert stripped.count(opener) == stripped.count(closer), f"{opener}{closer}"


def test_the_api_exposes_the_provenance_count_the_card_reads():
    """وحقلٌ تقرؤه الشاشةُ ولا يُصدره الخادمُ عمودٌ فارغٌ في البطاقة."""
    from athera_api.schemas.thesis import OpportunityResponse

    assert "provenance_count" in OpportunityResponse.model_fields

    from athera_api.routers import thesis as thesis_router

    builder = inspect.getsource(thesis_router._opportunity_response)  # noqa: SLF001
    assert "provenance_count=sum(" in builder, "العدُّ لا يُملأ من الصفّ"
    tree = ast.parse(builder.strip())
    assert "result_refs" in ast.unparse(tree)
    assert "sample_refs" in ast.unparse(tree)
    assert "variable_refs" in ast.unparse(tree)
