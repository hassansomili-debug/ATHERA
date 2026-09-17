"""تحمُّلُ إعادةٍ آمنة للطفرات | retry-safe mutations (RC-T1-H2-A).

## ما تحلّه هذه الطبقة، وما لا تحلّه

`RC-T1-H1` أغلق النجاحَ الكاذب. **ولم يُغلق الجوابَ الغامض:** أنّ الإيداعَ
وقع لا يعني أنّ العميلَ عَلِم. فينقطع الاتصال ويُعيد العميلُ الطلبَ نفسَه،
فتقع الطفرةُ مرّتين — وقد قِيس ذلك حقًّا: بحثان من نيّةٍ واحدة.

**ولا يُدَّعى «مرّةً واحدةً بالضبط».** ما هنا **تحمُّلُ إعادةٍ آمنة**، وهو
أضعفُ وأصدق. والطور A يغطّي الطفرات **الذرّيّةَ في القاعدة** وحدها.

## والصحّةُ من PostgreSQL لا من العمليّة

لا قفلَ خيطٍ، ولا `asyncio.Lock`، ولا قاموسَ في الذاكرة. الحَكَمُ قيدُ
الفرادة `uq_idempotency_scope` — لأنّ الخوادمَ عدّة، وذاكرةَ أحدها لا تعرف
طلبًا وصل غيرَه.

## ولمَ `ON CONFLICT DO NOTHING` لا استثناءُ فرادة

الاصطدامُ الخامّ (`IntegrityError`) **يُجهض معاملةَ الخاسر كلَّها**، فيصير
عليه أن يفتح معاملةً ثانية ليقرأ جوابَ الفائز — وذاك ينقض «معاملةٌ واحدةٌ
يُديرها الطلب» من `RC-T1-H1`. و`ON CONFLICT DO NOTHING` لا يُجهض شيئًا:
يعيد صفرَ صفوفٍ، فيقرأ الخاسرُ الفائزَ في معاملته نفسِها.

## والتزامنُ يُحسم في القاعدة

    الطلب A: INSERT (غير مُودَع) → الطفرة → completed → COMMIT
    الطلب B: INSERT ... ON CONFLICT DO NOTHING
             ⇒ يقف على مُدخَل الفهرس غير المُودَع حتى يُحسم A
             ⇒ A أُودع    : صفرُ صفوف ⇒ يقرأ صفَّ A ⇒ يُعيد جوابَه
             ⇒ A رجع      : الإدراجُ ينجح ⇒ يمضي بالطفرة

فلا مفتاحٌ يُسمَّم برجوعٍ، ولا طفرةٌ تقع مرّتين.

## وما هذه الطبقة ليست

ليست محرّكَ سيرِ عملٍ موزَّعًا، ولا صندوقَ صادر. ولا حجوزَ ولا إجارات
(`lease`) هنا: تلك للطور B — المسارات ذاتُ الانتظار الخارجيّ. والحقلُ موجودٌ
في المخطَّط ولا تكتبه هذه الطبقة.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Table, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import AtheraError
from ..models.idempotency import COMPLETED, IN_PROGRESS, IdempotencyRecord

#: الترويسةُ التي يحملها العميل — **اختياريّةٌ في الطور A**.
HEADER = "Idempotency-Key"

#: ترويسةُ جوابٍ تُعلن أنّ هذا إعادةٌ لا تنفيذٌ جديد.
REPLAYED_HEADER = "Idempotency-Replayed"

#: شكلُ المفتاح — طولٌ محدودٌ ومحارفُ آمنة. والحدُّ يمنع جدولًا يتضخّم
#: بمفاتيحَ عبثيّة، ويُرفض قبل أن يلمس الطلبُ القاعدة.
_KEY = re.compile(r"^[A-Za-z0-9_-]{16,128}$")

#: أربعٌ وعشرون ساعة — **انتهاءُ صلاحيةٍ منطقيّ لا حذفٌ ماديّ**. فبعدها
#: لا يُعيد المفتاحُ جوابًا ولا يمنع طفرة، ويُستردّ عند أوّل استعمال.
#: **ولا يُدَّعى أنّ الصفَّ يُمحى عندها**: الحذفُ كسولٌ ومحدود، وصفوفُ
#: فاعلٍ توقّف عن الاستعمال تبقى حتى صيانةٍ لاحقة (الطور C).
#: والمدّةُ تكفي كلَّ إعادةٍ واقعيّةٍ لنيّةٍ واحدة — شبكةٌ متقطّعة، ومستخدمٌ
#: يُعيد بعد انقطاع، وسلسلةُ تراجعٍ في العميل.
TTL = dt.timedelta(hours=24)

#: أقصى ما يُحذف في تنظيفةٍ واحدة. والتنظيفُ **ليس شرطًا للصحّة**:
#: مفتاحٌ منتهٍ يُعالَج صحيحًا ولو لم يُنظَّف شيءٌ قطّ.
CLEANUP_LIMIT = 100

#: حدثُ التدقيق لتعارض المفاتيح — **إشارةُ سلامةٍ تبقى بعد ٤٠٩**.
CONFLICT_ACTION = "idempotency.conflict"

#: نوعُ الموضوع في سجلّ التدقيق. **ولا معرّفَ صفٍّ يُكتب**: الصفُّ المتعارَض
#: صفُّ غيرِ هذا الطلب، ومعرّفُه لا يضيف تحقيقًا ويوسّع ما يُخزَّن.
CONFLICT_OBJECT_TYPE = "idempotency_key"


class KeyInvalid(AtheraError):
    """مفتاحٌ لا يطابق الشكل — يُرفض قبل أيّ عمل."""

    def __init__(self) -> None:
        super().__init__("idempotency.key_invalid", status_code=400)


class KeyReused(AtheraError):
    """المفتاحُ نفسُه لطلبٍ مختلف — **يُرفض ولا يُعاد جوابُ الأوّل**.

    وإعادةُ جوابِ الطلب الأوّل هنا كذبٌ: العميلُ طلب شيئًا آخر. وتنفيذُ
    الثاني تحت المفتاح نفسِه يجعل المفتاحَ بلا معنى. فالرفضُ صريح.

    **والسببُ سمةٌ لا سياق**: `AtheraError.context` يُنسخ إلى جسم الجواب،
    فما يُكتب في سجلّ التدقيق لا يُعرض على العميل. والسببُ للتحقيق لا له.
    """

    #: تعارضُ بصمةٍ حقيقيّ — المفتاحُ نفسُه بجسمٍ آخر.
    FINGERPRINT = "fingerprint_mismatch"
    #: سباقٌ نادر: حُذف الصفُّ بين الإدراج والقراءة، وخسِر الطلبُ الحجزَ مرّتين.
    LOST_RACE = "lost_claim_race"

    def __init__(self, cause: str = FINGERPRINT) -> None:
        super().__init__("idempotency.key_reused", status_code=409)
        self.cause = cause


@dataclass(frozen=True, slots=True)
class Replay:
    """جوابٌ مخزونٌ يُعاد كما كان — بمعرّفه وأزمنته الأصليّة."""

    status: int
    body: Any


@dataclass(frozen=True, slots=True)
class Claim:
    """ملكيّةُ تنفيذٍ اكتُسبت، أو جوابٌ يُعاد.

    و`replay` غيرُ `None` تعني: **لا تُنفّذ الطفرة**، أعِد الجوابَ.
    """

    record_id: uuid.UUID | None
    replay: Replay | None

    @property
    def is_replay(self) -> bool:
        return self.replay is not None


def validate_key(raw: str | None) -> str | None:
    """يتحقّق من الشكل — و`None` تعني «بلا حماية»، لا خطأً.

    **والترويسةُ اختياريّةٌ في الطور A**: طلبٌ بلا مفتاحٍ يسلك مسلكَه
    القديم حرفيًّا. ولا يُختلق مفتاحٌ في الخادم: نيّةُ المستخدم لا يعرفها
    الخادم، ومفتاحٌ يُولَّد لكلّ طلبٍ لا يحمي من شيء.
    """
    if raw is None:
        return None
    key = raw.strip()
    if not _KEY.match(key):
        raise KeyInvalid
    return key


def digest_key(key: str) -> str:
    """`sha256` ست عشريًّا صغيرًا — ولا يُخزَّن الخام."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _canonical(value: Any) -> Any:
    """تطبيعٌ حتميّ: مفاتيحٌ مرتَّبة، وترتيبُ المصفوفات محفوظ.

    و`None` تبقى `None` — «الحقلُ أُرسل فارغًا» ليس «الحقلُ لم يُرسل».
    """
    if isinstance(value, dict):
        return {k: _canonical(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        # ١ و١٫٠ طلبٌ واحد — ولا يُفرَّق بينهما ببصمةٍ مختلفة.
        return int(value)
    return value


def canonical_fingerprint(
    *, method: str, operation: str, body: Any,
    query: dict[str, Any] | None = None,
) -> str:
    """بصمةٌ حتميّةٌ للمعنى — **لا لبايتات JSON**.

    و`{"a":1,"b":2}` و`{"b":2,"a":1}` طلبٌ واحد: ترتيبُ المفاتيح في JSON
    ليس معنًى، ويختلف بين عميلٍ وآخر. فلو بُصِمت البايتاتُ الخام لصار
    عميلٌ يُعيد طلبَه فيُرَدّ بتعارضٍ لا سبب له.

    **ولا يُخزَّن الجسمُ الخام** — البصمةُ وحدها تكفي للتمييز، والجسمُ قد
    يحمل محتوًى بحثيًّا لا موضعَ له في جدولٍ عابر.
    """
    payload = {
        "method": method.upper(),
        "operation": operation,
        "query": _canonical(query or {}),
        "body": _canonical(body),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


async def acquire_or_replay(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    operation: str,
    key: str,
    fingerprint: str,
    now: dt.datetime | None = None,
) -> Claim:
    """يكتسب ملكيّةَ التنفيذ، أو يعيد جوابًا مخزونًا.

    **وتُنادى داخل معاملة الطلب** بعد المصادقة والتفويض — لا قبلهما، ولا
    في وسيطٍ عامّ: لو سبقت التفويضَ لصار جوابٌ مخزونٌ يُعاد لمن لم يبقَ له
    حقٌّ فيه.
    """
    moment = now or dt.datetime.now(dt.UTC)
    digest = digest_key(key)
    scope = {
        "tenant_id": tenant_id, "actor_user_id": actor_user_id,
        "operation": operation, "key_digest": digest,
    }

    claimed = await _try_claim(session, scope=scope, fingerprint=fingerprint,
                               moment=moment)
    if claimed is not None:
        return Claim(record_id=claimed, replay=None)

    existing = (await session.execute(
        select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == tenant_id,
            IdempotencyRecord.actor_user_id == actor_user_id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.key_digest == digest,
        )
    )).scalar_one_or_none()

    if existing is None:
        # نافذةٌ ضيّقة: صفٌّ حُذف بين الإدراج والقراءة. تُعاد المحاولةُ مرّةً،
        # والقيدُ يبقى الحَكَم.
        claimed = await _try_claim(session, scope=scope, fingerprint=fingerprint,
                                   moment=moment)
        if claimed is not None:
            return Claim(record_id=claimed, replay=None)
        raise KeyReused(KeyReused.LOST_RACE)

    if existing.expires_at <= moment:
        # **مفتاحٌ منتهٍ يُستعاد حتميًّا.** والفهرسُ ما زال يحمله حتى يُحذف،
        # فلا يكفي تجاهلُه. ويُحذف ثمّ يُدرَج من جديد **في معاملةٍ واحدة**:
        # فمتسابقانِ على مفتاحٍ منتهٍ يقف ثانيهما على القيد، ولا تقع طفرتان.
        await session.execute(
            delete(IdempotencyRecord).where(IdempotencyRecord.id == existing.id))
        claimed = await _try_claim(session, scope=scope, fingerprint=fingerprint,
                                   moment=moment)
        if claimed is not None:
            return Claim(record_id=claimed, replay=None)
        # خسر السباقَ على الاستعادة: يُقرأ الفائزُ ويُعاد جوابُه.
        existing = (await session.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.tenant_id == tenant_id,
                IdempotencyRecord.actor_user_id == actor_user_id,
                IdempotencyRecord.operation == operation,
                IdempotencyRecord.key_digest == digest,
            )
        )).scalar_one()

    if existing.request_fingerprint != fingerprint:
        raise KeyReused(KeyReused.FINGERPRINT)

    if existing.state == COMPLETED and existing.response_status is not None:
        return Claim(record_id=existing.id,
                     replay=Replay(status=existing.response_status,
                                   body=existing.response_body))

    # `in_progress` مُودَعٌ لا يقع في الطور A (انظر 0037)، و`failed` تعني
    # محاولةً سابقةً لم تُثمر — فالمفتاحُ يُستعاد لمحاولةٍ صادقة.
    existing.state = IN_PROGRESS
    existing.request_fingerprint = fingerprint
    existing.response_status = None
    existing.response_body = None
    existing.completed_at = None
    existing.created_at = moment
    existing.expires_at = moment + TTL
    return Claim(record_id=existing.id, replay=None)


