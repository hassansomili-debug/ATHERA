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
             results: int = 0, locale: str = "ar", archived: bool = False):
    from athera_api.services.thesis import card_actions

    return card_actions.compute(
        processing_state=state,
        file_id=uuid.uuid4() if has_file else None,
        sections=sections, results=results, locale=locale, archived=archived,
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

    assert "arg='lock'" in body or "with_for_update" in body, (
        "التنقيب بلا قفلٍ على صفّ الرسالة — طلبان متزامنان يكتبان معًا")
    assert "PublicationOpportunity" in body and "Continue" in body, (
        "لا تخطٍّ مشروطٌ في الحلقة — فكلُّ مقترحٍ يُكتب ولو كان قائمًا")
    # والقفلُ حقيقيّ في الحارس المشترك، لا اسمًا في وسيط.
    guard = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_thesis_or_404")
    assert "with_for_update" in ast.dump(guard), "الحارس لا يقفل صفًّا أصلًا"


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


def test_only_human_decided_work_makes_the_archive_ask_for_an_acknowledgement():
    """**والسؤالُ تغيّر مع الفعل.** كان «أيجوز حذفُها؟»؛ والحذفُ ذهب من
    المنتج، فصار «أيستوجب إخفاؤها إقرارًا صريحًا؟»."""
    from athera_api.services.thesis import removal

    def build(**counts):
        return removal.RemovalPreview(
            thesis_id=uuid.uuid4(),
            dependencies=tuple(
                removal.Dependency(key=key, count=counts.get(key, 0),
                                   blocking=key in removal.BLOCKING_KEYS)
                for key in removal.DEPENDENCY_KEYS))

    assert build().needs_acknowledgement is False
    # أقسامٌ ونتائجُ كثيرة لا تستوجب شيئًا: آلةٌ كتبتها، وقراءةٌ ثانية تُعيدها.
    assert build(sections=9, results=4).needs_acknowledgement is False
    assert build(publication_opportunities=1).needs_acknowledgement is True
    assert build(reviewed_candidates=1).needs_acknowledgement is True
    assert build(verified_sections=1).needs_acknowledgement is True
    asked = build(publication_opportunities=2, sections=5)
    assert asked.acknowledged_counts() == {"publication_opportunities": 2}


def test_the_acknowledgement_prompt_explains_itself_in_the_readers_language():
    from athera_api.services.thesis import removal

    asked = removal.RemovalPreview(
        thesis_id=uuid.uuid4(),
        dependencies=(removal.Dependency(
            key=removal.DEP_OPPORTUNITIES, count=3, blocking=True),))
    assert asked.needs_acknowledgement is True
    assert asked.explanation("ar") != asked.explanation("en")
    assert asked.explanation("ar").strip() and asked.explanation("en").strip()
    # **ولا يَعِد النصُّ بحذف** — الأرشفة تُخفي، والاسترجاع يعيد.
    assert "لا تحذف" in asked.explanation("ar")
    assert "deletes nothing" in asked.explanation("en")


def test_archiving_the_record_is_never_the_same_action_as_trashing_the_file():
    """**فعلان لصاحبين** — ولا يُنفَّذ أحدهما بأثرٍ جانبيّ للآخر.

    وموجّهُ الإزالة لا يذكر `trashed_at` ولا `File` في مسار الحذف: نقلُ
    الملفّ إلى السلّة نقطةٌ أخرى يطلبها الباحث وحده.
    """
    tree = ast.parse((API / "routers" / "thesis.py").read_text(encoding="utf-8"))
    handler = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "archive_thesis")
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
                  "can_parse", "can_attach_file", "can_mine", "can_archive",
                  "can_restore", "can_trash_file", "is_archived",
                  "lifecycle_blocked_reason", "mining_state", "mining_reason",
                  "blocked_reason"):
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


def test_the_screen_never_sends_a_delete_for_a_thesis():
    """**الحذفُ رُفع من المنتج** — فلا الشاشةُ ترسله ولا الخادمُ يقبله."""
    page = PAGE.read_text(encoding="utf-8")
    assert '"DELETE"' not in page, "الشاشة ما زالت ترسل حذفًا على رسالة"
    # والاسترجاع يمرّ بـ`run(id, "restore", …)` التي تبني المسار، فيُسأل عن
    # اسم الفعل لا عن سلسلةٍ حرفيّة لا وجود لها.
    assert "/archive" in page, "الشاشة لا تعرف الأرشفة"
    assert '"restore"' in page, "الشاشة لا تعرف الاسترجاع"


def test_the_screen_shows_the_archive_and_the_way_back_from_it():
    """**أرشفةٌ بلا طريقِ عودةٍ مرئيّ حذفٌ في تجربة الباحث.**"""
    page = PAGE.read_text(encoding="utf-8")
    assert "theses.viewArchived" in page, "لا عرضَ للأرشيف في القائمة"
    assert "actions.can_restore" in page, "لا استرجاع في الشاشة"
    assert "actions.is_archived" in page, "البطاقة لا تقول إنّها مؤرشَفة"


