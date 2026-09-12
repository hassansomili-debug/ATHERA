import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * إغلاقُ مركز الرسائل | Thesis Center release closure — الاسمُ، والمدخلُ،
 * والمراجعةُ التي تعدّ ما يُراجَع وحده.
 *
 * **وثلاثُ دعاوى لا تُثبَت بقراءة مصدر:**
 *
 *   ١ أنّ نموذجَ التسجيل القديم **غائبٌ عن الشجرة** لا مخفيٌّ بأسلوب —
 *     و`display:none` يمرّ على فحص المصدر ولا يمرّ على المتصفّح.
 *   ٢ أنّ البيانَ النظاميّ **لا يُصدِر `/decide`** — والدعوى أنّ الطلبَ لم
 *     يخرج، فتُلتقط الطلباتُ الخارجة لا الأزرارُ المعروضة.
 *   ٣ أنّ العدّادَ يأتي **من الخادم** — فيُردّ ردٌّ محدَّدٌ ويُقرأ ما ظهر.
 *
 * الشبكةُ معترَضة والجلسةُ مزروعة، كطبقة `thesis-center`: تعمل في كلّ PR
 * بلا خادمٍ خلفي وبلا اعتماد.
 */

const APP_ORIGIN = new URL(process.env.PUBRIVA_WEB_URL ?? "http://127.0.0.1:3000").origin;
const THESIS = "11111111-2222-3333-4444-555555555555";

/** الأسماءُ المتقاعدة — **لا تعود إلى المواضع الحرجة** (البند ١٥). */
const LEGACY = ["Theses", "Thesis library", "Back to theses", "مكتبة الرسائل"];

async function seedSession(page: Page) {
  await page.addInitScript(() => {
    if (sessionStorage.getItem("__seeded_closure")) return;
    sessionStorage.setItem("__seeded_closure", "1");
    localStorage.setItem("athera_access_token", "closure-access");
    localStorage.setItem("athera_refresh_token", "closure-refresh");
    localStorage.setItem("athera_token_expiry", String(Date.now() + 900_000));
  });
}

interface Field {
  key: string;
  label: string;
  value: unknown;
  status: "unverified" | "approved" | "rejected" | "unknown";
  decidable: boolean;
  quote?: string | null;
  locator?: string | null;
  confidence?: number | null;
}

/**
 * التجهيزةُ التي وُصف بها العطب — بأرقامها (البند ٦ من الطلب):
 * بيانان نظاميّان، ومعتمَدان، ومرفوضٌ، و«لا أعرف»، وثلاثةٌ منتظِرة.
 * فالمنتظِرُ **ثلاثة** لا خمسة، والإجماليُّ **سبعة** لا تسعة.
 */
const FIELDS: Field[] = [
  { key: "page_count", label: "عدد الصفحات", value: 142, status: "unverified",
    decidable: false },
  { key: "source_filename", label: "اسم الملف", value: "thesis.pdf",
    status: "unverified", decidable: false },

  { key: "title_ar", label: "العنوان بالعربية", value: "أثرُ التدريب",
    status: "approved", decidable: true, quote: "أثرُ التدريب", locator: "ص1 §1",
    confidence: 0.94 },
  { key: "institution", label: "المؤسسة", value: "جامعة", status: "approved",
    decidable: true, quote: "جامعة", locator: "ص1 §2", confidence: 0.9 },

  { key: "degree", label: "الدرجة", value: "ماجستير", status: "rejected",
    decidable: true, quote: "ماجستير", locator: "ص1 §3", confidence: 0.6 },
  { key: "sample_size", label: "حجم العينة", value: 120, status: "unknown",
    decidable: true, quote: "١٢٠ مشاركًا", locator: "ص40 §2", confidence: 0.55 },

  { key: "research_problem", label: "مشكلة البحث", value: "فجوةٌ في القياس",
    status: "unverified", decidable: true, quote: "فجوةٌ في القياس",
    locator: "ص5 §1", confidence: 0.81 },
  { key: "main_question", label: "السؤال الرئيس", value: "ما أثرُ التدريب؟",
    status: "unverified", decidable: true, quote: "ما أثرُ التدريب؟",
    locator: "ص6 §1", confidence: 0.77 },
  { key: "methodology", label: "المنهجية", value: "تجريبي", status: "unverified",
    decidable: true, quote: "تصميمٌ تجريبي", locator: "ص38 §1", confidence: 0.7 },
];

