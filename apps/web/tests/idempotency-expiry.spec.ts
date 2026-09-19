import { expect, test, type Page } from "@playwright/test";

/**
 * النيّةُ الشائخةُ تُغلق البابَ | Stage 6 — expiry fails closed.
 *
 * **وأخطرُ نافذةٍ هي الساعةُ الأخيرة.** بقاءُ الجيل في الخادم أربعٌ
 * وعشرون ساعة، والأفقُ الآمنُ للعميل ثلاثٌ وعشرون. فبينهما كان المتصفّحُ
 * يسكّ K2 بينما K1 ما زال حيًّا عند الخادم — توليدان لنيّةٍ واحدة،
 * وعملٌ يقع مرّتين وقد كُتب مرّة.
 *
 * والمقياسُ هنا ليس المفتاحَ بل **الصمت**: كم طلبًا خرج؟ صفر.
 */

const LOCALE = "ar";
const KEY = /^[A-Za-z0-9_-]{16,128}$/;
const CREATE = "**/api/v1/workspace/projects";
const NAMESPACE = "pubriva.idempotency.v1";
const HOUR = 60 * 60 * 1000;

let seq = 0;

async function register(page: Page): Promise<void> {
  seq += 1;
  const email = `stage6exp-${Date.now()}-${seq}@fixtures.athera`;
  await page.goto(`/${LOCALE}/register`);
  await page.locator("#reg-name").fill("Stage Six Expiry");
  await page.locator("#reg-email").fill(email);
  await page.locator("#reg-password").fill("Stage6-Passw0rd!");
  await page.locator("form button[type=submit]").click();
  await page.waitForURL(new RegExp(`/${LOCALE}$`), { timeout: 60_000 });
}

const fail = (status: number, code: string) => ({
  status, contentType: "application/json",
  body: JSON.stringify({ error: { code, locale: "ar", message: "x",
    messages: { ar: "x", en: "x" } } }),
});

/** يُشيخ كلَّ نيّةٍ معلَّقةٍ في التبويبة — بإرجاع ساعةِ ميلادها. */
async function ageAll(page: Page, by: number): Promise<void> {
  await page.evaluate(({ ns, by: shift }) => {
    const raw = window.sessionStorage.getItem(ns);
    if (!raw) throw new Error("no pending intent to age");
    const all = JSON.parse(raw) as Record<string, { createdAt: number }>;
    for (const row of Object.values(all)) row.createdAt = Date.now() - shift;
    window.sessionStorage.setItem(ns, JSON.stringify(all));
  }, { ns: NAMESPACE, by });
}

async function snapshot(page: Page): Promise<string> {
  return page.evaluate((ns) => window.sessionStorage.getItem(ns) ?? "", NAMESPACE);
}

async function openProjects(page: Page, title: string) {
  await page.goto(`/${LOCALE}/portfolio`);
  const field = page.getByLabel("عنوان البحث");
  await field.waitFor({ state: "visible", timeout: 30_000 });
  await field.fill(title);
}

const createCta = (page: Page) => page.getByRole("button", { name: /أنشئ البحث/ });

/**
 * يعدّ **كلَّ** طلبٍ يخرج إلى المسار المحميّ — لا المُعترَضَ وحده.
 *
 * فلو خرج طلبٌ من مسلكٍ آخر لَما رآه المُعترِض، وقيل «لم يخرج شيء» كذبًا.
 */
function countPosts(page: Page): { n: number } {
  const seen = { n: 0 };
  page.on("request", (req) => {
    if (req.method() === "POST" && req.url().includes("/api/v1/workspace/projects")) {
      seen.n += 1;
    }
  });
  return seen;
}

