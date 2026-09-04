import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * سطحُ المنتج | The product surface — dead UI, not the P1 journey.
 *
 * **الغرض واحد: ألّا تُعرض واجهةٌ تَعِد ولا تفعل.** ورحلةُ القبول تفحص أن
 * الطريق يُقطع من أوّله إلى آخره، وهذه لا تعيدها: تفتح الشاشات وتسأل عنها
 * ثلاثة أسئلة لا رابع لها —
 *
 *   ١ هل سقط في المتصفّح استثناء؟ صفحةٌ تُصيَّر ثم يقع فيها استثناءٌ تعني
 *     أزرارًا لا تستجيب، وليس في الشاشة ما يقول ذلك.
 *   ٢ هل ردّ أصلُنا بخطأ خمسمئة على شيءٍ طلبَته الصفحة؟
 *   ٣ هل انتهى «جارٍ التحميل…» بعد أن ردّ الخادم؟ رايةٌ تُرفع ولا تُنزَل
 *     مؤشِّرٌ بلا حدّ — وهو الوجه الآخر لعيب «لا يوجد» قبل السؤال: الأولى
 *     تكذب بالنفي، والثانية تكذب بالانتظار.
 *
 * **وطبقتها هي طبقة `auth-refresh`**: بناءٌ محلّي لشيفرة هذا الفرع، وشبكةٌ
 * معترَضة، وبلا اعتمادٍ إطلاقًا — فتعمل في كل PR. ورحلةُ القبول وحدها هي
 * التي تحتاج حسابًا حقيقيًّا وإنتاجًا منشورًا، وليست هذه منها.
 */

const AR = "ar";

/** «جارٍ التحميل…» كما هي في `messages/ar.json` — `app.loading`. */
const LOADING_AR = "جارٍ التحميل…";
/** `portfolio.empty` — الجملة التي كانت تُقال قبل السؤال. */
const NO_PROJECTS_AR = "لا مشاريع بعد.";

/**
 * أصلُ التطبيق — **يُشتقّ من المتغيّر نفسه الذي يضبطه ملفّ الإعداد**، فلا
 * ينفصل الفحص عن هدفه إن غُيّر أحدهما. ونداءات الـAPI تقع على نطاقٍ آخر
 * وهي معترَضة هنا، فما يبقى من أصلنا هو المستند وحُزَمه — وخطأُ خمسمئة
 * فيها عطبُ بناءٍ أو تصييرٍ على الخادم، وهو ما نبحث عنه.
 */
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
    if (response.status() >= 500) {
      seen.serverErrors.push(`${response.status()} ${response.url()}`);
    }
  });
  return seen;
}

/** جلسةٌ مزروعة — كما في فحص دورة الحياة، وبلا اعتمادٍ حقيقي. */
async function seedSession(page: Page) {
  await page.addInitScript(() => {
    if (sessionStorage.getItem("__seeded")) return;
    sessionStorage.setItem("__seeded", "1");
    localStorage.setItem("athera_access_token", "surface-access");
    localStorage.setItem("athera_refresh_token", "surface-refresh");
    localStorage.setItem("athera_token_expiry", String(Date.now() + 900_000));
  });
}

/**
 * أجسامٌ لأشكالٍ ليست قوائم.
 *
 * **والقائمة الفارغة هي الافتراض قصدًا**: هي الحال التي كان العيب يظهر
 * فيها — لا شيء عند الباحث، فتقول الشاشة «لا يوجد» قبل أن تعرف. وما ليس
 * قائمةً يُعطى شكله الأدنى الذي يقبله العقد، وإلّا سقطت الشاشة باستثناءٍ
 * لا علاقة له بما نفحص.
 */
const OBJECT_BODIES = new Map<string, unknown>([
  [
    "/api/v1/settings/posture",
    {
      tenant_name: "فحص السطح",
      locale: AR,
      supported_locales: ["ar", "en"],
      roles: [],
      items: [{ key: "model_provider", label: "المزوّد", value: "anthropic", detail: "" }],
    },
  ],
  [
    "/api/v1/inbox/summary",
    { pending_approvals: 0, open_alerts: 0, blocking_alerts: 0, unread_notifications: 0 },
  ],
  [
    "/api/v1/portfolio/reference-plan",
    {
      projects: 0,
      sole_authored: 0,
      planned_units: 0,
      is_binding: false,
      note_ar: "خطّة مرجعية",
      note_en: "Reference plan",
    },
  ],
  [
    "/api/v1/profile",
    {
      institution: null,
      current_rank: null,
      target_rank: null,
      primary_field: null,
      orcid: null,
      g0_approved_at: null,
      verified_memory_count: 0,
    },
  ],
]);

