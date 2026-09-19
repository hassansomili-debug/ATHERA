import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * الخادمُ الحقيقيُّ يقرأ المفتاح | Stage 6 — full stack, no stubbed replies.
 *
 * **ومفتاحٌ يُرسَل ليس مفتاحًا يُحترَم.** الرقعُ السابقةُ تثبت أن المتصفّح
 * يعيد المفتاحَ نفسَه؛ وهذه تُجري الطلبَ على الـAPI الحقيقيّ وتقطع **ردَّه**
 * وحدَه — فالخادمُ عمل، والمتصفّحُ لم يعلم. ثم تُعاد النيّةُ نفسُها، ويُسأل
 * سؤالٌ واحد: **كم كائنًا صار؟**
 *
 * ولا يُفبرَك في هذا الملفّ ردٌّ واحد: كلُّ جسمٍ يُقرأ هنا كتبه الخادم.
 */

const LOCALE = "ar";
const KEY = /^[A-Za-z0-9_-]{16,128}$/;

let seq = 0;

async function register(page: Page): Promise<void> {
  seq += 1;
  const email = `stage6fs-${Date.now()}-${seq}@fixtures.athera`;
  await page.goto(`/${LOCALE}/register`);
  await page.locator("#reg-name").fill("Stage Six Full");
  await page.locator("#reg-email").fill(email);
  await page.locator("#reg-password").fill("Stage6-Passw0rd!");
  await page.locator("form button[type=submit]").click();
  await page.waitForURL(new RegExp(`/${LOCALE}$`), { timeout: 60_000 });
}

const synthetic = (name: string) => ({
  name, mimeType: "text/plain",
  buffer: Buffer.from(
    `PUBRIVA stage-6 full stack ${name}. `.repeat(120) +
    "\n\nAbstract\nThis synthetic document exists only to exercise upload keying.\n",
    "utf-8"),
});

/**
 * **الغموضُ الحقيقيّ**: الطلب يُنفَّذ على الخادم، ثمّ يُطرح ردُّه.
 *
 * ولا يُستبدل الردُّ بمصنوع — يُقرأ ويُحتفظ به للمقارنة وحدها، ثمّ يُقطع
 * الاتصالُ كما ينقطع فعلًا.
 */
function dropFirstReply(
  page: Page,
  glob: string,
  seen: { keys: string[]; bodies: unknown[] },
) {
  let n = 0;
  return page.route(glob, async (route: Route) => {
    if (route.request().method() !== "POST") { await route.continue(); return; }
    n += 1;
    seen.keys.push(route.request().headers()["idempotency-key"] ?? "");
    const response = await route.fetch();
    let parsed: unknown = null;
    try { parsed = await response.json(); } catch { parsed = null; }
    seen.bodies.push(parsed);
    if (n === 1) { await route.abort("connectionfailed"); return; }
    await route.fulfill({ response });
  });
}

/** يراقب المفاتيح بلا اعتراضٍ ألبتّة — الخادمُ يردّ على المتصفّح مباشرة. */
function observeKeys(page: Page, fragment: string, keys: string[]) {
  page.on("request", (req) => {
    if (req.method() === "POST" && req.url().includes(fragment)) {
      keys.push(req.headers()["idempotency-key"] ?? "");
    }
  });
}

