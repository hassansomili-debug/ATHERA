import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * **معرّفات القواعد ثوابتٌ لا سلاسل داخل الكائن.**
 *
 * ماسحُ الأسرار يقرأ حقلًا اسمه `key` تليه سلسلةٌ عالية العشوائية مفتاحَ
 * واجهةٍ محتملًا، فأسقط البناءَ على تجهيزةٍ لا سرَّ فيها: القيمة معرّفُ
 * قاعدةٍ من سجلّ القواعد، لا مفتاح.
 *
 * **والشرحُ نفسه لا يعيد النمط.** حارسٌ يعاقب على شرحٍ صادق يُعطَّل ثم لا
 * يحرس شيئًا — وقد وقع ذلك في هذا المستودع مرّتين.
 *
 * ولم يُضعَّف الماسح باستثناءٍ في إعداده — استثناءُ مسارٍ اليوم يخفي سرًّا
 * حقيقيًّا في الملفّ نفسه غدًا. فرُفع النمط بدل أن يُستثنى.
 */
const RULE_CAUSALITY = "RB-CAUSALITY-01";
const RULE_DESIGN = "RB-DESIGN-02";

/**
 * العقل البحثي والخيط الذهبي في متصفّح | The two new product surfaces.
 *
 * وطبقتها طبقة `product-surface`: بناءٌ محلّي، وشبكةٌ معترَضة، وبلا اعتماد
 * — فتعمل في كل PR. والأسئلة المطروحة هنا خمسة:
 *
 *   ١ هل سقط استثناء، أو ردّ أصلُنا بخمسمئة على شيءٍ طلبَته الصفحة؟
 *   ٢ هل انتهى «جارٍ التحميل…» بعد أن ردّ الخادم؟
 *   ٣ **هل تُقرأ الشاشة الساقطة «لا شيء يُذكر»؟** وهذا هو العيب الذي
 *     تحرسه هذه الرقعة أكثر من غيره: تقييمٌ لم يصل يُعرض خانات فارغة،
 *     فيقرؤه الباحث براءةً — **وبحثٌ فارغ ليس بحثًا سليمًا**.
 *   ٤ هل ظهرت نسبةُ جاهزية؟ ولا يجوز أن تظهر بأيّ صيغة.
 *   ٥ هل في الشاشة زرٌّ أو رابطٌ لا يبلغه التنقّل بلوحة المفاتيح، أو
 *     ضابطٌ متكرّر لا يسمّي هدفه؟
 */

const AR = "ar";
const PROJECT = "11111111-2222-3333-4444-555555555555";
const BRAIN = `/${AR}/portfolio/${PROJECT}/brain`;
const THREAD = `/${AR}/portfolio/${PROJECT}/thread`;

/** «جارٍ التحميل…» كما هي في `messages/ar.json` — `app.loading`. */
const LOADING_AR = "جارٍ التحميل…";

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
    if (sessionStorage.getItem("__seeded")) return;
    sessionStorage.setItem("__seeded", "1");
    localStorage.setItem("athera_access_token", "surface-access");
    localStorage.setItem("athera_refresh_token", "surface-refresh");
    localStorage.setItem("athera_token_expiry", String(Date.now() + 900_000));
  });
}

/**
 * تقييمٌ فيه سطرٌ من كل خانة — والقاعدة مذكورة بمعرّفها.
 *
 * وخانةٌ واحدة مملوءة كانت ستمرّ على شاشةٍ تعرض أوّل خانة فقط؛ فالخمس
 * مملوءة، ويُسأل عن الخمس.
 */
