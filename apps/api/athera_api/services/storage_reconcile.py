"""مُصالِحُ الكائنات المهجورة | abandoned stable-object reconciliation (H2-C).

## العطبُ الذي يعالجه

الرفعُ المُمفتَح (H2-B3) يكتب الكائنَ **قبل** معاملةِ الإنهاء: فإن ماتت
العمليّةُ بين الاثنين بقي كائنٌ في المخزن بلا صفِّ `File`، وبقي جيلُ
التكرار `in_progress` مرساةً له — `stable_object_id(record_id)` هو معرّفُ
الملفّ، ومنه بادئةُ الكائن. والتنظيفُ العامُّ لا يمسّ `in_progress` عمدًا،
فلا شيءَ كان يُصالِح هذه المراسي قطّ.

## ولمَ ليس حذفًا أعمى

«الجيلُ قديم» ليس برهانًا على الهجر. **عاملٌ بائتٌ ما زال حيًّا** قد
يستيقظ فيُنهي صفَّه؛ وعميلٌ قد يستولي على الجيل فيُعيد الكتابةَ إلى
**المفتاح نفسِه** (الهُويّةُ ثابتة) — فحذفٌ بعد ذلك يمحو كائنَ مالكٍ قائم
ويُبقي صفَّه يشير إلى عدم. وذاك أسوأُ ما يمكن أن تنتجه صيانة:

    صفُّ File قائم  +  كائنُه محذوف

## العقد — ثلاثُ خطوات، ولا معاملةَ عبر الشبكة (RC-T1-H3)

  ١ **السياجُ والحجز** (قاعدةٌ وحدها): عبارةُ كتابةٍ واحدةٌ تستولي على الإجارة
    وتُثبّت **حجزَ الصيانة** (`STORAGE_RECONCILE_MARKER`) — بشرطٍ فيها: جيلٌ
    `in_progress` من أسرة كتابة التخزين، بلا وسمِ مزوّد، وإجارتُه منقضيةٌ منذ
    `grace` (أو حجزٌ سابقٌ انقضى أجلُه). ثمّ يُتحقّق من غياب كلِّ صفٍّ يشير إلى
    الملفّ في المعاملة نفسِها؛ فإن وُجد رجعت المعاملةُ **والحجزُ معها**.
  ٢ **المخزن** (بلا معاملة): تُسرد البادئةُ **التامّة** بحدّ، ويُحذف ما تحتها؛
    وقبل كلِّ حذفٍ سؤالٌ قصيرٌ للسياج.
  ٣ **التقاعد** (قاعدةٌ وحدها، مُسيَّج): تحقّقٌ أخير، ثمّ يُكتب الجيلُ `failed`
    **ومنتهيًا** (`expires_at = now()`). فالإعادةُ التاليةُ لا تستولي عليه بل
    تستعيده — **صفٌّ جديد، ومعرّفُ ملفٍّ جديد، وبادئةٌ جديدة**.

## لمَ لا ينتج «صفٌّ قائم + كائنُه محذوف» — بلا افتراضِ زمن

  • **الحجزُ يغلق الجيلَ على العملاء** إغلاقًا لا يفتحه انقضاءُ الأجل
    (`acquire_lease` تستثني الصفَّ المحجوز في عبارة الاستيلاء نفسِها). فمُصالِحٌ
    توقّف بعد فحصِه الأخير لا يجد مستوليًا كتب إلى مفتاحه حين يستيقظ.
  • **والعاملُ البائت** يرجع إنهاؤه كلُّه: سياجُه لم يعد السياج.
  • **وبعد التقاعد** لا يكتب أحدٌ إلى البادئة القديمة أبدًا: الإعادةُ التاليةُ
    جيلٌ جديدٌ ببادئةٍ جديدة. فحذفٌ متأخّرٌ من مُصالِحٍ عتيقٍ يقع على البادئة
    القديمة وحدَها — ولا يبلغ الملفَّ الجديد.

## والثمنُ — ويُقال

**مُصالِحٌ سقط يترك الجيلَ محجوزًا**، والنيّةُ القديمةُ عالقةٌ (`409
idempotency.in_progress`) حتى يُتمّ مُصالِحٌ آخرُ ما بدأه — فهو وحدَه يستأنف
حجزًا انقضى أجلُه. **والإخفاقُ الآمنُ أولى من فسادِ المخزن.**

و`DELETE_MARGIN` ليس حجّةَ الأمان بل **تحسينٌ للحيويّة**: مُصالِحٌ يعرف أنّ
أجلَه يوشك أن ينقضي يتوقّف قبل الحذف بدل أن يحذف ثمّ يجد نفسه منافَسًا.

والتسرّبُ — لا الفساد — ممكنٌ في حالٍ واحدة: عاملٌ **قبل** الصيانة ما زال داخل
`PUT` بعد أن انقضت إجارتُه بساعة، فيُنزل كائنَه بعد التقاعد تحت البادئة
القديمة. لا صفَّ يشير إليه؛ هو كائنٌ متروكٌ لا صفٌّ يشير إلى عدم.

## الحدود

- **يدويٌّ لا تلقائيّ**: تجربةٌ جافّةٌ افتراضًا، والتطبيقُ بعلَمٍ صريح.
- **مستأجرٌ وفاعلٌ بعينهما**: الجلسةُ `tenant_session(tenant, actor)` —
  نطاقُ الطلب الذي أنشأ الجيل نفسُه. وغيرُهما لا يُرى أصلًا (RLS).
- **بادئةُ ملفٍّ واحد**: لا مسحَ لحاوية، ولا لمستخدم، ولا لمستأجر.
- **لا نموذج**: أسرةُ العمليّات تخزينٌ وحدَه، وما حمل وسمَ عبورِ مزوّدٍ
  يُستبعد صراحةً.
- **التقريرُ معرّفاتٌ وبصمات**: لا اسمَ ملفٍّ ولا مفتاحَ ولا محتوى.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import sys
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import and_, func, or_, select, update

from ..models.files import File
from ..models.idempotency import FAILED, IN_PROGRESS, IdempotencyRecord
from ..models.thesis import Thesis
from . import audit, storage
from .idempotency import (
    EXTERNAL_MARKER,
    STORAGE_RECONCILE_MARKER,
    Lease,
    stable_object_id,
    storage_held,
)

#: أسرةُ كتابةِ التخزين — المساراتُ التي تكتب الكائنَ **قبل** إنهاء القاعدة.
#:
#: والرفعُ الموقَّعُ مسبقًا (`POST /api/v1/files`) ليس منها: صفُّ `File`
#: يُودَع مع الجيل **قبل** أن يحمل العميلُ رابطَ الكتابة، فلا يتيمَ له.
STORAGE_WRITE_OPERATIONS = frozenset({
    "POST /api/v1/files/upload",
    "POST /api/v1/theses/upload",
})

#: كم تنقضي الإجارةُ قبل أن تُعَدّ مهجورة — ساعةٌ فوق أطولِ إجارةٍ مشروعة.
RECONCILE_GRACE = dt.timedelta(hours=1)
#: أجلُ الصيانة: يردّ العملاءَ «قائمٌ لغيرك» طوال عملها.
MAINTENANCE_LEASE = dt.timedelta(hours=1)
#: أقلُّ ما يبقى من الأجل حين يصدر حذف — وهو هامشُ الافتراض الوحيد.
DELETE_MARGIN = dt.timedelta(minutes=30)
#: حدُّ المرشّحين في التشغيلة الواحدة.
CANDIDATE_LIMIT = 20
#: حدُّ المفاتيح في السردة الواحدة، وحدُّ السردات لكلّ بادئة.
KEYS_PER_LIST = 10
MAX_LIST_ROUNDS = 3

REASON = "storage_orphan_reconciled"


@dataclass(slots=True)
class Outcome:
    """نتيجةُ مرشّحٍ واحد — معرّفاتٌ وبصمات، ولا محتوى."""

    record_id: str
    file_id: str
    operation: str
    status: str
    objects: int = 0
    key_digests: list[str] = field(default_factory=list)
    detail: str = ""


def _no_provider_marker():
    # ولا وسمَ عبورِ مزوّد — لا نموذجَ يدخل هذا الباب.
    return or_(IdempotencyRecord.response_body.is_(None),
               ~IdempotencyRecord.response_body.has_key(EXTERNAL_MARKER))


def _eligible(grace: dt.timedelta):
    """أهليّةُ الصيانة — **حالان لا حالٌ واحدة**.

      • جيلٌ مهجورٌ **بلا حجز**: إجارتُه منقضيةٌ منذ `grace` على الأقلّ.
      • جيلٌ **تحت حجزٍ** انقضى أجلُه: مُصالِحٌ سابقٌ سقط. فيستأنفه مُصالِحٌ
        آخرُ فورًا — **ولا يستأنفه عميلٌ أبدًا** (انظر `acquire_lease`).
    """
    held = storage_held()
    return and_(
        IdempotencyRecord.state == IN_PROGRESS,
        IdempotencyRecord.operation.in_(STORAGE_WRITE_OPERATIONS),
        IdempotencyRecord.response_status.is_(None),
        or_(and_(~held, IdempotencyRecord.lease_expires_at <= func.now() - grace),
            and_(held, IdempotencyRecord.lease_expires_at <= func.now())),
    )


def _digest(key: str) -> str:
    # المفتاحُ يحمل اسمَ الملفّ — واسمُ الملفّ قد يكون بحثًا. فبصمةٌ لا اسم.
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


async def _domain_rows(session, *, file_id: uuid.UUID, prefix: str) -> list[str]:
    """ما يشير إلى الملفّ في القاعدة — ولو صفٌّ واحد فليس يتيمًا."""
    found: list[str] = []
    if (await session.execute(
            select(File.id).where(or_(File.id == file_id,
                                      File.storage_key.startswith(prefix, autoescape=True)))
    )).first() is not None:
        found.append("file")
    if (await session.execute(
            select(Thesis.id).where(Thesis.file_id == file_id))).first() is not None:
        found.append("thesis")
    return found


async def find_candidates(
    maker, *, grace: dt.timedelta = RECONCILE_GRACE, limit: int = CANDIDATE_LIMIT,
) -> list[tuple[uuid.UUID, str]]:
    """أجيالٌ مهجورةٌ من أسرة التخزين — **في نطاق الجلسة وحدَه** (RLS)."""
    async with maker() as session:
        rows = (await session.execute(
            select(IdempotencyRecord.id, IdempotencyRecord.operation)
            .where(_eligible(grace), _no_provider_marker())
            .order_by(IdempotencyRecord.lease_expires_at)
            .limit(max(1, limit))
        )).all()
    return [(row[0], row[1]) for row in rows]


async def _fence(maker, *, record_id: uuid.UUID, tenant_id: uuid.UUID,
                 actor_id: uuid.UUID, grace: dt.timedelta,
                 ) -> tuple[Lease | None, str]:
    """الخطوةُ الأولى: السياجُ وغيابُ الصفوف **في معاملةٍ واحدة**."""
    file_id = stable_object_id(record_id)
    prefix = storage.stable_file_prefix(tenant_id, actor_id, file_id)
    async with maker() as session:
        # **والحجزُ يُثبَّت مع السياج في العبارة نفسِها.** ومن لحظة إيداعه لا
        # يستولي على الجيل عميلٌ — ولو انقضى هذا الأجلُ وهذا المُصالِحُ متوقّف.
        taken = (await session.execute(
            update(IdempotencyRecord)
            .where(IdempotencyRecord.id == record_id, _eligible(grace),
                   _no_provider_marker())
            .values(lease_expires_at=func.now() + MAINTENANCE_LEASE,
                    response_body={STORAGE_RECONCILE_MARKER: {"hold": "operator"}})
            .returning(IdempotencyRecord.lease_expires_at, IdempotencyRecord.operation)
        )).first()
        if taken is None:
            return None, "contended"
        # **والتحقّقُ بعد السياج لا قبله**: قبله نافذةٌ يُودِع فيها عاملٌ
        # بائتٌ صفَّه؛ وبعده لا إنهاءَ بسياجٍ قديم يمكن أن يُودَع.
        if await _domain_rows(session, file_id=file_id, prefix=prefix):
            await session.rollback()     # والسياجُ والحجزُ يرجعان معها — لا حبسَ لمفتاحٍ سليم.
            return None, "skipped_domain_row"
    return Lease(record_id=record_id, operation=taken[1], fence=taken[0]), "fenced"


async def _still_ours(maker, lease: Lease) -> bool:
    """أما زال السياجُ سياجَنا، وفي الأجل هامشٌ يكفي حذفًا؟"""
    async with maker() as session:
        return (await session.execute(
            select(IdempotencyRecord.id)
            .where(IdempotencyRecord.id == lease.record_id,
                   IdempotencyRecord.state == IN_PROGRESS,
                   IdempotencyRecord.lease_expires_at == lease.fence,
                   IdempotencyRecord.lease_expires_at >= func.now() + DELETE_MARGIN))
        ).first() is not None


async def _reconcile_one(
    maker, store: storage.ObjectStore, *, record_id: uuid.UUID, operation: str,
    tenant_id: uuid.UUID, actor_id: uuid.UUID, grace: dt.timedelta, apply: bool,
) -> Outcome:
    file_id = stable_object_id(record_id)
    prefix = storage.stable_file_prefix(tenant_id, actor_id, file_id)
    outcome = Outcome(record_id=str(record_id), file_id=str(file_id),
                      operation=operation, status="pending")

    if not apply:
        # ══ تجربةٌ جافّة: قراءةٌ وحدَها — لا سياجَ ولا حذف ══
        async with maker() as session:
            rows = await _domain_rows(session, file_id=file_id, prefix=prefix)
        if rows:
            outcome.status, outcome.detail = "skipped_domain_row", ",".join(rows)
            return outcome
        try:
            keys = await asyncio.to_thread(store.list_prefix, prefix, limit=KEYS_PER_LIST)
        except Exception as exc:  # noqa: BLE001 — يُقال السببُ ويبقى الجيل
            outcome.status, outcome.detail = "list_failed", type(exc).__name__
            return outcome
        outcome.status = "would_reconcile"
        outcome.objects = len(keys)
        outcome.key_digests = [_digest(k) for k in keys]
        return outcome

    # ══ ١ · السياج ══
    lease, state = await _fence(maker, record_id=record_id, tenant_id=tenant_id,
                                actor_id=actor_id, grace=grace)
    if lease is None:
        outcome.status = state
        return outcome

    # ══ ٢ · المخزن — بلا معاملةٍ مفتوحة ══
    deleted: list[str] = []
    for _ in range(MAX_LIST_ROUNDS):
        try:
            keys = await asyncio.to_thread(store.list_prefix, prefix, limit=KEYS_PER_LIST)
        except Exception as exc:  # noqa: BLE001
            outcome.status, outcome.detail = "list_failed", type(exc).__name__
            outcome.objects, outcome.key_digests = len(deleted), [_digest(k) for k in deleted]
            return outcome                      # المرساةُ باقيةٌ بسياج الصيانة
        if not keys:
            break
        for key in keys:
            if not key.startswith(prefix):
                # مخزنٌ ردّ ما لم يُطلب — لا يُحذف شيءٌ خارجَ البادئة أبدًا.
                outcome.status, outcome.detail = "invariant_violation", "key_outside_prefix"
                return outcome
            if not await _still_ours(maker, lease):
                outcome.status = "contended"
                outcome.objects, outcome.key_digests = len(deleted), [_digest(k) for k in deleted]
                return outcome
            try:
                await asyncio.to_thread(store.delete, key)
            except Exception as exc:  # noqa: BLE001
                outcome.status, outcome.detail = "delete_failed", type(exc).__name__
                outcome.objects, outcome.key_digests = len(deleted), [_digest(k) for k in deleted]
                return outcome
            deleted.append(key)
    else:
        # بقيت كائناتٌ بعد السردات المحدودة — لا يُدَّعى النظافة، والمرساةُ تبقى.
        outcome.status, outcome.detail = "incomplete", "prefix_not_empty"
        outcome.objects, outcome.key_digests = len(deleted), [_digest(k) for k in deleted]
        return outcome

    outcome.objects, outcome.key_digests = len(deleted), [_digest(k) for k in deleted]

    # ══ ٣ · الإنهاء — مُسيَّجٌ، وبعد تحقّقٍ أخير ══
    async with maker() as session:
        rows = await _domain_rows(session, file_id=file_id, prefix=prefix)
        if rows:
            # لا يقع إن صحّ السياج — ويُقال بصوتٍ عالٍ إن وقع، ولا يُطوى الجيل.
            outcome.status, outcome.detail = "invariant_violation", ",".join(rows)
            return outcome
        # ══ **ويُتقاعَد الجيلُ لا يُفشَل وحسب** ══
        #
        # `failed` وحدَها تُبقي الصفَّ نفسَه: فإعادةُ العميل تستولي عليه
        # فتكتب إلى **البادئة القديمة** — والمُصالِحُ الأقدمُ المتوقّفُ قد
        # يستيقظ فيحذف فيها. فيُكتب `expires_at = now()` أيضًا: والإعادةُ
        # التاليةُ تستعيد المنتهيَ (`acquire_lease`) فتُدرج صفًّا جديدًا —
        # معرّفٌ جديد ⇒ ملفٌّ جديد ⇒ بادئةٌ جديدة. **والمفتاحُ الخامُ قد يبقى
        # هو هو؛ وجيلُ الخادم جديد**، لأنّ الصيانةَ أنهت القديمَ يقينًا.
        retired = await session.execute(
            update(IdempotencyRecord)
            .where(IdempotencyRecord.id == lease.record_id,
                   IdempotencyRecord.state == IN_PROGRESS,
                   IdempotencyRecord.lease_expires_at == lease.fence,
                   storage_held())
            .values(state=FAILED, completed_at=func.now(), lease_expires_at=None,
                    response_status=None,
                    response_body={"failure": REASON},
                    expires_at=func.now()))
        if (getattr(retired, "rowcount", 0) or 0) != 1:
            outcome.status = "contended"
            return outcome
        await audit.record(
            session, tenant_id=tenant_id, action="storage.orphan_reconciled",
            object_type="file", object_id=file_id, actor_user_id=None,
            actor_kind="system",
            state_after={"idempotency_record_id": str(record_id),
                         "operation": operation, "objects_deleted": len(deleted)},
            reason="operator reconciliation of an abandoned keyed upload; "
                   "no File row referenced the object")
    outcome.status = "reconciled"
    return outcome


async def reconcile(
    *, tenant_id: uuid.UUID, actor_id: uuid.UUID, apply: bool = False,
    grace: dt.timedelta = RECONCILE_GRACE, limit: int = CANDIDATE_LIMIT,
    maker: Any = None, store: storage.ObjectStore | None = None,
) -> list[Outcome]:
    """يصالح مراسيَ فاعلٍ واحدٍ في مستأجرٍ واحد — **تجربةٌ جافّةٌ افتراضًا**."""
    from ..db import tenant_session_maker  # noqa: PLC0415

    maker = maker or tenant_session_maker(tenant_id, actor_id)
    store = store or storage.get_store()
    outcomes: list[Outcome] = []
    for record_id, operation in await find_candidates(maker, grace=grace, limit=limit):
        outcomes.append(await _reconcile_one(
            maker, store, record_id=record_id, operation=operation,
            tenant_id=tenant_id, actor_id=actor_id, grace=grace, apply=apply))
    return outcomes


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m athera_api.services.storage_reconcile",
        description="Reconcile abandoned keyed-upload objects for ONE tenant+actor. "
                    "Dry-run unless --apply.")
    parser.add_argument("--tenant", required=True, type=uuid.UUID)
    parser.add_argument("--actor", required=True, type=uuid.UUID)
    parser.add_argument("--apply", action="store_true",
                        help="delete verified orphans (default: report only)")
    parser.add_argument("--limit", type=int, default=CANDIDATE_LIMIT)
    args = parser.parse_args(argv)
    outcomes = asyncio.run(reconcile(tenant_id=args.tenant, actor_id=args.actor,
                                     apply=args.apply, limit=args.limit))
    for item in outcomes:
        print(json.dumps(asdict(item), ensure_ascii=False))
    bad = {"list_failed", "delete_failed", "invariant_violation", "incomplete"}
    return 1 if any(o.status in bad for o in outcomes) else 0


if __name__ == "__main__":
    sys.exit(_main())
