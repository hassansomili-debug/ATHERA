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
        await commit_request_session(request) # ← الإيداعُ هنا
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

## المعاملةُ الواحدة — **طلبٌ واحد، معاملةٌ واحدةٌ على الأكثر**

وحالةُ الطلب **خانةٌ واحدة** لا قائمة، وذاك مقصود: قائمةٌ تُودَع بالتسلسل
**ليست ذرّيّة**. فلو أُودعت الأولى ثمّ أخفقت الثانية لَصار الجوابُ إخفاقًا
**والأولى مُودَعةٌ لا سبيل إلى إرجاعها** — نصفُ كتابةٍ تحت جوابِ إخفاق،
وهو أسوأُ من رفضٍ صريح.

فتُرفض المعاملةُ الثانية مغلقًا (`MultipleRequestTransactions`)، والرفعُ
يقع في التبعيّة **قبل `yield`** — أي قبل أن يكتب المعالجُ شيئًا.

**ولا مسارَ في التطبيق اليوم يحتاج اثنتين**: مقيسٌ على شجرة التبعيّات
المُركَّبة لمئتين وتسعةٍ وستّين مسارًا — الأقصى **واحدة**، ولا
`use_cache=False` على تبعيّةِ جلسةٍ في الشجرة كلِّها. ويحرسه فحص.

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

#: **خانةٌ واحدةٌ لا قائمة** — والوحدانيّةُ بنيةٌ لا عُرف. انظر §المعاملةُ الواحدة.
_STATE_KEY = "athera_request_session"

#: رمزُ الإخفاق — نصُّه في `i18n/catalog.py` بالعربية والإنجليزية.
COMMIT_FAILED = "db.commit_failed"

#: خطأُ بنيةٍ لا خطأُ عميل: طلبٌ حاول أن يملك معاملتين.
MULTIPLE_TRANSACTIONS = "db.multiple_request_transactions"


class MultipleRequestTransactions(AtheraError):
    """طلبٌ حاول تسجيلَ معاملةٍ ثانية — **وهذا خطأُ برمجةٍ يُوقف الطلب**.

    ولمَ يُرفع ولا يُجمَع: إيداعُ معاملتين بالتسلسل **ليس ذرّيًّا**. فلو
    نجحت الأولى وأخفقت الثانية لَصار الجوابُ إخفاقًا **والأولى مُودَعة
    لا سبيل إلى إرجاعها**. فالجمعُ يُنتج نصفَ كتابةٍ تحت جوابِ إخفاق —
    وهو أسوأُ من الرفض الصريح.

    ولا مسارَ في التطبيق اليوم يحتاج معاملتين (مقيسٌ على الشجرة
    المُركَّبة: الأقصى واحدة). فإن احتاج مسارٌ ذلك غدًا فهو **قرارُ تصميمٍ
    يُتّخذ صريحًا**، لا سلوكٌ يُسمح به صامتًا.
    """

    def __init__(self) -> None:
        super().__init__(MULTIPLE_TRANSACTIONS, status_code=500)


def register_request_session(request: Request, session: AsyncSession) -> None:
    """تُسجّل معاملةَ الطلب — **وواحدةً فقط**، وإلّا رُفض الطلب مغلقًا.

    والرفعُ يقع في التبعيّة **قبل `yield`**، أي قبل أن يعمل المعالجُ
    ويكتب شيئًا: فلا طفرةَ تقع ثمّ تُرفض.

    وتسجيلُ **الكائن نفسِه** مرّةً ثانيةً لا يضرّ (تخزينُ FastAPI المؤقّت
    يمنعه أصلًا، والسماحُ به يجعل الدالّةَ صالحةً لإعادة النداء).
    """
    existing: AsyncSession | None = getattr(request.state, _STATE_KEY, None)
    if existing is None:
        setattr(request.state, _STATE_KEY, session)
        return
    if existing is session:
        return
    logger.error(
        "a request attempted to own a second database transaction",
        extra={
            "request_id": request.headers.get("x-request-id"),
            "route": request.scope.get("route_path") or request.url.path,
            "method": request.method,
            "transaction_outcome": "refused_second_transaction",
        },
    )
    raise MultipleRequestTransactions


def request_session(request: Request) -> AsyncSession | None:
    """معاملةُ هذا الطلب — أو `None` إن كان المسارُ يملك معاملتَه في متنه."""
    return getattr(request.state, _STATE_KEY, None)


async def commit_request_session(request: Request) -> None:
    """يُودِع معاملةَ الطلب — **وإخفاقُها خطأٌ يُرفع لا سطرٌ في سجلّ**.

    ولا يُودَع إلّا ما بقيت معاملتُه حيّةً: فمسارٌ أودع بنفسه قبل جدولةِ
    عملٍ في الخلفية لا يُودَع مرّتين.
    """
    session = request_session(request)
    if session is not None and session.in_transaction():
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
            await commit_request_session(request)
            return response

        return transactional
