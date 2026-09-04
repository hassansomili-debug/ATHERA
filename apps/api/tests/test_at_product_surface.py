"""سطحُ المنتج | The product surface — no control that promises and does nothing.

**المالك قال: «بعض الأزرار لا تعمل — تبدو قابلةً للنقر ولا يحدث شيء».**
وذلك أسوأ من عطبٍ مُعلَن: العطب المُعلَن يُقرأ ويُبلَّغ عنه، والزرُّ الميت
يجعل الباحث يظن أنّ الخطأ منه فيعيد المحاولة ثم ينصرف.

**وله وجهان لا وجه واحد:**

  ١ زرٌّ بلا معالج — يُرسم قابلًا للنقر ولا يفعل شيئًا.
  ٢ حالٌ تكذب — «لا يوجد» قبل أن يُسأل، أو «جارٍ» بعد أن رُدّ عليه.

والثاني أخفى وأكثر: القائمة تبدأ `[]`، والتصيير يقول `items.length === 0 ?
«لا يوجد…»` — فتُعرض الجملة في اللحظة التي لا يُعرف فيها شيء. وهي دعوى عن
حال بحث الباحث لم تُفحص بعد، وهو يقرؤها حكمًا.

**والفحص هنا على المصدر لا على المتصفح**، كما تفعل بقية حرّاس الواجهة في
هذا المستودع: يعمل في كل PR، ويسبق فحصَ المتصفح ولا يُستبدل به —
`apps/web/tests/product-surface.spec.ts` هو الذي يفتح الشاشات فعلًا.

**والتعليقات تُنزع قبل أي فحص.** حارسٌ يعاقب على شرحٍ صادق يُعطَّل ثم لا
يحرس شيئًا، وقد وقع ذلك مرّتين في هذا المستودع — ولذلك `code_lines` مكتوبة
مرّة واحدة في `tests/tsscan.py` ويقرؤها كلّ حارس.
"""
import pathlib
import re

import pytest

from tests.tsscan import code_lines

WEB = pathlib.Path(__file__).resolve().parents[3] / "apps" / "web"
SRC = WEB / "src"

# ملفّان يملكهما غيرُ هذا الحارس، فلا يُحاسَبان به: مكتبة الباحث ومكوّن
# الرفع. وإخراجهما تصريحٌ بالحدّ لا استثناءٌ صامت.
NOT_OURS = {
    "app/[locale]/library/page.tsx",
    "components/FileUpload.tsx",
}


def _owned() -> list[tuple[str, str]]:
    """(المسار النسبي، الشيفرة بلا تعليقات) لكل ملف واجهة نملكه."""
    out: list[tuple[str, str]] = []
    for path in sorted(SRC.rglob("*.tsx")):
        rel = path.relative_to(SRC).as_posix()
        if rel in NOT_OURS:
            continue
        raw = path.read_text(encoding="utf-8")
        out.append((rel, "\n".join(text for _, text in code_lines(raw))))
    return out


OWNED = _owned()


