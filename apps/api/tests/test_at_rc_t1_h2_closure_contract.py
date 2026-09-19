"""RC-T1-H2 — **عقدُ الإغلاق** | the closure contract.

هذه الفحوصُ لا تحرس نثرًا. تحرس ثوابتَ الإغلاق التي لو انكسر أحدُها لصارت
دعوى «RC-T1-H2 مُغلَق» كاذبةً وهي مكتوبة:

  • المخطَّطُ الذي بُني عليه الإغلاق ما زال هو؛
  • مكوّناتُ H2 السبعةُ ما زالت لها فحوصُها؛
  • حارسُ سياسةِ المتصفّح ما زال قائمًا وموصولًا بمشغّل؛
  • **أفقُ المتصفّح الآمن ما زال دون بقاءِ الخادم** — وهذا تماسٌ كُتب
    طرفاه في لغتين ولم يكن يحرسه شيء؛
  • ولا دعوى «مرّةً واحدةً بالضبط» تسرّبت إلى مشغّلٍ ولا إلى الدفتر؛
  • والدفترُ يقول ما لا يُدَّعى، ويقول إنّ الحال مُغلَق، ويُسلّم إلى ٨.

**وموضعُ هذا الملفّ عمدًا في `apps/api`**: هو الوحيد الذي يرى الطرفين —
مصدرَ الخادم ومصدرَ الوِب — فيستطيع أن يفحص التماسَ بينهما.
"""
from __future__ import annotations

import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[3]
API = REPO / "apps" / "api"
WEB = REPO / "apps" / "web"
DOCS = REPO / "docs" / "maintenance"
LEDGER = DOCS / "RC-T1-H2-closure.md"

EXPECTED_SCHEMA_HEAD = "0037"

COMPONENT_TESTS = {
    "H2-A": "test_at_rc_t1_h2a_idempotency.py",
    "H2-B1": "test_at_rc_t1_h2b1_lease.py",
    "H2-B1-scanner": "test_at_rc_t1_h2b1_scanner_coverage.py",
    "H2-B2": "test_at_rc_t1_h2b2_external_read_flows.py",
    "H2-B3": "test_at_rc_t1_h2b3_file_storage.py",
    "H2-B4": "test_at_rc_t1_h2b4_model_ambiguity.py",
    "H2-B5": "test_at_rc_t1_h2b5_thesis_processing_recovery.py",
    "Stage6-provider": "test_at_stage6_web_key_reaches_provider_once.py",
}

WEB_GUARDS = (
    "idempotency-policy.spec.ts",
    "idempotency-coverage.spec.ts",
    "backend-keyed-routes.spec.ts",
    "idempotency-expiry.spec.ts",
)

MANDATORY_NON_CLAIMS = (
    "exactly-once execution",
    "exactly-once provider execution",
    "exactly-once physical storage PUT",
    "durable background queue",
    "automatic crash recovery without a later authorized request",
    "infinite idempotency retention",
    "cross-tab browser intent identity",
    "cross-device browser intent identity",
    "production-wide certification from repository closure",
)


def _text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


# ═════════ ١ · المخطَّطُ الذي بُني عليه الإغلاق ═════════


def test_01_the_closure_schema_head_is_unchanged() -> None:
    """٠٠٣٧ هو المخطَّطُ المُغلَقُ عليه — ولا ٠٠٣٨ في الشجرة.

    ولو أُضيف ترحيلٌ لاحقًا فليس ذلك عطبًا في نفسه؛ لكنّ الدفترَ يقول
    «٠٠٣٧» فيجب أن يُعاد النظرُ فيه صراحةً لا أن يتخلّف صامتًا.
    """
    versions = REPO / "infra" / "db" / "migrations" / "versions"
    files = sorted(p.name for p in versions.glob("*.py"))
    assert len(files) == 37, f"عددُ الترحيلات تغيّر: {len(files)}"
    assert files[-1].startswith(EXPECTED_SCHEMA_HEAD), files[-1]
    assert not [f for f in files if f.startswith("0038")], "ظهر ٠٠٣٨"
    assert EXPECTED_SCHEMA_HEAD in _text(LEDGER), "الدفترُ لا يذكر مخطَّطَه"


