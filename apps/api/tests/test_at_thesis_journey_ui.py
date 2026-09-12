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

    كانت تقف عند «اختر الورقة التي تريد بناءها» ولا شيءَ في الشاشة يختار.
    ثمّ صار للاختيار زرٌّ وللبناء زرٌّ آخر، فيمرّ الباحثُ بلوحةٍ وسيطة.

    **والفعلُ الرئيسُ واحدٌ الآن: «ابدأ هذه الورقة».** يختار إن لم تكن
    مختارة، ثمّ يبني. والقرارُ العلميُّ يُسجَّل بنقطة النهاية نفسِها —
    ولا يُفترض: الباحثُ هو من نقر.
    """
    source = _component()
    assert 'data-testid="journey-start-paper"' in source
    assert "/select`" in source, "الفعلُ لا ينادي نقطةَ الاختيار"
    assert "/build-paper`" in source, "الفعلُ لا ينادي نقطةَ البناء"
    assert 'opportunity.planning_status === "selected"' in source, (
        "الشاشةُ لا تقرأ قرارَ الباحث من عموده")
    for locale in ("ar", "en"):
        journey_copy = _messages(locale)["journey"]
        assert journey_copy["startPaper"], f"{locale}: نصُّ الفعل الرئيس مفقود"
        assert journey_copy["starting"], f"{locale}: نصُّ الانتظار مفقود"


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


def test_the_screen_never_recomputes_a_gate_the_server_owns():
    """**والشاشةُ تتبع الخادم** — لا تجتهد في البوّابات.

    وهذه هي الدعوى الباقية. **وقد سقط شطرٌ منها عمدًا**: كان الفعلُ
    الرئيسُ يُعطَّل بـ`!canBuild`، فيقف الباحثُ أمام زرٍّ مطفأٍ بلا مخرج
    — والحقوقُ والإذنُ كانا يطفئانه وهما لا يمسّان ما يفعله.

    فصار ما يلزم لما هو أبعد يُقال نصًّا ومعه سببُه، **ورمزُه يُقرأ من
    الخادم** (`blocking_reasons`) لا يُعاد حسابُه من الوقائع.
    """
    source = _component()
    # الرمزُ يُقرأ من الخادم كما أرسله.
    assert 'blocking_reasons.includes(\n    "rights_gate_not_passed")' in source \
        or '"rights_gate_not_passed"' in source
    assert "journey?.blocking_reasons" in source
    # **ولا منطقَ بوّابةٍ يُعاد في الشاشة** — وهذا ما لم يتغيّر.
    for gate in ("overlap_unresolved", "rights_passed", "ai_consent_granted"):
        assert gate not in source, f"منطقُ بوّابةٍ أُعيد في الشاشة: {gate}"
    for locale in ("ar", "en"):
        journey_copy = _messages(locale)["journey"]
        assert journey_copy["rightsCta"], f"{locale}: نصُّ استكمال الحقوق مفقود"
        assert journey_copy["rightsWhy"], f"{locale}: سببُ لزوم الحقوق مفقود"


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


# ══════════ ٤. المسارُ المقصود موجودٌ فعلًا ══════════
#
# **وزرٌّ يقصد مسارًا لا صفحةَ له عطبٌ كامل.** كان أوّلُ فعلٍ بعد بناء
# الورقة يقصد `‎/{locale}/manuscripts/{id}` — ولا `page.tsx` هناك، فيبلغ
# الباحثُ ٤٠٤. والفحصُ السابق كان يثبّت النصَّ المعروض على الزرّ ولا يسأل
# **أين يذهب** — فنجا العطبُ مرّتين تحت فحصٍ أخضر.
#
# فيُحلّ المسارُ هنا على شجرة موجّه Next نفسها: مقطعٌ حرفيّ يقابله مجلّد،
# ومقطعٌ متغيّر يقابله مجلّدٌ بين قوسين معقوفين، والنهايةُ `page.tsx`.


def _app() -> pathlib.Path:
    return _web() / "src/app"


def _route_resolves(segments: list[str]) -> bool:
    """أيَبلغ هذا المسارُ صفحةً حقيقية في موجّه Next؟"""
    current = _app()
    for segment in segments:
        if (current / segment).is_dir():
            current = current / segment
            continue
        # مقطعٌ متغيّر (`${...}`) يقابله مجلّدٌ متغيّر واحد.
        dynamic = sorted(
            p for p in current.iterdir() if p.is_dir() and p.name.startswith("["))
        if len(dynamic) != 1:
            return False
        current = dynamic[0]
    return (current / "page.tsx").exists()


def _manuscript_targets() -> list[tuple[str, str]]:
    """كلُّ رابطٍ يقصد مخطوطةً في الواجهة — بملفّه، لا في هذا المكوّن وحده."""
    found: list[tuple[str, str]] = []
    for path in sorted((_web() / "src").rglob("*.tsx")):
        source = path.read_text(encoding="utf-8")
        for target in re.findall(r"href=\{`([^`]*)`\}", source):
            if "manuscripts" in target:
                found.append((str(path.relative_to(_web())), target))
    return found


def test_the_route_resolver_would_catch_the_bug_it_was_written_for():
    """**وحارسٌ لا يعضّ حارسٌ ميّت.**

    فيُجرَّب على المسار المعطوب بعينه — `‎/{locale}/manuscripts/{id}` بلا
    `‎/studio` — ويجب أن يُرفض. ويُجرَّب على الصحيح فيُقبل.
    """
    broken = ["${locale}", "manuscripts", "${manuscriptId}"]
    assert not _route_resolves(broken), (
        "المُحلِّل يقبل مسارًا لا صفحةَ له — فهو بلا أثر")
    assert _route_resolves([*broken, "studio"]), (
        "المُحلِّل يرفض مسارَ الاستوديو الحقيقيّ — فهو يكذب")


def test_the_paper_studio_cta_targets_the_real_studio_route():
    """**الدعوى المركزية في هذا الإصلاح.**

    أوّلُ فعلٍ يلقاه الباحثُ بعد بناء ورقته يجب أن يبلغ الاستوديو، لا ٤٠٤.
    """
    source = _component()
    target = next(
        t for f, t in _manuscript_targets()
        if f.endswith("ThesisJourney.tsx"))

    assert target.endswith("/studio"), (
        f"زرُّ الاستوديو يقصد «{target}» — وليس مسارَ الاستوديو")
    assert 'data-testid="journey-open-studio"' in source
    assert _route_resolves([s for s in target.split("/") if s]), (
        f"مسارُ «{target}» لا يبلغ `page.tsx` — الزرُّ يقود إلى ٤٠٤")


def test_no_manuscript_cta_anywhere_points_at_a_route_that_does_not_exist():
    """**ولا زرَّ مخطوطةٍ واحدٍ يقصد صفحةً غير موجودة** — في الواجهة كلِّها."""
    targets = _manuscript_targets()
    assert targets, "لم يُعثر على أيّ رابطِ مخطوطة — تغيّر الشكل، والفحصُ أعمى"

    dead = [
        f"{file}: {target}" for file, target in targets
        if not _route_resolves([s for s in target.split("/") if s])
    ]
    assert dead == [], "روابطُ مخطوطاتٍ تقصد صفحاتٍ غير موجودة:\n" + "\n".join(dead)


# ══════════ ٥. الخيطُ الذهبيّ فعلٌ في الرحلة ══════════
#
# **وفعلٌ لا تعرفه الشاشةُ فعلٌ لا يقع.** كانت `build_thread` مكتوبةً
# ومفحوصةً ولها نقطةُ نهاية، ولا شيءَ في الرحلة ينادِيها — فالباحثُ إمّا
# يكتشف الـAPI بنفسه، أو يبقى `thread_ready` حالًا لا تقع أبدًا.


def _studio_page() -> str:
    return (_web() / "src/app/[locale]/manuscripts/[manuscriptId]/studio/page.tsx"
            ).read_text(encoding="utf-8")


def _section_workspace() -> str:
    return (_web() / "src/components/SectionWorkspace.tsx").read_text(encoding="utf-8")


def test_the_golden_thread_has_a_control_in_the_journey_itself():
    """**ولا يُطلب من الباحث أن يزور شاشةً أخرى ويجمع مشروعَه بنفسه.**"""
    source = _component()
    assert 'data-testid="journey-build-thread"' in source, "لا زرَّ للخيط الذهبيّ"
    assert "/thread`" in source, "الزرُّ لا ينادي نقطةَ بناء الخيط"
    assert "function buildThread" in source
    # وحالُ «قائمٌ» تُعلَن، فلا يُخفى الخيطُ حتى يُكتشف.
    assert 'data-testid="journey-thread-ready"' in source


def test_the_thread_endpoint_the_screen_calls_is_the_one_that_exists():
    """**ومسارٌ تكتبه الشاشةُ بيدها ينحرف عن الخادم بأوّل تعديل.**"""
    from athera_api.routers import thesis as thesis_router

    routes = {
        getattr(route, "path", "") for route in thesis_router.router.routes
    }
    assert "/api/v1/theses/{thesis_id}/opportunities/{opportunity_id}/thread" in routes, (
        "نقطةُ بناء الخيط غير معلَنة في الموجّه")
    source = _component()
    assert "/api/v1/theses/${thesisId}/opportunities/${opportunityId}/thread" in source


def test_the_thread_cta_follows_the_server_gate_and_reimplements_nothing():
    """**والشاشةُ لا تجتهد في البوّابات** — تقرأ حكمَ الخادم وتعرضه."""
    source = _component()
    assert "journey?.can_build_thread === true" in source
    assert "disabled={!canBuildThread" in source
    for gate in ("overlap_unresolved", "rights_passed", "ai_consent_granted"):
        assert gate not in source, f"منطقُ بوّابةٍ أُعيد في الشاشة: {gate}"


def test_the_stale_consent_reason_reaches_the_researcher_in_words():
    """بياتُ البصمة رمزٌ من الخادم — **وله نصٌّ في اللغتين**، لا يُعرض كما هو."""
    from athera_api.services.thesis import journey as j

    for locale in ("ar", "en"):
        blocked = _messages(locale)["journey"]["blocked"]
        assert j.BLOCK_STALE_CONSENT in blocked
        assert j.BLOCK_NO_CONSENT in blocked
    # والقائمةُ تُعرض فعلًا فوق البطاقات.
    assert 'data-testid="journey-blocked"' in _component()
    assert "t(`journey.blocked.${reason}`)" in _component()


# ══════════ ٦. الاستوديو يستعمل مساحةَ القسم القائمة، ولا يبني ثانية ══════════


def test_the_studio_mounts_the_existing_section_workspace():
    """**ولا تطبيقَ صياغةٍ ثانٍ.** المساحةُ القائمة تحمل الإذنَ والبصمة."""
    studio = _studio_page()
    assert 'import { SectionWorkspace } from "@/components/SectionWorkspace"' in studio
    assert "<SectionWorkspace" in studio
    # والاستوديو لا ينادي نقطةَ الصياغة بنفسه — المساحةُ وحدها تفعل.
    assert "/draft`" not in studio, "الاستوديو يبني صياغةً ثانية بجانب المساحة"


def test_the_drafting_flow_keeps_its_three_existing_steps():
    """السياقُ، ثمّ الإذنُ المربوط ببصمته، ثمّ الصياغة — **بلا دفعةٍ جماعية**."""
    workspace = _section_workspace()
    assert "/drafting-context`" in workspace
    assert "/drafting-consent`" in workspace
    assert "/draft`" in workspace
    assert "context_fingerprint: context.fingerprint" in workspace, (
        "الإذنُ غيرُ مربوطٍ ببصمة اللقطة")
    for batch in ("draft-all", "draftAll", "ENABLED_SECTIONS.map", "sections.map(draft"):
        assert batch not in workspace, f"صياغةٌ جماعية في الشاشة: {batch}"


def test_the_studio_lists_only_what_the_policy_enables():
    """**والسياسةُ هي السلطة**: الشاشةُ تقرأ `enabled` ولا تكتب قائمةً."""
    studio = _studio_page()
    assert "filter((s) => s.enabled)" in studio
    assert "filter((s) => !s.enabled)" in studio
    for hand_written in ('"literature_review"', '"references"', '"introduction"'):
        assert hand_written not in studio, (
            f"اسمُ قسمٍ مكتوبٌ بيد في الشاشة: {hand_written}")


def test_the_blocked_sections_stay_blocked_end_to_end():
    """`literature_review` و`references` — **معطَّلتان في السياسة، ومعلَنتان**."""
    from athera_api.services.publishing.drafting import policy

    for key in ("literature_review", "references"):
        assert key not in policy.ENABLED_SECTIONS
        assert policy.POLICIES[key].enabled is False
        assert policy.POLICIES[key].literature == "blocked"
        assert key in policy.PENDING_SECTIONS


# ══════════ ٧. السلسلةُ كاملةً: من زرِّ الرحلة إلى صفٍّ محفوظ ══════════


def test_a_persisted_section_is_reachable_from_the_journey_screen():
    """**الدعوى التي كانت كاذبةً قبل هذا الإصلاح.**

    `sections_drafted` لا تزيد أبدًا إن لم يكن للصياغة سبيلٌ في الواجهة.
    فتُفحص السلسلةُ حلقةً حلقة — وكلُّ حلقةٍ دعوى تُثبت وحدها:

      ١ زرُّ الرحلة يقصد مسارًا حقيقيًّا (`‎/studio`).
      ٢ ذلك المسارُ يركّب `SectionWorkspace`.
      ٣ المساحةُ تنادي نقطةَ `/draft`.
      ٤ تلك النقطةُ تكتب صفَّ `ManuscriptSection`.
      ٥ و`derive_state` تقرأ ذلك الصفَّ فتقول «صياغة».

    **وهذه سلسلةُ حلقاتٍ لا فحصُ متصفّح**: لا Node هنا، فما لا يُشغَّل
    يُقال إنّه لم يُشغَّل. وأضعفُ حلقةٍ فيها أقوى من لا شيء — وقبلها كانت
    الحلقةُ الأولى مقطوعةً ولا فحصَ يمسّها.
    """
    import inspect as _inspect

    from athera_api.routers import manuscript_drafting
    from athera_api.services.thesis import journey as j

    # ١
    target = next(t for f, t in _manuscript_targets()
                  if f.endswith("ThesisJourney.tsx"))
    assert _route_resolves([s for s in target.split("/") if s])
    # ٢
    assert "<SectionWorkspace" in _studio_page()
    # ٣
    assert "/draft`" in _section_workspace()
    # ٤
    drafting = _inspect.getsource(manuscript_drafting.draft_section)
    assert "ManuscriptSection(" in drafting, "نقطةُ الصياغة لا تكتب صفَّ قسم"
    # ٥
    facts = j.JourneyFacts(
        processing_state="ready_for_review", opportunities=1,
        selected_opportunity=True, rights_passed=True, ai_consent_granted=True,
        project_exists=True, thread_ready=True, outline_exists=True,
        manuscript_exists=True, sections_expected=10, sections_drafted=1)
    assert j.derive_state(facts) == j.DRAFTING


def test_a_refused_action_names_its_reason_not_a_dead_end():
    """**والجملةُ الجامعة تحيل إلى قائمةٍ لا تذكر السبب.**

    `thesis.journey_blocked` نصُّها «التفاصيل في أسباب التوقّف»، وأسبابُ
    الرحلة المعروضة تُشتقّ من وقائعَ لا تحمل بياتَ البصمة. فبصمةٌ بائتة
    كانت تُردّ بجملةٍ تحيل إلى ما لا يذكرها. والرمزُ يسافر في `context`.
    """
    source = _component()
    assert "err.payload.context?.reasons" in source, (
        "الشاشةُ لا تقرأ سببَ الرفض المحدَّد — فالبياتُ يصل طريقًا مسدودًا")
    assert "t(`journey.blocked.${code}`)" in source, "الرمزُ يُعرض كما هو"

    # والرمزُ الذي يرفعه الخادمُ عند البيات له نصٌّ في اللغتين.
    from athera_api.routers import thesis as thesis_router

    endpoint = inspect.getsource(thesis_router.build_thread)
    assert 'reasons=",".join(blocked.reasons)' in endpoint, (
        "الخادمُ لا يُرسل الرموزَ التفصيلية")
