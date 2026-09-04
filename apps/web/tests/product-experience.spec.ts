import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * تجربةُ المنتج ومعماريّةُ معلوماته | Product experience and information architecture.
 *
 * **ما تحرسه هذه الفحوص أعطابٌ وقعت فعلًا، لا مبادئ عامّة.** ولكلٍّ منها
 * أثرٌ في الشيفرة يُبطله لو عاد:
 *
 *   ١ عنصران في القائمة يلبسان لباس الصفحة الجارية معًا، على أيّ صفحة كان
 *     الباحث — فيُثبَت أن النشط **واحد**، وأن البقيّة **ليست** نشطة. ولا
 *     يكفي أن يُفحص وجودُ الواحد: العيب كان في الزائد لا في الناقص.
 *   ٢ نقاطٌ ملوّنة بلا معنى، وشاراتٌ تُلوّن ولا تقول — فيُثبَت ألّا لون
 *     يحمل معنى وحده: ما يميّز النشط يبقى مميِّزًا لو أُطفئت الألوان كلّها.
 *   ٣ سلّةُ «أدوات أخرى» — فيُثبَت أنها ذهبت وأن مكانها مجموعاتٌ مسمّاة.
 *   ٤ «قريبًا» على قدرةٍ تعمل — فيُثبَت أن الـDOI يُقبَل ويُوجَّه ويُبحَث
 *     عنه فعلًا، وأن الكلمة لم تعد تُقال عليه.
 *   ٥ أسماءُ مزوّدين وحالاتُ بنيةٍ تحتية في وجه الباحث — فيُثبَت غيابُها
 *     عن شاشاته، **ووجودُها في الإعدادات**: النقل يُفحص من طرفيه، وإلّا
 *     كان الفحص يقبل الحذف مكان النقل.
 *
 * وطبقتها طبقةُ `product-surface`: بناءٌ محلّي لشيفرة هذا الفرع، وشبكةٌ
 * معترَضة، وبلا اعتمادٍ إطلاقًا — فتعمل في كل PR.
 */

const AR = "ar";
const EN = "en";

/** أسماءُ العناصر كما هي في `messages/*.json` — لا مترادفات. */
const NAV_AR = {
  home: "الرئيسية",
  ai: "بُبريفا AI",
  portfolio: "أبحاثي",
  library: "مكتبتي",
  references: "البحث واكتشاف المراجع",
  trends: "رادار الاتجاهات",
  theses: "الرسائل",
  analysis: "البيانات والتحليل",
  manuscripts: "استوديو الورقة",
  review: "المراجعة والتحكيم",
  journals: "المجلات والنشر",
  settings: "الإعدادات",
} as const;

const GROUPS_AR = ["الاكتشاف والأدبيات", "بناء البحث", "المراجعة والنشر"] as const;

/** اسمُ منطقةِ التنقّل — `nav.primaryLabel`. */
const NAV_LABEL_AR = "التنقّل الرئيسي";
const NAV_LABEL_EN = "Primary navigation";

/** الأفعالُ الخمسة في الرئيسية — `home.*Title`. */
const INTENTS_AR = [
  "ابنِ بحثًا من فكرة",
  "ابحث عن أوراق علمية",
  "استخرج فرص نشر من رسالة علمية",
  "حلّل بيانات",
  "أكمل بحثًا قائمًا",
] as const;

/** DOI حقيقيُّ الشكل — ولا يُنادى به فهرسٌ خارجي: الشبكة معترَضة. */
const A_DOI = "10.1038/s41586-020-2649-2";

interface Seen {
  errors: string[];
}

function watch(page: Page): Seen {
  const seen: Seen = { errors: [] };
  page.on("pageerror", (error) => seen.errors.push(String(error)));
  return seen;
}

async function seedSession(page: Page) {
  await page.addInitScript(() => {
    if (sessionStorage.getItem("__seeded_experience")) return;
    sessionStorage.setItem("__seeded_experience", "1");
    localStorage.setItem("athera_access_token", "experience-access");
    localStorage.setItem("athera_refresh_token", "experience-refresh");
    localStorage.setItem("athera_token_expiry", String(Date.now() + 900_000));
  });
}

