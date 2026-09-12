import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * الذكاء البحثيّ في متصفّح | Research Intelligence, as the researcher reads it.
 *
 * **وثلاثةُ أشياء تُقاس هنا، وكلُّها أخطاءٌ وقعت في هذا المستودع من قبل:**
 *
 * ١ · **شاشةٌ ساقطة تُقرأ «لا شيء مطلوب».** الرحلةُ رايةٌ مستقلّة عن
 *   التقييم؛ فلو سقطت وعُرض مكانَها فراغٌ صامت لقرأ الباحثُ أنّ بحثَه لا
 *   ينقصه شيء. فيُقال السقوطُ بنصّه.
 *
 * ٢ · **منعٌ بلا سببٍ مكتوب.** وهو الطريقُ المسدود عينه الذي دُفع ثمنُه في
 *   رحلة الرسالة: زرٌّ مطفأٌ لا يقول لمَ. فكلُّ بوّابةٍ مغلقة تُعرض ومعها
 *   سببُها بالعربية لا برمزٍ إنجليزيّ.
 *
 * ٣ · **نسبةُ جاهزية.** لا تُعرض بأيّ صيغة — والقرارُ نفسُه متّخذٌ في
 *   الخادم وفي شاشة التقييم، ولا يُنقض من بابٍ ثالث.
 */

const AR = "ar";
const EN = "en";
const PROJECT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";

const brain = (locale: string) => `/${locale}/portfolio/${PROJECT}/brain`;

function json(route: Route, payload: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json",
                         body: JSON.stringify(payload) });
}

async function seedSession(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem("athera_access_token", "brain-v1");
    localStorage.setItem("athera_refresh_token", "brain-v1");
    localStorage.setItem("athera_token_expiry", String(Date.now() + 900_000));
  });
}

/**
 * قشرةُ التطبيق: الوضعُ والوارد — **وليسا تفصيلًا**.
 *
 * ردُّ `{}` عليهما يُسقط الشريطَ والقائمة فتنهار الشجرة، ويقرأ القارئُ
 * عطبَ التجهيزة عطبًا في الشاشة. والفخُّ مسجَّلٌ في `thesis-center-closure`.
 */
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

const EMPTY_ASSESSMENT = {
  project_id: PROJECT, title: "بحثٌ في أوّله",
  known: [], missing: [], needs_review: [], conflicts: [],
  methodological_alerts: [], read_notes: [],
  is_advisory_only: true, blocking_count: 0,
  advisory_note: "كلُّ ما يخرج من هذا المحرّك استشاريّ.",
  note: "لا تُعرض نسبةُ جاهزية.",
};

function journeyPayload(overrides: Record<string, unknown> = {}) {
  return {
    project_id: PROJECT, title: "بحثٌ في أوّله",
    context_fingerprint: "a".repeat(64),
    fingerprint_schema: "pubriva.brain.context.v1",
    first_seen_at: "2026-09-13T00:00:00Z", last_seen_at: "2026-09-13T00:00:00Z",
    recommended: {
      action_key: "define_research_question", category: "foundation",
      status: "recommended", title: "حدِّد سؤال البحث",
      reason: "لا سؤالَ بحثٍ مسجَّلٌ لهذا المشروع بعد، وعليه يُبنى ما بعده.",
      route: `/portfolio/${PROJECT}/thread`,
      blocking_reasons: [], requirements: [], evidence_refs: [],
    },
    actions: [
      {
        action_key: "define_research_question", category: "foundation",
        status: "recommended", title: "حدِّد سؤال البحث",
        reason: "لا سؤالَ بحثٍ مسجَّلٌ لهذا المشروع بعد، وعليه يُبنى ما بعده.",
        route: `/portfolio/${PROJECT}/thread`,
        blocking_reasons: [], requirements: [], evidence_refs: [],
      },
      {
        action_key: "link_sources", category: "evidence", status: "recommended",
        title: "اربط مصادر بالبحث",
        reason: "لا مصدرَ مربوطٌ بهذا البحث، ولا يُسنَد ادّعاءٌ بلا مصدر.",
        route: "/library",
        blocking_reasons: [], requirements: [], evidence_refs: [],
      },
    ],
    capabilities: [
      { key: "run_analysis", allowed: false, blocking_reasons: ["dataset_missing"] },
      { key: "record_finding", allowed: false, blocking_reasons: ["analysis_not_run"] },
      { key: "support_claim", allowed: true, blocking_reasons: [] },
      { key: "draft_results", allowed: false, blocking_reasons: ["no_findings_recorded"] },
    ],
    known_count: 0, missing_count: 9, needs_review_count: 0, conflict_count: 0,
    superseded_now: 0,
    limitations: "هذه قراءةٌ لما سُجِّل في هذا البحث داخل PUBRIVA وحدَه.",
    note: "لا تُعرض نسبةُ إنجاز.",
    ...overrides,
  };
}

async function serve(page: Page, opts: { journey?: unknown; journeyStatus?: number } = {}) {
  await page.route("**/api/v1/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (shell(route, path)) return;
    if (path.endsWith("/journey")) {
      return json(route, opts.journey ?? journeyPayload(), opts.journeyStatus ?? 200);
    }
    if (path.endsWith("/assessment")) return json(route, EMPTY_ASSESSMENT);
    if (path.endsWith("/brain/rules")) return json(route, []);
    if (path.includes("/suggested-actions")) return json(route, { actions: [] });
    return json(route, {});
  });
}

