import { expect, test, type ConsoleMessage, type Page, type Request } from "@playwright/test";

import { signIn } from "./journey";

/**
 * قبولُ الموجة 1.1 على الإنتاج | Wave 1.1 production acceptance.
 *
 * ## أربعةُ أخطاءِ حزمةٍ سبقت هذه الصياغة — ولا يُعاد أيٌّ منها
 *
 * **١ — خطوةٌ أُعلنت ناجحة لأنّ الزرّ ضُغط.** أثبتت القاعدةُ أنّ
 * `process-file` لم يقع أصلًا، والحزمةُ مضت. فصار الطلبُ يُرصد ويُعدّ
 * وتُقرأ حالُه، وغيرُ المتوقَّع يسقط فورًا.
 *
 * **٢ — انتظارٌ طويل بعد فشلٍ صامت.** خمسُ دقائق تنتظر بطاقةً بعد طلبٍ لم
 * يقع، فيظهر العطبُ في موضعٍ بريء. فصار كلُّ انقسامٍ يُحسم فورًا ويُطبع.
 *
 * **٣ — `page.reload()` داخل حلقة الاكتشاف.** والشاشةُ تحمّل قائمتها بـ
 * `useDeferredLoad`: إعادةُ تحميلٍ متكرّرة تهدم الصفحة قبل أن يستقرّ
 * الطلبُ المؤجَّل وتصييرُه، فيُقاس غيابٌ صنعه القياسُ نفسه. **فتنقّلٌ واحد
 * ثمّ انتظار**، في الاكتشاف وبعد التغيير سواء: `openThesisCentre` تنقّلٌ
 * كامل إلى مستندٍ جديد، وهو وحده ما يفصل الحفظَ عن تفاؤل الواجهة.
 *
 * **٤ — انتظارُ عدّادٍ بدل انتظار الحدث.** كان تبديلُ العرض ينام ألفَين
 * ونصفًا؛ فمرّةً كفى ومرّةً لم يكفِ، وسقطت «ز» على بطاقةٍ في الطريق.
 * فصار يُنتظر **ردُّ العرض المقصود بمعامله** `view=`، ولا يُقبل ردٌّ بائت.
 *
 * ## حدودٌ لا تُتجاوز
 *
 * لا رفعَ ملفّ، ولا نداءَ `process-file`، ولا حذفَ فيزيائيّ. ولا يُلمس إلّا
 * ما يحمل `PUBRIVA-W11-ACCEPT`. ولا يُطبع اعتمادٌ ولا رمزٌ ولا ترويسةٌ ولا
 * عناوينُ رسائلَ أخرى ولا محتوى مستند.
 */

const EMAIL = process.env.PUBRIVA_ACCEPT_EMAIL;
const PASSWORD = process.env.PUBRIVA_ACCEPT_PASSWORD;

/** البادئةُ الحارسة — **لا يُلمس ما لا يبدأ بها**. */
const MARKER = "PUBRIVA-W11-ACCEPT";

/**
 * الهدفُ التشخيصيّ — **معرّفٌ جاء من ردّ 202 حقيقي**، ويشير إلى الأثر
 * التركيبيّ وحده. وذكرُه هنا ليس إذنًا بلمس غيره.
 */
const THESIS_ID = "a07369e3-a0d6-4d00-a484-c16d59e9e128";
const EXPECTED_FILE = "PUBRIVA-W11-ACCEPT-1788779150628.txt";
const EXPECTED_FILE_ID = "543d03ec-d57d-40a3-ad26-3306b7844448";
/** ملفٌّ يتيم من تشغيلةٍ سابقة — يُنظَّف بعد اخضرار دورة الحياة وحده. */
const ORPHAN_FILE = "PUBRIVA-W11-ACCEPT-1788779531506.txt";

const LIST_PATH = "/api/v1/theses";

test.describe.configure({ mode: "serial", timeout: 12 * 60_000 });

// **ولا مسجّلَ يعمل**: الأثرُ والفيديو واللقطة تحمل DOM صفحةٍ فيها حقولُ
// اعتماد. ويُمحى ما بقي في خطوة `always()` قبل أيّ رفع — حزامان لا واحد.
test.use({ trace: "off", video: "off", screenshot: "off" });

