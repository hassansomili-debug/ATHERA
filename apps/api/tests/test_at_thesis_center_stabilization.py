"""تثبيتُ مركز الرسائل | Thesis Center stabilization (Wave 1.1).

**العطبُ الجذريّ: معماريّتان منفصلتان تُعرضان سيرَ عملٍ واحدًا.**

  • `ThesisSection` لا يُكتب إلّا في `POST /theses/{id}/parse` القديم.
  • خطُّ الرفع الحديث يكتب `FactCandidate` ولا يكتب أقسامًا ولا نتائج.
  • و`mine-opportunities` لا يقرأ إلّا الأقسام والنتائج.

فرسالةٌ عالجها الخطُّ الحديث **لا دليل عندها للمنقّب**، والشاشة كانت تعرض
زرّ التنقيب مشروطًا بـ`parsed_at` — ختمِ المسار القديم وحده.

**والعطبُ الثاني: التنقيب كان يضاعف نفسه.** لا فحصَ وجود في الحلقة، ولا
قيدَ تفرّدٍ في القاعدة، ولا فحصٌ واحد يغطّي التنقيب أصلًا. وهذا الملفّ يثبت
أنّ التكرار **كان ممكنًا** قبل أن يثبت أنّه لم يعد ممكنًا: إثباتُ الإصلاح
بلا إثباتِ العطب حراسةٌ على فراغ.
"""
from __future__ import annotations

import ast
import json
import pathlib
import uuid

import pytest

from tests.conftest import requires_db

ROOT = pathlib.Path(__file__).resolve().parents[3]
API = ROOT / "apps" / "api" / "athera_api"
WEB = ROOT / "apps" / "web"
PAGE = WEB / "src" / "app" / "[locale]" / "theses" / "page.tsx"


# ═════════════════════ ١. آلةُ حالِ البطاقة ═════════════════════
#
# **خالصةٌ بلا قاعدة بيانات** — فتُشغَّل في كل بيئة، وهي التي تحمل العقد.

def _actions(state: str, *, has_file: bool = True, sections: int = 0,
             results: int = 0, locale: str = "ar"):
    from athera_api.services.thesis import card_actions

    return card_actions.compute(
        processing_state=state,
        file_id=uuid.uuid4() if has_file else None,
        sections=sections, results=results, locale=locale,
    )


@pytest.mark.parametrize("state", ["queued", "parsing", "extracting"])
def test_a_thesis_being_processed_offers_no_action_that_the_server_would_refuse(state):
    """**حالٌ يجري فيها عملٌ الآن لا فعل عليها.**

    و`claim_for_processing` تردّ `thesis.processing_in_flight` بـ409 على
    أيّ طلبِ معالجةٍ في هذه الحالات. فزرٌّ معروضٌ هنا زرٌّ يَعِد ويُردّ.
    """
    actions = _actions(state)
    assert actions.is_running is True
    assert actions.primary is None, "فعلٌ أوّلٌ معروضٌ على رسالةٍ يجري عليها عمل"
    assert actions.can_process is False
    assert actions.can_reprocess is False
    assert actions.can_parse is False
    assert actions.can_mine is False
    assert actions.can_attach_file is False
    # ولا يُترك الباحث بلا خبر: ما يجري يُقال بنصّه.
    assert actions.blocked_reason, "حالٌ بلا فعلٍ وبلا خبرٍ عمّا يجري"


def test_the_in_flight_states_here_are_the_servers_own_list_not_a_copy():
    """**قائمتان تفترقان بأوّل تعديل.** فالشاشة تقرأ قائمة الخادم نفسها."""
    from athera_api.services.thesis import processing

    for state in processing.IN_FLIGHT:
        assert _actions(state).is_running is True, f"{state} ليست «يجري عليها عمل»"


def test_a_thesis_ready_for_review_leads_with_review_and_keeps_reprocess_second():
    """**الفعلُ الأوّل مراجعةٌ، والثاني إعادةُ قراءة** — لا العكس ولا كلاهما أوّل."""
    from athera_api.services.thesis import card_actions

    actions = _actions("ready_for_review")
    assert actions.primary == card_actions.ACTION_REVIEW
    assert actions.can_review is True
    assert actions.can_reprocess is True, "لا بابَ لإعادة القراءة على رسالةٍ جاهزة"
    assert actions.can_parse is False, "المسار القديم معروضٌ فعلًا عاديًّا"


@pytest.mark.parametrize("state", ["awaiting_consent", "ready_for_review", "completed"])
def test_only_the_states_that_have_something_to_review_open_the_review(state):
    assert _actions(state).can_review is True


@pytest.mark.parametrize("state", ["uploaded", "queued", "parsing", "extracting",
                                   "failed", "text_layer_missing"])
