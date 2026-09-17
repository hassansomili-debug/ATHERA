"""عزلُ الحزمة: جلسةٌ لا تُستعمل بعد مالكها | test session lifecycle.

## العطب الذي كان

خطأٌ **واحد** في التشغيلة الكاملة، على فحصٍ **مختلفٍ كلَّ مرّة**
(`test_at_s10_routers` مرّةً، و`test_at_thesis_canonical_bridge` أخرى)، مع
تحذير:

    The garbage collector is trying to clean up non-checked-in connection

والسببُ ليس في تلك الملفّات. `AsyncSession.close()` يُخلي الجلسةَ ولا
يُعطّلها، فاستعمالٌ بعد خروج `async with` يفتح معاملةً ويسحب اتصالًا لا
مالكَ له. والجمعُ يقع لاحقًا، فيُنهيه SQLAlchemy في فحصٍ بريء.

## وما يُثبت هنا

ثلاثةٌ، ولا يكفي واحدُها:

    ١ · رصيدُ الاتصالات صفرٌ بعد العمل — **بجمعٍ مُجبَر**
    ٢ · النمطُ الفاسدُ يُخِلّ بالرصيد فعلًا (فالميزانُ يعضّ)
    ٣ · ماسحٌ بنيويٌّ يمنع عودةَ النمط

**ولا تجهيزةَ عامّةً تُلزم الفحوصَ النقيّةَ بقاعدة.** المستودعُ يسمح لما
لا يمسّ القاعدةَ أن يعمل بلا PostgreSQL، والعقدُ محفوظ: ما هنا موسومٌ
بـ`requires_db` إلّا الماسحَ البنيويّ — وهو نصٌّ لا اتصال.
"""
from __future__ import annotations

import gc
import warnings

import pytest

from tests.conftest import requires_db
from tests.connection_balance import ConnectionBalance
from tests.session_lifecycle_audit import audit, audit_source

#: نصُّ التحذير الذي كان يُنهي الاتصالات المتسرّبة.
GC_WARNING = "The garbage collector is trying to clean up non-checked-in connection"


# ═════════════ ١ · الرصيدُ صفرٌ بعد العملِ الحقيقيّ ═════════════


@requires_db
@pytest.mark.asyncio
async def test_01_the_repaired_sequence_leaves_no_connection_checked_out(
    two_tenants, test_engine,
):
    """تسلسلُ الفحصِ المُصلَح: كلُّ ما سُحب أُعيد — **والجمعُ مُجبَر**.

    وهو شكلُ `test_building_the_shell_without_consent_is_allowed_but_ai_is_not`
    بعينه: جلستان متعاقبتان، والحدُّ يُعبَر بقيمةٍ عاديّة لا بجلسة.
    """
    from athera_api.db import tenant_session

    slot = two_tenants["a"]
    tid, uid = slot["tenant_id"], slot["user_id"]

    with ConnectionBalance(test_engine) as balance:
        async with tenant_session(tid, uid) as session:
            await session.execute(_ping())
        async with tenant_session(tid, uid) as session:
            await session.execute(_ping())
        outstanding = balance.settle()
        drawn = balance.checked_out

    assert drawn >= 2, f"لم يُسحب اتصالٌ فعلًا — فالميزانُ لا يقيس شيئًا ({drawn})"
    assert outstanding == 0, (
        f"بقي {outstanding} اتصالًا مسحوبًا بعد الجمع — "
        f"سُحب {balance.checked_out} وأُعيد {balance.checked_in}")


@requires_db
@pytest.mark.asyncio
async def test_02_the_repaired_journey_test_emits_no_gc_connection_warning(
    two_tenants, test_engine,
):
    """الفحصُ المُصلَح يُشغَّل هنا **والتحذيرُ مرفوعٌ خطأً**.

    ويُجبر الجمعُ داخل النطاق المرفوع، فلا يُؤجَّل الإنهاءُ إلى ما بعده —
    وذاك هو الفرقُ بين إصلاحٍ وتأجيل.
    """
    from tests.test_at_thesis_journey_build import (
        test_building_the_shell_without_consent_is_allowed_but_ai_is_not as subject,
    )

    with warnings.catch_warnings():
        warnings.filterwarnings("error", message=GC_WARNING)
        # وتحذيرُ المُفنيات يُغلَّف أحيانًا `unraisable`، فيُرفع كذلك.
        warnings.filterwarnings("error", category=pytest.PytestUnraisableExceptionWarning)
        with ConnectionBalance(test_engine) as balance:
            await subject(two_tenants)
            outstanding = balance.settle()
            gc.collect()

    assert outstanding == 0, \
        f"الفحصُ المُصلَح ترك {outstanding} اتصالًا مسحوبًا"


