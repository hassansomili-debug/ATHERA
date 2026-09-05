import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * ذكاءُ الباحث في المتصفّح | Researcher intelligence surface (Wave 2-A).
 *
 * تُثبت هذه الحزمة أربعة، وأخطرها الثالث:
 *
 *   ١ **الشاشتان تعملان بالعربية وبالإنجليزية استقلالًا** — كلتاهما لغةٌ
 *     أولى، لا ترجمةٌ لاحقة للأخرى.
 *   ٢ **والمرشَّحُ يختلف عن المؤكَّد بغير اللون وحده**: شارةٌ مكتوبة، ونصٌّ
 *     صريحٌ يقول «ليس في ملفّك»، وموضعٌ مستقلٌّ في الصفحة.
 *   ٣ **وتبديلُ لغة الواجهة لا يمسّ لغةَ المخطوطة المستهدَفة.** ومن بدّل
 *     لغةَ الشاشة يجب أن يجد هدفَ نشره كما تركه — ولا طلبَ كتابةٍ واحدًا
 *     يُرسَل من جرّاء التبديل. وهذا هو الفحصُ الذي كُتب الملفُّ لأجله.
 *   ٤ **ولا نسبةَ جاهزيةٍ ولا احتمالَ قبولٍ في الشاشة.**
 *
 * وطبقتها طبقةُ `product-surface`: شبكةٌ معترَضة، وبلا اعتماد، فتعمل في
 * كل PR.
 */

const AR = "ar";
const EN = "en";

/** `app.loading` كما هي في `messages/ar.json`. */
const LOADING_AR = "جارٍ التحميل…";

const APP_ORIGIN = new URL(process.env.PUBRIVA_WEB_URL ?? "http://127.0.0.1:3000").origin;

const PROFILE = {
  id: "11111111-1111-4111-8111-111111111111",
  user_id: "22222222-2222-4222-8222-222222222222",
  institution_ar: "جامعةُ الملك سعود",
  institution_en: "King Saud University",
  college_ar: null,
  department_ar: null,
  current_rank: "assistant_professor",
  target_rank: null,
  primary_field_ar: null,
  primary_field_en: null,
  country: null,
  keywords: null,
  preferred_research_languages: null,
  preferred_working_language: AR,
  // **لغةُ المخطوطة إنجليزية بينما لغةُ الشاشة عربية** — وهي بعينها الحال
  // التي يقع فيها الخلط، فتُثبَّت هنا ولا تُبدَّل.
  preferred_manuscript_language: EN,
  ai_response_language: AR,
  orcid: "0000-0002-1694-233X",
  orcid_status: "user_declared",
  orcid_verified_at: null,
  orcid_source: null,
  field_provenance: null,
};

const CANDIDATES = [
  {
    id: "33333333-3333-4333-8333-333333333333",
    field_name: "department_ar",
    candidate_value: "قسمُ علوم الحاسب",
    source_type: "cv_upload",
    source_id: null,
    provenance: "سيرةٌ ذاتية — صفحة ١",
    extraction_method: "deterministic",
    profile_state: "document_extracted",
    status: "proposed",
    in_active_profile: false,
    created_at: "2026-01-01T00:00:00Z",
    decided_at: null,
    decided_by: null,
    decision_reason: null,
  },
];

const GOALS = [
  {
    id: "44444444-4444-4444-8444-444444444444",
    goal_type: "publication",
    target: "ورقتان في مجلّةٍ محكَّمة",
    priority: "high",
    timeframe: "خلال سنة",
    status: "active",
    researcher_confirmed: true,
    notes: null,
    created_at: "2026-01-01T00:00:00Z",
  },
];

const CONSTRAINTS = [
  {
    id: "55555555-5555-4555-8555-555555555555",
    constraint_type: "no_fee_preference",
    value: "أفضّل مجلّاتٍ بلا رسوم نشر",
    notes: null,
    researcher_confirmed: true,
    created_at: "2026-01-01T00:00:00Z",
  },
];

const BODIES = new Map<string, unknown>([
  ["/api/v1/researcher/profile", PROFILE],
  ["/api/v1/researcher/profile/candidates", CANDIDATES],
  ["/api/v1/researcher/goals", GOALS],
  ["/api/v1/researcher/constraints", CONSTRAINTS],
  ["/api/v1/inbox/summary", {
    pending_approvals: 0, open_alerts: 0,
    blocking_alerts: 0, unread_notifications: 0,
  }],
]);

interface Seen {
  errors: string[];
  serverErrors: string[];
  writes: string[];
}

function watch(page: Page): Seen {
  const seen: Seen = { errors: [], serverErrors: [], writes: [] };
  page.on("pageerror", (error) => seen.errors.push(String(error)));
  page.on("response", (response) => {
    if (new URL(response.url()).origin !== APP_ORIGIN) return;
    if (response.status() >= 500) {
      seen.serverErrors.push(`${response.status()} ${response.url()}`);
    }
  });
  return seen;
}

async function seedSession(page: Page) {
  await page.addInitScript(() => {
    if (sessionStorage.getItem("__ri_seeded")) return;
    sessionStorage.setItem("__ri_seeded", "1");
    localStorage.setItem("athera_access_token", "researcher-access");
    localStorage.setItem("athera_refresh_token", "researcher-refresh");
    localStorage.setItem("athera_token_expiry", String(Date.now() + 900_000));
  });
}

