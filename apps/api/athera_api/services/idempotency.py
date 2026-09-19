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

from sqlalchemy import Table, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import AtheraError
from ..models.idempotency import COMPLETED, FAILED, IN_PROGRESS, IdempotencyRecord

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

    **ولا يمسّ `in_progress`**: ذاك أثرٌ غامضٌ ومرساةُ مصالحة — انظر
    الشرطَ في المتن.

    **والنطاقُ الفعليُّ أضيقُ من الشرط المكتوب**: الشرطُ مستأجرٌ،
    وسياسةُ الصفّ تشترط الفاعلَ أيضًا — فلا تُحذف إلّا صفوفُ الفاعل
    الحاليّ المنتهية. وذاك مقصود: التنظيفُ لا يُمنح صلاحيةً لا يملكها
    الطلب، والحدُّ الأمنيّ أوّلًا والصيانةُ بعده.
    """
    # ══ وساعةُ القاعدة هي الحَكَم (RC-T1-H2-B3) ══
    #
    # **وكانت ساعةَ العمليّة.** وقرارُ البقاء في الطور B-3 يُرتِّب عليه
    # **جيلًا جديدًا وهدفَ تخزينٍ جديدًا**: فخادمٌ ساعتُه متقدّمةٌ على
    # القاعدة كان يُرتجِع جيلًا لم تنقضِ ٢٤ ساعتُه عند القاعدة بعد —
    # فيُولَد هدفٌ جديدٌ قبل وقته، ويبقى كائنُ الجيل السابق بلا مالك.
    #
    # فالمقارنةُ بـ`func.now()`، ولا تُمرَّر ساعةٌ إلّا في فحصٍ يريد لحظةً
    # بعينها. والمُنادي الحيُّ لا يُمرّر شيئًا.
    moment: Any = func.now() if now is None else now
    doomed = (
        select(IdempotencyRecord.id)
        .where(IdempotencyRecord.tenant_id == tenant_id,
               IdempotencyRecord.expires_at <= moment,
               # ══ و`in_progress` لا يُمحى هنا أبدًا (RC-T1-H2-B3) ══
               #
               # **فقد يعني أنّ أثرًا خارجيًّا وقع ولا يُعرف أوقع أم لا.**
               # وفي الطور B-3 هذا الصفُّ هو **مرساةُ المصالحة**: منه
               # تُشتقّ هُويّةُ الملفّ ومفتاحُ التخزين، فمحوُه يجعل
               # الإعادةَ تُولّد هدفًا جديدًا — فيبقى كائنُ المحاولةِ
               # الأولى في المخزن لا صفَّ له ولا مالك.
               #
               # وانقضاءُ الإجارة (`lease_expires_at`) يكفي للاستيلاء،
               # فلا يُحتجَز العملُ. وتنظيفُ المهجورِ حقًّا — بعد التحقّق
               # من المخزن — شأنُ الطور C لا شأنُ تنظيفٍ عامٍّ أعمى.
               IdempotencyRecord.state != IN_PROGRESS)
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

    والعمليّةُ **قالبُ المسار** لا عنوانًا يحمل معرّفات: انظر
    `_operation_of` — كان يُقرأ من مفتاحٍ لا يضعه أحد.
    """
    operation = _operation_of(request)
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


# ═══════════════ الطور B — الحجزُ والإجارةُ والسياج ═══════════════
#
# **وقد وُصلت كلُّها** (B2…B5): بُنيت في B1 أساساتٍ بلا توصيل، ثمّ وُصلت
# طورًا طورًا. والجملةُ القديمةُ هنا — «لا مسارَ ينادي شيئًا منها» —
# صارت تاريخًا، فحُذفت كي لا يقرأها قارئٌ حالًا راهنة.
#
# ## ولمَ إجارةٌ أصلًا
#
# الطور A يكفيه أن يكون الحجزُ والطفرةُ والجوابُ في معاملةٍ واحدة. وما
# فيه فجوةٌ خارجيّة لا يكفيه ذلك: المعاملةُ يجب أن تُودَع **قبل** النداء
# الخارجيّ (RC-T1-H3)، فيبقى صفٌّ مُودَعٌ بحالِ `in_progress` لا يملكه
# أحدٌ إن مات العامل. فالإجارةُ مهلةٌ على الملكيّة، والسياجُ يمنع عاملًا
# بائتًا أن يكتب فوق من خلفه.
#
# ## والسياجُ هو `lease_expires_at` — وهذه حجّتُه
#
# ولا عمودَ مالكٍ ولا رمزَ حراسةٍ جديد. والدعوى أنّ الآجالَ **تتزايد
# تزايدًا صارمًا** بين المالكين المتعاقبين:
#
#   • الاستيلاءُ لا يقع إلّا إن كان `lease_expires_at <= now()`.
#   • فإن استولى مالكٌ ثانٍ في اللحظة `t₂` فقد كان `t₁ + L <= t₂`.
#   • وأجلُه الجديد `t₂ + L > t₁ + L` — أي أكبرُ من أجل الأوّل قطعًا.
#
# فسياجُ العامل البائت لا يساوي السياجَ القائم أبدًا، وشرطُ الإنهاء
# `lease_expires_at = :fence` يردّه بصفر صفوف. **ولا يُصدَّق هذا لأنّه
# مكتوب**: يُقاس على PostgreSQL حقيقيّة في
# `tests/test_at_rc_t1_h2b1_lease.py`.
#
# **والساعةُ ساعةُ القاعدة** (`now()`)، لا ساعةُ العمليّة: عاملان على
# آلتين بساعتين مختلفتين يجب أن يتّفقا على متى انتهت الإجارة.


