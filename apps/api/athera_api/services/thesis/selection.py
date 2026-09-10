"""اختيارُ الباحث لفرصةٍ | The researcher's opportunity selection (§18، §16).

**قرارٌ واحد، وموضعٌ واحد يكتبه.**

كان اختيارُ الفرصة يُكتب في `routers/planning.py` وحده، وذلك الموجّه يقرأ
الفرصةَ بشرط `PublicationOpportunity.project_id == project_id`. وفرصةُ
الرسالة — وهي ما تُنتجه T1 تلقائيًّا — لا مشروعَ لها بعدُ: `project_id`
فيها `NULL` حتى تُحوَّل. **فلم يكن للباحث سبيلٌ إلى اختيارها أصلًا**،
والرحلةُ تقف عند «اختر الفرصة» وتطلب فعلًا لا نقطةَ نهايةٍ تؤدّيه.

والعلاجُ ليس نسخةً ثانية من الكتابة في موجّه الرسائل: نسختان تفترقان بأوّل
تعديل — تُسجّل إحداهما في سلسلة التدقيق ما لا تُسجّله الأخرى، أو تُحدّث
واحدةٌ عمودًا وتنساه الثانية. فالكتابةُ هنا، ويناديها الموجّهان.

## ولماذا `planning_status` وحده

العمودان مُفرَدان عمدًا (`models/thesis.py`): `status` دورةُ إنتاج ورقة،
و`planning_status` قرارُ الباحث. ودمجُهما يجعل «مرفوضة» تحتمل معنيين —
ورقةٌ أُوقف إنتاجُها، وفرصةٌ لم يخترها الباحث. وهما حكمان يقولهما شخصان في
لحظتين. **فلا يمسّ هذا الملفُّ `status` بحال.**
"""
from __future__ import annotations

import datetime as dt
import uuid

from ...errors import AtheraError
from .. import audit

#: القراران اللذان يملكهما الباحث — ولا ثالثَ يُقبل صامتًا.
SELECT: str = "select"
EXCLUDE: str = "exclude"
DECISIONS: tuple[str, ...] = (SELECT, EXCLUDE)

#: ما يُكتب في العمود لكلِّ قرار.
_WRITES: dict[str, str] = {SELECT: "selected", EXCLUDE: "excluded"}

_ACTIONS: dict[str, str] = {
    SELECT: "planning.opportunity_selected",
    EXCLUDE: "planning.opportunity_excluded",
}


async def decide(
    session,
    *,
    tenant_id: uuid.UUID,
    opportunity,
    actor_user_id: uuid.UUID,
    decision: str,
    reason: str | None = None,
    request_id: str | None = None,
):
    """يكتب قرارَ الباحث في `planning_status` — **ولا يمسّ دورةَ الإنتاج**.

    ويُعيد الصفَّ نفسه بعد التعديل. والقرارُ **مُتكرِّرٌ آمن**: إعادةُ
    الاختيار تُعيد الكتابةَ نفسها ولا تُنشئ شيئًا.
    """
    if decision not in DECISIONS:
        raise AtheraError("planning.unknown_decision", status_code=422,
                          decision=decision, allowed=",".join(DECISIONS))

    before = opportunity.planning_status
    opportunity.planning_status = _WRITES[decision]
    opportunity.planning_decided_by = actor_user_id
    opportunity.planning_decided_at = dt.datetime.now(dt.UTC)

    await audit.record(
        session, tenant_id=tenant_id, action=_ACTIONS[decision],
        object_type="publication_opportunity", object_id=opportunity.id,
        actor_user_id=actor_user_id,
        state_before={"planning_status": before},
        # **ويُسجَّل صراحةً أنّ دورة النشر لم تُمسّ** — فالسلسلةُ تُقرأ
        # لاحقًا للإجابة عن «من قرّر ماذا»، والصمتُ هنا يُقرأ تغييرًا.
        state_after={"planning_status": opportunity.planning_status,
                     "publication_status_unchanged": opportunity.status},
        reason=(reason or "")[:1000] or "researcher planning decision",
        request_id=request_id,
    )
    return opportunity


__all__ = ["DECISIONS", "EXCLUDE", "SELECT", "decide"]