const ASSESSMENT = {
  project_id: PROJECT,
  title: "أثر برنامج تدريبي",
  known: [
    { key: "design_recorded", detail: "التصميم المسجَّل: quantitative.", rule_id: null,
      entity_ids: ["design:1"], excerpt: null },
  ],
  missing: [
    { key: "question", detail: "سؤال البحث: لا ذاكرة موثقة خلفه بعد.", rule_id: null,
      entity_ids: [], excerpt: null },
  ],
  needs_review: [
    { key: RULE_DESIGN, detail: "لم يمكن الحكم على ملاءمة الاختبار.",
      rule_id: RULE_DESIGN, entity_ids: ["analysis:7"], excerpt: null },
  ],
  conflicts: [
    { key: "contradictory_evidence", detail: "مصدران موثقان يقولان قولين.", rule_id: null,
      entity_ids: ["claim:2"], excerpt: null },
  ],
  methodological_alerts: [
    { key: RULE_CAUSALITY, detail: "لغةٌ سببية في دراسةٍ ارتباطية.",
      rule_id: RULE_CAUSALITY, entity_ids: ["claim:9"], excerpt: "أدّى البرنامج إلى" },
  ],
  read_notes: [
    { key: "temporal_frame_not_stored",
      detail: "الإطار الزمني غير مسجَّل في القاعدة، فلم يُقرأ ولم يُخمَّن.",
      rule_id: null, entity_ids: [], excerpt: null },
  ],
  is_advisory_only: true,
  blocking_count: 0,
  advisory_note: "كل ما في هذه الصفحة مشورةٌ تُقرأ ولا تُوقف عملًا.",
  note: "ولا تُعرض نسبة جاهزية.",
};

const RULES = [
  {
    id: "RB-CAUSALITY-01", category: "causality", severity: "blocking", status: "DRAFT",
    is_enforceable: false,
    condition: "يظهر تركيبٌ سببي في نصّ بحثٍ تصميمه ليس تجريبيًّا.",
    message: "التصميم الوصفي يصف اقترانًا ولا يثبت سببًا.",
    provenance: "§15.2 والكشف اللغوي التاسع.", related_issue_keys: [], version: 1,
  },
  {
    id: "RB-DESIGN-02", category: "design_fit", severity: "blocking", status: "DRAFT",
    is_enforceable: false,
    condition: "اختبارٌ إحصائي لا يلائم مقاييس متغيّراته.",
    message: "الاختبار غير الملائم يُخرج رقمًا لا معنى له.",
    provenance: "`TEST_KINDS` في مفردات التحليل.", related_issue_keys: [], version: 1,
  },
];