@dataclass(frozen=True, slots=True)
class Lease:
    """ملكيّةُ تنفيذٍ **مُودَعة** — والسياجُ قيمتُها."""

    record_id: uuid.UUID
    operation: str
    #: الأجلُ الذي كتبه الفائزُ بنفسه — وهو السياج.
    fence: dt.datetime


@dataclass(frozen=True, slots=True)
class InProgress:
    """حَجزٌ لغيرك وإجارتُه حيّة — فلا تُنفّذ ولا تُعِد جوابًا."""

    lease_expires_at: dt.datetime


@dataclass(frozen=True, slots=True)
class Stale:
    """إنهاءٌ رُدّ: الإجارةُ لم تعد لك. **ولا طفرةَ تُودَع.**"""

    reason: str = "lease superseded"


#: مهلةُ الإجارة — تُقرَّر لكلّ صنفِ عملٍ، ولا مهلةَ واحدةٌ للكلّ.
#: والمهلةُ يجب أن تفوق مهلةَ المزوّد نفسِه، وإلّا زاحم الاستيلاءُ نداءً
#: ما زال يعمل.
LEASE_NETWORK = dt.timedelta(seconds=30)
LEASE_STORAGE = dt.timedelta(seconds=120)
LEASE_MODEL = dt.timedelta(seconds=300)


async def _claim_with_lease(
    session: AsyncSession, *, scope: dict, fingerprint: str, ttl: dt.timedelta,
) -> dt.datetime | None:
    """يحجز صفًّا جديدًا بإجارة — ويعيد السياج، أو `None` إن سبقه غيرُه."""
    table = IdempotencyRecord.__table__
    assert isinstance(table, Table)  # noqa: S101 — يُضيّق النوعَ لا أكثر
    seconds = ttl.total_seconds()
    statement = (
        pg_insert(table)
        .values(id=uuid.uuid4(), **scope, request_fingerprint=fingerprint,
                state=IN_PROGRESS,
                created_at=func.now(),
                expires_at=func.now() + TTL,
                lease_expires_at=func.now() + dt.timedelta(seconds=seconds))
        .on_conflict_do_nothing(index_elements=[
            "tenant_id", "actor_user_id", "operation", "key_digest"])
        .returning(table.c.id, table.c.lease_expires_at)
    )
    row = (await session.execute(statement)).first()
    return None if row is None else row[1]