def _tags(code: str, name: str) -> list[str]:
    """وسمُ العنصر كاملًا — والأقواس المعقوفة تُعدّ، فـ`>` داخل JSX لا يخدع."""
    found: list[str] = []
    for match in re.finditer(rf"<{name}\b", code):
        index, depth = match.end(), 0
        while index < len(code):
            char = code[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            elif char == ">" and depth == 0:
                break
            index += 1
        found.append(code[match.start(): index + 1])
    return found


# ══════════ ١. الزرُّ الميت ══════════

def test_no_enabled_button_is_left_without_a_handler():
    """**العطب الذي أبلغ عنه المالك.**

    زرٌّ بلا `onClick`، ولا `type="submit"` داخل نموذج، ولا `disabled`
    يُعلن أنه لا يعمل — هو زرٌّ يَعِد ويخذل. و`disabled` وحدها لا تكفي
    عذرًا في السلوك، لكنها تكفي هنا: المُعطَّل لا يُنقر أصلًا، وصدقُ نصّه
    يُفحص بالعين لا بالماسح.
    """
    dead: list[str] = []
    for rel, code in OWNED:
        for tag in _tags(code, "button"):
            has_handler = "onClick" in tag or 'type="submit"' in tag or "disabled" in tag
            if not has_handler:
                dead.append(f"{rel}: {' '.join(tag.split())[:120]}")
    assert dead == [], (
        "أزرارٌ تُرسم قابلةً للنقر بلا معالج ولا إعلانِ تعطيل:\n" + "\n".join(dead))


def test_the_literature_search_surface_actually_calls_the_registry():
    """**النموذج كان `preventDefault` وحده**: لا نداء ولا نتيجة ولا رسالة.

    وكان مستورًا لأن البوابة تُعطّل الزرّ ما دام السجل «بلا شبكة» — أي
    زرٌّ ميت ينتظر أن يُفتح السجل ليُرى موته.

    **وسطحُ البحث صار واحدًا.** كانت شاشتان تفعلان الشيء نفسه: `/search`
    تنادي `/sources/search` فتتوقّف عند أوّل فهرسٍ ردّ بشيء ولا تفهم DOI
    وتبقى معطَّلة ما دام `LITERATURE_REGISTRY=offline`؛ و`/references`
    تنادي `/references/search` فتسأل الفهرسين معًا بلا إعداد. فأُحيلت
    الأولى إلى الثانية.

    والحارس يتبع السطح ولا يُلغى — **ويشتدّ**: كان يفحص نداءً واحدًا،
    وصار يفحص ثلاثة أشياء لا يجوز سقوط واحدٍ منها:

      ١ `/search` تحويلٌ صريح، فلا تعود صفحةً ميتة تُعرض ولا تنادي شيئًا.
      ٢ سطحُ البحث الباقي ينادي عميل الاكتشاف، وعميلُ الاكتشاف ينادي
        مسارًا **موجودًا في الموجِّه** — والسابقة تُقرأ منه لا تُكتب بجانبه.
      ٣ والمسار القديم باقٍ في الخادم: الإحالة قرارُ واجهةٍ لا حذفُ عقد.
    """
    owned = dict(OWNED)
    retired = owned["app/[locale]/search/page.tsx"]
    surface = owned["app/[locale]/references/page.tsx"]
    client = (WEB / "src" / "lib" / "discovery.ts").read_text(encoding="utf-8")
    router = (
        pathlib.Path(__file__).resolve().parents[1]
        / "athera_api" / "routers" / "literature.py"
    ).read_text(encoding="utf-8")

    # **والحارس كان يحرس عنوانًا لا وجود له.** يُطالب الشاشة بنداء
    # `/api/v1/literature/sources/search` ويُطالب الخادم بـ`"/sources/search"`،
    # ولا يجمع بينهما — فمرّ نداءٌ يعود ٤٠٤ وهو «محروس». والسابقة تُقرأ من
    # الموجِّه ويُركَّب المسار منها، فلا يُكتب العنوان مرّتين ولا يفترقان.
    prefix = re.search(r'APIRouter\(prefix="([^"]+)"', router)
    assert prefix, "لم تُعلَن سابقة الموجِّه"

    # ١ — المسار المتقاعد يُحيل، ولا يُترك شاشةً بلا نداء.
    assert "redirect(" in retired and "/references" in retired, (
        "‎/search لم تعد تنادي شيئًا ولا تُحيل — وتلك صفحةٌ ميتة")

    # ٢ — والسطح الباقي ينادي فهرسًا فعلًا، عبر عميلٍ ينادي مسارًا قائمًا.
    assert "searchReferences(" in surface, "شاشة اكتشاف المراجع لا تنادي شيئًا"
    assert '@router.post("/references/search"' in router, (
        "عميل الاكتشاف ينادي مسارًا لا وجود له في الخادم")
    assert f"{prefix.group(1)}/references/search" in client, (
        "عميل الاكتشاف لا ينادي مسار الموجِّه")

    # ٣ — والمسار القديم لم يُمَسّ في الخادم: أُحيلت الواجهة ولم يُحذف عقد.
    assert '@router.post("/sources/search"' in router, (
        "‎/sources/search اختفى من الخادم — والإحالة كانت قرار واجهة")


def test_no_tab_switches_state_without_switching_content():
    """**لسانُ «خريطة الأدلة» كان يُضاء ولا يُغيّر شيئًا.**

    يضبط `tab` إلى `map`، واللوحة شرطها `tab !== "outline"` — فهي لوحة
    «الخيط» بعينها. زرٌّ حيٌّ بلا أثر، وهو أسوأ من زرٍّ غائب.
    """
    code = dict(OWNED)[
        "app/[locale]/portfolio/[projectId]/publication-opportunities/page.tsx"
    ]
    assert '"map"' not in code, "لسانٌ يُضبط ولا لوحة له"


# ══════════ ٢. الحالُ التي تكذب ══════════

# **الرايةُ اسمها ليس واحدًا، وشرطُها واحد**: أن يكون في الشاشة ما يفرّق
# بين «لم يصل الجواب» و«وصل وهو خالٍ». وهذه هي الأسماء المستعملة فعلًا.
LOADING_SENTINELS = ("app.loading", "Load", "loading", "phase", "answered")


def test_every_screen_that_claims_emptiness_can_first_say_it_is_loading():
    """**النمط الذي تكرّر في تسع عشرة شاشة.**

    `useState([])` ثم تأثيرٌ يجلب، ثم `items.length === 0 ? «لا يوجد…»`.
    والقائمة فارغةٌ **قبل** أن يعود الجواب — فتُقال الجملة قبل أن يُسأل.

    ولا يُفحص هنا موضعُ الشرط سطرًا بسطر: يُفحص أن الشاشة **تملك** ما
    تقول به «جارٍ» أصلًا. فشاشةٌ تدّعي الخلوّ ولا تعرف الانتظار لا يمكن
    أن تكون صادقة في الحالين.
    """
    blind: list[str] = []
    for rel, code in OWNED:
        if ".length === 0" not in code:
            continue
        if not any(token in code for token in LOADING_SENTINELS):
            blind.append(rel)
    assert blind == [], (
        "شاشاتٌ تقول «لا يوجد» ولا تملك حالَ انتظارٍ تقوله قبلها:\n"
        + "\n".join(blind))


@pytest.mark.parametrize(
    "rel",
    [
        "app/[locale]/traces/page.tsx",
        "app/[locale]/memory/page.tsx",
        "app/[locale]/claims/page.tsx",
        "app/[locale]/facts/page.tsx",
        "app/[locale]/briefs/page.tsx",
        "app/[locale]/audit/page.tsx",
        "app/[locale]/approvals/page.tsx",
        "app/[locale]/settings/page.tsx",
        "app/[locale]/analysis/page.tsx",
        "app/[locale]/theses/page.tsx",
        "app/[locale]/manuscripts/page.tsx",
        "app/[locale]/team/page.tsx",
        "app/[locale]/trends/page.tsx",
        "app/[locale]/portfolio/page.tsx",
    ],
)
def test_the_repaired_screens_announce_the_wait_by_name(rel: str):
    """الشاشات التي أُصلحت بالاسم — فلا يعود العيب إلى واحدةٍ منها بصمت."""
    assert 't("app.loading")' in dict(OWNED)[rel], (
        f"{rel}: لا نصَّ انتظارٍ — والخلوّ سيُقال قبل الجواب")


def test_no_list_screen_claims_emptiness_while_an_error_is_showing():
    """**الخلوّ والإخفاق حالان لا تُجمعان.**

    شاشةٌ تقول «لا يوجد» وفوقها لافتةٌ حمراء تقول «تعذّر التحميل» تُناقض
    نفسها: الأولى تدّعي معرفةً، والثانية تُعلن أنها لم تُتَح.

    **والفحص على شاشات القوائم وحدها** — أي التي تحمل حمولتها في
    `useState([])`. وهي بالضبط موضع العيب: القائمة تبدأ فارغة وتبقى فارغة
    بعد الإخفاق، فلا يفرّق الشرطُ بينهما إلّا بذكر الخطأ صراحةً. أمّا من
    يحمل حمولته في حالةٍ تبدأ `null` فحارسُه الحمولةُ نفسها: لا تُملأ إلا
    بنجاح، فلا يُطلب منه ذكرٌ ثانٍ.
    """
    lax: list[str] = []
    for rel, code in OWNED:
        holds_a_list = re.search(r"useState<[^>]*\[\]>\(\[\]\)", code) is not None
        if not holds_a_list or ".length === 0" not in code:
            continue
        # أداتان مقبولتان: ذكرُ الخطأ صراحةً، أو حالُ تحميلٍ ثلاثيةٍ يُقرأ
        # منها طرفُ الإخفاق. والمرفوض أن يُقرأ من الثلاثية طرفٌ واحد فيصير
        # ما ليس «جارٍ» خلوًّا — وهو ما وقع في مساحة البحث بمواضعها الأربعة.
        if "!error" not in code and '=== "failed"' not in code:
            lax.append(rel)
    assert lax == [], (
        "شاشاتُ قوائمَ تدّعي الخلوّ بلا استثناء حال الإخفاق:\n" + "\n".join(lax))


def test_a_tri_state_load_flag_is_read_on_all_three_states():
    """**ثلاثيةٌ تُقرأ طرفَين تعود ثنائية.** ومساحة البحث كانت كذلك.

    فيها أربع حالاتِ تحميلٍ ثلاثية، ولم يكن يُقرأ منها إلا «جارٍ» — وما
    عداه خلوّ. فالإخفاق يُقرأ «لا ملف مرتبط» و«لا مراجع» و«لا مرشّحين»،
    والخطأ معلَنٌ فوقها في الوقت نفسه.
    """
    code = dict(OWNED)["app/[locale]/portfolio/[projectId]/page.tsx"]
    loading_reads = code.count('=== "loading"')
    failed_reads = code.count('=== "failed"')
    assert loading_reads == failed_reads, (
        f"حالاتُ تحميلٍ تُقرأ «جارٍ» {loading_reads} مرّة و«أخفق» "
        f"{failed_reads} — فما ليس جاريًا يُقرأ خلوًّا")


@pytest.mark.parametrize(
    "rel",
    [
        "app/[locale]/manuscripts/[manuscriptId]/studio/page.tsx",
        "components/SectionWorkspace.tsx",
    ],
)
def test_a_failed_read_never_reads_as_a_clean_bill(rel: str):
    """**ادّعاءُ براءةٍ مبنيٌّ على لا شيء.**

    الاستوديو كان يقول «لا عوائق» وقد سقطت قراءة الورقة، ومساحةُ القسم
    تقول «لا مخرجات تحليل مؤهَّلة» وقد سقطت قراءة سياقها. وهما أخطر من
    «لا يوجد» العادية: الأولى تُطمئن على ورقةٍ لم تُفحص.
    """
    assert "error ? null :" in dict(OWNED)[rel], (
        f"{rel}: الخلوّ يُقال ولو أخفقت القراءة")


# ══════════ ٣. الإتاحة ══════════

def test_no_field_leans_on_its_placeholder_for_a_name():
    """**النائب ليس اسمًا**: يختفي بأوّل حرفٍ يُكتب.

    فحقلٌ بلا `id` مقرونٍ بـ`label` ولا `aria-label` اسمُه المُعلَن فارغ —
    وقارئ الشاشة يقول «تحرير نصّ» ولا يقول تحريرَ ماذا.
    """
    nameless: list[str] = []
    for rel, code in OWNED:
        for name in ("input", "textarea", "select"):
            for tag in _tags(code, name):
                if "placeholder" not in tag:
                    continue
                if "id=" in tag or "aria-label" in tag:
                    continue
                nameless.append(f"{rel}: {' '.join(tag.split())[:120]}")
    assert nameless == [], (
        "حقولٌ اسمها المُعلَن نائبٌ يختفي:\n" + "\n".join(nameless))


def test_the_main_landmark_is_declared_exactly_once():
    """**كان ثلاثةً متداخلة**: الهيكل، ثم الاستوديو، ثم مساحة القسم تحته.

    ومن يتنقّل بالمعالم يقفز إلى «المحتوى الرئيسي» فيجد ثلاثة — أي لا معلَم.
    """
    holders = {rel: code.count("<main") for rel, code in OWNED if "<main" in code}
    assert holders == {"app/[locale]/layout.tsx": 1}, (
        f"معلَمُ `main` معلَنٌ في غير الهيكل العام أو أكثر من مرّة: {holders}")


def test_the_add_file_button_says_which_file_it_adds():
    """A11Y-1 — زرٌّ اسمه «+» لا يقول لأعمى ما يفعل ولا على أيّ ملف.

    وفي القسم زرٌّ لكل ملف، وكلّها متطابقة الاسم — فلا يُميَّز بينها بالسمع.
    والعلامة تبقى «+» بالعين: الاسم المُعلَن وحده هو ما تغيّر.
    """
    code = dict(OWNED)["app/[locale]/portfolio/[projectId]/page.tsx"]
    assert 't("project.addFile")}: ${file.original_filename}' in code, (
        "زرّ إضافة الملف بلا اسمٍ مُعلَن يحمل اسم الملف")
    # وأخوه في القسم نفسه هو النمط الذي حُذي عليه — فلا يسقط أحدهما وحده.
    assert 't("project.addSource")}: ${source.title}' in code


def test_the_impact_dialog_declares_its_name():
    """حوارٌ دورُه ونمطيّته معلَنان واسمه غائب يقول «حوار تنبيه» لا أكثر."""
    code = dict(OWNED)["app/[locale]/portfolio/[projectId]/page.tsx"]
    assert 'role="alertdialog"' in code
    assert "aria-labelledby=" in code, "حوارُ الأثر بلا اسمٍ مُعلَن"


def test_the_ai_file_input_is_not_offered_twice_to_a_screen_reader():
    """`sr-only` تخفي بالعين وتُبقي في شجرة الإتاحة.

    فكان قارئ الشاشة يجد حقلَ ملفٍّ بلا اسم بجانب الزرّ الذي هو مدخله
    الحقيقي — مدخلان لفعلٍ واحد، أحدهما بلا اسم. و`hidden` تُخرجه من
    الشجرة ولا تمنع `.click()`.
    """
    code = dict(OWNED)["components/AtheraAiInput.tsx"]
    file_inputs = [tag for tag in _tags(code, "input") if 'type="file"' in tag]
    assert len(file_inputs) == 1, "حقل الملف مفقودٌ أو مكرَّر"
    tag = file_inputs[0]
    # و`sr-only` مشروعةٌ على `label` في الملف نفسه — فيُفحص الوسم لا الملف.
    assert "sr-only" not in tag, "حقل الملف معروضٌ لقارئ الشاشة بلا اسمٍ مُعلَن"
    assert "hidden" in tag, "حقل الملف لم يُخرَج من شجرة الإتاحة"


def test_no_click_handler_hides_on_a_non_interactive_element():
    """`onClick` على `div` أو `span` بلا `role` و`tabIndex` فعلٌ للفأرة وحدها."""
    stranded: list[str] = []
    for rel, code in OWNED:
        for name in ("div", "span", "li", "p", "article", "section", "td", "tr"):
            for tag in _tags(code, name):
                if "onClick" not in tag:
                    continue
                if "role=" in tag and "tabIndex" in tag:
                    continue
                stranded.append(f"{rel}: {' '.join(tag.split())[:120]}")
    assert stranded == [], (
        "نقرٌ على عنصرٍ غير تفاعلي لا يبلغه لوحةُ المفاتيح:\n" + "\n".join(stranded))


# ══════════ ٤. الحارس نفسه ══════════

def test_the_scanner_reads_code_and_never_prose():
    """**حارسٌ يسقط على تعليقٍ صادق يُعطَّل ثم لا يحرس شيئًا.**

    وقد وقع ذلك مرّتين في هذا المستودع، ولذلك كُتبت `code_lines` مرّة
    واحدة. وهذا الاختبار يثبّت السبب: تعليقٌ يصف زرًّا ميتًا — وهو بالضبط
    ما تكتبه تعليقاتُ هذا الفرع — لا يجوز أن يُحاسَب عليه أحد.
    """
    prose = (
        "// كان هنا `<button>` بلا `onClick` فأُزيل\n"
        "/* و<button> ثانٍ في تعليقٍ كتلي */\n"
        '<button type="button" onClick={go}>نعم</button>\n'
    )
    code = "\n".join(text for _, text in code_lines(prose))
    assert len(_tags(code, "button")) == 1, "الماسح يقرأ التعليقات"
    assert "onClick" in _tags(code, "button")[0]


def test_the_boundary_of_this_guard_is_declared_not_assumed():
    """ملفّان يملكهما غيرُ هذا الحارس — والحدّ يُكتب ولا يُترك ضمنيًّا."""
    for rel in NOT_OURS:
        assert (SRC / rel).exists(), f"حدٌّ يشير إلى ملفٍ غير موجود: {rel}"
    scanned = {rel for rel, _ in OWNED}
    assert scanned.isdisjoint(NOT_OURS)
    # وما نملكه ليس فارغًا: حارسٌ لا يمسح شيئًا يمرّ دائمًا.
    assert len(scanned) > 30, f"الماسح لم يجد إلا {len(scanned)} ملفًا"


def test_the_posture_does_not_deny_a_call_that_happens():
    """**الشاشة لا تنفي نداءً يقع.**

    كان بند «سجل الأدبيات» يقول «بلا شبكة: لا يُستدعى سجل خارجي» ما دام
    `LITERATURE_REGISTRY=offline` — وهو حال الإنتاج. ثم وصل اكتشافُ
    المراجع، وهو ينادي Crossref وOpenAlex في كل بحث بلا مفتاح ولا إعداد.
    فصارت الشاشة تنفي نداءً يقع، وذلك أسوأ من ألّا تقول شيئًا.

    فالبندان اثنان: أحدهما للرصد المجدول، والآخر لفهارس الاكتشاف.
    """
    import pathlib

    settings_src = (pathlib.Path(__file__).resolve().parents[1] / "athera_api" / "routers"
                    / "settings.py").read_text(encoding="utf-8")
    assert 'key="reference_indexes"' in settings_src, "الفهارس التي تُستدعى لا تُذكر"
    assert "لا يُستدعى سجل خارجي." not in settings_src, "الشاشة ما زالت تنفي نداءً يقع"


def test_the_posture_reads_its_provider_names_from_the_providers():
    """**قيمةٌ تُكتب بجانب سجلّها تفترق عنه.** وهو الخطأ المتكرّر هنا:
    فتُشتقّ أسماءُ الفهارس من المزوّدين أنفسهم، فإن أُضيف فهرسٌ ظهر، وإن
    أُزيل اختفى — بلا سطرٍ يُحدَّث باليد."""
    from athera_api.discovery.service import default_providers
    from athera_api.routers.settings import _discovery_providers

    assert _discovery_providers() == tuple(p.name for p in default_providers())
    assert _discovery_providers(), "لا فهرس — والبحث عن المراجع يعمل"
