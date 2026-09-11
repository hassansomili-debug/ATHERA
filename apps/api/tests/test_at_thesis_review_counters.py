"""عدّادُ المراجعة | Review counters — ما يقبل قرارًا وحده يُعدّ.

**العطب.** كان `pending = len(FIELD_CATALOGUE) - decided`. والفهرسُ يحمل
حقلين حتميّين — `page_count` و`source_filename` — يقرؤهما الاستخراجُ من
بيانات الملفّ لا من متنه، فلا اقتباسَ لهما بحكم التعريف،
و`approve_candidate` تشترط التأصيل في النصّ. فكان يُعرض للباحث زرُّ اعتمادٍ
لا ينجح أبدًا، ويُحسب الحقلُ «بانتظار مراجعتك» — **عدّادٌ لا يبلغ صفرَه**،
وباحثٌ يُطلب منه فعلٌ لا سبيلَ إليه.

وعطبٌ ثانٍ معه: العدُّ كان من صفوف القاعدة القائمة، فحقلٌ قابلٌ للقرار لم
يُستخرَج له مرشّحٌ يسقط من الفئات الأربع ويظهر في الفرق وحده.

**والقاعدةُ الحاكمة `decidable`** لا اسمُ حقلٍ مكتوبٌ بيد: يُفحص هنا أنّ
الحقلين المذكورين غيرُ قابلين للقرار **لأنّ طريقتَهما حتميّة**، فلو أُضيف
حقلٌ حتميٌّ ثالثٌ يومًا خرج من العدّ بلا تعديلٍ هنا.
"""
from __future__ import annotations

from dataclasses import dataclass

from athera_api.routers.document_intelligence import review_tally
from athera_api.services.document_intelligence import fields as catalogue


@dataclass
class _Item:
    """أخفُّ ما يكفي: العدُّ يقرأ `decidable` و`status` ولا شيء غيرهما."""

    decidable: bool
    status: str


def test_the_fixture_the_bug_was_reported_with():
    """**التجهيزةُ التي وُصف بها العطب، بأرقامها.**

    مراجعتان نظاميّتان، ومعتمَدان، ومرفوضٌ، و«لا أعرف»، وثلاثةٌ منتظِرة.
    فالمنتظِرُ **ثلاثة** — وكان يُحسب خمسة بإضافة النظاميّين إليه.
    """
    items = [
        _Item(decidable=False, status="unverified"),   # page_count
        _Item(decidable=False, status="unverified"),   # source_filename
        _Item(decidable=True, status="approved"),
        _Item(decidable=True, status="approved"),
        _Item(decidable=True, status="rejected"),
        _Item(decidable=True, status="unknown"),
        _Item(decidable=True, status="unverified"),
        _Item(decidable=True, status="unverified"),
        _Item(decidable=True, status="unverified"),
    ]
    tally = review_tally(items)

    assert tally["pending"] == 3, (
        f"المنتظِرُ {tally['pending']} — والنظاميّان دخلا العدّ")
    assert tally["approved"] == 2
    assert tally["rejected"] == 1
    assert tally["unknown"] == 1
    # الإجماليُّ مجموعُ الفئات الأربع — لا حجمُ الفهرس.
    assert tally["reviewable_total"] == 7
    assert tally["reviewable_total"] == (
        tally["approved"] + tally["rejected"] + tally["unknown"] + tally["pending"])


def test_system_metadata_never_enters_any_review_category():
    """**ولا فئةَ واحدة تقبله** — لا المنتظِر ولا المحسوم."""
    only_system = [_Item(decidable=False, status=s)
                   for s in ("unverified", "approved", "rejected", "unknown")]
    tally = review_tally(only_system)
    assert tally["reviewable_total"] == 0
    for key in ("pending", "approved", "rejected", "unknown"):
        assert tally[key] == 0, f"بيانٌ نظاميّ دخل «{key}»"


def test_a_decidable_field_with_no_candidate_still_counts_as_pending():
    """حقلٌ لم يُستخرَج منتظِرٌ كغيره — وكان يسقط من الفئات ويظهر في الفرق."""
    tally = review_tally([_Item(decidable=True, status="unverified")])
    assert tally["pending"] == 1 and tally["reviewable_total"] == 1


def test_the_rule_is_decidable_not_a_hand_written_field_name():
    """**والحقلان يخرجان لأنّ طريقتَهما حتميّة، لا لأنّ اسمَهما مكتوبٌ هنا.**"""
    import ast
    import inspect
    import textwrap

    # **والشرحُ يذكرهما تفسيرًا — فيُفحص المنطقُ لا النثر.** وفحصٌ بالنصّ
    # يتّهم شرحَ الدالّة نفسِه، وقد وقع ذلك هنا فعلًا.
    tree = ast.parse(textwrap.dedent(inspect.getsource(review_tally)))
    body = tree.body[0].body
    if (isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]                      # يُطرح التوثيق
    logic = "\n".join(ast.unparse(node) for node in body)

    for name in ("page_count", "source_filename"):
        assert name not in logic, f"اسمُ حقلٍ مكتوبٌ بيد في منطق العدّ: {name}"
    assert "decidable" in logic

    # والفهرسُ يقول إنّهما الحتميّان — فالدعوى مثبَّتةٌ إلى المصدر.
    deterministic = {s.key for s in catalogue.FIELD_CATALOGUE
                     if s.method is catalogue.Method.DETERMINISTIC}
    assert deterministic == {"page_count", "source_filename"}, deterministic


def test_the_contract_exposes_a_review_total_separate_from_the_catalogue():
    """**وإجماليُّ المراجعة يأتي من الخادم** — لا تحسبه الشاشة ولا تستنتجه."""
    from athera_api.schemas.document_intelligence import ReviewResponse

    assert "reviewable_total" in ReviewResponse.model_fields
    # و`total` يبقى «كلُّ ما يُعرض» — والاثنان لا يُدمجان.
    assert "total" in ReviewResponse.model_fields
    assert len(catalogue.FIELD_CATALOGUE) != len(
        [s for s in catalogue.FIELD_CATALOGUE
         if s.method is not catalogue.Method.DETERMINISTIC]), (
        "لو تساوى الاثنان لما كان للفصل معنى — وتغيّر الفهرس")


def test_the_endpoint_reads_the_pure_rule_and_does_not_recount():
    """ولا نسختان من العدّ: نقطةُ النهاية تنادي القاعدة ولا تعيدها."""
    import inspect

    from athera_api.routers import document_intelligence as router

    source = inspect.getsource(router.review)
    assert "review_tally(" in source, "نقطةُ النهاية تعدّ بنفسها"
    assert "len(catalogue.FIELD_CATALOGUE) - " not in source, (
        "الفرقُ من حجم الفهرس عاد — وهو العطبُ نفسه")