/** كلُّ نداءٍ يُجاب — ونداءٌ معلَّقٌ يُبقي «جارٍ التحميل…» إلى الأبد. */
async function stubApi(page: Page, seen?: Seen) {
  await page.route("**/api/v1/**", (route: Route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (seen && request.method() !== "GET") {
      seen.writes.push(`${request.method()} ${path}`);
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(BODIES.has(path) ? BODIES.get(path) : []),
    });
  });
}

test.describe("ذكاءُ الباحث — الملفّ والأهداف والقيود", () => {
  test.beforeEach(async ({ page }) => {
    await seedSession(page);
  });

  test("الملفُّ البحثيُّ يُفتح بالعربية ويقول ما ليس في الملفّ", async ({ page }) => {
    const seen = watch(page);
    await stubApi(page);

    await page.goto(`/${AR}/researcher-profile`);
    await expect(page).not.toHaveURL(/\/login/);
    await expect(
      page.getByRole("heading", { name: "ملفي البحثي", exact: true }),
    ).toBeVisible();
    await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

    const candidate = page.getByTestId("profile-candidate").first();
    await expect(candidate).toBeVisible();
    // **والحقيقةُ الحاسمة مكتوبةٌ نصًّا، لا مرموزةٌ بلون.**
    await expect(candidate.getByText("ليس في ملفّك", { exact: true })).toBeVisible();
    await expect(candidate.getByText("مستخرَجة من مستند", { exact: true })).toBeVisible();

    // والزرّان يُطلبان داخل بطاقتهما لا في الصفحة كلِّها.
    await expect(candidate.getByRole("button", { name: "تأكيد", exact: true })).toBeEnabled();
    await expect(candidate.getByRole("button", { name: "رفض", exact: true })).toBeEnabled();

    expect(seen.errors).toEqual([]);
    expect(seen.serverErrors).toEqual([]);
  });

  test("والشاشةُ نفسها تعمل بالإنجليزية استقلالًا", async ({ page }) => {
    const seen = watch(page);
    await stubApi(page);

    await page.goto(`/${EN}/researcher-profile`);
    await expect(
      page.getByRole("heading", { name: "Researcher Profile", exact: true }),
    ).toBeVisible();
    await expect(page.getByText("Loading…")).toHaveCount(0, { timeout: 20_000 });

    const candidate = page.getByTestId("profile-candidate").first();
    await expect(
      candidate.getByText("Not in your profile", { exact: true }),
    ).toBeVisible();
    await expect(
      candidate.getByRole("button", { name: "Confirm", exact: true }),
    ).toBeEnabled();

    expect(seen.errors).toEqual([]);
    expect(seen.serverErrors).toEqual([]);
  });

  test("تبديلُ لغة الواجهة لا يبدّل لغةَ المخطوطة ولا يكتب شيئًا", async ({ page }) => {
    const seen = watch(page);
    await stubApi(page, seen);

    await page.goto(`/${AR}/researcher-profile`);
    await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });
    const arabicScreen = page.locator("#profile-preferred_manuscript_language");
    await expect(arabicScreen).toHaveValue(EN);

    // ثمّ تُقرأ الشاشةُ نفسها بالإنجليزية — والقيمةُ يجب أن تبقى كما هي.
    await page.goto(`/${EN}/researcher-profile`);
    await expect(page.getByText("Loading…")).toHaveCount(0, { timeout: 20_000 });
    const englishScreen = page.locator("#profile-preferred_manuscript_language");
    await expect(englishScreen).toHaveValue(EN);

    // **ولا طلبَ كتابةٍ واحدًا وقع من جرّاء التبديل.**
    expect(seen.writes).toEqual([]);
    expect(seen.errors).toEqual([]);
    expect(seen.serverErrors).toEqual([]);
  });

  test("الأهدافُ والقيود تُعرضان، ولا نسبةَ في الشاشة", async ({ page }) => {
    const seen = watch(page);
    await stubApi(page);

    await page.goto(`/${AR}/research-goals`);
    await expect(
      page.getByRole("heading", { name: "أهدافي البحثية وقيودي", exact: true }),
    ).toBeVisible();
    await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

    await expect(page.getByTestId("research-goal").first()).toBeVisible();
    await expect(page.getByTestId("research-constraint").first()).toBeVisible();

    // **ولا رقمَ يوهم يقينًا** — ولا شريطَ تقدّمٍ ولا علامةَ نسبة.
    const body = (await page.locator("body").innerText()).toLowerCase();
    for (const forbidden of ["readiness", "probability", "%", "جاهزية", "احتمال القبول"]) {
      expect(body).not.toContain(forbidden);
    }
    await expect(page.locator("progress")).toHaveCount(0);

    expect(seen.errors).toEqual([]);
    expect(seen.serverErrors).toEqual([]);
  });

  test("وتُبلَغان من الإعدادات بالاسم", async ({ page }) => {
    const seen = watch(page);
    await stubApi(page);

    await page.goto(`/${AR}/settings`);
    // **يُطلب الرابطُ بوجهته لا باسمه المعروض**: الاسمُ المتاح يضمّ العنوانَ
    // وتلميحَه معًا، فمطابقةٌ تامّةٌ للعنوان وحده تسقط على تفصيلِ تركيبٍ لا
    // على عيبِ منتج.
    const toProfile = page.locator('a[href="/ar/researcher-profile"]').first();
    const toGoals = page.locator('a[href="/ar/research-goals"]').first();
    await expect(toProfile).toBeVisible();
    await expect(toProfile).toContainText("ملفي البحثي");
    await expect(toGoals).toBeVisible();
    await expect(toGoals).toContainText("أهدافي وقيودي");

    expect(seen.errors).toEqual([]);
    expect(seen.serverErrors).toEqual([]);
  });
});