async def acquire_lease(
    session: AsyncSession, *, tenant_id: uuid.UUID, actor_user_id: uuid.UUID,
    operation: str, key: str, fingerprint: str,
    ttl: dt.timedelta = LEASE_MODEL,
) -> Lease | Replay | InProgress | ExternalUnknown:
    """يكتسب إجارةً، أو يعيد جوابًا مخزونًا، أو يقول «قائمٌ لغيرك».

    **وتُنادى داخل معاملةٍ يُودِعها المُنادي قبل أيّ عملٍ خارجيّ.** ولا
    تُمسَك هذه المعاملةُ عبر النداء الخارجيّ — وذاك شرطُ RC-T1-H3، وهو
    مسؤوليّةُ المُنادي لا هذه الدالّة.

    والقرارُ عند وجود صفٍّ سابق:

      • `completed` وبصمةٌ مطابقة  ⇒ `Replay`
      • بصمةٌ مختلفة             ⇒ `KeyReused` (كما في الطور A)
      • `in_progress` وإجارةٌ حيّة ⇒ `InProgress`
      • إجارةٌ منتهية أو `failed`  ⇒ استيلاءٌ مُحكَمٌ بالقاعدة
    """
    digest = digest_key(key)
    scope = {
        "tenant_id": tenant_id, "actor_user_id": actor_user_id,
        "operation": operation, "key_digest": digest,
    }

    fence = await _claim_with_lease(session, scope=scope, fingerprint=fingerprint,
                                   ttl=ttl)
    if fence is not None:
        return Lease(record_id=await _record_id(session, scope), operation=operation,
                     fence=fence)

    existing = (await session.execute(
        select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == tenant_id,
            IdempotencyRecord.actor_user_id == actor_user_id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.key_digest == digest,
        )
    )).scalar_one_or_none()
    if existing is None:
        # نافذةٌ ضيّقة: حُذف الصفُّ بين الإدراج والقراءة. تُعاد المحاولةُ مرّة.
        fence = await _claim_with_lease(session, scope=scope,
                                        fingerprint=fingerprint, ttl=ttl)
        if fence is not None:
            return Lease(record_id=await _record_id(session, scope),
                         operation=operation, fence=fence)
        raise KeyReused(KeyReused.LOST_RACE)

    # ══ جيلٌ انقضى بقاؤه يُستعاد — ولا مفتاحَ أبديّ ══
    #
    # **وهذا عقدُ الطور A نفسُه** (`acquire_or_replay`): بعد `expires_at` لا
    # يمنع مفتاحٌ مُتَمٌّ طفرةً جديدة. ولم تكن هذه الدالّةُ تقرأ `expires_at`
    # قطّ، فكان مفتاحٌ مُتَمٌّ يُعيد جوابَه **إلى الأبد** — عقدٌ يناقض
    # الطور A، ويُفسد الطور B-3 حين تُشتقّ هُويّةُ التخزين من المفتاح.
    #
    # والاستعادةُ حذفٌ ثمّ إدراجٌ في المعاملة نفسِها، فيتغيّر `id` —
    # **وذاك بعينه جيلٌ جديدٌ وهدفُ تخزينٍ جديد**.
    #
    # **و`in_progress` لا يُستعاد هكذا أبدًا**: قد يكون أثرٌ خارجيٌّ وقع
    # ولا يُعرف أوقع أم لا. فأمرُه إلى `lease_expires_at` (استيلاءٌ) لا
    # إلى `expires_at` (استعادة). وخلطُهما يجعل الغامضَ هدفًا جديدًا.
    #
    # **وبساعةِ القاعدة** (`func.now()`) لا بساعةِ العمليّة: الخوادمُ عدّةٌ
    # وساعاتُها تتفارق، والحَكَمُ واحد.
    if existing.state in (COMPLETED, FAILED):
        retired = await session.execute(
            delete(IdempotencyRecord)
            .where(IdempotencyRecord.id == existing.id,
                   IdempotencyRecord.state.in_((COMPLETED, FAILED)),
                   IdempotencyRecord.expires_at <= func.now())
        )
        if (getattr(retired, "rowcount", 0) or 0) == 1:
            # فاز بالاستعادة: جيلٌ جديدٌ بمعرّفٍ جديد.
            fence = await _claim_with_lease(session, scope=scope,
                                            fingerprint=fingerprint, ttl=ttl)
            if fence is not None:
                return Lease(record_id=await _record_id(session, scope),
                             operation=operation, fence=fence)
        # لم يُستعَد — إمّا البقاءُ قائم، وإمّا سبقنا مُستعيدٌ آخر. ويُعاد
        # القراءةُ فيُحكَم على **الصفّ القائم الآن** لا على لقطةٍ قديمة.
        refreshed = (await session.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.tenant_id == tenant_id,
                IdempotencyRecord.actor_user_id == actor_user_id,
                IdempotencyRecord.operation == operation,
                IdempotencyRecord.key_digest == digest,
            )
        )).scalar_one_or_none()
        if refreshed is None:
            raise KeyReused(KeyReused.LOST_RACE)
        existing = refreshed

    if existing.request_fingerprint != fingerprint:
        raise KeyReused(KeyReused.FINGERPRINT)

    if existing.state == COMPLETED and existing.response_status is not None:
        return Replay(status=existing.response_status, body=existing.response_body)

    # ══ جيلٌ عبَر الحدَّ الخارجيَّ لا يُعاد نداؤه (RC-T1-H2-B4) ══
    #
    # **وهذا موضعُ افتراقِ B-4 عن B-2/B-3.** هناك كان الاستيلاءُ بعد انتهاء
    # الإجارة صحيحًا لأنّ الهدفَ ثابتٌ والمحتوى هو هو: كتابةٌ ثانيةٌ إلى
    # المفتاح نفسِه لا تُفسد شيئًا. وهنا الأثرُ **توليدٌ مدفوع**: تكرارُه
    # يُحاسَب ولا يُسترَدّ.
    #
    # فإن حمل الصفُّ وسمَ العبور ولم يُثبَت لمزوّده إزالةُ تكرارٍ عند
    # الخادم، فلا استيلاءَ ولا نداءَ — بل قولُ الحقّ: لا يُعرف.
    #
    # ولا يعرف هذا الموضعُ بائعًا: الوسمُ يحمل القدرةَ نصًّا كتبه المُنادي.
    # **وإجارةٌ حيّةٌ تبقى «قائمًا لغيرك»**: صاحبُها ما زال يعمل وقد يعود
    # بجوابٍ ناجح. فالغموضُ لا يُعلَن إلّا حين تنقضي الإجارةُ ولا مالكَ.
    # ويُسأل الانقضاءُ **بساعة القاعدة** لا بساعة العمليّة.
    marker = _external_attempted(existing)
    if existing.state == IN_PROGRESS and marker is not None:
        abandoned = (await session.execute(
            select(IdempotencyRecord.id).where(
                IdempotencyRecord.id == existing.id,
                or_(IdempotencyRecord.lease_expires_at.is_(None),
                    IdempotencyRecord.lease_expires_at <= func.now()))
        )).first() is not None
        if abandoned and marker.get("capability") != "server_deduplicated":
            return ExternalUnknown(provider=str(marker.get("provider", "")),
                                   capability=str(marker.get("capability", "")))

    # ══ استيلاءٌ: القاعدةُ هي الحَكَم، ولا قفلَ في العمليّة ══
    #
    # والشرطُ في عبارة الكتابة نفسِها: `lease_expires_at <= now()`. فمتسابقان
    # على إجارةٍ منتهية يصيب أحدُهما صفًّا والآخرُ صفرًا — بلا قفلٍ ولا
    # Redis ولا تحكيمٍ في الذاكرة.
    seconds = ttl.total_seconds()
    taken = (await session.execute(
        update(IdempotencyRecord)
        .where(IdempotencyRecord.id == existing.id,
               IdempotencyRecord.state.in_((IN_PROGRESS, FAILED)),
               or_(IdempotencyRecord.lease_expires_at.is_(None),
                   IdempotencyRecord.lease_expires_at <= func.now()))
        .values(state=IN_PROGRESS,
                lease_expires_at=func.now() + dt.timedelta(seconds=seconds),
                # **ويُمدّ البقاءُ مع الاستيلاء**: جيلٌ يُعمل عليه الآن لا
                # يُرتجَع من تحت عامله لأنّ ساعةً قديمةً انقضت.
                expires_at=func.now() + TTL,
                completed_at=None, response_status=None, response_body=None)
        .returning(IdempotencyRecord.lease_expires_at)
    )).first()
    if taken is not None:
        return Lease(record_id=existing.id, operation=operation, fence=taken[0])

    # لم يُستولَ: إمّا الإجارةُ حيّةٌ لغيرنا، وإمّا سبقنا مستولٍ آخر.
    live = (await session.execute(
        select(IdempotencyRecord.lease_expires_at, IdempotencyRecord.state)
        .where(IdempotencyRecord.id == existing.id)
    )).one()
    if live[1] == COMPLETED:
        fresh = (await session.execute(
            select(IdempotencyRecord).where(IdempotencyRecord.id == existing.id)
        )).scalar_one()
        return Replay(status=fresh.response_status or 0, body=fresh.response_body)
    return InProgress(lease_expires_at=live[0])


