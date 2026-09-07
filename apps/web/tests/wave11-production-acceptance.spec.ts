import { expect, test, type Page, type Request } from "@playwright/test";

import { signIn } from "./journey";

/**
 * قبولُ الموجة 1.1 على الإنتاج | Wave 1.1 production acceptance — real account,
 * real browser, real production API, real persisted state.
 *
 * **ولا اعتراضَ شبكةٍ هنا ولا محاكاة.** حزمةُ `thesis-center.spec.ts` تعترض
 * الشبكة وتفحص الشاشة على عقدٍ مُعطى — وذاك فحصٌ نافع، وليس قبولًا. القبولُ
 * أن يقع الأمر كلُّه: ضغطةٌ في الشاشة، فطلبٌ إلى إنتاجٍ حقيقي، فردٌّ حقيقي،
 * فحالٌ تُحفظ، ثمّ **إعادةُ تحميل** تجدها كما تُركت. وإعادةُ التحميل هي
 * التي تفصل الحفظَ عن تفاؤل الواجهة.
 *
 * ## حدودٌ لا تُتجاوز
 *
 * **لا يُمسّ إلّا ما يحمل معرّفَ هذه التشغيلة.** `PUBRIVA-W11-ACCEPT-<وقت>`
 * يدخل في اسم الملفّ المرفوع، وكلُّ مُحدِّدٍ في هذا الملفّ يُرشَّح به. ورسالةُ
 * باحثٍ حقيقيّ لا تُلمس — لا تُؤرشَف ولا تُقرأ ولا تُعدّ.
 *
 * **ولا حذفَ فيزيائيّ.** الأرشفةُ إخفاءٌ يُستعاد، ونقلُ الملفّ إلى السلّة
 * نقلٌ ناعم. ولا يُصدر هذا الملفّ طلبَ `DELETE` على رسالةٍ إطلاقًا — ووجودُ
 * النقطة من عدمه يُقرأ من عقد OpenAPI الحيّ، لا بتجربتها.
 *
 * **ولا يُطبع اعتماد.** ولا يُبنى رمزُ وصولٍ بيد: الدخول يقع من الشاشة.
 */

const EMAIL = process.env.PUBRIVA_ACCEPT_EMAIL;
const PASSWORD = process.env.PUBRIVA_ACCEPT_PASSWORD;

/** معرّفُ التشغيلة — **وهو وحده ما يُلمس**. */
const RUN_ID = `PUBRIVA-W11-ACCEPT-${Date.now()}`;
const DOC_NAME = `${RUN_ID}.txt`;

/**
 * وثيقةٌ **تركيبية** بالكامل: لا محتوى بحثٍ ولا بيانات شخص. وصياغتها تشبه
 * رسالةً علمية ليقبلها المفكِّك ويبلغ المستندُ حالًا مستقرّة.
 */
const DOC_TEXT = [
  `معرّف تشغيلة القبول: ${RUN_ID}`,
  "مشكلة الدراسة: ضعفٌ في مهارات التفكير الناقد لدى طلاب المرحلة الثانوية.",
  "سؤال الدراسة: ما أثر برنامج تدريبي قائم على التعلّم النشط في التفكير الناقد؟",
  "منهج الدراسة: منهج شبه تجريبي بتصميم المجموعتين مع قياس قبلي وبعدي.",
  "عيّنة الدراسة: ستّون طالبًا وُزّعوا عشوائيًّا على مجموعتين متكافئتين.",
  "أداة الدراسة: اختبار التفكير الناقد المقنّن، وبلغ ثبات الأداة 0.87.",
  "النتائج: فرقٌ دالّ إحصائيًّا لصالح المجموعة التجريبية.",
  "حدود الدراسة: مدارس حكومية في مدينة واحدة خلال فصل دراسي واحد.",
].join("\n");

test.describe.configure({ mode: "serial", timeout: 15 * 60_000 });

// **ولا مسجّلَ يعمل في رحلة القبول.** الإعدادُ العام يُبقي الأثرَ والفيديو
// واللقطةَ عند الفشل، وهي هنا لقطاتُ صفحةٍ فيها حقولُ اعتماد. فتُطفأ
// الثلاثةُ صراحةً في هذا الملفّ، ويُمحى ما بقي في خطوةٍ `always()` قبل أيّ
// رفع — حزامان لا واحد.
test.use({ trace: "off", video: "off", screenshot: "off" });