// ═══════════ أ · الخطوةُ التالية تُعرض، ومعها سببُها ═══════════

test("أ · الخطوةُ التالية ومعها لماذا | the next step arrives with its reason",
  async ({ page }) => {
    await seedSession(page);
    await serve(page);
    await page.goto(brain(AR));

    const panel = page.getByTestId("brain-journey");
    await expect(panel).toBeVisible();
    await expect(page.getByTestId("journey-next-title")).toHaveText("حدِّد سؤال البحث");

    // **والسببُ معروضٌ مع الفعل** — لا في حاشيةٍ ولا خلف نقرة.
    await expect(page.getByTestId("journey-next-why"))
      .toContainText("لا سؤالَ بحثٍ مسجَّلٌ لهذا المشروع بعد");

    // والرابطُ يحمل اللغة — فلا يخرج القارئُ من لغته بلا أن يطلب.
    await expect(page.getByTestId("journey-next-route"))
      .toHaveAttribute("href", `/${AR}/portfolio/${PROJECT}/thread`);
  });

test("أ′ · وبالإنجليزية يحمل الرابطُ لغتَها | the route follows the reader's locale",
  async ({ page }) => {
    await seedSession(page);
    await serve(page);
    await page.goto(brain(EN));

    await expect(page.getByTestId("journey-next-route"))
      .toHaveAttribute("href", `/${EN}/portfolio/${PROJECT}/thread`);
  });

// ═══════════ ب · المنعُ يُسمّى بلغة القارئ ═══════════

test("ب · كلُّ بوّابةٍ مغلقة تقول لمَ | every closed gate names its reason",
  async ({ page }) => {
    await seedSession(page);
    await serve(page);
    await page.goto(brain(AR));

    const gate = page.getByTestId("journey-gate-run_analysis");
    await expect(gate).toBeVisible();
    // **والسببُ بالعربية لا برمزٍ إنجليزيّ** — `dataset_missing` رمزُ آلة.
    await expect(gate).toContainText("لا مجموعةَ بيانات في هذا البحث");
    await expect(gate).not.toContainText("dataset_missing");

    // وما هو مسموحٌ لا يُعرض في «ما لا يمكن».
    await expect(page.getByTestId("journey-gate-support_claim")).toHaveCount(0);
  });

test("ب′ · ولا بوّابةَ مغلقة ⇒ يُقال ذلك صراحةً | an open project says so",
  async ({ page }) => {
    await seedSession(page);
    await serve(page, {
      journey: journeyPayload({
        capabilities: [{ key: "run_analysis", allowed: true, blocking_reasons: [] }],
      }),
    });
    await page.goto(brain(AR));

    await expect(page.getByTestId("journey-cannot-none")).toBeVisible();
  });

// ═══════════ ج · الشاشةُ الساقطة تُقال ولا تُقرأ فراغًا ═══════════

test("ج · رحلةٌ لم تصل تُقال، ولا تُقرأ «لا شيء مطلوب» | a failed read is named",
  async ({ page }) => {
    await seedSession(page);
    await serve(page, { journeyStatus: 500, journey: { detail: "nope" } });
    await page.goto(brain(AR));

    await expect(page.getByTestId("journey-failed")).toBeVisible();
    await expect(page.getByTestId("journey-failed"))
      .toContainText("تعذّر قراءة حال البحث الآن");

    // **ولا خطوةٌ تُعرض عن قراءةٍ لم تصل.**
    await expect(page.getByTestId("journey-next")).toHaveCount(0);
    // والتقييمُ حوله يبقى معروضًا — رايتان مستقلّتان لا واحدة.
    await expect(page.getByTestId("brain-failed")).toHaveCount(0);
  });

// ═══════════ د · ولا نسبةَ إنجاز، ولا بصمةٌ في وجه الباحث ═══════════

test("د · لا نسبةَ جاهزية ولا بصمةٌ معروضة | no percentage, no fingerprint on screen",
  async ({ page }) => {
    await seedSession(page);
    await serve(page);
    await page.goto(brain(AR));
    await expect(page.getByTestId("brain-journey")).toBeVisible();

    const body = await page.locator("body").innerText();
    for (const shape of ["%", "٪"]) {
      expect(body, `نسبةٌ ظهرت: ${shape}`).not.toContain(shape);
    }
    // **والبصمةُ أداةُ تشخيصٍ لا معلومةٌ بحثية** — لا تُعرض للباحث (§84).
    expect(body).not.toContain("a".repeat(16));
    expect(body).not.toContain("pubriva.brain.context.v1");
  });

test("هـ · وحدودُ القراءة تُقال بجانبها | the reading states its own limits",
  async ({ page }) => {
    await seedSession(page);
    await serve(page);
    await page.goto(brain(AR));

    await expect(page.getByTestId("journey-limits")).toContainText("PUBRIVA");
    // **ولا مفردةَ مركزِ رسائلَ على هذا السطح** — الحدُّ المشروع وحده.
    const body = (await page.locator("body").innerText()).toLowerCase();
    for (const word of ["thesis", "mining_state", "أثيرا"]) {
      expect(body, `مفردةٌ لا تخصّ هذا السطح: ${word}`).not.toContain(word);
    }
  });
