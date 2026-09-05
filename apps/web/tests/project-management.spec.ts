import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * إدارة المشروع في متصفّح حقيقي | Project management, real browser (Wave1-B).
 *
 * **صفحةٌ تُصيَّر ليست منتجًا يعمل.** وفحصُ العقود في بايثون يثبت أن
 * الخادم يقول الصواب؛ وهذا يثبت أن الباحث **يرى** الصواب: أن اللوحة تنتهي
 * من التحميل، وأن العنوان المُلفَّق لا يظهر، وأن الاقتراح لا يُعرض حكمًا،
 * وأن المعاينة تسبق زرّ الإتلاف.
 *
 * **وطبقته طبقة `product-surface`**: بناءٌ محلّي لشيفرة هذا الفرع، وشبكةٌ
 * معترَضة، وبلا اعتمادٍ إطلاقًا — فيعمل في كل PR ولا يحتاج خادمًا خلفيًّا.
 */

const AR = "ar";
const LOADING_AR = "جارٍ التحميل…";
const PROJECT = "11111111-1111-4111-8111-111111111111";
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

async function seedSession(page: Page) {
  await page.addInitScript(() => {
    if (sessionStorage.getItem("__pm_seeded")) return;
    sessionStorage.setItem("__pm_seeded", "1");
    localStorage.setItem("athera_access_token", "pm-access");
    localStorage.setItem("athera_refresh_token", "pm-refresh");
    localStorage.setItem("athera_token_expiry", String(Date.now() + 900_000));
  });
}

/**
 * عنوانٌ مُلفَّق كما ظهر في الإنتاج — نصُّ تدقيقٍ وطابعٌ زمني.
 *
 * **والخادم هو من يطبّق العقد**، فالجسم هنا يحمل ما يردّه فعلًا: البديل
 * وسببه وتاريخ الإنشاء في حقلٍ منفصل. والشاشة تُفحص على ألّا تعيد تركيبه.
 */
const UNTITLED = {
  display_ar: "مشروع بدون عنوان",
  display_en: "Untitled project",
  is_placeholder: true,
  placeholder_reason: "audit_timestamp",
  created_at: "2026-09-09T17:12:41.883012+00:00",
  can_rename: true,
};

const DASHBOARD = {
  project_id: PROJECT,
  title: UNTITLED,
  stage: {
    current_stage: "analysis",
    current_stage_label: "التحليل",
    is_researcher_confirmed: false,
    confirmed_by: null,
    confirmed_at: null,
    confirmation_note_ar: null,
    suggestion: {
      is_offered: false,
      stage: null,
      stage_label: null,
      basis_kind: "none",
      basis: "لم يُعتمد بعد مَعْلَم «اكتمال التحليل» الذي تنتهي به «التحليل».",
    },
    disclaimer: "المرحلة ما أكّدتَه أنت. والمنصّة تقترح ولا تُقرّر.",
  },
  start_date: null,
  target_completion_date: null,
  counts: {
    open: 2,
    overdue: 1,
    awaiting_your_decision: 1,
    awaiting_review: 0,
    blocked: 0,
    completed: 0,
    total: 2,
  },
  team_members: 1,
  missing_scientific_items: [
    {
      key: "dataset",
      label: "مجموعة بيانات",
      expected_since_stage: "data_preparation_collection",
      expected_since_stage_label: "تهيئة البيانات وجمعها",
    },
  ],
  recent_activity: [],
  needs_your_attention: [
    {
      key: "overdue_tasks",
      label: "المهام المتأخرة",
      detail: "1 مهمّة فات موعدها ولم تكتمل.",
      count: 1,
      destination: "tasks",
    },
    {
      key: "stage_unconfirmed",
      label: "لم تؤكِّد مرحلة البحث بعد",
      detail: "يُعرض البحث عند «التحليل» موضعَ بدءٍ للعرض.",
      count: null,
      destination: "stage",
    },
  ],
  nothing_urgent_note: "لا شيء متأخّرٌ ولا موقوفٌ على قرارك الآن.",
};