test.beforeAll(() => {
  if (!EMAIL || !PASSWORD) {
    throw new Error(
      "PUBRIVA_ACCEPT_EMAIL / PUBRIVA_ACCEPT_PASSWORD are not set. Production "
      + "acceptance fails closed: it never reports green without having run.");
  }
});

// ═════════ الرصد ═════════

interface Watch {
  /** كلُّ نداءٍ مسارُه يحوي `/api/v1/theses` — **احتواءً لا مطابقةً هشّة**. */
  thesisCalls: { method: string; path: string; status: number }[];
  serverErrors: string[];
  consoleErrors: string[];
  pageErrors: string[];
  requestFailures: string[];
  /** `view:status` لكلّ ردّ قائمة، **بترتيب الوصول**. */
  listViews: string[];
  apiOrigin: string | null;
}

function watch(page: Page): Watch {
  const w: Watch = {
    thesisCalls: [], serverErrors: [], consoleErrors: [],
    pageErrors: [], requestFailures: [], listViews: [], apiOrigin: null,
  };
  page.on("response", (r) => {
    const url = new URL(r.url());
    if (!url.pathname.startsWith("/api/v1")) return;
    w.apiOrigin ??= url.origin;
    if (url.pathname.includes("/api/v1/theses")) {
      w.thesisCalls.push({
        method: r.request().method(), path: url.pathname, status: r.status(),
      });
      // **ترتيبُ ردود القائمة وعروضُها** — به وحده يُفصل عطبُ الحزمة عن
      // عطب المنتج: إن استقرّ `view=all` بعد اختيار «المؤرشفة»، فالردُّ
      // البائت كتب فوق الجديد، وذلك عطبٌ في الشاشة لا في القياس.
      if (url.pathname === LIST_PATH && r.request().method() === "GET") {
        w.listViews.push(`${url.searchParams.get("view") ?? "all"}:${r.status()}`);
      }
    }
    if (r.status() >= 500) {
      w.serverErrors.push(`${r.request().method()} ${url.pathname} -> ${r.status()}`);
    }
  });
  page.on("console", (m: ConsoleMessage) => {
    if (m.type() === "error") w.consoleErrors.push(m.text().slice(0, 200));
  });
  page.on("pageerror", (e) => w.pageErrors.push(String(e).slice(0, 200)));
  page.on("requestfailed", (r: Request) => {
    const url = new URL(r.url());
    if (url.pathname.startsWith("/api/v1")) {
      w.requestFailures.push(`${r.method()} ${url.pathname} :: ${r.failure()?.errorText}`);
    }
  });
  return w;
}

/** **يُطبع في حينه** — لا يُجمَع لتقريرٍ قد لا يُبلَغ. */
function shout(stage: string, facts: Record<string, unknown>): void {
  console.log(`\n── ACCEPTANCE · ${stage} ──`);
  for (const [k, v] of Object.entries(facts)) console.log(`   ${k}: ${v}`);
  console.log("─────────────────────────────\n");
}

function noise(w: Watch): Record<string, unknown> {
  return {
    consoleErrors: w.consoleErrors.slice(-3).join(" | ") || "none",
    pageErrors: w.pageErrors.slice(-3).join(" | ") || "none",
    requestFailed: w.requestFailures.slice(-3).join(" | ") || "none",
  };
}

const evidence: Record<string, string> = {};

/** الراصدُ الحيّ — ليقرأه التشخيصُ عند السقوط. */
let w0: Watch | null = null;

function targetCard(page: Page) {
  return page.locator(`article.card[data-testid="thesis-card-${THESIS_ID}"]`);
}

