import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * رحلةُ البحث في متصفّح | The unified research journey, as a researcher meets it.
 *
 * **وخمسةُ أسئلةٍ هي المنتج**: أين أنت، وماذا أُنجز، وما الناقص، وما
 * التالي، ولماذا. فتُقاس هنا بأعيانها، ومعها أربعةُ حدودٍ دُفع ثمنُها
 * من قبل:
 *
 * ١ · **لا نسبةَ إنجاز** بأيّ صيغة — والبحثُ ليس له مقامٌ كونيّ.
 * ٢ · **المنعُ يُسمّى** ومعه ما يلزم — لا ضابطٌ مطفأٌ صامت.
 * ٣ · **السقوطُ ليس فراغًا** — شاشةٌ بلا خطوةٍ تُقرأ «لا شيء مطلوب».
 * ٤ · **ولا مفردةَ نظامٍ** في وجه الباحث.
 */

const AR = "ar";
const EN = "en";
const PROJECT = "11111111-aaaa-bbbb-cccc-222222222222";

const home = (locale: string) => `/${locale}/portfolio/${PROJECT}`;

function json(route: Route, payload: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json",
                         body: JSON.stringify(payload) });
}

async function seedSession(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem("athera_access_token", "rc0");
    localStorage.setItem("athera_refresh_token", "rc0");
    localStorage.setItem("athera_token_expiry", String(Date.now() + 900_000));
  });
}

/** قشرةُ التطبيق — وردُّ `{}` عليها يُسقط الشجرةَ فيُقرأ عطبُ التجهيزة عطبًا في الشاشة. */
function shell(route: Route, path: string): boolean {
  if (path === "/api/v1/settings/posture") {
    json(route, { tenant_name: "مركز", locale: "ar",
                  supported_locales: ["ar", "en"], roles: [], items: [] });
    return true;
  }
  if (path === "/api/v1/inbox/summary") {
    json(route, { pending_approvals: 0, open_alerts: 0, blocking_alerts: 0,
                  unread_notifications: 0 });
    return true;
  }
  return false;
}

const OVERVIEW = {
  project: { id: PROJECT, title_ar: "أثر التدريب في الأداء", status: "planned",
             current_gate: "G1", archived_at: null },
  brain: [], recommended_next: null, blockers: [],
  note: "لا تُعرض نسبةُ جاهزية.",
};

function stage(key: string, title: string, status: string, opts: {
  current?: boolean; reason?: string; summary?: string; blocking?: string[];
} = {}) {
  return {
    key, status, is_current: opts.current ?? false, title,
    reason: opts.reason ?? `سببُ حال ${title}.`,
    summary: opts.summary ?? "",
    route: `/portfolio/${PROJECT}/thread`,
    blocking_reasons: opts.blocking ?? [],
  };
}

