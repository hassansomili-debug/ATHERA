import { defineConfig, devices } from "@playwright/test";

/**
 * قبولٌ بمتصفّح حقيقي | Real-browser acceptance.
 *
 * **وصفحةٌ تُصيَّر ليست منتجًا يعمل.** فحصُ HTML يثبت أن الترميز وصل، ولا
 * يثبت أن الزرّ يعمل ولا أن الجلسة تصمد. ولهذا لا يُستبدل هذا الملف بفحص
 * شبكةٍ ولا بفحص واجهة برمجية.
 *
 * وهذا الملف واختباراته خارج `tsconfig` عمدًا: حزمتهما تُثبَّت في مهمّة
 * المتصفح وحدها، فلا يكسر استيرادُها فحصَ أنواع التطبيق.
 *
 * والهدف يُضبط بمتغيّر: محليًّا خادم التطوير، وفي CI البناء الحقيقي، وعند
 * القبول النهائي عنوان الإنتاج.
 */
const BASE = process.env.PUBRIVA_WEB_URL ?? "http://127.0.0.1:3000";
const usingLocalServer = BASE.startsWith("http://127.0.0.1") || BASE.startsWith("http://localhost");

/**
 * خادمٌ يبدأ **خارج** Playwright — لبيئة المرشَّح للإصدار (rc-e2e).
 *
 * تلك المهمّة تبني الوِب بنفسها بـ`NEXT_PUBLIC_API_BASE_URL` يشير إلى
 * الـAPI الذي أقلعته في الخطوة السابقة، ثم تُشغّله. ولو تولّى Playwright
 * الإقلاع أيضًا لاصطدم بمنفذٍ مشغول: `reuseExistingServer` مُطفأ في CI
 * عمدًا، فيسقط التشغيل قبل أن يبدأ. فيُقال له صراحةً إنّ الخادم قائم.
 *
 * ولا يتغيّر شيء لبقية المهام: المتغيّر غير مضبوط عندها، والسلوك كما كان.
 */
const externalServer = process.env.PUBRIVA_WEB_SERVER === "external";

export default defineConfig({
  testDir: "./tests",
  // التوازي مُطفأ: رحلة القبول تُنشئ بحوثًا وتحذفها، وتداخلها يُنتج فشلًا
  // متقطّعًا لا علاقة له بالمنتج.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: BASE,
    locale: "ar",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: usingLocalServer && !externalServer
    ? {
        command: "npm run build && npm run start",
        url: BASE,
        reuseExistingServer: !process.env.CI,
        timeout: 180_000,
      }
    : undefined,
});