def test_the_screen_hides_lifecycle_actions_while_work_is_running_and_says_why():
    page = PAGE.read_text(encoding="utf-8")
    assert "actions.can_archive" in page, "الأرشفة تُعرض بلا شرطٍ من الخادم"
    assert "actions.can_trash_file" in page, "السلّة تُعرض بلا شرطٍ من الخادم"
    assert "actions.lifecycle_blocked_reason" in page, "منعٌ بلا تفسيرٍ في الشاشة"


def test_the_screen_sends_the_acknowledgement_explicitly():
    """**والإقرارُ يُرسَل صريحًا** — لا يُفترض في الخادم ولا يُرسَل دائمًا `true`."""
    page = PAGE.read_text(encoding="utf-8")
    assert "acknowledge" in page
    assert "needs_acknowledgement" in page, (
        "الشاشة لا تقرأ حاجةَ الإقرار من المعاينة، فتُقرّ عن الباحث")


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


def test_migration_0030_belongs_to_this_wave_and_is_purely_additive():
    """**ترحيلٌ واحد، وتوسعةٌ محضة** — والخادمُ القائم يبقى صحيحًا عليه.

    بين ترحيل القاعدة ونشر الموجة نافذةٌ يخدم فيها الخادمُ القديم مخطَّطًا
    جديدًا (الدرس المكتوب في 0028/0029). فيُطلب من هذا الترحيل ثلاثة:

      • **لا عمودَ إلزاميّ ولا افتراضٌ يكتب شيئًا** — الخادمُ القائم يُدرج
        صفوفًا بلا ذكر العمودين، فيأخذان `NULL` ومعناها «غير مؤرشَفة».
      • **ولا `ALTER` ولا `DROP` ولا `UPDATE` على ما هو قائم** — توسعةٌ لا
        تعديل، فلا صفَّ يُمسّ ولا عمودَ قديمٌ يتغيّر عقده.
      • **ولا حذفَ صفوفٍ في المنتج** يوجب هذا العمود أصلًا.
    """
    versions = ROOT / "infra" / "db" / "migrations" / "versions"
    numbers = sorted(path.name.split("_", 1)[0] for path in versions.glob("0*.py"))
    assert numbers[-1] == "0030", f"آخرُ ترحيلٍ ليس 0030: {numbers[-1]}"
    assert numbers.count("0030") == 1, "ترحيلان يحملان الرقم 0030"

    body = (versions / "0030_thesis_archive.py").read_text(encoding="utf-8")
    upgrade = body[body.index("def upgrade()"):body.index("def downgrade()")]

    assert "nullable=True" in upgrade
    assert "nullable=False" not in upgrade, "عمودٌ إلزاميّ يكسر الخادمَ القائم"
    assert "server_default" not in upgrade, "افتراضٌ يكتب في صفوفٍ قائمة"
    # و«ON DELETE RESTRICT» وصفُ مفتاحٍ أجنبيّ لا حذفُ صفوف — فيُسأل عن
    # عبارات الكتابة بأسمائها الكاملة لا عن كلمةٍ تقع فيها.
    for forbidden in ("DROP COLUMN", "ALTER COLUMN", "UPDATE THESES",
                      "DELETE FROM", "TRUNCATE"):
        assert forbidden not in upgrade.upper(), (
            f"الترحيل ليس توسعةً محضة — فيه {forbidden}")
    # والقيدُ الوحيد يصف العمودين الجديدين وحدهما، فتحقّقه الصفوفُ القائمة
    # جميعًا (كلاهما `NULL` فيها). ونصُّه ثابتٌ في رأس الملفّ لا في الجسم.
    assert "(archived_at IS NULL) = (archived_by IS NULL)" in body
    assert "ADD CONSTRAINT" in upgrade and "CHECK" in upgrade


