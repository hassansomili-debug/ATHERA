"""الاكتمالُ يعني شيئًا | Stage completion must mean something (RC-0 §24، §32–§37).

**أخطرُ عطبٍ يمكن أن يحمله ملفُّ المراحل أن يعدّ وجودَ صفٍّ إنجازًا.**

    مصدرٌ مربوط    ≠  الدراساتُ السابقة قُرئت
    مجموعةُ بيانات  ≠  التحليلُ تمّ
    مخطوطةٌ قائمة   ≠  الورقةُ كُتبت
    أداةٌ مُنشأة    ≠  ثمّة ما يقيس

ومنظومةٌ تفعل ذلك تُخبر الباحثَ أنّه أنجز ما لم يبدأه. فكلُّ فحصٍ هنا يقابل
**وجودَ الشيء** بـ**تمامِ معناه**، ويفشل إن سُوّي بينهما.

وتُفحص معه ثلاثةُ حدودٍ أخرى: أن المنهجَ لا يُستنبط، وأنّ الأداةَ والبيانات
ليستا شرطًا على كلّ بحث، وأنّ الرحلةَ بلا نسبةِ إنجاز.
"""
from __future__ import annotations

import pytest

from athera_api.research_brain import stages as s

P = "project-1"


def derive(**kw) -> s.JourneyStages:
    return s.derive(s.StageFacts(**kw), project_id=P)


def status_of(key: s.StageKey, **kw) -> s.StageStatus:
    return derive(**kw).by_key(key).status


# ═════════════════ أ · بحثٌ خاوٍ يعمل ولا يخترع (§25، §89) ═════════════════


def test_an_empty_project_starts_at_the_idea_and_invents_nothing():
    out = derive()
    assert out.current is s.StageKey.IDEA
    assert out.by_key(s.StageKey.IDEA).is_current is True
    assert out.by_key(s.StageKey.IDEA).status is s.StageStatus.NOT_STARTED
    assert out.completed == ()
    assert "لا سؤالَ" in out.by_key(s.StageKey.IDEA).reason_ar


def test_every_stage_always_carries_a_reason_in_both_languages():
    """**ولا حالَ بلا تفسير** (§43) — في كلّ تركيبةٍ لا في الخاوية وحدها."""
    for facts in (s.StageFacts(),
                  s.StageFacts(questions=1, sources_linked=2),
                  s.StageFacts(questions=1, has_method_row=True,
                               study_type="quantitative", datasets=1,
                               analysis_runs=1, analysis_outputs=2, findings=1,
                               manuscripts=1, sections_with_text=3,
                               sections_approved=1)):
        for row in s.derive(facts, project_id=P).stages:
            assert row.reason_ar.strip() and row.reason_en.strip()
            assert row.title_ar.strip() and row.title_en.strip()


# ═════════════════ ب · وجودُ الصفّ ليس اكتمالًا (§24) ═════════════════


def test_linked_sources_do_not_complete_the_literature_stage():
    """**§27 — مصدرٌ مربوطٌ ليس دراسةً مقروءة.**"""
    out = derive(questions=1, sources_linked=5, sources_included=5)
    assert out.by_key(s.StageKey.REFERENCES).status is s.StageStatus.COMPLETED
    assert out.by_key(s.StageKey.LITERATURE).is_current is True
    assert out.by_key(s.StageKey.LITERATURE).status is s.StageStatus.NOT_STARTED


def test_saved_sources_alone_do_not_complete_references():
    """**و«محفوظ» ليس «مُدرَجًا»** — والإدراجُ قرارٌ له صاحبٌ ووقت."""
    assert status_of(s.StageKey.REFERENCES,
                     questions=1, sources_linked=4) is s.StageStatus.NEEDS_ACTION
    assert status_of(s.StageKey.REFERENCES, questions=1, sources_linked=4,
                     sources_included=1) is s.StageStatus.COMPLETED


def test_a_dataset_alone_does_not_complete_the_analysis_stage():
    out = derive(questions=1, has_method_row=True, study_type="quantitative",
                 datasets=1)
    assert out.by_key(s.StageKey.DATA).status is s.StageStatus.COMPLETED
    assert out.by_key(s.StageKey.ANALYSIS).status is not s.StageStatus.COMPLETED