async def _record_id(session: AsyncSession, scope: dict) -> uuid.UUID:
    """معرّفُ الصفّ في نطاقه — يُقرأ بعد حجزٍ فائز."""
    return (await session.execute(
        select(IdempotencyRecord.id).where(
            IdempotencyRecord.tenant_id == scope["tenant_id"],
            IdempotencyRecord.actor_user_id == scope["actor_user_id"],
            IdempotencyRecord.operation == scope["operation"],
            IdempotencyRecord.key_digest == scope["key_digest"],
        )
    )).scalar_one()


async def finalize_leased(
    session: AsyncSession, lease: Lease, *, status: int, body: Any,
) -> Stale | None:
    """يُنهي عملًا مُستأجَرًا — **إن كانت الإجارةُ ما زالت لك**.

    ويُنادى في معاملةِ الطفرة نفسِها: فإن رُدَّ (`Stale`) وجب على المُنادي
    أن يُرجِع المعاملةَ، فلا تُودَع طفرةٌ لعاملٍ فقد إجارتَه.

    والشرطُ سياجٌ: `lease_expires_at = :fence`. وآجالُ المالكين تتزايد
    تزايدًا صارمًا (انظر رأس هذا القسم)، فسياجُ البائت لا يطابق القائم.
    """
    settled = await session.execute(
        update(IdempotencyRecord)
        .where(IdempotencyRecord.id == lease.record_id,
               IdempotencyRecord.state == IN_PROGRESS,
               IdempotencyRecord.lease_expires_at == lease.fence)
        .values(state=COMPLETED, response_status=status, response_body=body,
                completed_at=func.now(), lease_expires_at=None)
    )
    if (getattr(settled, "rowcount", 0) or 0) == 1:
        return None
    return Stale()


async def fail_leased(
    session: AsyncSession, lease: Lease, *, reason: str,
) -> Stale | None:
    """يُسجّل إخفاقًا **معلومًا** — والمفتاحُ يبقى قابلًا لإعادةِ محاولةٍ صادقة.

    **ولا يُستعمل لنتيجةٍ غامضة.** فإخفاقٌ حتميٌّ معروف (رفضٌ من المزوّد،
    مدخلٌ غيرُ صالح) يُسجَّل `failed` فيُعاد المحاولةُ بأمان. أمّا نداءٌ
    انقطع ولا يُعرف أوقع أثرُه أم لا فذاك بابٌ آخر، ولا تُختلق له دلالةٌ
    في هذا الطور.
    """
    settled = await session.execute(
        update(IdempotencyRecord)
        .where(IdempotencyRecord.id == lease.record_id,
               IdempotencyRecord.state == IN_PROGRESS,
               IdempotencyRecord.lease_expires_at == lease.fence)
        .values(state=FAILED, completed_at=func.now(), lease_expires_at=None,
                response_status=None,
                response_body={"failure": reason[:200]})
    )
    if (getattr(settled, "rowcount", 0) or 0) == 1:
        return None
    return Stale()


# ═══════════ وصلةُ الطور B بالمسار — تحضيرٌ يملك معاملتَه ═══════════
#
# **ولمَ مُعاملٌ للجلسة لا جلسةٌ جاهزة.**
#
# مساراتُ الطور B لا تملك جلسةَ طلبٍ أصلًا (`Depends(get_session)` غائبةٌ
# عنها عمدًا: RC-T1-H3). فالتحضيرُ يفتح معاملتَه القصيرة **ويُودعها** ثمّ
# يُعيد التحكّم، فلا يبقى شيءٌ مفتوحًا حين يبدأ الانتظارُ الخارجيّ. ولو
# أُعطيت هذه الدالّةُ جلسةً جاهزةً لَورّطت المُنادي في إبقائها.


#: رفضٌ صريحٌ حين تكون الإجارةُ حيّةً لغيرك — **ولا يُنتظر عليها**.
IN_PROGRESS_CODE = "idempotency.in_progress"
#: الإجارةُ لم تعد لك — استُولي عليها بعد انتهائها.
SUPERSEDED_CODE = "idempotency.lease_superseded"