def test_a_state_with_nothing_reviewed_yet_does_not_offer_a_review(state):
    """**رابطُ مراجعةٍ على رسالةٍ لم تُقرأ يفتح شاشةً فارغة** — وهو وعدٌ يخذل."""
    assert _actions(state).can_review is False


def test_a_first_read_is_not_called_a_retry():
    """«أعد المحاولة» على رسالةٍ لم تُقرأ قطّ تجعل الباحث يظنّ أنّه أضاع شيئًا."""
    from athera_api.services.thesis import card_actions

    fresh = _actions("uploaded")
    assert fresh.primary == card_actions.ACTION_PROCESS
    assert fresh.can_process is True and fresh.can_reprocess is False

    broken = _actions("failed")
    assert broken.primary == card_actions.ACTION_REPROCESS
    assert broken.can_reprocess is True and broken.can_process is False


def test_a_manually_registered_thesis_with_no_file_is_never_offered_parse():
    """**العطب بعينه**: `POST /theses/{id}/parse` تردّ `thesis.no_file` بـ422.

    فكان الزرّ يُعرض على كلّ بطاقة بلا استثناء — ومنها رسالةٌ سجّلها الباحث
    يدويًّا ولا ملفّ لها. فيُعرض بدله فعلٌ يمكن أن يقع: أرفق الملفّ.
    """
    from athera_api.services.thesis import card_actions

    actions = _actions("uploaded", has_file=False)
    assert actions.can_parse is False, "زرٌّ يردّه الخادم بـ422 معروضٌ على البطاقة"
    assert actions.can_process is False and actions.can_reprocess is False
    assert actions.primary == card_actions.ACTION_ATTACH_FILE
    assert actions.can_attach_file is True
    # ولا يُعرض «انقل الملفّ إلى السلّة» على رسالةٍ لا ملفّ لها.
    assert actions.can_trash_file is False


def test_no_card_state_in_the_product_offers_the_legacy_parse_action():
    """**المسار القديم مسحوبٌ من البطاقة — والنقطة باقيةٌ في الواجهة البرمجية.**

    والحارس يمرّ على كلّ حالٍ في المفردة المغلقة، بملفّ وبلا ملفّ. فإن
    أُعيد عرضُه يومًا لحالٍ بعينها، سقط هذا الفحص وطُلب سببٌ مكتوب.
    """
    from athera_api.services.thesis import processing

    offered = [
        (state, has_file)
        for state in processing.PROCESSING_STATES
        for has_file in (True, False)
        if _actions(state, has_file=has_file).can_parse
    ]
    assert not offered, f"«تفكيك الرسالة» معروضٌ فعلًا عاديًّا على: {offered}"


def test_the_parse_endpoint_itself_is_not_deleted():
    """**لا تُحذف نقاطُ الواجهة لتنظيف شاشة.** عملاءُ آخرون يبلغونها."""
    source = (API / "routers" / "thesis.py").read_text(encoding="utf-8")
    assert '@router.post("/theses/{thesis_id}/parse"' in source, (
        "نقطةُ التفكيك حُذفت — والعهد يبقيها")


def test_a_scanned_document_is_offered_nothing_and_told_why():
    """إعادةُ قراءةِ ممسوحٍ ضوئيًّا تُنتج النتيجة نفسها حرفًا بحرف ما دام لا OCR."""
    actions = _actions("text_layer_missing")
    assert actions.primary is None
    assert actions.can_reprocess is False and actions.can_process is False
    assert actions.blocked_reason, "منعٌ بلا تفسير"
    assert "OCR" in actions.blocked_reason or "ضوئية" in actions.blocked_reason


def test_the_blocked_reason_speaks_the_readers_language():
    english = _actions("text_layer_missing", locale="en").blocked_reason
    arabic = _actions("text_layer_missing", locale="ar").blocked_reason
    assert english and arabic and english != arabic


# ═════════════════════ ٢. صدقُ استخراج الفرص ═════════════════════

def test_mining_is_measured_by_evidence_the_miner_can_read_not_by_parsed_at():
    """**العطبُ الجذريّ في سطرٍ واحد.**

    الشاشة كانت تسأل `parsed_at`، وهو ختمُ `/parse` وحده. والمنقّب يقرأ
    `thesis_sections` و`thesis_results`. فرسالةٌ عالجها الخطُّ الحديث تحمل
    مرشّحاتِ وقائع ولا تحمل قسمًا واحدًا — فليس عند المنقّب ما يقرؤه.
    """
    from athera_api.services.thesis import card_actions

    modern = _actions("ready_for_review", sections=0, results=0)
    assert modern.mining_state == card_actions.MINING_NO_EVIDENCE
    assert modern.can_mine is False, "زرٌّ يَعِد بتنقيبٍ بلا دليلٍ يُنقَّب فيه"

    parsed = _actions("ready_for_review", sections=2, results=0)
    assert parsed.mining_state == card_actions.MINING_AVAILABLE
    assert parsed.can_mine is True

    # والنتائجُ وحدها تكفي دليلًا — المنقّب يقرؤها أيضًا.
    with_results = _actions("completed", sections=0, results=3)
    assert with_results.can_mine is True