# ═════════ ٢ · مكوّناتُ H2 ما زالت لها فحوصُها ═════════


@pytest.mark.parametrize("component,module", sorted(COMPONENT_TESTS.items()))
def test_02_every_h2_component_still_has_its_test_module(
    component: str, module: str,
) -> None:
    """**ومكوّنٌ بلا فحصٍ ليس مُغلَقًا** — الإغلاقُ يُحرس أو يُنقَض."""
    assert (API / "tests" / module).exists(), f"{component}: {module} مفقود"


def test_03_the_browser_policy_guards_exist_and_are_wired() -> None:
    """حارسُ سياسةِ المتصفّح قائمٌ **ويبلغه مشغّل** — وإلّا فهو حبرٌ على ورق."""
    for spec in WEB_GUARDS:
        assert (WEB / "tests" / spec).exists(), f"{spec} مفقود"

    scripts = _text(WEB / "package.json")
    workflows = "".join(
        _text(p) for p in (REPO / ".github" / "workflows").glob("*.yml"))
    invoked = set(re.findall(r"npm run ([A-Za-z0-9:_-]+)", workflows))
    reachable = "".join(
        m.group(1) for name in invoked
        for m in re.finditer(rf'"{re.escape(name)}"\s*:\s*"([^"]*)"', scripts))
    for spec in WEB_GUARDS:
        assert spec in reachable, f"{spec} لا يشغّله مشغّل"


# ═════════ ٣ · التماسُ الذي لم يكن يحرسه شيء ═════════


def test_04_the_browser_horizon_stays_inside_server_retention() -> None:
    """**أخطرُ تماسٍ في H2 كلِّه** — وطرفاه مكتوبان بلغتين.

    بقاءُ الجيل في الخادم `TTL`، وأفقُ المتصفّح الآمن `REUSE_WINDOW_MS`.
    فلو قُصّر الأوّلُ يومًا لبقي المتصفّحُ يعيد مفتاحًا على صفٍّ **زال**،
    فيصير المفتاحُ القديمُ في نظر الخادم مفتاحًا جديدًا — ويقع العملُ
    مرّتين بلا أن يحمرّ شيء. فيُقرأ الثابتان معًا ويُقارَنان.
    """
    server = _text(API / "athera_api" / "services" / "idempotency.py")
    hours = re.search(r"^TTL\s*=\s*dt\.timedelta\(hours=(\d+)\)", server, re.M)
    assert hours, "لم يُقرأ `TTL` من خدمة التكرار"
    server_ms = int(hours.group(1)) * 60 * 60 * 1000

    web = _text(WEB / "src" / "lib" / "idempotency.ts")
    declared = re.search(
        r"const SERVER_RETENTION_MS\s*=\s*(\d+)\s*\*\s*60\s*\*\s*60\s*\*\s*1000", web)
    assert declared, "لم يُقرأ `SERVER_RETENTION_MS` من الوِب"
    web_declared_ms = int(declared.group(1)) * 60 * 60 * 1000

    assert web_declared_ms == server_ms, (
        f"المتصفّحُ يظنّ بقاءَ الخادم {web_declared_ms}ms وهو {server_ms}ms")

    margin = re.search(
        r"const REUSE_WINDOW_MS\s*=\s*SERVER_RETENTION_MS\s*-\s*(?:(\d+)\s*\*\s*)?"
        r"60\s*\*\s*60\s*\*\s*1000", web)
    assert margin, "أفقُ المتصفّح لا يُشتقّ من بقاءِ الخادم"
    safety_ms = int(margin.group(1) or 1) * 60 * 60 * 1000
    assert safety_ms >= 60 * 60 * 1000, "لا هامشَ أمانٍ دون بقاءِ الخادم"
    assert server_ms - safety_ms > 0, "الأفقُ الآمنُ ليس دون البقاء"


