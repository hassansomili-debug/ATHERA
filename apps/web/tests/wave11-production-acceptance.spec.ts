import { expect, test, type ConsoleMessage, type Page, type Request } from "@playwright/test";

import { signIn } from "./journey";

/**
 * قبولُ الموجة 1.1 على الإنتاج | Wave 1.1 production acceptance.
 *
 * **العطبُ الذي أسقط الصياغة السابقة: خطوةٌ أُعلنت ناجحة لأنّ الزرّ ضُغط.**
 *
 * كانت ترفع مستندًا وتضغط «معالجة المستند» وتمضي. وأثبتت قاعدةُ الإنتاج
 * لاحقًا أنّ شيئًا لم يقع: صفُّ الملفّ موجود، ولا صفَّ رسالة، ولا تشغيلةَ
 * استخراج، ولا مقاطع، ولا مرشّحات، ولا حدثَ تدقيقٍ إلّا `file.uploaded`.
 * أي أنّ `POST /theses/process-file/{id}` **لم يقع أصلًا** — والحزمةُ
 * أعلنت الخطوة خضراء. وذاك أسوأ من فحصٍ يسقط: فحصٌ يكذب.
 *
 * فالقاعدةُ هنا: **لا خطوةَ تُعلن نجاحًا إلّا بردٍّ حقيقي**. الطلبُ يُرصد
 * قبل الضغط، ويُعدّ، وتُقرأ حالُه — و**غيرُ 202 يسقط فورًا** ولا يُنتظر
 * بعده شيء. الانتظارُ الطويل بعد طلبٍ فاشل هو ما أخفى العطب أوّلَ مرّة.
 *
 * ## حدودٌ لا تُتجاوز
 *
 * **لا يُلمس إلّا ما يحمل `PUBRIVA-W11-ACCEPT`.** ولا يُرفع ملفٌّ جديد:
 * التشغيلتان السابقتان خلّفتا ملفَّين، فيُعاد استعمال أحدهما ويُنظَّف
 * الآخر. ولا حذفَ فيزيائيّ في أيّ موضع. ولا يُطبع اعتمادٌ ولا رمزٌ ولا
 * ترويسةٌ ولا رابطٌ موقَّع ولا محتوى مستند.
 */

const EMAIL = process.env.PUBRIVA_ACCEPT_EMAIL;
const PASSWORD = process.env.PUBRIVA_ACCEPT_PASSWORD;

/** البادئةُ الحارسة — **لا يُلمس ما لا يبدأ بها**. */
const MARKER = "PUBRIVA-W11-ACCEPT";
/** الملفُّ الذي تعمل عليه هذه الرحلة — من مخلّفات تشغيلةٍ سابقة، لا رفعٌ جديد. */
const TARGET_FILE = "PUBRIVA-W11-ACCEPT-1788779150628.txt";
/** ملفٌّ يتيم من التشغيلة الثانية — يُنظَّف بعد إثبات دورة الحياة. */
const ORPHAN_FILE = "PUBRIVA-W11-ACCEPT-1788779531506.txt";

/** مفردةُ حالِ المعالجة كما يعرّفها الخادم — لا نصٌّ حرّ. */
const PROCESSING_STATES = new Set([
  "uploaded", "queued", "parsing", "extracting", "awaiting_consent",
  "ready_for_review", "completed", "failed", "text_layer_missing",
]);

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

test.describe.configure({ mode: "serial", timeout: 12 * 60_000 });

// **ولا مسجّلَ يعمل**: الأثرُ والفيديو واللقطة تحمل DOM صفحةٍ فيها حقولُ
// اعتماد. ويُمحى ما بقي في خطوة `always()` قبل أيّ رفع — حزامان لا واحد.
test.use({ trace: "off", video: "off", screenshot: "off" });

// **الاعتمادُ شرطُ تشغيل لا سببَ تخطٍّ** — والقبولُ يسقط مغلقًا.
test.beforeAll(() => {
  if (!EMAIL || !PASSWORD) {
    throw new Error(
      "PUBRIVA_ACCEPT_EMAIL / PUBRIVA_ACCEPT_PASSWORD are not set. Production "
      + "acceptance fails closed: it never reports green without having run.");
  }
});

// ═════════ رصدُ الشبكة والأخطاء ═════════

interface Watch {
  apiCalls: { method: string; path: string; status: number }[];
  serverErrors: string[];
  consoleErrors: string[];
  pageErrors: string[];
  requestFailures: string[];
  apiOrigin: string | null;
}

