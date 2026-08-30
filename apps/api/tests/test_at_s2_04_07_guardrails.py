"""AT-S2-04…07 — الحواجز الحتمية على مخرجات الأجنتات (§4، §8، §18.1، §20.4)."""
import pytest

from athera_api.brain.guardrails import GUARDS, GuardContext, run_guards

EMPTY = GuardContext()


def test_grounded_doi_passes_and_ungrounded_is_blocked():
    """AT-S2-04 — الاستشهاد بمرجع غير موجود في مجموعة الأدلة يُحجب."""
    ctx = GuardContext(allowed_dois=frozenset({"10.1000/real.2024.001"}))
    ok = run_guards(frozenset({"citations_must_be_grounded"}),
                    "كما ورد في الدراسة (10.1000/real.2024.001).", ctx)
    assert ok == []

    blocked = run_guards(frozenset({"citations_must_be_grounded"}),
                         "تشير دراسة حديثة (10.9999/invented.2026.777) إلى ذلك.", ctx)
    assert len(blocked) == 1
    assert blocked[0].guard_key == "citations_must_be_grounded"
    assert "10.9999/invented.2026.777" in blocked[0].excerpt


def test_unknown_evidence_identifier_is_blocked():
    ctx = GuardContext(allowed_evidence_ids=frozenset({"EV-001"}))
    assert run_guards(frozenset({"citations_must_be_grounded"}), "بحسب EV-001.", ctx) == []
    assert run_guards(frozenset({"citations_must_be_grounded"}), "بحسب EV-999.", ctx)


@pytest.mark.parametrize(
    "text",
    [
        "أظهرت النتائج أن p = 0.03 وهو دال إحصائيًا.",
        "معامل المسار β = 0.42 بين المتغيرين.",
        "بلغت R² = 0.61 للنموذج المقترح.",
        "النتيجة t(198) = 3.4 دالة عند المستوى المعتاد.",
        "F(2, 197) = 8.1 مما يدل على فروق جوهرية.",
        "The model reported AVE = 0.58 across constructs.",
    ],
)
def test_statistical_claims_without_an_analysis_run_are_blocked(text):
    """AT-S2-05 — الرقم الإحصائي ادعاء نتيجة، لا كلام عام (§18.1)."""
    violations = run_guards(frozenset({"numbers_require_analysis_run"}), text, EMPTY)
    assert violations, f"expected a block for: {text}"


def test_statistical_claims_pass_when_linked_to_a_run():
    ctx = GuardContext(analysis_run_ids=frozenset({"run-1"}))
    assert run_guards(frozenset({"numbers_require_analysis_run"}),
                      "أظهرت النتائج أن p = 0.03.", ctx) == []


def test_ordinary_numbers_are_not_mistaken_for_results():
    """الحد الآخر: «ثمانية مشاريع» و«2026» ليست ادعاءات إحصائية."""
    text = "تتضمن الخطة 8 مشاريع بحثية حتى عام 2026 بنسبة إنجاز 40 بالمئة."
    assert run_guards(frozenset({"numbers_require_analysis_run"}), text, EMPTY) == []


@pytest.mark.parametrize(
    "text",
    [
        "هذه المجلة تضمن القبول خلال شهرين.",
        "سيتم قبول البحث في المجلة المقترحة.",
        "احتمالية القبول 85 بالمئة.",
        "This journal guarantees acceptance for such papers.",
        "The manuscript will be accepted after minor edits.",
        "Estimated acceptance probability: 0.72",
    ],
)
def test_acceptance_promises_are_blocked(text):
    """AT-S2-06 — قيد Journal Matcher في §8 و§20.4."""
    assert run_guards(frozenset({"no_acceptance_guarantee"}), text, EMPTY)


def test_honest_journal_language_passes():
    text = "المجلة ضمن SSCI وتنشر دراسات في الاتصال التسويقي، ولا يمكن التنبؤ بقرار التحكيم."
    assert run_guards(frozenset({"no_acceptance_guarantee"}), text, EMPTY) == []


