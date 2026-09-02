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

import json
import os
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.files import File
from ..models.research import FactCandidate, ResearcherMemory
from ..brain.contracts import strip_markup
from ..brain.orchestrator import Orchestrator
from ..providers.gateway import provider_readiness
from ..schemas.ai import AiAskRequest, AiAskResponse
from ..services import ai_policy, ai_rate_limit, audit, consent

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
    actions: list[str] = []

    # ── الملف المختار: يُقرأ من **معرفته المعتمَدة** لا من محتواه الخام ──
    #
    # **ولا تصير المحادثة بابًا خلفيًّا.** إرسال مقاطع المستند إلى مزوّد
    # خارجي محكومٌ بإذن C2 في مسار معالجة المستندات؛ فلو قرأت المحادثة
    # المقاطع مباشرةً لالتفّت على ذلك الإذن بسؤالٍ بريء الشكل.
    #
    # فالمحادثة تقرأ ما **اعتمده الباحث بنفسه**: الذاكرة الموثقة المشتقّة من
    # هذا الملف بعينه. وهي معرفته لا محتوى مستنده، وقد مرّت بمراجعته.
    document_context: list[dict] = []
    pending_fields: list[str] = []
    if payload.selected_file is not None:
        record = (
            await session.execute(select(File).where(
                File.id == payload.selected_file,
                File.tenant_id == principal.tenant_id))
        ).scalar_one_or_none()
        if record is None:
            raise NotFound("file.not_found")

        rows = (await session.execute(
            select(FactCandidate, ResearcherMemory)
            .outerjoin(ResearcherMemory,
                       ResearcherMemory.id == FactCandidate.resulting_memory_id)
            .where(FactCandidate.tenant_id == principal.tenant_id,
                   FactCandidate.file_id == record.id)
        )).all()

        for candidate, memory in rows:
            if candidate.status == "approved" and memory is not None \
                    and memory.verification_status == "verified":
                document_context.append({
                    "field": candidate.field_key,
                    "value": memory.statement_ar,
                    "locator": memory.source_locator,
                })
            elif candidate.status == "unverified":
                pending_fields.append(candidate.field_key)

        if not rows:
            # §10 — يُقال بصدق، ويُعطى الفعل التالي.
            limitations.append(_t(
                locale,
                "هذا الملف لم تُقرأ محتوياته بعد.",
                "This file has not been read yet.",
            ))
            # §10 — ويُعطى الفعل التالي، لا يُترك الباحث أمام «لا أستطيع».
            actions.append(_t(
                locale, "اطلب «معالجة المستند» من مكتبتك البحثية أولًا.",
                "Ask for “Process document” in your research library first.",
            ))
        elif not document_context:
            limitations.append(_t(
                locale,
                "قُرئ الملف ولم تعتمد بعد أيًّا من معلوماته، فلا أستطيع الإجابة منه.",
                "The file was read but you have not approved any of its facts yet, "
                "so I cannot answer from it.",
            ))
        else:
            capabilities.append(_t(
                locale,
                f"أجيب من {len(document_context)} معلومة اعتمدتَها من هذا الملف.",
                f"Answering from {len(document_context)} facts you approved from this file.",
            ))
        if pending_fields:
            limitations.append(_t(
                locale,
                f"و{len(set(pending_fields))} حقلًا مستخرَجًا ما زال بانتظار مراجعتك.",
                f"And {len(set(pending_fields))} extracted fields still await your review.",
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

    # **معرفة الملف المعتمَدة تُرسل بوصفها سياقًا، لا سؤالًا.**
    #
    # وتصنيفها C2: معرفة بحثية غير منشورة اعتمدها الباحث. فالسقف يُرفع
    # **لهذا النداء وحده** حين يوجد سياق مستند، ويبقى C1 فيما عداه — ولا
    # يُرفع السقف العام بحال.
    question = payload.question
    classification = "C1"
    grant = None
    if document_context:
        # §13 — **الإذن أولًا.** معرفةُ الباحث المعتمَدة تصنيفها C2، والسقف
        # العام C1. فلولا إذنٌ مسمّى لصارت المحادثة بابًا خلفيًّا: سؤالٌ
        # بريء الشكل يُخرج ما يمنع الإذنُ إخراجَه.
        grant = await consent.chat_authorization(
            session, tenant_id=principal.tenant_id, file_id=payload.selected_file)
        if grant is None:
            document_context = []
            limitations.append(_t(
                locale,
                "الإجابة من هذا المستند تحتاج إذنك الصريح — يُرسَل ما اعتمدتَه "
                "منه وحده، لا نصّه.",
                "Answering from this document needs your explicit consent — only "
                "the facts you approved would be sent, not its text.",
            ))
            actions.append(_t(
                locale, "امنح الإذن من صفحة المستند لتُجيب أثيرا منه.",
                "Grant consent on the document page so ATHERA can answer from it.",
            ))

    if document_context:
        classification = "C2"
        facts = json.dumps(document_context, ensure_ascii=False)
        question = (
            f"{payload.question}\n\n"
            "أجب من هذه المعلومات المعتمَدة من مستند الباحث وحدها:\n"
            f"{facts}\n\n"
            "وما لا تجده فيها قل إنه غير موجود في المستند — ولا تُكمله من "
            "معرفتك. وميّز صراحةً بين ما ورد في المعلومات وبين أي اقتراح منك."
        )

    try:
        result = await Orchestrator().run_agent(
            session,
            tenant_id=principal.tenant_id,
            actor_user_id=principal.user_id,
            agent_key=S5B_AGENT,
            question=question,
            tool_calls=[],
            input_classification=classification,
            grant=grant,
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
        answer=strip_markup(
            (answer.answer_en or answer.answer_ar) if locale == "en"
            else answer.answer_ar),
        status="ok",
        # بلا أدوات فلا استشهاد مسنود: اقتراح نموذج، لا دليل (§7.4).
        # §12 — إجابةٌ من معرفةٍ اعتمدها الباحث ليست اقتراح نموذج، وتُقال
        # كذلك. وما لا سند له يبقى `model_suggestion` مهما بدا واثقًا.
        evidence_state=("verified" if (answer.citations or document_context)
                        else "model_suggestion"),
        capabilities_used=capabilities,
        limitations=limitations,
        recommended_next_actions=actions + [
            _t(locale, "راجع الاقتراح واعتمد ما تريد إدخاله في مشروعك.",
               "Review the proposal and approve what you want to enter into your project."),
        ],
        model_run_id=result.model_run_id,
    )
