"""RC-T1-H2-B1 — تغطيةُ ماسح الانتظار الخارجيّ | external-wait scanner coverage.

## لماذا وُسّع الماسح قبل أن يُبنى شيء

الطورُ B سيمسّ مساراتِ التخزين. ودعوى «صفرُ معاملاتٍ عبر انتظارٍ خارجيّ»
لا تصلح أساسًا لذلك ما دام الحارسُ **أعمى عن التخزين**. فالتغطيةُ أوّلًا،
ثمّ البناء.

وثلاثُ ثقوبٍ سُدّت، وكلُّها كانت تُسقط حافةً صامتةً لا تُبلِّغ عن شيء:

  ١ **إسنادٌ محلّيٌّ من بانٍ**: `x = Orchestrator()` ثمّ `x.method()`.
  ٢ **عملياتُ مخزن الكائنات**: كُشفت بسلسلةِ نصٍّ (`boto3`/`_s3`) لا تظهر
    إلّا في `__init__`، فبقيت كلُّ قراءةٍ وكتابةٍ خارجَ مجموعة المنافذ.
  ٣ **تسليمٌ إلى مُنفِّذ**: `run_in_threadpool(store.put_stream, …)` —
    الطريقةُ وسيطٌ لا نداء، فلا حافةَ تُجمع منها. ومعه حلُّ `<نداء>.<سمة>`
    بنوعِ العودة المُعلَن، وإلّا حلَّ `get_store().put_stream` إلى اسمٍ
    لا وجودَ له.

**وكلُّ ثقبٍ يُقاس بعضّة**: تُزال قدرتُه فيسقط فحصُه.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:  # pragma: no cover
    sys.path.insert(0, str(HERE.parent))

from tests.external_wait_audit import (  # noqa: E402
    EXECUTOR_HANDOFFS,
    OBJECT_STORE_OPS,
    audit,
)

#: النمطُ الحقيقيُّ القائم في المستودع — لا شجرةٌ مُصطنَعة.
BRAIN_ASK = "athera_api.routers.brain:ask"
UPLOAD_FILE = "athera_api.routers.files:upload_file"


@pytest.fixture(scope="module")
def scan():
    return audit()


def test_01_a_local_variable_constructor_edge_is_followed(scan):
    """**الثقبُ الأوّل**: `brain.py::ask` يبني منسّقًا في متغيّرٍ ثمّ ينادي عليه.

    والطريقةُ المُنادى عليها موسومةٌ `MODEL` أصلًا؛ المفقودُ كان الحافةَ
    وحدها. فكان أشهرُ مسارِ نموذجٍ في المنتج غيرَ مرئيٍّ للوصوليّة كلِّها.
    """
    assert scan.reach.get(BRAIN_ASK) == "MODEL", (
        "مسارُ `brain/ask` غيرُ مرئيٍّ للماسح — حافةُ الإسناد المحلّيّ مفقودة")
    target = "athera_api.brain.orchestrator:Orchestrator.run_agent_detached"
    assert scan.reach.get(target) == "MODEL", "الطريقةُ نفسُها ليست موسومة"


def test_02_object_store_operations_are_egress(scan):
    """**الثقبُ الثاني**: عملياتُ المخزن تُعرَف بواجهتها لا بنصِّ متنها.

    و`S3ObjectStore.put` تنادي `self._client.put_object`، فلا `boto3` في
    متنها ولا `_s3`. فالحدُّ هو الصنفُ المجرَّد `ObjectStore` وعملياتُه
    المُعلَنة — ويشمل ذلك كلَّ تنفيذٍ يرثه.
    """
    marked = {q for q, kind in scan.egress.items() if kind == "STORAGE"}
    for op in ("put", "put_stream", "get", "get_stream", "delete",
               "presign_get", "presign_put"):
        assert op in OBJECT_STORE_OPS, f"عمليّةٌ غائبةٌ عن الإعلان: {op}"
        assert any(q.endswith(f"S3ObjectStore.{op}") for q in marked), (
            f"عمليّةُ التخزين غيرُ موسومةٍ منفذًا: S3ObjectStore.{op}")
    # وكلُّ تنفيذٍ للواجهة، لا الملموسَ وحده.
    for impl in ("ObjectStore", "MemoryObjectStore"):
        assert any(q.endswith(f"{impl}.put_stream") for q in marked), (
            f"تنفيذُ الواجهة غيرُ مشمول: {impl}")


def test_03_an_executor_handoff_is_an_edge(scan):
    """**الثقبُ الثالث**: `run_in_threadpool(store.put_stream, …)`.

    والطريقةُ تُمرَّر ولا تُنادى، وجمعُ الحافات يقرأ `func` النداءات
    وحدَها. فكلُّ كتابةِ تخزينٍ في `files.py` كانت غيرَ مرئيّة — ومعها
    مسارُ الرفع نفسُه.
    """
    assert "run_in_threadpool" in EXECUTOR_HANDOFFS
    assert scan.reach.get(UPLOAD_FILE) == "STORAGE", (
        "مسارُ الرفع غيرُ مرئيٍّ — حافةُ تسليم المُنفِّذ مفقودة")
    for handler in ("init_upload", "download_file", "stream_file"):
        assert scan.reach.get(f"athera_api.routers.files:{handler}") == "STORAGE", (
            f"مسارُ تخزينٍ غيرُ مرئيّ: {handler}")


def test_04_the_expanded_scanner_does_not_flag_everything(scan):
    """**ولا يُوسَّع الحارسُ إلى ضجيج.**

    فتوسيعٌ يَسِم كلَّ شيءٍ لا يحرس شيئًا. والمساراتُ التي لا تمسّ خارجًا
    تبقى غيرَ موسومة، والأسماءُ العامّة لا تُرقّى إلى منافذ.
    """
    # مساراتٌ ذرّيّةٌ في القاعدة — لا خارجَ فيها البتّة (الطور A).
    for clean in ("athera_api.routers.workspace:create_project",
                  "athera_api.routers.portfolio:create_project",
                  "athera_api.routers.publishing:create_manuscript"):
        assert scan.reach.get(clean) is None, (
            f"مسارٌ ذرّيٌّ وُسم خارجيًّا — بلاغٌ كاذب: {clean}")
    # ولا بذرةَ واجهةٍ فُقدت بالتوسيع.
    assert scan.missing_seeds == [], f"بذورٌ مفقودة: {scan.missing_seeds}"


# ════════ المخالفةُ التي كشفها التوسيع — وقد أُصلحت ════════
#
# `POST /api/v1/theses/upload` كان يُعلن `Depends(get_session)`، والتبعيّةُ
# تفتح معاملةَ الطلب **قبل** أن يعمل المتن. فكانت معاملةُ قاعدةٍ تُمسَك
# عبر بثِّ الملفّ إلى التخزين مقطعًا مقطعًا — إلى مئات الميغابايت.
#
# وقد وقع العطبُ نفسُه من قبل في `files.upload_file` وعُولج هناك، فبقي
# المتّصلُ به يفتح المعاملةَ من فوقه. فالعلاجُ يكتمل عند المُنادي.


def test_05_the_thesis_upload_holds_no_transaction_across_the_storage_write(scan):
    """**ولا معاملةَ حتى يعود التخزين** — ويُقاس بالبنية لا بالنيّة."""
    import ast
    import inspect
    import textwrap

    from athera_api.routers import document_intelligence as router_module

    source = textwrap.dedent(inspect.getsource(router_module.upload_thesis))
    tree = ast.parse(source)
    fn = tree.body[0]

    # (أ) لا تبعيّةَ جلسةٍ على المعالج — وهي التي كانت تفتح المعاملة.
    defaults = [d for d in [*fn.args.defaults,
                            *[k for k in fn.args.kw_defaults if k is not None]]]
    depends = {
        arg.id
        for d in defaults if isinstance(d, ast.Call)
        and getattr(d.func, "id", "") == "Depends"
        for arg in d.args if isinstance(arg, ast.Name)
    }
    assert "get_session" not in depends, (
        "عاد `Depends(get_session)` إلى معالج الرفع — فمعاملةُ الطلب "
        "تُمسَك عبر بثِّ الملفّ إلى التخزين")

    # (ب) نداءُ التخزين خارج كلِّ معاملةٍ يملكها المتن.
    owned = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.AsyncWith)
        and any(getattr(c.func, "id", getattr(c.func, "attr", "")) == "tenant_session"
                for item in n.items for c in ast.walk(item.context_expr)
                if isinstance(c, ast.Call))
    ]
    uploads = [n.lineno for n in ast.walk(fn)
               if isinstance(n, ast.Call)
               and getattr(n.func, "id", "") == "upload_file"]
    assert uploads, "لم يُعد المعالجُ ينادي `upload_file`"
    for at in uploads:
        assert not any(b.lineno <= at <= (b.end_lineno or b.lineno) for b in owned), (
            "نداءُ التخزين داخل معاملةٍ مفتوحة — وهو عطبُ RC-T1-H3 بعينه")

    # (ج) والرفعُ يسبق عملَ القاعدة، فلا يُنشأ سجلٌّ لملفٍّ لم يُحفظ.
    assert owned, "لا معاملةً قصيرةً بعد الرفع — من يكتب سجلَّ الرسالة؟"
    assert min(uploads) < min(b.lineno for b in owned), (
        "عملُ القاعدة يسبق الرفع — فقد يُكتب سجلٌّ لملفٍّ لم يُحفظ")


def test_06_the_thesis_upload_is_visible_but_not_an_offender(scan):
    """**والإصلاحُ أزال المخالفةَ لا الرؤية.**

    فحارسٌ يُسكَت بإخفاء المسار عنه لا يحرس شيئًا. فالمسارُ يبقى موسومًا
    `STORAGE` — أي إنّ الماسحَ يراه ويقيسه — ولا يُبلَّغ عنه لأنّ المعاملةَ
    لم تعد مفتوحةً أثناء الانتظار.
    """
    route = "athera_api.routers.document_intelligence:upload_thesis"
    assert scan.reach.get(route) == "STORAGE", (
        "فُقدت رؤيةُ مسار الرفع — أُصلحت المخالفةُ بإخفائها لا بإزالتها")
    assert [o for o in scan.offenders() if o.handler == "upload_thesis"] == [], (
        "ما زال مسارُ رفع الرسالة مخالفًا")


def test_07_the_application_has_zero_external_wait_offenders(scan):
    """**والدعوى المُطلَقة تُعاد بعد التوسيع** — وهي الآن تشمل التخزين."""
    offenders = scan.offenders()
    assert offenders == [], (
        "مخالفاتٌ حقيقيّةٌ في التطبيق:\n" + "\n".join(o.describe() for o in offenders))