/**
 * تجهيزةٌ جديدةٌ لكلِّ فحص — **ونسخةٌ سطحيّة لا تكفي**.
 *
 * `[...FIELDS]` ينسخ المصفوفةَ ويترك العناصرَ مشتركة، ومعالجُ `/decide`
 * يكتب في `field.status`. فاعتمادٌ في فحصٍ كان يجعل `research_problem`
 * «معتمَدًا» في كلِّ ما بعده، فيهاجر إلى القسم المطويّ ويختفي — ويسقط
 * فحصٌ لاحقٌ بسبب فحصٍ سابق، وهو أسوأ أنواع الإخفاق.
 */
function freshFields(): Field[] {
  return FIELDS.map((field) => ({ ...field }));
}

interface Server {
  fields: Field[];
  /** كلُّ طلبٍ خرج من الشاشة — **الشاهدُ على ما أُرسل وما لم يُرسَل**. */
  seen: { method: string; path: string }[];
}

/** العدُّ **كما يحسبه الخادم**: على القابل للقرار وحده. */
function tally(fields: Field[]) {
  const decidable = fields.filter((f) => f.decidable);
  const of = (s: string) => decidable.filter((f) => f.status === s).length;
  const pending = of("unverified");
  return {
    total: fields.length,
    reviewable_total: of("approved") + of("rejected") + of("unknown") + pending,
    approved: of("approved"),
    rejected: of("rejected"),
    unknown: of("unknown"),
    pending,
  };
}

function reviewBody(server: Server) {
  const group = (key: string, label: string, keys: string[]) => ({
    key,
    label,
    fields: server.fields
      .filter((f) => keys.includes(f.key))
      .map((f) => ({
        id: `cand-${f.key}`,
        field_key: f.key,
        label: f.label,
        value: f.value,
        status: f.status,
        extraction_status: "found",
        extraction_confidence: f.confidence ?? null,
        quote: f.quote ?? null,
        locator: f.locator ?? null,
        decided_at: null,
        edited_by_human: false,
        conflict_with: null,
        decidable: f.decidable,
      })),
  });
  return {
    thesis_id: THESIS,
    thesis_title: "أثرُ التدريب على الأداء",
    source_filename: "thesis.pdf",
    sections: [
      group("metadata", "بيانات الرسالة",
            ["page_count", "source_filename", "title_ar", "institution", "degree"]),
      group("problem", "المشكلة", ["research_problem"]),
      group("questions", "الأسئلة", ["main_question"]),
      group("methodology", "المنهجية", ["methodology", "sample_size"]),
    ].filter((g) => g.fields.length > 0),
    ...tally(server.fields),
    note: "هذه مقترحات استخرجتها أثيرا من ملفك، وليست حقائق معتمدة.",
  };
}

async function serve(page: Page, server: Server) {
  await page.route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    server.seen.push({ method, path });

    const send = (payload: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(payload) });

    // **والطبقةُ تسقط على ردٍّ فارغ.** `{}` لِـ`posture` تُعطِّل الشريطَ
    // والقائمة، فتنهار الشجرةُ ويقرأ الباحثُ «This page couldn't load» —
    // وهو عطبُ التجهيزة لا عطبُ الشاشة.
    if (path === "/api/v1/settings/posture") {
      return send({
        tenant_name: "مركز الرسائل", locale: "ar", supported_locales: ["ar", "en"],
        roles: [], items: [],
      });
    }
    if (path === "/api/v1/inbox/summary") {
      return send({
        pending_approvals: 0, open_alerts: 0, blocking_alerts: 0, unread_notifications: 0,
      });
    }
    if (path === "/api/v1/theses" && method === "GET") return send([]);
    if (path === `/api/v1/theses/${THESIS}/review`) return send(reviewBody(server));
    if (path === `/api/v1/theses/${THESIS}/consent`) {
      return send({
        file_id: "f-1", state: "granted", capability: "thesis_extraction_external_c2",
        max_classification: "C2", provider: "anthropic", model: "m",
        title: "إذن", body: "نصّ الإذن",
      });
    }
    const decide = path.match(/^\/api\/v1\/theses\/candidates\/cand-([a-z_]+)\/decide$/);
    if (decide && method === "POST") {
      const key = decide[1];
      const post = route.request().postDataJSON() as { decision: string };
      const field = server.fields.find((f) => f.key === key);
      if (field) {
        field.status = post.decision === "approve"
          ? "approved" : post.decision === "reject" ? "rejected" : "unknown";
      }
      return send({ id: `cand-${key}`, field_key: key, status: field?.status });
    }
    // نداءٌ معلَّق يُبقي «جارٍ التحميل» إلى الأبد — فكلُّ ما عدا ذلك يُجاب.
    return send([]);
  });
}

