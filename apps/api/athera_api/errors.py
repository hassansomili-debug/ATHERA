"""أخطاء ثنائية اللغة | Bilingual error envelope."""
from fastapi import Request
from fastapi.responses import JSONResponse

from .i18n.catalog import all_translations, negotiate_locale, translate


class AtheraError(Exception):
    """خطأ يحمل مفتاح رسالة لا نصًا — الترجمة تقع عند حدود الـHTTP."""

    def __init__(self, code: str, status_code: int = 400, **context: object) -> None:
        self.code = code
        self.status_code = status_code
        self.context = context
        super().__init__(code)


class NotFound(AtheraError):
    def __init__(self, code: str, **context: object) -> None:
        super().__init__(code, status_code=404, **context)


class Forbidden(AtheraError):
    def __init__(self, code: str = "authz.forbidden", **context: object) -> None:
        super().__init__(code, status_code=403, **context)


class Unauthorized(AtheraError):
    def __init__(self, code: str, **context: object) -> None:
        super().__init__(code, status_code=401, **context)


async def athera_error_handler(request: Request, exc: AtheraError) -> JSONResponse:
    locale = negotiate_locale(request.headers.get("accept-language"))
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "locale": locale,
                "message": translate(exc.code, locale),
                "messages": all_translations(exc.code),
                "context": {k: str(v) for k, v in exc.context.items()},
            }
        },
        headers={"Content-Language": locale},
    )
