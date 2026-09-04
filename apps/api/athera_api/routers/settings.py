"""الإعدادات ووضع التشغيل | Settings and runtime posture (§26.4، §32، §36).

الغرض من هذه الشاشة ليس تغيير الإعدادات — الإعداد يقع في البيئة لا في
المتصفح — بل **الإفصاح** عن وضع التشغيل الحالي: أيّ مزود نموذج يعمل، وأيّ
سجل أدبيات، وهل الرصد المجدول مفعّل. مستخدم يظن أن النظام يستدعي نموذجًا
بينما `MODEL_PROVIDER=null` سيقرأ صمت النظام على أنه رأي.

ولا يُعاد هنا مفتاح ولا سرّ: تُعاد **حالة** المفتاح لا قيمته (§36.2).
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..deps import Principal, get_principal, get_session
from ..i18n.catalog import SUPPORTED_LOCALES
from ..models.identity import Tenant
from ..providers import gateway
from ..services import storage

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class PostureItem(BaseModel):
    key: str
    label: str
    value: str
    detail: str


class PostureResponse(BaseModel):
    tenant_name: str
    locale: str
    supported_locales: list[str]
    roles: list[str]
    items: list[PostureItem]


def _discovery_providers() -> tuple[str, ...]:
    """أسماءُ الفهارس من المزوّدين أنفسهم — لا قائمةٌ تُكتب بجانبهم فتفترق.

    وهو الخطأ المتكرّر في هذا المستودع: قيمةٌ تُكتب بجانب سجلّها بدل أن
    تُشتقّ منه، فيتغيّر السجلّ ويبقى النصّ يقول ما لم يعد صحيحًا.
    """
    from ..discovery.service import default_providers  # noqa: PLC0415

    return tuple(provider.name for provider in default_providers())


def _pick(locale: str, arabic: str, english: str) -> str:
    return english if locale == "en" else arabic


@router.get("/posture", response_model=PostureResponse)
async def posture(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> PostureResponse:
    settings = get_settings()
    locale = principal.locale

    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == principal.tenant_id))
    ).scalar_one_or_none()

    provider, ai_ready, _ai_reason = gateway.provider_readiness()
    registry = os.getenv("LITERATURE_REGISTRY", "offline")
    temporal = os.getenv("TEMPORAL_ENABLED", "0") == "1"
    items = [
        PostureItem(
            key="model_provider",
            label=_pick(locale, "مزوّد النموذج", "Model provider"),
            # الحال لا الاسم: `openai` بلا مفتاح ليس «متاحًا».
            value=provider if ai_ready else ("null" if provider == "null" else "not_configured"),
            detail=_pick(
                locale,
                "لا يُستدعى أي نموذج: المخرجات كلها من قواعد حتمية."
                if provider == "null" else
                ("المزوّد جاهز: أثيرا AI تستدعي نموذجًا."
                 if ai_ready else
                 "المزوّد مُسمّى ولا مفتاح له — أثيرا AI معطّلة حتى يُضبط على الخادم."),
                "No model is called: every output comes from deterministic rules."
                if provider == "null" else
                ("The provider is ready: ATHERA AI calls a model."
                 if ai_ready else
                 "A provider is named but has no key — ATHERA AI stays disabled until it is set on the server."),
            ),
        ),
        PostureItem(
            key="storage",
            label=_pick(locale, "تخزين ملفات البحث", "Research file storage"),
            # القيمة تصف الحال لا الاسم المكتوب في الإعداد.
            value=settings.storage_provider if storage.is_configured() else "not_configured",
            detail=_pick(
                locale,
                "التخزين مُهيّأ: الرفع والتنزيل يعملان. والملفات خاصة — لا رابط عام."
                if storage.is_configured() else
                "لا تخزين مُهيّأ: الرفع معطّل حتى تُضبط بيانات المزوّد على الخادم.",
                "Storage is configured: upload and download work. Files stay private — no public URL."
                if storage.is_configured() else
                "No storage configured: upload is disabled until provider credentials are set on the server.",
            ),
        ),
        # **والحال المعروضة تصف ما يقع فعلًا.**
        #
        # كان هذا البند يقول «بلا شبكة: لا يُستدعى سجل خارجي» ما دام
        # `LITERATURE_REGISTRY=offline`. وصار ذلك غيرَ صحيح حين وصل اكتشافُ
        # المراجع: هو ينادي Crossref وOpenAlex في كل بحث، بلا مفتاح ولا
        # إعداد. فالشاشة تنفي نداءً يقع — وهي أسوأ من شاشةٍ لا تقول شيئًا.
        #
        # فالبندان صارا اثنين: هذا يصف رصد الأدبيات المجدول وحده، وذاك
        # يصف فهارس الاكتشاف. ولكلٍّ حاله الصادقة.
        PostureItem(
            key="literature_registry",
            label=_pick(locale, "رصد الأدبيات المجدول", "Scheduled literature registry"),
            value=registry,
            detail=_pick(
                locale,
                "لا رصد مجدول من سجل خارجي. والبحث عن المراجع يعمل — انظر «فهارس المراجع»."
                if registry == "offline"
                else "يُستدعى سجل خارجي للرصد المجدول.",
                "No scheduled monitoring from an external registry. Reference search still "
                "works — see “Reference indexes”." if registry == "offline"
                else "An external registry is called for scheduled monitoring.",
            ),
        ),
        PostureItem(
            key="reference_indexes",
            label=_pick(locale, "فهارس المراجع", "Reference indexes"),
            value=", ".join(_discovery_providers()) or "none",
            detail=_pick(
                locale,
                "تُستدعى هذه الفهارس عند البحث عن المراجع، وكلُّ قيمةٍ تبقى منسوبة "
                "إلى قائلها." if _discovery_providers()
                else "لا فهرس مُفعَّل: البحث عن المراجع لا يعمل.",
                "These indexes are called when searching for references, and every value "
                "stays attributed to the index that stated it." if _discovery_providers()
                else "No index enabled: reference search does not work.",
            ),
        ),
        PostureItem(
            key="scheduled_monitoring",
            label=_pick(locale, "الرصد المجدول", "Scheduled monitoring"),
            value="on" if temporal else "off",
            detail=_pick(
                locale,
                "الجداول تعمل وتجمع إشارات في الخلفية." if temporal
                else "لا رصد في الخلفية؛ الإشارات تُدخَل يدويًّا فقط.",
                "Schedules run and collect signals in the background." if temporal
                else "No background monitoring; signals are entered manually only.",
            ),
        ),
        PostureItem(
            key="classification_ceiling",
            label=_pick(locale, "سقف تصنيف البيانات", "Data classification ceiling"),
            value=settings.model_external_send_max_classification,
            detail=_pick(
                locale, "أعلى تصنيف يُسمح بإرساله إلى مزود النموذج.",
                "The highest classification allowed to reach the model provider.",
            ),
        ),
    ]

    return PostureResponse(
        tenant_name=(tenant.name_en or tenant.name_ar) if locale == "en" and tenant
        else (tenant.name_ar if tenant else "—"),
        locale=locale, supported_locales=list(SUPPORTED_LOCALES),
        roles=principal.roles, items=items,
    )