/**
 * حضورُ البطاقة — **بانتظارٍ يعيد المحاولة، لا بعدٍّ لحظيّ**.
 *
 * و`count()` لا يعيد المحاولة: يُقرأ في اللحظة ويُجاب. وقد استقرّ ردُّ
 * القائمة ولمّا يُصيَّر بعد، فيُقرأ صفرٌ ويُبنى عليه فرعٌ كامل. وأخطرُ ما
 * فيه في «ي»: صفرٌ كاذب يتخطّى الأرشفة ثمّ يجد القائمةَ خاليةً فيُعلن
 * النجاح — **خضرةٌ على عملٍ لم يقع**. فيُنتظر الظهور، ويُسمّى الغيابُ
 * غيابًا بعد انقضاء المهلة وحدها.
 */
function cardPresent(page: Page, timeout = 15_000): Promise<boolean> {
  return targetCard(page).first()
    .waitFor({ state: "visible", timeout })
    .then(() => true, () => false);
}

/**
 * **لا يُلمس صفٌّ حتى يُثبت أنّه الأثرُ التركيبيّ.**
 *
 * والهويّةُ ثلاثةُ شروط: المعرّفُ في `data-testid` — وهو معرّفُ ردّ 202
 * بعينه — والبادئةُ الحارسة واسمُ الملفّ في نصّ البطاقة.
 *
 * و`withFileId` يُطفأ في خطوة التسوية وحدها: `source_file_id` لا يُعرف قبل
 * أن تقرأ «ب» ردَّ القائمة، والاشتراطُ عليه هناك يشترط على معلومةٍ لم
 * تُقرأ بعد — لا يزيد أمانًا ويسقط دائمًا. والشروطُ الثلاثةُ الباقية
 * تكفي: معرّفٌ كامل، وبادئةٌ حارسة، واسمُ ملفٍّ مطابق.
 */
async function assertOwnership(page: Page, stage: string, withFileId = true) {
  const card = targetCard(page).first();
  try {
    await expect(card).toBeVisible({ timeout: 30_000 });
  } catch {
    // **يُحسم الانقسام هنا** — لا في قراءةِ أثرٍ بعد انتهاء التشغيلة.
    shout(`${stage}/not-on-screen`, {
      "#thesis-view value": await page.locator("#thesis-view").inputValue(),
      "cards rendered": await page.locator("article.card").count(),
      "list responses (view:status, in order)": w0?.listViews.join(" → ") || "none",
      VERDICT: "if a view=all response settled last, a stale response overwrote the view",
    });
    throw new Error(`${stage}: the target card is not on screen`);
  }
  const text = await card.innerText();
  const ok = text.includes(MARKER) && text.includes(EXPECTED_FILE)
    && (!withFileId || evidence.targetFileId === EXPECTED_FILE_ID);
  if (!ok) {
    shout(`${stage}/ownership`, {
      "REFUSING TO MUTATE": "identity could not be proven",
      expectedFile: EXPECTED_FILE,
      sourceFileIdSeen: evidence.targetFileId || "(none)",
    });
    throw new Error(`${stage}: refusing to mutate — ownership not proven`);
  }
}

async function openThesisCentre(page: Page, locale = "ar") {
  const settled = listResponseFor(page, "all");
  await page.goto(`/${locale}/theses`);
  await expect(page.locator("#thesis-view")).toBeVisible({ timeout: 60_000 });
  // **تُترك الشاشةُ ساكنة**: ظهورُ عنصر الاختيار يسبق استقرارَ التحميل
  // المؤجَّل، وتبديلُ العرض وطلبٌ في الطريق يفتح سباقًا لا يخصّ ما نقيس.
  await settled;
}

/**
 * ينتظر **ردَّ العرض المقصود بعينه**، لا أيَّ ردِّ قائمة.
 *
 * والشاشةُ تُرسل `view=archived` وتُسقط المعامل حين «الكلّ» — ففي المعامل
 * تمييزٌ قاطع. وانتظارُ «أيّ ردّ» كان يستقرّ على ردٍّ بائتٍ للعرض السابق
 * ويمضي والعرضُ المطلوب في الطريق.
 */
function listResponseFor(page: Page, view: string) {
  return page.waitForResponse((r) => {
    const u = new URL(r.url());
    return u.pathname === LIST_PATH && r.request().method() === "GET"
           && (u.searchParams.get("view") ?? "all") === view;
  }, { timeout: 60_000 }).catch(() => null);
}

