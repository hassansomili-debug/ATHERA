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

    provider = settings.model_provider
    registry = os.getenv("LITERATURE_REGISTRY", "offline")
    temporal = os.getenv("TEMPORAL_ENABLED", "0") == "1"
    has_key = bool(
        settings.anthropic_api_key if provider == "anthropic"
        else settings.openai_api_key if provider == "openai"
        else True
    )

    items = [
        PostureItem(
            key="model_provider",
            label=_pick(locale, "مزوّد النموذج", "Model provider"),
            value=provider,
            detail=_pick(
                locale,
                "لا يُستدعى أي نموذج: المخرجات كلها من قواعد حتمية."
                if provider == "null" else
                ("المفتاح مضبوط." if has_key else "المفتاح غير مضبوط — الاستدعاء سيفشل."),
                "No model is called: every output comes from deterministic rules."
                if provider == "null" else
                ("The key is configured." if has_key else
                 "The key is not configured — calls will fail."),
            ),
        ),
        PostureItem(
            key="storage",
            label=_pick(locale, "تخزين ملفات البحث", "Research file storage"),
            value=settings.storage_provider,
            detail=_pick(
                locale,
                "التخزين مُهيّأ: الرفع والتنزيل يعملان. والملفات خاصة — لا رابط عام."
                if settings.storage_provider != "none" else
                "لا تخزين مُهيّأ: الرفع معطّل حتى تُضبط بيانات المزوّد.",
                "Storage is configured: upload and download work. Files stay private — no public URL."
                if settings.storage_provider != "none" else
                "No storage configured: upload is disabled until provider credentials are set.",
            ),
        ),
        PostureItem(
            key="literature_registry",
            label=_pick(locale, "سجل الأدبيات", "Literature registry"),
            value=registry,
            detail=_pick(
                locale,
                "بلا شبكة: لا يُستدعى سجل خارجي." if registry == "offline"
                else "يُستدعى سجل خارجي عند البحث والرصد.",
                "Offline: no external registry is called." if registry == "offline"
                else "An external registry is called for search and monitoring.",
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