async function openReview(page: Page, locale: "ar" | "en") {
  await page.goto(`/${locale}/theses/${THESIS}/review`);
  await expect(page.getByTestId("review-thesis-name")).toBeVisible({ timeout: 20_000 });
}

test.beforeEach(async ({ page }) => {
  await seedSession(page);
});

// ══════════ ١. الاسمُ والهويّة ══════════

test.describe("the Thesis Center is named that, in both locales", () => {
  for (const [locale, expected] of [["en", "Thesis Center"], ["ar", "مركز الرسائل"]] as const) {
    test(`${locale}: heading and navigation read «${expected}»`, async ({ page }) => {
      const server: Server = { fields: freshFields(), seen: [] };
      await serve(page, server);
      await page.goto(`/${locale}/theses`);

      const h1 = page.getByRole("heading", { level: 1 }).first();
      await expect(h1).toHaveText(expected);
      // والقائمةُ تحمل الاسمَ نفسَه — لا اسمًا ثانيًا للشيء الواحد.
      await expect(
        page.getByRole("navigation").getByRole("link", { name: expected }).first(),
      ).toBeVisible();
    });
  }

  test("the retired names are absent from the critical places", async ({ page }) => {
    const server: Server = { fields: freshFields(), seen: [] };
    await serve(page, server);

    for (const locale of ["ar", "en"] as const) {
      await page.goto(`/${locale}/theses`);
      const h1 = await page.getByRole("heading", { level: 1 }).first().innerText();
      const nav = await page.getByRole("navigation").innerText();
      for (const legacy of LEGACY) {
        expect(h1, `${locale} H1 carries «${legacy}»`).not.toContain(legacy);
        expect(nav, `${locale} nav carries «${legacy}»`).not.toContain(legacy);
      }

      await openReview(page, locale);
      const head = await page.getByRole("heading", { level: 1 }).first().innerText();
      const back = await page.getByRole("link", { name: /مركز الرسائل|Thesis Center/ })
        .first().innerText();
      for (const legacy of LEGACY) {
        expect(head, `${locale} review H1 carries «${legacy}»`).not.toContain(legacy);
        expect(back, `${locale} back link carries «${legacy}»`).not.toContain(legacy);
      }
    }
  });
});

// ══════════ ٢. المدخلُ: رفعُ ملفّ، ولا نموذجَ تسجيلٍ في الشجرة ══════════

test.describe("the only way in is a file", () => {
  test("the retired registration form is gone from the DOM, not hidden", async ({ page }) => {
    const server: Server = { fields: freshFields(), seen: [] };
    await serve(page, server);

    for (const locale of ["ar", "en"] as const) {
      await page.goto(`/${locale}/theses`);
      await expect(page.getByTestId("thesis-intake")).toBeVisible();

      // **وحضورُ الحقول يُقاس بالعدّ لا بالظهور**: `toBeHidden` يمرّ على
      // عنصرٍ قائمٍ في الشجرة، وهو ما يُمنع هنا صراحةً.
      for (const label of ["Degree", "الدرجة العلمية", "Defence date", "تاريخ المناقشة",
                           "Rights basis", "سند الحقوق", "Supervisor", "المشرف"]) {
        await expect(page.getByLabel(label)).toHaveCount(0);
      }
      // ولا زرَّ تسجيلٍ ولا عنوانَ له.
      await expect(page.getByRole("button", { name: /Register|تسجيل رسالة/ })).toHaveCount(0);
      // وعددُ النماذج: البحثُ وحده — لا نموذجٌ ثانٍ للتسجيل.
      expect(await page.locator("form").count()).toBeLessThanOrEqual(1);
    }
  });
});

// ══════════ ٣. بياناتُ الملفّ: تُعرض، ولا تُراجَع ══════════

