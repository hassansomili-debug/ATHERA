import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * تبنّي مفاتيح النيّة في المتصفّح | Stage 6 runtime proofs.
 *
 * **والطلبُ يمرّ بالمتصفّح الحقيقيّ**: بـ`apiFetch` الحقيقيّ وبـ`fetch`
 * الحقيقيّ وبـ`sessionStorage` الحقيقيّ — لا بدوالَّ مُحاكاة. والترويسةُ
 * تُقرأ من الطلب كما يراها الخادم.
 */

const LOCALE = "ar";
const KEY = /^[A-Za-z0-9_-]{16,128}$/;
const QUESTION = "ما المنهجُ الأنسبُ لدراسةِ أثرٍ تعليميّ؟";
const CREATE = "**/api/v1/workspace/projects";

let seq = 0;

/**
 * حسابٌ **حقيقيّ** بالنموذج — لا رموزٌ تُدسّ.
 *
 * ورمزٌ مختلَقٌ في `localStorage` يردّه الخادمُ ٤٠١، فيمحو العميلُ الجلسةَ
 * ويقذف إلى صفحة الدخول — وهو تصرّفٌ صحيحٌ من المنتج على حالٍ صنعها الفحص.
 * فتُقطع تلك الحالُ من أصلها: تسجيلٌ فعليٌّ على الـAPI القائم.
 */
async function register(page: Page): Promise<void> {
  seq += 1;
  const email = `stage6-${Date.now()}-${seq}@fixtures.athera`;
  await page.goto(`/${LOCALE}/register`);
  await page.locator("#reg-name").fill("Stage Six");
  await page.locator("#reg-email").fill(email);
  await page.locator("#reg-password").fill("Stage6-Passw0rd!");
  await page.locator("form button[type=submit]").click();
  await page.waitForURL(new RegExp(`/${LOCALE}$`), { timeout: 60_000 });
}

const AI_ANSWER = JSON.stringify({
  answer: "جواب", status: "ok", limitations: [], capabilities: {},
  references: [], provider_statuses: [], citations: [],
});

const PROJECT = JSON.stringify({
  id: "11111111-2222-3333-4444-555555555555",
  title_ar: "بحثٌ للفحص", title_en: null, status: "idea",
  current_gate: "idea", created_at: new Date().toISOString(),
});

/**
 * يفتح شاشةَ البحوثِ ويكتب عنوانًا — **مسارٌ محميٌّ بلا بوّابةِ نموذج**.
 *
 * فـ`/ai/ask` معطَّلٌ حين يكون المزوّدُ `null` (وهو ضبطُ الفحص الصحيح)،
 * والمقصودُ هنا دلالةُ المفتاح لا النموذجُ نفسُه.
 */
async function openProjects(page: Page, title: string) {
  await page.goto(`/${LOCALE}/portfolio`);
  const field = page.getByLabel("عنوان البحث");
  await field.waitFor({ state: "visible", timeout: 30_000 });
  await field.fill(title);
}

async function create(page: Page) {
  await page.getByRole("button", { name: /أنشئ البحث/ }).click();
}

/** يلتقط ترويسةَ المفتاح لكلّ محاولةِ إنشاء. */
function captureCreate(
  page: Page,
  handler: (route: Route, key: string, n: number) => Promise<void>,
) {
  let n = 0;
  return page.route(CREATE, async (route) => {
    if (route.request().method() !== "POST") { await route.continue(); return; }
    n += 1;
    await handler(route, route.request().headers()["idempotency-key"] ?? "", n);
  });
}

/** يفتح شاشةَ السؤال ويكتب فيه. */
async function openAi(page: Page, question = QUESTION) {
  await page.goto(`/${LOCALE}/ai`);
  const box = page.locator("#athera-ai-input");
  await box.waitFor({ state: "visible" });
  await box.fill(question);
}

async function send(page: Page) {
  await page.locator("button.ai-send").click();
}

/** يلتقط ترويسةَ المفتاح لكلّ محاولةٍ على `/ai/ask`. */
function captureAsk(page: Page, handler: (route: Route, key: string, n: number) => Promise<void>) {
  let n = 0;
  return page.route("**/api/v1/ai/ask", async (route) => {
    n += 1;
    const key = route.request().headers()["idempotency-key"] ?? "";
    await handler(route, key, n);
  });
}

const fail = (status: number, code: string) => ({
  status, contentType: "application/json",
  body: JSON.stringify({ error: { code, locale: "ar", message: "x",
    messages: { ar: "x", en: "x" } } }),
});

