import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * تجربةُ الهويّة | The brand experience — ثلاثُ قشورٍ لا واحدة.
 *
 * **ما تحرسه هذه الرقعة أعطابٌ وقعت، لا مبادئ عامّة:**
 *
 *   ١ الجذرُ كان أربعمئة وأربعة، ثمّ تحويلًا إلى نموذج دخولٍ لمنتجٍ لا
 *     يعرف الزائر ما هو. فيُثبَت أن `/` صفحةٌ عامّة تُقرأ باللغتين.
 *   ٢ وصفحاتُ الحساب كانت تُصيَّر داخل هيكل التطبيق بشريطه الجانبي —
 *     ثلاثةَ عشر رابطًا خلف مصادقةٍ لم تقع. فيُثبَت غيابُ الشريط عنها،
 *     **ووجودُه في مساحة العمل**: الفحص من طرفيه، وإلّا قَبِل الحذفَ
 *     مكانَ الفصل.
 *   ٣ والنشطُ واحدٌ في القائمة — دعوى الموجة الأولى، تُعاد هنا لأن الهيكل
 *     نُقل ونُقلت معه القائمة.
 *   ٤ واللونُ لا يحمل معنى وحده: أربعُ حالاتٍ لكلٍّ لونُها، ولكلٍّ اسمُها
 *     مكتوبًا. فتُقرأ الألوان من المتصفّح وتُقارَن، ويُقرأ النصّ معها.
 *   ٥ ولا اسمَ داخليًّا على سطحٍ عام.
 *
 * **وطبقتها طبقةُ `product-surface`**: بناءٌ محلّي لشيفرة هذا الفرع،
 * وشبكةٌ معترَضة، وبلا اعتمادٍ إطلاقًا — ولا تُقرأ `PUBRIVA_ACCEPT_*` ولا
 * أيُّ سرّ. فتعمل في كل PR.
 */

const AR = "ar";
const EN = "en";

/** اسمُ المنتج كما في الكتالوجين — لا مترادفات. */
const NAME_AR = "بُبريفا";
const NAME_EN = "PUBRIVA";

/** أسماءٌ داخليّة لا يجوز أن تُرى على سطحٍ عام. */
const INTERNAL_NAMES = ["athera", "أثيرا"];

/** اسمُ منطقةِ التنقّل في الهيكل — `nav.primaryLabel`. */
const NAV_LABEL_AR = "التنقّل الرئيسي";

const APP_ORIGIN = new URL(process.env.PUBRIVA_WEB_URL ?? "http://127.0.0.1:3000").origin;

interface Seen {
  errors: string[];
  serverErrors: string[];
}

function watch(page: Page): Seen {
  const seen: Seen = { errors: [], serverErrors: [] };
  page.on("pageerror", (error) => seen.errors.push(String(error)));
  page.on("response", (response) => {
    if (new URL(response.url()).origin !== APP_ORIGIN) return;
    if (response.status() >= 500) seen.serverErrors.push(`${response.status()} ${response.url()}`);
  });
  return seen;
}

/** جلسةٌ مزروعة — رموزٌ مصطنعة، ولا اعتمادَ حقيقيًّا بحال. */
async function seedSession(page: Page) {
  await page.addInitScript(() => {
    if (sessionStorage.getItem("__seeded_brand")) return;
    sessionStorage.setItem("__seeded_brand", "1");
    localStorage.setItem("athera_access_token", "brand-access");
    localStorage.setItem("athera_refresh_token", "brand-refresh");
    localStorage.setItem("athera_token_expiry", String(Date.now() + 900_000));
  });
}

const POSTURE = {
  tenant_name: "فحص الهويّة",
  locale: AR,
  supported_locales: [AR, EN],
  roles: [],
  items: [],
};

/** مقترَحٌ مصطنع: الحالُ هي ما تُفحص لا محتواها. */
const FACT_CANDIDATES = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    memory_category: "method",
    statement: "عيّنةٌ مصطنعة لفحص الهويّة.",
    quote: "نصٌّ مصطنع لا مصدر له خارج هذا الفحص.",
    locator: "ص ١",
    confidence: null,
    status: "unknown",
  },
];

const OBJECT_BODIES = new Map<string, unknown>([
  ["/api/v1/settings/posture", POSTURE],
  [
    "/api/v1/inbox/summary",
    { pending_approvals: 0, open_alerts: 0, blocking_alerts: 0, unread_notifications: 0 },
  ],
  ["/api/v1/profile/facts", FACT_CANDIDATES],
]);

/** كلُّ نداءٍ يُجاب — نداءٌ معلَّق يُبقي «جارٍ التحميل» فيسقط الفحص على الشبكة. */
async function stubApi(page: Page) {
  await page.route("**/api/v1/**", (route: Route) => {
    const path = new URL(route.request().url()).pathname;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(OBJECT_BODIES.has(path) ? OBJECT_BODIES.get(path) : []),
    });
  });
}

/** تمريرٌ أفقيّ للمستند — واحدُ بكسلٍ يُغتفر للتقريب. */
async function sidewaysOverflow(page: Page): Promise<number> {
  return page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
}