def test_the_unavailable_state_names_the_missing_integration_and_promises_nothing():
    """**«غير متاح» تُقال بسببها، لا بزرٍّ مطفأ ولا بصمت.**

    والنصّ يذكر ما ينقص فعلًا — أنّ خطّ القراءة ينتج مرشّحاتٍ تُراجَع ولا
    يكتب أقسامًا — فلا يُقرأ عطبًا في حساب الباحث.
    """
    arabic = _actions("ready_for_review").mining_reason
    english = _actions("ready_for_review", locale="en").mining_reason
    assert "مراجعة" in arabic and "أقسام" in arabic
    assert "review" in english.lower() and "sections" in english.lower()
    assert arabic != english


def test_mining_is_not_offered_while_the_document_is_still_being_read():
    from athera_api.services.thesis import card_actions

    running = _actions("extracting", sections=4)
    assert running.can_mine is False
    # وسببُه «يجري الآن» لا «لا دليل» — والخبران مختلفان.
    assert running.mining_state == card_actions.MINING_AVAILABLE
    assert running.is_running is True


def test_every_mining_state_and_every_dependency_speaks_both_languages():
    from athera_api.services.thesis import card_actions, removal

    for state in card_actions.MINING_STATES:
        arabic, english = card_actions.MINING_LABELS[state]
        assert arabic.strip() and english.strip() and arabic != english, state
    for key in removal.DEPENDENCY_KEYS:
        arabic, english = removal.DEPENDENCY_LABELS[key]
        assert arabic.strip() and english.strip() and arabic != english, key


# ═════════════════════ ٣. التكرار: يُثبَت أوّلًا، ثمّ يُمنع ═════════════════════

def _facts():
    from athera_api.services.thesis import miner

    return miner.ThesisFacts(
        thesis_id="t-1", title="محددات الرضا الوظيفي ومقارنة الفروق بين المجموعات",
        questions=("ما محددات الرضا الوظيفي؟", "ما أثر الحوافز؟"),
        results=(("r1", "نتيجة أولى"), ("r2", "نتيجة ثانية")),
        variables=("الحوافز", "الرضا", "الأقدمية"),
        sample_ids=("s1",),
    )


def test_the_miner_is_deterministic_so_a_second_click_would_have_duplicated_everything():
    """**إثباتُ العطب قبل إثباتِ إصلاحه.**

    المنقّب حتميّ: المدخلات نفسها تُنتج المقترحات نفسها حرفًا بحرف. وحلقةُ
    الموجّه كانت `session.add(...)` بلا فحصِ وجود، ولا قيدَ تفرّدٍ في
    القاعدة. فضغطتان تكتبان كلّ فرصةٍ مرّتين — وهو ما يثبته هذا الفحص:
    مفتاحُ الهويّة نفسه يعود مرّتين.
    """
    from athera_api.services.thesis import miner

    first = miner.mine(_facts())
    second = miner.mine(_facts())
    assert first, "المنقّب لم يُنتج شيئًا — فالفحص لا يثبت شيئًا"

    def key(draft):
        return (draft.opportunity_kind, draft.paper_kind, draft.working_title_ar)

    assert [key(d) for d in first] == [key(d) for d in second], (
        "المنقّب غير حتميّ — ومفتاحُ منعِ التكرار لا يصلح")
    # ولولا المنع، لصارت الفرص ضِعفَين بعد ضغطتين.
    assert len(first) + len(second) == 2 * len(first)


def test_the_router_refuses_to_write_a_proposal_that_already_exists():
    """**الحلقةُ صارت تفحص الوجود** — والحارس يقرأ الشجر لا النصّ.

    فحصٌ يقرأ نصّ الملفّ يُخدع بتعليق. وهذا يقرأ جسم `mine_opportunities`
    ويطلب: أن يُقرأ ما هو قائم، وأن يوجد `continue` مشروط قبل `add`.
    """
    tree = ast.parse((API / "routers" / "thesis.py").read_text(encoding="utf-8"))
    handler = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "mine_opportunities")
    body = ast.dump(handler)

    assert "with_for_update" in body, (
        "التنقيب بلا قفلٍ على صفّ الرسالة — طلبان متزامنان يكتبان معًا")
    assert "PublicationOpportunity" in body and "Continue" in body, (
        "لا تخطٍّ مشروطٌ في الحلقة — فكلُّ مقترحٍ يُكتب ولو كان قائمًا")