/** خيطٌ فيه الحالات الأربع كلها — فتُفحص أربعتها لا أفضلها. */
const THREAD_VIEW = {
  project_id: PROJECT,
  title: "أثر برنامج تدريبي",
  stages: [
    { key: "problem", label: "المشكلة", label_ar: "المشكلة", label_en: "Problem",
      nodes: [{ id: "e1", stage: "problem", label: "المشكلة المسجَّلة",
                origin: "thread_elements", detail: null }] },
    { key: "objective", label: "الأهداف", label_ar: "الأهداف", label_en: "Objectives",
      nodes: [{ id: "e2", stage: "objective", label: "قياس النية السلوكية",
                origin: "thread_elements", detail: null }] },
    { key: "question", label: "الأسئلة والفروض", label_ar: "الأسئلة والفروض",
      label_en: "Questions and hypotheses", nodes: [] },
    { key: "theory", label: "النظرية", label_ar: "النظرية", label_en: "Theory", nodes: [] },
    { key: "construct", label: "البُنى", label_ar: "البُنى", label_en: "Constructs",
      nodes: [{ id: "c1", stage: "construct", label: "الرضا", origin: "constructs",
                detail: null }] },
    { key: "method", label: "المنهج والأدوات", label_ar: "المنهج والأدوات",
      label_en: "Method and instruments", nodes: [] },
    { key: "analysis", label: "التحليل", label_ar: "التحليل", label_en: "Analysis", nodes: [] },
    { key: "finding", label: "النتائج", label_ar: "النتائج", label_en: "Findings",
      nodes: [{ id: "o1", stage: "finding", label: "مخرَج", origin: "analysis_outputs",
                detail: null }] },
    { key: "recommendation", label: "التوصيات", label_ar: "التوصيات",
      label_en: "Recommendations",
      nodes: [{ id: "r1", stage: "recommendation", label: "توصية", origin: "thread_elements",
                detail: null }] },
  ],
  connections: [
    { stage_from: "problem", stage_to: "objective", state: "known",
      detail: "رابطٌ مخزَّن بين العنصرين.", source_id: "e1", source_label: "المشكلة المسجَّلة",
      target_id: "e2", target_label: "قياس النية السلوكية", basis: "thread_links.addresses" },
    { stage_from: "question", stage_to: "construct", state: "missing",
      detail: "لا نظرية مسجَّلة على هذا السؤال.", source_id: null, source_label: null,
      target_id: "c1", target_label: "الرضا", basis: null },
    { stage_from: "construct", stage_to: "method", state: "conflicting",
      detail: "الأدوات المسجَّلة تقيس بُنًى أخرى.", source_id: "c1", source_label: "الرضا",
      target_id: null, target_label: null, basis: null },
    { stage_from: "finding", stage_to: "recommendation", state: "needs_review",
      detail: "لا مفتاح في المنصّة يربط توصيةً بمخرَج تحليل.", source_id: null,
      source_label: null, target_id: "r1", target_label: "توصية", basis: null },
  ],
  read_notes: [
    { key: "recommendation_to_output_not_stored",
      detail: "لا مفتاح في المنصّة يربط توصيةً بمخرَج تحليل." },
    { key: "question_to_construct_not_stored",
      detail: "لا مفتاح مباشر بين سؤالٍ وبناء." },
  ],
  counts: { known: 1, needs_review: 1, missing: 1, conflicting: 1 },
  note: "لا تُعرض درجة اتساق هنا.",
  // اسمُ البحث يصل من عقد العرض، ومعه رايةُ البديل وتاريخُ الإنشاء منفصلًا.
  title_is_fallback: false,
  created_at: "2026-03-01T09:00:00Z",
};

/**
 * فعلٌ مقترح على الكشف المنهجي — **ولا شيء فيه يُنشئ التزامًا**.
 *
 * و`finding_key` و`entity_ids` يطابقان سطر `methodological_alerts` في
 * التقييم: المطابقةُ بالمفتاح والمواضع معًا هي ما يمنع ضمَّ اقتراح متغيّرٍ
 * إلى سطر متغيّرٍ آخر.
 */
const ACTIONS = {
  project_id: PROJECT,
  actions: [
    {
      key: `methodological_alerts:${RULE_CAUSALITY}:claim:9`,
      finding_key: RULE_CAUSALITY,
      category: "methodological_alerts",
      state: "needs_review",
      action_kind: "review_causal_language",
      title: "راجع لغة السببية في نصّك، أو سجّل تصميمًا تجريبيًّا يسندها.",
      detail: "لغةٌ سببية في دراسةٍ ارتباطية.",
      rule_id: RULE_CAUSALITY,
      rule_status: "DRAFT",
      rule_is_enforceable: false,
      provenance: "§15.2 والكشف اللغوي التاسع.",
      excerpt: "أدّى البرنامج إلى",
      entity_ids: ["claim:9"],
      has_evidence: true,
      creates_obligation: false,
    },
  ],
  advisory_note: "كل ما في هذه الصفحة مشورةٌ تُقرأ ولا تُوقف عملًا.",
};

/** المعاينة: ما ستكون عليه المهمّة **لو** قَبِل الباحث. */
const PREVIEW = {
  action_key: `methodological_alerts:${RULE_CAUSALITY}:claim:9`,
  title: "راجع لغة السببية في نصّك، أو سجّل تصميمًا تجريبيًّا يسندها.",
  detail: "لغةٌ سببية في دراسةٍ ارتباطية.",
  source: `قاعدة ${RULE_CAUSALITY} — رتبتها: DRAFT — مصدرها: §15.2`,
  excerpt: "أدّى البرنامج إلى",
  entity_ids: ["claim:9"],
  undetermined_fields: [
    { key: "assignee", label: "المسؤول" },
    { key: "due_date", label: "تاريخ الاستحقاق" },
    { key: "priority", label: "الأولوية" },
  ],
  is_preview: true,
  created: false,
  not_created_note: "هذه معاينة: لم تُنشأ مهمّة، ولا شيء سُجّل في بحثك.",
  pending_contract_note: "عقد إنشاء المهام لم يصل بعد، فزرّ القبول غير مفعَّل.",
};