const TASKS = {
  project_id: PROJECT,
  tasks: [
    {
      id: "22222222-2222-4222-8222-222222222222",
      project_id: PROJECT,
      title: "استخراج المتغيّرات من المصفوفة",
      description: null,
      stage: "analysis",
      stage_label: "التحليل",
      status: "in_progress",
      status_label: "قيد العمل",
      priority: "high",
      priority_label: "عالية",
      assignee_member_id: "33333333-3333-4333-8333-333333333333",
      assignee_name: "د. سارة",
      created_by: "44444444-4444-4444-8444-444444444444",
      source: "researcher_created",
      source_label: "أنشأها الباحث",
      suggested_by_system: false,
      accepted_by: null,
      accepted_at: null,
      due_at: "2026-01-01T00:00:00+00:00",
      started_at: "2026-02-01T00:00:00+00:00",
      completed_at: null,
      is_overdue: true,
      requires_decision: false,
      decision_gate: null,
      related_entity_type: null,
      related_entity_id: null,
      created_at: "2026-01-01T00:00:00+00:00",
      updated_at: "2026-02-01T00:00:00+00:00",
    },
  ],
  counts: {
    open: 1,
    overdue: 1,
    awaiting_your_decision: 0,
    awaiting_review: 0,
    blocked: 0,
    completed: 0,
    total: 1,
  },
  note: "إتمامُ مهمّةٍ إنجازُ عمل، لا شهادةٌ بصحّةٍ علمية.",
};

const SUGGESTIONS = {
  project_id: PROJECT,
  suggestions: [
    {
      key: "register_dataset",
      title_ar: "سجّل مجموعة بيانات هذا البحث",
      why_ar: "لا مجموعة بياناتٍ مسجَّلة في هذا البحث.",
      stage: "data_preparation_collection",
      stage_label: "تهيئة البيانات وجمعها",
      priority: "normal",
      source: "research_brain_suggestion",
    },
  ],
  note: "هذه معاينة — لم يُنشأ منها شيء، ولا تصير مهمّةً في قائمتك إلا بقبولك.",
};

const TIMELINE = {
  start_date: "2026-01-05",
  target_completion_date: "2026-12-01",
  milestones: [
    {
      key: "idea_approved",
      label: "اعتماد الفكرة",
      target_date: null,
      completed_at: "2026-01-10T00:00:00+00:00",
      completed_by: "44444444-4444-4444-8444-444444444444",
      evidence_note_ar: null,
      is_completed: true,
    },
    {
      key: "analysis_completed",
      label: "اكتمال التحليل",
      target_date: "2026-06-01",
      completed_at: null,
      completed_by: null,
      evidence_note_ar: null,
      is_completed: false,
    },
  ],
  stage_events: [],
};

const HISTORY = {
  project_id: PROJECT,
  events: [
    {
      id: "55555555-5555-4555-8555-555555555555",
      from_stage: "analysis",
      from_stage_label: "التحليل",
      to_stage: "design_methodology",
      to_stage_label: "التصميم والمنهجية",
      occurred_at: "2026-03-01T09:00:00+00:00",
      confirmed_by: "44444444-4444-4444-8444-444444444444",
      note_ar: "التحليل كشف عيبًا في التصميم",
      system_suggested_stage: "scientific_writing",
      followed_the_suggestion: false,
      is_return_to_earlier_stage: true,
    },
  ],
  note: "كلُّ سطرٍ هنا اعتمادُ إنسان.",
};

const DELETION_PREVIEW = {
  project_id: PROJECT,
  title: UNTITLED,
  is_in_trash: true,
  dependencies: [
    { kind: "sources", count: 12, label: "مرجعًا في مجموعة هذا البحث" },
    { kind: "claims", count: 3, label: "ادعاءً علميًّا" },
    { kind: "approved_knowledge", count: 5, label: "معرفةً موثَّقة معتمَدة" },
    { kind: "files", count: 4, label: "ملفًّا مرتبطًا" },
    { kind: "team", count: 2, label: "عضوًا في الفريق" },
    { kind: "tasks", count: 7, label: "مهمّة" },
    { kind: "decisions", count: 1, label: "قرارًا مسجَّلًا" },
    { kind: "manuscript", count: 1, label: "مخطوطة" },
    { kind: "synthesis_objects", count: 9, label: "عنصرًا في طبقة التركيب" },
    { kind: "audit_dependencies", count: 44, label: "حدثًا في سجلّ التدقيق يشير إلى هذا البحث" },
  ],
  total_dependent_rows: 88,
  is_blocked: true,
  blocked_reason: "retention_policy_undefined",
  message: "الإتلاف الدائم موقوف: لا سياسةَ احتفاظٍ قابلةً للتنفيذ في هذا النظام.",
  unblock_requirement: "يُرفع الوقف بقرار معمارية مكتوب يحدّد مدّة الاحتفاظ وإذن الإتلاف.",
  policy_sources: ["docs/data-classification.md"],
};

const TRASH = {
  projects: [
    {
      project_id: PROJECT,
      title: UNTITLED,
      created_at: "2026-09-09T17:12:41.883012+00:00",
      deleted_at: "2026-09-10T08:00:00+00:00",
      deleted_by: "44444444-4444-4444-8444-444444444444",
    },
  ],
  note: "ما في السلّة باقٍ كما هو ويمكن استعادته.",
};