def test_the_response_tells_the_researcher_that_nothing_new_was_written():
    """**«٠ فرص» بعد تنقيبٍ ثانٍ خبرٌ كاذب** — المنقّب وجد ما كان موجودًا.

    فيُفصَل العددان: ما كُتب الآن، وما وُجد قائمًا فلم يُكتب ثانيةً.
    """
    from athera_api.schemas.thesis import MineResponse

    assert "opportunities_already_present" in MineResponse.model_fields
    assert MineResponse.model_fields["opportunities_already_present"].default == 0


# ═════════════════════ ٤. عقدُ الإزالة ═════════════════════

def test_machine_output_never_blocks_removal_and_human_decisions_always_do():
    """**القاعدة الفاصلة**: ما تُعيده قراءةٌ ثانية لا يمنع، وما فيه حكمُ إنسانٍ يمنع."""
    from athera_api.services.thesis import removal

    assert removal.DEP_SECTIONS not in removal.BLOCKING_KEYS
    assert removal.DEP_RESULTS not in removal.BLOCKING_KEYS
    for key in (removal.DEP_VERIFIED_SECTIONS, removal.DEP_REVIEWED_CANDIDATES,
                removal.DEP_OPPORTUNITIES, removal.DEP_CONVERTED_PROJECTS,
                removal.DEP_AUTHORSHIP_RECORDS, removal.DEP_RIGHTS_APPROVALS):
        assert key in removal.BLOCKING_KEYS, f"{key} لا تمنع الإزالة — وهي حكمُ إنسان"


def test_an_unknown_decision_counts_as_a_decision_like_any_other():
    """§٧ — «لا أعرف» قرارٌ حسمه إنسان، ويُحفظ مثل «معتمَد» تمامًا."""
    from athera_api.services.thesis import removal

    assert set(removal.REVIEWED_CANDIDATE_STATES) == {"approved", "rejected", "unknown"}


def test_a_preview_with_any_blocking_dependency_is_not_removable():
    from athera_api.services.thesis import removal

    def build(**counts):
        return removal.RemovalPreview(
            thesis_id=uuid.uuid4(),
            dependencies=tuple(
                removal.Dependency(key=key, count=counts.get(key, 0),
                                   blocking=key in removal.BLOCKING_KEYS)
                for key in removal.DEPENDENCY_KEYS))

    assert build().removable is True
    # أقسامٌ ونتائجُ كثيرة لا تمنع: آلةٌ كتبتها، وقراءةٌ ثانية تُعيدها.
    assert build(sections=9, results=4).removable is True
    assert build(publication_opportunities=1).removable is False
    assert build(reviewed_candidates=1).removable is False
    assert build(verified_sections=1).removable is False
    blocked = build(publication_opportunities=2, sections=5)
    assert blocked.blocking_counts() == {"publication_opportunities": 2}


def test_the_refusal_explains_itself_in_the_readers_language():
    from athera_api.services.thesis import removal

    blocked = removal.RemovalPreview(
        thesis_id=uuid.uuid4(),
        dependencies=(removal.Dependency(
            key=removal.DEP_OPPORTUNITIES, count=3, blocking=True),))
    assert blocked.removable is False
    assert blocked.explanation("ar") != blocked.explanation("en")
    assert blocked.explanation("ar").strip() and blocked.explanation("en").strip()


def test_removing_the_record_is_never_the_same_action_as_trashing_the_file():
    """**فعلان لصاحبين** — ولا يُنفَّذ أحدهما بأثرٍ جانبيّ للآخر.

    وموجّهُ الإزالة لا يذكر `trashed_at` ولا `File` في مسار الحذف: نقلُ
    الملفّ إلى السلّة نقطةٌ أخرى يطلبها الباحث وحده.
    """
    tree = ast.parse((API / "routers" / "thesis.py").read_text(encoding="utf-8"))
    handler = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "remove_thesis")
    body = ast.dump(handler)
    assert "trashed_at" not in body, "الإزالة تمسّ ملفّ المكتبة بأثرٍ جانبيّ"
    assert "delete_object" not in body and "s3" not in body.lower(), (
        "الإزالة تمسّ كائنَ التخزين — ولا يُمحى كائنٌ نهائيًّا")