const BODIES = new Map<string, unknown>([
  [`/api/v1/workspace/projects/${PROJECT}/assessment`, ASSESSMENT],
  ["/api/v1/brain/rules", RULES],
  [`/api/v1/projects/${PROJECT}/thread/golden-view`, THREAD_VIEW],
  [`/api/v1/projects/${PROJECT}/brain/suggested-actions`, ACTIONS],
  [`/api/v1/projects/${PROJECT}/brain/suggested-actions/preview`, PREVIEW],
  [
    "/api/v1/settings/posture",
    { tenant_name: "فحص السطح", locale: AR, supported_locales: ["ar", "en"], roles: [],
      items: [] },
  ],
  [
    "/api/v1/inbox/summary",
    { pending_approvals: 0, open_alerts: 0, blocking_alerts: 0, unread_notifications: 0 },
  ],
]);

async function stubApi(page: Page, failing: string[] = []) {
  await page.route("**/api/v1/**", (route: Route) => {
    const path = new URL(route.request().url()).pathname;
    if (failing.some((needle) => path.includes(needle))) {
      return route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          code: "server.error", locale: AR, message: "عطبٌ في الخادم",
          messages: { ar: "عطبٌ في الخادم", en: "Server error" },
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

/**
 * الدعوى الممنوعة: **رقمٌ إلى جانب لفظ جاهزية أو درجة**.
 *
 * ولفظُ «جاهزية» وحده مسموح — بل مطلوب: الصفحة تقول «لا تُعرض نسبة
 * جاهزية»، ومنعُ اللفظ كان سيمنع النفي نفسه. فالممنوع اقترانُه برقم.
 *
 * و«٪» و«%» كلتاهما تُفحص: كتالوجٌ عربي قد يكتب الرمز العربي، وحارسٌ يفحص
 * الرمز اللاتيني وحده يمرّ عليه.
 */
const SCORE_WORD = "(?:جاهزي\\S*|درج[ةه]|readiness|score|ratio)";
/** والرقم عربيّ الأصل كان أو لاتينيّه: «٨٢» و«82» الدعوى نفسها. */
const DIGIT = "[0-9\\u0660-\\u0669]";
const SCORE_CLAIM = new RegExp(
  `${SCORE_WORD}[^\\n]{0,16}${DIGIT}|${DIGIT}[^\\n]{0,16}${SCORE_WORD}`,
  "i",
);
/** ونسبةٌ عارية ممنوعة ولو بلا لفظ: «٨٢٪» وحدها هي الدعوى. */
const BARE_PERCENTAGE = new RegExp(`${DIGIT}\\s*[%٪]`);

test.describe("the research brain and the golden thread", () => {
  test.beforeEach(async ({ page }) => {
    await seedSession(page);
  });

  for (const [name, path] of [["research brain", BRAIN], ["golden thread", THREAD]] as const) {
    test(`${name} renders, answers, and stops saying it is loading`, async ({ page }) => {
      const seen = watch(page);
      await stubApi(page);
      await page.goto(path);

      await expect(page).not.toHaveURL(/\/login/);
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
      await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

      expect(seen.errors, `JS exceptions on ${path}`).toEqual([]);
      expect(seen.serverErrors, `5xx from our own origin on ${path}`).toEqual([]);
    });

    test(`${name} shows no readiness score of any shape`, async ({ page }) => {
      await stubApi(page);
      await page.goto(path);
      await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

      const text = (await page.locator("body").first().innerText()).replace(/\u00a0/g, " ");
      expect(text, `a readiness claim on ${path}`).not.toMatch(SCORE_CLAIM);
      expect(text, `a bare percentage on ${path}`).not.toMatch(BARE_PERCENTAGE);
      // والنفي نفسه معروض: الباحث يقرأ لماذا لا رقم هنا، لا يستنتجه من صمت.
      expect(text, `the no-score note on ${path}`).toMatch(/لا تُعرض/);
    });

    test(`${name} keeps every control reachable by keyboard`, async ({ page }) => {
      await stubApi(page);
      await page.goto(path);
      await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

      const unreachable = await page.evaluate(() =>
        [...(document.querySelector("main") ?? document.body).querySelectorAll("button, a[href], summary")]
          .filter((node) => !(node as HTMLButtonElement).disabled)
          .filter((node) => !(node as HTMLElement).hidden)
          .filter((node) => (node as HTMLElement).tabIndex < 0)
          .map((node) => node.outerHTML.slice(0, 120)),
      );
      expect(unreachable, `controls removed from the tab order on ${path}`).toEqual([]);
    });

    test(`${name} gives every repeated control a name`, async ({ page }) => {
      await stubApi(page);
      await page.goto(path);
      await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

      const nameless = await page.evaluate(() =>
        [...(document.querySelector("main") ?? document.body).querySelectorAll("button, a[href], summary")]
          .filter((node) => {
            const element = node as HTMLElement;
            const label =
              (element.textContent ?? "").trim() ||
              element.getAttribute("aria-label") ||
              element.getAttribute("title") ||
              "";
            return label.length === 0;
          })
          .map((node) => node.outerHTML.slice(0, 120)),
      );
      expect(nameless, `icon-only controls on ${path}`).toEqual([]);
    });
  }

  test("a failed assessment is not rendered as nothing to report", async ({ page }) => {
    // **العيب الذي تحرسه هذه الرقعة.** تقييمٌ لم يصل يُعرض خانات فارغة،
    // فيقرؤه الباحث «لا شيء يُذكر» — وبحثٌ فارغ ليس بحثًا سليمًا.
    await stubApi(page, ["/assessment"]);
    await page.goto(BRAIN);

    await expect(page.getByTestId("brain-failed")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("brain-empty")).toHaveCount(0);
    await expect(page.getByTestId("brain-count-known")).toHaveCount(0);
    await expect(page.getByRole("alert").first()).toBeVisible();
  });

  test("a failed thread is not rendered as an empty thread", async ({ page }) => {
    await stubApi(page, ["/thread/golden-view"]);
    await page.goto(THREAD);

    await expect(page.getByTestId("thread-failed")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("thread-empty")).toHaveCount(0);
    await expect(page.getByTestId("stage-count-problem")).toHaveCount(0);
  });

  test("a lost rule registry is said, not silently dropped", async ({ page }) => {
    // التنبيه يصل بلا رتبةٍ فيُقرأ حكمًا معتمَدًا — فيُقال إنّ السجل لم يصل.
    await stubApi(page, ["/brain/rules"]);
    await page.goto(BRAIN);

    await expect(page.getByTestId("brain-rules-failed")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("brain-count-methodological_alerts")).toBeVisible();
  });

  test("a screen that has not answered yet says so, and says nothing else", async ({ page }) => {
    let release: () => void = () => {};
    const held = new Promise<void>((resolve) => {
      release = () => resolve();
    });
    await page.route("**/api/v1/**", async (route: Route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/assessment")) await held;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(BODIES.has(path) ? BODIES.get(path) : []),
      });
    });

    await page.goto(BRAIN);
    await expect(page.getByTestId("brain-loading")).toBeVisible();
    // لا حكمَ على بحثٍ لم يُقرأ بعد: لا «فارغ» ولا «سليم».
    await expect(page.getByTestId("brain-empty")).toHaveCount(0);
    await expect(page.getByTestId("brain-failed")).toHaveCount(0);

    release();
    await expect(page.getByTestId("brain-loading")).toHaveCount(0, { timeout: 20_000 });
    await expect(page.getByTestId("brain-count-known")).toBeVisible();
  });

  test("the alert carries what was detected, why it matters, and the rule's standing",
    async ({ page }) => {
      await stubApi(page);
      await page.goto(BRAIN);
      await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

      const alerts = page.locator("#brain-methodological_alerts").locator("..");
      await expect(alerts.getByText("لغةٌ سببية في دراسةٍ ارتباطية.").first()).toBeVisible();
      await expect(alerts.getByText("التصميم الوصفي يصف اقترانًا ولا يثبت سببًا.").first()).toBeVisible();
      await expect(alerts.getByText("RB-CAUSALITY-01", { exact: false }).first()).toBeVisible();
      await expect(alerts.getByText("مسوّدة — لم يراجعها مختصّ").first()).toBeVisible();
      await expect(alerts.getByText("لا توقف عملًا").first()).toBeVisible();
      await expect(page.getByTestId("brain-blocking")).toContainText("لا شيء");
    });

  test("the thread draws no line the data does not carry", async ({ page }) => {
    await stubApi(page);
    await page.goto(THREAD);
    await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

    // الوصلة المعلومة تسمّي صفّها، والفجوة تقول إنّ لا صفّ لها.
    await expect(page.getByText("thread_links.addresses").first()).toBeVisible();
    await expect(page.getByText("لا صفّ يشهد لهذه الوصلة، فلم يُرسم خط.").first()).toBeVisible();
    // الطرف الغائب يُسمّى غائبًا ولا يُملأ بأقرب عقدة.
    await expect(page.getByText("لا طرف مسجَّل").first()).toBeVisible();
    // والحالات الأربع كلها معروضة بأسمائها.
    for (const label of ["موصولة", "تحتاج مراجعة", "ناقصة", "متعارضة"]) {
      await expect(page.getByText(label).first()).toBeVisible();
    }
    // وما لا تسجّله المنصّة يُعلَن بجانب الرسم.
    await expect(page.getByText("لا مفتاح مباشر بين سؤالٍ وبناء.").first()).toBeVisible();
  });

  test("each screen opens the other, so neither is a dead end", async ({ page }) => {
    await stubApi(page);
    await page.goto(BRAIN);
    await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

    await page.getByRole("link", { name: "افتح الخيط الذهبي لهذا البحث" }).click();
    await expect(page).toHaveURL(new RegExp(`${PROJECT}/thread$`));
    await expect(page.getByRole("heading", { level: 1 })).toContainText("الخيط الذهبي");

    await page.getByRole("link", { name: "افتح العقل البحثي لهذا البحث" }).click();
    await expect(page).toHaveURL(new RegExp(`${PROJECT}/brain$`));
  });

  /**
   * **الخيط يقول أيَّ بحثٍ يعرض.**
   *
   * وشاشةٌ عنوانها «الخيط الذهبي» وحدها تُقرأ على أيّ بحث، والباحث الذي
   * فتح تبويبين لا يعرف أيّهما أمامه.
   */
  test("the thread names the project it is drawing", async ({ page }) => {
    await stubApi(page);
    await page.goto(THREAD);
    await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

    await expect(page.getByTestId("thread-project-title")).toContainText("أثر برنامج تدريبي");
    // وعنوانٌ حقيقي لا يُوسَم بديلًا.
    await expect(page.getByTestId("thread-title-fallback")).toHaveCount(0);
  });

  test("a nameless project is named a fallback, and says so", async ({ page }) => {
    await page.route("**/api/v1/**", (route: Route) => {
      const path = new URL(route.request().url()).pathname;
      const body = path.endsWith("/thread/golden-view")
        ? { ...THREAD_VIEW, title: "مشروع بدون عنوان", title_is_fallback: true }
        : BODIES.has(path)
          ? BODIES.get(path)
          : [];
      return route.fulfill({
        status: 200, contentType: "application/json", body: JSON.stringify(body),
      });
    });
    await page.goto(THREAD);
    await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

    await expect(page.getByTestId("thread-project-title")).toContainText("مشروع بدون عنوان");
    // **والبديل يُعلَن بديلًا**، وإلّا قُرئ عنوانًا سجّله الباحث بنفسه.
    await expect(page.getByTestId("thread-title-fallback")).toBeVisible();
  });

  /**
   * **الكشف لا يُنشئ التزامًا** — وهذا هو الفحص الذي يحرس السلسلة.
   *
   * والمعاينة تُفتح، وتقول بنصّها إنّ شيئًا لم يُنشأ، وزرُّ القبول معطَّل
   * لأنّ عقد المهامّ لم يصل. وزرٌّ يَعِد بما لا يقع أسوأ من غيابه: من ضغطه
   * مرّةً بلا أثرٍ لا يضغطه حين يعمل.
   */
  test("an advisory finding previews a task without creating one", async ({ page }) => {
    const seen = watch(page);
    const writes: string[] = [];
    await page.route("**/api/v1/**", (route: Route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      // **أيُّ كتابةٍ على مسار الاقتراحات دعوى.** وتُلتقط هنا لا تُفترض غائبة.
      if (request.method() !== "GET" && path.includes("suggested-actions")) {
        writes.push(`${request.method()} ${path}`);
      }
      return route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify(BODIES.has(path) ? BODIES.get(path) : []),
      });
    });
    await page.goto(BRAIN);
    await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

    // الفعل المقترح معروضٌ على الكشف قبل أيّ نقرة.
    await expect(
      page.getByText("راجع لغة السببية في نصّك، أو سجّل تصميمًا تجريبيًّا يسندها.").first(),
    ).toBeVisible();

    // ولا معاينة قبل أن يطلبها الباحث.
    await expect(page.getByTestId("brain-preview")).toHaveCount(0);

    await page.getByRole("button", { name: "عاين المهمّة المقترحة", exact: true }).click();
    const preview = page.getByTestId("brain-preview");
    await expect(preview).toBeVisible();

    // والسند ينتقل إلى المعاينة: مهمّةٌ بلا ما أثارها لا تُراجَع.
    await expect(preview).toContainText("أدّى البرنامج إلى");
    await expect(preview).toContainText(RULE_CAUSALITY);
    // وما لا يُعرف يُسمَّى ولا يُملأ باختراع.
    for (const label of ["المسؤول", "تاريخ الاستحقاق", "الأولوية"]) {
      await expect(preview.getByText(label, { exact: true }).first()).toBeVisible();
    }

    // **«لم تُنشأ مهمّة» يُقال بنصّه** لا يُستنتج من صمت.
    await expect(page.getByTestId("brain-preview-not-created")).toContainText(
      "لم تُنشأ مهمّة",
    );
    // وزرّ القبول معطَّل — ويبقى معطَّلًا لأنّ العقد لم يصل.
    await expect(page.getByTestId("brain-accept-disabled")).toBeDisabled();

    // ولا طلبَ كتابةٍ واحد خرج من الشاشة في هذه الرحلة كلها.
    expect(writes, "the preview wrote to the server").toEqual([]);
    expect(seen.serverErrors).toEqual([]);
    expect(seen.errors).toEqual([]);
  });

  /**
   * **سقوطُ الاقتراحات ليس «لا فعل مطلوب».**
   *
   * والتقييم قد يصل وهي تسقط، فتُعرض الكشوف بلا أفعالها — ويقرؤها الباحث
   * «لا شيء عليّ أن أفعله» عن جوابٍ لم يصل أصلًا.
   */
  test("failed suggestions are announced, not read as nothing to do", async ({ page }) => {
    await stubApi(page, ["suggested-actions"]);
    await page.goto(BRAIN);
    await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });

    // التقييم نفسه وصل، فالخانات معروضة.
    await expect(page.getByText("لغةٌ سببية في دراسةٍ ارتباطية.").first()).toBeVisible();
    // والاقتراحات سقطت، ويُقال ذلك بنصّه.
    await expect(page.getByTestId("brain-actions-failed").first()).toBeVisible();
  });
});
