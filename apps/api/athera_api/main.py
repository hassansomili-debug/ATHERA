"""نقطة الدخول | ATHERA API entrypoint.

المسار الإلزامي (§38.6.8):
    UI → API Gateway → Brain/Policy → Model Provider/Tools → Audit → Response
لا يوجد مسار جانبي: الواجهة لا تعرف مزود النموذج، ولا تحمل مفتاحه.
"""
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .errors import AtheraError, athera_error_handler
from .i18n.catalog import all_translations, negotiate_locale, translate
from .routers import analysis as analysis_router
from .routers import ai as ai_router
from .routers import audit as audit_router
from .routers import auth as auth_router
from .routers import brain as brain_router
from .routers import document_intelligence as document_intelligence_router
from .routers import files as files_router
from .routers import golden_thread as golden_thread_router
from .routers import health as health_router
from .routers import inbox as inbox_router
from .routers import literature as literature_router
from .routers import manuscript_drafting as manuscript_drafting_router
from .routers import memory as memory_router
from .routers import planning as planning_router
from .routers import portfolio as portfolio_router
from .routers import profile as profile_router
from .routers import publishing as publishing_router
from .routers import settings as settings_router
from .routers import team as team_router
from .routers import tenants as tenants_router
from .routers import thesis as thesis_router
from .routers import trends as trends_router
from .routers import workspace as workspace_router

settings = get_settings()

app = FastAPI(
    title="ATHERA API",
    version="0.1.0",
    description=(
        "AI-Native Scientific Research & Publication Platform. "
        "واجهة برمجية ثنائية اللغة؛ كل خطأ يحمل رمزًا آليًا ونصًا بالعربية والإنجليزية."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Language", "X-Request-ID"],
)


# **البطء كان يُشتكى منه ولا يُقاس.**
#
# «المنصّة بطيئة» جملةٌ لا تُصلَّح: لا تقول أيّ مسار، ولا كم، ولا هل هو
# الشبكة أم الاستعلام. وكنّا نخمّن ثم نُحسّن ما لم يكن بطيئًا.
#
# **والقالب لا المسار.** يُسجَّل `/api/v1/files/{file_id}` لا المسار
# المملوء: المملوء يحمل معرّفات الباحث وملفّاته، والقالب يجيب عن السؤال
# نفسه («أيّ نقطة بطيئة») بلا أن يحمل شيئًا من ذلك. ولا أجسام، ولا
# استعلامات، ولا ترويسات، ولا نصّ مستند، ولا موجّه نموذج.
_timing = logging.getLogger("athera.timing")

# ما تجاوز هذا يُعلَن تحذيرًا — فلا يُبتلع بطءٌ في سطرٍ عادي بين آلاف.
SLOW_REQUEST_MS = 1000.0


@app.middleware("http")
async def request_context(request: Request, call_next):
    """معرّف طلب + تفاوض لغة + زمنُ الاستجابة على كل استجابة (§38.5، §26.4)."""
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    locale = negotiate_locale(request.headers.get("accept-language"))
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers.setdefault("Content-Language", locale)
    # مقياسٌ يقرؤه المتصفّح أيضًا، فيُرى البطء من جهة الباحث لا من السجلّ وحده.
    response.headers["Server-Timing"] = f"app;dur={duration_ms:.1f}"

    route = request.scope.get("route")
    template = getattr(route, "path", None) or "unmatched"
    _timing.log(
        logging.WARNING if duration_ms >= SLOW_REQUEST_MS else logging.INFO,
        "%s %s -> %s in %.1fms [%s]",
        request.method, template, response.status_code, duration_ms, request_id,
    )
    return response


app.add_exception_handler(AtheraError, athera_error_handler)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """يوحّد مظروف أخطاء العقد مع بقية الأخطاء (§26.4).

    كان رفض Pydantic يعود بشكل FastAPI الافتراضي: بلا `code` وبلا اللغتين،
    فيقع عميل المتصفح على رسالته الاحتياطية. وثنائية اللغة شرط في كل طبقة لا
    في الطبقات التي تذكّرنا بها — ومسار الرفض هو أكثر ما يقرأه المستخدم.

    مواضع الحقول تُنقل كما هي: هي أسماء حقول العقد، لا نصوص تُترجم.
    """
    locale = negotiate_locale(request.headers.get("accept-language"))
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation.failed",
                "locale": locale,
                "message": translate("validation.failed", locale),
                "messages": all_translations("validation.failed"),
                "context": {
                    ".".join(str(part) for part in error.get("loc", ())): error.get("msg", "")
                    for error in exc.errors()
                },
            }
        },
        headers={"Content-Language": locale},
    )


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    locale = negotiate_locale(request.headers.get("accept-language"))
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "server.error",
                "locale": locale,
                "message": translate("server.error", locale),
                "messages": all_translations("server.error"),
            }
        },
    )


app.include_router(health_router.router)

app.include_router(auth_router.router)
app.include_router(tenants_router.router)
app.include_router(files_router.router)
app.include_router(audit_router.router)
app.include_router(inbox_router.router)
app.include_router(profile_router.router)
app.include_router(memory_router.router)
app.include_router(brain_router.router)
app.include_router(ai_router.router)
app.include_router(planning_router.router)
app.include_router(portfolio_router.router)
app.include_router(team_router.router)
app.include_router(settings_router.router)
app.include_router(literature_router.router)
app.include_router(golden_thread_router.router)
app.include_router(document_intelligence_router.router)
app.include_router(thesis_router.router)
app.include_router(publishing_router.router)
app.include_router(manuscript_drafting_router.router)
app.include_router(analysis_router.router)
app.include_router(trends_router.router)
app.include_router(workspace_router.router)
