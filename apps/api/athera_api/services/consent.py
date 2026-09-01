"""موافقة المعالجة الخارجية | Explicit per-document external-processing consent.

**السقف العام يبقى C1.** مادة بحثية غير منشورة لا تغادر الخادم افتراضًا،
ولا يُرفع السقف العام ليعمل S5C — لأن رفعه يأذن لكل مسار لا لمسار واحد.

وما هنا استثناءٌ **ضيّق ومسمّى ومحسوم بقرار إنسان**: قدرةٌ واحدة، على مستند
واحد، بموافقة صريحة من صاحبه. ولا تُستنتج الموافقة من رفعٍ ولا دخولٍ ولا
عضوية ولا استعمالٍ سابق للذكاء الاصطناعي في شيء آخر.

**وأين تُحفظ؟** في `approvals` — وهو الجدول القائم للبوابات: كائنٌ له فاعل
وتاريخ وسبب وحالة، مقيَّد بالمستأجر تحت RLS. ولا يحتاج ترحيلًا:

  gate        رمز البوابة `DIC2`
  object_type «ملف + القدرة» معًا، فالموافقة مقيَّدة بالاثنين لا بالملف وحده
  object_id   معرّف الملف
  status      approved (موافقة) · rejected (رفض أو سحب) · pending (لم تُطلب)

وسياق الموافقة الكامل — المزوّد والنموذج والقدرة ووقتها — في `audit_events`
المتسلسل بالتجزئة. ولا نصّ مستند في أيٍّ منهما.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.audit import Approval
from . import audit

# القدرة الوحيدة المأذون لها بتجاوز السقف العام — وباسمها لا بصفتها.
CAPABILITY: Final = "document_intelligence_external_c2"

# ما تأذن به هذه القدرة **بالضبط**. لا C3 ولا C4 مهما كانت الموافقة.
CAPABILITY_CEILING: Final[dict[str, str]] = {CAPABILITY: "C2"}

GATE: Final = "DIC2"
OBJECT_TYPE: Final = f"file.{CAPABILITY}"

GRANTED: Final = "granted"
DECLINED: Final = "declined"
ABSENT: Final = "absent"


@dataclass(frozen=True, slots=True)
class ExternalProcessingGrant:
    """إذنٌ لنداء واحد — يحمل قدرته ومستنده ومصدر قراره.

    **لا يُنشأ إلا هنا**، بعد قراءة صفّ موافقة محسوم بـ`approved`. ولا مسار
    آخر في المنظومة يبنيه، فلا يستطيع `/ai/ask` ولا أداة أخرى أن تدّعيه.
    """

    capability: str
    file_id: uuid.UUID
    approval_id: uuid.UUID
    max_classification: str


async def _row(session: AsyncSession, *, tenant_id: uuid.UUID,
               file_id: uuid.UUID) -> Approval | None:
    return (
        await session.execute(
            select(Approval).where(
                Approval.tenant_id == tenant_id,
                Approval.object_type == OBJECT_TYPE,
                Approval.object_id == file_id,
            ).order_by(Approval.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()


async def state(session: AsyncSession, *, tenant_id: uuid.UUID,
                file_id: uuid.UUID) -> str:
    """`granted` أو `declined` أو `absent` — ولا رابع."""
    row = await _row(session, tenant_id=tenant_id, file_id=file_id)
    if row is None:
        return ABSENT
    return GRANTED if row.status == "approved" else DECLINED


async def authorization_for(
    session: AsyncSession, *, tenant_id: uuid.UUID, file_id: uuid.UUID,
) -> ExternalProcessingGrant | None:
    """الإذن لهذا المستند وحده — أو `None`.

    وموافقةٌ على مستند لا تصلح لغيره: الاستعلام مقيَّد بـ`object_id`، فلا
    يرث ملفٌ إذن ملف آخر ولو كانا لنفس الباحث.
    """
    row = await _row(session, tenant_id=tenant_id, file_id=file_id)
    if row is None or row.status != "approved":
        return None
    return ExternalProcessingGrant(
        capability=CAPABILITY, file_id=file_id, approval_id=row.id,
        max_classification=CAPABILITY_CEILING[CAPABILITY],
    )


async def record_decision(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    file_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    granted: bool,
    provider: str,
    model: str | None,
    revocation: bool = False,
    request_id: str | None = None,
) -> Approval:
    """يسجّل قرار الباحث — موافقةً أو رفضًا أو سحبًا.

    والمزوّد والنموذج يُحفظان **كما كانا لحظة القرار**: موافقةٌ أُعطيت
    لمزوّد ما ليست موافقة مفتوحة لأي مزوّد يُضبط لاحقًا، والسجل يبقى قادرًا
    على قول ذلك.
    """
    now = dt.datetime.now(dt.UTC)
    row = await _row(session, tenant_id=tenant_id, file_id=file_id)
    before = row.status if row is not None else None

    if row is None:
        row = Approval(
            tenant_id=tenant_id, gate=GATE, object_type=OBJECT_TYPE, object_id=file_id,
            requested_by=actor_user_id,
        )
        session.add(row)

    row.status = "approved" if granted else "rejected"
    row.decided_by = actor_user_id
    row.decided_at = now
    # سببٌ وصفيّ لا محتوى: لا سطر من المستند يدخل سجل الموافقة.
    row.reason = (
        "consent revoked by researcher" if revocation
        else ("researcher authorized external AI processing for this document"
              if granted else "researcher declined external AI processing")
    )
    await session.flush()

    await audit.record(
        session, tenant_id=tenant_id,
        action="consent.external_processing_revoked" if revocation
        else ("consent.external_processing_granted" if granted
              else "consent.external_processing_declined"),
        object_type="file", object_id=file_id, actor_user_id=actor_user_id,
        approval_id=row.id,
        state_before={"status": before},
        state_after={
            "status": row.status,
            "capability": CAPABILITY,
            "max_classification": CAPABILITY_CEILING[CAPABILITY],
            # المزوّد والنموذج لحظة القرار — لا محتوى ولا مفاتيح.
            "provider": provider,
            "model": model,
        },
        reason=row.reason,
        request_id=request_id,
    )
    return row