test.describe("system metadata is shown, never reviewed", () => {
  test("it sits in its own block and claims no pending review", async ({ page }) => {
    const server: Server = { fields: freshFields(), seen: [] };
    await serve(page, server);
    await openReview(page, "ar");

    const block = page.getByTestId("review-file-metadata");
    await expect(block).toBeVisible();
    await expect(block).toContainText("معلومة نظامية");

    for (const key of ["page_count", "source_filename"]) {
      const row = page.getByTestId(`review-metadata-${key}`);
      await expect(row).toHaveCount(1);
      await expect(row).toHaveAttribute("data-candidate-status", "system_metadata");
      // ولا «بانتظار مراجعتك» عليه.
      await expect(row).not.toContainText("بانتظار");
    }
  });

  test("it offers no decision control", async ({ page }) => {
    const server: Server = { fields: freshFields(), seen: [] };
    await serve(page, server);
    await openReview(page, "ar");

    const block = page.getByTestId("review-file-metadata");
    expect(await block.getByRole("button").count()).toBe(0);
    // ولا بطاقةَ قرارٍ له أصلًا — البطاقاتُ للأدلّة العلمية.
    await expect(page.locator('[data-field-card="page_count"]')).toHaveCount(0);
    await expect(page.locator('[data-field-card="source_filename"]')).toHaveCount(0);
  });

  test("no /decide request can be emitted for it", async ({ page }) => {
    const server: Server = { fields: freshFields(), seen: [] };
    await serve(page, server);
    await openReview(page, "ar");
    await page.getByTestId("review-file-metadata").click();

    // **والدعوى أنّ الطلبَ لم يخرج** — لا أنّ الزرَّ غائب.
    const decides = server.seen.filter((r) => r.path.includes("/decide"));
    expect(decides, `طلبُ قرارٍ خرج: ${JSON.stringify(decides)}`).toEqual([]);
  });
});

// ══════════ ٤. العدّاد: من الخادم، وعلى ما يُراجَع وحده ══════════

test.describe("the counter counts only what can be reviewed", () => {
  test("the reported fixture yields pending=3 and total=7", async ({ page }) => {
    const server: Server = { fields: freshFields(), seen: [] };
    await serve(page, server);
    await openReview(page, "ar");

    const line = page.locator("[data-review-total]").first();
    // سبعةٌ لا تسعة: البيانان النظاميّان خارج العدّ.
    await expect(line).toHaveAttribute("data-review-total", "7");
    await expect(line).toHaveAttribute("data-review-approved", "2");
    // وثلاثةٌ منتظِرة لا خمسة.
    await expect(line).toContainText("3");
  });

  test("a decision moves the counter, and the server is its source", async ({ page }) => {
    const server: Server = { fields: freshFields(), seen: [] };
    await serve(page, server);
    await openReview(page, "ar");

    const line = page.locator("[data-review-total]").first();
    await expect(line).toHaveAttribute("data-review-approved", "2");

    const card = page.locator('[data-field-card="research_problem"]');
    await expect(card).toBeVisible();
    await card.getByRole("button", { name: /اعتمد|Approve/ }).first().click();

    // الطلبُ خرج…
    await expect
      .poll(() => server.seen.filter((r) => r.path.includes("/decide")).length)
      .toBeGreaterThan(0);
    // …والعدّادُ تحرّك بما ردّه الخادمُ لا بحسابٍ في الشاشة.
    await expect(line).toHaveAttribute("data-review-approved", "3");
    await expect(line).toHaveAttribute("data-review-total", "7");
  });
});

test.describe("an older API must never render «undefined»", () => {
  test("the review total falls back to the four categories when the field is absent",
    async ({ page }) => {
      const server: Server = { fields: freshFields(), seen: [] };
      await serve(page, server);
      // **خادمٌ أقدم**: العقدُ بلا `reviewable_total` — كما في الإنتاج حين
      // سبق الوِبُ الـAPI. والفئاتُ الأربع موجودةٌ فيه، فيُشتقّ منها.
      await page.route(`**/api/v1/theses/${THESIS}/review`, async (route) => {
        const body = reviewBody(server) as Record<string, unknown>;
        delete body.reviewable_total;
        await route.fulfill({
          status: 200, contentType: "application/json", body: JSON.stringify(body),
        });
      });
      await openReview(page, "ar");

      const line = page.locator("[data-review-total]").first();
      await expect(line).toHaveAttribute("data-review-total", "7");
      await expect(line).not.toContainText("undefined");
      await expect(page.locator("body")).not.toContainText("undefined");
    });
});

