import { expect, test, type Page } from "@playwright/test";

/**
 * دورة حياة الجلسة | The session lifecycle — in a real browser.
 *
 * **رمز الوصول يعيش تسعمئة ثانية.** وكان كل 401 يمحو الجلسة ويقذف الباحث
 * إلى صفحة الدخول، ورمز التحديث في المخزن لم يُستعمل قط — فباحثٌ يكتب
 * ورقته يُطرد كل ربع ساعة. هذه الاختبارات تحرس ألّا يعود ذلك.
 *
 * والشبكة تُعترض هنا لا تُحاكى بدوالّ: الاختبار يمرّ بـ`fetch` الحقيقي
 * وبـ`localStorage` الحقيقي وبإعادة التوجيه الحقيقية.
 */

const LOCALE = "ar";
const API = "**/api/v1";

/** جلسةٌ مزروعة قبل تحميل أي صفحة — كما لو دخل الباحث للتوّ. */
async function seedSession(page: Page, opts: { expired?: boolean } = {}) {
  await page.addInitScript((expired) => {
    localStorage.setItem("athera_access_token", "access-v1");
    localStorage.setItem("athera_refresh_token", "refresh-v1");
    localStorage.setItem(
      "athera_token_expiry",
      String(Date.now() + (expired ? -1000 : 900_000)),
    );
  }, Boolean(opts.expired));
}

/** كل ما تحتاجه الشاشة لتُصيَّر، عدا ما يخصّه الاختبار. */
async function stubBaseline(page: Page) {
  await page.route("**/api/v1/settings/posture", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [{ key: "model_provider", label: "", value: "anthropic", detail: "" }] }),
    }),
  );
}