function watch(page: Page): Watch {
  const w: Watch = {
    apiCalls: [], serverErrors: [], consoleErrors: [],
    pageErrors: [], requestFailures: [], apiOrigin: null,
  };
  page.on("response", (r) => {
    const url = new URL(r.url());
    if (!url.pathname.startsWith("/api/v1")) return;
    w.apiOrigin ??= url.origin;
    w.apiCalls.push({ method: r.request().method(), path: url.pathname, status: r.status() });
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

/** **يُطبع فورًا عند كلّ فشل** — لا يُجمَع لتقريرٍ قد لا يُبلَغ. */
function shout(stage: string, facts: Record<string, unknown>): void {
  console.log(`\n── ACCEPTANCE DIAGNOSTIC · ${stage} ──`);
  for (const [k, v] of Object.entries(facts)) console.log(`   ${k}: ${v}`);
  console.log("──────────────────────────────────────\n");
}

// ═════════ الحالةُ المشتركة ═════════

let thesisId = "";
let processedFileId = "";
const evidence: Record<string, string> = {};

function targetCard(page: Page) {
  return page.locator(`article.card[data-testid="thesis-card-${thesisId}"]`);
}

/**
 * **لا يُلمس صفٌّ حتى يُثبت أنّه صفُّنا** — بأمرين معًا: المعرّفُ جاء من
 * ردّ `process-file` بعينه، والبطاقةُ تحمل اسمَ الملفّ التركيبيّ.
 */
async function assertOwnership(page: Page, stage: string) {
  expect(thesisId, "no thesis id captured from a real response").toMatch(UUID);
  const card = targetCard(page).first();
  await expect(card, `${stage}: the target card is not on screen`).toBeVisible({
    timeout: 30_000,
  });
  const text = await card.innerText();
  if (!text.includes(MARKER) || !text.includes(TARGET_FILE)) {
    shout(stage, {
      "refusing to mutate": "card does not carry the synthetic filename",
      thesisId, expectedFile: TARGET_FILE,
    });
    throw new Error(`${stage}: refusing to act on a card that is not ours`);
  }
}

async function openThesisCentre(page: Page, locale = "ar") {
  await page.goto(`/${locale}/theses`);
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible({
    timeout: 60_000,
  });
}

async function chooseView(page: Page, value: string) {
  await page.locator("#thesis-view").selectOption(value);
  await page.waitForTimeout(2000);
}

// ═════════ الرحلة ═════════

test("Wave 1.1 thesis lifecycle on production", async ({ page }) => {
  const w = watch(page);

  // ── أ — الدخول من الشاشة ──
  await test.step("A · sign in through the real UI", async () => {
    await page.goto("/ar/login");
    await signIn(page, EMAIL!, PASSWORD!);
    await openThesisCentre(page);
    evidence.auth = "signed in via the login form; Thesis Center rendered";
  });

  // ── ب — الملفُّ القائم يُوجد بالاسم، ولا يُرفع جديد ──
  await test.step("B · locate the existing synthetic file in My Library", async () => {
    await page.goto("/ar/library");
    const card = page.locator("article.card").filter({ hasText: TARGET_FILE }).first();
    if (await card.count() === 0) {
      shout("B/locate", {
        targetFile: TARGET_FILE,
        totalCards: await page.locator("article.card").count(),
        markerCards: await page.locator("article.card").filter({ hasText: MARKER }).count(),
      });
    }
    await expect(card, `the synthetic file ${TARGET_FILE} is not in My Library`)
      .toBeVisible({ timeout: 60_000 });
    evidence.fileFound = `${TARGET_FILE} present in My Library (not re-uploaded)`;
  });

  // ── ج — الطلبُ يُثبت نفسه بردٍّ، لا بضغطة ──
  await test.step("C · process-file must actually be emitted and answer 202", async () => {
    const card = page.locator("article.card").filter({ hasText: TARGET_FILE }).first();
    const button = card.getByRole("button", { name: /^معالجة المستند:/ });
    await expect(button, "no processing control on the synthetic file").toBeVisible();

    // **الرصدُ قبل الضغط** — وإلّا فاتنا الطلبُ الذي نريد إثباته.
    const posts: string[] = [];
    const onRequest = (r: Request) => {
      const path = new URL(r.url()).pathname;
      if (r.method() === "POST" && path.startsWith("/api/v1/theses/process-file/")) {
        posts.push(path);
      }
    };
    page.on("request", onRequest);

    const waiting = page.waitForResponse(
      (r) => new URL(r.url()).pathname.startsWith("/api/v1/theses/process-file/")
             && r.request().method() === "POST",
      { timeout: 90_000 }).catch(() => null);

    await button.click();
    const response = await waiting;
    // فسحةٌ قصيرة تكشف طلبًا ثانيًا لو وقع.
    await page.waitForTimeout(3000);
    page.off("request", onRequest);

    let status = 0;
    let safeCode = "";
    let body: Record<string, unknown> = {};
    if (response) {
      status = response.status();
      try {
        body = await response.json();
      } catch {
        body = {};
      }
      if (status >= 400) {
        // **رمزُ الخطأ وحده** — لا ترويسة ولا جسمَ كامل ولا رابط موقَّع.
        safeCode = String((body as { error?: { code?: string } }).error?.code ?? "unknown");
      }
    }

    if (posts.length !== 1 || status !== 202) {
      shout("C/process-file", {
        "PROCESS REQUEST": posts.length > 0 ? "emitted" : "NOT EMITTED",
        "REQUEST COUNT": posts.length,
        "STATUS": status || "no response",
        "SAFE ERROR CODE": safeCode || "n/a",
        "REQUESTFAILED": w.requestFailures.join(" | ") || "none",
        "CONSOLE ERROR": w.consoleErrors.slice(-3).join(" | ") || "none",
        "PAGE ERROR": w.pageErrors.slice(-3).join(" | ") || "none",
      });
    }
    // **ولا انتظارَ بعد طلبٍ فاشل** — ذاك ما أخفى العطب أوّلَ مرّة.
    expect(posts.length, `expected exactly one process-file POST, saw ${posts.length}`).toBe(1);
    expect(status, `process-file answered ${status}${safeCode ? ` (${safeCode})` : ""}`).toBe(202);

    // ── هويّةٌ من جسم الردّ، لا من نصّ عنوان ──
    thesisId = String(body.thesis_id ?? "");
    processedFileId = String(body.file_id ?? "");
    const state = String(body.status ?? "");
    expect(thesisId, "202 carried no thesis_id").toMatch(UUID);
    expect(processedFileId, "202 carried no file_id").toMatch(UUID);
    // ومعرّفُ الملفّ في الردّ هو الذي في مسار الطلب — فلا التباس.
    expect(posts[0], "the 202 file_id does not match the clicked file")
      .toContain(processedFileId);
    expect(PROCESSING_STATES.has(state), `status '${state}' is outside the contract`)
      .toBe(true);

    evidence.processRequest = "emitted";
    evidence.requestCount = "1";
    evidence.processStatus = "202";
    evidence.safeErrorCode = "n/a";
    evidence.requestFailed = w.requestFailures.join(" | ") || "none";
    evidence.consoleError = w.consoleErrors.slice(-3).join(" | ") || "none";
    evidence.pageError = w.pageErrors.slice(-3).join(" | ") || "none";
    evidence.thesisId = thesisId;
    evidence.processingState = state;
  });

  // ── د — البطاقةُ بالمعرّف، لا بالنصّ ──
  await test.step("D · the thesis card appears, selected by its id", async () => {
    await openThesisCentre(page);
    try {
      await expect
        .poll(async () => {
          await page.reload();
          await expect(page.getByRole("heading", { level: 1 }).first())
            .toBeVisible({ timeout: 60_000 });
          return await targetCard(page).count() > 0 ? "FOUND" : "absent";
        }, { timeout: 240_000, message: "the thesis card never rendered" })
        .toBe("FOUND");
    } catch (error) {
      shout("D/card", {
        thesisId,
        testidPresent: await page.locator(`[data-testid="thesis-card-${thesisId}"]`).count(),
        totalCards: await page.locator("article.card").count(),
        activeView: await page.locator("#thesis-view").inputValue().catch(() => "n/a"),
        listCalls: w.apiCalls.filter((c) => c.path === "/api/v1/theses")
          .slice(-3).map((c) => `${c.method}:${c.status}`).join(",") || "none",
        errorsOnPage: await page.locator(".error").count(),
      });
      throw error;
    }
    await assertOwnership(page, "D");
    evidence.thesisCard = "visible in the active Thesis Center list, matched by data-testid";
  });

  // ── هـ — معاينةُ الإزالة من ردٍّ حقيقي ──
  await test.step("E · removal preview comes from the real response", async () => {
    await assertOwnership(page, "E");
    const card = targetCard(page).first();
    await card.getByTestId("card-menu").click();
    const waiting = page.waitForResponse(
      (r) => r.url().includes(`/theses/${thesisId}/removal-preview`)
             && r.request().method() === "GET", { timeout: 60_000 });
    await card.getByTestId("menu-archive").click();
    const response = await waiting;
    if (response.status() !== 200) {
      shout("E/preview", { status: response.status(), thesisId });
    }
    expect(response.status()).toBe(200);
    const body = await response.json();
    evidence.removalPreview = `200 · needs_acknowledgement=${body.needs_acknowledgement}`;
    const deps = (body.dependencies ?? [])
      .filter((d: { count: number }) => d.count > 0)
      .map((d: { key: string; count: number; blocking: boolean }) =>
        `${d.key}=${d.count}${d.blocking ? "(ack)" : ""}`);
    evidence.dependencies = deps.length ? deps.join(" ") : "none";
    evidence.needsAcknowledgement = String(body.needs_acknowledgement);

    const preview = card.getByTestId("removal-preview");
    await expect(preview).toBeVisible({ timeout: 30_000 });
    await expect(preview).toContainText(String(body.explanation).slice(0, 40));
  });

  // ── و — الأرشفة، ثمّ إعادةُ تحميلٍ تُثبت الحفظ ──
  await test.step("F · archive, proven persistent across a reload", async () => {
    const card = targetCard(page).first();
    const confirm = card.getByTestId("archive-confirm");
    await expect(confirm).toHaveText(
      evidence.needsAcknowledgement === "true" ? "أقرّ وأخفِ السجلّ" : "أخفِ السجلّ");

    const waiting = page.waitForResponse(
      (r) => r.url().includes(`/theses/${thesisId}/archive`)
             && r.request().method() === "POST", { timeout: 60_000 });
    await confirm.click();
    const response = await waiting;
    if (response.status() !== 200) shout("F/archive", { status: response.status(), thesisId });
    expect(response.status()).toBe(200);
    expect((await response.json()).rows_deleted, "archive deleted rows").toBe(0);
    evidence.archive = "200 · rows_deleted=0";

    await expect(targetCard(page)).toHaveCount(0, { timeout: 30_000 });
    await page.reload();
    await openThesisCentre(page);
    await expect(targetCard(page), "still active after reload").toHaveCount(0, {
      timeout: 30_000,
    });
    await chooseView(page, "archived");
    await expect(targetCard(page).first(), "not in the Archived view after reload")
      .toBeVisible({ timeout: 30_000 });
    evidence.reloadAfterArchive = "absent from active, present in Archived, after a reload";
  });

  // ── ز — الملفُّ لم يُمسّ ──
  await test.step("G · the linked library file survives archiving", async () => {
    await page.goto("/ar/library");
    await expect(page.locator("article.card").filter({ hasText: TARGET_FILE }).first(),
                 "the linked file disappeared after archiving")
      .toBeVisible({ timeout: 60_000 });
    evidence.linkedFilePreserved = `${TARGET_FILE} still in My Library`;
  });

  // ── ح — الاسترجاع ──
  await test.step("H · restore, proven persistent across a reload", async () => {
    await openThesisCentre(page);
    await chooseView(page, "archived");
    await assertOwnership(page, "H");
    const waiting = page.waitForResponse(
      (r) => r.url().includes(`/theses/${thesisId}/restore`)
             && r.request().method() === "POST", { timeout: 60_000 });
    await targetCard(page).first().getByTestId("card-restore").click();
    const response = await waiting;
    if (response.status() !== 200) shout("H/restore", { status: response.status(), thesisId });
    expect(response.status()).toBe(200);
    evidence.restore = "200";

    await page.reload();
    await openThesisCentre(page);
    await expect(targetCard(page).first(), "not back in the active list")
      .toBeVisible({ timeout: 30_000 });
    await chooseView(page, "archived");
    await expect(targetCard(page), "still in Archived after restore").toHaveCount(0, {
      timeout: 30_000,
    });
    evidence.reloadAfterRestore = "present in active, absent from Archived, after a reload";
  });

  // ── ط — الإنجليزية: قراءةٌ فقط ──
  await test.step("I · English surface reads correctly, read-only", async () => {
    await openThesisCentre(page, "en");
    const options = (await page.locator("#thesis-view option").allTextContents()).join(" ");
    expect(options, "the Archived view is missing in English").toContain("Archived");
    await expect(targetCard(page).first(), "the thesis is not visible in English")
      .toBeVisible({ timeout: 30_000 });
    const body = (await page.locator("body").innerText()).trim();
    const rawKeys = body.match(/\btheses\.[a-zA-Z]+/g) ?? [];
    if (rawKeys.length) shout("I/english", { untranslatedKeys: rawKeys.join(", ") });
    expect(rawKeys, "untranslated message keys rendered").toEqual([]);
    evidence.arabic = "full mutation journey performed in Arabic";
    evidence.english = "Active/Archived terminology present, no untranslated keys";
  });

  // ── ي — لا نقطةَ حذف، ولا تُجرَّب ──
  await test.step("J · the live OpenAPI has no thesis DELETE route", async () => {
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

  // ── الحالُ النهائية: مؤرشَفة ──
  await test.step("K · leave the synthetic thesis archived", async () => {
    await openThesisCentre(page);
    if (await targetCard(page).count() > 0) {
      await assertOwnership(page, "K");
      const card = targetCard(page).first();
      await card.getByTestId("card-menu").click();
      await card.getByTestId("menu-archive").click();
      await expect(card.getByTestId("removal-preview")).toBeVisible({ timeout: 60_000 });
      const waiting = page.waitForResponse(
        (r) => r.url().includes(`/theses/${thesisId}/archive`)
               && r.request().method() === "POST", { timeout: 60_000 });
      await card.getByTestId("archive-confirm").click();
      expect((await waiting).status()).toBe(200);
    }
    await page.reload();
    await openThesisCentre(page);
    await expect(targetCard(page)).toHaveCount(0, { timeout: 30_000 });
    evidence.finalThesisState = "archived (hidden, not deleted)";
  });

  // ── تنظيفُ اليتيم: بعد إثبات دورة الحياة، وبشروطه ──
  await test.step("L · soft-trash the orphan file, only if provably safe", async () => {
    await page.goto("/ar/library");
    const orphan = page.locator("article.card").filter({ hasText: ORPHAN_FILE }).first();
    if (await orphan.count() === 0) {
      evidence.orphanCleanup = `${ORPHAN_FILE} not found in My Library — nothing done`;
      return;
    }
    const text = await orphan.innerText();
    // **شروطٌ قبل أيّ لمس**: الاسمُ بعينه، والبادئةُ الحارسة، وأنّه ليس
    // الملفَّ الذي عملنا عليه.
    if (!text.includes(ORPHAN_FILE) || !text.includes(MARKER)
        || ORPHAN_FILE === TARGET_FILE) {
      evidence.orphanCleanup = "identity could not be proven — left untouched";
      return;
    }
    const trash = orphan.getByRole("button", { name: /حذف الملف/ });
    if (await trash.count() === 0) {
      evidence.orphanCleanup =
        "no ordinary soft-Trash control offered on the card — left untouched";
      return;
    }
    await trash.click();
    // حوارُ تأكيدٍ يظهر إن كان الملفّ مرتبطًا ببحث — والارتباطُ يعني «اتركه»:
    // التنظيفُ لا يقتحم شيئًا.
    const linkedConfirm = page.getByRole("button", { name: /احذف على أي حال/ });
    if (await linkedConfirm.count() > 0) {
      evidence.orphanCleanup =
        "the orphan is linked to projects — refused to force; left untouched";
      const cancel = page.getByRole("button", { name: /لا تحذف/ });
      if (await cancel.count() > 0) await cancel.click();
      return;
    }
    await page.waitForTimeout(3000);
    await page.reload();
    const still = await page.locator("article.card").filter({ hasText: ORPHAN_FILE }).count();
    evidence.orphanCleanup = still === 0
      ? `${ORPHAN_FILE} moved to the product's soft Trash (recoverable)`
      : `${ORPHAN_FILE} still listed after the attempt — left as is`;
  });

  // ── لا خمسمئة في الرحلة كلّها ──
  if (w.serverErrors.length) shout("final/5xx", { serverErrors: w.serverErrors.join(" | ") });
  expect(w.serverErrors, "unexpected 5xx during the journey").toEqual([]);
  evidence.unexpected5xx = "none";
  evidence.apiCalls = String(w.apiCalls.length);

  console.log("── Wave 1.1 production acceptance ──");
  for (const [k, v] of Object.entries(evidence)) console.log(`  ${k}: ${v}`);
});
