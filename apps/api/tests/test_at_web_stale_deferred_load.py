"""ردٌّ بائت لا يكتب فوق شاشةٍ حاضرة | No stale load may overwrite current state.

**العطب كما ظهر في الإنتاج.** رُصد في قبول الموجة 1.1: تُفتح شاشةُ مركز
الرسائل فينطلق طلبُ عرض «الكلّ»، ويُبدَّل العرضُ إلى «المؤرشفة» قبل أن
يستقرّ الأوّل، فيمضي الطلبان معًا. ويصل «الكلّ» أخيرًا فيكتب صفوفَه فوق
صفوف «المؤرشفة»: القائمةُ المنسدلة تقول عرضًا، والصفوفُ تقول عرضًا آخر.

**والسببُ في خطّافٍ مشترك** — `useDeferredLoad` — تستعمله خمسَ عشرةَ شاشة.
كانت فيه رايةُ `active` تُطفأ عند التنظيف، ووُصفت بأنّها تمنع الكتابة بعد
فكّ التركيب. ولم تكن: الرايةُ تُقرأ *قبل* استدعاء `load` فتمنع بدايةً
متأخّرة، وضبطُ الحالة يقع *داخل* `load` بعد `await` حيث لا تُقرأ أصلًا.

**والعلاجُ عقدٌ لا رقعة.** يُعطى `load` بوّابةً `commit` لا تُنفِّذ الكتابة
إلّا إن كان جيلُها هو الحاضر. وهذه الفحوص تحرس العقدَ في كلّ مستهلك، لأنّ
المترجم لا يستطيع: `async () => {}` يقبله TypeScript مكانَ
`(commit) => {}` — فحذفُ البوّابة سهوًا **لا يكسر البناء**، ويكسر هذه
الفحوص وحدها.
"""
from __future__ import annotations

import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[3]
WEB_SRC = REPO / "apps" / "web" / "src"
HOOK = WEB_SRC / "lib" / "useDeferredLoad.ts"

#: كتابةُ حالةٍ في React — `setX(` باصطلاح التسمية المتّبع في هذه الشيفرة.
STATE_WRITE = re.compile(r"\bset[A-Z]\w*\s*\(")


def _consumers() -> list[pathlib.Path]:
    """كلُّ ملفٍّ يستورد الخطّاف — يُكتشف، ولا يُكتب عددُه يدويًّا."""
    found = [
        path
        for path in sorted(WEB_SRC.rglob("*.ts*"))
        if path != HOOK and "useDeferredLoad" in path.read_text(encoding="utf-8")
    ]
    assert found, "لم يُعثر على أيّ مستهلك — الفحص يقيس فراغًا"
    return found


def _strip_strings(text: str) -> str:
    """يُبدِّل محتوى النصوص بفراغٍ مساوٍ في الطول.

    فأقواسُ نصٍّ ليست أقواسَ شيفرة، وعدُّها يُفسد الموازنة. ويُحفظ الطول
    ليبقى كلُّ فهرسٍ صالحًا على النصّ الأصلي.
    """
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in "\"'`":
            quote = ch
            i += 1
            while i < n and text[i] != quote:
                if text[i] == "\\":
                    out[i] = " "
                    i += 1
                if i < n:
                    out[i] = " "
                    i += 1
            i += 1
            continue
        i += 1
    return "".join(out)