/**
 * **وضعُ التشغيل يُردّ بقيمٍ خام قصدًا.**
 *
 * `anthropic` و`s3` و`offline` هي بعينها ما كان يُعرض على الباحث في صفحة
 * الذكاء. فلو رُدّ هنا وضعٌ نظيف لمرّ الفحص على شاشةٍ عادت تُسرّبها.
 */
const POSTURE = {
  tenant_name: "فحص التجربة",
  locale: AR,
  supported_locales: ["ar", "en"],
  roles: [],
  items: [
    { key: "model_provider", label: "مزوّد النموذج", value: "anthropic", detail: "المزوّد جاهز." },
    { key: "storage", label: "تخزين ملفات البحث", value: "s3", detail: "التخزين مُهيّأ." },
    { key: "literature_registry", label: "رصد الأدبيات المجدول", value: "offline", detail: "لا رصد مجدول." },
    { key: "reference_indexes", label: "فهارس المراجع", value: "crossref, openalex", detail: "تُستدعى عند البحث." },
  ],
};

/** ردٌّ كامل الشكل لاكتشاف المراجع — فارغُ النتائج، صحيحُ العقد. */
const EMPTY_DISCOVERY = {
  candidates: [],
  providers: [
    { provider: "crossref", ok: true, detail: null, results: 0 },
    { provider: "openalex", ok: true, detail: null, results: 0 },
  ],
  providers_enabled: true,
  any_provider_failed: false,
  all_providers_failed: false,
  external_link: null,
  ordered_by: "relevance",
  query_understanding: null,
  note_ar: "لا نتائج مطابقة.",
  note_en: "No matching results.",
};

const OBJECT_BODIES = new Map<string, unknown>([
  ["/api/v1/settings/posture", POSTURE],
  ["/api/v1/references/search", EMPTY_DISCOVERY],
  ["/api/v1/inbox/summary", { pending_approvals: 0, open_alerts: 0, blocking_alerts: 0, unread_notifications: 0 }],
  ["/api/v1/files/folders", { folder_id: null, breadcrumb: [], folders: [] }],
  [
    "/api/v1/profile",
    {
      institution: null, current_rank: null, target_rank: null, primary_field: null,
      orcid: null, g0_approved_at: null, verified_memory_count: 0,
    },
  ],
]);

/** كل نداء يُجاب — نداءٌ معلَّق يُبقي «جارٍ التحميل» فيسقط الفحص على الشبكة. */
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

/** روابطُ منطقة التنقّل وحدها — لا كل روابط الصفحة. */
function nav(page: Page, label = NAV_LABEL_AR) {
  return page.getByRole("navigation", { name: label });
}

/**
 * عنوانُ مجموعةٍ دلالية — **يُطابَق بنصّ العنصر لا بالاسم المحسوب**.
 *
 * الورقة تضع `text-transform: uppercase` على `.nav-label`، وبعض المتصفّحات
 * تُدخل التحويل في الاسم المتاح. فيُقرأ `textContent` — وهو لا يتغيّر —
 * والتعبير مُثبَّت الطرفين فلا يطابق عنوانًا أطول يحتوي هذا.
 */
function groupHeading(menu: ReturnType<typeof nav>, title: string) {
  return menu.locator("h2.nav-label").filter({ hasText: new RegExp(`^\\s*${title}\\s*$`) });
}