def test_the_product_has_no_way_to_physically_delete_a_thesis():
    """**الحذفُ رُفع من المنتج، ولم يُستبدل بحذفٍ أهدأ.**

    وأوّلُ علاجٍ كتب `DELETE FROM theses` على رسالةٍ لا تبعات لها اليوم —
    و«لا تبعات اليوم» ليست «لن تكون»، و`ON DELETE CASCADE` قائمٌ تحتها على
    خمسة جداول. فلا نقطةَ حذفٍ ولا عبارةَ حذفٍ على الرسائل في أيّ موجّه.
    """
    tree = ast.parse((API / "routers" / "thesis.py").read_text(encoding="utf-8"))
    dumped = ast.dump(tree)
    assert "delete(Thesis)" not in ast.unparse(tree), "عبارةُ حذفٍ على الرسائل"
    assert "'delete'" in dumped or '"delete"' in dumped  # مستوى الإذن، لا الفعل

    for path in sorted((API / "routers").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "@router.delete(\"/theses" not in source, (
            f"{path.name}: نقطةُ حذفٍ على الرسائل")


def test_an_archived_thesis_is_offered_restore_and_no_work_action():
    """**المؤرشَفة ساكنة**: قراءةٌ أو تنقيبٌ على سجلٍّ مُخفًى يكتب في ما لا يراه صاحبه."""
    from athera_api.services.thesis import card_actions

    actions = _actions("ready_for_review", sections=3, archived=True)
    assert actions.is_archived is True
    assert actions.primary == card_actions.ACTION_RESTORE
    assert actions.can_restore is True
    assert actions.can_archive is False
    assert actions.can_review is False
    assert actions.can_reprocess is False and actions.can_process is False
    assert actions.can_mine is False
    assert actions.can_trash_file is False


@pytest.mark.parametrize("state", ["queued", "parsing", "extracting"])
def test_no_lifecycle_action_is_offered_while_work_is_running(state):
    """**ولا عقدَ إلغاءٍ يُدَّعى.** أرشفةٌ أو سلّةٌ أثناء مهمّةٍ تقرأ الملفّ
    وتكتب مرشّحاتها تتركان نصفَ حال، ولا سبيل إلى إيقافها في هذه المرحلة."""
    actions = _actions(state, sections=4)
    assert actions.can_archive is False, "أرشفةٌ معروضةٌ أثناء عملٍ جارٍ"
    assert actions.can_trash_file is False, "سلّةٌ معروضةٌ أثناء عملٍ جارٍ"
    assert actions.lifecycle_blocked_reason, "منعٌ بلا تفسير"
    assert "إلغاء" in actions.lifecycle_blocked_reason


def test_the_lifecycle_block_is_stated_in_both_languages_and_promises_no_cancel():
    from athera_api.services.thesis import card_actions

    arabic, english = card_actions.LIFECYCLE_BLOCKED_LABELS
    assert arabic.strip() and english.strip() and arabic != english
    # **ولا وعدَ بإلغاء**: النصّ يقول إنّه غير متاح، لا إنّه سيقع.
    assert "no cancellation contract" in english


def test_the_server_refuses_lifecycle_actions_in_flight_not_only_the_screen():
    """**شاشةٌ تُخفي زرًّا وخادمٌ يقبل الطلب حارسٌ واحدٌ لا اثنان.**

    فيُقرأ الشجرُ: كلُّ نقطةٍ تغيّر دورة الحياة تنادي `_refuse_if_in_flight`.
    """
    tree = ast.parse((API / "routers" / "thesis.py").read_text(encoding="utf-8"))
    guarded = {
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef)
        and "_refuse_if_in_flight" in ast.dump(node)
    }
    for endpoint in ("archive_thesis", "parse_thesis", "mine_opportunities"):
        assert endpoint in guarded, f"{endpoint} لا يفحص العمل الجاري"


def test_every_thesis_endpoint_asks_for_an_object_permission_not_only_a_tenant():
    """**العزلُ بين المستأجرين لا يحمي بين عضوين في المستأجر الواحد.**

    والحارسُ المشترك `_thesis_or_404` يسأل `require_object_action` على ملفّ
    الرسالة — وهو النموذج نفسه الذي يستعمله `document_intelligence`. فيُطلب
    أن تمرّ كلُّ نقطةٍ به، وأن يكون المستوى المطلوب مذكورًا صراحةً.
    """
    tree = ast.parse((API / "routers" / "thesis.py").read_text(encoding="utf-8"))
    guard = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_thesis_or_404")
    assert "require_object_action" in ast.dump(guard), (
        "الحارس لا يسأل عن إذنٍ على الكائن — العزلُ وحده لا يكفي")

    wanted = {
        "parse_thesis": "write",
        "mine_opportunities": "write",
        "removal_preview": "read",
        "archive_thesis": "delete",
        "restore_thesis": "delete",
    }
    for name, level in wanted.items():
        node = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
        body = ast.dump(node)
        assert "_thesis_or_404" in body, f"{name} لا يمرّ بالحارس"
        assert f"'{level}'" in body, f"{name} لا يطلب مستوى `{level}`"


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