/**
 * تبديلُ العرض — **وينتظر ردَّ ذلك العرض، لا عدّادًا**.
 *
 * وكان ينام ألفَين ونصفًا ثمّ يمضي. والقاعدةُ في مومباي والخادمُ في
 * سنغافورة، فالردُّ قد يتأخّر عن أيّ رقمٍ يُكتب بيد. والنومُ الثابت يخدع
 * مرّتين: يُبطئ حين يكفي أقلُّ منه، ويكذب حين يلزم أكثر. فيُنتظر الحدث.
 */
async function chooseView(page: Page, value: string) {
  const settled = listResponseFor(page, value);
  await page.locator("#thesis-view").selectOption(value);
  await settled;
}

// ═════════ الرحلة ═════════

test("Wave 1.1 thesis lifecycle on production", async ({ page }) => {
  const w = watch(page);
  w0 = w;

  // ── أ — الدخول من الشاشة ──
  await test.step("A · sign in through the real UI", async () => {
    await page.goto("/ar/login");
    await signIn(page, EMAIL!, PASSWORD!);
    evidence.auth = "signed in via the login form";
  });

  // ── أ٢ — التسوية: تبدأ الرحلةُ من حالٍ معلومة ──
  //
  // **التشغيلةُ السابقة أرشفت ثمّ انقطعت قبل الاسترجاع**، فالأثرُ التركيبيّ
  // مؤرشَفٌ الآن، و«ي» تتركه مؤرشَفًا في كلّ مرّة عمدًا. ولو مضت «ب» على
  // ذلك لغاب الهدفُ عن القائمة الحيّة فأعلنت **عطبَ إدراجٍ في الخادم** —
  // تهمةً لبريء، وهي بعينها الغلطةُ الثانية في الترويسة: عطبٌ يظهر في
  // موضعٍ لا يخصّه. فتُسوّى الحالُ أوّلًا، ويُقال في التقرير إنّها سُوّيت.
  //
  // وهذه الخطوةُ **لا تُثبت شيئًا** من عقد الموجة 1.1؛ الإثباتُ في «هـ»
  // و«ز» بعدها. وهي لا تلمس إلّا ما تثبت هويّتُه.
  await test.step("A2 · normalize: begin from a known active state", async () => {
    await openThesisCentre(page);
    if (await cardPresent(page)) {
      evidence.startState = "already active — nothing to normalize";
      shout("A2/normalize", { "starting state": "active", restored: false });
      return;
    }

    await chooseView(page, "archived");
    if (!(await cardPresent(page))) {
      // لا يُفتعل شيء: «ب» تملك التشخيصَ الكامل وتُسمّي الانقسام.
      evidence.startState = "in neither view — B will diagnose";
      shout("A2/normalize", { "starting state": "absent from active and archived",
                              restored: false, note: "left to B to diagnose" });
      return;
    }

    await assertOwnership(page, "A2", false);
    const waiting = page.waitForResponse(
      (r) => r.url().includes(`/theses/${THESIS_ID}/restore`)
             && r.request().method() === "POST", { timeout: 60_000 });
    await targetCard(page).first().getByTestId("card-restore").click();
    const response = await waiting;
    if (response.status() !== 200) shout("A2/normalize", { status: response.status(), ...noise(w) });
    expect(response.status(), "could not restore the synthetic thesis to a known start state")
      .toBe(200);
    evidence.startState = "was left archived by an earlier interrupted run — restored to active";
    shout("A2/normalize", { "starting state": "archived", restored: true, status: 200 });
  });

  // ── ب — الانقسامُ الحاسم: هل خرج طلبُ القائمة، وماذا حمل؟ ──
  //
  // **تنقّلٌ واحد بلا إعادةِ تحميل.** الشاشةُ تحمّل قائمتها بطلبٍ مؤجَّل،
  // وإعادةُ التحميل المتكرّرة تهدمها قبل أن يستقرّ — فيُقاس غيابٌ مصنوع.
  await test.step("B · did the list request go out, and what did it carry?", async () => {
    const listing = page.waitForResponse(
      (r) => new URL(r.url()).pathname === LIST_PATH && r.request().method() === "GET",
      { timeout: 30_000 }).catch(() => null);

    await page.goto("/ar/theses");
    const response = await listing;

    // ── لا طلب ──
    if (!response) {
      shout("B/list", {
        "LIST REQUEST": "NOT EMITTED",
        "URL PATH": LIST_PATH,
        "thesis-scoped calls seen": w.thesisCalls.map((c) => `${c.method} ${c.path}:${c.status}`)
          .join(" | ") || "none",
        ...noise(w),
        VERDICT: "FRONTEND LOADING / HYDRATION DEFECT",
      });
      evidence.listRequest = "NOT EMITTED";
      throw new Error("LIST REQUEST = NOT EMITTED — no GET /api/v1/theses within 30s");
    }

    const status = response.status();
    evidence.listRequest = "emitted";
    evidence.listPath = LIST_PATH;
    evidence.listStatus = String(status);

    // ── طلبٌ خرج وردَّ بغير 2xx ──
    if (status < 200 || status >= 300) {
      let safeCode = "unknown";
      try {
        const body = await response.json();
        safeCode = String((body as { error?: { code?: string } }).error?.code ?? "unknown");
      } catch { /* جسمٌ غيرُ JSON — لا يُطبع */ }
      shout("B/list", {
        "LIST REQUEST": "emitted", "URL PATH": LIST_PATH, "STATUS": status,
        "SAFE ERROR CODE": safeCode, ...noise(w),
        VERDICT: "LIST REQUEST FAILED",
      });
      evidence.safeErrorCode = safeCode;
      throw new Error(`list request answered ${status} (${safeCode})`);
    }

    // ── 200: يُقرأ في الذاكرة، ولا يُفرَغ في السجلّ ──
    const rows = (await response.json()) as Array<Record<string, unknown>>;
    const target = rows.find((r) => String(r.id) === THESIS_ID);
    evidence.rowCount = String(rows.length);
    evidence.containsTarget = String(Boolean(target));

    const facts: Record<string, unknown> = {
      "LIST REQUEST": "emitted", "URL PATH": LIST_PATH, "STATUS": status,
      "SAFE ERROR CODE": "n/a",
      "ROW COUNT": rows.length,
      "CONTAINS TARGET THESIS ID": Boolean(target),
    };
    if (target) {
      // **الصفُّ الهدف وحده** — ولا سطرَ عن غيره.
      evidence.targetFileId = String(target.source_file_id ?? "");
      evidence.targetFilename = String(target.source_filename ?? "");
      evidence.targetState = String(target.processing_state ?? "");
      evidence.targetArchivedAt = target.archived_at ? "set" : "null";
      facts["TARGET id"] = target.id;
      facts["TARGET source_file_id matches"] = evidence.targetFileId === EXPECTED_FILE_ID;
      facts["TARGET source_filename matches"] = evidence.targetFilename === EXPECTED_FILE;
      facts["TARGET processing_state"] = evidence.targetState;
      facts["TARGET archived_at"] = evidence.targetArchivedAt;
    }
    shout("B/list", facts);

    // ── 200 والهدفُ غائب: العطبُ في الخادم لا في الشاشة ──
    if (!target) {
      shout("B/verdict", {
        VERDICT: "BACKEND LISTING / AUTHORIZATION DEFECT",
        why: "step A2 left this thesis active for this same tenant, yet the list "
             + "response does not contain it",
        "A2 said": evidence.startState ?? "(A2 did not run)",
        rowCount: rows.length,
      });
      throw new Error("BACKEND LISTING / AUTHORIZATION DEFECT — target absent from a 200 list");
    }
  });

  // ── ج — الصفُّ في الردّ: فهل يُصيَّر؟ ──
  await test.step("C · the API returned it — does the DOM render it?", async () => {
    const rendered = await targetCard(page).first()
      .waitFor({ state: "visible", timeout: 15_000 })
      .then(() => true, () => false);

    if (!rendered) {
      shout("C/render", {
        "API CONTAINS TARGET": "YES",
        "DOM CONTAINS TARGET": "NO",
        "TARGET processing_state": evidence.targetState,
        totalCards: await page.locator("article.card").count(),
        activeView: await page.locator("#thesis-view").inputValue().catch(() => "n/a"),
        errorsOnPage: await page.locator(".error").count(),
        ...noise(w),
        VERDICT: "FRONTEND RENDER / STATE DEFECT",
      });
      throw new Error("FRONTEND RENDER / STATE DEFECT — in the API response, absent from the DOM");
    }
    evidence.targetCard = "rendered in the active list, matched by data-testid";
    shout("C/render", { "API CONTAINS TARGET": "YES", "DOM CONTAINS TARGET": "YES",
                        "TARGET processing_state": evidence.targetState });
  });

  // ── د — معاينةُ الإزالة من ردٍّ حقيقي ──
  await test.step("D · removal preview comes from the real response", async () => {
    await assertOwnership(page, "D");
    const card = targetCard(page).first();
    await card.getByTestId("card-menu").click();
    const waiting = page.waitForResponse(
      (r) => r.url().includes(`/theses/${THESIS_ID}/removal-preview`)
             && r.request().method() === "GET", { timeout: 60_000 });
    await card.getByTestId("menu-archive").click();
    const response = await waiting;
    if (response.status() !== 200) {
      shout("D/preview", { status: response.status(), ...noise(w) });
    }
    expect(response.status()).toBe(200);
    const body = await response.json();
    evidence.removalPreview = `200 · needs_acknowledgement=${body.needs_acknowledgement}`;
    evidence.needsAcknowledgement = String(body.needs_acknowledgement);
    const deps = (body.dependencies ?? [])
      .filter((d: { count: number }) => d.count > 0)
      .map((d: { key: string; count: number; blocking: boolean }) =>
        `${d.key}=${d.count}${d.blocking ? "(ack)" : ""}`);
    evidence.dependencies = deps.length ? deps.join(" ") : "none";
    shout("D/preview", { status: 200, needsAcknowledgement: evidence.needsAcknowledgement,
                         dependencies: evidence.dependencies });
    await expect(card.getByTestId("removal-preview")).toBeVisible({ timeout: 30_000 });
    await expect(card.getByTestId("removal-preview"))
      .toContainText(String(body.explanation).slice(0, 40));
  });

  // ── هـ — الأرشفة، وإعادةُ تحميلٍ تُثبت الحفظ ──
  await test.step("E · archive, proven persistent across a reload", async () => {
    const card = targetCard(page).first();
    const confirm = card.getByTestId("archive-confirm");
    await expect(confirm).toHaveText(
      evidence.needsAcknowledgement === "true" ? "أقرّ وأخفِ السجلّ" : "أخفِ السجلّ");

    const posted: string[] = [];
    const onRequest = (r: Request) => {
      const path = new URL(r.url()).pathname;
      if (r.method() === "POST" && /\/theses\/[^/]+\/(archive|restore)$/.test(path)) {
        posted.push(path);
      }
    };
    page.on("request", onRequest);

    const waiting = page.waitForResponse(
      (r) => r.url().includes(`/theses/${THESIS_ID}/archive`)
             && r.request().method() === "POST", { timeout: 60_000 });
    await confirm.click();
    const response = await waiting;
    await page.waitForTimeout(2500);
    page.off("request", onRequest);

    if (response.status() !== 200) shout("E/archive", { status: response.status(), ...noise(w) });
    expect(response.status()).toBe(200);
    expect((await response.json()).rows_deleted, "archive deleted rows").toBe(0);
    // **ضغطةٌ واحدة، طلبٌ واحد.**
    expect(posted.length, `one click emitted ${posted.length} lifecycle POSTs`).toBe(1);
    evidence.archive = "200 · rows_deleted=0";
    evidence.doubleSubmit = "one click -> exactly one lifecycle POST";
    shout("E/archive", { status: 200, lifecyclePosts: posted.length });

    await expect(targetCard(page)).toHaveCount(0, { timeout: 30_000 });
    // **هنا يُقصد التنقّلُ من جديد** — يفصل الحفظَ عن تفاؤل الواجهة:
    // مستندٌ جديد، وحالةٌ صفرية، وقائمةٌ تُقرأ من الخادم لا من الذاكرة.
    // وتنقّلٌ واحد لا تنقّلان: `reload()` ثمّ `goto()` يترك طلبَ الأولى
    // في الطريق، فيستقرّ انتظارُنا عليه ونمضي والثانيةُ لم تصل بعد.
    await openThesisCentre(page);
    await expect(targetCard(page), "still active after reload").toHaveCount(0, { timeout: 30_000 });
    await chooseView(page, "archived");
    await expect(targetCard(page).first(), "not in the Archived view after reload")
      .toBeVisible({ timeout: 30_000 });
    evidence.reloadAfterArchive = "absent from active, present in Archived, after a reload";
  });

  // ── و — الملفُّ لم يُمسّ ──
  await test.step("F · the linked library file survives archiving", async () => {
    await page.goto("/ar/library");
    await expect(page.locator("article.card").filter({ hasText: EXPECTED_FILE }).first(),
                 "the linked file disappeared after archiving")
      .toBeVisible({ timeout: 60_000 });
    evidence.linkedFilePreserved = `${EXPECTED_FILE} still in My Library`;
  });

  // ── ز — الاسترجاع ──
  await test.step("G · restore, proven persistent across a reload", async () => {
    await openThesisCentre(page);
    await chooseView(page, "archived");
    await assertOwnership(page, "G");
    const waiting = page.waitForResponse(
      (r) => r.url().includes(`/theses/${THESIS_ID}/restore`)
             && r.request().method() === "POST", { timeout: 60_000 });
    await targetCard(page).first().getByTestId("card-restore").click();
    const response = await waiting;
    if (response.status() !== 200) shout("G/restore", { status: response.status(), ...noise(w) });
    expect(response.status()).toBe(200);
    evidence.restore = "200";
    shout("G/restore", { status: 200 });

    await openThesisCentre(page);
    await expect(targetCard(page).first(), "not back in the active list")
      .toBeVisible({ timeout: 30_000 });
    await chooseView(page, "archived");
    await expect(targetCard(page), "still in Archived after restore")
      .toHaveCount(0, { timeout: 30_000 });
    evidence.reloadAfterRestore = "present in active, absent from Archived, after a reload";
  });

  // ── ح — الإنجليزية: قراءةٌ فقط ──
  await test.step("H · English surface reads correctly, read-only", async () => {
    await openThesisCentre(page, "en");
    const options = (await page.locator("#thesis-view option").allTextContents()).join(" ");
    expect(options, "the Archived view is missing in English").toContain("Archived");
    await expect(targetCard(page).first(), "the thesis is not visible in English")
      .toBeVisible({ timeout: 30_000 });
    const body = (await page.locator("body").innerText()).trim();
    const rawKeys = body.match(/\btheses\.[a-zA-Z]+/g) ?? [];
    if (rawKeys.length) shout("H/english", { untranslatedKeys: rawKeys.join(", ") });
    expect(rawKeys, "untranslated message keys rendered").toEqual([]);
    evidence.arabic = "full mutation journey performed in Arabic";
    evidence.english = "Active/Archived terminology present, no untranslated keys";
  });

  // ── ط — لا نقطةَ حذف، ولا تُجرَّب ──
  await test.step("I · the live OpenAPI has no thesis DELETE route", async () => {
    expect(w.apiOrigin, "no API origin observed").toBeTruthy();
    const spec = await page.request.get(`${w.apiOrigin}/openapi.json`);
    expect(spec.status()).toBe(200);
    const paths = (await spec.json()).paths as Record<string, Record<string, unknown>>;
    for (const route of [
      "/api/v1/theses/{thesis_id}/removal-preview",
      "/api/v1/theses/{thesis_id}/archive",
      "/api/v1/theses/{thesis_id}/restore",
    ]) {
      expect(Object.keys(paths), `missing ${route}`).toContain(route);
    }
    const byId = paths["/api/v1/theses/{thesis_id}"] ?? {};
    expect(Object.keys(byId).map((m) => m.toLowerCase()),
           "a DELETE verb exists on the thesis resource").not.toContain("delete");
    evidence.deleteRoute = "absent from the live OpenAPI (never requested)";
  });

  // ── ي — الحالُ النهائية: مؤرشَفة ──
  await test.step("J · leave the synthetic thesis archived", async () => {
    await openThesisCentre(page);
    if (await cardPresent(page)) {
      await assertOwnership(page, "J");
      const card = targetCard(page).first();
      await card.getByTestId("card-menu").click();
      await card.getByTestId("menu-archive").click();
      await expect(card.getByTestId("removal-preview")).toBeVisible({ timeout: 60_000 });
      const waiting = page.waitForResponse(
        (r) => r.url().includes(`/theses/${THESIS_ID}/archive`)
               && r.request().method() === "POST", { timeout: 60_000 });
      await card.getByTestId("archive-confirm").click();
      expect((await waiting).status()).toBe(200);
    }
    await openThesisCentre(page);
    await expect(targetCard(page)).toHaveCount(0, { timeout: 30_000 });
    // **والغيابُ وحده لا يُثبت الأرشفة**: بطاقةٌ تغيب لأنّ القائمة لم
    // تُصيَّر تغيب أيضًا. فيُطلب حضورٌ في «المؤرشفة» — إثباتٌ موجب.
    await chooseView(page, "archived");
    expect(await cardPresent(page), "not in the Archived view at the end of the journey")
      .toBe(true);
    evidence.finalThesisState = "archived — absent from active, present in Archived";
  });

  // ── ك — اليتيم: بعد اخضرار دورة الحياة وحده، وبشروطه ──
  await test.step("K · soft-trash the orphan file, only if provably safe", async () => {
    await page.goto("/ar/library");
    const orphan = page.locator("article.card").filter({ hasText: ORPHAN_FILE }).first();
    // انتظارٌ يعيد المحاولة: عدٌّ لحظيّ على مكتبةٍ لم تُصيَّر يقول «غير
    // موجود» عن ملفٍّ موجود، فيُترك اليتيمُ ويُقال إنّه لم يوجد.
    const orphanHere = await orphan.waitFor({ state: "visible", timeout: 20_000 })
      .then(() => true, () => false);
    if (!orphanHere) {
      evidence.orphanCleanup = `${ORPHAN_FILE} not found — nothing done`;
      return;
    }
    const text = await orphan.innerText();
    if (!text.includes(ORPHAN_FILE) || !text.includes(MARKER) || ORPHAN_FILE === EXPECTED_FILE) {
      evidence.orphanCleanup = "identity could not be proven — left untouched";
      return;
    }
    const trash = orphan.getByRole("button", { name: /حذف الملف/ });
    if (await trash.count() === 0) {
      evidence.orphanCleanup = "no ordinary soft-Trash control offered — left untouched";
      return;
    }
    await trash.click();
    // ارتباطٌ ببحثٍ يعني «اتركه»: التنظيفُ لا يقتحم شيئًا.
    const force = page.getByRole("button", { name: /احذف على أي حال/ });
    if (await force.count() > 0) {
      const cancel = page.getByRole("button", { name: /لا تحذف/ });
      if (await cancel.count() > 0) await cancel.click();
      evidence.orphanCleanup = "orphan is linked to projects — refused to force; left untouched";
      return;
    }
    await page.waitForTimeout(3000);
    await page.reload();
    const still = await page.locator("article.card").filter({ hasText: ORPHAN_FILE }).count();
    evidence.orphanCleanup = still === 0
      ? `${ORPHAN_FILE} moved to the product's soft Trash (recoverable)`
      : `${ORPHAN_FILE} still listed — left as is`;
  });

  if (w.serverErrors.length) shout("final/5xx", { serverErrors: w.serverErrors.join(" | ") });
  expect(w.serverErrors, "unexpected 5xx during the journey").toEqual([]);
  evidence.unexpected5xx = "none";

  console.log("── Wave 1.1 production acceptance ──");
  for (const [k, v] of Object.entries(evidence)) console.log(`  ${k}: ${v}`);
});
