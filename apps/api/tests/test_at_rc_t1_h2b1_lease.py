"""RC-T1-H2-B1 — الإجارةُ والسياج | lease, takeover and fencing.

## الدعوى المُبرهَنة هنا

الطور A يكفيه أن يكون الحجزُ والطفرةُ والجوابُ في معاملةٍ واحدة. وما فيه
فجوةٌ خارجيّة لا يكفيه ذلك: المعاملةُ تُودَع **قبل** النداء الخارجيّ
(RC-T1-H3)، فيبقى صفٌّ مُودَعٌ `in_progress` لا يملكه أحدٌ إن مات العامل.

فالإجارةُ مهلةٌ على الملكيّة، والسياجُ يمنع عاملًا بائتًا أن يكتب فوق من
خلفه. **والسياجُ هو `lease_expires_at` نفسُه** — ولا عمودَ جديد، ولا
ترحيلَ ٠٠٣٨.

## وحجّةُ السياج — تُبرهَن لا تُقرَّر

آجالُ المالكين المتعاقبين **تتزايد تزايدًا صارمًا**: الاستيلاءُ لا يقع
إلّا إن كان `lease_expires_at <= now()`، فمن استولى في `t₂` كان
`t₁ + L <= t₂`، وأجلُه `t₂ + L > t₁ + L`. فسياجُ البائت لا يطابق القائم
أبدًا، وشرطُ الإنهاء يردّه بصفر صفوف.

و`test_07` يقيس هذا التزايدَ على القاعدة، و`test_08` يقيس أثرَه: عاملٌ
بائتٌ لا يُنهي ولا يُودِع طفرةً.

**ولا يُدَّعى «مرّةً واحدةً بالضبط».** ما يُبنى تحمُّلُ إعادةٍ حيث تُبرهَن.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import uuid

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.asyncio

OPERATION = "POST /api/v1/__h2b1_probe__"
SHORT = dt.timedelta(milliseconds=250)


def _key() -> str:
    return uuid.uuid4().hex


async def _maker(slot):
    from athera_api.db import tenant_session_maker
    return tenant_session_maker(slot["tenant_id"], slot["user_id"])


async def _fingerprint(body: dict) -> str:
    from athera_api.services.idempotency import canonical_fingerprint
    return canonical_fingerprint(method="POST", operation=OPERATION, body=body)


async def _acquire(slot, key, body, ttl):
    """PREPARE في معاملةٍ قصيرة تُودَع — ثمّ يُعاد التحكّمُ للمُنادي."""
    from athera_api.services import idempotency as idem
    maker = await _maker(slot)
    async with maker() as session:
        return await idem.acquire_lease(
            session, tenant_id=slot["tenant_id"], actor_user_id=slot["user_id"],
            operation=OPERATION, key=key, fingerprint=await _fingerprint(body),
            ttl=ttl)


async def _finalize(slot, lease, *, status=201, body=None):
    from athera_api.services import idempotency as idem
    maker = await _maker(slot)
    async with maker() as session:
        return await idem.finalize_leased(session, lease, status=status,
                                          body=body or {"id": "x"})


async def _state(slot, key):
    maker = await _maker(slot)
    from athera_api.services.idempotency import digest_key
    async with maker() as session:
        return (await session.execute(text(
            "SELECT state, lease_expires_at FROM idempotency_records"
            " WHERE operation = :o AND key_digest = :d"),
            {"o": OPERATION, "d": digest_key(key)})).first()


# ═════════════ ١ · الحجزُ والقرار ═════════════


async def test_01_the_first_claimant_owns_a_committed_lease(two_tenants):
    """**والإجارةُ مُودَعة** — فلو مات العاملُ بقي الأثرُ لا الفراغ."""
    from athera_api.services.idempotency import Lease
    slot = two_tenants["a"]
    key = _key()
    lease = await _acquire(slot, key, {"n": 1}, dt.timedelta(seconds=60))
    assert isinstance(lease, Lease), lease
    assert lease.fence is not None
    row = await _state(slot, key)
    assert row is not None and row[0] == "in_progress", (
        "الحجزُ لم يُودَع — فلا شيءَ يحرس العملَ الخارجيّ")
    assert row[1] == lease.fence, "السياجُ المُعاد ليس ما كُتب في الصفّ"


async def test_02_a_live_lease_cannot_be_taken_over(two_tenants):
    """حَجزٌ قائمٌ وإجارتُه حيّة ⇒ لا تنفيذٌ ثانٍ ولا جوابٌ مُختلَق."""
    from athera_api.services.idempotency import InProgress, Lease
    slot = two_tenants["a"]
    key = _key()
    first = await _acquire(slot, key, {"n": 1}, dt.timedelta(seconds=60))
    assert isinstance(first, Lease)
    second = await _acquire(slot, key, {"n": 1}, dt.timedelta(seconds=60))
    assert isinstance(second, InProgress), second
    assert second.lease_expires_at == first.fence


async def test_03_concurrent_claims_yield_exactly_one_owner(two_tenants):
    """**والقاعدةُ هي الحَكَم** — لا قفلَ عمليّةٍ ولا Redis."""
    from athera_api.services.idempotency import InProgress, Lease
    slot = two_tenants["a"]
    key = _key()
    results = await asyncio.gather(*[
        _acquire(slot, key, {"n": 1}, dt.timedelta(seconds=60)) for _ in range(5)
    ], return_exceptions=True)
    owners = [r for r in results if isinstance(r, Lease)]
    waiters = [r for r in results if isinstance(r, InProgress)]
    assert len(owners) == 1, f"عددُ المالكين {len(owners)} — يُنتظر واحد"
    assert len(owners) + len(waiters) == 5, results
    assert len({o.fence for o in owners}) == 1


async def test_04_an_expired_lease_is_taken_over_once(two_tenants):
    """إجارةٌ انتهت ⇒ استيلاءٌ واحد، وسياجٌ جديد."""
    from athera_api.services.idempotency import Lease
    slot = two_tenants["a"]
    key = _key()
    first = await _acquire(slot, key, {"n": 1}, SHORT)
    assert isinstance(first, Lease)
    await asyncio.sleep(0.4)
    second = await _acquire(slot, key, {"n": 1}, dt.timedelta(seconds=60))
    assert isinstance(second, Lease), second
    assert second.record_id == first.record_id, "استُولي على صفٍّ آخر"
    assert second.fence > first.fence, (
        "السياجُ الجديد ليس أكبرَ — فحجّةُ التزايد تسقط")


async def test_05_concurrent_takeover_of_an_expired_lease_has_one_winner(
    two_tenants,
):
    """**ومتسابقون على إجارةٍ منتهية ⇒ فائزٌ واحد.**"""
    from athera_api.services.idempotency import InProgress, Lease
    slot = two_tenants["a"]
    key = _key()
    first = await _acquire(slot, key, {"n": 1}, SHORT)
    assert isinstance(first, Lease)
    await asyncio.sleep(0.4)
    results = await asyncio.gather(*[
        _acquire(slot, key, {"n": 1}, dt.timedelta(seconds=60)) for _ in range(5)
    ], return_exceptions=True)
    owners = [r for r in results if isinstance(r, Lease)]
    others = [r for r in results if isinstance(r, InProgress)]
    assert len(owners) == 1, f"عددُ المستولين {len(owners)} — يُنتظر واحد"
    assert len(owners) + len(others) == 5, results


# ═════════════ ٢ · السياج — الدعوى المركزيّة ═════════════


async def test_06_the_current_owner_can_finalize(two_tenants):
    slot = two_tenants["a"]
    key = _key()
    lease = await _acquire(slot, key, {"n": 1}, dt.timedelta(seconds=60))
    assert await _finalize(slot, lease, body={"id": "kept"}) is None
    row = await _state(slot, key)
    assert row[0] == "completed"


async def test_07_successive_fences_increase_strictly(two_tenants):
    """**حجّةُ السياج، مقيسةً على القاعدة.**

    والاستيلاءُ لا يقع إلّا بعد انتهاء الإجارة، فالأجلُ الجديد أكبرُ قطعًا.
    وهذا ما يجعل `lease_expires_at` كافيًا سياجًا بلا عمودٍ جديد.
    """
    from athera_api.services.idempotency import Lease
    slot = two_tenants["a"]
    key = _key()
    fences = []
    for _ in range(3):
        got = await _acquire(slot, key, {"n": 1}, SHORT)
        assert isinstance(got, Lease), got
        fences.append(got.fence)
        await asyncio.sleep(0.4)
    assert fences == sorted(fences) and len(set(fences)) == 3, (
        f"الآجالُ لا تتزايد تزايدًا صارمًا: {fences}")


async def test_08_a_stale_worker_cannot_finalize_after_takeover(two_tenants):
    """**والعاملُ البائتُ يُردّ، ولا يُودِع طفرةً.**

    وهذا هو الخطرُ الذي وُجد السياجُ له: عاملٌ نام، وانتهت إجارتُه،
    واستولى غيرُه، ثمّ استيقظ الأوّلُ ليكتب نتيجتَه فوق نتيجةِ من خلفه.
    """
    from athera_api.services.idempotency import Lease, Stale
    slot = two_tenants["a"]
    key = _key()
    stale = await _acquire(slot, key, {"n": 1}, SHORT)
    assert isinstance(stale, Lease)
    await asyncio.sleep(0.4)
    fresh = await _acquire(slot, key, {"n": 1}, dt.timedelta(seconds=60))
    assert isinstance(fresh, Lease) and fresh.fence > stale.fence

    # البائتُ يحاول الإنهاء — ويُردّ.
    verdict = await _finalize(slot, stale, body={"id": "stale-write"})
    assert isinstance(verdict, Stale), "أنهى عاملٌ بائتٌ عملًا ليس له"

    # ولا أثرَ له في الصفّ: ما زال للمالك الجديد.
    row = await _state(slot, key)
    assert row[0] == "in_progress", "كتب البائتُ حالًا نهائيّة"
    assert row[1] == fresh.fence, "كتب البائتُ فوق سياج المالك الجديد"

    # والمالكُ الجديد يُنهي.
    assert await _finalize(slot, fresh, body={"id": "fresh"}) is None
    kept = await _state(slot, key)
    assert kept[0] == "completed"


async def test_09_two_workers_never_both_finalize(two_tenants):
    """**ولا يُنهي اثنان بعد استيلاء** — وهي الدعوى بصيغتها السالبة."""
    from athera_api.services.idempotency import Lease, Stale
    slot = two_tenants["a"]
    key = _key()
    old = await _acquire(slot, key, {"n": 1}, SHORT)
    await asyncio.sleep(0.4)
    new = await _acquire(slot, key, {"n": 1}, dt.timedelta(seconds=60))
    assert isinstance(old, Lease) and isinstance(new, Lease)
    verdicts = await asyncio.gather(
        _finalize(slot, old, body={"id": "old"}),
        _finalize(slot, new, body={"id": "new"}),
        return_exceptions=True)
    settled = [v for v in verdicts if v is None]
    refused = [v for v in verdicts if isinstance(v, Stale)]
    assert len(settled) == 1, f"عددُ من أنهى {len(settled)} — يُنتظر واحد"
    assert len(refused) == 1, verdicts


# ═════════════ ٣ · الإعادةُ والتعارضُ والعزل ═════════════


async def test_10_a_completed_lease_replays(two_tenants):
    from athera_api.services.idempotency import Lease, Replay
    slot = two_tenants["a"]
    key = _key()
    lease = await _acquire(slot, key, {"n": 1}, dt.timedelta(seconds=60))
    assert isinstance(lease, Lease)
    await _finalize(slot, lease, status=201, body={"id": "abc"})
    again = await _acquire(slot, key, {"n": 1}, dt.timedelta(seconds=60))
    assert isinstance(again, Replay), again
    assert again.status == 201 and again.body == {"id": "abc"}


async def test_11_same_key_different_body_still_conflicts(two_tenants):
    from athera_api.services.idempotency import KeyReused
    slot = two_tenants["a"]
    key = _key()
    await _acquire(slot, key, {"n": 1}, dt.timedelta(seconds=60))
    with pytest.raises(KeyReused):
        await _acquire(slot, key, {"n": 2}, dt.timedelta(seconds=60))


async def test_12_a_known_failure_keeps_the_key_retryable(two_tenants):
    """إخفاقٌ **معلوم** ⇒ `failed`، والمفتاحُ يُعاد بأمان.

    ولا دلالةَ تُختلق لنتيجةٍ غامضة: ذاك بابٌ لطورٍ لاحق.
    """
    from athera_api.services import idempotency as idem
    slot = two_tenants["a"]
    key = _key()
    lease = await _acquire(slot, key, {"n": 1}, dt.timedelta(seconds=60))
    maker = await _maker(slot)
    async with maker() as session:
        assert await idem.fail_leased(session, lease, reason="provider_rejected") is None
    row = await _state(slot, key)
    assert row[0] == "failed"
    # وإعادةُ المحاولة تستولي من جديد.
    retry = await _acquire(slot, key, {"n": 1}, dt.timedelta(seconds=60))
    assert isinstance(retry, idem.Lease), retry


async def test_13_leases_are_isolated_by_tenant_and_actor(two_tenants):
    """المفتاحُ نفسُه في مستأجرٍ آخر — أو لفاعلٍ آخر — إجارةٌ أخرى."""
    from athera_api.services.idempotency import Lease
    key = _key()
    a = await _acquire(two_tenants["a"], key, {"n": 1}, dt.timedelta(seconds=60))
    b = await _acquire(two_tenants["b"], key, {"n": 1}, dt.timedelta(seconds=60))
    assert isinstance(a, Lease) and isinstance(b, Lease)
    assert a.record_id != b.record_id, "تشارك مستأجران صفَّ إجارةٍ واحدًا"


async def test_14_the_raw_key_is_never_stored(two_tenants):
    slot = two_tenants["a"]
    key = _key()
    await _acquire(slot, key, {"n": 1}, dt.timedelta(seconds=60))
    maker = await _maker(slot)
    async with maker() as session:
        blob = (await session.execute(text(
            "SELECT count(*) FROM idempotency_records"
            " WHERE key_digest = :raw OR request_fingerprint = :raw"),
            {"raw": key})).scalar_one()
    assert blob == 0, "المفتاحُ الخام في القاعدة"


async def test_15_prepare_commits_before_control_returns(two_tenants):
    """**ولا معاملةَ مفتوحةٌ حين يعود التحكّمُ للمُنادي** (RC-T1-H3).

    فالإجارةُ لا تُفيد شيئًا إن بقيت المعاملةُ ممسوكةً عبر النداء الخارجيّ:
    يكون الأثرُ محجوزًا والاتصالُ محجوزًا معه.
    """
    from athera_api.services.idempotency import Lease
    slot = two_tenants["a"]
    key = _key()
    lease = await _acquire(slot, key, {"n": 1}, dt.timedelta(seconds=60))
    assert isinstance(lease, Lease)
    # يُقرأ الصفُّ من **جلسةٍ أخرى**: لو لم يُودَع لَما رأته.
    maker = await _maker(slot)
    async with maker() as other:
        seen = (await other.execute(text(
            "SELECT state FROM idempotency_records WHERE id = :i"),
            {"i": str(lease.record_id)})).scalar_one_or_none()
    assert seen == "in_progress", "لم تُودَع معاملةُ التحضير"


async def test_16_lease_time_comes_from_the_database_clock(two_tenants):
    """**وساعةُ الإجارة ساعةُ القاعدة، لا ساعةُ العمليّة.**

    وعاملان على آلتين بساعتين مختلفتين يجب أن يتّفقا على متى انتهت
    الإجارة. فلو حُسب الأجلُ بساعةِ العمليّة لَأمكن لآلةٍ متقدّمةِ الساعة
    أن تستولي على إجارةٍ حيّة، ولآلةٍ متأخّرةٍ أن تحسب إجارتَها حيّةً وقد
    انتهت — وكلاهما ينقض الحصريّة.

    **وهذا الفحصُ بنيويٌّ عن قصد، ويُقال سببُه.** انحرافُ الساعات لا
    يُصطنَع في عمليّةٍ واحدة: عضّةٌ بدّلت `func.now()` بساعة العمليّة مرّت
    على الفحوص الخمسةَ عشرَ كلِّها. فتُشترط الساعةُ في الموضع الذي تُكتب
    فيه، ويبقى `test_01` يشترط أنّ السياجَ المُعاد هو ما كُتب في الصفّ.
    """
    import inspect

    from athera_api.services import idempotency as idem

    for fn in (idem._claim_with_lease, idem.acquire_lease):  # noqa: SLF001
        source = inspect.getsource(fn)
        if "lease_expires_at" not in source:
            continue
        assert "func.now()" in source, (
            f"{fn.__name__}: أجلُ الإجارة لا يُحسب بساعة القاعدة")
        assert "dt.datetime.now(" not in source, (
            f"{fn.__name__}: أجلُ الإجارة يُحسب بساعة العمليّة — "
            "فعاملان بساعتين مختلفتين لا يتّفقان على انتهائها")

    # والسياجُ المُعاد قيمةٌ كتبتها القاعدة، ويقع في نافذةٍ معقولةٍ حولها.
    slot = two_tenants["a"]
    lease = await _acquire(slot, _key(), {"n": 1}, dt.timedelta(seconds=60))
    assert isinstance(lease, idem.Lease)
    maker = await _maker(slot)
    async with maker() as session:
        db_now = (await session.execute(text("SELECT now()"))).scalar_one()
    drift = abs((lease.fence - db_now).total_seconds() - 60)
    assert drift < 30, f"السياجُ بعيدٌ عن ساعة القاعدة بـ{drift:.1f}ث"