async def _second_member(tenant_id):
    """عضوٌ ثانٍ في **المستأجر نفسه** — لا مستأجرٌ آخر.

    **وهو الفجوة التي كُشفت**: RLS تحمي بين المستأجرين، ولا تحمي بين عضوين
    تحت المظلّة نفسها. فبلا إذنٍ على الكائن يبلغ أيُّ عضوٍ رسالةَ زميله.
    """
    from sqlalchemy import select

    from athera_api.db import system_session
    from athera_api.models.identity import Membership, Role, User
    from athera_api.security import hash_password

    async with system_session() as session:
        user = User(
            email=f"second-{uuid.uuid4().hex[:10]}@example.test",
            password_hash=hash_password("correct-horse-battery-staple"),
            full_name_ar="زميلٌ في المستأجر نفسه",
            full_name_en="A colleague in the same tenant")
        session.add(user)
        await session.flush()
        role = (await session.execute(
            select(Role).where(Role.tenant_id == tenant_id, Role.key == "researcher")
        )).scalar_one()
        session.add(Membership(tenant_id=tenant_id, user_id=user.id, role_id=role.id))
        return user.id


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
async def test_over_http_the_history_of_an_archived_thesis_stays_readable(two_tenants):
    """**التاريخ يبقى، والصفُّ يبقى معه.**

    وكانت هذه الدعوى تفحص أنّ سجلّ التدقيق ينجو من حذفِ الصفّ. والحذفُ ذهب،
    فصارت تفحص ما هو أقوى: أنّ الصفّ **والسجلّ** كليهما باقيان، وأنّ حدث
    الأرشفة نفسه مكتوبٌ بمن فعله.
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
        assert preview.json()["needs_acknowledgement"] is False
        assert preview.json()["explanation"]
        assert preview.json()["source_file_id"] == str(file_id)

        archived = await client.post(f"/api/v1/theses/{thesis_id}/archive", json={})
        assert archived.status_code == 200, archived.text
        assert archived.json()["archived"] is True

        assert not [row for row in (await client.get("/api/v1/theses")).json()
                    if row["id"] == str(thesis_id)]

    async with tenant_session(tid, uid) as session:
        # **والصفُّ باقٍ** — مؤرشَفًا، لا محذوفًا.
        row = (await session.execute(
            select(Thesis).where(Thesis.id == thesis_id))).scalar_one()
        assert row.archived_at is not None
        assert row.archived_by == uid, "أرشفةٌ لا يُعرف بيد مَن"

        trail = (await session.execute(
            select(func.count(AuditEvent.id))
            .where(AuditEvent.object_id == thesis_id,
                   AuditEvent.action == "thesis.archived"))).scalar_one()
        assert trail > 0, "الأرشفة لم تُسجَّل"

        # **وملفُّ المكتبة لم يُمسّ** — نقلُه إلى السلّة فعلٌ آخر.
        record = (await session.execute(
            select(File).where(File.id == file_id))).scalar_one()
        assert record.trashed_at is None, "الأرشفة نقلت الملفّ إلى السلّة بأثرٍ جانبيّ"


@requires_db
@pytest.mark.asyncio
async def test_over_http_archiving_asks_before_it_hides_human_decided_work(two_tenants):
    """**لا إخفاءَ صامتٌ لما بُني عليها.** فرصةُ نشرٍ قائمة تستوجب إقرارًا،
    ويُقال ما يستوجبه بعدده — ثمّ يمضي الفعل بالإقرار، ويُستعاد بالاسترجاع."""
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
        assert body["needs_acknowledgement"] is True
        asked = {row["key"]: row for row in body["blocking"]}
        assert asked["publication_opportunities"]["count"] == 1
        assert asked["publication_opportunities"]["label"], "تبعةٌ بلا اسمٍ يُقرأ"

        refused = await client.post(f"/api/v1/theses/{thesis_id}/archive", json={})
        assert refused.status_code == 409, refused.text
        assert refused.json()["error"]["code"] == "thesis.archive_needs_acknowledgement"
        assert refused.json()["error"]["message"], "رفضٌ بلا تفسير"

    # **ولم تُمسّ**: لا الرسالة ولا ما بُني عليها.
    async with tenant_session(tid, uid) as session:
        row = (await session.execute(
            select(Thesis).where(Thesis.id == thesis_id))).scalar_one()
        assert row.archived_at is None
        assert (await session.execute(
            select(PublicationOpportunity)
            .where(PublicationOpportunity.thesis_id == thesis_id))).scalars().all()



@requires_db
@pytest.mark.asyncio
async def test_over_http_another_tenant_can_neither_read_nor_mine_nor_archive(two_tenants):
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
            await intruder.post(f"/api/v1/theses/{thesis_id}/archive",
                                json={"acknowledge": True}),
            await intruder.post(f"/api/v1/theses/{thesis_id}/restore"),
        ):
            assert response.status_code == 404, response.text
            assert response.json()["error"]["code"] == "thesis.not_found"

    # **والرسالةُ باقيةٌ كما هي** — ولا فرصةَ كُتبت عليها من خارج مستأجرها،
    # ولا أُرشفت من خارجه.
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        row = (await session.execute(
            select(Thesis).where(Thesis.id == thesis_id))).scalar_one_or_none()
        assert row is not None
        assert row.archived_at is None

    async with _client(a["tenant_id"], a["user_id"]) as owner:
        card = next(row for row in (await owner.get("/api/v1/theses")).json()
                    if row["id"] == str(thesis_id))
    assert card["opportunities_found"] == 0, "تنقيبُ مستأجرٍ آخر أصاب رسالةً ليست له"


# ═════════════════════ ٧. الأرشفة على قاعدةٍ حيّة ═════════════════════


@requires_db
@pytest.mark.asyncio
async def test_over_http_archiving_hides_the_record_and_deletes_not_one_row(two_tenants):
    """**الأرشفة تُخفي ولا تحذف** — ويُثبَت ذلك بالعدّ لا بالوعد.

    فتُبنى رسالةٌ بكلّ ما يتدلّى منها — أقسامٌ ونتائجُ وفرصةُ نشر — ثمّ
    تُؤرشَف، ثمّ **تُعدّ الصفوفُ كلُّها من جديد**: لا صفَّ نقص. وذاك هو
    الفرق بين هذا العقد وأوّل صياغةٍ كتبت `DELETE FROM theses`.
    """
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import (
        PublicationOpportunity, Thesis, ThesisResult, ThesisSection,
    )

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id = await _seed(tid, uid, filename="تُؤرشَف.pdf",
                                     title_ar="رسالةٌ يقوم عليها عمل")
    await _give_the_miner_something_to_read(tid, uid, thesis_id)
    async with tenant_session(tid, uid) as session:
        session.add(PublicationOpportunity(
            tenant_id=tid, thesis_id=thesis_id,
            opportunity_kind="independent_question", paper_kind="extraction",
            working_title_ar="ورقةٌ قائمة"))
        await session.flush()

    async def census():
        async with tenant_session(tid, uid) as session:
            out = {}
            for label, model in (("sections", ThesisSection), ("results", ThesisResult),
                                 ("opportunities", PublicationOpportunity)):
                out[label] = (await session.execute(
                    select(func.count(model.id))
                    .where(model.thesis_id == thesis_id))).scalar_one()
            out["thesis"] = (await session.execute(
                select(func.count(Thesis.id))
                .where(Thesis.id == thesis_id))).scalar_one()
            return out

    before = await census()
    assert before == {"sections": 1, "results": 1, "opportunities": 1, "thesis": 1}

    async with _client(tid, uid) as client:
        # **ما يتدلّى منه عملُ إنسانٍ يستوجب إقرارًا** — ولا يقع بغفلة.
        refused = await client.post(f"/api/v1/theses/{thesis_id}/archive", json={})
        assert refused.status_code == 409, refused.text
        assert refused.json()["error"]["code"] == "thesis.archive_needs_acknowledgement"
        assert await census() == before, "طلبٌ مردودٌ غيّر شيئًا"

        done = await client.post(f"/api/v1/theses/{thesis_id}/archive",
                                 json={"acknowledge": True})
        assert done.status_code == 200, done.text
        assert done.json()["archived"] is True
        assert done.json()["rows_deleted"] == 0

        # **خرجت من القائمة** — ولم تُحذف.
        assert not [row for row in (await client.get("/api/v1/theses")).json()
                    if row["id"] == str(thesis_id)]
        archived = (await client.get("/api/v1/theses", params={"view": "archived"})).json()
        assert [row["id"] for row in archived] == [str(thesis_id)]
        assert archived[0]["actions"]["is_archived"] is True
        assert archived[0]["actions"]["primary"] == "restore"

    # **ولا صفَّ نقص** — وهو بيتُ القصيد.
    assert await census() == before, "الأرشفة حذفت صفوفًا"

    async with _client(tid, uid) as client:
        back = await client.post(f"/api/v1/theses/{thesis_id}/restore")
        assert back.status_code == 200, back.text
        assert back.json()["archived"] is False
        listed = (await client.get("/api/v1/theses")).json()
        assert str(thesis_id) in {row["id"] for row in listed}, "الاسترجاع لم يُعدها"

    assert await census() == before
    # وملفُّ المكتبة لم يُمسّ في شيءٍ من ذلك.
    from athera_api.models.files import File
    async with tenant_session(tid, uid) as session:
        record = (await session.execute(
            select(File).where(File.id == file_id))).scalar_one()
        assert record.trashed_at is None


@requires_db
@pytest.mark.asyncio
async def test_over_http_a_disposable_thesis_archives_without_an_acknowledgement(two_tenants):
    """**ولا يُسأل الباحث عمّا لا يقوم عليه شيء.** سؤالٌ يُطرح دائمًا لا يُقرأ."""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _ = await _seed(tid, uid, filename="لا شيء عليها.pdf")

    async with _client(tid, uid) as client:
        preview = await client.get(f"/api/v1/theses/{thesis_id}/removal-preview")
        assert preview.status_code == 200, preview.text
        assert preview.json()["needs_acknowledgement"] is False

        done = await client.post(f"/api/v1/theses/{thesis_id}/archive", json={})
        assert done.status_code == 200, done.text
        assert done.json()["archived"] is True


@requires_db
@pytest.mark.asyncio
async def test_over_http_mining_a_thesis_with_no_extracted_title_never_returns_5xx(
        two_tenants):
    """**رسالةٌ بلا عنوانٍ مستخرَج كانت تُسقط التنقيب بخمسمئة.**

    `theses.title_ar` عمودٌ يقبل `NULL` (ترحيل 0015)، و`ThesisFacts.title`
    كان موصوفًا `str`. فـ`" ".join([facts.title, …])` يسقط بـ`TypeError`،
    ويُردّ الباحثُ بخمسمئة على مسارٍ صحيحٍ تمامًا: رسالةٌ فُكِّكت بالمسار
    القديم فصار عندها أقسامٌ ونتائج، ولم يُستخرَج عنوانها بعد.

    **والعلاجُ لا يخترع عنوانًا**: ما يقوم على العنوان يُعلَّق ويُقال عددُه،
    وما يقوم على السؤال يُقترح كما هو.
    """
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    # `title_ar=None` صراحةً — وهي حالُ كلّ رسالةٍ رُفعت ولم تُقرأ بعد.
    thesis_id, _ = await _seed(tid, uid, filename="بلا عنوان.pdf", title_ar=None)
    await _give_the_miner_something_to_read(tid, uid, thesis_id)

    async with _client(tid, uid) as client:
        response = await client.post(f"/api/v1/theses/{thesis_id}/mine-opportunities")

    assert response.status_code < 500, f"خمسمئة على مسارٍ صحيح: {response.text}"
    assert response.status_code == 202, response.text
    body = response.json()
    # المقترحُ المعلَّق بالسؤال قائم، والمعلَّق بالعنوان مؤجَّلٌ ومعلَنٌ عددُه.
    assert body["opportunities_created"] >= 1
    assert body["withheld_for_missing_title"] >= 1
    assert body["title_note"], "عُلِّقت مقترحاتٌ بلا أن يُقال لماذا"

    async with _client(tid, uid) as client:
        card = next(row for row in (await client.get("/api/v1/theses")).json()
                    if row["id"] == str(thesis_id))
    # **ولا عنوانَ مخترَع** تسرّب إلى العمود ولا إلى البطاقة.
    assert card["title_ar"] is None
    assert card["title"] is None


@requires_db
@pytest.mark.asyncio
async def test_over_http_legacy_parse_never_drags_the_state_back_to_extracting(two_tenants):
    """**المسار القديم كان يكتب حالًا بائتة فوق حالٍ أحدث.**

    التسلسل المعروف: الخطُّ الحديث يبلغ `ready_for_review`، ثمّ يُشغَّل
    التفكيك القديم بعده. وكان يقرأ الحال في أوّل الطلب ويكتبها بلا شرط، فإن
    كانت `extracting` وقتَ القراءة عادت البطاقة إليها بعد أن بلغت المراجعة
    — وتبقى كذلك بلا مهمّةٍ ترفعها.

    **والحالُ النهائية هنا يجب أن تبقى قانونية**، ولا تصير `extracting`
    ولا تبقى عليها.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import Thesis
    from athera_api.services.thesis import processing

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _ = await _seed(tid, uid, filename="تسلسلٌ معروف.pdf")

    # ١ — الخطُّ الحديث يبلغ المراجعة.
    async with tenant_session(tid, uid) as session:
        await processing.mark(session, tenant_id=tid, thesis_id=thesis_id,
                              state=processing.READY_FOR_REVIEW)

    # ٢ — ثمّ يُشغَّل التفكيك القديم بعده. والملفّ في التجهيزة بلا محتوًى
    #     صالح، فيُردّ الطلب بـ٤٢٢ — **والحال هي المفحوصة لا رمزُ الردّ**.
    async with _client(tid, uid) as client:
        parsed = await client.post(f"/api/v1/theses/{thesis_id}/parse")
    assert parsed.status_code < 500, f"خمسمئة من التفكيك: {parsed.text}"

    async with tenant_session(tid, uid) as session:
        state = (await session.execute(
            select(Thesis.processing_state).where(Thesis.id == thesis_id))).scalar_one()

    assert state != processing.EXTRACTING, "التفكيك أعاد الحال إلى «جارٍ الاستخراج»"
    assert state not in processing.IN_FLIGHT, (
        f"التفكيك ترك حالًا جاريةً بلا مهمّةٍ ترفعها: {state}")
    assert state in processing.PROCESSING_STATES