class InProgressRefused(AtheraError):
    """طلبٌ بمفتاحٍ إجارتُه حيّةٌ لعاملٍ آخر — يُردّ ولا يُكرَّر النداء."""

    def __init__(self) -> None:
        super().__init__(IN_PROGRESS_CODE, status_code=409)


class LeaseSuperseded(AtheraError):
    """رُفع بعد أن فُقدت الإجارة — **ويُرجِع معاملةَ الإنهاء كلَّها**.

    ورفعُه داخل `async with` الجلسة يُرجِع المعاملة، فلا تُودَع طفرةُ
    مجالٍ ولا حدثُ تدقيقٍ لعاملٍ بائت. وهذا هو المقصود: الرجوعُ لا التبليغ.
    """

    def __init__(self) -> None:
        super().__init__(SUPERSEDED_CODE, status_code=409)


@dataclass(slots=True)
class LeaseGuard:
    """نتيجةُ التحضير: إمّا جوابٌ يُعاد الآن، وإمّا إجارةٌ يُعمل تحتها.

    و`answer` و`lease` لا يجتمعان. وكلاهما `None` يعني **بلا مفتاح**:
    فالمسارُ يسلك مسلكَه القديم حرفيًّا، ولا حجزَ ولا إعادة.
    """

    lease: Lease | None = None
    answer: Any = None
    operation: str = ""
    #: هُويّةٌ ثابتةٌ **لهذا الجيل** — `None` بلا إجارةٍ مكتسَبة (B-3).
    #:
    #: ومرساتُها `Lease.record_id`: تبقى عبر الاستيلاء وانتهاء الإجارة،
    #: وتتغيّر حين يُستعاد المفتاحُ بعد انقضاء بقائه.
    stable_id: uuid.UUID | None = None
    #: الإعادةُ **قيمةً** حين يطلب المسارُ ذلك: جسمٌ مخزونٌ يُعاد بناؤه.
    #:
    #: ولهذا موضعٌ واحد: جوابٌ يحمل **قدرةً عابرة** (رابطٌ موقّع) لا يجوز
    #: تخزينُها ولا إعادتُها بعد انتهائها. فيُخزَّن ما يدوم، ويُولَّد
    #: العابرُ من جديدٍ عند كلّ إعادة.
    replay: Replay | None = None


# ══════════ حدُّ التنفيذ الخارجيّ — الطور B-4 ══════════
#
# ## العطبُ الذي يُغلق
#
# **مهلةٌ بعد إرسال طلبٍ إلى نموذجٍ لا تُثبت أنّ النموذجَ لم ينفّذ.** فقد
# ولّد وحُوسِبنا ثمنَه، وانقطع السلكُ قبل أن يعود الجواب. فإعادةُ النداء
# عميانًا تُنفّذ توليدًا ثانيًا وتُحاسَب مرّةً ثانية.
#
# ## ولمَ لا يكفي التقاطُ الاستثناء
#
# العمليّةُ قد تموت **وهي واقفةٌ داخل نداء المزوّد**: لا استثناءَ يُلتقَط،
# ولا `finally` يعمل. فلا بدّ من تدوينٍ **مُودَعٍ قبل النداء** يقول إنّ
# هذا الجيلَ عبَر الحدّ.
#
# وتبقى نافذةٌ ضيّقة: يُودَع التدوينُ ثمّ تموت العمليّةُ قبل أن يخرج
# الطلبُ فعلًا. وحينها نقول «لا يُعرف» ونحن نعلم أنّه لم يُرسَل —
# **والسلامةُ قبل الإعادةِ التلقائيّة**: أن نمتنع عن توليدٍ مدفوعٍ ثانٍ
# أهونُ من أن نُكرّره.
#
# ## وكيف يُمثَّل في المخطَّط 0037 بلا هجرة
#
#     `state='in_progress'` وبلا وسمٍ  ⇒ عملٌ مهجورٌ **قبل** الحدّ  ⇒ يُستولى عليه
#     `state='in_progress'` ومعه وسمٌ ⇒ عبَر الحدَّ ولا يُعرف أثرُه ⇒ لا يُعاد النداء
#     `state='completed'`             ⇒ إعادةٌ من عندنا بلا مزوّد
#     `state='failed'`                ⇒ إخفاقٌ **معلومٌ** قبل الحدّ ⇒ يُعاد بأمان
#
# والوسمُ يُكتب في `response_body` و`response_status` يبقى `NULL`، وشرطُ
# الإعادة `state == COMPLETED and response_status is not None` — فلا يصير
# وسمٌ جوابًا يُعاد. ويمحوه الإتمامُ لأنّه يكتب الجسمَ الحقيقيّ فوقه.
#: مفتاحُ الوسم — حضورُه في `response_body` مع `in_progress` هو الدعوى.
EXTERNAL_MARKER = "__athera_external_attempt__"

#: رمزٌ صادقٌ لأثرٍ لا يُعرف — لا «أخفق» ولا «لم يُنفَّذ».
EXTERNAL_UNKNOWN_CODE = "idempotency.external_result_unknown"


class ExternalResultUnknown(AtheraError):
    """قد يكون النموذجُ نفّذ — ولا يُعاد النداءُ تحت الجيل نفسِه.

    ومن أراد تنفيذًا جديدًا فليبدأ **جيلًا جديدًا** بمفتاحٍ آخر: القرارُ
    قرارُه، ولا يُتّخذ عنه صامتًا.
    """

    def __init__(self) -> None:
        super().__init__(EXTERNAL_UNKNOWN_CODE, status_code=409)