const BODIES = new Map<string, unknown>([
  [`/api/v1/project-management/projects/${PROJECT}/dashboard`, DASHBOARD],
  [`/api/v1/project-management/projects/${PROJECT}/tasks`, TASKS],
  [`/api/v1/project-management/projects/${PROJECT}/task-suggestions`, SUGGESTIONS],
  [`/api/v1/project-management/projects/${PROJECT}/timeline`, TIMELINE],
  [`/api/v1/project-management/projects/${PROJECT}/stage/history`, HISTORY],
  [`/api/v1/project-management/trash`, TRASH],
  [`/api/v1/project-management/trash/${PROJECT}/deletion-preview`, DELETION_PREVIEW],
  ["/api/v1/inbox/summary", { pending_approvals: 0, open_alerts: 0, blocking_alerts: 0, unread_notifications: 0 }],
  [
    "/api/v1/settings/posture",
    { tenant_name: "فحص الإدارة", locale: AR, supported_locales: ["ar", "en"], roles: [], items: [] },
  ],
]);

/**
 * كل نداءٍ يُجاب — **ولا نداء يُترك معلَّقًا**.
 *
 * ونداءٌ لا يُجاب يُبقي «جارٍ التحميل…» قائمًا إلى الأبد، فيسقط الفحص على
 * الشبكة لا على المنتج، ويُفهم العيب في غير موضعه.
 *
 * والإتلاف الدائم وحده يُجاب بـ٤٠٩ كما يفعل الخادم فعلًا.
 */
async function stubApi(page: Page) {
  await page.route("**/api/v1/**", (route: Route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/permanent-delete")) {
      return route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "project_management.permanent_delete_blocked",
            locale: AR,
            message: DELETION_PREVIEW.message,
            messages: { ar: DELETION_PREVIEW.message, en: "Permanent deletion is blocked." },
            context: { reason: "retention_policy_undefined" },
          },
        }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(BODIES.has(path) ? BODIES.get(path) : []),
    });
  });
}