/** بحثٌ في أوّله: الفكرةُ حاليّة، والدراساتُ متوقّفة، والأداةُ اختيارية. */
function journeyPayload(overrides: Record<string, unknown> = {}) {
  return {
    project_id: PROJECT, title: "أثر التدريب في الأداء",
    context_fingerprint: "e".repeat(64),
    fingerprint_schema: "pubriva.brain.context.v2",
    first_seen_at: "2026-09-13T00:00:00Z", last_seen_at: "2026-09-13T00:00:00Z",
    stages: [
      stage("idea", "الفكرة", "not_started", { current: true }),
      stage("references", "المراجع", "not_started"),
      stage("literature", "الدراسات السابقة", "blocked",
            { blocking: ["no_sources_linked"] }),
      stage("synthesis", "التركيب والفجوة", "blocked",
            { blocking: ["no_literature_read"] }),
      stage("design", "تصميم البحث", "blocked",
            { blocking: ["research_question_missing"] }),
      stage("instrument", "أداة الدراسة", "optional"),
      stage("data", "البيانات", "optional"),
      stage("analysis", "التحليل", "blocked", { blocking: ["no_data_available"] }),
      stage("paper", "الورقة", "not_started"),
    ],
    current_stage: "idea",
    known: [
      { key: "question", label: "سؤال البحث", value: "", known: false },
      { key: "method", label: "المنهج", value: "", known: false },
    ],
    missing: [
      { key: "idea", label: "الفكرة", severity: "recommended" },
      { key: "literature", label: "الدراسات السابقة", severity: "blocking" },
      { key: "instrument", label: "أداة الدراسة", severity: "optional" },
    ],
    recommended: {
      action_key: "define_research_question", category: "foundation",
      status: "recommended", title: "حدِّد سؤال البحث",
      reason: "لا سؤالَ بحثٍ مسجَّلٌ لهذا المشروع بعد، وعليه يُبنى ما بعده.",
      route: `/portfolio/${PROJECT}/thread`,
      blocking_reasons: [], requirements: [], evidence_refs: [],
    },
    actions: [], capabilities: [],
    known_count: 0, missing_count: 3, needs_review_count: 0, conflict_count: 0,
    limitations: "قراءةٌ لما سُجِّل داخل PUBRIVA وحدَه.",
    note: "لا تُعرض نسبةُ إنجاز.",
    ...overrides,
  };
}

async function serve(page: Page, opts: { journey?: unknown; status?: number } = {}) {
  await page.route("**/api/v1/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (shell(route, path)) return;
    if (path.endsWith("/journey")) {
      // **و`??` لا تصلح هنا**: `null` جوابٌ مقصودٌ نفحصه، و`null ?? x`
      // تُعيد `x` — فكانت الحالةُ «المشوَّه null» تُقدَّم لها حمولةٌ سليمة
      // ويمرّ الفحصُ بلا أن يفحص شيئًا.
      const body = "journey" in opts ? opts.journey : journeyPayload();
      return json(route, body, opts.status ?? 200);
    }
    if (path.endsWith("/overview")) return json(route, OVERVIEW);
    if (path.endsWith("/files") || path.endsWith("/sources")) return json(route, []);
    return json(route, []);
  });
}

// ═══════════ أ · الأسئلةُ الخمسة تُجاب ═══════════

test("أ · أين أنت، وماذا أُنجز، وما الناقص، وما التالي، ولماذا",
  async ({ page }) => {
    await seedSession(page);
    await serve(page);
    await page.goto(home(AR));

    await expect(page.getByTestId("research-journey")).toBeVisible();

    // أين أنت؟
    await expect(page.getByTestId("journey-current-stage")).toHaveText("الفكرة");
    // ماذا أُنجز؟ — ولا شيءَ بعد، ويُقال ذلك لا يُترك فراغًا.
    await expect(page.getByTestId("journey-done-none")).toBeVisible();
    // ما التالي؟
    await expect(page.getByTestId("journey-next-title")).toHaveText("حدِّد سؤال البحث");
    // لماذا؟
    await expect(page.getByTestId("journey-next-why"))
      .toContainText("لا سؤالَ بحثٍ مسجَّلٌ لهذا المشروع بعد");
    // ما الناقص؟ — بثلاث رتبٍ لا قائمةٍ واحدة.
    await expect(page.getByTestId("journey-missing-blocking")).toBeVisible();
    await expect(page.getByTestId("journey-missing-optional")).toBeVisible();
  });

test("أ′ · وفعلٌ رئيسٌ واحد يقصد وجهةً قائمة | one primary CTA, to a real route",
  async ({ page }) => {
    await seedSession(page);
    await serve(page);
    await page.goto(home(AR));

    const cta = page.getByTestId("journey-primary-cta");
    await expect(cta).toBeVisible();
    await expect(cta).toHaveAttribute("href", `/${AR}/portfolio/${PROJECT}/thread`);

    // **والوجهةُ تُفتح فعلًا** — لا رابطَ ميت (§59).
    await cta.click();
    await expect(page).toHaveURL(new RegExp(`/${AR}/portfolio/${PROJECT}/thread$`));
  });

