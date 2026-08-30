"""AT-S3-01 — لا ثابت جامعي واحد في الحاسبة (§3).

§3 تنص: «قواعد الترقية يجب ألا تكون Hard-coded على هذه الحالة؛ بل تُدار عبر
Promotion Policy Engine». هذا الاختبار يجعل النص شرط بناء.
"""
import ast
import pathlib
import re

CALCULATOR = pathlib.Path(__file__).resolve().parents[1] / "athera_api/services/promotion/calculator.py"
SCENARIOS = pathlib.Path(__file__).resolve().parents[1] / "athera_api/services/promotion/scenarios.py"

# ألفاظ لا يجوز أن تظهر في محرك عام يخدم أي جامعة.
FORBIDDEN_TOKENS = [
    "الإمام", "Imam", "جامعة الملك", "King Saud", "SSCI", "AHCI", "SCIE", "ESCI",
    "أستاذ مشارك", "associate_professor", "professor",
]


def _source(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _executable_code(path: pathlib.Path) -> str:
    """يعيد الكود القابل للتنفيذ بلا تعليقات ولا docstrings.

    الفحص يستهدف المنطق لا الشرح: توثيق يوضح كيف يُعبَّر عن شرط §20.3 بالآلية
    العامة مفيد، وحظر ذكر اسم فهرس في شرحٍ يعاقب التوثيق الجيد. أما ظهور الاسم
    في الكود نفسه فهو ما يكسر عمومية المحرك (§3).
    """
    tree = ast.parse(_source(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body.pop(0)
    return ast.unparse(tree)


def test_calculator_logic_names_no_institution_or_index():
    """الحاسبة تعرف أنواع القواعد، لا قيم لائحة بعينها."""
    code = _executable_code(CALCULATOR)
    found = [token for token in FORBIDDEN_TOKENS if token in code]
    assert not found, f"institution- or policy-specific tokens leaked into calculator logic: {found}"


def test_index_exclusion_is_driven_by_policy_data_not_code():
    """آلية الاستبعاد عامة: اسم الفهرس يأتي من `conditional_indexes` في اللائحة."""
    code = _executable_code(CALCULATOR)
    assert "conditional_indexes" in code
    # لا مقارنة بأي اسم فهرس بعينه داخل المنطق.
    assert not re.search(r"discard\(\s*[\x27\x22][A-Z]", code)


def test_calculator_contains_no_policy_threshold_literals():
    """لا رقم عتبة مكتوب في الكود: كل عتبة تُقرأ من params."""
    tree = ast.parse(_source(CALCULATOR))
    suspicious = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            # المسموح: 0 و1 (منطق عد)، و365.25 (تحويل أيام إلى سنوات)، و3/60 (تقريب واقتطاع).
            if node.value not in (0, 1, 2, 3, 60, 365.25):
                suspicious.append(node.value)
    assert not suspicious, f"numeric literals that look like policy thresholds: {suspicious}"


def test_every_threshold_is_read_from_rule_params():
    """كل عتبة تصل عبر rule.params — وهذا ما يجعل لائحة أخرى تعمل بلا كود."""
    source = _source(CALCULATOR)
    for key in ("min_years", "min_units", "min_count", "min_points",
                "min_distinct_outlets", "credit_table", "conditional_indexes"):
        assert f'"{key}"' in source, f"{key} is not read from rule params"
    assert 'rule.params.get' in source or 'rule.params[' in source


def test_credit_table_has_no_default_guess():
    """جدول احتساب مفقود ⇒ None (غير محسوب)، لا قيمة افتراضية مخمّنة."""
    from athera_api.services.promotion.calculator import credit_for
    from athera_api.services.promotion.facts import PublicationFact

    publication = PublicationFact(
        publication_id="p", title="t", published_on=None, author_count=4, author_position=3,
        is_corresponding=False, is_refereed=True, is_thesis_derived=False,
        indexes=(), journal_name=None, verification_status="verified",
    )
    assert credit_for({}, publication) is None
    assert credit_for({"sole": 1.0}, publication) is None
    assert credit_for({"4": 0.25}, publication) == 0.25
    assert credit_for({"default": 0.2}, publication) == 0.2


def test_scenarios_never_promise_acceptance():
    """§20.4 — السيناريو يفترض القبول ويقول ذلك، ولا يعد به."""
    source = _source(SCENARIOS)
    assert "غير مضمون" in source
    assert "not guaranteed" in source
    assert not re.search(r"acceptance_probability|احتمالية القبول", source)