test.describe("Stage 6 — the live API honours the browser's key", () => {
  test("a create whose reply was lost, retried, yields exactly one project",
    async ({ page }) => {
      await register(page);
      const title = `بحثٌ للتحقّق ${Date.now()}`;
      const seen = { keys: [] as string[], bodies: [] as unknown[] };
      await dropFirstReply(page, "**/api/v1/workspace/projects", seen);

      await page.goto(`/${LOCALE}/portfolio`);
      const field = page.getByLabel("عنوان البحث");
      await field.waitFor({ state: "visible", timeout: 30_000 });
      await field.fill(title);
      await page.getByRole("button", { name: /أنشئ البحث/ }).click();
      await expect.poll(() => seen.bodies.length, { timeout: 30_000 }).toBe(1);

      // النيّةُ نفسُها تُعاد: العنوانُ لم يتغيّر، فالبصمةُ هي هي.
      await expect(field).toHaveValue(title);
      await page.getByRole("button", { name: /أنشئ البحث/ }).click();
      await expect.poll(() => seen.bodies.length, { timeout: 30_000 }).toBe(2);
      await page.waitForURL(/\/portfolio\/[0-9a-f-]{36}/, { timeout: 30_000 });

      expect(seen.keys[0]).toMatch(KEY);
      expect(seen.keys[1], "الخادمُ الحقيقيُّ تلقّى مفتاحَين لنيّةٍ واحدة")
        .toBe(seen.keys[0]);

      const first = seen.bodies[0] as { id?: string } | null;
      const second = seen.bodies[1] as { id?: string } | null;
      expect(first?.id, "الطلبُ الأوّل لم يُنشئ بحثًا على الخادم").toMatch(/[0-9a-f-]{36}/);
      expect(second?.id, "الإعادةُ أنشأت بحثًا ثانيًا").toBe(first?.id);

      await page.goto(`/${LOCALE}/portfolio`);
      await page.getByTestId("projects-loading").waitFor({ state: "detached", timeout: 30_000 });
      await expect(page.getByRole("link", { name: title })).toHaveCount(1);
    });

  test("an upload whose reply was lost, retried, stores exactly one file",
    async ({ page }) => {
      await register(page);
      const name = `fullstack-${Date.now()}.txt`;
      const seen = { keys: [] as string[], bodies: [] as unknown[] };
      await dropFirstReply(page, "**/api/v1/files/upload", seen);

      await page.goto(`/${LOCALE}/library`);
      const input = page.locator('input[type="file"]').first();
      await input.waitFor({ state: "attached", timeout: 30_000 });
      await input.setInputFiles([synthetic(name)]);
      await expect.poll(() => seen.bodies.length, { timeout: 40_000 }).toBe(1);

      const retry = page.getByTestId("upload-retry").first();
      await retry.waitFor({ state: "visible", timeout: 30_000 });
      await retry.click();
      await expect.poll(() => seen.bodies.length, { timeout: 40_000 }).toBe(2);

      expect(seen.keys[0]).toMatch(KEY);
      expect(seen.keys[1]).toBe(seen.keys[0]);
      const first = seen.bodies[0] as { id?: string } | null;
      const second = seen.bodies[1] as { id?: string } | null;
      expect(first?.id).toMatch(/[0-9a-f-]{36}/);
      expect(second?.id, "الإعادةُ خزّنت ملفًّا ثانيًا").toBe(first?.id);

      await page.goto(`/${LOCALE}/library`);
      await page.getByTestId("library-files-loading")
        .waitFor({ state: "detached", timeout: 30_000 });
      await expect(
        page.getByTestId("library-file-card").filter({ hasText: name }),
      ).toHaveCount(1);
    });

  test("a genuine expired token: the real refresh retries the real upload with the same key",
    async ({ page }) => {
      await register(page);
      const keys: string[] = [];
      observeKeys(page, "/api/v1/theses/upload", keys);
      // **٤٠١ حقيقيّ**: الرمز يُفسَد في التخزين، فيرفضه الخادمُ هو — ولا
      // يُفبرَك ردٌّ ولا يُعترَض طلب. ثمّ يجدّد العميلُ ويعيد.
      await page.goto(`/${LOCALE}/theses`);
      await page.evaluate(() => {
        const token = window.localStorage.getItem("athera_access_token");
        if (!token) throw new Error("no access token stored");
        window.localStorage.setItem("athera_access_token", `${token}tampered`);
        if (!window.localStorage.getItem("athera_refresh_token")) {
          throw new Error("no refresh token stored");
        }
      });
      const input = page.locator('input[type="file"]').first();
      await input.waitFor({ state: "attached", timeout: 30_000 });
      await input.setInputFiles([synthetic(`thesis-fs-${Date.now()}.txt`)]);

      await expect.poll(() => keys.length, { timeout: 60_000 }).toBe(2);
      expect(keys[0]).toMatch(KEY);
      expect(keys[1], "التجديدُ الحقيقيُّ أعاد الطلبَ بمفتاحٍ جديد").toBe(keys[0]);
      // والرسالة وصلت: طورٌ غيرُ خامل ظهر للباحث.
      await expect(page.getByTestId("thesis-intake")).toBeVisible();
    });

  test("a lost process-file reply, retried, does not start a second reading",
    async ({ page }) => {
      await register(page);
      const name = `process-${Date.now()}.txt`;
      await page.goto(`/${LOCALE}/library`);
      const input = page.locator('input[type="file"]').first();
      await input.waitFor({ state: "attached", timeout: 30_000 });
      await input.setInputFiles([synthetic(name)]);
      const card = page.getByTestId("library-file-card").filter({ hasText: name });
      await card.first().waitFor({ state: "visible", timeout: 60_000 });

      const seen = { keys: [] as string[], bodies: [] as unknown[] };
      await dropFirstReply(page, "**/api/v1/theses/process-file/**", seen);
      const start = card.first().getByRole("button", { name: /:/ })
        .filter({ hasText: /./ }).first();
      await start.click();
      await expect.poll(() => seen.bodies.length, { timeout: 40_000 }).toBe(1);
      await expect(start).toBeEnabled({ timeout: 30_000 });
      await start.click();
      await expect.poll(() => seen.bodies.length, { timeout: 40_000 }).toBe(2);

      expect(seen.keys[0]).toMatch(KEY);
      expect(seen.keys[1], "قراءةٌ ثانيةٌ بدأت بمفتاحٍ ثانٍ").toBe(seen.keys[0]);
      const first = seen.bodies[0] as { thesis_id?: string } | null;
      const second = seen.bodies[1] as { thesis_id?: string } | null;
      expect(first?.thesis_id).toMatch(/[0-9a-f-]{36}/);
      expect(second?.thesis_id, "الإعادةُ أنشأت رسالةً ثانية").toBe(first?.thesis_id);
    });

  test("a settled intent is released: the next deliberate create mints a new key",
    async ({ page }) => {
      await register(page);
      const keys: string[] = [];
      observeKeys(page, "/api/v1/workspace/projects", keys);
      await page.goto(`/${LOCALE}/portfolio`);
      const field = page.getByLabel("عنوان البحث");
      await field.waitFor({ state: "visible", timeout: 30_000 });

      const title = `نيّةٌ مستقرّة ${Date.now()}`;
      await field.fill(title);
      await page.getByRole("button", { name: /أنشئ البحث/ }).click();
      await page.waitForURL(/\/portfolio\/[0-9a-f-]{36}/, { timeout: 30_000 });
      expect(keys).toHaveLength(1);

      // **والعنوانُ نفسُه بعد نجاحٍ نيّةٌ جديدة** — لأن الأولى حُسمت.
      await page.goto(`/${LOCALE}/portfolio`);
      await field.waitFor({ state: "visible", timeout: 30_000 });
      await field.fill(title);
      await page.getByRole("button", { name: /أنشئ البحث/ }).click();
      await page.waitForURL(/\/portfolio\/[0-9a-f-]{36}/, { timeout: 30_000 });

      await expect.poll(() => keys.length, { timeout: 30_000 }).toBe(2);
      expect(keys[1]).toMatch(KEY);
      expect(keys[1], "نيّةٌ جديدةٌ وُلدت بمفتاحٍ مستهلَك").not.toBe(keys[0]);
    });
});
