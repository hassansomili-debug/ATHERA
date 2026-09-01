from fastapi import APIRouter, Depends

from ..config import get_settings
from ..deps import get_locale
from ..providers.gateway import provider_readiness
from ..schemas.common import Health

router = APIRouter(tags=["health"])


def _health(status: str, locale: str) -> Health:
    """وصف الحال بلا إنشاء عميل ولا اتصال بمزوّد.

    **الجهوزية لا تُبنى بالمزوّد.** `build_provider()` يُنشئ عميلًا حقيقيًا
    ويرفع استثناءً بلا مفتاح — فمزوّد مُسمّى بلا سرّ كان سيُسقط فحص صحة
    التطبيق كله، وتُعدّ الآلة معطوبة بينما المكتبة والتخزين والفحوص الحتمية
    تعمل تمامًا. عطل عند مزوّد خارجي يجب ألّا يُطفئ منتجًا يعمل بلا نموذج.
    """
    settings = get_settings()
    provider, ai_ready, _ = provider_readiness()
    return Health(
        status=status, locale=locale, supported_locales=settings.locales,
        provider=provider, ai_configured=ai_ready,
    )


@router.get("/healthz", response_model=Health)
async def healthz(locale: str = Depends(get_locale)) -> Health:
    return _health("ok", locale)


@router.get("/readyz", response_model=Health)
async def readyz(locale: str = Depends(get_locale)) -> Health:
    from sqlalchemy import text

    from ..db import engine

    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return _health("ready", locale)