async def _try_claim(
    session: AsyncSession, *, scope: dict[str, Any], fingerprint: str,
    moment: dt.datetime,
) -> uuid.UUID | None:
    """إدراجٌ لا يُجهض المعاملةَ عند الاصطدام — ويعيد `None` إن خسر."""
    table = IdempotencyRecord.__table__
    assert isinstance(table, Table)  # noqa: S101 — يُضيّق النوعَ لا أكثر
    statement = (
        pg_insert(table)
        .values(
            id=uuid.uuid4(),
            **scope,
            request_fingerprint=fingerprint,
            state=IN_PROGRESS,
            created_at=moment,
            expires_at=moment + TTL,
        )
        .on_conflict_do_nothing(index_elements=[
            "tenant_id", "actor_user_id", "operation", "key_digest"])
        .returning(table.c.id)
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def complete(
    session: AsyncSession, claim: Claim, *, status: int, body: Any,
    now: dt.datetime | None = None,
) -> None:
    """يُثبّت الجوابَ في الصفِّ نفسِه — **في معاملة الطفرة**.

    فالصفُّ والطفرةُ يُودَعان معًا أو لا يُودَع أيٌّ منهما: لا مفتاحٌ يبقى
    مُكتمَلًا على طفرةٍ رجعت، ولا طفرةٌ تقع بلا مفتاحٍ يحميها من إعادتها.
    """
    if claim.record_id is None or claim.is_replay:
        return
    record = (await session.execute(
        select(IdempotencyRecord).where(IdempotencyRecord.id == claim.record_id)
    )).scalar_one()
    record.state = COMPLETED
    record.response_status = status
    record.response_body = body
    record.completed_at = now or dt.datetime.now(dt.UTC)


async def bounded_cleanup(
    session: AsyncSession, *, tenant_id: uuid.UUID,
    limit: int = CLEANUP_LIMIT, now: dt.datetime | None = None,
) -> int:
    """يحذف دفعةً محدودةً من المنتهي — **ولا تتّكل الصحّةُ عليه**.

    ولا مُجدوِلَ في هذا الطور: التنظيفُ يجري على ظهر مرورٍ قائم، محدودًا
    بمئةِ صفٍّ، وبفهرسٍ على `expires_at`. ومفتاحٌ منتهٍ يُعالَج صحيحًا ولو
    لم يُنظَّف شيءٌ قطّ — انظر استعادةَ المنتهي في `acquire_or_replay`.

    **والنطاقُ الفعليُّ أضيقُ من الشرط المكتوب**: الشرطُ مستأجرٌ،
    وسياسةُ الصفّ تشترط الفاعلَ أيضًا — فلا تُحذف إلّا صفوفُ الفاعل
    الحاليّ المنتهية. وذاك مقصود: التنظيفُ لا يُمنح صلاحيةً لا يملكها
    الطلب، والحدُّ الأمنيّ أوّلًا والصيانةُ بعده.
    """
    moment = now or dt.datetime.now(dt.UTC)
    doomed = (
        select(IdempotencyRecord.id)
        .where(IdempotencyRecord.tenant_id == tenant_id,
               IdempotencyRecord.expires_at <= moment)
        .limit(limit)
    ).scalar_subquery()
    result = await session.execute(
        delete(IdempotencyRecord).where(IdempotencyRecord.id.in_(doomed)))
    return getattr(result, "rowcount", 0) or 0


# ═══════════════ الوصلةُ بالمسار — ستّةُ أسطرٍ في المعالج ═══════════════
#
# **ولا وسيطَ عامّ (middleware).** الوسيطُ يعمل قبل حلِّ التبعيّات، فلا
# مُصادَقةَ ولا مستأجرَ ولا فاعل، ولا تفويضَ مسارٍ بعد. ولو بحث في الجدول
# هناك لصار جوابٌ مخزونٌ يُعاد **لمن سُحبت صلاحيّتُه** — وذاك التفافٌ على
# التفويض لا تحمُّلُ إعادة. فالوصلةُ تقع في متن المعالج، بعد أن يمرّ
# التفويضُ الذي يمرّ به الطلبُ الأوّل.


async def record_conflict(
    session: AsyncSession, *, tenant_id: uuid.UUID, actor_user_id: uuid.UUID,
    operation: str, cause: str, request_id: str | None,
) -> None:
    """يُدوّن التعارضَ في السجلّ المُلحَق — **وهو يبقى بعد الـ٤٠٩**.

    ## ولمَ يُكتب في معاملة الطلب نفسِها

    الطريقُ البديهيُّ أن يُرفع ٤٠٩ فورًا، لكنّ رفعَه يُرجِع المعاملة —
    **فيُمحى الحدثُ مع الرفض**، ويضيع أوّلُ ما يُنظر إليه عند التحقيق.
    وإشارةُ السلامة التي لا تبقى ليست إشارة.

    والبديلُ الثاني — معاملةٌ ثانيةٌ قصيرة تُودَع على حدة — **يُفتح بابَ
    تجمُّدٍ حقيقيّ**: `audit.record` تأخذ `pg_advisory_xact_lock` لكلّ
    مستأجرٍ لتسلسلِ سلسلة التجزئة، فمعاملةٌ ثانيةٌ تطلب القفلَ نفسَه بينما
    الأولى ما زالت مفتوحةً تنتظر إلى الأبد. ولا تُبنى صحّةٌ على أنّ الأولى
    «لم تأخذ القفلَ بعد» — ذاك شرطٌ يكسره أوّلُ تعديل.

    **فالمخرجُ ألّا يُرفع أصلًا**: يُكتب الحدثُ في المعاملة القائمة، ويُعاد
    جوابُ ٤٠٩ **قيمةً لا استثناءً**. فتُودِع البنيةُ المعاملةَ قبل إرسال
    الجواب كأيّ طفرةٍ ناجحة — وهذا **يُعمِل** RC-T1-H1 ولا يلتفّ عليه.
    وليست هذه كتابةً نصفيّة: المعاملةُ لا تحمل إلّا الحدث، ولا صفَّ مجالٍ
    فيها — الإدراجُ المتعارَض لم يُدرج شيئًا، وما قبل الحارس قراءاتٌ.

    ## وما يُكتب — وما لا يُكتب أبدًا

    **لا يُكتب**: المفتاحُ الخام، ولا جسمُ الطلب، ولا بصمتُه، ولا محتوى
    بحثٍ، ولا الجوابُ المخزون. والبصمةُ مستبعَدةٌ عمدًا: هي دالّةُ الجسم،
    وتخزينُها يسمح بتأكيد جسمٍ مُخمَّن.

    ويُكتب: المستأجرُ، والفاعلُ، والعمليّةُ (فعلٌ وقالبُ مسار)، والسببُ،
    ومعرّفُ الطلب إن وُجد.
    """
    from . import audit  # noqa: PLC0415 — يُؤجَّل ليبقى ترتيبُ الاستيراد حرًّا

    await audit.record(
        session, tenant_id=tenant_id, action=CONFLICT_ACTION,
        object_type=CONFLICT_OBJECT_TYPE, object_id=None,
        actor_user_id=actor_user_id,
        state_after={"operation": operation, "cause": cause},
        reason="an idempotency key was presented with a different request",
        request_id=request_id,
    )


def _replay_response(replay: Replay):
    """الجوابُ الأصليُّ كما كان — بحالته وجسمه ومعرّفه وأزمنته.

    و`JSONResponse` تُعيد الجسمَ المخزون حرفيًّا بلا إعادةِ تحقّقٍ من نموذج
    الجواب: المطلوبُ هو **ما رآه العميلُ أوّلَ مرّة**، لا ما يُنتجه المسارُ
    الآن.

    **ولا تُعاد ترويسةُ نقلٍ ولا أمن**: لا `Set-Cookie` ولا `Authorization`
    ولا معرّفُ طلبٍ — الجسمُ والحالةُ وحدهما، ومعهما علامةٌ تقول إنّ هذا
    إعادة.
    """
    from fastapi.responses import JSONResponse  # noqa: PLC0415

    return JSONResponse(status_code=replay.status, content=replay.body,
                        headers={REPLAYED_HEADER: "true"})


@dataclass(slots=True)
class Guard:
    """حارسُ مسارٍ واحد — و`None` يعني «بلا مفتاح، فالسلوكُ كما كان»."""

    claim: Claim | None
    operation: str
    #: جوابٌ جاهزٌ يُعاد بدل تنفيذ الطفرة: إعادةٌ مخزونة، أو رفضُ تعارضٍ
    #: دُوِّن بالفعل. و`None` تعني «امضِ في الطفرة».
    answer: Any = None

    @property
    def replay(self) -> Replay | None:
        return self.claim.replay if self.claim is not None else None

    def replay_response(self):
        """الجوابُ المخزون — و`answer` تحمله جاهزًا، وهذه تبقى للنداء المباشر."""
        replay = self.replay
        assert replay is not None  # noqa: S101 — يُضيّق النوعَ لا أكثر
        return _replay_response(replay)

    async def finish(self, session: AsyncSession, *, status: int, body: Any) -> None:
        """يُثبّت الجوابَ — في معاملة الطفرة نفسِها، فيُودَعان معًا."""
        if self.claim is None:
            return
        await complete(session, self.claim, status=status, body=body)


async def begin(
    request, session: AsyncSession, *, tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID, body: Any,
) -> Guard:
    """يقرأ الترويسةَ ويكتسب الملكيّة — أو يمضي بلا حماية.

    والعمليّةُ **قالبُ المسار** لا عنوانًا يحمل معرّفات: `route_path` من
    نطاق الطلب، فـ`/projects/{project_id}/x` عمليّةٌ واحدة مهما تغيّر
    المعرّف. وبلا قالبٍ يسقط إلى المسار الحرفيّ.
    """
    operation = (f"{request.method.upper()} "
                 f"{request.scope.get('route_path') or request.url.path}")
    key = validate_key(request.headers.get(HEADER))
    if key is None:
        return Guard(claim=None, operation=operation)

    fingerprint = canonical_fingerprint(
        method=request.method, operation=operation, body=body,
        query=dict(request.query_params))
    try:
        claim = await acquire_or_replay(
            session, tenant_id=tenant_id, actor_user_id=actor_user_id,
            operation=operation, key=key, fingerprint=fingerprint)
    except KeyReused as conflict:
        # **ويُدوَّن قبل أن يُردّ، وفي المعاملة القائمة** — انظر
        # `record_conflict`: الرفعُ هنا كان يمحو الحدثَ مع الرجوع.
        await record_conflict(
            session, tenant_id=tenant_id, actor_user_id=actor_user_id,
            operation=operation, cause=conflict.cause,
            request_id=request.headers.get("x-request-id"))
        from ..errors import athera_error_handler  # noqa: PLC0415

        return Guard(claim=None, operation=operation,
                     answer=await athera_error_handler(request, conflict))

    if claim.replay is None:
        # تنظيفٌ محدودٌ على ظهر مرورٍ قائم — ولا تتّكل الصحّةُ عليه.
        await bounded_cleanup(session, tenant_id=tenant_id)
        return Guard(claim=claim, operation=operation)
    return Guard(claim=claim, operation=operation,
                 answer=_replay_response(claim.replay))