// ══════════ ٥. تجربةُ المراجعة ══════════

test.describe("the review screen puts the decision first", () => {
  test("research evidence keeps its quote, locator and extraction confidence",
    async ({ page }) => {
      const server: Server = { fields: freshFields(), seen: [] };
      await serve(page, server);
      await openReview(page, "ar");

      const card = page.locator('[data-field-card="research_problem"]');
      await expect(card).toContainText("فجوةٌ في القياس");   // الاقتباس
      await expect(card).toContainText("ص5 §1");             // الموضع
      await expect(card).toContainText("81");               // ثقةُ الاستخراج
    });

  test("pending comes before settled inside a section", async ({ page }) => {
    const server: Server = { fields: freshFields(), seen: [] };
    await serve(page, server);
    await openReview(page, "ar");

    // المنهجيةُ منتظِرة وحجمُ العيّنة «لا أعرف» — والمنتظِرُ أوّلًا.
    const keys = await page.locator("[data-field-card]")
      .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("data-field-card")));
    expect(keys.indexOf("methodology")).toBeLessThan(keys.indexOf("sample_size"));
  });

  test("approved is collapsed until asked for", async ({ page }) => {
    const server: Server = { fields: freshFields(), seen: [] };
    await serve(page, server);
    await openReview(page, "ar");

    const toggle = page.getByTestId("review-approved-toggle");
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await expect(page.locator('[data-field-card="title_ar"]')).toHaveCount(0);

    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await expect(page.locator('[data-field-card="title_ar"]')).toHaveCount(1);
  });

  test("«review next» moves to the first pending field and focuses it", async ({ page }) => {
    const server: Server = { fields: freshFields(), seen: [] };
    await serve(page, server);
    await openReview(page, "ar");

    await page.getByTestId("review-next").click();
    const focused = await page.evaluate(
      () => document.activeElement?.getAttribute("data-field-card"));
    expect(focused).toBe("research_problem");
  });

  test("the thesis being reviewed is named, with a declared filename fallback",
    async ({ page }) => {
      const server: Server = { fields: freshFields(), seen: [] };
      await serve(page, server);
      await openReview(page, "ar");
      await expect(page.getByTestId("review-thesis-name"))
        .toHaveAttribute("data-name-source", "title");
      await expect(page.getByTestId("review-thesis-name")).toContainText("أثرُ التدريب");
    });
});

// ══════════ ٦. التنقّل واللغة ══════════

test.describe("navigation keeps the researcher's place", () => {
  test("the back link returns to the Thesis Center in the same locale", async ({ page }) => {
    const server: Server = { fields: freshFields(), seen: [] };
    await serve(page, server);

    for (const locale of ["ar", "en"] as const) {
      await openReview(page, locale);
      await page.getByRole("link", { name: /مركز الرسائل|Thesis Center/ }).first().click();
      await expect(page).toHaveURL(new RegExp(`/${locale}/theses$`));
    }
  });

  test("switching locale keeps the thesis being reviewed", async ({ page }) => {
    const server: Server = { fields: freshFields(), seen: [] };
    await serve(page, server);
    await openReview(page, "ar");

    await page.locator(".locale-switch a").first().click();
    await expect(page).toHaveURL(new RegExp(`/en/theses/${THESIS}/review`));
  });
});

// ══════════ ٧. لا فيضٌ أفقيّ ══════════

test.describe("nothing overflows sideways", () => {
  for (const [name, size] of [
    ["desktop", { width: 1280, height: 900 }],
    ["mobile", { width: 390, height: 844 }],
  ] as const) {
    test(`${name}: Thesis Center and Review fit their width`, async ({ page }) => {
      const server: Server = { fields: freshFields(), seen: [] };
      await serve(page, server);
      await page.setViewportSize(size);

      for (const go of [
        () => page.goto("/ar/theses"),
        () => openReview(page, "ar"),
      ]) {
        await go();
        const over = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        expect(over, `${name}: فيضٌ أفقيّ بمقدار ${over}px`).toBeLessThanOrEqual(1);
      }
    });
  }
});
