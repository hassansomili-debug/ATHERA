import logging

from fastapi import APIRouter, Depends

from ..config import get_settings
from ..deps import get_locale
from ..errors import AtheraError
from ..providers.gateway import provider_readiness
from ..schemas.common import Health
from ..services import db_posture

router = APIRouter(tags=["health"])

logger = logging.getLogger("athera.health")


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
    """جاهزٌ يعني: القاعدة تُجيب **وعزل المستأجرين ينطبق على هذا الاتصال**.

    فحص `SELECT 1` وحده كان يقول «جاهز» بينما الرابط يتصل بدورٍ يتجاوز RLS
    — وهو بالضبط ما وقع في الإنتاج. والاتصال السليم ليس جهوزية إن كان يبطل
    طبقة العزل: عطبٌ صامت أسوأ من عطبٍ معلن.
    """
    from ..db import engine

    posture = await db_posture.inspect(engine)
    if not posture.safe:
        # يُسجَّل بالتفصيل داخليًّا، ويُردّ برمز واحد لا يفشي بنية القاعدة.
        logger.error("readiness refused — %s: %s", db_posture.UNSAFE_REASON,
                     posture.detail())
        raise AtheraError("readiness.database_role_unsafe", status_code=503)
    return _health("ready", locale)
