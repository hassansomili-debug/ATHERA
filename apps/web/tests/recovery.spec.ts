import { expect, test } from "@playwright/test";

/**
 * آليّات الاستعادة في المتصفح | Recovery UI mechanics.
 *
 * **بلا رمزٍ حقيقي.** الرمز الحقيقي يصل بريدًا، وإدخاله هنا يضعه في أثر
 * التشغيلة — وهو بالضبط ما وقع مرّة وأُصلح. فتُفحص الآليّات: أن الجواب
 * واحد، وأن الرمز يُقرأ من الجزء ولا يُعرض، وأنه يُنزع من شريط العنوان.
 *
 * والمسجّلات مُطفأة هنا أيضًا احتياطًا: الشاشة تحمل حقول كلمة مرور، وما
 * يُكتب فيها يُسجَّل في الأثر.
 */
test.use({ trace: "off", video: "off", screenshot: "off" });

const LOCALE = "ar";

test("the login page offers a recovery path", async ({ page }) => {
  await page.goto(`/${LOCALE}/login`);
  const link = page.getByRole("link", { name: /نسيت كلمة المرور/ });
  await expect(link).toBeVisible();
  await link.click();
  await page.waitForURL(/\/forgot-password/);
  await expect(page.getByRole("heading", { name: /نسيت كلمة المرور/ })).toBeVisible();
});

test("the answer is identical for any email, revealing nothing", async ({ page }) => {
  const seen: string[] = [];

  // الخادم يُقلَّد هنا: المقصود فحصُ أن الشاشة تعرض جوابه كما هو، لا أن
  // تخترع نصًّا يفرّق بين حالٍ وحال.
  await page.route("**/api/v1/auth/forgot-password", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        message_ar: "إذا كان البريد مرتبطًا بحساب، فستصلك رسالة لإعادة تعيين كلمة المرور.",
        message_en: "If that email is linked to an account, a password reset message is on its way.",
      }),
    }),
  );

  for (const email of ["known@fixtures.athera", "absent@fixtures.athera"]) {
    await page.goto(`/${LOCALE}/forgot-password`);
    await page.getByLabel(/البريد/).fill(email);
    await page.getByRole("button", { name: /أرسل رابط الاستعادة/ }).click();
    const sent = page.getByTestId("forgot-sent");
    await expect(sent).toBeVisible({ timeout: 15_000 });
    seen.push((await sent.innerText()).trim());
  }

  expect(seen[0]).toBe(seen[1]);
  expect(seen[0]).toContain("إذا كان البريد مرتبطًا بحساب");
});

test("the reset token is read from the fragment, never shown, and stripped", async ({ page }) => {
  // رمزٌ صوريّ: لا يبلغ خادمًا، ولا يفتح شيئًا.
  const placeholder = "fragment-mechanics-check";
  await page.goto(`/${LOCALE}/reset-password#token=${placeholder}`);

  // النموذج ظهر — أي أن الرمز قُرئ من الجزء.
  await expect(page.getByLabel("كلمة المرور الجديدة")).toBeVisible();

  // **ولا يُعرض في الصفحة.**
  expect(await page.locator("body").innerText()).not.toContain(placeholder);

  // **ويُنزع من شريط العنوان**، فلا يبقى في تاريخ المتصفح ولا في لقطة شاشة.
  await expect.poll(() => page.url()).not.toContain(placeholder);
  expect(await page.evaluate(() => window.location.hash)).toBe("");
});

test("a link with no token says so instead of failing after submit", async ({ page }) => {
  await page.goto(`/${LOCALE}/reset-password`);
  await expect(page.getByTestId("reset-no-token")).toBeVisible();
  await expect(page.getByLabel("كلمة المرور الجديدة")).toHaveCount(0);
});

test("the reset form refuses a weak or mismatched password before sending", async ({ page }) => {
  await page.goto(`/${LOCALE}/reset-password#token=fragment-mechanics-check`);
  const submit = page.getByRole("button", { name: /احفظ كلمة المرور الجديدة/ });

  await page.getByLabel("كلمة المرور الجديدة").fill("short");
  await expect(submit).toBeDisabled();

  await page.getByLabel("كلمة المرور الجديدة").fill("a-long-enough-password");
  await page.getByLabel("تأكيد كلمة المرور الجديدة").fill("different-password-xx");
  await expect(page.getByTestId("reset-mismatch")).toBeVisible();
  await expect(submit).toBeDisabled();
});