@dataclass(frozen=True, slots=True)
class ExternalUnknown:
    """نتيجةُ تحكيمٍ: هذا الجيلُ عبَر الحدَّ ولا يُعرف أثرُه."""

    provider: str = ""
    capability: str = ""


def _external_attempted(row) -> dict | None:
    """وسمُ عبورِ الحدّ إن كان الصفُّ يحمله — وإلّا `None`."""
    body = row.response_body
    if isinstance(body, dict):
        marker = body.get(EXTERNAL_MARKER)
        if isinstance(marker, dict):
            return marker
    return None


async def mark_external_attempt(
    session: AsyncSession, lease: Lease, *, provider: str, capability: str,
) -> Stale | None:
    """يُدوّن عبورَ الحدّ — **ويُنادى في معاملةٍ تُودَع قبل نداء المزوّد**.

    ومُسَيَّجٌ كالإنهاء: عاملٌ فقد إجارتَه لا يُدوّن على جيلٍ صار لغيره.
    """
    settled = await session.execute(
        update(IdempotencyRecord)
        .where(IdempotencyRecord.id == lease.record_id,
               IdempotencyRecord.state == IN_PROGRESS,
               IdempotencyRecord.lease_expires_at == lease.fence)
        .values(response_body={EXTERNAL_MARKER: {
            "provider": provider[:64], "capability": capability[:64]}})
    )
    if (getattr(settled, "rowcount", 0) or 0) == 1:
        return None
    return Stale()


#: فضاءُ أسماءٍ ثابتٌ لهُويّات الطور B-3 — لا يتغيّر بعد اليوم.
#:
#: وتغييرُه يعني أنّ إعادةَ طلبٍ قديمٍ تُولّد هُويّةً أخرى، فيُكتب كائنٌ
#: ثانٍ لنيّةٍ واحدة. فهو ثابتٌ كالمخطَّط، لا إعدادٌ يُضبط.
STABLE_NAMESPACE = uuid.UUID("6f1c9a52-0e4d-5b77-9c3a-2d8e41b0f6a7")


def stable_object_id(record_id: uuid.UUID) -> uuid.UUID:
    """هُويّةٌ ثابتةٌ **لجيلِ حجزٍ واحد** — مرساتُها صفُّ الإجارة.

    ## ولمَ لا تُشتقّ من نطاق المفتاح

    كانت تُشتقّ من (مستأجر + فاعل + عمليّة + بصمةُ مفتاح). وذاك **دائمٌ
    للمفتاح**، وهو يناقض عقدَ البقاء ٢٤ ساعة (`TTL`) — فيُفسد البيانات:

        ١· رفعٌ بمفتاح K وبايتات A ينجح؛ فصفٌّ A وكائنٌ A قائمان.
        ٢· ينقضي `expires_at` ويُنظَّف صفُّ الحجز.
        ٣· يُعاد K لاحقًا ببايتات B والاسم نفسِه.
        ٤· جيلٌ جديدٌ ببصمة B — **لكنّ الهُويّةَ المشتقّةَ هي القديمة**.
        ٥· فتُكتب B على **مفتاح A**، ويُعاد استعمالُ صفِّ A.
        ⇒ القاعدةُ تصف A والمخزنُ يحمل B.

    ## والمرساةُ الصحيحة: `id` صفِّ الإجارة

    المعرّفُ يبقى نفسَه للمُطالِب الأوّل، وعبر انتهاء الإجارة، وعبر
    الاستيلاء، ولعامِلين متزامنين — **ويتغيّر حين يُستعاد المفتاحُ بعد
    انقضاء بقائه**، لأنّ الاستعادةَ تحذف الصفَّ وتُدرج غيرَه. فالثباتُ
    ثباتُ **جيل**، لا ثباتٌ أبديٌّ للمفتاح. ولا إزالةَ تكرارٍ أبديّة.

    **ولا عمودَ جديد**: `id` مُودَعٌ في المخطَّط 0037 أصلًا.
    """
    return uuid.uuid5(STABLE_NAMESPACE, f"idempotency-generation:{record_id}")


def is_keyed(request) -> bool:
    """أحمَل الطلبُ ترويسةَ مفتاحٍ — **بلا تدقيقِ شكلٍ ولا رفع**.

    ولهذا موضعٌ واحد: مسارٌ ترتيبُ أطوارِه يفترق بين المُمفتَحِ وغيرِه
    (`/references/search`: التحضيرُ قبل حدِّ المعدّل للمُمفتَح، والحدُّ
    وحدَه لغيرِه). فيُسأل **الحضور** لا الصحّة؛ والصحّةُ يليها
    `begin_leased` فيرفع ٤٠٠ للمشوَّه — قبل أن يُستهلَك حدُّ أحد.
    """
    return request.headers.get(HEADER) is not None