test.describe("Stage 6 — an expired ambiguous intent never rotates its key", () => {
  test("past the safe horizon: no new key, no request, the record untouched",
    async ({ page }) => {
      await register(page);
      const posts = countPosts(page);
      const keys: string[] = [];
      await page.route(CREATE, async (route) => {
        if (route.request().method() !== "POST") { await route.continue(); return; }
        const key = route.request().headers()["idempotency-key"] ?? "";
        await route.fulfill(fail(503, "server.error"));
        keys.push(key);
      });

      const title = `نيّةٌ شاخت ${Date.now()}`;
      await openProjects(page, title);
      await createCta(page).click();
      await expect.poll(() => keys.length, { timeout: 30_000 }).toBe(1);
      expect(keys[0]).toMatch(KEY);
      expect(posts.n).toBe(1);

      // ══ بين الثالثةِ والعشرين والرابعةِ والعشرين: جيلُ الخادم ما زال حيًّا ══
      const before = await snapshot(page);
      await ageAll(page, 23.5 * HOUR);
      const aged = await snapshot(page);
      await createCta(page).click();

      // لا طلبَ خرج — وهذا هو المقياس.
      await expect(page.locator(".error").first()).toBeVisible({ timeout: 30_000 });
      expect(posts.n, "طلبٌ محميٌّ خرج على نيّةٍ شائخة").toBe(1);
      expect(keys.length, "المُعترِضُ رأى محاولةً ثانية").toBe(1);
      // ولا مفتاحَ بديلٌ كُتب: الصفُّ هو هو (بعد التشييخ).
      expect(await snapshot(page), "السجلُّ استُبدل صامتًا").toBe(aged);
      expect(before).not.toBe("");

      // ══ وبعد انقضاء الخادم أيضًا — الجهلُ هو الجهل ══
      await ageAll(page, 30 * HOUR);
      const stale = await snapshot(page);
      await createCta(page).click();
      await expect(page.locator(".error").first()).toBeVisible({ timeout: 30_000 });
      expect(posts.n, "نيّةٌ منقضيةٌ أطلقت طلبًا").toBe(1);
      expect(await snapshot(page)).toBe(stale);
    });

  test("the refusal is a truthful error, and never says the work failed",
    async ({ page }) => {
      await register(page);
      const keys: string[] = [];
      await page.route(CREATE, async (route) => {
        if (route.request().method() !== "POST") { await route.continue(); return; }
        keys.push(route.request().headers()["idempotency-key"] ?? "");
        await route.fulfill(fail(503, "server.error"));
      });
      await openProjects(page, `نيّةٌ صادقة ${Date.now()}`);
      await createCta(page).click();
      await expect.poll(() => keys.length, { timeout: 30_000 }).toBe(1);

      await ageAll(page, 23.5 * HOUR);
      await createCta(page).click();
      const banner = page.locator(".error").first();
      await expect(banner).toBeVisible({ timeout: 30_000 });
      const text = (await banner.innerText()).trim();
      expect(text.length, "رفضٌ بلا جملة").toBeGreaterThan(20);
      // **ولا يُدَّعى ما لا يُعرَف**: لا «فشلت» ولا «لم تُنفَّذ».
      for (const lie of ["فشل", "لم تُنفَّذ", "لم ينفذ", "لم يتم"]) {
        expect(text, `الرفضُ ادّعى معرفةَ المصير: ${lie}`).not.toContain(lie);
      }
    });

  test("a different deliberate intent is not held hostage by the expired one",
    async ({ page }) => {
      await register(page);
      const keys: string[] = [];
      await page.route(CREATE, async (route) => {
        if (route.request().method() !== "POST") { await route.continue(); return; }
        const key = route.request().headers()["idempotency-key"] ?? "";
        await route.fulfill(fail(503, "server.error"));
        keys.push(key);
      });
      await openProjects(page, `الأولى ${Date.now()}`);
      await createCta(page).click();
      await expect.poll(() => keys.length, { timeout: 30_000 }).toBe(1);

      await ageAll(page, 25 * HOUR);
      // **عنوانٌ آخرُ نيّةٌ أخرى** — وبصمتُها غيرُ المحبوسة.
      await page.getByLabel("عنوان البحث").fill(`الثانية ${Date.now()}`);
      await createCta(page).click();
      await expect.poll(() => keys.length, { timeout: 30_000 }).toBe(2);
      expect(keys[1]).toMatch(KEY);
      expect(keys[1]).not.toBe(keys[0]);
    });
});
