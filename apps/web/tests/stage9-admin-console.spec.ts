import { createHmac } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { ADMIN_ROLE_KEYS, hasAdminRole } from "../src/lib/admin";

/**
 * لوحة الإدارة V1 في متصفّحٍ حقيقيّ | Stage 9 — real API, real database, real MFA.
 *
 * **ولا تُطفأ سياسةُ MFA لتسهيل الفحص.** المديرُ يُسجَّل من الواجهة، ثمّ يُمنح
 * دورًا إداريًّا وعاملَ TOTP مؤكَّدًا في قاعدته (لا مسارَ منحٍ في المنتج — ذاك
 * للمرحلة ١٠)، ثمّ يدخل من الواجهة نفسِها **برمزٍ يُحسب هنا** بخوارزميّة RFC 6238.
 * فالخادمُ يرفض دخولَه بلا رمز، كما يرفضه في الإنتاج.
 *
 * وموضعُ هذه الرقعة RC E2E لا `ci.yml`: تحتاج API وقاعدةً حيّين.
 */

const SECRET = "JBSWY3DPEHPK3PXP";
const PASSWORD = "Stage9-Passw0rd!";
const RESEARCH_TEXT = "HIPPOCAMPAL-TRIAL-ARM-B-9127";
const API_DIR = join(process.cwd(), "..", "api");
const PYTHON = process.env.PUBRIVA_API_PYTHON ?? "python";

let seq = 0;
const email = (tag: string) => `s9-${tag}-${Date.now()}-${(seq += 1)}@fixtures.athera`;

function seed(...args: string[]): string {
  return execFileSync(PYTHON, ["-m", "tests.stage9_admin_seed", ...args],
    { cwd: API_DIR, env: process.env, encoding: "utf-8" });
}

/** TOTP بحسب RFC 6238 — HMAC-SHA1، ونافذةُ ثلاثين ثانية، وستّةُ أرقام. */
function totp(secret: string, at = Date.now()): string {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const ch of secret.replace(/=+$/, "")) {
    bits += alphabet.indexOf(ch).toString(2).padStart(5, "0");
  }
  const key = Buffer.from(bits.match(/.{8}/g)!.map((b) => parseInt(b, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(at / 1000 / 30)));
  const mac = createHmac("sha1", key).update(counter).digest();
  const offset = mac[mac.length - 1] & 0x0f;
  const code = (mac.readUInt32BE(offset) & 0x7fffffff) % 1_000_000;
  return code.toString().padStart(6, "0");
}

async function register(page: Page, address: string, locale = "ar") {
  await page.goto(`/${locale}/register`);
  await page.locator("#reg-name").fill("Stage Nine");
  await page.locator("#reg-email").fill(address);
  await page.locator("#reg-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").click();
  await page.waitForURL(new RegExp(`/${locale}$`), { timeout: 60_000 });
}

async function signOut(page: Page) {
  await page.evaluate(() => window.sessionStorage.clear());
}

/** دخولٌ من الواجهة — بكلمته، ثمّ **برمز TOTP حين يطلبه الخادم**. */
async function adminLogin(page: Page, address: string, locale = "ar") {
  await signOut(page);
  await page.goto(`/${locale}/login`);
  await page.locator("input[type=email]").fill(address);
  await page.locator("#login-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").click();
  await expect(page.getByTestId("login-mfa-step")).toBeVisible({ timeout: 30_000 });
  await page.locator('input[autocomplete="one-time-code"]').fill(totp(SECRET));
  await page.locator("form button[type=submit]").click();
  await page.waitForURL(new RegExp(`/${locale}$`), { timeout: 60_000 });
}

/** مديرٌ حقيقيٌّ بمساحته — وباحثٌ في مساحةٍ أخرى لا يراه. */
async function freshAdmin(page: Page, locale = "ar") {
  const admin = email("admin");
  await register(page, admin, locale);
  seed("grant", admin, "system_admin", SECRET);
  await adminLogin(page, admin, locale);
  return admin;
}

const adminNav = (page: Page) => page.getByRole("link", { name: /لوحة الإدارة|Admin console/ });

// ═════════════════════════════ ١ · الرابطُ والحارس ═════════════════════════════

test.describe("Stage 9 — admin navigation is derived from canonical RBAC", () => {
  test("the browser admin role list equals rbac.ADMIN_ROLE_KEYS", () => {
    const source = readFileSync(join(API_DIR, "athera_api", "services", "rbac.py"), "utf-8");
    const match = /ADMIN_ROLE_KEYS[^=]*=\s*frozenset\(\{([^}]*)\}\)/.exec(source);
    expect(match, "لم يُقرأ ADMIN_ROLE_KEYS من المصدر").not.toBeNull();
    const canonical = [...match![1].matchAll(/"([a-z_]+)"/g)].map((m) => m[1]).sort();
    expect([...ADMIN_ROLE_KEYS].sort(), "دورٌ إداريٌّ في المصدر غائبٌ عن الرابط").toEqual(canonical);
  });

  test("the link shows for every admin role and no other role", () => {
    for (const role of ["research_admin", "college_admin", "institution_admin", "system_admin"]) {
      expect(hasAdminRole([role]), role).toBe(true);
    }
    for (const role of ["researcher", "student", "co_author", "supervisor", "internal_reviewer"]) {
      expect(hasAdminRole([role]), role).toBe(false);
    }
  });
});