def test_05_an_expired_browser_intent_never_mints_a_replacement() -> None:
    """والأفقُ **يُغلق** ولا يدور: لا سكَّ مفتاحٍ بعد انقضائه.

    حارسٌ بنيويّ: `keyForIntent` ترفع عند التجاوز، ولا تكتب صفًّا بديلًا.
    """
    web = _text(WEB / "src" / "lib" / "idempotency.ts")
    body = web[web.index("export function keyForIntent"):]
    body = body[:body.index("\n}")]
    assert "throw new IdempotencyIntentExpired" in body, (
        "النيّةُ المنقضيةُ لا تُغلق — يُسكّ لها بديلٌ صامت")
    # **التعليقُ يذكرها لينفيها** — فتُجرَّد التعليقاتُ قبل الحكم.
    code = re.sub(r"/\*[\s\S]*?\*/", "", web)
    code = re.sub(r"//[^\n]*", "", code)
    assert "Math.random" not in code, "عشوائيّةٌ غيرُ معمّاةٍ في مولّد المفاتيح"


def test_06_the_model_boundary_still_stands_on_every_authorized_flow() -> None:
    """الستّةُ المأذونة ما زال لكلٍّ منها حدُّ المزوّد.

    ولو سقط `before_provider_call` عن أحدها لَعاد النداءُ الأعمى إلى جيلٍ
    قد أُنفق فيه — وهي الدعوى التي يقوم عليها B4 كلُّه.
    """
    flows = {
        "ai.py": "ask",
        "brain.py": "ask",
        "manuscript_drafting.py": "draft_section",
        "planning.py": "generate_opportunities",
        "profile.py": "import_document",
        "thesis.py": "build_thread",
    }
    # **ووجودُ الاسم ليس وصلَه.** `ModelBoundary(` قد تبقى مبنيّةً في
    # متغيّرٍ لا يُمرَّر — فيُطلب أن يصل المبنيُّ إلى المَعلَم نفسِه.
    for module in flows:
        src = _text(API / "athera_api" / "routers" / module)
        built = re.search(r"(\w+)\s*=\s*idempotency\.ModelBoundary\(", src)
        assert built, f"{module}: لا حدَّ للمزوّد يُبنى"
        name = built.group(1)
        assert re.search(rf"before_provider_call\s*=\s*\(?\s*{name}\b", src), (
            f"{module}: الحدُّ يُبنى ولا يُمرَّر إلى `before_provider_call`")
    # وB5 لها حدُّها في قارئها الخلفيّ.
    di = _text(API / "athera_api" / "routers" / "document_intelligence.py")
    assert re.search(r"before_provider_call\s*=\s*\(?\s*_boundary\b", di), (
        "B5: قارئُ النموذج بلا حدٍّ مُمرَّر")