def test_a_manuscript_shell_does_not_complete_the_paper_stage():
    """**§37 — مخطوطةٌ قائمةٌ ليست ورقةً مكتوبة.**"""
    assert status_of(s.StageKey.PAPER,
                     manuscripts=1) is s.StageStatus.NEEDS_ACTION
    assert status_of(s.StageKey.PAPER, manuscripts=1,
                     sections_with_text=3) is s.StageStatus.NEEDS_ACTION
    assert status_of(s.StageKey.PAPER, manuscripts=1, sections_with_text=3,
                     sections_approved=2) is s.StageStatus.COMPLETED


def test_an_instrument_without_items_is_not_complete():
    """**§95 — أداةٌ بلا بنودٍ قشرة**، والبندُ هو ما يقيس."""
    base = dict(questions=1, has_method_row=True, study_type="quantitative")
    assert status_of(s.StageKey.INSTRUMENT, **base,
                     instruments=1) is s.StageStatus.NEEDS_ACTION
    assert status_of(s.StageKey.INSTRUMENT, **base, instruments=1,
                     instrument_items=12) is s.StageStatus.COMPLETED


def test_an_empty_method_row_is_not_a_design():
    """**وصفُّ منهجٍ بلا نوعٍ ليس تصميمًا.**"""
    assert status_of(s.StageKey.DESIGN, questions=1,
                     has_method_row=True) is s.StageStatus.NOT_STARTED
    assert status_of(s.StageKey.DESIGN, questions=1, has_method_row=True,
                     study_type="qualitative") is s.StageStatus.COMPLETED


def test_read_studies_do_not_complete_synthesis():
    """**§29 — التركيبُ مخرَجٌ، لا أثرٌ جانبيّ لقراءة الدراسات.**"""
    base = dict(questions=1, sources_linked=3, sources_included=3,
                matrix_sources=3, matrix_cells_known=20)
    assert status_of(s.StageKey.LITERATURE, **base) is s.StageStatus.COMPLETED
    assert status_of(s.StageKey.SYNTHESIS, **base) is s.StageStatus.NOT_STARTED
    # ومحاورُ بلا فجوةٍ ما زالت ناقصة.
    assert status_of(s.StageKey.SYNTHESIS, **base,
                     themes=4) is s.StageStatus.NEEDS_ACTION
    assert status_of(s.StageKey.SYNTHESIS, **base, themes=4,
                     gaps=1) is s.StageStatus.COMPLETED


# ═════════════════ ج · النتيجةُ تلزمها تشغيلة (§36) ═════════════════


def test_a_finding_is_never_implied_without_analysis_output():
    """**أخطرُ ثابتٍ هنا**: لا نتيجةَ بلا مخرَجِ تحليلٍ تُشتقّ منه.

    ومنظومةٌ تعرض «نتائج» بلا سندٍ تُعلّم الباحثَ أن يبني ورقةً على رقمٍ
    لا أصلَ له.
    """
    base = dict(questions=1, has_method_row=True, study_type="quantitative",
                datasets=1)
    # لا تشغيلةَ بعد.
    assert status_of(s.StageKey.ANALYSIS, **base) is s.StageStatus.NOT_STARTED
    # جرت تشغيلةٌ ولم تُنتج مخرَجًا.
    assert status_of(s.StageKey.ANALYSIS, **base,
                     analysis_runs=1) is s.StageStatus.NEEDS_ACTION
    # ومخرجاتٌ بلا نتيجةٍ تُشتقّ منها ما تزال ناقصة.
    assert status_of(s.StageKey.ANALYSIS, **base, analysis_runs=1,
                     analysis_outputs=3) is s.StageStatus.NEEDS_ACTION
    assert status_of(s.StageKey.ANALYSIS, **base, analysis_runs=1,
                     analysis_outputs=3, findings=2) is s.StageStatus.COMPLETED


def test_analysis_is_blocked_without_data_and_says_so():
    """**§44 — المنعُ يُسمّى**، ومعه ما يلزم لرفعه."""
    stage = derive(questions=1).by_key(s.StageKey.ANALYSIS)
    assert stage.status is s.StageStatus.BLOCKED
    assert stage.blocking_reasons == (s.NEEDS_DATA,)
    assert stage.reason_ar.strip()


