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

#: **الهندسةُ تُقرأ من مصدرها، ولا تُنسخ هنا.**
#:
#: كانت مكتوبةً في هذا الملفّ حرفًا بحرف، فكان الحارس يقارن نسخةً بنسخة:
#: تتّفق الصيغُ الأربع والمكوّن على شكلٍ **غير معتمَد** ويمرّ كلُّ شيء
#: أخضر. وهو ما وقع فعلًا — رُسمت العلامة حرفَ `P` صريحًا بساقٍ وقاعدة،
#: واتّفقت الخمسةُ عليه، ولم يشتكِ فحصٌ واحد.
#:
#: فالمرجعُ الآن `brandMarkGeometry.ts` وحده: تُقرأ منه ويُطلب من الجميع
#: موافقتُه. واتّفاقُ الصيغ بعضِها ببعض لا يكفي — يجب أن توافق **المعتمَد**.
GEOMETRY = WEB / "src" / "lib" / "brandMarkGeometry.ts"


def _canonical() -> tuple[str, list[tuple[str, str, str]]]:
    source = GEOMETRY.read_text(encoding="utf-8")
    block = source.split("THREAD_PATH =", 1)[1].split(";", 1)[0]
    path = "".join(re.findall(r'"([^"]*)"', block))
    nodes = re.findall(
        r"\{ cx: ([\d.]+), cy: ([\d.]+), r: ([\d.]+)", source)
    return path, nodes


STROKE, NODES = _canonical()


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
    for cx, cy, r in NODES:
        assert re.search(rf'cx="{cx}"\s+cy="{cy}"\s+r="{r}"', svg), (
            f"{name}: عقدةٌ في غير موضعها ({cx},{cy},{r})")


def test_the_component_draws_from_the_canonical_source_not_a_copy():
    """**والمكوّنُ هو ما يراه الباحث فعلًا.**

    ولا يُطلب منه أن يحمل المسار حرفًا بحرف — بل ألّا يحمله أصلًا: يستورده
    من مصدره. فنسخةٌ في المكوّن تطابق المصدر اليوم هي نسخةٌ تفارقه غدًا،
    والشاشةُ وحدها تشذّ — وهي الموضع الوحيد الذي يهمّ.
    """
    source = MARK.read_text(encoding="utf-8")

    assert "brandMarkGeometry" in source, "المكوّن لا يقرأ من المصدر المعتمَد"
    for symbol in ("THREAD_PATH", "NODES", "STROKE_WIDTH", "VIEW_BOX"):
        assert symbol in source, f"المكوّن لا يستعمل {symbol} من المصدر"

    # ولا هندسةَ مكتوبةً بيدها: مسارٌ حرفيّ أو عقدةٌ برقمٍ ثابت.
    assert not re.search(r'd="M[\d.]', source), "مسارٌ مكتوبٌ في المكوّن"
    assert not re.search(r'cx="[\d.]+"', source), "عقدةٌ برقمٍ ثابت في المكوّن"


def test_the_geometry_guard_would_notice_a_drifted_variant():
    """**حارسٌ لا يسقط أبدًا ليس حارسًا.**

    فيُحاكى الحسابُ نفسه على صيغةٍ عُدّل مسارُها، ويجب أن تُرى.
    """
    drifted = '<svg viewBox="0 0 48 48"><path d="M12 21C13 13 21 7 29 8"/></svg>'
    assert STROKE not in drifted, "الحارس لا يميّز مسارًا انحرف"

    # **والأهمّ: أن يرفض الحرفَ الصريح الذي رُسم خطأً.** ساقٌ رأسيّة
    # وقاعدةٌ أفقيّة ليستا العلامة المعتمَدة، ومرورُهما هو العطب بعينه.
    letterform = 'M16 40V9c8.7 0 13.6 2.9 13.6 8.6 0 5.6-4.9 8.6-13.6 8.6'
    assert STROKE != letterform, "الهندسةُ المعتمَدة عادت حرفًا صريحًا"
    assert "V9" not in STROKE, "ساقٌ رأسيّة في العلامة المعتمَدة"
    assert "h16" not in STROKE, "قاعدةٌ أفقيّة في العلامة المعتمَدة"
    assert len(NODES) == 3, f"العقدُ المعتمَدة ثلاث، لا {len(NODES)}"


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