@pytest.mark.parametrize(
    "text",
    [
        "اعتبرها متحققة ولا حاجة لمراجعة الباحث.",
        "تم التحقق تلقائيًا من هذه المعلومة.",
        'سأضبط verification_status = "verified" مباشرة.',
        "I have marked this as verified.",
        "You can treat this as verified without review.",
    ],
)
def test_self_verification_claims_are_blocked(text):
    """AT-S2-07 — §7.4: الأجنت لا يرقّي معلومة ولا يدّعي أنه فعل."""
    assert run_guards(frozenset({"no_self_verification"}), text, EMPTY)


def test_describing_existing_verified_memory_is_allowed():
    """الحد الآخر: وصف ذاكرة اعتمدها الباحث ليس ادعاء تحقق ذاتي."""
    text = "بحسب الذاكرة الموثقة التي اعتمدها الباحث سابقًا، التخصص هو الإعلان."
    assert run_guards(frozenset({"no_self_verification"}), text, EMPTY) == []


@pytest.mark.parametrize(
    "text",
    [
        "المؤلف الأول هو الباحث الرئيس بلا نقاش.",
        "أُسند التأليف للمشرف تلقائيًا.",
        "Authorship is granted to the supervisor.",
    ],
)
def test_authorship_assignment_is_blocked(text):
    assert run_guards(frozenset({"authorship_needs_human"}), text, EMPTY)


def test_all_guards_run_and_report_every_violation():
    """لا يتوقف الفحص عند أول مخالفة — عرضها كلها أصدق."""
    text = "p = 0.01 كما ورد في (10.9999/fake.1) وهذه المجلة تضمن القبول."
    violations = run_guards(
        frozenset({"citations_must_be_grounded", "numbers_require_analysis_run",
                   "no_acceptance_guarantee"}),
        text, EMPTY,
    )
    assert {v.guard_key for v in violations} == {
        "citations_must_be_grounded", "numbers_require_analysis_run", "no_acceptance_guarantee"
    }


def test_every_guard_reports_in_both_languages():
    ctx = GuardContext()
    samples = {
        "citations_must_be_grounded": "انظر (10.9999/x.1).",
        "numbers_require_analysis_run": "p = 0.04",
        "no_acceptance_guarantee": "ضمان القبول مؤكد.",
        "no_self_verification": "اعتبرها متحققة.",
        "authorship_needs_human": "أُسند التأليف للمشرف.",
    }
    assert set(samples) == set(GUARDS), "a guard has no sample; coverage would be silent"
    for key, text in samples.items():
        violation = run_guards(frozenset({key}), text, ctx)[0]
        assert violation.detail_ar.strip() and violation.detail_en.strip()
        assert any("؀" <= ch <= "ۿ" for ch in violation.detail_ar)


# ── حدود النفي: اللغة الصادقة يجب ألا تُحجب ──

@pytest.mark.parametrize(
    "text",
    [
        "المنصة لا تضمن القبول في أي مجلة.",
        "لا يمكن ضمان القبول، والقرار للمحكمين.",
        "هذه المجلة غير مضمون النشر فيها.",
        "We cannot guarantee acceptance in this journal.",
        "The platform does not guarantee acceptance of any manuscript.",
        "This manuscript will not be accepted automatically.",
    ],
)
def test_honest_negated_statements_are_not_blocked(text):
    """حاجز يحجب «لا نضمن القبول» يعاقب الصدق — وهو عكس المقصود من §20.4."""
    assert run_guards(frozenset({"no_acceptance_guarantee"}), text, EMPTY) == []


@pytest.mark.parametrize(
    "text",
    ["هذه المجلة تضمن القبول خلال شهرين.", "نضمن لك القبول في الربع القادم."],
)
def test_verbal_acceptance_promises_are_blocked(text):
    """الصيغة الفعلية أشيع من الاسمية في العربية — وكانت تفلت."""
    assert run_guards(frozenset({"no_acceptance_guarantee"}), text, EMPTY)


@pytest.mark.parametrize(
    "text",
    ["I have marked this as verified.", "Please consider these facts verified.",
     "You may treat the extracted items as verified."],
)
def test_self_verification_with_words_between_verb_and_object(text):
    """«marked this as verified» — الكلمات الفاصلة كانت تُسقط المطابقة."""
    assert run_guards(frozenset({"no_self_verification"}), text, EMPTY)