test.describe("project management surface", () => {
  test.beforeEach(async ({ page }) => {
    await seedSession(page);
    await stubApi(page);
  });

  test("the project board answers, then stops saying it is loading", async ({ page }) => {
    const seen = watch(page);
    await page.goto(`/${AR}/portfolio/${PROJECT}/plan`);

    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    // **الحدّ هو الشاهد**: الردّ وصل، فلا يجوز أن تبقى الشاشة تقول «جارٍ».
    await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

    // «ما الذي يحتاج انتباهك الآن؟» — بالعمل لا بالرقم المجرَّد.
    await expect(page.getByText("ما الذي يحتاج انتباهك الآن؟")).toBeVisible();
    await expect(page.getByTestId("attention-overdue_tasks")).toBeVisible();

    expect(seen.errors).toEqual([]);
    expect(seen.serverErrors).toEqual([]);
  });

  test("no screen in this track ever shows a completion percentage", async ({ page }) => {
    // **العطبُ الذي يُحرَس هنا**: «٧٣٪ مكتمل» تُقرأ حكمًا على الورقة، ولم
    // يقع من ذلك شيء — عُدَّت بطاقاتٌ وقُسمت على بطاقات.
    for (const path of [
      `/${AR}/portfolio/${PROJECT}/plan`,
      `/${AR}/portfolio/${PROJECT}/tasks`,
      `/${AR}/portfolio/${PROJECT}/timeline`,
    ]) {
      await page.goto(path);
      await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });
      const body = (await page.locator("body").innerText()).replace(/\s+/g, " ");
      expect(body, `a percentage leaked onto ${path}`).not.toMatch(/\d+\s*%/);
      expect(body, `a readiness claim leaked onto ${path}`).not.toMatch(/جاهزية بحثية/);
    }
  });

  test("an unconfirmed stage is shown as unconfirmed, never as a platform verdict", async ({
    page,
  }) => {
    await page.goto(`/${AR}/portfolio/${PROJECT}/plan`);
    await expect(page.getByTestId("stage-unconfirmed")).toBeVisible();
    // والامتناع عن الاقتراح يُعرض بسببه، لا بشرطةٍ فارغة.
    await expect(page.getByTestId("suggestion-empty")).toContainText("لم يُعتمد بعد");
  });

  test("the task list shows the overdue badge and names every repeated control", async ({
    page,
  }) => {
    const seen = watch(page);
    await page.goto(`/${AR}/portfolio/${PROJECT}/tasks`);
    await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

    await expect(page.getByTestId("task-card")).toHaveCount(1);
    // **شارةٌ لا لون** — واللون وحده لا يبلغ قارئ الشاشة.
    await expect(page.getByTestId("task-overdue")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /^غيّر الحال completed: استخراج المتغيّرات/ }),
    ).toBeVisible();

    expect(seen.errors).toEqual([]);
    expect(seen.serverErrors).toEqual([]);
  });

  test("a suggestion is shown as a preview with its reason and needs an explicit accept", async ({
    page,
  }) => {
    await page.goto(`/${AR}/portfolio/${PROJECT}/tasks`);
    await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

    await expect(page.getByTestId("suggestion-card")).toHaveCount(1);
    await expect(page.getByText("لم يُنشأ منها شيء", { exact: false })).toBeVisible();
    // **السبب يشير إلى واقعة** — ولا اقتراحَ بلا سببه.
    await expect(page.getByText("لا مجموعة بياناتٍ مسجَّلة في هذا البحث.")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /^اقبل واجعلها مهمّة: سجّل مجموعة بيانات/ }),
    ).toBeVisible();
  });

  test("the timeline shows milestones and names a return to an earlier stage as a return", async ({
    page,
  }) => {
    const seen = watch(page);
    await page.goto(`/${AR}/portfolio/${PROJECT}/timeline`);
    await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

    await expect(page.getByTestId("milestone-row")).toHaveCount(2);
    await expect(page.getByTestId("stage-event")).toHaveCount(1);
    // **العودة إلى المنهجية بعد التحليل صوابٌ علميّ** — فتُسمّى عودة.
    await expect(page.getByTestId("returned-earlier")).toBeVisible();
    await expect(page.getByText("خالف الاقتراح")).toBeVisible();

    expect(seen.errors).toEqual([]);
    expect(seen.serverErrors).toEqual([]);
  });

  test("a project with no meaningful title is shown as untitled with its date apart", async ({
    page,
  }) => {
    await page.goto(`/${AR}/portfolio/trash`);
    await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

    await expect(page.getByTestId("trashed-project")).toHaveCount(1);
    await expect(page.getByText("مشروع بدون عنوان", { exact: true })).toBeVisible();
    await expect(page.getByTestId("untitled-note")).toBeVisible();
    // **ولا أثر للطابع الزمني في موضع العنوان.**
    const body = await page.locator("body").innerText();
    expect(body).not.toContain("قبول 2026-09-09T17:12");
    expect(body).not.toContain("17:12:41.883012");
  });

  test("permanent deletion previews its dependencies and then says it is blocked", async ({
    page,
  }) => {
    const seen = watch(page);
    await page.goto(`/${AR}/portfolio/trash`);
    await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

    // **الزرُّ يُطلب داخل بطاقته، لا في الصفحة كلّها.**
    //
    // وضوابطُ التلف تتكرّر بتكرار البحوث؛ فمُحدِّدٌ على مستوى الصفحة قد
    // يُصيب بطاقةً أخرى يوم تصير البطاقات اثنتين — ولا شيء يشتكي، لأنّ
    // زرًّا وُجد وضُغط. فالنطاقُ البطاقة، والاسمُ يحمل هدفه.
    const card = page
      .getByTestId("trashed-project")
      .filter({ hasText: "مشروع بدون عنوان" });
    await expect(card).toHaveCount(1);

    const preview = card.getByRole("button", {
      name: /^ماذا يُتلَف؟: مشروع بدون عنوان$/,
    });
    await expect(preview).toHaveCount(1);
    await preview.click();
    await expect(page.getByTestId("deletion-preview")).toBeVisible();
    // **بعشرة أعدادٍ باسمها، لا بـ«هل أنت متأكد؟».**
    await expect(page.getByTestId("deletion-preview").getByRole("listitem")).toHaveCount(10);
    await expect(page.getByText("حدثًا في سجلّ التدقيق يشير إلى هذا البحث: 44")).toBeVisible();

    const destroy = card.getByRole("button", {
      name: /^إتلاف دائم: مشروع بدون عنوان$/,
    });
    await expect(destroy).toHaveCount(1);
    await destroy.click();
    await expect(page.getByTestId("deletion-blocked")).toBeVisible();
    // والبحث ما زال معروضًا في السلّة — الوقف ليس إتلافًا مؤجَّلًا.
    await expect(page.getByTestId("trashed-project")).toHaveCount(1);

    expect(seen.errors).toEqual([]);
    expect(seen.serverErrors).toEqual([]);
  });
});