# ═════════════ ٢ · الميزانُ يعضّ: النمطُ الفاسد ═════════════


@requires_db
@pytest.mark.asyncio
async def test_03_using_a_session_after_its_scope_really_does_leak(
    two_tenants, test_engine,
):
    """**العضّة**: النمطُ الفاسدُ يُخِلّ بالرصيد — فالصفرُ أعلاه ذو معنى.

    ولولا هذا لَكان «الرصيدُ صفر» دعوًى لا يُعرف أنّها تُقاس. فيُعاد
    النمطُ الفاسدُ عمدًا **هنا وحده**، ويُقاس أثرُه، ثمّ يُنظَّف يدويًّا
    كي لا يُسمِّم فحصًا آخر.
    """
    from athera_api.db import tenant_session

    slot = two_tenants["a"]
    tid, uid = slot["tenant_id"], slot["user_id"]

    with ConnectionBalance(test_engine) as balance:
        async with tenant_session(tid, uid) as session:
            await session.execute(_ping())
        before = balance.outstanding
        # **الاستعمالُ بعد الخروج**: `close()` أخلى ولم يُعطّل، فتُفتَح
        # معاملةٌ جديدةٌ ويُسحب اتصالٌ لا مالكَ له.
        await session.execute(_ping())  # lifecycle-audit: deliberate-leak
        leaked = balance.outstanding

        assert before == 0, f"النطاقُ المالكُ لم يُعِد اتصالَه ({before})"
        assert leaked == 1, (
            "الاستعمالُ بعد الخروج لم يسحب اتصالًا — فالميزانُ لا يكشف العطب "
            f"(الرصيد {leaked})")

        # يُعاد باليد: هذا الفحصُ يصنع التسرّبَ ليقيسه، ولا يُورّثه.
        await session.close()
        assert balance.settle() == 0, "التنظيفُ اليدويُّ لم يُعِد الاتصال"


def _ping():
    from sqlalchemy import text

    return text("SELECT 1")


# ═════════════ ٣ · حارسٌ بنيويٌّ يمنع العودة ═════════════


def test_04a_the_only_marked_exemption_lives_in_this_proof_file() -> None:
    """الوسمُ الظاهرُ **معدود**، ولا يُرَشّ في فحصٍ آخر بلا كشف.

    فاستثناءٌ واحدٌ مقصودٌ (الفحصُ الذي يصنع التسرّبَ ليقيسه) مقبول؛ أمّا
    أن يُسكَت الحارسُ في ملفٍّ بعد ملفٍّ فذاك موتُه البطيء. فيُشترط أن
    تكون الوسومُ كلُّها هنا.
    """
    import pathlib

    from tests.session_lifecycle_audit import MARKER, marked_lines

    here = pathlib.Path(__file__).resolve().parent
    # وملفُّ الماسحِ نفسُه يُستثنى: هو موضعُ **تعريف** الوسم لا استعمالِه.
    definition_site = "session_lifecycle_audit.py"
    carriers: dict[str, int] = {}
    for path in sorted(here.rglob("*.py")):
        if "__pycache__" in path.parts or path.name == definition_site:
            continue
        count = len(marked_lines(path.read_text(encoding="utf-8")))
        if count:
            carriers[path.name] = count

    assert carriers == {pathlib.Path(__file__).name: 1}, (
        f"وسمُ {MARKER!r} خارج ملفِّ البرهان أو أكثرُ من واحد: {carriers}")