def test_no_path_in_this_repository_permanently_deletes_a_stored_object():
    """**حدٌّ يُفحَص لا يُوعَد به.** الحذفُ نقلٌ إلى سلّة في كل مسار."""
    forbidden = ("delete_object", "delete_objects", "DeleteObject")
    offenders = []
    for path in sorted((API / "routers").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        offenders += [f"{path.name}:{marker}" for marker in forbidden if marker in text]
    assert not offenders, f"مسارٌ يمحو كائنَ تخزينٍ نهائيًّا: {offenders}"


def test_the_audit_row_is_not_tied_to_the_thesis_it_describes():
    """**التاريخ يبقى بعد إسقاط الصفّ.** ولو حمل `object_id` مفتاحًا أجنبيًّا
    إلى `theses` لسقط السجلّ مع الرسالة أو منع إسقاطها."""
    source = (API / "models" / "audit.py").read_text(encoding="utf-8")
    assert 'ForeignKey("theses.id")' not in source, (
        "سجلُّ التدقيق مربوطٌ بالرسالة — فالتاريخ يُمحى معها")


def test_the_removal_refusal_has_a_message_in_both_catalogues():
    from athera_api.i18n.catalog import CATALOG

    entry = CATALOG["thesis.removal_blocked"]
    assert entry["ar"].strip() and entry["en"].strip()


# ═════════════════════ ٥. العقدُ الذي تقرؤه الشاشة ═════════════════════

def test_the_card_contract_carries_the_actions_the_screen_must_render():
    from athera_api.schemas.thesis import ThesisCardActions, ThesisResponse

    assert "actions" in ThesisResponse.model_fields
    assert ThesisResponse.model_fields["actions"].annotation is ThesisCardActions
    for field in ("primary", "is_running", "can_review", "can_process", "can_reprocess",
                  "can_parse", "can_attach_file", "can_mine", "can_remove",
                  "can_trash_file", "mining_state", "mining_reason", "blocked_reason"):
        assert field in ThesisCardActions.model_fields, field


def test_the_screen_asks_the_server_and_does_not_rebuild_the_rules_itself():
    """**الشاشة لا تجتهد.** كلُّ شرطٍ أُعيد بناؤه في JSX يفترق عن الخادم.

    وهذا العطبُ بعينه: الزرّ كان مشروطًا بـ`thesis.parsed_at` في الشاشة،
    والخادم لا يقيس الإتاحة بذلك أصلًا.
    """
    page = PAGE.read_text(encoding="utf-8")
    assert "actions.can_mine" in page, "الشاشة لا تقرأ إتاحة التنقيب من الخادم"
    assert "actions.primary" in page, "الشاشة لا تقرأ الفعل الأوّل من الخادم"
    assert "!thesis.parsed_at" not in page, (
        "الشاشة ما زالت تحكم على التنقيب بـ`parsed_at` — ختمِ المسار القديم")


def test_the_screen_never_dispatches_the_legacy_parse_action():
    """**المسار القديم مسحوبٌ من الشاشة** — ولا زرّ يرسله."""
    page = PAGE.read_text(encoding="utf-8")
    assert '"parse"' not in page, "زرُّ التفكيك القديم ما زال يُرسل من الشاشة"
    assert "/parse" not in page


def test_every_action_result_is_rendered_inside_its_own_card():
    """**الباحث الذي يضغط البطاقة الخامسة عشرة لا يصعد إلى أعلى الصفحة ليعرف.**

    فالحال محفوظةٌ لكلّ بطاقة على حدة — لا `busyId` واحدة و`setError`
    عامّة تكتبان فوق بعضهما.
    """
    page = PAGE.read_text(encoding="utf-8")
    assert "cardState" in page, "لا حالَ لكل بطاقة على حدة"
    assert "busyId" not in page, "حالُ انشغالٍ واحدة لكلّ الصفحة — والضغطتان تتصادمان"


def test_every_new_message_key_exists_in_both_catalogues():
    """**تكافؤُ الكتالوجين مفروضٌ بفحص** — ونصٌّ ناقصٌ يُعرض مفتاحًا للباحث."""
    arabic = json.loads((WEB / "messages" / "ar.json").read_text(encoding="utf-8"))
    english = json.loads((WEB / "messages" / "en.json").read_text(encoding="utf-8"))

    def flatten(node, prefix=""):
        out = set()
        for key, value in node.items():
            path = f"{prefix}{key}"
            if isinstance(value, dict):
                out |= flatten(value, f"{path}.")
            else:
                out.add(path)
        return out

    missing = flatten(arabic) ^ flatten(english)
    assert not missing, f"مفاتيحُ تنقص أحد الكتالوجين: {sorted(missing)}"


def test_the_browser_spec_is_wired_into_both_the_scripts_and_the_workflow():
    """**رقعةٌ لا يُشغّلها المشغّل حبرٌ على ورق** — والحارس العامّ يمنع ذلك،
    وهذا يذكر الرقعة بالاسم فلا تُنزع بصمت."""
    scripts = json.loads((WEB / "package.json").read_text(encoding="utf-8"))["scripts"]
    body = scripts.get("test:thesis-center", "")
    assert "thesis-center.spec.ts" in body, "لا سكربت يشغّل رقعة مركز الرسائل"
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "npm run test:thesis-center" in workflow, "المشغّل لا ينادي الرقعة"


def test_this_repair_needed_no_migration():
    """**الترقيم `0030` مملوكٌ لموجة 2-A** — ولا يُنشأ ترحيلٌ منافس هنا.

    والقفلُ على صفّ الرسالة يحرس ما كان قيدُ التفرّد سيحرسه على هذا المسار،
    ووسمُ الإزالة لم يُحتَجْ أصلًا: رسالةٌ بلا تبعاتٍ علميّة تُسقط صفُّها،
    وسجلُّ التدقيق يبقى.
    """
    versions = ROOT / "infra" / "db" / "migrations" / "versions"
    numbers = sorted(p.name.split("_", 1)[0] for p in versions.glob("0*.py"))
    assert "0030" not in numbers, "ترحيلٌ 0030 أُنشئ هنا — والترقيم مملوكٌ لموجةٍ أخرى"
    assert numbers[-1] == "0029", f"آخر ترحيلٍ ليس 0029: {numbers[-1]}"


# ═════════════════════ ٦. القاعدةُ الحقيقية ═════════════════════
#
# **تُتخطّى بلا PostgreSQL حيّة، ولا تُعدّ ناجحة.**

async def _seed(tenant_id, user_id, *, filename="رسالة.pdf", with_file=True, **columns):
    """رسالةٌ كما يكتبها المنتج عند الرفع — بملفّها ومِنحتها، أو بلا ملفّ."""
    from athera_api.db import tenant_session
    from athera_api.models.files import File
    from athera_api.models.identity import ObjectGrant
    from athera_api.models.thesis import Thesis

    async with tenant_session(tenant_id, user_id) as session:
        file_id = None
        if with_file:
            record = File(
                tenant_id=tenant_id,
                storage_key=f"tenants/{tenant_id}/files/{uuid.uuid4()}/{filename}",
                original_filename=filename, content_type="application/pdf",
                size_bytes=2048, status="stored", uploaded_by=user_id)
            session.add(record)
            await session.flush()
            session.add(ObjectGrant(
                tenant_id=tenant_id, object_type="file", object_id=record.id,
                user_id=user_id, grant_level="owner", granted_by=user_id))
            file_id = record.id
        # الافتراضاتُ تُدمَج لا تُكرَّر: `Thesis(title_ar=None, **{"title_ar": …})`
        # يسقط بـ«multiple values for keyword argument» قبل أن يفحص شيئًا.
        thesis = Thesis(**{"tenant_id": tenant_id, "file_id": file_id,
                           "title_ar": None, "degree": None, **columns})
        session.add(thesis)
        await session.flush()
        return thesis.id, file_id


def _client(tenant_id, user_id, locale="ar"):
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    token = issue_access_token(user_id=user_id, tenant_id=tenant_id,
                               roles=["researcher"], mfa_satisfied=True)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": locale})


async def _give_the_miner_something_to_read(tenant_id, user_id, thesis_id):
    """أقسامٌ ونتائجُ كما يكتبها `/parse` — **دليلُ المنقّب الوحيد**."""
    from athera_api.db import tenant_session
    from athera_api.models.thesis import ThesisResult, ThesisSection

    async with tenant_session(tenant_id, user_id) as session:
        session.add(ThesisSection(
            tenant_id=tenant_id, thesis_id=thesis_id, section_key="questions",
            content_ar="ما محددات الرضا الوظيفي؟", locator="ص ٣٤",
            quote="ما محددات الرضا الوظيفي؟", verification_status="unverified"))
        session.add(ThesisResult(
            tenant_id=tenant_id, thesis_id=thesis_id, label_ar="نتيجة أولى",
            variables=["الحوافز", "الرضا", "الأقدمية"], locator="ص ٩٠"))
        await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_over_http_mining_twice_never_produces_a_duplicate(two_tenants):
    """**العطبُ الأصلي، ومنعُه، في فحصٍ واحد.**

    التشغيلة الأولى تكتب، والثانية تجد ما كتبته الأولى فلا تكتب شيئًا —
    والعدُّ في القاعدة هو الشاهد، لا جسمُ الردّ وحده. ولو بقيت الحلقة كما
    كانت لصار العدد ضِعفًا بعد الطلب الثاني وثلاثةَ أضعافٍ بعد الثالث.
    """
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import PublicationOpportunity

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _ = await _seed(tid, uid, title_ar="محددات الرضا الوظيفي ومقارنة الفروق")
    await _give_the_miner_something_to_read(tid, uid, thesis_id)

    async def count():
        async with tenant_session(tid, uid) as session:
            return (await session.execute(
                select(func.count(PublicationOpportunity.id))
                .where(PublicationOpportunity.thesis_id == thesis_id))).scalar_one()

    async with _client(tid, uid) as client:
        first = await client.post(f"/api/v1/theses/{thesis_id}/mine-opportunities")
        assert first.status_code == 202, first.text
        created = first.json()["opportunities_created"]
        assert created > 0, "المنقّب لم يجد شيئًا — فالفحص لا يثبت شيئًا"
        assert await count() == created

        for _ in range(2):
            again = await client.post(f"/api/v1/theses/{thesis_id}/mine-opportunities")
            assert again.status_code == 202, again.text
            assert again.json()["opportunities_created"] == 0, "تنقيبٌ كرّر نفسه"
            # **و«٠ الآن» تُقال بسببها**: وُجد ما كان موجودًا، لا «لم يُوجد شيء».
            assert again.json()["opportunities_already_present"] == created

    assert await count() == created, "الفرصُ تضاعفت في القاعدة"


@requires_db
@pytest.mark.asyncio
async def test_over_http_a_thesis_from_the_modern_pipeline_is_told_mining_is_not_ready(
        two_tenants):
    """**الرسالةُ التي كشفت العطب.** جاهزةٌ للمراجعة، ولا قسم ولا نتيجة."""
    from athera_api.db import tenant_session
    from athera_api.services.thesis import processing

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _ = await _seed(tid, uid, filename="حديثة.pdf")
    async with tenant_session(tid, uid) as session:
        await processing.mark(session, tenant_id=tid, thesis_id=thesis_id,
                              state=processing.READY_FOR_REVIEW)

    async with _client(tid, uid) as client:
        card = next(row for row in (await client.get("/api/v1/theses")).json()
                    if row["id"] == str(thesis_id))

    assert card["actions"]["primary"] == "review"
    assert card["actions"]["can_mine"] is False
    assert card["actions"]["mining_state"] == "no_evidence"
    assert card["actions"]["mining_reason"], "«غير متاح» بلا سبب"
    assert card["actions"]["can_parse"] is False


@requires_db
@pytest.mark.asyncio
async def test_over_http_a_manual_thesis_with_no_file_is_offered_an_attachment(two_tenants):
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]

    async with _client(tid, uid) as client:
        created = await client.post("/api/v1/theses", json={
            "title_ar": "رسالةٌ سجّلتها بيدي", "degree": "masters"})
        assert created.status_code == 201, created.text
        card = created.json()

    assert card["source_file_id"] is None
    assert card["actions"]["can_parse"] is False, "زرٌّ يردّه الخادم بـ422"
    assert card["actions"]["primary"] == "attach_file"
    assert card["actions"]["can_trash_file"] is False


