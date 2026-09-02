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
from ..providers.gateway import capability_ceiling
from . import audit

# القدرات المأذون لها بتجاوز السقف العام — كلٌّ باسمها لا بصفتها.
#
# **وقدرةٌ لا تأذن لأختها.** موافقة قراءة المستند (S5C) لا تصلح لتخطيط النشر
# (S5D): الأولى تُرسل مقاطع رسالة لاستخراج بياناتها، والثانية تُرسل حقائق
# موثقة لبناء مقترحات. غرضان مختلفان يقرّهما الباحث مرتين.
# **وتخطيطُ النشر لا يأذن بكتابة الورقة (S5E).** الثانية أذنت بإرسال حقائق
# لبناء **مقترحات** يقرؤها الباحث ويختار منها؛ والثالثة تأذن بإرسالها لصياغة
# **نصّ ورقة** يحمل اسمه. ثلاثة أغراض يقرّها الباحث ثلاث مرات.
CAPABILITY: Final = "document_intelligence_external_c2"
PLANNING_CAPABILITY: Final = "publication_planning_external_c2"
DRAFTING_CAPABILITY: Final = "manuscript_drafting_external_c2"
# **والمحادثة لا تلتفّ على شيء من ذلك.** سؤالٌ عن مستند يُرسل معرفةً اعتمدها
# الباحث — وهي C2. فلولا قدرةٌ رابعة لصارت المحادثة بابًا خلفيًّا: سؤالٌ
# بريء الشكل يُخرج ما يمنع الإذنُ إخراجَه.
CHAT_CAPABILITY: Final = "document_chat_external_c2"

# ما تأذن به كل قدرة **بالضبط** — **مشتقًّا من سجل البوابة لا مكتوبًا بجانبه**.
#
# كانت هذه الخريطة نسخةً ثانية للحقيقة نفسها، فأُضيفت قدرة الصياغة هنا ولم
# تُضف هناك: فصار الإذن صحيحًا والبوابة ترفض `C2` — والرسالة تقول
# «disabled_for_classification» بينما الباحث أذن فعلًا. وهو صنف العطب الذي
# كلّف S5D ثلاثة عوائق: معرّفٌ يُكتب بجانب سجلّه بدل أن يُشتقّ منه.
#
# والسلطة عند البوابة عمدًا: هي حدّ المغادرة إلى الخارج، وإضافة اسم فيها
# قرار سياسة يُرى في المراجعة. وهذه تقرأ منها ولا تعيد كتابتها.
CAPABILITY_CEILING: Final[dict[str, str]] = {
    name: ceiling
    for name, ceiling in (
        (CAPABILITY, capability_ceiling(CAPABILITY)),
        (PLANNING_CAPABILITY, capability_ceiling(PLANNING_CAPABILITY)),
        (DRAFTING_CAPABILITY, capability_ceiling(DRAFTING_CAPABILITY)),
        (CHAT_CAPABILITY, capability_ceiling(CHAT_CAPABILITY)),
    )
    if ceiling is not None
}

GATE: Final = "DIC2"
PLANNING_GATE: Final = "PPC2"
DRAFTING_GATE: Final = "MDC2"
CHAT_GATE: Final = "DCC2"
OBJECT_TYPE: Final = f"file.{CAPABILITY}"
PLANNING_OBJECT_TYPE: Final = f"project.{PLANNING_CAPABILITY}"
# **على المخطوطة لا على المشروع**: الإذن يُعطى لصياغة ورقة بعينها، ومشروعٌ
# قد يحمل أكثر من مخطوطة لأكثر من فرصة.
DRAFTING_OBJECT_TYPE: Final = f"manuscript.{DRAFTING_CAPABILITY}"
# على الملف: الإذن يُعطى للسؤال عن مستندٍ بعينه.
CHAT_OBJECT_TYPE: Final = f"file.{CHAT_CAPABILITY}"

GRANTED: Final = "granted"
# أُذن ثم تغيّرت الأدلة — ليست رفضًا، وليست إذنًا للقطة الجديدة.
STALE: Final = "stale"
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
    # بصمة اللقطة التي أُذن لها — `None` لقدرات لا تعمل على لقطة (S5C).
    context_fingerprint: str | None = None


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