# ═════════════════ د · ولا يُفترض منهجٌ (§32، §34، §51) ═════════════════


@pytest.mark.parametrize("study_type, expected", [
    (None, s.StageStatus.OPTIONAL),
    ("qualitative", s.StageStatus.OPTIONAL),
    ("review", s.StageStatus.OPTIONAL),
    ("quantitative", s.StageStatus.NOT_STARTED),
    ("experimental", s.StageStatus.NOT_STARTED),
    ("mixed_methods", s.StageStatus.NOT_STARTED),
])
def test_the_instrument_is_required_only_where_the_method_calls_for_it(
        study_type, expected):
    """**ودراسةٌ كيفيةٌ لا تُوقَف بحجّةِ أداةٍ لا تخصّها.**"""
    facts = s.StageFacts(questions=1, has_method_row=study_type is not None,
                         study_type=study_type)
    got = s.derive(facts, project_id=P).by_key(s.StageKey.INSTRUMENT).status
    assert got is expected


def test_a_dataset_never_makes_the_method_known():
    """**§51 — المجهولُ يبقى مجهولًا.**

    ووجودُ بياناتٍ استنباطٌ مغرٍ: «ثمّة أرقام، إذن البحثُ كمّي». وهو حكمٌ
    على منهج باحثٍ لم يقله.
    """
    facts = s.StageFacts(questions=1, datasets=3, analysis_runs=2)
    assert facts.method_recorded is False
    assert facts.measurement_expected is False
    known = {row.key: row for row in s.known_facts(facts)}
    assert known["method"].known is False
    assert known["method"].value_ar == ""


def test_a_qualitative_project_is_not_blocked_on_data():
    """**ولا حاجزَ كمّيٌّ كونيّ** (§34)."""
    out = derive(questions=1, has_method_row=True, study_type="qualitative",
                 sources_linked=2, sources_included=2, matrix_cells_known=4,
                 matrix_sources=2, gaps=1)
    assert out.by_key(s.StageKey.DATA).status is s.StageStatus.OPTIONAL
    assert out.by_key(s.StageKey.INSTRUMENT).status is s.StageStatus.OPTIONAL
    # فالمرحلةُ الحاليّة تتجاوزهما إلى ما يلزم فعلًا — والتحليلُ متوقّفٌ
    # بلا بيانات، فلا يُدعى إليه.
    assert out.current is s.StageKey.PAPER


# ═════════════════ هـ · حتميّةٌ، ومرحلةٌ حاليّة واحدة (§46، §101) ═════════════════


def test_the_same_state_always_gives_the_same_journey():
    facts = s.StageFacts(questions=1, sources_linked=2, sources_included=1)
    runs = [tuple((r.key.value, r.status.value)
                  for r in s.derive(facts, project_id=P).stages) for _ in range(8)]
    assert len(set(runs)) == 1


def test_the_stage_order_is_fixed_and_nine():
    keys = [row.key for row in derive().stages]
    assert keys == list(s.ORDER)
    assert len(keys) == 9


def test_exactly_one_stage_is_current():
    for facts in (s.StageFacts(),
                  s.StageFacts(questions=1),
                  s.StageFacts(questions=1, sources_linked=1, sources_included=1)):
        rows = s.derive(facts, project_id=P).stages
        assert sum(1 for r in rows if r.is_current) == 1


def test_a_blocked_stage_is_never_relabelled_current():
    """**ولا يُدعى الباحثُ إلى بابٍ مغلق.**

    الدراساتُ السابقة أوّلُ ما لم يكتمل حين لا مصادر، لكنّها متوقّفةٌ
    بسببها — فتبقى متوقّفةً وتُعرض الحاليّةُ حيث يمكن العمل.
    """
    out = derive(questions=1)
    assert out.current is s.StageKey.REFERENCES
    assert out.by_key(s.StageKey.REFERENCES).is_current is True
    blocked = out.by_key(s.StageKey.LITERATURE)
    assert blocked.status is s.StageStatus.BLOCKED and blocked.is_current is False


# ═════════════════ و · ولا نسبةَ إنجاز، ولا لغةَ داخلية (§18، §23) ═════════════════