test.describe("navigation: one active item, semantic groups, no decorative colour", () => {
  test.beforeEach(async ({ page }) => {
    await seedSession(page);
    await stubApi(page);
  });

  /**
   * المسارُ ومالكُه في القائمة. و`portfolio` تملك `approvals` لأنها تُفتح
   * من داخل بحث؛ و`settings` تملك `profile` لأنه يُفتح منها.
   */
  const OWNERSHIP: Array<[string, string]> = [
    ["", NAV_AR.home],
    ["/ai", NAV_AR.ai],
    ["/portfolio", NAV_AR.portfolio],
    ["/approvals", NAV_AR.portfolio],
    ["/library", NAV_AR.library],
    ["/references", NAV_AR.references],
    ["/trends", NAV_AR.trends],
    ["/theses", NAV_AR.theses],
    ["/analysis", NAV_AR.analysis],
    ["/manuscripts", NAV_AR.manuscripts],
    ["/review", NAV_AR.review],
    ["/journals", NAV_AR.journals],
    ["/settings", NAV_AR.settings],
    ["/profile", NAV_AR.settings],
  ];

  for (const [path, expected] of OWNERSHIP) {
    test(`/${AR}${path} marks exactly one navigation item active — and it is «${expected}»`, async ({
      page,
    }) => {
      const seen = watch(page);
      await page.goto(`/${AR}${path}`);
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();

      const menu = nav(page);
      const active = menu.locator('a[aria-current="page"]');

      // **العيب كان في الزائد.** فالعدد يُثبَت قبل الهويّة.
      await expect(active).toHaveCount(1);
      await expect(active).toHaveText(expected);

      // وكلُّ ما عداه ليس نشطًا — تصريحًا، لا استنتاجًا من العدد وحده.
      for (const name of Object.values(NAV_AR)) {
        if (name === expected) continue;
        await expect(
          menu.getByRole("link", { name, exact: true }),
        ).not.toHaveAttribute("aria-current", "page");
      }

      expect(seen.errors, `JS exceptions on /${AR}${path}`).toEqual([]);
    });
  }

  test("a route no navigation item owns lights nothing — zero is truer than an invented one", async ({
    page,
  }) => {
    // صفحةُ الدخول تُعرض داخل القشرة نفسها، ولا تخصّ عنصرًا في القائمة.
    await page.goto(`/${AR}/login`);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    await expect(nav(page).locator('a[aria-current="page"]')).toHaveCount(0);
  });

  test("the «other tools» bucket is gone and named semantic groups stand in its place", async ({
    page,
  }) => {
    await page.goto(`/${AR}`);
    const menu = nav(page);

    // سلّةُ ما تبقّى — لا تعود بأيّ صورة، مطويّةً أو مفتوحة.
    await expect(page.getByText("أدوات أخرى", { exact: true })).toHaveCount(0);
    await expect(page.locator("aside details")).toHaveCount(0);

    for (const group of GROUPS_AR) {
      await expect(groupHeading(menu, group)).toBeVisible();
    }

    // ولا عنصرَ مخفيًّا: ما كان في السلّة صار ظاهرًا بلا نقرة.
    for (const name of Object.values(NAV_AR)) {
      await expect(menu.getByRole("link", { name, exact: true })).toBeVisible();
    }
  });

  test("no decorative dot survives, and the active item is legible with every colour removed", async ({
    page,
  }) => {
    await page.goto(`/${AR}/theses`);
    const menu = nav(page);

    // النقطةُ التي لا تعني شيئًا — لا في القائمة ولا في غيرها.
    await expect(page.locator(".nav-dot")).toHaveCount(0);

    const active = menu.locator('a[aria-current="page"]');
    await expect(active).toHaveCount(1);

    // **حاملٌ غيرُ لوني.** لو أُطفئت الألوان كلّها بقي الوزنُ فارقًا، وبقي
    // `aria-current` منطوقًا. والمقارنة بجارٍ حقيقي لا بقيمةٍ محفوظة.
    const idle = menu.getByRole("link", { name: NAV_AR.analysis, exact: true });
    const weightOf = (target: typeof active) =>
      target.evaluate((node) => Number(getComputedStyle(node).fontWeight));
    expect(await weightOf(active)).toBeGreaterThan(await weightOf(idle));
  });

  test("both writing directions render their own navigation", async ({ page }) => {
    await page.goto(`/${AR}`);
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.locator("html")).toHaveAttribute("lang", AR);
    await expect(nav(page, NAV_LABEL_AR).getByRole("link", { name: NAV_AR.home, exact: true }))
      .toBeVisible();

    await page.goto(`/${EN}`);
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
    await expect(page.locator("html")).toHaveAttribute("lang", EN);
    const english = nav(page, NAV_LABEL_EN);
    await expect(english.getByRole("link", { name: "Home", exact: true })).toBeVisible();
    await expect(groupHeading(english, "Discovery & literature")).toBeVisible();
    // والنشطُ واحدٌ في اللغتين — لا خاصّيةَ عربيّة.
    await expect(english.locator('a[aria-current="page"]')).toHaveCount(1);
  });
});