@requires_db
@pytest.mark.asyncio
async def test_over_http_the_settle_rule_is_evaluated_at_write_time(two_tenants):
    """**والشرطُ يُقيَّم وقت الكتابة** — فتُجرَّب الدالّة على حالٍ تغيّرت.

    ويُبلَغ الحدُّ من طرف الخدمة مباشرةً: تُوضع الرسالة في `extracting` ثمّ
    يُطلب التثبيت، فيجب أن تبقى كما هي — لا أن تُرفع ولا أن تُخفض.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import Thesis
    from athera_api.services.thesis import processing

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]

    async def settle_from(state: str) -> str:
        thesis_id, _ = await _seed(tid, uid, filename=f"{state}.pdf")
        async with tenant_session(tid, uid) as session:
            await processing.mark(
                session, tenant_id=tid, thesis_id=thesis_id, state=state,
                failure_code="parse_failed" if state == processing.FAILED else (
                    "text_layer_missing" if state == processing.TEXT_LAYER_MISSING
                    else None),
                text_layer=(processing.TEXT_LAYER_ABSENT
                            if state == processing.TEXT_LAYER_MISSING else None))
        async with tenant_session(tid, uid) as session:
            await processing.settle_after_legacy_parse(
                session, tenant_id=tid, thesis_id=thesis_id)
        async with tenant_session(tid, uid) as session:
            return (await session.execute(
                select(Thesis.processing_state)
                .where(Thesis.id == thesis_id))).scalar_one()

    # ما يجوز رفعه يُرفع.
    for state in processing.LEGACY_PARSE_MAY_SETTLE:
        assert await settle_from(state) == processing.READY_FOR_REVIEW, state

    # **وما لا يجوز يبقى حرفيًّا** — ومنها الحالُ الجارية بعينها.
    for state in (processing.EXTRACTING, processing.PARSING, processing.QUEUED,
                  processing.AWAITING_CONSENT, processing.COMPLETED):
        assert await settle_from(state) == state, f"التثبيت غيّر حالًا ليست له: {state}"


# ═════════════════════ ٨. الإذنُ على الكائن، لا العزل وحده ═════════════════════


@requires_db
@pytest.mark.asyncio
async def test_over_http_a_colleague_in_the_same_tenant_cannot_touch_another_thesis(
        two_tenants):
    """**العزلُ بين المستأجرين لا يحمي بين عضوين تحت المظلّة نفسها.**

    و`files.upload_file` تكتب `ObjectGrant(grant_level="owner")` مع صفّ
    الملفّ، والصلاحية تُقرأ من تلك المِنحة لا من عمود `uploaded_by`. فعضوٌ
    ثانٍ في المستأجر نفسه — مصادَقٌ، وله دورُ باحث — لا مِنحة له على ملفّ
    زميله. فيجب أن يُردّ عن كلّ فعلٍ يمسّ الرسالة.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import Thesis

    a = two_tenants["a"]
    tid, owner = a["tenant_id"], a["user_id"]
    colleague = await _second_member(tid)

    thesis_id, _ = await _seed(tid, owner, filename="ليست لزميلي.pdf",
                               title_ar="رسالةٌ لصاحبها")
    await _give_the_miner_something_to_read(tid, owner, thesis_id)

    async with _client(tid, colleague) as intruder:
        # يراها في مستأجره — والعزلُ وحده لا يمنع ذلك، وهو بيتُ القصيد.
        attempts = {
            "parse": await intruder.post(f"/api/v1/theses/{thesis_id}/parse"),
            "mine": await intruder.post(
                f"/api/v1/theses/{thesis_id}/mine-opportunities"),
            "preview": await intruder.get(
                f"/api/v1/theses/{thesis_id}/removal-preview"),
            "archive": await intruder.post(
                f"/api/v1/theses/{thesis_id}/archive", json={"acknowledge": True}),
            "restore": await intruder.post(f"/api/v1/theses/{thesis_id}/restore"),
        }

    for name, response in attempts.items():
        assert response.status_code == 403, f"{name} مرّ بلا إذنٍ على الكائن: {response.text}"
        assert response.json()["error"]["code"] == "authz.forbidden", name

    # **ولم يقع شيء**: الرسالة كما تركها صاحبها، ولا فرصةَ كُتبت عليها.
    async with tenant_session(tid, owner) as session:
        row = (await session.execute(
            select(Thesis).where(Thesis.id == thesis_id))).scalar_one()
        assert row.archived_at is None, "زميلٌ أرشف رسالةَ غيره"
        assert row.parsed_at is None, "زميلٌ فكّك رسالةَ غيره"
        assert row.opportunities_mined_at is None, "زميلٌ نقّب في رسالةِ غيره"