/** الجسم المناسب لمسارٍ بعينه — والمطابقة تامّة، فـ`/profile/facts` قائمة. */
function bodyFor(path: string): unknown {
  return OBJECT_BODIES.has(path) ? OBJECT_BODIES.get(path) : [];
}

/**
 * كل نداءٍ إلى الـAPI يُجاب — **ولا نداء يُترك معلَّقًا**.
 *
 * نداءٌ لا يُجاب يُبقي «جارٍ التحميل…» قائمًا إلى الأبد، فيسقط الفحص على
 * الشبكة لا على المنتج — ويُفهم العيب في غير موضعه.
 */
async function stubApi(page: Page) {
  await page.route("**/api/v1/**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(bodyFor(new URL(route.request().url()).pathname)),
    }),
  );
}

/** المسارات العامّة: ما يُنشئ الجلسة أو يسترجعها، ولا يحتاج واحدةً. */
const PUBLIC_PATHS = ["/login", "/register", "/forgot-password"];

/**
 * المسارات المحميّة المفحوصة — **كلٌّ منها يقرأ قائمةً ويقول عن فراغها
 * شيئًا**، وهي بعينها المواضع التي كانت تقوله قبل السؤال.
 */
const GUARDED_PATHS = [
  "/portfolio",
  "/theses",
  "/manuscripts",
  "/analysis",
  "/trends",
  "/approvals",
  "/briefs",
  "/claims",
  "/facts",
  "/memory",
  "/traces",
  "/audit",
  "/agents",
  "/profile",
  "/settings",
];

test.describe("public surface", () => {
  for (const locale of [AR, "en"]) {
    for (const path of PUBLIC_PATHS) {
      test(`/${locale}${path} renders with no exception and no 5xx`, async ({ page }) => {
        const seen = watch(page);
        const response = await page.goto(`/${locale}${path}`);
        expect(response?.status(), `the document for /${locale}${path}`).toBeLessThan(400);
        // العنوان شاهدُ تصييرٍ فعلي، لا مجرّد ردٍّ بمئتين.
        await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
        expect(seen.errors, `JS exceptions on /${locale}${path}`).toEqual([]);
        expect(seen.serverErrors, `5xx from our own origin on /${locale}${path}`).toEqual([]);
      });
    }
  }

  test("no control on the public surface is taken out of the tab order", async ({ page }) => {
    // زرٌّ أو رابطٌ لا يبلغه التنقّل بلوحة المفاتيح موجودٌ للفأرة وحدها.
    await page.goto(`/${AR}/login`);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    const unreachable = await page.evaluate(() =>
      [...document.querySelectorAll("button, a[href], input, select, textarea")]
        .filter((node) => !(node as HTMLButtonElement).disabled)
        .filter((node) => !(node as HTMLElement).hidden)
        .filter((node) => (node as HTMLElement).tabIndex < 0)
        .map((node) => node.outerHTML.slice(0, 120)),
    );
    expect(unreachable, "controls removed from the tab order").toEqual([]);
  });
});

test.describe("guarded surface", () => {
  test.beforeEach(async ({ page }) => {
    await seedSession(page);
    await stubApi(page);
  });

  for (const path of GUARDED_PATHS) {
    test(`/${AR}${path} answers, then stops saying it is loading`, async ({ page }) => {
      const seen = watch(page);
      await page.goto(`/${AR}${path}`);

      // ولم يُقذف إلى الدخول: الجلسة مزروعة والـAPI يردّ بمئتين.
      await expect(page).not.toHaveURL(/\/login/);
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();

      // **الحدّ هو الشاهد.** الردّ وصل، فلا يجوز أن تبقى الشاشة تقول «جارٍ».
      await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

      expect(seen.errors, `JS exceptions on /${AR}${path}`).toEqual([]);
      expect(seen.serverErrors, `5xx from our own origin on /${AR}${path}`).toEqual([]);
    });
  }

  test("a screen that has not answered yet says so, and says nothing else", async ({ page }) => {
    // **العيب الأصلي مثبَّتٌ هنا**: الردّ يتأخّر، والشاشة تقول «لا مشاريع
    // بعد» قبل أن يصل. فيُحبَس الردّ قصدًا، ويُثبَت أن المعروض حينها «جارٍ
    // التحميل…» وحدها — لا حكمٌ على محفظةٍ لم تُقرأ بعد.
    let release = () => {};
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route("**/api/v1/**", async (route: Route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/portfolio/projects")) await held;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(bodyFor(path)),
      });
    });

    await page.goto(`/${AR}/portfolio`);
    await expect(page.getByTestId("projects-loading")).toBeVisible();
    await expect(page.getByText(NO_PROJECTS_AR)).toHaveCount(0);

    release();
    await expect(page.getByTestId("projects-loading")).toHaveCount(0, { timeout: 20_000 });
    await expect(page.getByText(NO_PROJECTS_AR)).toBeVisible();
  });
});