def test_04_no_test_uses_a_database_session_after_its_owning_scope() -> None:
    """لا فحصَ في المستودع يستعمل جلسةً بعد خروج مالكها.

    وليست مطابقةَ نصّ: أسطرُ `async with … as <اسم>` تُحدَّد بالتفكيك، ثمّ
    يُسأل عمّا بعد آخرِ سطرٍ منها — وإعادةُ الربطِ بمالكٍ جديدٍ تُبرّئ ما
    بعدها، وإلّا لَاتُّهم كلُّ فحصٍ يفتح جلستين على التوالي.
    """
    offenders = audit()
    assert offenders == [], (
        "جلسةٌ تُستعمل بعد خروج مالكها:\n"
        + "\n".join(o.describe() for o in offenders))


def test_05_the_guard_bites_the_pattern_it_claims_to_forbid() -> None:
    """الحارسُ يعضّ النمطَ المُحرَّم — وحارسٌ لا يعضّ ليس حارسًا.

    ويُعاد هنا شكلُ العطبِ الأصليِّ حرفيًّا (جلسةٌ تُمرَّر إلى خدمةٍ بعد
    الخروج، ثمّ عمليّةٌ عليها مباشرةً).
    """
    bad = (
        "async def t(tid, uid):\n"
        "    async with tenant_session(tid, uid) as session:\n"
        "        thesis = await session.get(Thesis, 1)\n"
        "    assert await journey.consent_granted(session, tenant_id=tid) is False\n"
    )
    found = audit_source(bad, "<bad>")
    assert found, "الحارسُ لم يعضّ تمريرَ جلسةٍ بعد خروج مالكها"
    assert found[0].name == "session"
    assert found[0].factory == "tenant_session"

    worse = (
        "async def t(tid, uid):\n"
        "    async with tenant_session(tid, uid) as s:\n"
        "        pass\n"
        "    await s.execute(q)\n"
    )
    assert audit_source(worse, "<worse>"), "الحارسُ لم يعضّ عمليّةً مباشرةً بعد الخروج"

    # والوسمُ يُبرّئ **سطرَه وحدَه** لا الدالّةَ كلَّها.
    #
    # ويُبنى الوسمُ من الثابت لا يُكتب حرفيًّا: فـ`test_04a` يَعُدّ الوسومَ
    # الحرفيّةَ في الملفّات، ونصٌّ مُصطنَعٌ هنا كان يُحسَب وسمًا ثانيًا.
    from tests.session_lifecycle_audit import MARKER

    marked_one = (
        "async def t(tid, uid):\n"
        "    async with tenant_session(tid, uid) as s:\n"
        "        pass\n"
        f"    await s.execute(q)  # {MARKER}\n"
        "    await s.flush()\n"
    )
    still = audit_source(marked_one, "<mixed>")
    assert len(still) == 1, f"الوسمُ أبرأ أكثرَ من سطره: {len(still)}"
    assert still[0].use == "s.flush(...)", still[0].use


def test_06_the_guard_does_not_flag_the_correct_shapes() -> None:
    """ولا يعضّ الصحيحَ: جلستان متعاقبتان، وقيمةٌ تعبُر الحدَّ.

    فحارسٌ يُنبّه على الصحيح يُدفَع إلى الإسكات، فيموت.
    """
    sequential = (
        "async def t(tid, uid):\n"
        "    async with tenant_session(tid, uid) as session:\n"
        "        thesis = await session.get(Thesis, 1)\n"
        "        file_id = thesis.file_id\n"
        "    async with tenant_session(tid, uid) as session:\n"
        "        await journey.consent_granted(session, file_id=file_id)\n"
    )
    assert audit_source(sequential, "<ok>") == [], \
        "جلستان متعاقبتان اتُّهمتا — والحارسُ يُشوّش"

    scalar_only = (
        "async def t(tid, uid):\n"
        "    async with tenant_session(tid, uid) as session:\n"
        "        row = await session.get(Thesis, 1)\n"
        "        name = row.title\n"
        "    assert name == 'x'\n"
        "    assert row is not None\n"
    )
    assert audit_source(scalar_only, "<ok2>") == [], \
        "قيمةٌ عاديّةٌ بعد الحدِّ اتُّهمت"