// **الاعتمادُ شرطُ تشغيل، لا سببَ تخطٍّ.** وهذا يخالف خطوةَ القبول القائمة
// في `ci.yml` عمدًا: تلك تُحذّر وتتخطّى، وهذه **تسقط مغلقة**. قبولٌ يُتخطّى
// بصمتٍ يُقرأ خضرةً، وخضرةٌ عن رحلةٍ لم تقع أسوأ من حمرة.
test.beforeAll(() => {
  if (!EMAIL || !PASSWORD) {
    throw new Error(
      "PUBRIVA_ACCEPT_EMAIL / PUBRIVA_ACCEPT_PASSWORD are not set. Production "
      + "acceptance fails closed: it never reports green without having run.");
  }
});

// ═════════ أدواتٌ مشتركة ═════════

interface Seen {
  /** كلُّ نداءٍ إلى الـAPI: الطريقة والمسار والحال. */
  calls: { method: string; path: string; status: number }[];
  /** أصلُ الـAPI كما لوحظ من طلبٍ حقيقي — **لا يُكتب بيد**. */
  apiOrigin: string | null;
  /** أخطاءُ خمسمئة غير المتوقَّعة — وأيُّها يُسقط الرحلة. */
  serverErrors: string[];
}

function watch(page: Page): Seen {
  const seen: Seen = { calls: [], apiOrigin: null, serverErrors: [] };
  page.on("response", (response) => {
    const url = new URL(response.url());
    if (!url.pathname.startsWith("/api/v1")) return;
    seen.apiOrigin ??= url.origin;
    const entry = {
      method: response.request().method(),
      path: url.pathname,
      status: response.status(),
    };
    seen.calls.push(entry);
    // **وخمسمئةٌ واحدة تُسقط الرحلة كلَّها** — أينما وقعت.
    if (response.status() >= 500) {
      seen.serverErrors.push(`${entry.method} ${entry.path} -> ${entry.status}`);
    }
  });
  return seen;
}

/** بطاقةُ الرسالة التركيبية — **مُرشَّحةٌ بمعرّف التشغيلة دائمًا**. */
function syntheticCard(page: Page) {
  return page.locator("article.card").filter({ hasText: RUN_ID });
}

/** معرّفُ الرسالة من الشاشة — من `data-testid`، لا من قاعدةِ بيانات. */
async function thesisIdFromCard(page: Page): Promise<string> {
  const testid = await syntheticCard(page).first().getAttribute("data-testid");
  expect(testid, "the synthetic thesis card carries no test id").toBeTruthy();
  return testid!.replace(/^thesis-card-/, "");
}

async function openThesisCentre(page: Page, locale = "ar") {
  await page.goto(`/${locale}/theses`);
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible({
    timeout: 60_000,
  });
}

async function chooseView(page: Page, value: string) {
  await page.locator("#thesis-view").selectOption(value);
  // القائمةُ تُعاد قراءتها من الخادم بعد تبديل العرض.
  await page.waitForTimeout(1500);
}

// ═════════ الرحلة ═════════