// ══════════════ ١. الموقع العام: يُقرأ بلا حساب، وباللغتين ══════════════

test.describe("the public site stands at the root, in both languages", () => {
  test("the root serves a real landing page — not a redirect into a protected app", async ({
    page,
  }) => {
    const seen = watch(page);
    const response = await page.goto("/");
    expect(response?.status(), "the document for /").toBeLessThan(400);

    // **الرابط يبقى الجذر.** إعادةُ كتابةٍ لا تحويل: من كتب النطاق يبقى عليه.
    expect(new URL(page.url()).pathname).toBe("/");

    // وليست صفحةَ دخول: لا حقلَ كلمة مرور على الصفحة العامّة.
    await expect(page.locator('input[type="password"]')).toHaveCount(0);

    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(seen.errors, "JS exceptions on /").toEqual([]);
    expect(seen.serverErrors, "5xx from our own origin on /").toEqual([]);
  });

  /** المسارُ الداخلي للموقع العام — اللغةُ فيه لا في استعلام. */
  const PUBLIC_PAGES: Array<[string, string, string, string]> = [
    ["/welcome/ar", AR, "rtl", NAME_AR],
    ["/welcome/en", EN, "ltr", NAME_EN],
  ];

  for (const [path, locale, dir, name] of PUBLIC_PAGES) {
    test(`${path} renders in ${locale} with the right direction and the product name`, async ({
      page,
    }) => {
      const seen = watch(page);
      const response = await page.goto(path);
      expect(response?.status(), `the document for ${path}`).toBeLessThan(400);

      // **الاتجاه على `<html>` نفسه** — لا مرآة CSS، ولا لغةٌ في استعلام.
      await expect(page.locator("html")).toHaveAttribute("lang", locale);
      await expect(page.locator("html")).toHaveAttribute("dir", dir);

      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      // الاسمُ المعروض هو اسم المنتج، مرّةً على الأقل.
      await expect(page.getByText(name).first()).toBeVisible();

      // وبابان إلى الحساب — الصفحةُ العامّة ليست طريقًا مسدودًا.
      expect(
        await page.locator(`a[href="/${locale}/login"]`).count(),
        "no way into sign-in from the public site",
      ).toBeGreaterThan(0);
      expect(
        await page.locator(`a[href="/${locale}/register"]`).count(),
        "no way into account creation from the public site",
      ).toBeGreaterThan(0);

      expect(seen.errors, `JS exceptions on ${path}`).toEqual([]);
      expect(seen.serverErrors, `5xx from our own origin on ${path}`).toEqual([]);
    });

    test(`${path} carries no internal name anywhere a visitor can read it`, async ({ page }) => {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      const body = (await page.locator("body").innerText()).toLowerCase();
      for (const internal of INTERNAL_NAMES) {
        expect(body, `«${internal}» is visible on the public page ${path}`).not.toContain(internal);
      }
    });

    test(`${path} carries no sidebar and no product navigation`, async ({ page }) => {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.locator("aside.sidebar")).toHaveCount(0);
      await expect(page.getByRole("navigation", { name: NAV_LABEL_AR })).toHaveCount(0);
    });
  }

  test("the two languages reach each other, and neither is a mirror of the other", async ({
    page,
  }) => {
    await page.goto("/welcome/en");
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
    const englishTitle = await page.getByRole("heading", { level: 1 }).innerText();

    await page.goto("/welcome/ar");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    const arabicTitle = await page.getByRole("heading", { level: 1 }).innerText();

    // نصّان مختلفان فعلًا — لا كتالوجٌ واحد يُعرض مرّتين.
    expect(arabicTitle).not.toBe(englishTitle);
    expect(arabicTitle.trim().length).toBeGreaterThan(0);
    expect(englishTitle.trim().length).toBeGreaterThan(0);
  });

  test("the public page invents nothing: no price, no customer count, no testimonial", async ({
    page,
  }) => {
    /**
     * **دعوى مخترَعة على صفحةٍ عامّة أسوأ من صفحةٍ غائبة.** فيُمنع ما
     * يُخترع عادةً: سعرٌ برمز عملة، وعددُ مستخدمين، و«يثق بنا».
     */
    for (const path of ["/welcome/ar", "/welcome/en"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      const body = await page.locator("body").innerText();

      expect(body, `a currency figure appears on ${path}`).not.toMatch(/[$€£]\s?\d/);
      expect(body, `a «trusted by» claim appears on ${path}`).not.toMatch(/trusted by|يثق بنا/i);
      expect(body, `a testimonial marker appears on ${path}`).not.toMatch(
        /testimonial|آراء العملاء/i,
      );
      // ولا عددٌ كبير يُساق دعوى — «١٢٠٠٠ باحث»، «٥٠٠+ جامعة».
      expect(body, `a headline count appears on ${path}`).not.toMatch(/\d{3,}\s*\+/);
    }
  });
});

// ══════════════ ٢. قشرةُ الحساب: بلا شريطٍ جانبي ══════════════