// ═══════════ ب · المراحلُ التسع، والمنعُ يُسمّى ═══════════

test("ب · تسعُ مراحلَ وواحدةٌ حاليّة | nine stages, exactly one current",
  async ({ page }) => {
    await seedSession(page);
    await serve(page);
    await page.goto(home(AR));

    await expect(page.getByTestId("journey-stages").locator("> li")).toHaveCount(9);
    await expect(page.locator('[data-current="true"]')).toHaveCount(1);
    // **والحاليّةُ تُعلَن للقارئ الآليّ** لا باللون وحده (§105).
    await expect(page.getByTestId("stage-idea")).toHaveAttribute("aria-current", "step");
  });

test("ب′ · المرحلةُ المتوقّفة تقول لمَ وما يلزم | a blocked stage names its reason",
  async ({ page }) => {
    await seedSession(page);
    await serve(page);
    await page.goto(home(AR));

    const blocked = page.getByTestId("stage-blocked-literature");
    await expect(blocked).toBeVisible();
    await expect(blocked).toContainText("ما يلزم");
    // **والسببُ بالعربية لا برمزٍ إنجليزيّ.**
    await expect(blocked).toContainText("لا مصدرَ مربوطًا بهذا البحث");
    await expect(blocked).not.toContainText("no_sources_linked");
  });

test("ب″ · والمجهولُ يبقى مجهولًا | unknown stays unknown", async ({ page }) => {
  await seedSession(page);
  await serve(page);
  await page.goto(home(AR));

  await page.getByTestId("journey-known").locator("summary").click();
  await expect(page.getByTestId("known-method")).toContainText("غير مسجَّل");
});

// ═══════════ ج · لا نسبة، ولا مفردةَ نظام ═══════════

test("ج · لا نسبةَ إنجاز بأيّ صيغة | no completion percentage anywhere",
  async ({ page }) => {
    await seedSession(page);
    await serve(page);
    await page.goto(home(AR));
    await expect(page.getByTestId("research-journey")).toBeVisible();

    const body = await page.getByTestId("research-journey").innerText();
    for (const shape of ["%", "٪", "percent"]) {
      expect(body, `نسبةٌ ظهرت: ${shape}`).not.toContain(shape);
    }
  });

test("ج′ · ولا مفردةَ نظامٍ ولا علامةٍ قديمة | no internal or legacy vocabulary",
  async ({ page }) => {
    await seedSession(page);
    await serve(page);
    await page.goto(home(AR));
    await expect(page.getByTestId("research-journey")).toBeVisible();

    const body = (await page.getByTestId("research-journey").innerText()).toLowerCase();
    for (const leak of ["action_key", "fingerprint", "ontology", "capability",
                        "context snapshot", "not_started", "needs_action",
                        "أثيرا", "athera"]) {
      expect(body, `مفردةٌ داخلية ظهرت: ${leak}`).not.toContain(leak);
    }
  });

// ═══════════ د · السقوطُ ليس فراغًا ═══════════

test("د · رحلةٌ لم تصل تُقال ولا تُقرأ «لا شيء مطلوب» | a failed load is named",
  async ({ page }) => {
    await seedSession(page);
    await serve(page, { status: 500, journey: { detail: "nope" } });
    await page.goto(home(AR));

    await expect(page.getByTestId("journey-failed")).toBeVisible();
    await expect(page.getByTestId("journey-failed"))
      .toContainText("تعذّر تحميل رحلة البحث");
    await expect(page.getByTestId("research-journey")).toHaveCount(0);
  });