def _balanced(text: str, open_at: int) -> int:
    """فهرسُ القوس المُغلِق المقابل للقوس عند `open_at`."""
    depth = 0
    for j in range(open_at, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return j
    raise AssertionError("قوسٌ غير مُغلَق")


def _load_bodies(source: str) -> list[str]:
    """أجسامُ كلِّ دالّةٍ تُمرَّر إلى `useDeferredLoad`."""
    bare = _strip_strings(source)
    bodies: list[str] = []
    for call in re.finditer(r"useDeferredLoad\(\s*([A-Za-z0-9_]+)\s*\)", bare):
        name = call.group(1)
        decl = re.search(r"const\s+" + re.escape(name) + r"\s*=\s*useCallback\s*\(", bare)
        assert decl, f"لم يُعثر على تعريف `{name}`"
        open_at = bare.index("(", decl.end() - 1)
        bodies.append(source[decl.start() : _balanced(bare, open_at) + 1])
    return bodies


def _outside_commit(body: str) -> str:
    """الجسمُ بعد نزع كلّ نطاقات `commit(...)` منه."""
    bare = _strip_strings(body)
    keep, cursor = [], 0
    for call in re.finditer(r"\bcommit\s*\(", bare):
        if call.start() < cursor:
            continue
        close = _balanced(bare, bare.index("(", call.end() - 1))
        keep.append(body[cursor : call.start()])
        cursor = close + 1
    keep.append(body[cursor:])
    return "".join(keep)


# ═════════ الخطّاف نفسه ═════════


def _squeeze(text: str) -> str:
    """يُوحَّد البياضُ ليُقارَن البناءُ لا التنسيق."""
    return re.sub(r"\s+", " ", text)


def test_the_hook_offers_a_commit_gate_and_tracks_generations() -> None:
    """البوّابةُ مُصدَّرة، والجيلُ عدّادٌ لا راية."""
    source = HOOK.read_text(encoding="utf-8")
    assert "export type Commit" in source
    assert "load: (commit: Commit) => Promise<void>" in source
    assert "useRef" in source and "generation" in source


def test_the_gate_itself_compares_generations_before_writing() -> None:
    """**البوّابةُ تفحص قبل أن تكتب — ولا تكتفي الفحوصُ بوجود المقارنة.**

    كانت هذه الفحوص تكتفي بأن تجد `generation.current === mine` في الملفّ.
    وهي موجودةٌ أيضًا عند بدء التحميل، فمرّ إفراغُ البوّابة من محتواها —
    `write()` بلا شرط — والفحوصُ خضراء. فيُقرأ جسمُ البوّابة وحده.
    """
    body = re.search(
        r"const commit: Commit = \(write\) => \{(.*?)\};",
        HOOK.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    assert body, "لم يُعثر على تعريف البوّابة `commit`"
    assert _squeeze(body.group(1).strip()) == "if (generation.current === mine) write();", (
        "جسمُ البوّابة ليس فحصًا مشروطًا قبل الكتابة — "
        f"وُجد: {_squeeze(body.group(1).strip())!r}"
    )


def test_the_hook_does_not_rely_on_a_boolean_active_flag() -> None:
    """**الرايةُ المنطقية هي العطبُ بعينه** — لا تعود بابًا خلفيًّا.

    كانت `let active = true` تُقرأ قبل الاستدعاء وحده، فتمنع بدايةً متأخّرة
    ولا تمنع كتابةً متأخّرة. وعودتُها تعني عودةَ العطب صامتًا.
    """
    source = HOOK.read_text(encoding="utf-8")
    assert "let active" not in source
    assert "active = false" not in source


def test_a_superseded_generation_can_never_be_current_again() -> None:
    """التنظيفُ يُقدّم العدّاد — فلا يعود جيلٌ سابقٌ مساويًا للحاضر."""
    source = HOOK.read_text(encoding="utf-8")
    assert "generation.current += 1" in source
    assert "generation.current === mine" in source


# ═════════ كلُّ مستهلك ═════════


def test_every_consumer_receives_the_commit_gate() -> None:
    """لا شاشةَ تُحمِّل بلا بوّابة."""
    offenders = []
    for path in _consumers():
        source = path.read_text(encoding="utf-8")
        if "type Commit" not in source:
            offenders.append(f"{path.relative_to(REPO)}: لا تستورد `Commit`")
            continue
        for body in _load_bodies(source):
            if "commit: Commit" not in body:
                offenders.append(f"{path.relative_to(REPO)}: `load` بلا بوّابة")
    assert not offenders, "شاشاتٌ بلا بوّابة:\n" + "\n".join(offenders)


def test_no_state_write_after_an_await_escapes_the_commit_gate() -> None:
    """**الفحصُ الذي يمنع عودةَ العطب.**

    كلُّ كتابةٍ بعد أوّل `await` تمرّ عبر `commit` — نجاحًا كانت أو في
    `catch` أو في `finally`. وما قبل أوّل `await` لجيله بالبناء، إذ لم يبدأ
    جيلٌ بعده، فهو وحده المستثنى.
    """
    offenders = []
    for path in _consumers():
        for body in _load_bodies(path.read_text(encoding="utf-8")):
            outside = _outside_commit(body)
            bare = _strip_strings(outside)
            first_await = bare.find("await")
            if first_await < 0:
                continue
            for write in STATE_WRITE.finditer(bare):
                if write.start() > first_await:
                    line = outside[: write.start()].count("\n") + 1
                    offenders.append(
                        f"{path.relative_to(REPO)}: "
                        f"`{write.group().rstrip('( ')}` بعد `await` بلا بوّابة "
                        f"(سطر {line} من جسم `load`)"
                    )
    assert not offenders, "كتاباتٌ متأخّرة بلا بوّابة:\n" + "\n".join(offenders)


def test_the_hook_hands_back_a_guarded_refresh() -> None:
    """الإعادةُ اليدويّة تمرّ من المدخل نفسه."""
    source = HOOK.read_text(encoding="utf-8")
    assert "): () => Promise<void> {" in source
    assert "const refresh = useCallback(" in source
    assert "return refresh;" in source


#: `load` وحدها — لا `loaded` ولا `reload` ولا `useDeferredLoad`.
LOAD_TOKEN = re.compile(r"(?<![A-Za-z0-9_])load(?![A-Za-z0-9_])")


def test_load_is_never_handed_out_except_to_the_hook() -> None:
    """**`load` لا تُستدعى ولا تُمرَّر — تُسلَّم للخطّاف وحده.**

    البوّابةُ وسيطٌ مطلوب، فكلُّ نداءٍ لا يُمرّرها يكسر الشاشة عند أوّل
    `commit`. وللتسريب وجهان: `load()` رأسًا، و**تمريرُها قيمةً** إلى مكوّنٍ
    ابن يناديها بلا وسائط — `onChanged={load}`. والوجهُ الثاني هو الذي أفلت
    من أوّل صياغةٍ لهذه الفحوص، وأمسكه المترجمُ في CI: مكوّنُ الأقسام كان
    يتسلّم `load` ويناديها عند كلّ تغيير.

    فالقاعدةُ تُكتب على الاسم لا على شكل النداء: لا يظهر `load` إلّا في
    تعريفها وفي تسليمها إلى `useDeferredLoad`.
    """
    offenders = []
    for path in _consumers():
        bare = _strip_strings(path.read_text(encoding="utf-8"))
        allowed = set()
        for ok in re.finditer(r"const\s+load\s*=\s*useCallback", bare):
            allowed.add(ok.start() + ok.group().index("load"))
        for ok in re.finditer(r"useDeferredLoad\(\s*load\s*\)", bare):
            allowed.add(ok.start() + ok.group().index("load", len("useDeferredLoa")))
        for hit in LOAD_TOKEN.finditer(bare):
            if hit.start() in allowed:
                continue
            line = bare[: hit.start()].count("\n") + 1
            snippet = bare.splitlines()[line - 1].strip()[:70]
            offenders.append(f"{path.relative_to(REPO)}:{line}: {snippet}")
    assert not offenders, (
        "`load` خرجت من يد الخطّاف — تُستعمل `refresh` بدلها:\n"
        + "\n".join(offenders)
    )


@pytest.mark.parametrize(
    "screen",
    [
        "app/[locale]/theses/page.tsx",
        "app/[locale]/audit/page.tsx",
        "app/[locale]/team/page.tsx",
        "components/SectionWorkspace.tsx",
    ],
)
def test_the_dependency_sensitive_screens_are_covered(screen: str) -> None:
    """الشاشاتُ التي يتغيّر فيها الاعتمادُ بلا فكّ تركيب — أخطرُها.

    وفيها الفرعان الداخليّان في `team` و`SectionWorkspace`: `catch` متداخلة
    تكتب حالةً بعد `await`، وهي أكثرُ ما يُنسى.
    """
    source = (WEB_SRC / screen).read_text(encoding="utf-8")
    bodies = _load_bodies(source)
    assert bodies, f"{screen}: لا `load`"
    for body in bodies:
        assert "commit: Commit" in body
        assert "commit(" in body
