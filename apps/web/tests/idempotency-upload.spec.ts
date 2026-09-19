import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * الرفعُ ومفتاحُ النيّة | Stage 6 — the upload transports.
 *
 * **ونقلان كانا يفترقان.** الرفعُ يبدأ بـ`XMLHttpRequest`، فإن رُدّ ٤٠١
 * سقط إلى `apiFetch` — ولكلِّ نقلٍ توليدُه من قبل، فصار الطلبان مستقلَّين
 * في نظر الخادم ورفعةٌ واحدةٌ تُنتج كائنَين. وهذه الرقعةُ تحرس اتّحادَهما.
 */

const LOCALE = "ar";
const KEY = /^[A-Za-z0-9_-]{16,128}$/;
const UPLOAD = "**/api/v1/files/upload";

let seq = 0;

async function register(page: Page): Promise<void> {
  seq += 1;
  const email = `stage6up-${Date.now()}-${seq}@fixtures.athera`;
  await page.goto(`/${LOCALE}/register`);
  await page.locator("#reg-name").fill("Stage Six Upload");
  await page.locator("#reg-email").fill(email);
  await page.locator("#reg-password").fill("Stage6-Passw0rd!");
  await page.locator("form button[type=submit]").click();
  await page.waitForURL(new RegExp(`/${LOCALE}$`), { timeout: 60_000 });
}

const synthetic = (name: string) => ({
  name, mimeType: "text/plain",
  buffer: Buffer.from(`PUBRIVA stage-6 ${name}\n`.repeat(200), "utf-8"),
});

const STORED = (id: string, name: string) => JSON.stringify({
  id, original_filename: name, content_type: "text/plain", size_bytes: 10,
  status: "stored", classification: "C2", created_at: new Date().toISOString(),
});

/** يلتقط مفتاحَ كلِّ محاولةِ رفع، مع اسمِ الملفّ المرسَل. */
function captureUploads(
  page: Page,
  handler: (route: Route, key: string, n: number, filename: string) => Promise<void>,
) {
  let n = 0;
  return page.route(UPLOAD, async (route) => {
    if (route.request().method() !== "POST") { await route.continue(); return; }
    n += 1;
    const key = route.request().headers()["idempotency-key"] ?? "";
    const body = route.request().postData() ?? "";
    const match = /filename="([^"]+)"/.exec(body);
    await handler(route, key, n, match?.[1] ?? "");
  });
}

async function openLibrary(page: Page) {
  await page.goto(`/${LOCALE}/library`);
  await page.locator('input[type="file"]').first().waitFor({ state: "attached", timeout: 30_000 });
}

