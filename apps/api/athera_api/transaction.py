"""حدُّ المعاملة للطلب — **جوابُ النجاح يعني أنّ الإيداع وقع** (RC-T1-H1).

## العطبُ الذي يُغلقه هذا الملفّ

تبعيّةُ الجلسة ذاتُ `yield` تُودِع معاملتَها في فكِّ حزمةِ الطلب، و FastAPI
يفكّها **بعد** أن يُرسل الجوابَ (`fastapi/routing.py`، 0.141.1):

```python
async with AsyncExitStack() as request_stack:      # التبعيّةُ ذاتُ yield هنا
    async with AsyncExitStack() as function_stack:
        response = await f(request)                # ← معالجُ المسار
    await response(scope, receive, send)           # ← الجوابُ يُرسَل
# ← تُفكّ الحزمةُ الآن، فتُودِع التبعيّةُ معاملتَها
```

فمئةٌ وتسعةٌ وعشرون مسارَ طفرةٍ تقول «تمّ» ثمّ تُودِع. وإن أخفق الإيداعُ
بعد ذلك **فلا سبيلَ إلى إبلاغ العميل**: قد قيل له تمّ، ومعه معرّفُ صفٍّ لا
وجود له. وقد ثبت هذا بقيدٍ مؤجَّلٍ حقيقيّ في
`tests/test_at_rc_t1_h1_transaction_integrity.py`: العميلُ أخذ ٢٠١ ومعه
`id`، والقاعدةُ رفضت الإيداع.

## والعلاجُ بنيةٌ لا عُرف

**ملكيّةُ الإيداع تنتقل إلى البنية، وتقع داخل معالج المسار** — أي قبل
`await response(...)` بحكم الترتيب أعلاه، لا برجاءٍ ولا بمهلة:

    TransactionalRoute.get_route_handler()
        response = await original(request)     # المعالجُ بنى الجواب
        await commit_request_sessions(request) # ← الإيداعُ هنا
        return response                        # ← ثمّ يُرسَل الجواب

وإن أخفق الإيداعُ رُفع `AtheraError` من المعالج نفسِه، فيمرّ بمعالجات
استثناءات التطبيق ويصل العميلَ **خطأً مُصنَّفًا** لا نجاحًا. ولأنّ الاستثناء
يصعد قبل `await response(...)` فلا جوابَ أُرسل ليُنقض.

## ولمَ صنفُ مسارٍ لا وسيط (middleware)

الوسيطُ يعمل خارج حلّ التبعيّات، فلا يعرف المستأجرَ ولا الفاعلَ — وهما من
`get_principal` — فيلزمه فكُّ الرمز بنفسه. **وتكرارُ المصادقة في موضعٍ ثانٍ
هو بعينه ما يجمعه هذا المستودع في موضعٍ واحد.** فيُرفض.

وصنفُ المسار يُثبَّت مرّةً على كلِّ موجّه، ويحرسه فحصٌ معماريّ: موجّهٌ جديد
بلا `route_class` يُسقط الحزمة. **فالإنفاذُ بنيويّ لا قائمةُ مراجعةٍ بشرية.**

## وما لا يُمَسّ

  • **الرجوعُ يبقى للتبعيّة**: `db._scope` تُرجِع في `finally` إن بقيت
    معاملةٌ حيّة — فسقوطُ المعالج يُرجِع، وإخفاقُ الإيداع يُرجِع.
  • **الإغلاقُ يبقى لـ`SessionFactory`**: `async with` تُغلق دائمًا.
  • **ولا إيداعَ مزدوج**: يُودَع ما بقيت معاملتُه حيّةً وحدَه، فمسارٌ
    أودع بنفسه (`document_intelligence`) يمرّ بلا مسّ.
  • **ومسارٌ يملك معاملتَه في متنه** (`auth`، `analysis`) لا يُسجّل جلسةً
    هنا أصلًا، فالغلافُ لا يفعل شيئًا له — وهو صحيحٌ بحكم بنيته.
  • **ولا توسيعَ صلاحية**: لا يُمَسّ دورٌ ولا سياقُ مستأجرٍ ولا RLS.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import Request, Response
from fastapi.routing import APIRoute

from .errors import AtheraError

if TYPE_CHECKING:  # pragma: no cover - للأنواع وحدها
    from collections.abc import Callable, Coroutine

    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("athera.transaction")

#: موضعُ جلسات الطلب على حالته — قائمةٌ لأنّ طلبًا قد يفتح أكثر من جلسة.
_STATE_KEY = "athera_request_sessions"

#: رمزُ الإخفاق — نصُّه في `i18n/catalog.py` بالعربية والإنجليزية.
COMMIT_FAILED = "db.commit_failed"


def register_request_session(request: Request, session: AsyncSession) -> None:
    """تُسجّل جلسةً يملك الطلبُ إيداعَها — تناديها تبعيّاتُ الجلسة وحدها."""
    sessions: list[AsyncSession] | None = getattr(request.state, _STATE_KEY, None)
    if sessions is None:
        sessions = []
        setattr(request.state, _STATE_KEY, sessions)
    sessions.append(session)


def request_sessions(request: Request) -> list[AsyncSession]:
    """جلساتُ هذا الطلب — تُقرأ في الفحوص وفي الغلاف."""
    return list(getattr(request.state, _STATE_KEY, ()) or ())


async def commit_request_sessions(request: Request) -> None:
    """يُودِع معاملاتِ الطلب — **وإخفاقُها خطأٌ يُرفع لا سطرٌ في سجلّ**.

    ويُودَع ما بقيت معاملتُه حيّةً وحدَه: فمسارٌ أودع بنفسه قبل جدولةِ
    عملٍ في الخلفية لا يُودَع مرّتين.
    """
    for session in request_sessions(request):
        if not session.in_transaction():
            continue
        try:
            await session.commit()
        except Exception as failure:
            # **والرجوعُ صريحٌ قبل الرفع.** الجلسةُ تُغلق على أيّ حال في
            # `SessionFactory`، لكنّ إعادةَ ضبطها هنا تمنع أن يُقرأ شيءٌ
            # من معاملةٍ مُجهَضة في ما بقي من فكِّ الحزمة.
            try:
                await session.rollback()
            except Exception:  # pragma: no cover - الإغلاق يتولّى الباقي
                logger.debug("rollback after a failed commit did not complete")
            # **ولا حمولةَ في السجلّ**: مسارٌ ومعرّفُ طلبٍ وتصنيفٌ آمن،
            # ولا جسمَ طلبٍ ولا محتوى بحثٍ ولا ترويسةَ تفويض.
            logger.error(
                "transaction commit failed",
                extra={
                    "request_id": request.headers.get("x-request-id"),
                    "route": request.scope.get("route_path") or request.url.path,
                    "method": request.method,
                    "transaction_outcome": "commit_failed",
                    "failure_class": type(failure).__name__,
                },
            )
            raise AtheraError(COMMIT_FAILED, status_code=503) from failure


class TransactionalRoute(APIRoute):
    """مسارٌ يُودِع معاملةَ طلبه **قبل** أن يُرسل جوابَه.

    ولا يعرف المعالجُ بهذا شيئًا: يبني جوابَه كما كان، والبنيةُ تُودِع
    بعده وقبل الإرسال. فلا سطرَ في مسارٍ واحدٍ يلزم تغييرُه لأجل الصحّة.
    """

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def transactional(request: Request) -> Response:
            response = await original(request)
            # **هنا بعينه**: المعالجُ انتهى وبنى جوابَه، والجوابُ لم يُرسَل
            # بعد — فإخفاقُ الإيداع ما زال قابلًا لأن يُقال للعميل.
            await commit_request_sessions(request)
            return response

        return transactional