async def begin_leased(
    request, maker, *, tenant_id: uuid.UUID, actor_user_id: uuid.UUID,
    body: Any, ttl: dt.timedelta, replay_as_value: bool = False,
) -> LeaseGuard:
    """التحضير في معاملةٍ **خاصّةٍ به** ثمّ يُعيد التحكّم بلا معاملةٍ مفتوحة.

    ويُنادى **بعد** المصادقة والتفويض: الحجزُ ليس بوّابةَ وصول، ومن لا
    يملك الحقَّ لا يبلغ هذا السطر.

    و`maker` دالّةٌ تفتح جلسةً تملك إيداعَها (`db.tenant_session_maker`).
    """
    if validate_key(request.headers.get(HEADER)) is None:
        # بلا مفتاحٍ لا جلسةَ تُفتح: المسلكُ القديم حرفيًّا، ولا رحلةَ
        # ذهابٍ إلى قاعدةٍ في مدينةٍ أخرى بلا داعٍ.
        return LeaseGuard(operation=_operation_of(request))
    async with maker() as session:
        return await begin_leased_in(
            session, request, tenant_id=tenant_id, actor_user_id=actor_user_id,
            body=body, ttl=ttl, replay_as_value=replay_as_value)


async def begin_leased_in(
    session: AsyncSession, request, *, tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID, body: Any, ttl: dt.timedelta,
    replay_as_value: bool = False,
) -> LeaseGuard:
    """التحضيرُ نفسُه **في معاملةٍ يملكها المُنادي**.

    ولهذا موضعٌ واحد: مسارٌ يحتاج أن يقرأ من القاعدة ما يبني به معنى
    الطلب (`verify` يقرأ المعرّف)، فتُوفَّر رحلةٌ ويُقرأ ويُحجز في معاملةٍ
    واحدة. وعلى المُنادي أن يُودِعها — والخروجُ من `async with` يفعل.
    """
    operation = _operation_of(request)
    key = validate_key(request.headers.get(HEADER))
    if key is None:
        return LeaseGuard(operation=operation)

    fingerprint = canonical_fingerprint(
        method=request.method, operation=operation, body=body,
        query=dict(request.query_params))

    try:
        outcome = await acquire_lease(
            session, tenant_id=tenant_id, actor_user_id=actor_user_id,
            operation=operation, key=key, fingerprint=fingerprint, ttl=ttl)
    except KeyReused as conflict:
        # **تُدوَّن في هذه المعاملة بعينها فتُودَع معها** — كما في الطور A:
        # الرفعُ كان يمحو الحدثَ مع الرجوع. فيُعاد الجوابُ **قيمةً**.
        await record_conflict(
            session, tenant_id=tenant_id, actor_user_id=actor_user_id,
            operation=operation, cause=conflict.cause,
            request_id=request.headers.get("x-request-id"))
        from ..errors import athera_error_handler  # noqa: PLC0415

        return LeaseGuard(operation=operation,
                          answer=await athera_error_handler(request, conflict))

    if isinstance(outcome, Replay):
        # **والإعادةُ قيمةً حين يطلبها المسار**: جوابٌ يحمل قدرةً عابرة
        # يُعاد بناؤه من المخزون الدائم، ولا يُعاد المخزونُ حرفيًّا.
        if replay_as_value:
            return LeaseGuard(operation=operation, replay=outcome)
        return LeaseGuard(operation=operation, answer=_replay_response(outcome))
    if isinstance(outcome, ExternalUnknown):
        # أثرٌ لا يُعرف — ٤٠٩ صادقة، ولا نداءَ ثانيًا لمزوّدٍ قد نفّذ.
        from ..errors import athera_error_handler  # noqa: PLC0415

        return LeaseGuard(operation=operation,
                          answer=await athera_error_handler(request,
                                                            ExternalResultUnknown()))
    if isinstance(outcome, InProgress):
        from ..errors import athera_error_handler  # noqa: PLC0415

        return LeaseGuard(operation=operation,
                          answer=await athera_error_handler(request, InProgressRefused()))
    # ══ والتنظيفُ المحدودُ هنا أيضًا (H2-C) ══
    #
    # **وكان الطورُ A وحدَه يبلغه.** `begin` تنظّف على ظهر كلِّ جيلٍ جديد،
    # وهذه لم تكن تنظّف قطّ — فالمساراتُ المُجارةُ كلُّها (B2…B5) تُراكم
    # صفوفَها المنتهية بلا حدّ. والموضعُ هو موضعُ الطور A نفسُه: **جيلٌ
    # جديدٌ فاز بإجارته**، لا إعادةٌ ولا رفض.
    #
    # وهو في المعاملة القصيرة **قبل** الانتظار الخارجيّ (RC-T1-H3): عبارةٌ
    # واحدةٌ محدودةٌ بمئة صفّ، ولا شبكةَ فيها. ولا يمسّ `in_progress` —
    # فمرساةُ المصالحة تبقى — ولا يتعدّى فاعلَ الطلب (RLS).
    await bounded_cleanup(session, tenant_id=tenant_id)
    # **والهُويّةُ من الإجارة وحدَها**: مرساتُها `record_id`، فلا تُعرَف قبل
    # اكتسابها — ولا تُعرَف لجيلٍ غير هذا.
    return LeaseGuard(lease=outcome, operation=operation,
                      stable_id=stable_object_id(outcome.record_id))