def test_no_stage_text_carries_a_completion_percentage():
    rich = s.StageFacts(questions=2, objectives=3, sources_linked=9,
                        sources_included=7, matrix_sources=7,
                        matrix_cells_known=40, themes=5, contradictions=2,
                        gaps=3, has_method_row=True, study_type="quantitative",
                        theories=1, constructs=4, instruments=1,
                        instrument_items=22, datasets=2, analysis_runs=3,
                        analysis_outputs=9, findings=4, manuscripts=1,
                        sections_with_text=6, sections_approved=2)
    for row in s.derive(rich, project_id=P).stages:
        blob = " ".join([row.reason_ar, row.reason_en, row.summary_ar,
                         row.summary_en])
        for shape in ("%", "٪", "percent"):
            assert shape not in blob, f"نسبةٌ ظهرت في {row.key.value}: {shape}"


def test_no_internal_vocabulary_reaches_the_researcher():
    """**§18 — لا اسمَ جدولٍ ولا عمودٍ ولا رمزَ حالةٍ في وجه الباحث.**"""
    leaks = ("literature_matrix_cells", "project_sources", "analysis_outputs",
             "interpretations", "thread_elements", "cell_state", "use_state",
             "fingerprint", "ontology", "StageFacts")
    for row in s.derive(s.StageFacts(questions=1, sources_linked=2),
                        project_id=P).stages:
        blob = " ".join([row.title_ar, row.title_en, row.reason_ar,
                         row.reason_en, row.summary_ar, row.summary_en])
        for word in leaks:
            assert word not in blob, f"مفردةٌ داخلية ظهرت: {word}"


def test_no_thesis_vocabulary_anywhere_in_the_journey():
    """**§108 — الرحلةُ لا تعرف مركزَ الرسائل.**

    **والفحصُ بالكلمة لا بالجزء**: «synthesis» تحتوي «thesis» حرفًا، وحارسٌ
    يقرأ الأجزاء يُسقط مرحلةً سليمةً باسمها — ثمّ يُضعَّف الحارسُ ليمرّ،
    فلا يحرس شيئًا. وقد وقع ذلك هنا فعلًا قبل أن يُصلَح.
    """
    import re

    for row in s.derive(s.StageFacts(questions=1), project_id=P).stages:
        blob = " ".join([row.title_ar, row.title_en, row.reason_ar, row.reason_en,
                         row.route or ""]).lower()
        for word in ("thesis", "mining", "رسالة", "تنقيب"):
            assert not re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", blob), (
                f"مفردةُ مركزِ الرسائل ظهرت: {word} — في {row.key.value}")


# ═════════════════ ز · المنعُ بنيويّ، والناقصُ مصنَّف ═════════════════


def test_a_blocked_stage_cannot_exist_without_a_named_reason():
    with pytest.raises(ValueError, match="بلا سببٍ مسمّى"):
        s.Stage(key=s.StageKey.DATA, status=s.StageStatus.BLOCKED,
                title_ar="ع", title_en="x", reason_ar="ع", reason_en="x")


def test_reasons_may_not_be_attached_to_an_unblocked_stage():
    with pytest.raises(ValueError, match="أسبابُ منعٍ"):
        s.Stage(key=s.StageKey.DATA, status=s.StageStatus.COMPLETED,
                title_ar="ع", title_en="x", reason_ar="ع", reason_en="x",
                blocking_reasons=("no_data_available",))


def test_missing_items_are_graded_not_piled_into_one_red_list():
    """**§49 — ثلاثُ رتبٍ لا قائمةٌ واحدة.**"""
    facts = s.StageFacts(questions=1)
    grades = {m.key: m.severity
              for m in s.missing_items(facts, s.derive(facts, project_id=P))}
    assert grades["literature"] == s.BLOCKING
    assert grades["instrument"] == s.OPTIONAL_GAP
    assert grades["references"] == s.RECOMMENDED
    # وما اكتمل لا يُعدّ ناقصًا.
    assert "idea" not in grades


def test_every_stage_routes_somewhere_and_carries_the_project():
    for row in derive().stages:
        assert row.route and row.route.startswith("/")
        assert "{project_id}" not in row.route