@requires_db
@pytest.mark.asyncio
async def test_over_http_the_owner_of_the_linked_file_still_passes_every_action(two_tenants):
    """**والحارسُ لا يُغلق البابَ على صاحبه.**

    فحصُ منعٍ بلا فحصِ سماحٍ يمرّ على حارسٍ يردّ الجميع — وذاك عطبٌ آخر.
    """
    a = two_tenants["a"]
    tid, owner = a["tenant_id"], a["user_id"]
    thesis_id, _ = await _seed(tid, owner, filename="لصاحبها.pdf", title_ar="رسالتي")

    async with _client(tid, owner) as client:
        assert (await client.get(
            f"/api/v1/theses/{thesis_id}/removal-preview")).status_code == 200
        assert (await client.post(
            f"/api/v1/theses/{thesis_id}/mine-opportunities")).status_code == 202
        archived = await client.post(f"/api/v1/theses/{thesis_id}/archive", json={})
        assert archived.status_code == 200, archived.text
        assert (await client.post(
            f"/api/v1/theses/{thesis_id}/restore")).status_code == 200


# ═════════════════════ ٩. لا فعلَ دورةِ حياةٍ أثناء عملٍ جارٍ ═════════════════════


@requires_db
@pytest.mark.asyncio
async def test_over_http_the_server_refuses_to_archive_while_work_is_running(two_tenants):
    """**الخادمُ يفرض الحدّ، لا الشاشةُ وحدها.**

    من نادى النقطة مباشرةً وهي جارية كان يمرّ. ولا عقدَ إلغاءٍ في هذا
    المنتج، فالمهمّة تمضي وتكتب مرشّحاتها لسجلٍّ غاب عن الشاشة.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import Thesis
    from athera_api.services.thesis import processing

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]

    for state in processing.IN_FLIGHT:
        thesis_id, _ = await _seed(tid, uid, filename=f"{state}.pdf")
        async with tenant_session(tid, uid) as session:
            await processing.mark(session, tenant_id=tid, thesis_id=thesis_id,
                                  state=state)

        async with _client(tid, uid) as client:
            refused = await client.post(f"/api/v1/theses/{thesis_id}/archive",
                                        json={"acknowledge": True})
            assert refused.status_code == 409, f"{state}: {refused.text}"
            assert refused.json()["error"]["code"] == "thesis.processing_in_flight"
            # والبطاقة تقول ذلك أيضًا، بالسبب نفسه.
            card = next(row for row in (await client.get("/api/v1/theses")).json()
                        if row["id"] == str(thesis_id))
            assert card["actions"]["can_archive"] is False
            assert card["actions"]["can_trash_file"] is False
            assert card["actions"]["lifecycle_blocked_reason"]

        async with tenant_session(tid, uid) as session:
            row = (await session.execute(
                select(Thesis).where(Thesis.id == thesis_id))).scalar_one()
            assert row.archived_at is None, f"{state}: أُرشفت أثناء عملٍ جارٍ"


@requires_db
@pytest.mark.asyncio
async def test_the_old_server_can_still_write_a_thesis_on_the_new_schema(two_tenants):
    """**نافذةُ النشر المتدحرج**: خادمُ الموجة الأولى على مخطَّط 0030.

    بين ترحيل القاعدة ونشر الموجة نافذةٌ يخدم فيها الخادمُ القائم (واجهة
    v88) مخطَّطًا لا يعرف عموديه الجديدين. وهو يُدرج صفوفَ رسائل بقائمة
    أعمدةٍ صريحة يولّدها SQLAlchemy من نماذجه — فلا ذكر لـ`archived_at` ولا
    `archived_by` فيها.

    فيُحاكى ذلك حرفيًّا: `INSERT` بالأعمدة التي يعرفها 0029 وحدها. ويجب أن
    ينجح، وأن يأخذ العمودان `NULL` — ومعناها «غير مؤرشَفة»، وهي الحالُ
    الصحيحة لكلّ ما يكتبه ذلك الخادم. **ولو كان أحدُهما إلزاميًّا أو ذا
    افتراضٍ كاتب، لسقط كلُّ رفعِ رسالةٍ في تلك النافذة بخمسمئة.**

    (وهو الدرسُ نفسه المكتوب في 0028/0029، مطبَّقًا على هذا الترحيل.)
    """
    from sqlalchemy import text

    from athera_api.db import system_session

    a = two_tenants["a"]
    tid = a["tenant_id"]
    thesis_id = uuid.uuid4()

    async with system_session() as session:
        head = (await session.execute(
            text("SELECT version_num FROM alembic_version"))).scalar_one()
        if head < "0030":
            pytest.skip(f"قاعدةُ الاختبارات عند {head}، والعمودان يُضافان في 0030")

        # **بأعمدة 0029 وحدها** — لا ذكرَ للعمودين الجديدين، كخادمِ v88.
        await session.execute(
            text("INSERT INTO theses (id, tenant_id, title_ar, degree, "
                 "processing_state, processing_attempts, text_layer_state, ocr_state) "
                 "VALUES (:id, :tenant, :title, 'masters', 'uploaded', 0, "
                 "'not_checked', 'unavailable')"),
            {"id": thesis_id, "tenant": tid, "title": "رسالةٌ كتبها الخادمُ القديم"})

        row = (await session.execute(
            text("SELECT archived_at, archived_by FROM theses WHERE id = :id"),
            {"id": thesis_id})).one()

    assert row.archived_at is None, "عمودٌ جديد كُتب فيه شيءٌ لم يطلبه الخادمُ القديم"
    assert row.archived_by is None
    # **وما كتبه الخادمُ القديم يُقرأ «في القائمة»** لا «مؤرشَفًا».
    async with _client(tid, a["user_id"]) as client:
        listed = (await client.get("/api/v1/theses")).json()
    card = next(row for row in listed if row["id"] == str(thesis_id))
    assert card["archived_at"] is None
    assert card["actions"]["is_archived"] is False