test.describe("the auth pages carry no product sidebar", () => {
  const AUTH_PATHS = ["/login", "/register", "/forgot-password", "/reset-password"];

  for (const locale of [AR, EN]) {
    for (const path of AUTH_PATHS) {
      test(`/${locale}${path} renders with a heading and with no sidebar`, async ({ page }) => {
        const seen = watch(page);
        const response = await page.goto(`/${locale}${path}`);
        expect(response?.status(), `the document for /${locale}${path}`).toBeLessThan(400);

        await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();

        // **لا شريطَ منتجٍ خلف مصادقةٍ لم تقع** — ولا بأي صورة.
        await expect(page.locator("aside.sidebar")).toHaveCount(0);
        await expect(page.getByRole("navigation", { name: NAV_LABEL_AR })).toHaveCount(0);
        await expect(page.locator('nav[aria-label="Primary navigation"]')).toHaveCount(0);

        // والاتجاه صحيحٌ في القشرة الجديدة كما كان في القديمة.
        await expect(page.locator("html")).toHaveAttribute("lang", locale);
        await expect(page.locator("html")).toHaveAttribute(
          "dir",
          locale === AR ? "rtl" : "ltr",
        );

        expect(seen.errors, `JS exceptions on /${locale}${path}`).toEqual([]);
        expect(seen.serverErrors, `5xx on /${locale}${path}`).toEqual([]);
      });
    }
  }

  test("the sign-in form shows no two-step field until the server asks for one", async ({
    page,
  }) => {
    /**
     * **حقلٌ لا يعني القارئ يُعلّم العين أن تتخطّى الحقول.** فالخطوة
     * تُفتح حين يقول الخادم إنّ الرمز مطلوب — وتُفحص من طرفيها: غائبةً
     * أوّلًا، ثمّ ظاهرةً بعد ردّ الخادم. ولو فُحص الغياب وحده لمرّ حذفُ
     * الخطوة كلّها، وذاك عطبُ دخولٍ لا إصلاحُ تجربة.
     */
    await page.goto(`/${AR}/login`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    const step = page.getByTestId("login-mfa-step");
    await expect(step).toHaveCount(0);
    await expect(page.getByLabel("رمز التحقق بخطوتين")).toHaveCount(0);

    // الخادمُ يقول: لهذا الحساب عاملٌ ثانٍ، وما وصل لا يكفي.
    await page.route("**/api/v1/auth/login", (route: Route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        // **الغلاف هو ما يردّه الخادم فعلًا**: `{"error": {...}}` كما في
        // `athera_error_handler`، وكما يقرؤه `apiFetch` (`body?.error`).
        // وأوّلُ صياغةٍ لهذا القالب وضعت الحقول عاريةً بلا غلاف، فقرأ
        // العميلُ `server.error` ولم تُفتح الخطوة — **والعطب كان في
        // القالب لا في الصفحة**. وقالبٌ يخالف عقد الخادم يفحص وهمًا.
        body: JSON.stringify({
          error: {
            code: "auth.mfa_invalid_code",
            locale: AR,
            message: "رمز التحقّق بخطوتين غير صحيح.",
            messages: {
              ar: "رمز التحقّق بخطوتين غير صحيح.",
              en: "The two-step verification code is not valid.",
            },
            context: {},
          },
        }),
      }),
    );

    await page.getByLabel("البريد الإلكتروني").fill("brand-spec@example.test");
    await page.getByLabel("كلمة المرور").fill("not-a-real-password");
    await page.getByRole("button", { name: "دخول", exact: true }).click();

    // ثمّ — وعندها وحدها — تُفتح الخطوة.
    await expect(step).toBeVisible();
    await expect(page.getByLabel("رمز التحقق بخطوتين")).toBeVisible();
  });
});

// ══════════════ ٣. مساحةُ العمل: الشريط قائم، والنشط واحد ══════════════