test.describe("Stage 6 — protected intents carry one key", () => {
  test("a protected POST sends a well-formed key", async ({ page }) => {
    await register(page);
    const keys: string[] = [];
    await captureCreate(page, async (route, key) => {
      keys.push(key);
      await route.fulfill({ status: 201, contentType: "application/json", body: PROJECT });
    });
    await openProjects(page, "بحثٌ أوّل"); await create(page);
    await expect.poll(() => keys.length).toBe(1);
    expect(keys[0]).toMatch(KEY);
  });

  test("a 401 refresh retries with the exact same key", async ({ page }) => {
    await register(page);
    const keys: string[] = [];
    let refreshes = 0;
    await page.route("**/api/v1/auth/refresh", async (route) => {
      refreshes += 1;
      // **ولا مفتاحَ على مسارِ الرموز** — ويمضي الطلبُ إلى الخادم الحقيقيّ.
      expect(route.request().headers()["idempotency-key"]).toBeUndefined();
      await route.continue();
    });
    await captureCreate(page, async (route, key, n) => {
      keys.push(key);
      if (n === 1) { await route.fulfill(fail(401, "auth.expired")); return; }
      await route.fulfill({ status: 201, contentType: "application/json", body: PROJECT });
    });
    await openProjects(page, "بحثُ التجديد"); await create(page);
    await expect.poll(() => keys.length).toBe(2);
    expect(refreshes).toBe(1);
    expect(keys[0]).toMatch(KEY);
    expect(keys[1], "وُلّد مفتاحٌ ثانٍ عند التجديد").toBe(keys[0]);
  });

  test("a transport failure keeps the key for the next attempt", async ({ page }) => {
    await register(page);
    const keys: string[] = [];
    await captureCreate(page, async (route, key, n) => {
      keys.push(key);
      if (n === 1) { await route.abort("connectionfailed"); return; }
      await route.fulfill({ status: 201, contentType: "application/json", body: PROJECT });
    });
    await openProjects(page, "بحثُ الانقطاع"); await create(page);
    await expect.poll(() => keys.length).toBe(1);
    await create(page);                       // الباحثُ يعيد المحاولة بنفسه
    await expect.poll(() => keys.length).toBe(2);
    expect(keys[1], "أُسقط المفتاحُ على انقطاعٍ لا يُعرف أثرُه").toBe(keys[0]);
  });

  test("a 503 keeps the key, and success then releases it", async ({ page }) => {
    await register(page);
    const keys: string[] = [];
    await captureCreate(page, async (route, key, n) => {
      keys.push(key);
      if (n <= 2) { await route.fulfill(fail(503, "server.error")); return; }
      await route.fulfill({ status: 201, contentType: "application/json", body: PROJECT });
    });
    const TITLE = "بحثُ الخمسمئة";
    await openProjects(page, TITLE); await create(page);
    await expect.poll(() => keys.length).toBe(1);
    await create(page);
    await expect.poll(() => keys.length).toBe(2);
    expect(keys[1], "لم يبقَ المفتاحُ على ٥٠٣").toBe(keys[0]);
    await create(page);                        // الثالثةُ تنجح
    await expect.poll(() => keys.length).toBe(3);
    expect(keys[2], "تبدّل المفتاحُ قبل أن يُحسَم").toBe(keys[0]);

    // **ويُنتظر أن يستقرّ النجاحُ قبل الانتقال.** فاعتراضُ الطلب يقع قبل
    // أن يقرأ العميلُ الجوابَ؛ وانتقالٌ في تلك اللحظة يُجهض المعالجة —
    // فيبدو أنّ النيّةَ لم تُحسَم وهي حُسمت. وسباقُ الفحصِ لا يُحتسب عطبًا.
    await page.waitForURL(/\/portfolio\/[0-9a-f-]{36}/, { timeout: 30_000 });

    // ══ ونيّةٌ جديدةٌ مقصودةٌ بالعنوان نفسِه ══
    //
    // فالنجاحُ نقل الباحثَ إلى بيتِ بحثه؛ ويعود فيُنشئ بحثًا آخرَ بالعنوان
    // عينِه — وذاك **قصدٌ ثانٍ** لا إعادةُ الأوّل. فلو حمل المفتاحَ القديم
    // لأعاد الخادمُ البحثَ الأوّلَ ولم يُنشئ شيئًا.
    await openProjects(page, TITLE); await create(page);
    await expect.poll(() => keys.length).toBe(4);
    expect(keys[3], "أُعيد المفتاحُ بعد نجاحٍ حاسم").not.toBe(keys[0]);
  });

  for (const code of ["idempotency.in_progress", "idempotency.external_result_unknown"]) {
    test(`${code} keeps the pending key`, async ({ page }) => {
      await register(page);
      const keys: string[] = [];
      await captureCreate(page, async (route, key) => {
        keys.push(key);
        await route.fulfill(fail(409, code));
      });
      await openProjects(page, `بحثُ ${code}`); await create(page);
      await expect.poll(() => keys.length).toBe(1);
      await create(page);
      await expect.poll(() => keys.length).toBe(2);
      expect(keys[1], `الرمز ${code} أسقط المفتاح`).toBe(keys[0]);
    });
  }

  test("a definitive rejection releases the intent", async ({ page }) => {
    await register(page);
    const keys: string[] = [];
    await captureCreate(page, async (route, key) => {
      keys.push(key);
      await route.fulfill(fail(422, "validation.failed"));
    });
    await openProjects(page, "بحثٌ مرفوض"); await create(page);
    await expect.poll(() => keys.length).toBe(1);
    await create(page);
    await expect.poll(() => keys.length).toBe(2);
    expect(keys[1], "بقي مفتاحٌ على رفضٍ نهائيّ").not.toBe(keys[0]);
  });

  test("a changed title is a new intent", async ({ page }) => {
    await register(page);
    const keys: string[] = [];
    await captureCreate(page, async (route, key) => {
      keys.push(key);
      await route.fulfill(fail(503, "server.error"));
    });
    await openProjects(page, "عنوانٌ أوّل"); await create(page);
    await expect.poll(() => keys.length).toBe(1);
    await page.getByLabel("عنوان البحث").fill("عنوانٌ آخرُ تمامًا");
    await create(page);
    await expect.poll(() => keys.length).toBe(2);
    expect(keys[1], "عِلمٌ آخرُ حمل المفتاحَ القديم").not.toBe(keys[0]);
  });

  test("reads and auth routes never carry a key", async ({ page }) => {
    const offenders: string[] = [];
    await page.route("**/api/v1/**", async (route) => {
      const req = route.request();
      const key = req.headers()["idempotency-key"];
      const url = new URL(req.url()).pathname;
      if (key && (req.method() === "GET" || url.startsWith("/api/v1/auth/"))) {
        offenders.push(`${req.method()} ${url}`);
      }
      await route.continue();
    });
    await register(page);
    await page.goto(`/${LOCALE}/portfolio`);
    await page.getByLabel("عنوان البحث").waitFor({ state: "visible", timeout: 30_000 });
    expect(offenders, offenders.join(", ")).toEqual([]);
  });

  test("session storage keeps only the key, a hash and a timestamp", async ({ page }) => {
    await register(page);
    const secret = "عنوانٌ علميٌّ سرّيٌّ لا يُخزَّن";
    await captureCreate(page, async (route) => {
      await route.fulfill(fail(503, "server.error"));
    });
    await openProjects(page, secret); await create(page);
    await page.waitForTimeout(500);

    const raw = await page.evaluate(() =>
      sessionStorage.getItem("pubriva.idempotency.v1") ?? "");
    expect(raw, "لم تُحفظ نيّةٌ معلَّقة").not.toBe("");
    const stored = JSON.parse(raw) as Record<string, Record<string, unknown>>;
    const entries = Object.values(stored);
    expect(entries.length).toBeGreaterThan(0);
    for (const entry of entries) {
      expect(Object.keys(entry).sort()).toEqual(["createdAt", "fingerprint", "key"]);
      expect(String(entry.key)).toMatch(KEY);
    }
    // **ولا متنَ بحثٍ ولا رمزَ وصولٍ في المخزن.**
    expect(raw).not.toContain(secret);
    expect(raw).not.toContain("عنوان");
    const tokens = await page.evaluate(() => ({
      access: localStorage.getItem("athera_access_token") ?? "",
      refresh: localStorage.getItem("athera_refresh_token") ?? "",
    }));
    expect(raw).not.toContain(tokens.access);
    expect(raw).not.toContain(tokens.refresh);
  });

  test("the key never leaks into the URL or the request body", async ({ page }) => {
    await register(page);
    let url = ""; let body = ""; let key = "";
    await captureCreate(page, async (route, headerKey) => {
      key = headerKey;
      url = route.request().url();
      body = route.request().postData() ?? "";
      await route.fulfill({ status: 201, contentType: "application/json", body: PROJECT });
    });
    await openProjects(page, "بحثٌ بلا تسريب"); await create(page);
    await expect.poll(() => key.length).toBeGreaterThan(0);
    expect(url).not.toContain(key);
    expect(body).not.toContain(key);
  });
});