test("Wave 1.1 thesis lifecycle, end to end on production", async ({ page }) => {
  const seen = watch(page);
  let thesisId = "";
  const evidence: Record<string, string> = { runId: RUN_ID };

  // ── أ — الدخول من الشاشة، لا ببناء رمز ──
  await test.step("A · sign in through the real UI", async () => {
    await page.goto("/ar/login");
    await signIn(page, EMAIL!, PASSWORD!);
    await openThesisCentre(page);
    evidence.auth = "signed in via the login form; Thesis Center rendered";
  });

  // ── ب — إنشاءُ رسالةٍ بالمسار القانونيّ: رفعٌ ثمّ معالجة ──
  await test.step("B · upload a synthetic document and process it", async () => {
    await page.goto("/ar/library");
    await page.locator('input[type="file"]').setInputFiles({
      name: DOC_NAME,
      mimeType: "text/plain",
      buffer: Buffer.from(DOC_TEXT, "utf-8"),
    });
    await expect(page.getByText("تم الحفظ")).toBeVisible({ timeout: 120_000 });

    const card = page.locator("article.card").filter({ hasText: RUN_ID }).first();
    await expect(card, "the synthetic file never appeared in My Library")
      .toBeVisible({ timeout: 60_000 });

    // **زرٌّ حقيقي بهدفه** — أزرارُ المعالجة كثيرة، واحدٌ لكلّ ملفّ.
    const process = card.getByRole("button", { name: /^معالجة المستند:/ });
    await expect(process, "no processing control on the synthetic file").toBeVisible();
    await process.click();
    evidence.created = `uploaded ${DOC_NAME} and started processing via the UI`;
  });

  // ── ك — الحمايةُ أثناء العمل الجاري: من الشاشة وحدها ──
  //
  // **ولا يُسابَق نداءُ سلّةٍ في الإنتاج.** لو انتهت المعالجة بين الفحص
  // والنداء لنجح النداء — فأُتلف ملفٌّ لسببٍ لا علاقة له بالحدّ المفحوص.
  // والحدُّ على الخادم مفحوصٌ في حزمة PostgreSQL؛ وهنا تُقرأ الشاشة فقط.
  await test.step("K · in-flight state withdraws destructive actions (UI only)", async () => {
    await openThesisCentre(page);
    let observed = false;
    for (let attempt = 0; attempt < 20 && !observed; attempt += 1) {
      const card = syntheticCard(page).first();
      if (await card.count() > 0 && await card.getByTestId("card-running").count() > 0) {
        observed = true;
        // القائمةُ تُفتح، فلا يُعرض فيها فعلٌ يُتلف.
        const menu = card.getByTestId("card-menu");
        if (await menu.count() > 0) {
          await menu.click();
          await expect(card.getByTestId("menu-archive")).toHaveCount(0);
          await expect(card.getByTestId("menu-trash-file")).toHaveCount(0);
          await expect(card.getByTestId("menu-lifecycle-blocked"))
            .toContainText("إلغاء");
          await menu.click();
        }
        evidence.inFlight =
          "observed in-flight: archive and trash withdrawn, reason shown";
      }
      if (!observed) {
        await page.waitForTimeout(3000);
        await page.reload();
      }
    }
    if (!observed) {
      // **ولا يُدَّعى ما لم يُرَ.** المعالجةُ قد تنتهي أسرع من أوّل قراءة.
      evidence.inFlight =
        "NOT OBSERVED — processing settled before an in-flight render was caught";
    }
  });

  // ── ج — بطاقةٌ حيّة في مركز الرسائل ──
  await test.step("C · the thesis appears as an active card", async () => {
    await openThesisCentre(page);
    await expect
      .poll(async () => {
        await page.reload();
        return syntheticCard(page).count();
      }, { timeout: 300_000, message: "the synthetic thesis never appeared" })
      .toBeGreaterThan(0);
    thesisId = await thesisIdFromCard(page);
    expect(thesisId, "no thesis id could be read from the card").toBeTruthy();
    evidence.thesisId = thesisId;
    evidence.activeCard = "present in the default (active) Thesis Center list";
  });

  // ── د — معاينةُ الإزالة: من ردٍّ حقيقي، لا من نصٍّ مُختلق ──
  await test.step("D · removal preview comes from the real response", async () => {
    const card = syntheticCard(page).first();
    await card.getByTestId("card-menu").click();

    const waiting = page.waitForResponse(
      (r) => r.url().includes(`/theses/${thesisId}/removal-preview`)
             && r.request().method() === "GET",
      { timeout: 60_000 });
    await card.getByTestId("menu-archive").click();
    const response = await waiting;
    expect(response.status(), "removal-preview did not answer 200").toBe(200);

    const body = await response.json();
    evidence.previewStatus = "200";
    evidence.needsAcknowledgement = String(body.needs_acknowledgement);

    const counts = (body.dependencies ?? [])
      .filter((d: { count: number }) => d.count > 0)
      .map((d: { key: string; count: number; blocking: boolean }) =>
        `${d.key}=${d.count}${d.blocking ? "(needs-ack)" : ""}`);
    evidence.dependencies = counts.length ? counts.join(" ") : "none";

    // **والمعروضُ هو المُستقبَل** — لا نصٌّ ثابت في الشاشة.
    const preview = card.getByTestId("removal-preview");
    await expect(preview).toBeVisible({ timeout: 30_000 });
    await expect(preview).toContainText(body.explanation.slice(0, 40));
    if (!body.needs_acknowledgement) {
      await expect(card.getByTestId("removal-no-dependencies")).toBeVisible();
    }
  });

  // ── هـ — الأرشفة، ثمّ إعادةُ تحميلٍ تُثبت الحفظ ──
  await test.step("E · archive, then prove it persisted across a reload", async () => {
    const card = syntheticCard(page).first();
    const confirm = card.getByTestId("archive-confirm");
    const needsAck = evidence.needsAcknowledgement === "true";

    if (needsAck) {
      // **ولا أرشفةَ صامتة**: الزرّ نفسه يقول إنّه إقرار.
      await expect(confirm).toHaveText("أقرّ وأخفِ السجلّ");
    } else {
      await expect(confirm).toHaveText("أخفِ السجلّ");
    }

    const archiving = page.waitForResponse(
      (r) => r.url().includes(`/theses/${thesisId}/archive`)
             && r.request().method() === "POST",
      { timeout: 60_000 });
    await confirm.click();
    const response = await archiving;
    expect(response.status(), "archive did not answer 200").toBe(200);
    evidence.archiveStatus = "200";

    // **ولا كتابةَ حذف**: الردّ يقول صفرَ صفوف.
    const body = await response.json();
    expect(body.rows_deleted, "archive reported deleted rows").toBe(0);

    await expect(syntheticCard(page)).toHaveCount(0, { timeout: 30_000 });
    evidence.activeAfterArchive = "absent from the active list";

    // **إعادةُ التحميل هي الفرق بين الحفظ وتفاؤل الواجهة.**
    await page.reload();
    await openThesisCentre(page);
    await expect(syntheticCard(page)).toHaveCount(0, { timeout: 30_000 });

    await chooseView(page, "archived");
    await expect(syntheticCard(page).first(),
                 "the archived thesis is not in the Archived view")
      .toBeVisible({ timeout: 30_000 });
    await expect(syntheticCard(page).first().getByTestId("card-archived"))
      .toBeVisible();
    evidence.archivedAfterReload = "present in the Archived view after a full reload";
  });

  // ── و — الملفّ لم يُمسّ: فعلان لصاحبين ──
  await test.step("F · archiving the thesis did not trash its library file", async () => {
    await page.goto("/ar/library");
    const file = page.locator("article.card").filter({ hasText: RUN_ID }).first();
    await expect(file, "the synthetic library file disappeared after archiving")
      .toBeVisible({ timeout: 60_000 });
    evidence.fileAfterArchive = "still present in My Library";
  });

  // ── ز — الاسترجاع، ثمّ إعادةُ تحميل ──
  await test.step("G · restore from the Archived view, and prove it persisted", async () => {
    await openThesisCentre(page);
    await chooseView(page, "archived");
    const card = syntheticCard(page).first();
    await expect(card).toBeVisible({ timeout: 30_000 });

    const restoring = page.waitForResponse(
      (r) => r.url().includes(`/theses/${thesisId}/restore`)
             && r.request().method() === "POST",
      { timeout: 60_000 });
    await card.getByTestId("card-restore").click();
    const response = await restoring;
    expect(response.status(), "restore did not answer 200").toBe(200);
    evidence.restoreStatus = "200";

    await page.reload();
    await openThesisCentre(page);
    await expect(syntheticCard(page).first(),
                 "the restored thesis is not back in the active list")
      .toBeVisible({ timeout: 30_000 });
    evidence.activeAfterRestore = "present in the active list after a full reload";

    await chooseView(page, "archived");
    await expect(syntheticCard(page),
                 "the restored thesis is still in the Archived view")
      .toHaveCount(0, { timeout: 30_000 });
    evidence.archivedAfterRestore = "absent from the Archived view";

    await page.goto("/ar/library");
    await expect(page.locator("article.card").filter({ hasText: RUN_ID }).first())
      .toBeVisible({ timeout: 60_000 });
    evidence.fileAfterRestore = "still present in My Library";
  });

  // ── ح — ضغطةٌ واحدة، طلبٌ واحد ──
  await test.step("H · one click produces exactly one lifecycle request", async () => {
    await openThesisCentre(page);
    const card = syntheticCard(page).first();
    await expect(card).toBeVisible({ timeout: 30_000 });

    const posted: string[] = [];
    const record = (request: Request) => {
      const path = new URL(request.url()).pathname;
      if (request.method() === "POST" && /\/theses\/[^/]+\/(archive|restore)$/.test(path)) {
        posted.push(path);
      }
    };
    page.on("request", record);

    await card.getByTestId("card-menu").click();
    await card.getByTestId("menu-archive").click();
    await expect(card.getByTestId("removal-preview")).toBeVisible({ timeout: 60_000 });

    const archiving = page.waitForResponse(
      (r) => r.url().includes(`/theses/${thesisId}/archive`)
             && r.request().method() === "POST",
      { timeout: 60_000 });
    await card.getByTestId("archive-confirm").click();
    await archiving;
    await page.waitForTimeout(2500);
    page.off("request", record);

    expect(posted.length,
           `one click emitted ${posted.length} lifecycle POSTs: ${posted.join(", ")}`)
      .toBe(1);
    evidence.doubleSubmit = "one click -> exactly one lifecycle POST";
  });

  // ── ط — الإنجليزية: قراءةٌ فقط، بلا تغيير ──
  await test.step("I · English surface reads correctly, read-only", async () => {
    await openThesisCentre(page, "en");
    await expect(page.locator("#thesis-view")).toBeVisible({ timeout: 30_000 });

    const options = await page.locator("#thesis-view option").allTextContents();
    expect(options.join(" "), "the Archived view is missing in English")
      .toContain("Archived");
    expect(options.join(" ")).toContain("All");

    await chooseView(page, "archived");
    await expect(syntheticCard(page).first(),
                 "the synthetic thesis is not visible on the English surface")
      .toBeVisible({ timeout: 30_000 });

    // **ولا مفتاحٌ غيرُ مترجَم يظهر للباحث.**
    const body = (await page.locator("body").innerText()).trim();
    const rawKeys = body.match(/\btheses\.[a-zA-Z]+/g) ?? [];
    expect(rawKeys, `untranslated message keys rendered: ${rawKeys.join(", ")}`)
      .toEqual([]);
    evidence.english = "Active/Archived terminology present, no untranslated keys";
    evidence.arabic = "full mutation journey performed in Arabic";
  });

  // ── ي — لا نقطةَ حذفٍ في العقد الحيّ — **ولا تُجرَّب** ──
  await test.step("J · the live OpenAPI has no thesis DELETE endpoint", async () => {
    expect(seen.apiOrigin, "no API origin was observed from real traffic").toBeTruthy();
    const spec = await page.request.get(`${seen.apiOrigin}/openapi.json`);
    expect(spec.status()).toBe(200);
    const paths = (await spec.json()).paths as Record<string, Record<string, unknown>>;

    for (const route of [
      "/api/v1/theses/{thesis_id}/removal-preview",
      "/api/v1/theses/{thesis_id}/archive",
      "/api/v1/theses/{thesis_id}/restore",
    ]) {
      expect(Object.keys(paths), `missing ${route}`).toContain(route);
    }
    // **ولا يُصدَر طلبُ حذفٍ**: يُقرأ العقد ولا تُجرَّب النقطة.
    const byId = paths["/api/v1/theses/{thesis_id}"] ?? {};
    expect(Object.keys(byId).map((m) => m.toLowerCase()),
           "a DELETE verb exists on /api/v1/theses/{thesis_id}")
      .not.toContain("delete");
    evidence.deleteEndpoint = "absent from the live OpenAPI (never requested)";
    evidence.openapiPaths = String(Object.keys(paths).length);
  });

  // ── الحالُ النهائية: مؤرشَفة، فلا تُلوَّث قائمةُ الحساب ──
  await test.step("final · leave the synthetic thesis archived", async () => {
    await openThesisCentre(page);
    if (await syntheticCard(page).count() > 0) {
      const card = syntheticCard(page).first();
      await card.getByTestId("card-menu").click();
      await card.getByTestId("menu-archive").click();
      await expect(card.getByTestId("removal-preview")).toBeVisible({ timeout: 60_000 });
      const archiving = page.waitForResponse(
        (r) => r.url().includes(`/theses/${thesisId}/archive`)
               && r.request().method() === "POST",
        { timeout: 60_000 });
      await card.getByTestId("archive-confirm").click();
      expect((await archiving).status()).toBe(200);
    }
    await page.reload();
    await openThesisCentre(page);
    await expect(syntheticCard(page)).toHaveCount(0, { timeout: 30_000 });
    evidence.finalThesisState = "archived (hidden, not deleted)";
    evidence.finalFileState = "left in My Library, untouched";
  });

  // ── لا خمسمئة في الرحلة كلّها ──
  expect(seen.serverErrors,
         `unexpected 5xx during the journey: ${seen.serverErrors.join(", ")}`)
    .toEqual([]);
  evidence.unexpected5xx = "none";
  evidence.apiCalls = String(seen.calls.length);

  // **خلاصةٌ تُقرأ في سجلّ المشغّل** — بلا اعتماد ولا معرّفٍ شخصي.
  console.log("── Wave 1.1 production acceptance ──");
  for (const [key, value] of Object.entries(evidence)) {
    console.log(`  ${key}: ${value}`);
  }
});