@requires_db
@pytest.mark.asyncio
async def test_over_http_the_parse_endpoint_still_refuses_a_thesis_with_no_file(two_tenants):
    """**النقطة باقيةٌ وحدُّها باقٍ** — والبطاقة وحدها كفّت عن عرضها."""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _ = await _seed(tid, uid, with_file=False, title_ar="بلا ملفّ")

    async with _client(tid, uid) as client:
        response = await client.post(f"/api/v1/theses/{thesis_id}/parse")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "thesis.no_file"


@requires_db
@pytest.mark.asyncio
async def test_over_http_a_disposable_thesis_is_removed_and_its_history_survives(two_tenants):
    """**رسالةٌ لا يقوم عليها شيءٌ علميّ تُزال** — ويبقى سجلُّها كاملًا.

    ولا يُمسّ ملفُّ المكتبة: صفُّه باقٍ و`trashed_at` فيه `NULL`.
    """
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.audit import AuditEvent
    from athera_api.models.files import File
    from athera_api.models.thesis import Thesis

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id = await _seed(tid, uid, filename="يُستغنى عنها.pdf")

    async with _client(tid, uid) as client:
        preview = await client.get(f"/api/v1/theses/{thesis_id}/removal-preview")
        assert preview.status_code == 200, preview.text
        assert preview.json()["removable"] is True
        assert preview.json()["explanation"]
        assert preview.json()["source_file_id"] == str(file_id)

        removed = await client.delete(f"/api/v1/theses/{thesis_id}")
        assert removed.status_code == 200, removed.text
        assert removed.json()["removed"] is True

        assert not [row for row in (await client.get("/api/v1/theses")).json()
                    if row["id"] == str(thesis_id)]

    async with tenant_session(tid, uid) as session:
        assert (await session.execute(
            select(Thesis).where(Thesis.id == thesis_id))).scalar_one_or_none() is None
        # **التاريخ يبقى** — والسجلُّ يذكر ما جرى على معرّفٍ لم يعد له صفّ.
        trail = (await session.execute(
            select(func.count(AuditEvent.id))
            .where(AuditEvent.object_id == thesis_id))).scalar_one()
        assert trail > 0, "سجلُّ التدقيق مُحي مع الرسالة"
        # **وملفُّ المكتبة لم يُمسّ** — نقلُه إلى السلّة فعلٌ آخر.
        record = (await session.execute(
            select(File).where(File.id == file_id))).scalar_one()
        assert record.trashed_at is None, "الإزالة نقلت الملفّ إلى السلّة بأثرٍ جانبيّ"