test.describe("the workspace keeps its shell and exactly one active item", () => {
  test.beforeEach(async ({ page }) => {
    await seedSession(page);
    await stubApi(page);
  });

  test("the authenticated shell renders the sidebar beside the content", async ({ page }) => {
    /**
     * **الفحص من طرفيه.** لو فُحص غيابُ الشريط عن صفحات الحساب وحده لمرّ
     * حذفُه من المنتج كلّه — وذاك ليس فصلًا بل إتلاف.
     */
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`/${AR}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    const aside = await page.locator("aside.sidebar").boundingBox();
    const main = await page.locator("main#main-content").boundingBox();
    expect(aside, "the sidebar is not rendered in the workspace").not.toBeNull();
    expect(main, "the content region is not rendered").not.toBeNull();
    expect(main!.y).toBeLessThan(aside!.y + aside!.height);

    // والعلامةُ تحمل اسم المنتج، لا اسمًا داخليًّا.
    await expect(page.locator(".brand")).toContainText(NAME_AR);
  });

  for (const [path, expected] of [
    ["", "الرئيسية"],
    ["/ai", "بُبريفا AI"],
    ["/library", "مكتبتي"],
  ] as const) {
    test(`/${AR}${path} marks exactly one navigation item active`, async ({ page }) => {
      await page.goto(`/${AR}${path}`);
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();

      const active = page
        .getByRole("navigation", { name: NAV_LABEL_AR })
        .locator('a[aria-current="page"]');
      await expect(active).toHaveCount(1);
      await expect(active).toHaveText(expected);
    });
  }
});

// ══════════════ ٤. رموزُ الهويّة مطبَّقة فعلًا ══════════════

test.describe("the brand tokens are applied, not merely declared", () => {
  /** الطيف المعتمد — كما في `globals.css`، بصيغة `rgb()` كما يردّها المتصفّح. */
  const INDIGO = "rgb(75, 70, 169)";
  const VIOLET = "rgb(120, 103, 242)";
  const TEAL = "rgb(23, 190, 187)";
  const INK = "rgb(24, 34, 51)";
  const PAPER = "rgb(247, 248, 251)";

  /**
   * **القيمةُ تُسوّى قبل المقارنة.** مصغِّرُ الأنماط يخفض حالةَ الأحرف في
   * الرقم السداسي، فيردّ المتصفّح `#4b46a9` والملفُّ يكتب `#4B46A9`.
   * ومقارنةُ النصّ الخام كانت تسقط على الحالة وحدها — وهو فرقُ عرضٍ لا
   * فرقُ لون. فتُخفَض الحالة وتُقصّ الفراغات، **ولا يُضعَف الشرط**: القيمة
   * ما زالت تُقابَل بالرقم بعينه لا بجزءٍ منه.
   */
  const readToken = async (page: Page, token: string) =>
    (
      await page.evaluate(
        (name) => getComputedStyle(document.documentElement).getPropertyValue(name),
        token,
      )
    )
      .trim()
      .toLowerCase();

  test("the approved five are defined once, at the root, on every shell", async ({ page }) => {
    /**
     * **الطبقةُ الأولى هي الوحيدة التي تُبدَّل.** ولو عاد أحدهم يكتب لونًا
     * في شاشة لبقيت هذه القيم على حالها وهو يخالفها — فيُقرأ التعريف من
     * القشور الثلاث، لا من واحدة.
     */
    for (const path of ["/welcome/ar", `/${AR}/login`]) {
      await page.goto(path);
      expect(await readToken(page, "--brand-indigo"), path).toBe("#4b46a9");
      expect(await readToken(page, "--brand-violet"), path).toBe("#7867f2");
      expect(await readToken(page, "--brand-teal"), path).toBe("#17bebb");
      expect(await readToken(page, "--brand-ink"), path).toBe("#182233");
      expect(await readToken(page, "--brand-paper"), path).toBe("#f7f8fb");
    }
  });

  test("the old palette is gone: the derived names now resolve to the brand", async ({ page }) => {
    /**
     * **الأسماءُ القديمة لم تُحذف، بُدِّل معناها.** وحذفُها كان يترك أربعًا
     * وأربعين شاشةً بلونٍ غير معرَّف — وهو في CSS صمتٌ لا خطأ، فيمرّ ولا
     * يُرى. فيُثبَت أنها تُشتقّ من الطيف الجديد لا أنها بقيت على القديم.
     */
    await page.goto("/welcome/ar");
    // `--aqua` كان `#00d4c5`؛ صار النيليَّ المعتمد. والقيمةُ المحسوبة
    // تُعيد ما استقرّ عليه `var()` لا نصَّ الإحالة.
    expect(await readToken(page, "--aqua")).toBe("#4b46a9");
    expect(await readToken(page, "--aqua")).not.toBe("#00d4c5");
    expect(await readToken(page, "--violet")).toBe("#7867f2");
    // ولا اسمَ ميّتًا: ثلاثةٌ كانت تُستعمل بلا تعريفٍ أصلًا.
    expect(await readToken(page, "--athera-teal")).not.toBe("");
    expect(await readToken(page, "--athera-gold")).not.toBe("");
  });

  test("the four semantic colours are the sheet's, to the digit", async ({ page }) => {
    /**
     * **ورقةُ الهويّة تكتب أربعةً بأرقامها**، فلا تُقارَب بالاشتقاق:
     * النجاح والتحذير والخطأ والحياد. وهي ألوانُ الحشو والحدّ.
     *
     * وكلٌّ منها **يُربَط بحالته** — فقيمةٌ معرَّفةٌ لا تصل إلى شارةٍ هي
     * لونٌ في ورقةٍ لا في منتج.
     */
    await page.goto("/welcome/ar");
    expect(await readToken(page, "--success")).toBe("#22c55e");
    expect(await readToken(page, "--warning")).toBe("#f59e0b");
    expect(await readToken(page, "--error")).toBe("#ef4444");
    expect(await readToken(page, "--neutral")).toBe("#f7f8fb");

    // والحالُ تُشتقّ من الرقم المعتمد لا من قيمةٍ ثانية بجانبه.
    expect(await readToken(page, "--state-verified")).toBe("#22c55e");
    expect(await readToken(page, "--state-review")).toBe("#f59e0b");
    expect(await readToken(page, "--state-conflict")).toBe("#ef4444");
    expect(await readToken(page, "--state-candidate")).toBe("#7867f2");
  });

  test("the brand typefaces are served from our own origin, never a third party", async ({
    page,
  }) => {
    /**
     * **سياسةُ المحتوى تقول `font-src 'self'`** — فرابطٌ إلى خطوط خادمٍ
     * ثالث يُحجب في المتصفّح بلا رسالةٍ مفهومة، وتعود الصفحة إلى خطّ
     * النظام بلا أن يقول شيءٌ لماذا. فيُفحص الأمران: أن يكون للخطّ ملفٌّ
     * من أصلنا، وألّا يُطلب من غيره.
     */
    const foreign: string[] = [];
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (url.origin !== APP_ORIGIN && /font|\.woff2?$/i.test(url.href)) {
        foreign.push(url.href);
      }
    });

    await page.goto("/welcome/en");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(foreign, "a font was requested from a third-party origin").toEqual([]);

    // والخطُّ وصل فعلًا: المتغيّر معرَّف، والجسمُ يستعمله.
    const family = await page
      .locator("body")
      .evaluate((node) => getComputedStyle(node).fontFamily);
    expect(family.length).toBeGreaterThan(0);
    expect(await readToken(page, "--font-latin")).not.toBe("");
    expect(await readToken(page, "--font-arabic")).not.toBe("");
  });

  test("the page paints with the brand, not with the retired spectrum", async ({ page }) => {
    await page.goto("/welcome/ar");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    const bodyBackground = await page
      .locator("body")
      .evaluate((node) => getComputedStyle(node).backgroundColor);
    expect(bodyBackground).toBe(PAPER);

    const headingColour = await page
      .getByRole("heading", { level: 1 })
      .evaluate((node) => getComputedStyle(node).color);
    expect(headingColour).toBe(INK);

    // وزرُّ الفعل الأول يحمل النيليّ المعتمد.
    const cta = page.locator("a.btn-primary").first();
    await expect(cta).toBeVisible();
    expect(
      await cta.evaluate((node) => getComputedStyle(node).backgroundColor),
    ).toBe(INDIGO);
  });

  test("the Research Thread is drawn, and its nodes carry the brand colours", async ({ page }) => {
    await page.goto("/welcome/ar");
    const thread = page.locator("svg.hero-thread");
    await expect(thread).toBeVisible();

    const nodeColours = await thread
      .locator("circle")
      .evaluateAll((nodes) => nodes.map((node) => getComputedStyle(node).fill));
    expect(nodeColours.length, "the thread has no nodes").toBeGreaterThan(2);
    expect(nodeColours).toContain(INDIGO);
    expect(nodeColours).toContain(VIOLET);
    expect(nodeColours).toContain(TEAL);
  });
});

