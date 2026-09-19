"""سِجلُّ تنفيذِ أقسامِ المستند | the per-section execution ledger (RC-T1-H2-B5).

**ولمَ قسمًا قسمًا لا تشغيلةً واحدة؟** لأنّ كلَّ قسمٍ نداءُ مزوّدٍ مستقلٌّ
مدفوع. فحاجزٌ واحدٌ للأقسام السبعة يعني أنّ سقوطًا في القسم السابع يجعل
الأقسامَ الستّةَ الأولى «غيرَ معروفةِ الأثر» وهي قد تمّت وحُفظت مرشّحاتُها —
أو يجعلها تُعاد كلُّها فيُدفع ثمنُها مرّتين. فلكلِّ قسمٍ **جيلُ تنفيذٍ خاصٌّ
به**:

    محاولةُ المعالجة + القسم = جيلُ تنفيذٍ داخليٌّ واحد

ولا جدولَ جديدًا لذلك: `idempotency_records` (الترحيل 0037) تكفي، وتُستعمل
بأدواتها الدنيا مباشرةً — بلا اختلاقِ `Request` وهميّ لمجرّد استدعاء مُعِين.

## الفاعلُ التقنيُّ الثابت — وهذا هو الموضعُ الدقيق

`idempotency_records` محكومةٌ بـRLS على **المستأجرِ والفاعل** معًا:

    tenant_id = app_current_tenant() AND actor_user_id = app_current_actor()

والاستعادةُ قد يطلبها مستخدمٌ آخرُ مأذونٌ له اليوم. فلو نُسب جيلُ التنفيذ
إلى «من ضغط زرَّ الاستعادة» لصار لكلّ مستعيدٍ جيلٌ خاصٌّ به — فيُنادى المزوّدُ
مرّةً لكلِّ مستعيد، وهو بعينه ما يمنعه الطور B-4.

فيُنسَب إلى `File.uploaded_by`: عمودٌ **غيرُ فارغٍ** (فُحص في القاعدة) ودائمٌ
لا تغيّره استعادة.

**وهو فاعلٌ تقنيٌّ لا سلطةٌ**: ليس تفويضًا، ولا إثباتَ وصولٍ حاليّ، ولا
يُكتب في التدقيق بوصفه صاحبَ الطلب. تفويضُ الطالبِ الحاليِّ يُفحص في مساره،
والتدقيقُ يحمل فاعلَه الحقيقيَّ قيمةً صريحة. وهذا وحده سياقُ RLS لصفِّ
الجيل الداخليّ — ولا تُضعَّف السياسةُ ولا يُوسَّع مداها.

**والتحقّق**: من الجداول التي يمسّها هذا الخطّ، `idempotency_records` وحدها
محكومةٌ بالفاعل؛ وما عداها — الرسائلُ والتشغيلاتُ والمرشّحاتُ والمقاطعُ
والملفّاتُ والتدقيق — محكومةٌ بالمستأجر وحده. فضبطُ سياقِ الفاعلِ على
الرافعِ لا يغيّر ما يراه العاملُ من أيٍّ منها.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from ..idempotency import (
    ExternalUnknown,
    InProgress,
    Lease,
    Replay,
    acquire_lease,
    canonical_fingerprint,
    fail_leased,
    finalize_leased,
    mark_external_attempt,
)

#: اسمُ العمليّة الداخليّة — **ليس مسارَ HTTP**، ويُميَّز بذلك صراحةً.
#: فالجيلُ الداخليُّ لا يخصّ طلبًا بعينه، بل محاولةَ معالجةٍ تعيش بعده.
OPERATION: Final = "INTERNAL thesis.document.section"

#: فضاءُ أسماءِ مفتاحِ القسم — ثابتٌ، فالمفتاحُ يُشتقّ ولا يُخزَّن خامًّا.
SECTION_NAMESPACE: Final = uuid.UUID("b7a41f09-6c53-5d82-9e14-7f3a8c26d5b1")


@dataclass(frozen=True, slots=True)
class SectionGate:
    """قرارُ البوّابةِ لقسمٍ واحد — وما يجوز فعلُه بعده.

    `lease` غيرُ `None` تعني: امضِ، وأنت المالك.
    """

    #: `granted` | `completed` | `unknown` | `in_progress` | `conflict`
    outcome: str
    lease: Lease | None = None

    @property
    def may_call_provider(self) -> bool:
        return self.outcome == "granted"


def section_key(run_id: uuid.UUID, section: str) -> str:
    """مفتاحُ جيلِ القسم — مشتقٌّ من التشغيلةِ الثابتةِ واسمِ القسم.

    والتشغيلةُ ثابتةٌ لكلّ محاولة (`run_id_for`)، فالمفتاحُ ثابتٌ عبر
    الاستئناف ويختلف مع كلّ محاولةٍ جديدةٍ مقصودة.

    **ولا يُخزَّن هذا المفتاحُ خامًّا**: `acquire_lease` تخزّن تجزئتَه وحدها،
    كما هو عقدُ الترحيل 0037 لكلّ مفتاح.
    """
    return uuid.uuid5(SECTION_NAMESPACE, f"{run_id}:{section}").hex


def section_fingerprint(
    *,
    run_id: uuid.UUID,
    section: str,
    checksum_sha256: str | None,
    prompt: str,
    chunks: tuple[tuple[str, str], ...],
    field_keys: tuple[str, ...],
    locale: str,
    provider: str,
    model: str | None,
    capability: str | None,
) -> str:
    """بصمةُ المعنى العلميِّ لقسمٍ واحد — **ولا نصَّ مستندٍ فيها**.

    ما يدخلها: هُويّةُ التشغيلة، والقسم، وبصمةُ الملفّ، وتجزئةُ المطالبة،
    وهُويّاتُ المقاطعِ المختارةِ وتجزئةُ نصوصِها، والحقولُ المطلوبة، واللغة،
    والمزوّدُ والنموذجُ — فهما يغيّران المخرَجَ فعلًا — وقدرةُ الإذن.

    وما لا يدخلها ولا يُحفَظ في أيّ حال: **متنُ المستند، ونصُّ المطالبة،
    والمقاطعُ، والاقتباسات**. تجزئاتٌ ومعرّفاتٌ فقط.
    """
    body: dict[str, Any] = {
        "run_id": str(run_id),
        "section": section,
        "checksum_sha256": checksum_sha256,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "chunks": [{"id": cid, "sha256": sha} for cid, sha in chunks],
        "field_keys": list(field_keys),
        "locale": locale,
        "provider": provider,
        "model": model,
        "capability": capability,
    }
    return canonical_fingerprint(method="INTERNAL", operation=OPERATION, body=body)


def chunk_identities(chunks) -> tuple[tuple[str, str], ...]:
    """هُويّةُ كلِّ مقطعٍ وتجزئةُ نصِّه — **ولا نصَّ يخرج من هنا**."""
    return tuple(
        (str(chunk.chunk_id),
         hashlib.sha256((chunk.text or "").encode("utf-8")).hexdigest())
        for chunk in chunks
    )


async def open_section(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    subject_id: uuid.UUID,
    run_id: uuid.UUID,
    section: str,
    fingerprint: str,
) -> SectionGate:
    """يفتح جيلَ القسم — أو يقول لماذا لا يجوز النداء.

    والقراراتُ أربعة، وكلُّها من الطور B-4 حرفيًّا:

    ‏• **`granted`** — الجيلُ لنا: يجوز نداءُ المزوّدِ مرّةً واحدة.
    ‏• **`completed`** — القسمُ تمّ وأُودعت مرشّحاتُه: لا نداءَ ولا إدراجَ ثانٍ.
    ‏• **`unknown`** — عُبِر الحدُّ ولم يُعرف الأثر: **لا نداءَ ثانيًا** تحت
      الجيل نفسِه. ومحاولةٌ جديدةٌ مقصودةٌ هي البابُ الوحيد.
    ‏• **`in_progress`** — عاملٌ آخرُ يحمل الجيلَ وإجارتُه حيّة.
    ‏• **`conflict`** — المفتاحُ نفسُه بمعنًى علميٍّ آخر: لا يُنادى المزوّد.
    """
    # **والصِّدامُ قرارٌ لا انفجار.** `acquire_lease` ترفع `KeyReused` حين
    # يأتي المفتاحُ نفسُه بمعنًى آخر — وهو هنا حالٌ متوقّعةٌ تُعالَج: قسمٌ
    # بلغه مُدخلٌ علميٌّ غيرُ الذي بُدئ عليه. فيُردّ بلا نداءِ مزوّد، ولا
    # يُترك يخرج استثناءً فيسقط في مسارِ إخفاقٍ لا إجارةَ له فيُعطب.
    from ..idempotency import KeyReused  # noqa: PLC0415

    try:
        outcome = await acquire_lease(
            session, tenant_id=tenant_id, actor_user_id=subject_id,
            operation=OPERATION, key=section_key(run_id, section),
            fingerprint=fingerprint)
    except KeyReused:
        return SectionGate("conflict")
    if isinstance(outcome, Lease):
        return SectionGate("granted", outcome)
    if isinstance(outcome, Replay):
        return SectionGate("completed")
    if isinstance(outcome, ExternalUnknown):
        return SectionGate("unknown")
    if isinstance(outcome, InProgress):
        return SectionGate("in_progress")
    return SectionGate("conflict")


async def mark_section_external(
    session: AsyncSession, lease: Lease, *, provider: str, capability: str,
) -> None:
    """يُدوّن عبورَ حدِّ المزوّدِ لهذا القسم — **في معاملةٍ تُودَع قبل النداء**."""
    from ..idempotency import LeaseSuperseded  # noqa: PLC0415

    if await mark_external_attempt(session, lease, provider=provider,
                                   capability=capability) is not None:
        raise LeaseSuperseded


async def settle_section(
    session: AsyncSession, lease: Lease, *, accepted: int, rejected: int,
) -> None:
    """يُثبّت تمامَ القسم — **في معاملةِ حفظِ مرشّحاتِه نفسِها**.

    وهذا شرطُ الصحّة كلِّه: «تمّ» تُودَع مع الأثر أو لا تُودَع. فلو سبقت
    الأثرَ لرأى الاستئنافُ قسمًا «تامًّا» بلا مرشّحاتٍ — فيتخطّاه، ويضيع
    عملُه بلا أن يدري أحد.

    **ولا يُخزَّن مخرَجُ المزوّدِ الخام** في صفِّ الجيل: عددان يكفيان،
    والأثرُ الحقيقيُّ في `fact_candidates`.
    """
    from ..idempotency import LeaseSuperseded  # noqa: PLC0415

    if await finalize_leased(session, lease, status=200,
                             body={"accepted": accepted,
                                   "rejected": rejected}) is not None:
        raise LeaseSuperseded


async def fail_section_pre_external(
    session: AsyncSession, lease: Lease, *, reason: str,
) -> None:
    """إخفاقٌ **قبل** الحدّ: معلومٌ، فيبقى القسمُ قابلًا لإعادةٍ صادقة.

    سياسةٌ أو تصنيفٌ أو عقدٌ محلّيٌّ — كلُّها قبل أيّ نداء. ولا وسمَ عبورٍ
    يُكتب، فاستئنافُ المحاولةِ نفسِها يجوز له أن ينادي المزوّدَ مرّةً.
    """
    await fail_leased(session, lease, reason=reason[:200])
