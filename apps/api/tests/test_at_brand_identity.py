"""هويّةُ المنتج تُفحص بالبنية لا بالعين | structural brand-identity guards.

**العلامةُ التي تفترق عن نفسها ليست علامة.** وورقةُ الهويّة تطلب أربعَ صيغ
— أيقونةَ تطبيق، وأيقونةَ لسان، وأحاديّةَ لون، وصيغةَ الوضع الداكن —
و«الهندسةُ نفسها في الأربع». وهذا شرطٌ يسهل خرقُه بلا أن يراه أحد: تُعدَّل
واحدةٌ لأنها بدت ثقيلةً في موضعها، فتصير عندنا علامتان تتشابهان ولا
تتطابقان، ولا شيء في الفحوص يقول ذلك.

فتُقرأ الملفّات وتُقابَل هندستُها ببعضها وبالمكوّن الذي يرسمها في التطبيق.

**والألوانُ كذلك.** الورقة تكتب سبعةَ أرقام؛ ورقمٌ يُقارَب اشتقاقًا هويّةٌ
أخرى تشبه المعتمدة. فتُطلب بحرفها من الطبقة الأولى.
"""
from __future__ import annotations

import pathlib
import re

import pytest

WEB = pathlib.Path(__file__).resolve().parents[3] / "apps" / "web"
PUBLIC = WEB / "public"
TOKENS = WEB / "src" / "styles" / "globals.css"
MARK = WEB / "src" / "components" / "BrandMark.tsx"

#: صيغُ العلامة التي تطلبها الورقة — واسمُ كلٍّ يقول أين تُستعمل.
VARIANTS = {
    "favicon.svg": "أيقونةُ لسان المتصفّح",
    "brand/mark-app-icon.svg": "أيقونةُ التطبيق على أرضيّةٍ بيضاء",
    "brand/mark-monochrome.svg": "أحاديّةُ اللون للطباعة",
    "brand/mark-dark.svg": "صيغةُ الوضع الداكن",
}

#: هندسةُ العلامة: المسار الأول، ثمّ الذيل، ثمّ مواضع العقد الأربع.
STROKE = "M16 40V9c8.7 0 13.6 2.9 13.6 8.6 0 5.6-4.9 8.6-13.6 8.6"
TAIL = "M16 40h16"
NODES = [("16", "9", "3.4"), ("29.6", "17.6", "3.1"),
         ("16", "26.2", "2.8"), ("32", "40", "3.6")]


def _svg(name: str) -> str:
    path = PUBLIC / name
    assert path.exists(), f"صيغةٌ تطلبها الورقة وليست في الشجرة: {name}"
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", sorted(VARIANTS))
def test_every_logo_variant_exists_and_is_a_square_svg(name: str):
    """أربعُ صيغ، ولكلٍّ إطارٌ واحد — فالعلامةُ لا تتمطّط في موضعٍ دون آخر."""
    svg = _svg(name)
    assert 'viewBox="0 0 48 48"' in svg, f"{name}: إطارٌ يخالف الأخوات"


@pytest.mark.parametrize("name", sorted(VARIANTS))
def test_every_logo_variant_draws_the_same_geometry(name: str):
    """**الهندسةُ واحدة، واللونُ وحده يتبدّل.**

    ولو عُدِّل مسارٌ في صيغةٍ لأنها بدت ثقيلةً في موضعها لصار عندنا علامتان
    تتشابهان ولا تتطابقان — وذاك ما لا تلتقطه عينٌ تقارن بالذاكرة.
    """
    svg = _svg(name)
    assert STROKE in svg, f"{name}: مسارُ الخيط يخالف الأصل"
    assert TAIL in svg, f"{name}: ذيلُ الخيط يخالف الأصل"
    for cx, cy, r in NODES:
        assert re.search(rf'cx="{cx}"\s+cy="{cy}"\s+r="{r}"', svg), (
            f"{name}: عقدةٌ في غير موضعها ({cx},{cy},{r})")