// ══════════════ ٥. الحالاتُ العلميّة: لونٌ ومعه اسمُه ══════════════

test.describe("scientific state semantics carry text, never colour alone", () => {
  /** الحالات الأربع كما تُعلَن في الشجرة — `data-state`. */
  const STATES = ["candidate", "review", "verified", "conflict"] as const;

  test("each of the four states is named in writing beside its colour", async ({ page }) => {
    await page.goto("/welcome/ar");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    const colours: string[] = [];
    for (const state of STATES) {
      const chip = page.locator(`.legend [data-state="${state}"]`);
      await expect(chip, `no chip for the «${state}» state`).toHaveCount(1);

      // **النصّ هو الحامل الأول.** ولو أُطفئت الألوان بقي المعنى.
      const text = (await chip.innerText()).trim();
      expect(text.length, `the «${state}» chip carries colour and no words`).toBeGreaterThan(1);

      colours.push(await chip.evaluate((node) => getComputedStyle(node).color));
    }

    // **ثمّ اللون يفرّق فعلًا.** أربعةُ ألوانٍ مختلفة لا لونٌ واحد أربع مرّات.
    expect(new Set(colours).size, `the four states share colours: ${colours.join(", ")}`).toBe(4);
  });

  test("the four states are legible with every colour removed", async ({ page }) => {
    await page.goto("/welcome/ar");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    // لا لونَ إطلاقًا — ويبقى اسمُ كل حالٍ مقروءًا.
    await page.addStyleTag({
      content: "*, *::before, *::after { color: #000 !important; background: #fff !important; }",
    });
    for (const state of STATES) {
      const chip = page.locator(`.legend [data-state="${state}"]`);
      await expect(chip).toBeVisible();
      expect((await chip.innerText()).trim().length).toBeGreaterThan(1);
    }
  });

  test("a candidate in the product wears the same state as the one on the public page", async ({
    page,
  }) => {
    /**
     * **المفتاحُ على الصفحة العامّة يَعِد بخريطة.** ولو خالفها المنتجُ
     * لكان الوعدُ أسوأ من ألّا يُقال: يتعلّم الباحث خريطةً ثمّ تكذبه.
     * فيُقرأ لونُ «المقترَح» من الموضعين ويُقابَلان.
     */
    await page.goto("/welcome/ar");
    const onSite = await page
      .locator('.legend [data-state="candidate"]')
      .evaluate((node) => getComputedStyle(node).color);

    await seedSession(page);
    await stubApi(page);
    await page.goto(`/${AR}/facts`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    const inProduct = page.locator('[data-state="candidate"]').first();
    await expect(inProduct).toBeVisible();
    expect((await inProduct.innerText()).trim().length).toBeGreaterThan(1);
    expect(
      await inProduct.evaluate((node) => getComputedStyle(node).color),
      "the same state wears two different colours in two screens",
    ).toBe(onSite);
  });
});

// ══════════════ ٦. الهاتف: لا تمرير أفقي في أي قشرة ══════════════

test.describe("390px: no shell scrolls the document sideways", () => {
  const PHONE = { width: 390, height: 844 };

  for (const path of ["/welcome/ar", "/welcome/en", "/ar/login", "/ar/register"]) {
    test(`${path} fits a phone without a sideways scroll`, async ({ page }) => {
      await page.setViewportSize(PHONE);
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
      expect(
        await sidewaysOverflow(page),
        `the document scrolls sideways on a phone at ${path}`,
      ).toBeLessThanOrEqual(1);
    });
  }

  test("the workspace fits a phone too", async ({ page }) => {
    await seedSession(page);
    await stubApi(page);
    await page.setViewportSize(PHONE);
    await page.goto(`/${AR}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(await sidewaysOverflow(page)).toBeLessThanOrEqual(1);
  });
});

// ══════════════ ٧. الإتاحة على السطح العام ══════════════

test.describe("accessibility on the public and auth shells", () => {
  test("the first Tab on the public site reaches a skip link into the content", async ({
    page,
  }) => {
    await page.goto("/welcome/ar");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.keyboard.press("Tab");

    const skip = page.getByRole("link", { name: "تخطَّ إلى المحتوى", exact: true });
    await expect(skip).toBeFocused();
    await expect(skip).toBeVisible();

    await page.keyboard.press("Enter");
    await expect
      .poll(() => page.evaluate(() => document.activeElement?.id ?? ""))
      .toBe("main-content");
  });

  test("the public shell declares its landmarks once each", async ({ page }) => {
    await page.goto("/welcome/ar");
    await expect(page.getByRole("banner")).toHaveCount(1);
    await expect(page.getByRole("main")).toHaveCount(1);
    await expect(page.getByRole("contentinfo")).toHaveCount(1);
  });

  test("headings on the public page descend in order, with a single h1", async ({ page }) => {
    await page.goto("/welcome/ar");
    const levels = await page
      .locator("h1, h2, h3")
      .evaluateAll((nodes) => nodes.map((node) => Number(node.tagName.slice(1))));

    expect(levels.filter((level) => level === 1)).toHaveLength(1);
    expect(levels[0], "the page does not open with its h1").toBe(1);
    // ولا قفزةَ مستوى: من الثاني إلى الرابع تترك فجوةً في الشجرة.
    for (let index = 1; index < levels.length; index += 1) {
      expect(levels[index]! - levels[index - 1]!).toBeLessThanOrEqual(1);
    }
  });

  test("every focusable control on the public and auth shells shows a focus ring", async ({
    page,
  }) => {
    for (const path of ["/welcome/ar", `/${AR}/login`]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();

      // ولا رابطَ أُخرج من ترتيب الجدولة — موجودٌ للفأرة وحدها.
      const outOfOrder = await page.evaluate(() =>
        [...document.querySelectorAll("a[href], button, input, select, textarea")]
          .filter((node) => !(node as HTMLButtonElement).disabled)
          .filter((node) => !(node as HTMLElement).hidden)
          .filter((node) => (node as HTMLElement).tabIndex < 0).length,
      );
      expect(outOfOrder, `controls removed from the tab order on ${path}`).toBe(0);

      const first = page.locator("a[href]").first();
      await first.focus();
      const ring = await first.evaluate((node) => {
        const style = getComputedStyle(node);
        return { width: style.outlineWidth, style: style.outlineStyle };
      });
      expect(ring.style, `no focus ring on ${path}`).not.toBe("none");
      expect(Number.parseFloat(ring.width)).toBeGreaterThan(0);
    }
  });

  test("the mark is announced by name where it stands alone, and silent where the name is written", async ({
    page,
  }) => {
    await page.goto("/welcome/ar");
    // الاسم مكتوبٌ بجانب العلامة، فالعلامةُ مخفيّة عن الشجرة — لا يُقال مرّتين.
    const marks = page.locator("svg.brand-mark");
    expect(await marks.count()).toBeGreaterThan(0);
    for (let index = 0; index < (await marks.count()); index += 1) {
      await expect(marks.nth(index)).toHaveAttribute("aria-hidden", "true");
    }
    // والرسمُ الكبير كذلك: ما يقوله مكتوبٌ بجانبه.
    await expect(page.locator("svg.hero-thread")).toHaveAttribute("aria-hidden", "true");
  });
});

// ══════════════ ٨. نصُّ ورقة الهويّة، وما لم يُنقَل منها ══════════════

test.describe("the brand sheet's own content, and the four things left out", () => {
  /** بطاقاتُ القدرات الستّ — بعناوينها كما في الورقة. */
  const CARDS_EN = ["Discover", "Build", "Manage", "Analyze", "Write", "Publish"];

  /** عقدُ الخيط الستّ، **بترتيبها**: الترتيب هو الدعوى. */
  const NODES_EN = ["Idea", "Literature", "Research", "Evidence", "Manuscript", "Publication"];

  /** قواعدُ النزاهة الستّ — بحرفها، لا بمعناها. */
  const INTEGRITY_EN = [
    "No fabricated references",
    "No invented results",
    "Clear distinction between suggestions and scientific facts",
    "Evidence traceability",
    "Researcher approval for key decisions",
    "Transparency in AI use",
  ];

  test("the hero carries the sheet's eyebrow, its two-line headline and its promise", async ({
    page,
  }) => {
    await page.goto("/welcome/en");
    await expect(page.getByText("THE RESEARCH OPERATING SYSTEM")).toBeVisible();

    // **عنوانٌ واحد في الشجرة وإن كان سطرين في العين.** والكلمةُ الثانية
    // ملوّنة، فيُفحص أنّها داخل العنوان لا عنوانًا ثانيًا بجانبه.
    const headline = page.getByRole("heading", { level: 1 });
    await expect(headline).toContainText("Research to Publication.");
    await expect(headline).toContainText("Connected.");
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);

    // والكلمةُ الثانية بالبنفسجي — لهجةُ الذكاء في الورقة.
    const accent = headline.locator(".accent");
    await expect(accent).toHaveText("Connected.");
    expect(await accent.evaluate((n) => getComputedStyle(n).color)).toBe("rgb(74, 56, 200)");
  });

  test("the six thread nodes read in the sheet's order", async ({ page }) => {
    await page.goto("/welcome/en");
    const nodes = page.locator(".stages-six .stage strong");
    await expect(nodes).toHaveCount(6);
    // **الترتيب يُقاس، لا الوجود.** «الفكرة قبل الأدبيات» هي الدعوى.
    expect(await nodes.allTextContents()).toEqual(NODES_EN);

    await expect(page.getByText("One journey. A bigger impact.")).toBeVisible();
    await expect(page.getByText("Researchers today. A more open tomorrow.")).toBeVisible();
  });

  test("the six capability cards carry the sheet's titles", async ({ page }) => {
    await page.goto("/welcome/en");
    const cards = page.locator(".cap h3");
    await expect(cards).toHaveCount(6);
    expect(await cards.allTextContents()).toEqual(CARDS_EN);
  });

  test("the six integrity rules appear verbatim, and are readable without their marks", async ({
    page,
  }) => {
    await page.goto("/welcome/en");
    await expect(page.getByRole("heading", { name: "Research integrity by design" })).toBeVisible();

    const rules = page.locator(".integrity li");
    await expect(rules).toHaveCount(6);
    for (const rule of INTEGRITY_EN) {
      await expect(rules.filter({ hasText: rule })).toHaveCount(1);
    }

    // **والعلامةُ زخرفٌ لا معنى.** القاعدةُ نصٌّ بجانبها، فالعلامة مخفيّة
    // عن الشجرة — ولو أُطفئت الرموز كلُّها بقيت القواعد الستّ مقروءة.
    const ticks = page.locator(".integrity .tick");
    await expect(ticks).toHaveCount(6);
    for (let index = 0; index < 6; index += 1) {
      await expect(ticks.nth(index)).toHaveAttribute("aria-hidden", "true");
    }
  });

  test("every nav item leads somewhere that actually exists on the page", async ({ page }) => {
    /**
     * **رابطٌ في القائمة إلى صفحةٍ غير موجودة يَعِد ثمّ يُخرج.** فتُقرأ
     * مراسي القائمة كلُّها ويُطلب هدفُ كلٍّ في المستند — والمقياس وجودُ
     * العنصر لا نيّةُ كاتبه.
     */
    await page.goto("/welcome/en");
    const anchors = await page
      .locator('.site-nav a[href^="#"]')
      .evaluateAll((nodes) => nodes.map((node) => node.getAttribute("href") ?? ""));

    expect(anchors.length, "the sheet's section links are missing entirely").toBe(3);
    for (const anchor of anchors) {
      await expect(
        page.locator(anchor),
        `the nav points at ${anchor}, and nothing on the page has that id`,
      ).toHaveCount(1);
    }

    // والبابان إلى الحساب: «تسجيل الدخول» محدَّد، و«ابدأ» ممتلئ.
    await expect(page.locator(`.site-nav a.site-signin[href="/${EN}/login"]`)).toBeVisible();
    await expect(page.locator(`.site-nav a.site-cta[href="/${EN}/register"]`)).toBeVisible();
  });

  test("what the sheet asks for and we cannot honour honestly is absent, not faked", async ({
    page,
  }) => {
    /**
     * **حارسُ الامتناع.** الورقة تطلب «الأسعار» و«شاهد الفيديو» وصفحاتٍ لا
     * وجود لها. والامتناعُ قرارٌ مكتوب في `docs/integration/brand-requests.md`
     * — ولو لم يُحرَس لعاد أوّلُ من يقرأ الورقة يضيفه بحسن نيّة.
     *
     * وسقوطُ هذا الفحص لا يعني «أضِف الحارس»، بل: أُضيف شيءٌ من هذه
     * إمّا بوجهةٍ حقيقية (فيُحدَّث الفحص ويُشطب من الوثيقة)، وإمّا بلا
     * وجهة (فيُزال).
     */
    for (const path of ["/welcome/ar", "/welcome/en"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      const body = (await page.locator("body").innerText()).toLowerCase();

      expect(body, `a pricing entry appears on ${path}`).not.toMatch(/pricing|الأسعار|التسعير/);
      expect(body, `a video CTA appears on ${path} and no video exists`).not.toMatch(
        /watch video|شاهد الفيديو/,
      );

      // **ولا رابطٍ خارج ما بُني.** كلُّ وجهةٍ إمّا مرساةٌ في هذه الصفحة،
      // وإمّا لغةٌ أخرى، وإمّا بابُ حساب — لا رابعَ لها.
      const stray = await page
        .locator(".site-head a, .site-foot a")
        .evaluateAll((nodes) =>
          nodes
            .map((node) => node.getAttribute("href") ?? "")
            .filter(
              (href) =>
                !href.startsWith("#") &&
                href !== "/" &&
                !/^\/welcome\/(ar|en)$/.test(href) &&
                !/^\/(ar|en)\/(login|register)$/.test(href),
            ),
        );
      expect(stray, `links with no destination we built, on ${path}`).toEqual([]);
    }
  });

  test("the auth shell says what the sheet says, and hides its panel on a phone", async ({
    page,
  }) => {
    await page.goto(`/${EN}/login`);
    await expect(page.getByRole("heading", { name: "Welcome back", exact: true })).toBeVisible();
    await expect(page.getByText("Sign in to your research workspace")).toBeVisible();
    await expect(page.getByText("Think. Organize. Build. Verify. Publish.")).toBeVisible();
    await expect(page.getByText("A more open tomorrow.")).toBeVisible();
    await expect(page.getByRole("link", { name: "Forgot your password?" })).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Don't have an account? Create one" }),
    ).toBeVisible();

    // **واللوحةُ تختفي على الهاتف ولا تزاحم.** الداخلُ جاء ليدخل.
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.locator(".auth-aside")).toBeHidden();
    await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
  });

  test("the password reveal names what it does, and changes its name when it does it", async ({
    page,
  }) => {
    /**
     * **ومن لا يرى الحقل لا يقرأ رسمَ عين.** فالزرُّ اسمُه منطوق، ويتبدّل
     * بتبدّل الحال — وإلّا قال «أظهِر» وكلمةُ المرور ظاهرة.
     */
    await page.goto(`/${EN}/login`);
    const field = page.getByLabel("Password", { exact: true });
    await expect(field).toHaveAttribute("type", "password");

    const show = page.getByRole("button", { name: "Show password", exact: true });
    await expect(show).toBeVisible();
    await show.click();

    await expect(field).toHaveAttribute("type", "text");
    await expect(page.getByRole("button", { name: "Hide password", exact: true })).toBeVisible();
    await expect(show).toHaveCount(0);
  });

  test("the sidebar keeps the sheet's order and its three named groups", async ({ page }) => {
    /**
     * ترتيبُ الورقة هو الترتيبُ القائم من الموجة الأولى — فيُحرَس أنه لم
     * ينكسر وأنا أنقل الهيكل، لا أنه أُنشئ الآن.
     */
    await seedSession(page);
    await stubApi(page);
    await page.goto(`/${EN}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    const menu = page.getByRole("navigation", { name: "Primary navigation" });
    expect(
      await menu.locator("a").allTextContents(),
      "the sidebar order drifted from the approved sheet",
    ).toEqual([
      "Home",
      "PUBRIVA AI",
      "My Research",
      "My Library",
      "Search & Reference Discovery",
      "Research Radar",
      "Theses",
      "Data & Analysis",
      "Manuscript Studio",
      "Peer Review",
      "Journals & Publishing",
      "Settings",
    ]);

    // **`innerText` يُدخل `text-transform` في النصّ المُعاد**، والورقة
    // تكتب عناوين المجموعات بالكبير. فيُقرأ `textContent` — وهو ما في
    // الكتالوج بحرفه، ولا يتبدّل بورقة أنماط.
    expect(await menu.locator("h2.nav-label").allTextContents()).toEqual([
      "Discovery & literature",
      "Build the research",
      "Review & publishing",
    ]);

    // **ولا أداةٍ مملوكةٍ لبحثٍ بعينه في القائمة العامّة.**
    const projectScoped = await menu
      .locator("a")
      .evaluateAll((nodes) =>
        nodes
          .map((node) => node.getAttribute("href") ?? "")
          .filter((href) => /\/portfolio\/[^/]+\//.test(href)),
      );
    expect(projectScoped, "a project-scoped tool leaked into global navigation").toEqual([]);
  });
});
