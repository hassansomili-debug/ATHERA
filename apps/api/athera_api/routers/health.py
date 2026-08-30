from fastapi import APIRouter, Depends

from ..config import get_settings
from ..deps import get_locale
from ..providers.gateway import build_provider
from ..schemas.common import Health

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=Health)
async def healthz(locale: str = Depends(get_locale)) -> Health:
    settings = get_settings()
    return Health(status="ok", locale=locale, supported_locales=settings.locales,
                  provider=build_provider().name)


@router.get("/readyz", response_model=Health)
async def readyz(locale: str = Depends(get_locale)) -> Health:
    from sqlalchemy import text

    from ..db import engine

    settings = get_settings()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return Health(status="ready", locale=locale, supported_locales=settings.locales,
                  provider=build_provider().name)