test.describe("Stage 9 — the admin console on the real stack", () => {
  test("a researcher sees no admin link, and typing the URL reveals no data", async ({ page }) => {
    await register(page, email("researcher"));
    await expect(page.getByRole("link", { name: /الإعدادات/ }).first()).toBeVisible({ timeout: 30_000 });
    await expect(adminNav(page)).toHaveCount(0);

    await page.goto("/ar/admin");
    await expect(page.getByTestId("admin-forbidden")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("admin-overview-cards")).toHaveCount(0);
    await page.goto("/ar/admin/users");
    await expect(page.getByTestId("admin-forbidden")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("admin-users-table")).toHaveCount(0);
  });

  test("an admin (with real MFA) sees the link, the overview and its workspace scope",
    async ({ page }) => {
      await freshAdmin(page);
      await expect(adminNav(page)).toBeVisible({ timeout: 30_000 });
      await adminNav(page).click();
      await page.waitForURL(/\/ar\/admin$/);
      await expect(page.getByRole("heading", { name: "لوحة إدارة PUBRIVA" })).toBeVisible();
      await expect(page.getByTestId("admin-scope")).toContainText(
        "تعرض هذه اللوحة بيانات مساحة العمل الحالية فقط.");
      await expect(page.getByTestId("admin-scope")).toContainText("مساحة العمل الحالية");
      await expect(page.getByTestId("card-members")).toContainText("١");
      // والشكلُ يمينيّ: الصفحةُ عربيّةٌ والاتّجاهُ منها.
      expect(await page.evaluate(() => document.documentElement.dir)).toBe("rtl");
    });

  test("search finds a member and never a user of another workspace", async ({ page }) => {
    const outsider = email("outsider");
    await register(page, outsider);
    const admin = await freshAdmin(page);
    const colleague = email("colleague");
    seed("member", admin, colleague, "supervisor", "true");

    await page.goto("/ar/admin/users");
    await expect(page.getByTestId("admin-users-table")).toBeVisible({ timeout: 30_000 });
    await page.getByLabel("ابحث بالاسم أو البريد").fill(colleague);
    await page.getByTestId("admin-users-apply").click();
    await expect(page.getByTestId("admin-user-row")).toHaveCount(1);
    await expect(page.getByTestId("admin-user-row")).toContainText(colleague);

    await page.getByLabel("ابحث بالاسم أو البريد").fill(outsider);
    await page.getByTestId("admin-users-apply").click();
    await expect(page.getByTestId("admin-users-empty")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator("body")).not.toContainText(outsider);
  });

  test("role and status filters narrow the member list", async ({ page }) => {
    const admin = await freshAdmin(page);
    const sup = email("sup");
    const idle = email("idle");
    seed("member", admin, sup, "supervisor", "true");
    seed("member", admin, idle, "researcher", "false");

    await page.goto("/ar/admin/users");
    await expect(page.getByTestId("admin-user-row")).toHaveCount(3, { timeout: 30_000 });
    await page.getByLabel("الدور").selectOption("supervisor");
    await page.getByTestId("admin-users-apply").click();
    await expect(page.getByTestId("admin-user-row")).toHaveCount(1);
    await expect(page.getByTestId("admin-user-row")).toContainText(sup);

    await page.getByLabel("الدور").selectOption("");
    await page.getByLabel("حالة الحساب").selectOption("inactive");
    await page.getByTestId("admin-users-apply").click();
    await expect(page.getByTestId("admin-user-row")).toHaveCount(1);
    await expect(page.getByTestId("admin-user-row")).toContainText(idle);
    // ولا زرَّ تعطيلٍ ولا انتحالٍ ولا تعديلِ دور.
    await expect(page.getByRole("button", { name: /تعطيل|انتحال|disable|impersonat/i })).toHaveCount(0);
    await expect(page.locator("select").filter({ hasText: /مدير النظام/ })).toHaveCount(1);
  });

  test("projects list its own workspace and not another's", async ({ page }) => {
    const other = email("other");
    await register(page, other);
    seed("project", other, "مشروعُ مساحةٍ أخرى");
    const admin = await freshAdmin(page);
    seed("project", admin, "مشروعُ هذه المساحة");

    await page.goto("/ar/admin/projects");
    await expect(page.getByTestId("admin-project-row")).toHaveCount(1, { timeout: 30_000 });
    await expect(page.getByTestId("admin-project-row")).toContainText("مشروعُ هذه المساحة");
    await expect(page.locator("body")).not.toContainText("مشروعُ مساحةٍ أخرى");
  });

  test("usage shows the seeded 30-day totals and names the missing cost honestly",
    async ({ page }) => {
      const admin = await freshAdmin(page);
      seed("activity", admin, RESEARCH_TEXT);
      await page.goto("/ar/admin/usage");
      await expect(page.getByTestId("usage-model-runs")).toHaveText("٣", { timeout: 30_000 });
      await expect(page.getByTestId("usage-input-tokens")).toHaveText("٣٥٠");
      await expect(page.getByTestId("usage-output-tokens")).toHaveText("٩٠");
      // والأرقامُ عربيّةٌ في الصفحة العربيّة — ٠٫١٦ لا 0.16، بلا تقريبٍ يُذهب السنتات.
      await expect(page.getByTestId("cost-value")).toContainText("٠٫١٦");
      await expect(page.getByTestId("cost-coverage")).toContainText("٢ من ٣");
      await expect(page.getByTestId("usage-by-provider")).toBeVisible();
    });

  test("a workspace with runs but no recorded cost says so instead of $0.00", async ({ page }) => {
    const admin = await freshAdmin(page);
    await page.route("**/api/v1/admin/usage**", async (route) => {
      const real = await route.fetch();
      const body = await real.json();
      body.summary = { ...body.summary, model_runs: 2, runs_with_cost: 0, runs_without_cost: 2,
        recorded_cost_usd: "0" };
      await route.fulfill({ response: real, json: body });
    });
    void admin;
    await page.goto("/ar/admin/usage");
    await expect(page.getByTestId("cost-not-recorded")).toHaveText(
      "التكلفة غير مسجّلة لهذه التشغيلات.", { timeout: 30_000 });
    await expect(page.getByTestId("usage-cost")).not.toContainText("0.00");
  });

  test("operations show the failure as metadata — never the research payload", async ({ page }) => {
    const admin = await freshAdmin(page);
    seed("activity", admin, RESEARCH_TEXT);
    await page.goto("/ar/admin/operations");
    await expect(page.getByTestId("ops-agent-row").first()).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("ops-tool-row").first()).toContainText("سُجّل خطأ");
    await expect(page.getByTestId("ops-model-row").first()).toBeVisible();
    await expect(page.locator("body")).not.toContainText(RESEARCH_TEXT);
  });

  test("no zero is shown before the overview has answered", async ({ page }) => {
    await freshAdmin(page);
    let release: () => void = () => {};
    const held = new Promise<void>((resolve) => { release = resolve; });
    await page.route("**/api/v1/admin/overview", async (route) => {
      await held;
      await route.continue();
    });
    await page.goto("/ar/admin");
    await expect(page.getByTestId("admin-loading")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("admin-overview-cards")).toHaveCount(0);
    await expect(page.locator("body")).not.toContainText("٠ ");
    release();
    await expect(page.getByTestId("admin-overview-cards")).toBeVisible({ timeout: 30_000 });
  });

  test("a failed request is shown as an error, never as an empty list", async ({ page }) => {
    await freshAdmin(page);
    await page.route("**/api/v1/admin/users**", (route) => route.fulfill({
      status: 503, contentType: "application/json",
      body: JSON.stringify({ error: { code: "server.error", locale: "ar", message: "تعذّر",
        messages: { ar: "تعذّر الوصول", en: "Unavailable" } } }),
    }));
    await page.goto("/ar/admin/users");
    await expect(page.getByTestId("admin-error")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("admin-users-empty")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "أعد المحاولة" })).toBeVisible();
  });

  test("the console speaks English left-to-right and Arabic right-to-left", async ({ page }) => {
    const admin = await freshAdmin(page, "en");
    seed("activity", admin, RESEARCH_TEXT);
    const pages: Array<[string, RegExp]> = [
      ["/en/admin", /Overview/], ["/en/admin/users", /Users/],
      ["/en/admin/projects", /Projects/], ["/en/admin/usage", /AI usage/],
      ["/en/admin/operations", /Operations/],
    ];
    for (const [url, tab] of pages) {
      await page.goto(url);
      await expect(page.getByTestId("admin-scope")).toContainText(
        "This console shows data for the current workspace only.", { timeout: 30_000 });
      await expect(page.getByRole("navigation", { name: "Admin console sections" })
        .getByRole("link", { name: tab })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.dir)).toBe("ltr");
    }
    await expect(page.getByRole("link", { name: "Admin console" })).toBeVisible();

    for (const url of ["/ar/admin", "/ar/admin/users", "/ar/admin/projects",
      "/ar/admin/usage", "/ar/admin/operations"]) {
      await page.goto(url);
      await expect(page.getByTestId("admin-scope")).toContainText("مساحة العمل الحالية فقط",
        { timeout: 30_000 });
      expect(await page.evaluate(() => document.documentElement.dir)).toBe("rtl");
    }
    await expect(page.getByRole("link", { name: "لوحة الإدارة" })).toBeVisible();
  });
});