def _operation_of(request) -> str:
    """اسمُ العمليّة: المسارُ **المُقولَب** لا المُستبدَل.

    فـ`/sources/{source_id}/verify` عمليّةٌ واحدةٌ لكلّ المصادر، ومعرّفُ
    المصدر يدخل في **البصمة** لا في الاسم. ولو دخل الاسمَ لَصار لكلّ مصدرٍ
    فضاءُ مفاتيحَ خاصٌّ به، فمفتاحٌ أُعيد على مصدرٍ آخر لا يُكشَف تعارضُه.

    **وكان هذا مكسورًا:** `scope["route_path"]` مفتاحٌ **لا يضعه أحد** — لا
    هذا المستودع ولا Starlette (وفيها `get_route_path` دالّةٌ تحسبه ولا
    تُودعه النطاق). فكان التعبيرُ يسقط دائمًا إلى `request.url.path`
    المُستبدَل. والذي يضعه FastAPI هو `scope["route"]`، و`.path` منه قالبٌ
    تامٌّ يحمل بادئةَ الموجِّه. وقد قِيس الأمران: الأوّلُ غائبٌ والثاني
    `/api/v1/sources/{source_id}/verify`.

    ومساراتُ الطور A الأربعةُ بلا معاملٍ في المسار (`/runs` و`/manuscripts`
    و`/projects` مرّتين)، فالتصحيحُ **لا يُغيّر اسمَ عمليّةٍ لمفتاحٍ قائم**:
    المُستبدَلُ والقالبُ فيها نصٌّ واحد. وقد قِيس ذلك أيضًا.
    """
    route_path = getattr(request.scope.get("route"), "path", None)
    return f"{request.method.upper()} {route_path or request.url.path}"


async def begin_model(
    request, maker, *, tenant_id: uuid.UUID, actor_user_id: uuid.UUID,
    body: Any, ttl: dt.timedelta = LEASE_MODEL,
) -> LeaseGuard:
    """تحضيرُ مسارِ نموذج — إجارةٌ تُودَع قبل أيّ نداءٍ للمزوّد.

    وهو `begin_leased` بمدّةِ النموذج؛ ويُفرَد باسمه لأنّ مساراتِ النموذج
    تلزمها خطوةٌ لا يلزم غيرَها: `enter_external` قبل النداء.
    """
    return await begin_leased(request, maker, tenant_id=tenant_id,
                              actor_user_id=actor_user_id, body=body, ttl=ttl)


async def enter_external(maker, guard: LeaseGuard, *, provider: str,
                         capability: str) -> None:
    """يُودِع وسمَ عبورِ الحدّ — **ويُنادى قبل نداء المزوّد لا بعده**.

    ومعاملتُه قصيرةٌ تُغلق فورًا، فلا تمتدّ معاملةٌ على انتظارِ نموذج
    (RC-T1-H3). وبلا مفتاحٍ لا يفعل شيئًا: لا حجزَ فلا وسم.

    ويرفع `LeaseSuperseded` إن كان قد فُقد السياج — فلا يُنادى المزوّدُ
    باسم جيلٍ صار لغيرنا.
    """
    if guard.lease is None:
        return
    async with maker() as session:
        if await mark_external_attempt(session, guard.lease, provider=provider,
                                       capability=capability) is not None:
            raise LeaseSuperseded


class ModelBoundary:
    """مُعلَّقٌ يقف على حدِّ المزوّد — ويُخبر أَعبَرَه الطلبُ أم لا.

    ويُمرَّر إلى المنسّقِ أو المستخرِج، فيُنادى **بعد** التفويض و**قبل**
    `invoke` مباشرةً. فموضعُ الحدِّ يملكه المنسّق، ولا يُكرَّر في ستّة
    موجِّهات، ولا يُخمّنه موجِّهٌ من خارجه.

    و`crossed` هي فارقُ الصدق: ما رُدّ قبل العبور **لم يبلغ مزوّدًا**،
    فيُغلَق مفتاحُه إخفاقًا معلومًا ويبقى قابلًا لإعادةٍ صادقة؛ وما عبَر
    لا يُعرف أثرُه فلا يُعاد نداؤه.
    """

    __slots__ = ("_maker", "_guard", "_provider", "_capability", "crossed")

    def __init__(self, maker, guard: LeaseGuard, *, provider: str,
                 capability: str) -> None:
        self._maker = maker
        self._guard = guard
        self._provider = provider
        self._capability = capability
        self.crossed = False

    async def __call__(self) -> None:
        await enter_external(self._maker, self._guard, provider=self._provider,
                             capability=self._capability)
        self.crossed = True


async def close_pre_external(maker, guard: LeaseGuard, *, reason: str) -> None:
    """يُغلق جيلًا رُدّ **قبل** الحدّ — فيبقى المفتاحُ قابلًا للإعادة.

    ولا يُوسَم غامضًا: لم يُنادَ مزوّدٌ، وهذا معلومٌ لا مظنون.
    """
    if guard.lease is None:
        return
    async with maker() as session:
        await fail_leased(session, guard.lease, reason=reason)


async def settle_leased(
    session: AsyncSession, guard: LeaseGuard, *, status: int, body: Any,
) -> None:
    """يُنهي تحت السياج — **ويرفع إن فُقدت الإجارة**.

    ويُنادى داخل معاملةِ الإنهاء نفسِها، فرفعُه يُرجِعها: صفرُ طفراتٍ
    لعاملٍ بائت. وبلا مفتاحٍ لا يفعل شيئًا.
    """
    if guard.lease is None:
        return
    if await finalize_leased(session, guard.lease, status=status, body=body) is not None:
        raise LeaseSuperseded