@requires_db
@pytest.mark.asyncio
async def test_over_http_removal_is_refused_when_a_human_decision_rests_on_the_thesis(
        two_tenants):
    """**لا حذفٌ متسلسلٌ صامت.** فرصةُ نشرٍ قائمة تمنع، ويُقال ما يمنع بعدده."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import PublicationOpportunity, Thesis

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _ = await _seed(tid, uid, filename="يقوم عليها عمل.pdf")
    async with tenant_session(tid, uid) as session:
        session.add(PublicationOpportunity(
            tenant_id=tid, thesis_id=thesis_id,
            opportunity_kind="independent_question", paper_kind="extraction",
            working_title_ar="ورقةٌ من السؤال الأول"))
        await session.flush()

    async with _client(tid, uid) as client:
        preview = await client.get(f"/api/v1/theses/{thesis_id}/removal-preview")
        assert preview.status_code == 200, preview.text
        body = preview.json()
        assert body["removable"] is False
        blocking = {row["key"]: row for row in body["blocking"]}
        assert blocking["publication_opportunities"]["count"] == 1
        assert blocking["publication_opportunities"]["label"], "تبعةٌ بلا اسمٍ يُقرأ"

        refused = await client.delete(f"/api/v1/theses/{thesis_id}")
        assert refused.status_code == 409, refused.text
        assert refused.json()["error"]["code"] == "thesis.removal_blocked"
        assert refused.json()["error"]["message"], "رفضٌ بلا تفسير"

    # **ولم تُمسّ**: لا الرسالة ولا ما بُني عليها.
    async with tenant_session(tid, uid) as session:
        assert (await session.execute(
            select(Thesis).where(Thesis.id == thesis_id))).scalar_one_or_none() is not None
        assert (await session.execute(
            select(PublicationOpportunity)
            .where(PublicationOpportunity.thesis_id == thesis_id))).scalars().all()


@requires_db
@pytest.mark.asyncio
async def test_over_http_another_tenant_can_neither_read_nor_mine_nor_remove(two_tenants):
    """**العزلُ يُجرَّب على كلّ نقطةٍ جديدة، لا على القراءة وحدها.**

    وسياسةٌ تمنع القراءة وتسمح بالحذف عزلٌ نصفيّ يُقرأ سليمًا في اختبارٍ
    نصفيّ. فتُجرَّب الأربع: القائمة، المعاينة، التنقيب، الإزالة.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import Thesis

    a, b = two_tenants["a"], two_tenants["b"]
    thesis_id, _ = await _seed(a["tenant_id"], a["user_id"], filename="ليست لك.pdf")
    await _give_the_miner_something_to_read(a["tenant_id"], a["user_id"], thesis_id)

    async with _client(b["tenant_id"], b["user_id"]) as intruder:
        listing = await intruder.get("/api/v1/theses")
        assert listing.status_code == 200
        assert not [row for row in listing.json() if row["id"] == str(thesis_id)]

        for response in (
            await intruder.get(f"/api/v1/theses/{thesis_id}/removal-preview"),
            await intruder.post(f"/api/v1/theses/{thesis_id}/mine-opportunities"),
            await intruder.delete(f"/api/v1/theses/{thesis_id}"),
        ):
            assert response.status_code == 404, response.text
            assert response.json()["error"]["code"] == "thesis.not_found"

    # **والرسالةُ باقيةٌ كما هي** — ولا فرصةَ كُتبت عليها من خارج مستأجرها.
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        assert (await session.execute(
            select(Thesis).where(Thesis.id == thesis_id))).scalar_one_or_none() is not None

    async with _client(a["tenant_id"], a["user_id"]) as owner:
        card = next(row for row in (await owner.get("/api/v1/theses")).json()
                    if row["id"] == str(thesis_id))
    assert card["opportunities_found"] == 0, "تنقيبُ مستأجرٍ آخر أصاب رسالةً ليست له"