test.describe("Stage 6 — uploads carry one key across both transports", () => {
  test("the XHR upload itself sends a well-formed key", async ({ page }) => {
    await register(page);
    const keys: string[] = [];
    await captureUploads(page, async (route, key, _n, name) => {
      keys.push(key);
      await route.fulfill({ status: 201, contentType: "application/json",
        body: STORED("11111111-1111-1111-1111-111111111111", name) });
    });
    await openLibrary(page);
    await page.locator('input[type="file"]').first().setInputFiles([synthetic("one.txt")]);
    await expect.poll(() => keys.length).toBe(1);
    expect(keys[0]).toMatch(KEY);
  });

  test("a 401 falls back to apiFetch with the exact same key", async ({ page }) => {
    await register(page);
    const keys: string[] = [];
    await page.route("**/api/v1/auth/refresh", (route) => route.continue());
    await captureUploads(page, async (route, key, n, name) => {
      keys.push(key);
      if (n === 1) {
        // ٤٠١ على نقلِ XHR ⇒ السقوطُ إلى `apiFetch` — وبالمفتاح نفسِه.
        await route.fulfill({ status: 401, contentType: "application/json",
          body: JSON.stringify({ error: { code: "auth.expired", locale: "ar",
            message: "x", messages: { ar: "x", en: "x" } } }) });
        return;
      }
      await route.fulfill({ status: 201, contentType: "application/json",
        body: STORED("22222222-2222-2222-2222-222222222222", name) });
    });
    await openLibrary(page);
    await page.locator('input[type="file"]').first().setInputFiles([synthetic("switch.txt")]);
    await expect.poll(() => keys.length, { timeout: 30_000 }).toBe(2);
    expect(keys[0]).toMatch(KEY);
    expect(keys[1], "تبديلُ النقلِ ولّد مفتاحًا ثانيًا").toBe(keys[0]);
  });

  test("a network failure keeps the key for a manual retry of the same item",
    async ({ page }) => {
      await register(page);
      const keys: string[] = [];
      await captureUploads(page, async (route, key, n, name) => {
        keys.push(key);
        if (n === 1) { await route.abort("connectionfailed"); return; }
        await route.fulfill({ status: 201, contentType: "application/json",
          body: STORED("33333333-3333-3333-3333-333333333333", name) });
      });
      await openLibrary(page);
      await page.locator('input[type="file"]').first()
        .setInputFiles([synthetic("retry.txt")]);
      await expect.poll(() => keys.length).toBe(1);
      const retry = page.getByTestId("upload-retry").first();
      await retry.waitFor({ state: "visible", timeout: 30_000 });
      await retry.click();
      await expect.poll(() => keys.length, { timeout: 30_000 }).toBe(2);
      expect(keys[1], "إعادةُ العنصرِ نفسِه ولّدت مفتاحًا آخر").toBe(keys[0]);
    });

  test("two queue items never share a key, and one success frees only its own",
    async ({ page }) => {
      await register(page);
      const byName = new Map<string, string[]>();
      await captureUploads(page, async (route, key, _n, name) => {
        const list = byName.get(name) ?? [];
        list.push(key);
        byName.set(name, list);
        if (name.startsWith("alpha")) {
          await route.fulfill({ status: 201, contentType: "application/json",
            body: STORED("44444444-4444-4444-4444-444444444444", name) });
          return;
        }
        // بيتا تسقط — فيبقى مفتاحُها معلَّقًا وحدَه.
        await route.fulfill({ status: 503, contentType: "application/json",
          body: JSON.stringify({ error: { code: "server.error", locale: "ar",
            message: "x", messages: { ar: "x", en: "x" } } }) });
      });
      await openLibrary(page);
      await page.locator('input[type="file"]').first()
        .setInputFiles([synthetic("alpha.txt"), synthetic("beta.txt")]);
      await expect.poll(() => byName.size, { timeout: 40_000 }).toBe(2);

      const alpha = byName.get("alpha.txt")![0];
      const beta = byName.get("beta.txt")![0];
      expect(alpha).toMatch(KEY);
      expect(beta).toMatch(KEY);
      expect(beta, "ملفّان في طابورٍ واحد تشاركا مفتاحًا").not.toBe(alpha);

      // وإعادةُ بيتا وحدَها تحمل مفتاحَها هو — ونجاحُ ألفا لم يمسسه.
      const retry = page.getByTestId("upload-retry").first();
      await retry.waitFor({ state: "visible", timeout: 30_000 });
      await retry.click();
      await expect.poll(() => byName.get("beta.txt")!.length, { timeout: 30_000 })
        .toBe(2);
      expect(byName.get("beta.txt")![1],
        "نجاحُ ملفٍّ آخرَ حرّر مفتاحَ هذا").toBe(beta);
    });

  test("the thesis intake retries the SAME File and keeps its key, then a new selection mints another",
    async ({ page }) => {
      await register(page);
      const keys: string[] = [];
      let n = 0;
      await page.route("**/api/v1/theses/upload", async (route) => {
        if (route.request().method() !== "POST") { await route.continue(); return; }
        n += 1;
        const key = route.request().headers()["idempotency-key"] ?? "";
        if (n <= 2) {
          await route.fulfill({ status: 503, contentType: "application/json",
            body: JSON.stringify({ error: { code: "server.error", locale: "ar",
              message: "x", messages: { ar: "x", en: "x" } } }) });
        } else {
          await route.fulfill({ status: 202, contentType: "application/json",
            body: JSON.stringify({
              thesis_id: "77777777-7777-4777-8777-777777777777",
              file_id: "88888888-8888-4888-8888-888888888888",
              status: "queued", chunks: 0, candidates: 0, message: "queued",
            }) });
        }
        keys.push(key);
      });
      await page.goto(`/${LOCALE}/theses`);
      const input = page.locator('input[type="file"]').first();
      await input.waitFor({ state: "attached", timeout: 30_000 });

      await input.setInputFiles([synthetic("thesis-a.txt")]);
      await expect.poll(() => keys.length, { timeout: 30_000 }).toBe(1);
      expect(keys[0]).toMatch(KEY);

      // ══ الإعادةُ على الملفِّ نفسِه — **بلا فتحِ المنتقي** ══
      //
      // وهذا هو موضعُ العطب: منتقٍ يُفتح يصنع كائن `File` آخر، فتصير
      // الرفعةُ الواحدةُ نيّتَين. فالزرُّ يُعيد على الكائن المحفوظ.
      const retry = page.getByTestId("thesis-upload-retry");
      await retry.waitFor({ state: "visible", timeout: 30_000 });
      await retry.click();
      await expect.poll(() => keys.length, { timeout: 30_000 }).toBe(2);
      expect(keys[1], "إعادةُ الملفِّ نفسِه ولّدت مفتاحًا ثانيًا").toBe(keys[0]);

      // ══ والإعادةُ الناجحةُ تحسم النيّة وتُخفي الزرّ ══
      await retry.click();
      await expect.poll(() => keys.length, { timeout: 30_000 }).toBe(3);
      expect(keys[2], "الإعادةُ الثالثةُ غيّرت المفتاح").toBe(keys[0]);
      await expect(retry).toBeHidden({ timeout: 30_000 });

      // ══ **واختيارٌ آخرُ نيّةٌ أخرى** — ولو تطابق الاسمُ والحجمُ والنوع ══
      await input.setInputFiles([synthetic("thesis-b.txt")]);
      await expect.poll(() => keys.length, { timeout: 30_000 }).toBe(4);
      expect(keys[3], "اختيارٌ جديدٌ حمل مفتاحَ الاختيارِ السابق")
        .not.toBe(keys[0]);
    });

  test("the AI attachment retries the SAME File and keeps its key, then a new selection mints another",
    async ({ page }) => {
      await register(page);
      // بوّابةُ النموذج تُفتح بإعلانِ جاهزيّةٍ مصطنع — والمرفقُ هو المفحوص.
      await page.route("**/api/v1/settings/posture", (route) => route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({ items: [
          { key: "model_provider", label: "p", value: "openai", detail: "" },
          { key: "literature_registry", label: "l", value: "online", detail: "" },
        ] }),
      }));
      const keys: string[] = [];
      let n = 0;
      await page.route("**/api/v1/files/upload", async (route) => {
        if (route.request().method() !== "POST") { await route.continue(); return; }
        n += 1;
        const key = route.request().headers()["idempotency-key"] ?? "";
        if (n <= 2) {
          await route.fulfill({ status: 503, contentType: "application/json",
            body: JSON.stringify({ error: { code: "server.error", locale: "ar",
              message: "x", messages: { ar: "x", en: "x" } } }) });
        } else {
          await route.fulfill({ status: 201, contentType: "application/json",
            body: JSON.stringify({
              id: "99999999-9999-4999-8999-999999999999",
              original_filename: "attach-a.txt",
            }) });
        }
        keys.push(key);
      });

      await page.goto(`/${LOCALE}/ai`);
      const input = page.locator('input[type="file"]').first();
      await input.waitFor({ state: "attached", timeout: 30_000 });
      await input.setInputFiles([synthetic("attach-a.txt")]);
      await expect.poll(() => keys.length, { timeout: 30_000 }).toBe(1);
      expect(keys[0]).toMatch(KEY);

      const retry = page.getByTestId("ai-attachment-retry");
      await retry.waitFor({ state: "visible", timeout: 30_000 });
      await retry.click();
      await expect.poll(() => keys.length, { timeout: 30_000 }).toBe(2);
      expect(keys[1], "إعادةُ المرفقِ نفسِه ولّدت مفتاحًا ثانيًا").toBe(keys[0]);

      await retry.click();
      await expect.poll(() => keys.length, { timeout: 30_000 }).toBe(3);
      expect(keys[2]).toBe(keys[0]);
      // نجاحٌ يحسم النيّة: الزرُّ يذهب، والمرفقُ يُعلَن.
      await expect(page.getByTestId("ai-attachment")).toBeVisible({ timeout: 30_000 });
      await expect(retry).toBeHidden({ timeout: 30_000 });

      await input.setInputFiles([synthetic("attach-b.txt")]);
      await expect.poll(() => keys.length, { timeout: 30_000 }).toBe(4);
      expect(keys[3], "مرفقٌ جديدٌ حمل مفتاحَ سابقه").not.toBe(keys[0]);
    });
});
