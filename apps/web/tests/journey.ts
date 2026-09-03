import { expect, type Page } from "@playwright/test";

/**
 * أدوات الرحلة | Journey helpers.
 *
 * **الوجهة بعد الدخول تُعرَّف مرّة واحدة.** وكان الفحص يستعمل
 * `new RegExp("/ar(\\?|$|/)")` على الرابط كاملًا — و`/ar/login?next=%2Far`
 * يطابقها، وكذلك `/ar/portfolio`. فكان الشرط يمرّ والصفحة ما زالت على
 * الدخول، ويُعلَن نجاح خطوةٍ لم تقع. ثم يظهر الفشل بعد خطوتين في موضعٍ
 * بريء، فيُبحث عن العلّة حيث ليست.
 *
 * فيُشتقّ الشرط من موضعٍ واحد يستعمله الفحص وحارسه معًا — ولا يفترقان.
 */
export const LOCALE = "ar";

/** الوجهة الوحيدة المقبولة بعد دخولٍ ناجح: جذر اللغة، لا شيء تحته. */
export function isSignedInDestination(url: URL): boolean {
  return url.pathname === `/${LOCALE}` || url.pathname === `/${LOCALE}/`;
}

/**
 * دخولٌ يُثبت نفسه بثلاثة شواهد — **ولا يكتفي بشكل الرابط**:
 *
 *   ١ ردّ الخادم على `POST /auth/login` وصل، وحالته ٢٠٠
 *   ٢ المسار صار جذر اللغة بالضبط
 *   ٣ رمز الوصول محفوظ فعلًا
 *
 * والشاهد الأول هو المهم: كان الفحص يبدأ التنقّل قبل أن يردّ الدخول،
 * فيُجهض الطلب (status -1) ويُعيد `AuthGate` التوجيه إلى الدخول — وهو
 * تصرّفٌ صحيح من المنتج على حالةٍ صنعها الفحص. فيُنتظر الردّ أولًا.
 */
export async function signIn(page: Page, email: string, password: string): Promise<void> {
  const loginResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/auth/login") &&
      response.request().method() === "POST",
    { timeout: 60_000 },
  );

  await page.getByLabel(/البريد|email/i).fill(email);
  await page.getByLabel(/كلمة المرور|password/i).first().fill(password);
  await page.getByRole("button", { name: /دخول|sign in/i }).click();

  const response = await loginResponse;
  expect(
    response.status(),
    `login returned ${response.status()} — the sign-in step itself failed`,
  ).toBe(200);

  await page.waitForURL((url) => isSignedInDestination(url), { timeout: 30_000 });

  expect(
    await page.evaluate(() => Boolean(localStorage.getItem("athera_access_token"))),
    "no access token was stored after a 200 login",
  ).toBe(true);
}