test.describe("home: five intents, and truthful routing", () => {
  test.beforeEach(async ({ page }) => {
    await seedSession(page);
    await stubApi(page);
  });

  test("home asks what to accomplish and offers the five primary intents", async ({ page }) => {
    await page.goto(`/${AR}`);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("ماذا تريد أن تنجز؟");
    for (const intent of INTENTS_AR) {
      await expect(page.getByRole("link", { name: new RegExp(`^${intent}`) })).toBeVisible();
    }
  });

  test("home is not a second chat: it routes, and never generates an answer", async ({ page }) => {
    await page.goto(`/${AR}`);
    // مربّعُ المحادثة بعينه — لا يُعاد إلى الرئيسية بأي اسم.
    await expect(page.locator("#athera-ai-input")).toHaveCount(0);
    await expect(page.locator(".ai-box")).toHaveCount(0);
    await expect(page.locator("#home-intake")).toBeVisible();
  });

  test("a DOI is accepted, named as a DOI, and actually searched — no «coming soon»", async ({
    page,
  }) => {
    const asked: string[] = [];
    await page.route("**/api/v1/**", (route: Route) => {
      const url = new URL(route.request().url());
      if (url.pathname === "/api/v1/references/search") {
        asked.push(String(route.request().postData()));
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          OBJECT_BODIES.has(url.pathname) ? OBJECT_BODIES.get(url.pathname) : [],
        ),
      });
    });

    await page.goto(`/${AR}`);
    await page.locator("#home-intake").fill(A_DOI);

    // **يُقال أين سيذهب قبل أن يذهب** — وباسم النوع لا بلون.
    await expect(page.getByTestId("home-intake-route")).toContainText("DOI");
    await expect(page.getByTestId("home-intake-route")).not.toContainText("قريبًا");

    await page.getByRole("button", { name: "ابدأ", exact: true }).click();

    await expect(page).toHaveURL(new RegExp(`/${AR}/references\\?q=`));
    // والمعرّف وصل مكتوبًا في المربّع، فلا يُطلب من الباحث لصقه ثانية.
    await expect(page.locator("#reference-query")).toHaveValue(A_DOI);
    // **والبحث وقع فعلًا.** وصولٌ بلا نداءٍ توجيهٌ إلى شاشةٍ ساكنة.
    await expect.poll(() => asked.length, { timeout: 20_000 }).toBeGreaterThan(0);
    expect(asked.join("")).toContain(A_DOI);
  });

  test("free text goes to the AI surface, carrying what was written", async ({ page }) => {
    await page.goto(`/${AR}`);
    const idea = "أثر التعلّم المدمج على تحصيل طلبة الهندسة في الجامعات السعودية";
    await page.locator("#home-intake").fill(idea);
    await expect(page.getByTestId("home-intake-route")).toContainText("بُبريفا AI");
    await page.getByRole("button", { name: "ابدأ", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/${AR}/ai\\?q=`));
    await expect(page.locator("#athera-ai-input")).toHaveValue(idea);
  });

  test("the DOI/link control on the AI surface no longer claims «coming soon»", async ({ page }) => {
    await page.goto(`/${AR}/ai`);
    const link = page.getByRole("link", { name: /DOI أو رابط/ });
    await expect(link).toBeVisible();
    await expect(link).not.toContainText("قريبًا");
    await expect(link).toHaveAttribute("href", `/${AR}/references`);
  });

  test("the retired «Scientific Search» URL redirects rather than 404s", async ({ page }) => {
    await page.goto(`/${AR}/search`);
    await expect(page).toHaveURL(new RegExp(`/${AR}/references`));
    await expect(nav(page).locator('a[aria-current="page"]')).toHaveText(NAV_AR.references);
  });
});

test.describe("technical diagnostics belong in settings, not in a researcher's face", () => {
  test.beforeEach(async ({ page }) => {
    await seedSession(page);
    await stubApi(page);
  });

  /** ما لا يخصّ عملًا علميًّا: أسماءُ مزوّدين وحالاتُ بنيةٍ تحتية. */
  const INFRASTRUCTURE = ["anthropic", "not_configured", "s3", "offline"];

  for (const path of ["", "/ai", "/portfolio", "/library", "/references", "/theses"]) {
    test(`/${AR}${path} shows no provider name or storage internals`, async ({ page }) => {
      await page.goto(`/${AR}${path}`);
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
      const body = (await page.locator("body").innerText()).toLowerCase();
      for (const term of INFRASTRUCTURE) {
        expect(body, `«${term}» is visible to a researcher on /${AR}${path}`).not.toContain(term);
      }
    });
  }

  test("and settings still discloses them — the values moved, they were not deleted", async ({
    page,
  }) => {
    // **الفحص من طرفيه.** لو فُحص الغياب وحده لمرّ حذفُ الإفصاح كلّه،
    // وذاك عطبُ شفافيةٍ لا إصلاحُ تجربة.
    await page.goto(`/${AR}/settings`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const body = (await page.locator("body").innerText()).toLowerCase();
    for (const term of ["anthropic", "s3", "offline"]) {
      expect(body, `settings no longer discloses «${term}»`).toContain(term);
    }
  });
});

test.describe("keyboard, focus and viewport", () => {
  test.beforeEach(async ({ page }) => {
    await seedSession(page);
    await stubApi(page);
  });

  test("the first Tab reaches a skip link, and it moves focus into the content", async ({
    page,
  }) => {
    await page.goto(`/${AR}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.keyboard.press("Tab");

    const skip = page.getByRole("link", { name: "تخطَّ إلى المحتوى", exact: true });
    await expect(skip).toBeFocused();
    // مخفيٌّ حتى يُركَّز عليه — ثم يظهر ظهورًا كاملًا لا خافتًا.
    await expect(skip).toBeVisible();

    await page.keyboard.press("Enter");
    await expect.poll(() => page.evaluate(() => document.activeElement?.id ?? ""))
      .toBe("main-content");
  });

  test("every navigation link is reachable by keyboard and shows a visible focus ring", async ({
    page,
  }) => {
    await page.goto(`/${AR}`);
    const links = nav(page).getByRole("link");
    await expect(links.first()).toBeVisible();

    // لا رابطَ أُخرج من ترتيب الجدولة — موجودٌ للفأرة وحدها.
    const outOfOrder = await nav(page).evaluate((menu) =>
      [...menu.querySelectorAll("a[href]")]
        .filter((node) => (node as HTMLElement).tabIndex < 0).length,
    );
    expect(outOfOrder).toBe(0);

    // وحلقةُ التركيز مرئيّة: `:focus-visible` تُطبَّق على التنقّل بالمفاتيح.
    await links.first().focus();
    const ring = await links.first().evaluate((node) => {
      const style = getComputedStyle(node);
      return { width: style.outlineWidth, style: style.outlineStyle };
    });
    expect(ring.style).not.toBe("none");
    expect(Number.parseFloat(ring.width)).toBeGreaterThan(0);
  });

  test("the phone viewport shows the whole menu without a sideways scroll", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`/${AR}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    const menu = nav(page);
    // المجموعاتُ الدلاليّة تبقى مقروءة على الهاتف — لا تُطوى عند الضيق.
    for (const group of GROUPS_AR) {
      await expect(groupHeading(menu, group)).toBeVisible();
    }
    await expect(menu.getByRole("link", { name: NAV_AR.settings, exact: true })).toBeVisible();

    // **ولا تمرير أفقي للمستند.** كان `overflow-x: auto` يدفع نصف القائمة
    // خارج الحافة، ومجموعةٌ نصفُها غير مرئي تساوي المطويّ الذي أُزيل.
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, "the document scrolls sideways on a phone").toBeLessThanOrEqual(1);
  });

  test("the desktop viewport keeps the sidebar alongside the content", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`/${AR}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    const aside = await page.locator("aside.sidebar").boundingBox();
    const main = await page.locator("main#main-content").boundingBox();
    expect(aside, "the sidebar is not rendered").not.toBeNull();
    expect(main, "the content region is not rendered").not.toBeNull();
    // جنبًا إلى جنب لا واحدًا فوق الآخر — والقياس بالصناديق لا بالأنماط.
    expect(main!.y).toBeLessThan(aside!.y + aside!.height);
  });
});