def test_the_component_the_app_renders_matches_the_files_on_disk():
    """**والمكوّنُ هو ما يراه الباحث فعلًا.**

    فلو طابقت الملفّاتُ الأربعُ بعضَها وخالفها المكوّن لبقيت الشجرة متّسقة
    والشاشةُ وحدها شاذّة — وهي الموضع الوحيد الذي يهمّ.
    """
    source = MARK.read_text(encoding="utf-8")
    assert STROKE in source, "المكوّن يرسم مسارًا غير مسار الملفّات"
    assert TAIL in source, "المكوّن يرسم ذيلًا غير ذيل الملفّات"
    for cx, cy, r in NODES:
        assert re.search(rf'cx="{cx}" cy="{cy}" r="{r}"', source), (
            f"المكوّن يضع عقدةً في غير موضعها ({cx},{cy},{r})")


def test_the_geometry_guard_would_notice_a_drifted_variant():
    """**حارسٌ لا يسقط أبدًا ليس حارسًا.**

    فيُحاكى الحسابُ نفسه على صيغةٍ عُدّل مسارُها، ويجب أن تُرى.
    """
    drifted = '<svg viewBox="0 0 48 48"><path d="M16 40V9c9 0 14 3 14 9"/></svg>'
    assert STROKE not in drifted


#: أرقامُ ورقة الهويّة — تُكتب هنا مرّة، وتُطلب من الطبقة الأولى بحرفها.
SHEET_COLOURS = {
    "--brand-indigo": "#4B46A9",
    "--brand-violet": "#7867F2",
    "--brand-teal": "#17BEBB",
    "--brand-ink": "#182233",
    "--brand-paper": "#F7F8FB",
    "--success": "#22C55E",
    "--warning": "#F59E0B",
    "--error": "#EF4444",
    "--neutral": "#F7F8FB",
}


@pytest.mark.parametrize("token,value", sorted(SHEET_COLOURS.items()))
def test_every_approved_colour_is_declared_with_the_sheet_value(token: str, value: str):
    """**رقمٌ يُقارَب اشتقاقًا هويّةٌ أخرى تشبه المعتمدة.**

    والقيمةُ تُطلب في الطبقة الأولى وحدها؛ وما بعدها يُشتقّ منها — فشاشةٌ
    تكتب اللون بيدها تُخالف الورقةَ ولا يُرى ذلك في لقطة.
    """
    css = TOKENS.read_text(encoding="utf-8")
    assert re.search(rf"{re.escape(token)}:\s*{re.escape(value)};", css), (
        f"{token} لا يحمل قيمة الورقة {value}")


def test_the_states_derive_from_the_approved_semantic_colours():
    """الحالاتُ الأربع تُشتقّ من الأرقام المعتمدة، لا من قيمةٍ ثانية بجانبها."""
    css = TOKENS.read_text(encoding="utf-8")
    for token, source in (("--state-verified", "var(--success)"),
                          ("--state-review", "var(--warning)"),
                          ("--state-conflict", "var(--error)"),
                          ("--state-candidate", "var(--brand-violet)")):
        assert re.search(rf"{re.escape(token)}:\s*{re.escape(source)};", css), (
            f"{token} لا يُشتقّ من {source} — قيمتان لمعنًى واحد تفترقان")


def test_the_retired_spectrum_is_gone_from_the_token_layer():
    """**الطيفُ القديم لا يبقى رقمًا في الطبقة الأولى.**

    والأسماءُ باقيةٌ عمدًا (`--aqua` وأخواتها) لأنّ أربعًا وأربعين شاشةً
    تستعملها؛ لكنّها تُشتقّ من الجديد. فما يُمنع هو الرقمُ نفسه.
    """
    css = TOKENS.read_text(encoding="utf-8")
    for retired in ("#00d4c5", "#14b8a6", "#38bdf8", "#8b5cf6"):
        assert retired.lower() not in css.lower(), (
            f"لونٌ من الطيف المتقاعد ما زال مكتوبًا: {retired}")