# ─────────────────── تخطيط النشر: موافقة مربوطة بلقطة ───────────────────


async def _planning_row(session: AsyncSession, *, tenant_id: uuid.UUID,
                        project_id: uuid.UUID) -> Approval | None:
    return (
        await session.execute(
            select(Approval).where(
                Approval.tenant_id == tenant_id,
                Approval.object_type == PLANNING_OBJECT_TYPE,
                Approval.object_id == project_id,
            ).order_by(Approval.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()


async def planning_state(session: AsyncSession, *, tenant_id: uuid.UUID,
                         project_id: uuid.UUID,
                         context_fingerprint: str | None = None) -> str:
    """`granted` أو `declined` أو `stale` أو `absent`.

    و`stale` حالةٌ رابعة يحتاجها التخطيط وحده: أُذن، ثم تغيّرت الأدلة. وليست
    رفضًا — الباحث لم يرجع عن شيء — لكنها ليست إذنًا للقطة الجديدة.
    """
    row = await _planning_row(session, tenant_id=tenant_id, project_id=project_id)
    if row is None:
        return ABSENT
    if row.status != "approved":
        return DECLINED
    if context_fingerprint and row.context_fingerprint != context_fingerprint:
        return STALE
    return GRANTED


async def planning_authorization(
    session: AsyncSession, *, tenant_id: uuid.UUID, project_id: uuid.UUID,
    context_fingerprint: str,
) -> ExternalProcessingGrant | None:
    """إذن التخطيط — **ولا يُمنح للقطة غير التي أُذن لها**.

    فبصمةٌ مختلفة تعني أدلةً تغيّرت: أُضيفت ذاكرة موثقة، أو تبدّل نصّها.
    وإرسالها تحت إذنٍ سابق إرسالٌ لما لم يره صاحب القرار.
    """
    row = await _planning_row(session, tenant_id=tenant_id, project_id=project_id)
    if row is None or row.status != "approved":
        return None
    if row.context_fingerprint != context_fingerprint:
        return None
    return ExternalProcessingGrant(
        capability=PLANNING_CAPABILITY, file_id=project_id, approval_id=row.id,
        max_classification=CAPABILITY_CEILING[PLANNING_CAPABILITY],
        context_fingerprint=context_fingerprint,
    )


async def record_planning_decision(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    granted: bool,
    provider: str,
    model: str | None,
    context_fingerprint: str,
    evidence_count: int,
    revocation: bool = False,
    request_id: str | None = None,
) -> Approval:
    """يسجّل قرار الباحث في إرسال أدلته الموثقة لبناء فرص نشر.

    والبصمة تُحفظ مع القرار، فيُعرف لاحقًا **على أي أدلة** أُذن.
    """
    now = dt.datetime.now(dt.UTC)
    row = await _planning_row(session, tenant_id=tenant_id, project_id=project_id)
    before = row.status if row is not None else None

    if row is None:
        row = Approval(
            tenant_id=tenant_id, gate=PLANNING_GATE, object_type=PLANNING_OBJECT_TYPE,
            object_id=project_id, requested_by=actor_user_id,
        )
        session.add(row)

    row.status = "approved" if granted else "rejected"
    row.decided_by = actor_user_id
    row.decided_at = now
    row.context_fingerprint = context_fingerprint if granted else None
    row.reason = (
        "planning consent revoked by researcher" if revocation
        else ("researcher authorized external AI publication planning for this project"
              if granted else "researcher declined external AI publication planning")
    )
    await session.flush()

    await audit.record(
        session, tenant_id=tenant_id,
        action="consent.publication_planning_revoked" if revocation
        else ("consent.publication_planning_granted" if granted
              else "consent.publication_planning_declined"),
        object_type="research_project", object_id=project_id,
        actor_user_id=actor_user_id, approval_id=row.id,
        state_before={"status": before},
        state_after={
            "status": row.status,
            "capability": PLANNING_CAPABILITY,
            "max_classification": CAPABILITY_CEILING[PLANNING_CAPABILITY],
            "provider": provider,
            "model": model,
            # بصمةٌ وعدد — لا نصّ دليل واحد.
            "context_fingerprint": context_fingerprint,
            "evidence_count": evidence_count,
        },
        reason=row.reason,
        request_id=request_id,
    )
    return row


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


# ══════════ S5E — إذن صياغة المخطوطة (MDC2) ══════════
#
# **وصفٌ لا تكرار:** الصفّ واحد لكل (مخطوطة، بصمة) لا لكل مخطوطة. فقسمان من
# مخطوطة واحدة لهما سياقان مختلفان وبصمتان مختلفتان — وإذنٌ يُعطى لصياغة
# المنهجية لا يصلح لصياغة النتائج، ولا يجوز أن يمحوه.


async def _drafting_row(session: AsyncSession, *, tenant_id: uuid.UUID,
                        manuscript_id: uuid.UUID,
                        context_fingerprint: str | None = None) -> Approval | None:
    query = select(Approval).where(
        Approval.tenant_id == tenant_id,
        Approval.object_type == DRAFTING_OBJECT_TYPE,
        Approval.object_id == manuscript_id,
    )
    if context_fingerprint is not None:
        query = query.where(Approval.context_fingerprint == context_fingerprint)
    return (
        await session.execute(query.order_by(Approval.created_at.desc()).limit(1))
    ).scalar_one_or_none()


async def drafting_state(session: AsyncSession, *, tenant_id: uuid.UUID,
                         manuscript_id: uuid.UUID, context_fingerprint: str) -> str:
    """`granted` أو `declined` أو `stale` أو `absent` — لهذا السياق بعينه."""
    exact = await _drafting_row(session, tenant_id=tenant_id, manuscript_id=manuscript_id,
                                context_fingerprint=context_fingerprint)
    if exact is not None and exact.status == "approved":
        return GRANTED

    latest = await _drafting_row(session, tenant_id=tenant_id, manuscript_id=manuscript_id)
    if latest is None:
        return ABSENT
    if latest.status == "rejected":
        return DECLINED
    # أُذن لسياق آخر — أدلةٌ تغيّرت أو قسمٌ آخر. ليس رفضًا، وليس إذنًا لهذا.
    return STALE if latest.status == "approved" else ABSENT


async def drafting_authorization(
    session: AsyncSession, *, tenant_id: uuid.UUID, manuscript_id: uuid.UUID,
    context_fingerprint: str,
) -> ExternalProcessingGrant | None:
    """إذنٌ لنداء صياغة واحد — بمطابقة بصمة تامة لا تقريبية."""
    row = await _drafting_row(session, tenant_id=tenant_id, manuscript_id=manuscript_id,
                              context_fingerprint=context_fingerprint)
    if row is None or row.status != "approved":
        return None
    if row.context_fingerprint != context_fingerprint:
        return None
    return ExternalProcessingGrant(
        capability=DRAFTING_CAPABILITY, file_id=manuscript_id, approval_id=row.id,
        max_classification=CAPABILITY_CEILING[DRAFTING_CAPABILITY],
        context_fingerprint=context_fingerprint,
    )


async def record_drafting_decision(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    manuscript_id: uuid.UUID,
    section_key: str,
    actor_user_id: uuid.UUID,
    granted: bool,
    provider: str,
    model: str | None,
    context_fingerprint: str,
    evidence_count: int,
    revocation: bool = False,
    request_id: str | None = None,
) -> Approval:
    """يسجّل قرار الباحث في إرسال أدلة قسمٍ لصياغته."""
    now = dt.datetime.now(dt.UTC)
    row = await _drafting_row(session, tenant_id=tenant_id, manuscript_id=manuscript_id,
                              context_fingerprint=context_fingerprint)
    before = row.status if row is not None else None

    if row is None:
        row = Approval(
            tenant_id=tenant_id, gate=DRAFTING_GATE, object_type=DRAFTING_OBJECT_TYPE,
            object_id=manuscript_id, requested_by=actor_user_id,
        )
        session.add(row)

    row.status = "approved" if granted else "rejected"
    row.decided_by = actor_user_id
    row.decided_at = now
    row.context_fingerprint = context_fingerprint if granted else None
    row.reason = (
        "drafting consent revoked by researcher" if revocation
        else (f"researcher authorized external AI drafting of section {section_key}"
              if granted else "researcher declined external AI manuscript drafting")
    )
    await session.flush()

    await audit.record(
        session, tenant_id=tenant_id,
        action="consent.manuscript_drafting_revoked" if revocation
        else ("consent.manuscript_drafting_granted" if granted
              else "consent.manuscript_drafting_declined"),
        object_type="manuscript", object_id=manuscript_id,
        actor_user_id=actor_user_id, approval_id=row.id,
        state_before={"status": before},
        state_after={
            "status": row.status,
            "capability": DRAFTING_CAPABILITY,
            "max_classification": CAPABILITY_CEILING[DRAFTING_CAPABILITY],
            "provider": provider, "model": model,
            "section_key": section_key,
            # بصمةٌ وعدد — لا نصّ دليل واحد ولا سطر من المسودة.
            "context_fingerprint": context_fingerprint,
            "evidence_count": evidence_count,
        },
        reason=row.reason, request_id=request_id,
    )
    return row


# ══════════ سؤال أثيرا عن مستند مختار (DCC2) ══════════


async def _chat_row(session: AsyncSession, *, tenant_id: uuid.UUID,
                    file_id: uuid.UUID) -> Approval | None:
    return (
        await session.execute(
            select(Approval).where(
                Approval.tenant_id == tenant_id,
                Approval.object_type == CHAT_OBJECT_TYPE,
                Approval.object_id == file_id,
            ).order_by(Approval.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()


async def chat_state(session: AsyncSession, *, tenant_id: uuid.UUID,
                     file_id: uuid.UUID) -> str:
    """`granted` أو `declined` أو `absent` — لهذا الملف بعينه.

    **ولا بصمة هنا.** الإذن يُعطى للسؤال عن مستند، وما يُرسل معرفةٌ اعتمدها
    الباحث بنفسه واحدةً واحدة؛ فاعتمادُه لها هو التغيّر ذو المعنى، وربطُ
    الإذن ببصمةٍ تتغيّر كلما اعتمد حقلًا يجعله يُبطَل عند كل موافقة.
    """
    row = await _chat_row(session, tenant_id=tenant_id, file_id=file_id)
    if row is None:
        return ABSENT
    return GRANTED if row.status == "approved" else DECLINED


async def chat_authorization(session: AsyncSession, *, tenant_id: uuid.UUID,
                             file_id: uuid.UUID) -> ExternalProcessingGrant | None:
    row = await _chat_row(session, tenant_id=tenant_id, file_id=file_id)
    if row is None or row.status != "approved":
        return None
    return ExternalProcessingGrant(
        capability=CHAT_CAPABILITY, file_id=file_id, approval_id=row.id,
        max_classification=CAPABILITY_CEILING[CHAT_CAPABILITY],
        context_fingerprint=None,
    )


async def record_chat_decision(
    session: AsyncSession, *, tenant_id: uuid.UUID, file_id: uuid.UUID,
    actor_user_id: uuid.UUID, granted: bool, provider: str, model: str | None,
    fact_count: int, request_id: str | None = None,
) -> Approval:
    now = dt.datetime.now(dt.UTC)
    row = await _chat_row(session, tenant_id=tenant_id, file_id=file_id)
    before = row.status if row is not None else None
    if row is None:
        row = Approval(tenant_id=tenant_id, gate=CHAT_GATE,
                       object_type=CHAT_OBJECT_TYPE, object_id=file_id,
                       requested_by=actor_user_id)
        session.add(row)
    row.status = "approved" if granted else "rejected"
    row.decided_by = actor_user_id
    row.decided_at = now
    row.reason = ("researcher authorized answering questions from this document's "
                  "approved facts" if granted
                  else "researcher declined external answering from this document")
    await session.flush()

    await audit.record(
        session, tenant_id=tenant_id,
        action="consent.document_chat_granted" if granted
        else "consent.document_chat_declined",
        object_type="file", object_id=file_id, actor_user_id=actor_user_id,
        approval_id=row.id, state_before={"status": before},
        state_after={"status": row.status, "capability": CHAT_CAPABILITY,
                     "max_classification": CAPABILITY_CEILING[CHAT_CAPABILITY],
                     "provider": provider, "model": model,
                     # عددٌ لا نصّ: كم معلومة معتمَدة قد تُرسل.
                     "approved_fact_count": fact_count},
        reason=row.reason, request_id=request_id,
    )
    return row