test.describe("session lifecycle", () => {
  test("a valid access token is used and never refreshed", async ({ page }) => {
    await seedSession(page);
    let refreshCalls = 0;
    let authorized = "";
    await page.route("**/api/v1/auth/refresh", (route) => {
      refreshCalls += 1;
      return route.fulfill({ status: 200, body: "{}" });
    });
    await page.route("**/api/v1/settings/posture", (route) => {
      authorized = route.request().headers()["authorization"] ?? "";
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [] }),
      });
    });

    await page.goto(`/${LOCALE}`);
    await expect(page).toHaveURL(new RegExp(`/${LOCALE}$`));
    expect(authorized).toBe("Bearer access-v1");
    expect(refreshCalls).toBe(0);
  });

  test("an expired access token is refreshed once and the request replayed once", async ({ page }) => {
    await seedSession(page, { expired: true });
    let refreshCalls = 0;
    const postureAuth: string[] = [];

    await page.route("**/api/v1/auth/refresh", async (route) => {
      refreshCalls += 1;
      const body = JSON.parse(route.request().postData() ?? "{}");
      expect(body.refresh_token).toBe("refresh-v1");
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        // **الرمزان يدوران معًا** — وحفظ الوصول وحده يترك تحديثًا مُبطَلًا.
        body: JSON.stringify({
          access_token: "access-v2",
          refresh_token: "refresh-v2",
          token_type: "bearer",
          expires_in: 900,
        }),
      });
    });

    await page.route("**/api/v1/settings/posture", (route) => {
      const auth = route.request().headers()["authorization"] ?? "";
      postureAuth.push(auth);
      if (auth === "Bearer access-v1") {
        return route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ error: { code: "auth.invalid_token", locale: "ar", message: "", messages: {} } }),
        });
      }
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [] }) });
    });

    await page.goto(`/${LOCALE}`);
    await expect.poll(() => postureAuth.length).toBeGreaterThanOrEqual(2);

    expect(refreshCalls).toBe(1);
    expect(postureAuth[0]).toBe("Bearer access-v1");
    expect(postureAuth[1]).toBe("Bearer access-v2");
    // ولم يُطرد الباحث.
    await expect(page).not.toHaveURL(/login/);
    // والرمزان المُدوَّران محفوظان كلاهما.
    expect(await page.evaluate(() => localStorage.getItem("athera_access_token"))).toBe("access-v2");
    expect(await page.evaluate(() => localStorage.getItem("athera_refresh_token"))).toBe("refresh-v2");
  });

  test("a failed refresh clears the session and lands on login exactly once", async ({ page }) => {
    await seedSession(page, { expired: true });
    let refreshCalls = 0;
    await page.route("**/api/v1/auth/refresh", (route) => {
      refreshCalls += 1;
      return route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ error: { code: "auth.invalid_token", locale: "ar", message: "", messages: {} } }),
      });
    });
    await page.route("**/api/v1/settings/posture", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ error: { code: "auth.invalid_token", locale: "ar", message: "", messages: {} } }),
      }),
    );

    await page.goto(`/${LOCALE}`);
    await page.waitForURL(/\/login/);
    // **ولا حلقة**: التجديد يُجرَّب مرّة، لا مرّة لكل محاولة.
    expect(refreshCalls).toBe(1);
    expect(await page.evaluate(() => localStorage.getItem("athera_access_token"))).toBeNull();
    expect(await page.evaluate(() => localStorage.getItem("athera_refresh_token"))).toBeNull();
  });

  test("concurrent 401s consume the rotating refresh token exactly once", async ({ page }) => {
    // **الاختبار على شاشة تُطلق ثلاثة نداءات معًا.** مساحة عمل البحث تقرأ
    // النظرة العامة والملفات والمراجع في وقتٍ واحد — وهي النافذة التي كانت
    // الطلبات تتزاحم فيها على رمز تحديثٍ يدور، فيفوز واحدٌ ويُطرد الباقون.
    await seedSession(page, { expired: true });
    let refreshCalls = 0;
    const consumed: string[] = [];
    const firstRound: string[] = [];

    await page.route("**/api/v1/auth/refresh", async (route) => {
      refreshCalls += 1;
      consumed.push(JSON.parse(route.request().postData() ?? "{}").refresh_token);
      // تأخيرٌ متعمَّد يوسّع نافذة التزاحم.
      await new Promise((r) => setTimeout(r, 400));
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: "access-v2",
          refresh_token: "refresh-v2",
          token_type: "bearer",
          expires_in: 900,
        }),
      });
    });

    await page.route("**/api/v1/workspace/**", (route) => {
      const auth = route.request().headers()["authorization"] ?? "";
      if (auth === "Bearer access-v1") {
        firstRound.push(route.request().url());
        return route.fulfill({
          status: 401,
          contentType: "application/json",
          body: JSON.stringify({ error: { code: "auth.invalid_token", locale: "ar", message: "", messages: {} } }),
        });
      }
      const url = route.request().url();
      const body = url.includes("/overview")
        ? JSON.stringify({
            project: { id: "p1", title_ar: "بحث", status: "planned", created_at: new Date().toISOString(),
                       archived_at: null, deleted_at: null, files: 0, sources: 0, verified_facts: 0, manuscripts: 0 },
            brain: [], recommended_next: null, blockers: [], note: "",
          })
        : "[]";
      return route.fulfill({ status: 200, contentType: "application/json", body });
    });
    await stubBaseline(page);

    await page.goto(`/${LOCALE}/portfolio/p1`);

    // ثلاثة نداءات على الأقل اصطدمت بـ401 في اللحظة نفسها…
    await expect.poll(() => firstRound.length, { timeout: 15_000 }).toBeGreaterThanOrEqual(2);
    // …ومع ذلك لم يُستهلك رمز التحديث إلا مرّة واحدة.
    await expect.poll(() => refreshCalls, { timeout: 15_000 }).toBe(1);
    expect(consumed).toEqual(["refresh-v1"]);
    await expect(page).not.toHaveURL(/login/);
  });

  test("the login page never redirects to itself", async ({ page }) => {
    // بلا جلسة إطلاقًا: الحدّ يرسل إلى الدخول، والدخول لا يرسل إلى نفسه.
    const visits: string[] = [];
    page.on("framenavigated", (f) => {
      if (f === page.mainFrame()) visits.push(f.url());
    });
    await stubBaseline(page);
    await page.goto(`/${LOCALE}`);
    await page.waitForURL(/\/login/);
    await page.waitForTimeout(1500);
    const loginVisits = visits.filter((u) => u.includes("/login"));
    expect(loginVisits.length).toBeLessThanOrEqual(2);
  });

  test("an unauthenticated visitor is sent to login before any workspace renders", async ({ page }) => {
    await stubBaseline(page);
    await page.goto(`/${LOCALE}/portfolio`);
    await page.waitForURL(/\/login/);
    // والوجهة محفوظة، فيعود إلى ما قصده.
    expect(page.url()).toContain("next=");
  });
});
