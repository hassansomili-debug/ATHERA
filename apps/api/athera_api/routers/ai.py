"""أثيرا AI | The researcher-facing AI entry point (§32، §4، §8).

مسار واحد يخاطبه الباحث. لا اسم أجنت ولا أداة ولا مزوّد يظهر له — «أثيرا
AI» هي الهوية، والتتبّع الداخلي يبقى في `traces` لمن يريده.

وثلاثة حدود مفروضة هنا لا موصوفة:
1. **الجهوزية تُقرأ لا تُفترض**: مزوّد بلا مفتاح يردّ `disabled` ولا يحاول.
2. **الملف يُذكر ولا يُقرأ**: مرحلة معالجة المستندات لم تبدأ، فلا يُرسل
   بايت واحد من محتواه إلى المزوّد.
3. **محتوى المستخدم بيانات**: يدخل في دور `user` وحده، ولا مسار يضعه في
   دور `system` — فلا يستطيع نصّ أن ينقض سياسة النزاهة.
"""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.files import File
from ..brain.orchestrator import Orchestrator
from ..providers.gateway import provider_readiness
from ..schemas.ai import AiAskRequest, AiAskResponse
from ..services import ai_policy, ai_rate_limit, audit

# الأجنت الذي ينفّذ نيّة S5B النصّية. الاسم داخلي ولا يظهر للباحث.
S5B_AGENT = "research_manager"

router = APIRouter(prefix="/api/v1/ai", tags=["athera-ai"])


def _t(locale: str, ar: str, en: str) -> str:
    return en if locale == "en" else ar


@router.post("/ask", response_model=AiAskResponse)
async def ask(
    payload: AiAskRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> AiAskResponse:
    locale = principal.locale
    ai_rate_limit.check(principal.tenant_id, principal.user_id)

    provider, ready, reason = provider_readiness()
    literature_online = os.getenv("LITERATURE_REGISTRY", "offline") != "offline"

    limitations: list[str] = []
    capabilities: list[str] = []

    # ── الملف: يُذكر ولا يُقرأ ──
    if payload.attachment_file_id is not None:
        record = (
            await session.execute(select(File).where(File.id == payload.attachment_file_id))
        ).scalar_one_or_none()
        if record is None:
            raise NotFound("file.not_found")
        # RLS تمنع أصلًا رؤية ملف مستأجر آخر؛ والتحقق هنا يجعل الرفض صريحًا.
        limitations.append(_t(
            locale,
            "تم حفظ الملف، لكن معالجة محتواه ستُفعّل في مرحلة معالجة المستندات.",
            "The file is stored, but processing its content will be enabled in the document-processing stage.",
        ))

    if not literature_online:
        limitations.append(_t(
            locale,
            "البحث الخارجي في الأدبيات غير مفعّل حاليًا، فلا مصادر مسترجَعة في هذا الرد.",
            "External literature search is not enabled, so this answer contains no retrieved sources.",
        ))

    # ── الجهوزية تُقرأ لا تُفترض ──
    if not ready:
        return AiAskResponse(
            answer=_t(
                locale,
                "تنفيذ أثيرا AI غير مُفعَّل بعد: لم يُضبط مزوّد نموذج على الخادم. "
                "وما يعمل اليوم بلا نموذج: الاستخراج الحتمي، وفحوص الاتساق، ومطابقة المجلات.",
                "ATHERA AI execution is not activated yet: no model provider is configured on the server. "
                "What works today without a model: deterministic extraction, consistency checks, and journal matching.",
            ),
            status="disabled",
            evidence_state="none",
            limitations=limitations + [_t(locale, f"سبب التعطيل: {reason}", f"Reason: {reason}")],
            recommended_next_actions=[_t(
                locale, "اضبط مزوّد النموذج ومفتاحه في أسرار الخادم.",
                "Configure the model provider and its key in the server secrets.",
            )],
        )

    # ── الاستدعاء عبر المنسّق: هو الطبقة المعمارية، والبوابة تحته ──
    #
    # **بلا أدوات في هذه المرحلة.** والقرار ليس تبسيطًا: أداة الذاكرة تصنيفها
    # C2، وسقف الإرسال الخارجي C1. فاستدعاؤها هنا كان يعني إمّا رفع السقف —
    # وهو إضعاف عام مرفوض — أو إرسال محتوى بحثي حسّاس. وS5B نصّي فقط: لا
    # ذاكرة موثقة، ولا ملفات، ولا بحث خارجي، ولا سياق مستأجر آخر.
    #
    # ونداء نموذج **واحد**: الموجّه لا يمسّ البوابة، والمنسّق وحده يستدعيها.
    notice = ai_policy.capability_notice(locale, literature_online=literature_online)
    policy = ai_policy.system_prompt(locale)
    if notice:
        policy = f"{policy}\n\n{notice}"

    try:
        result = await Orchestrator().run_agent(
            session,
            tenant_id=principal.tenant_id,
            actor_user_id=principal.user_id,
            agent_key=S5B_AGENT,
            question=payload.question,
            tool_calls=[],
            input_classification="C1",
            extra_system=policy,
            output_locale=locale,
        )
    except AtheraError:
        raise
    except Exception as exc:  # noqa: BLE001 — يُترجم لا يُسرَّب
        await audit.record(
            session, tenant_id=principal.tenant_id, action="ai.provider_failed",
            object_type="ai_request", object_id=uuid.uuid4(),
            actor_user_id=principal.user_id,
            state_after={"provider": provider, "error_type": type(exc).__name__},
            request_id=principal.request_id,
        )
        return AiAskResponse(
            answer=_t(
                locale,
                "تعذّر الوصول إلى مزوّد النموذج الآن. لم يُولَّد أي محتوى، ولم يُحفظ شيء.",
                "The model provider could not be reached. No content was generated and nothing was saved.",
            ),
            status="provider_error",
            evidence_state="none",
            limitations=limitations,
            recommended_next_actions=[_t(locale, "أعد المحاولة بعد قليل.", "Try again shortly.")],
        )

    answer = result.answer
    if answer is None:
        return AiAskResponse(
            answer=_t(locale, "لم تُنتَج إجابة.", "No answer was produced."),
            status="provider_error", evidence_state="none", limitations=limitations,
        )

    capabilities.append("model_reasoning")

    # ما لم يجد النموذج له سندًا يُعلَن حدًّا لا يُبتلع في النصّ.
    limitations.extend(answer.unsupported_claims)
    limitations.extend(answer.evidence_gaps)

    return AiAskResponse(
        answer=(answer.answer_en or answer.answer_ar) if locale == "en" else answer.answer_ar,
        status="ok",
        # بلا أدوات فلا استشهاد مسنود: اقتراح نموذج، لا دليل (§7.4).
        evidence_state="verified" if answer.citations else "model_suggestion",
        capabilities_used=capabilities,
        limitations=limitations,
        recommended_next_actions=[
            _t(locale, "راجع الاقتراح واعتمد ما تريد إدخاله في مشروعك.",
               "Review the proposal and approve what you want to enter into your project."),
        ],
        model_run_id=result.model_run_id,
    )