def test_07_the_processing_fence_is_still_a_database_clock() -> None:
    """سياجُ B5 بساعةِ القاعدة لا بساعةِ العمليّة — والخلطُ يُبطل التحكيم."""
    import ast

    path = API / "athera_api" / "services" / "thesis" / "processing.py"
    proc = _text(path)
    fenced = ("claim_generation", "recover_generation", "advance")
    tree = ast.parse(proc)
    bodies = {n.name: (ast.get_source_segment(proc, n) or "")
              for n in ast.walk(tree)
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for fn in fenced:
        assert fn in bodies, f"`{fn}` غابت عن خطّ المعالجة"

    # **وكلُّ كتابةِ سياجٍ داخل دوالِّ الجيل بساعةِ القاعدة.**
    #
    # وساعةُ العمليّة تجعل التحكيمَ كذبًا: عاملان على آلتين بساعتَين
    # متفارقتَين يقرآن «بائت» و«حيّ» للصفّ نفسِه. أمّا المسلكُ بلا جيل
    # (`claim is None`) والمسلكُ القديمُ المشروط فخارجَ الجيل أصلًا، ولا
    # يُسيَّجان — وذاك دَينٌ مُحال إلى المرحلة ٨، لا خللٌ في الإغلاق.
    for fn in fenced:
        body = bodies[fn]
        # الإسنادُ وحدَه يُحاسَب — و`== claim.fence` شرطُ سياجٍ لا كتابة.
        assigns = re.findall(
            r"processing_state_changed_at\s*(?:=(?!=)|\"\s*:)\s*([A-Za-z_.]+\()",
            body)
        assert not any(a.startswith("_now") for a in assigns), (
            f"`{fn}` يكتب السياجَ بساعةِ العمليّة: {assigns}")
        if assigns:
            assert any(a.startswith("func.now") for a in assigns), (
                f"`{fn}` يكتب السياجَ بـ{assigns} لا بساعةِ القاعدة")

    # وحيثُ يُقارَن السياجُ يُقارَن بما كُتب، لا بساعةِ عمليّةٍ أخرى.
    assert "func.now() - STALE_AFTER" in proc, "تحكيمُ البيات ترك ساعةَ القاعدة"


# ═════════ ٤ · ما تقوله التقاريرُ والمشغّلات ═════════


def test_08_no_workflow_claims_exactly_once() -> None:
    """**ولا مشغّلَ يدّعي «مرّةً واحدةً بالضبط»** — ولا في ملخّصٍ ولا تعليق."""
    offenders: list[str] = []
    negations = ("not prove", "does not", "never", "not claimed",
                 "no ", "لا يُدَّعى", "ولا يُدَّعى")
    for wf in sorted((REPO / ".github" / "workflows").glob("*.yml")):
        lines = _text(wf).splitlines()
        for n, line in enumerate(lines, 1):
            low = line.lower()
            if "exactly-once" not in low and "exactly once" not in low:
                continue
            # **والنفيُ قد يسبق بسطر**: جملةُ «ما لا يثبته» تُلفّ على أسطر،
            # فيُقرأ ما حولها لا السطرُ وحدَه. والنفيُ مسموحٌ بل مطلوب.
            window = " ".join(lines[max(0, n - 4):n + 1]).lower()
            if any(w in window for w in negations):
                continue
            offenders.append(f"{wf.name}:{n}: {line.strip()[:70]}")
    assert offenders == [], f"ادّعاءُ exactly-once في مشغّل: {offenders}"


def test_09_the_ledger_states_every_mandatory_non_claim() -> None:
    """الدفترُ يقول ما **لا** يُدَّعى — كلَّ بندٍ بحرفه."""
    ledger = _text(LEDGER)
    missing = [c for c in MANDATORY_NON_CLAIMS if c not in ledger]
    assert missing == [], f"بنودُ نفيٍ ساقطةٌ من الدفتر: {missing}"

    # **ووجودُ البند لا يكفي**: لو قُلب `NOT CLAIMED` إلى `CLAIMED` لبقي
    # النصُّ موجودًا والدعوى مقلوبة. فيُقرأ سطرُ كلِّ بندٍ بحكمه.
    lines = ledger.splitlines()
    flipped = []
    for claim in MANDATORY_NON_CLAIMS:
        row = next(ln for ln in lines if claim in ln)
        if "NOT CLAIMED" not in row:
            flipped.append(row.strip()[:70])
    assert flipped == [], f"بندُ نفيٍ انقلب إلى دعوى: {flipped}"

    # ولا تُدَّعى «مرّةً واحدةً بالضبط» إيجابًا في الدفتر نفسِه.
    for n, row in enumerate(lines, 1):
        low = row.lower()
        if "exactly-once" not in low:
            continue
        window = " ".join(lines[max(0, n - 3):n + 1]).lower()
        # صيغُ النفي المقبولة — عربيّةً وإنجليزيّة.
        denials = ("not claimed", "لا يُدَّعى", "لا يُقال", "لا تُحوَّل",
                   "not_claimed", "أضعف")
        assert any(d in window for d in denials), (
            f"دعوى exactly-once في الدفتر، السطر {n}: {row.strip()[:70]}")


def test_10_the_canonical_status_is_closed_and_hands_off_to_stage_eight() -> None:
    """الحالُ الراهنةُ مُغلَق، والتسليمُ إلى المرحلة ٨ لا إلى ما بعدها."""
    ledger = _text(LEDGER)
    assert "مُغلَق" in ledger, "الدفترُ لا يعلن الإغلاق"
    assert "78288d53b52e92f0df20e5d0cb49851333e6b67f" in ledger, \
        "الدفترُ بلا جيلٍ مُغلِق"
    assert re.search(r"المرحلة\s*٨", ledger), "لا تسليمَ إلى المرحلة ٨"
    for later in ("المرحلة ٩", "Stage #9", "Stage 9"):
        assert later not in ledger, f"تسليمٌ إلى ما بعد الثامنة: {later}"


def test_11_no_canonical_doc_still_calls_h2_open() -> None:
    """**ولا وثيقةٌ مرجعيّةٌ تناقض الدفتر.**

    والتاريخُ يبقى تاريخًا: ما يوصَف بأنّه حالُ طورٍ مضى مسموح. الممنوعُ
    جملةُ حالٍ **راهنةٍ** تقول إنّ H2 مفتوح أو أنّ تبنّي المتصفّح لم يقع.
    """
    canonical = [
        DOCS / "RC-T1-H2-mutation-idempotency.md",
        DOCS / "RC-T1-H2-B5-thesis-processing-recovery.md",
        DOCS / "RC-T1-H2-Web-idempotency-adoption.md",
        DOCS / "RC-T1-H1-commit-before-response.md",
        DOCS / "RC-T1-H3-ai-long-transactions.md",
        LEDGER,
        REPO / "docs" / "architecture" / "transactions.md",
    ]
    # **ولا مطابقةَ حرفيّةً بعددِ مسافات** — تلك تفوت السطرَ نفسَه بمحاذاةٍ
    # أخرى، وقد فاتته فعلًا في أوّل صياغةٍ لهذا الحارس.
    forbidden = (
        r"RC-T1-H2 globally\s*:\s*NOT CLOSED",
        r"Web Idempotency-Key adoption\s*:\s*OPEN",
        r"Idempotency-Key في الواجهة\s*:\s*OPEN",
        r"Ambiguous delivery — مساراتُ الانتظار الخارجيّ\s*:\s*OPEN",
        r"Ambiguous delivery — external-wait routes\s*:\s*OPEN",
        r"\*\*مفتوح\*\* — لم يُبدَأ",
    )
    offenders = [f"{p.name}: {m.group(0)[:50]}" for p in canonical
                 for pattern in forbidden
                 if (m := re.search(pattern, _text(p)))]

    # وسطرُ الحالِ الإجماليِّ يُقرأ بقيمته لا بغيابِ كلمة.
    for p in canonical:
        for value in re.findall(r"RC-T1-H2 (?:إجمالًا|globally)\s*:\s*(\S+)",
                                _text(p)):
            assert value.startswith("CLOSED"), f"{p.name}: الحالُ «{value}»"
    assert offenders == [], f"دعوى حالٍ راهنةٍ تناقض الإغلاق: {offenders}"


def test_12_no_database_transaction_spans_an_external_wait() -> None:
    """حدُّ H3 باقٍ نظيفًا — وهو شرطُ إغلاقِ H2 لا جارُه.

    **ولمَ هو شرط.** أجيالُ التكرار تُودَع وتُقرأ في معاملات؛ فلو أمسك
    مسارٌ معاملةً عبر نداءِ نموذجٍ أو تخزين، لَاحتجز اتصالًا طوالَ زمنٍ
    خارجيٍّ غيرِ محدود — وتحت الضغط تنفد البِركة، فيصير الغموضُ الذي بُني
    H2 لعلاجه هو الحالَ الغالبة. فالحدّان يقفان معًا أو يسقطان معًا.

    والمقياسُ ماسحُ الاستيراد لا `grep`: يحلّ كلَّ حافةٍ إلى هدفٍ مؤهَّل.
    """
    from tests.external_wait_audit import audit
    from tests.session_lifecycle_audit import audit as session_audit

    external = audit().offenders()
    assert external == [], (
        "مسارٌ يمسك معاملةً عبر انتظارٍ خارجيّ: "
        + ", ".join(f"{o.file}:{o.line}" for o in external))

    leaks = session_audit()
    assert leaks == [], f"جلسةٌ تُستعمل خارج نطاقها: {leaks}"