for (const [label, payload] of [
  ["null", null], ["array", []], ["empty object", {}],
  ["missing stages", { ...journeyPayload(), stages: undefined }],
] as const) {
  test(`د′ · جوابٌ مشوَّه (${label}) لا يُبيّض الشاشة | malformed payload never white-screens`,
    async ({ page }) => {
      const crashes: string[] = [];
      page.on("pageerror", (e) => crashes.push(String(e)));
      await seedSession(page);
      await serve(page, { journey: payload });
      await page.goto(home(AR));

      await expect(page.getByTestId("journey-failed")).toBeVisible();
      expect(crashes, `استثناءٌ سقط: ${crashes[0]}`).toHaveLength(0);
      // **والصفحةُ حولها تبقى قائمة** — رايةٌ مستقلّة لا انهيارٌ عامّ.
      await expect(page.locator("h1")).toBeVisible();
    });
}

// ═══════════ هـ · الجوّال والاتجاهان ═══════════

for (const locale of [AR, EN]) {
  test(`هـ · يُفهم على ٣٧٥px بلا تمريرٍ أفقيّ (${locale}) | mobile, no horizontal scroll`,
    async ({ page }) => {
      await page.setViewportSize({ width: 375, height: 720 });
      await seedSession(page);
      await serve(page);
      await page.goto(home(locale));
      await expect(page.getByTestId("research-journey")).toBeVisible();

      // **ويبقى المفهومُ كاملًا**: أين أنت، وما التالي، ولماذا.
      await expect(page.getByTestId("journey-current-stage")).toBeVisible();
      await expect(page.getByTestId("journey-next-title")).toBeVisible();
      await expect(page.getByTestId("journey-next-why")).toBeVisible();

      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow, "الصفحةُ تحتاج تمريرًا أفقيًّا").toBeLessThanOrEqual(1);
    });
}

test("هـ′ · والاتجاهُ يتبع اللغة | the document direction follows the locale",
  async ({ page }) => {
    await seedSession(page);
    await serve(page);

    await page.goto(home(AR));
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await page.goto(home(EN));
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  });

// ═══════════ و · الوصول بلوحة المفاتيح ═══════════

test("و · الرحلةُ تُبلَغ بلوحة المفاتيح | the journey is reachable by keyboard",
  async ({ page }) => {
    await seedSession(page);
    await serve(page);
    await page.goto(home(AR));
    await expect(page.getByTestId("journey-primary-cta")).toBeVisible();

    // كلُّ رابطِ مرحلةٍ يحمل نصًّا يُقرأ — لا أيقونةً صامتة (§105).
    const links = page.getByTestId("journey-stages").getByRole("link");
    const count = await links.count();
    expect(count).toBeGreaterThan(0);
    for (let i = 0; i < count; i += 1) {
      expect((await links.nth(i).innerText()).trim().length).toBeGreaterThan(0);
    }

    // والعنوانُ بنيويّ، والقائمةُ ملاحةٌ مسمّاة.
    await expect(page.getByRole("heading", { name: "رحلة البحث" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "مراحل البحث" })).toBeVisible();
  });

// ═══════════ ز · قائمةُ الأبحاث: فعلُ متابعةٍ واحد ═══════════

test("ز · بطاقةُ البحث لها فعلُ متابعةٍ واحدٌ واضح | one obvious continuation",
  async ({ page }) => {
    await seedSession(page);
    await page.route("**/api/v1/**", (route) => {
      const path = new URL(route.request().url()).pathname;
      if (shell(route, path)) return;
      if (path.endsWith("/projects")) {
        return json(route, [{ id: PROJECT, working_title: "أثر التدريب في الأداء",
                              current_gate: "G1", study_type: null,
                              target_journal_name: null }]);
      }
      return json(route, []);
    });
    await page.goto(`/${AR}/portfolio`);

    const cta = page.getByTestId(`project-continue-${PROJECT}`);
    await expect(cta).toHaveText("متابعة البحث");
    await expect(cta).toHaveAttribute("href", `/${AR}/portfolio/${PROJECT}`);
  });
