import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * الميلُ الأخير | From a paper idea to a paper shell, in one click.
 *
 * **الطريقُ المسدود الذي تحرسه هذه الرقعة.**
 *
 * صار التنقيبُ يعمل في الإنتاج: رسالةٌ تُرفع، فتُقرأ، فتظهر فكرةُ ورقة.
 * ثمّ تقف الرحلةُ عند:
 *
 *     فرصُ النشر = تمّت
 *     → الحقوق والتأليف = أنت هنا
 *     → ابنِ هذه الورقة بالذكاء الاصطناعي = معطَّل
 *
 * وذاك حدٌّ في غير موضعه. `build_paper` لا تُنادي نموذجًا ولا تُرسل حرفًا:
 * تُنشئ مشروعًا وهيكلًا ومخطوطةً — صفوفًا حتميّة في قاعدتنا. فاشتراطُ
 * الحقوق وإذنِ الذكاء الاصطناعي عليها كان يمنع ما لا يمسّانه، ويعرض
 * للباحث زرًّا مطفأً بلا فعلٍ يُنقر.
 *
 * **والحدّان لم يسقطا، بل نُقلا**: الحقوقُ تلزم عند إعلان الجاهزية
 * للإرسال، والإذنُ عند أوّل نداءِ نموذج. وهذه الرقعةُ تقيس الأمرين معًا:
 * أنّ الهيكل يُبنى بنقرةٍ واحدة، وأنّ ما نُقل بقي حدًّا.
 */

const AR = "ar";
const EN = "en";
const THESIS = "mile-1";
const OPPORTUNITY = "op-1";
const MANUSCRIPT = "ms-1";

async function seedSession(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem("athera_access_token", "final-mile-access");
    localStorage.setItem("athera_refresh_token", "final-mile-refresh");
  });
}

function json(route: Route, status: number, payload: unknown) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  });
}

/** حالُ الرحلة كما يقولها الخادمُ بعد فصل بوّابة الهيكل عن بوّابات النشر. */
function journeyView(opts: {
  state: string;
  canBuild: boolean;
  blocking: string[];
  built?: boolean;
}) {
  return {
    thesis_id: THESIS,
    state: opts.state,
    // **والعددُ هو ما يفتح قراءةَ خريطة الأوراق** — بدونه لا تُطلب أصلًا.
    opportunities: 1,
    blocking_reasons: opts.blocking,
    can_build_paper: opts.canBuild,
    can_build_thread: false,
    thread_ready: false,
    project_exists: opts.built ?? false,
    outline_exists: opts.built ?? false,
    manuscript_exists: opts.built ?? false,
  };
}

function opportunity(planningStatus: string) {
  return {
    id: OPPORTUNITY,
    working_title: "فكرة ورقة مبدئية من نتيجةٍ مستخرَجة",
    opportunity_kind: "extension",
    paper_kind: "extension",
    planning_status: planningStatus,
    status: "discovered",
    evidence_readiness_score: null,
    salami_alert: false,
    overlap_unresolved: 0,
    contribution: null,
    provenance: "primary_findings",
  };
}

/**
 * خادمٌ متخيَّل يحكي العقدَ الجديد — **ويعدّ ما يُطلب منه**.
 *
 * ويُسجَّل كلُّ نداءٍ ليُبرهَن أنّ نقرةً واحدة كفت، وأنّ ما وقع هو
 * الاختيارُ ثمّ البناء — بلا مرورٍ بشاشة مراجعةِ الأدلّة.
 */
async function serve(page: Page, opts: {
  rightsPassed: boolean;
  consentGranted: boolean;
  calls: string[];
}) {
  let selected = false;
  let built = false;

  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    opts.calls.push(`${method} ${path}`);

    if (path.endsWith("/select") && method === "POST") {
      selected = true;
      return json(route, 200, opportunity("selected"));
    }
    if (path.endsWith("/build-paper") && method === "POST") {
      built = true;
      return json(route, 201, {
        project_id: "pr-1",
        outline_id: "ol-1",
        manuscript_id: MANUSCRIPT,
        created: ["project", "outline", "manuscript"],
        reused: [],
      });
    }
    if (path.endsWith("/journey")) {
      // **الحقوقُ والإذنُ يُذكران فيما يلزم لما هو أبعد، ولا يمنعان البناء.**
      const blocking: string[] = [];
      if (!selected) blocking.push("researcher_selection_required");
      if (!opts.rightsPassed) blocking.push("rights_gate_not_passed");
      if (!opts.consentGranted) blocking.push("ai_consent_required");
      return json(route, 200, journeyView({
        state: built
          ? "manuscript_created"
          : selected ? "opportunities_ready" : "researcher_decision_required",
        // بوّابةُ الهيكل: فرصةٌ قائمة وبلا تداخل — لا الحقوقُ ولا الإذن.
        canBuild: true,
        blocking,
        built,
      }));
    }
    if (path.endsWith("/publication-map")) {
      return json(route, 200, {
        opportunities: [opportunity(selected ? "selected" : "proposed")],
      });
    }
    if (path.endsWith("/posture")) return json(route, 200, { items: [] });
    if (path.includes("/theses/") && !path.includes("/opportunities")) {
      return json(route, 200, { id: THESIS, title_ar: "رسالة", title_en: "Thesis" });
    }
    return json(route, 200, {});
  });
}

// ═══════════ ١ · نقرةٌ واحدة تبني الورقة ═══════════

for (const locale of [AR, EN]) {
  test(`${locale} · نقرةٌ واحدة تبني هيكلَ الورقة | one click builds the paper shell`,
    async ({ page }) => {
      const calls: string[] = [];
      await seedSession(page);
      // **بلا حقوقٍ وبلا إذن** — وهما بالضبط ما كان يسدّ الطريق.
      await serve(page, { rightsPassed: false, consentGranted: false, calls });
      await page.goto(`/${locale}/theses/${THESIS}/journey`);

      const start = page.getByTestId("journey-start-paper");
      await expect(start).toBeVisible();
      // **ولا زرَّ معطّلًا**: الفعلُ الرئيسُ قابلٌ للنقر.
      await expect(start).toBeEnabled();

      await start.click();

      // الاختيارُ ثمّ البناء — نقرةٌ واحدة، وما كان يُطلب في ثلاث.
      await expect.poll(() => calls.filter((c) => c.endsWith("/build-paper")).length)
        .toBeGreaterThan(0);
      expect(calls.some((c) => c.endsWith("/select"))).toBe(true);

      // **ولم يُطلب المرورُ بمراجعة الأدلّة، ولا نداءُ قرارٍ لكلِّ حقل.**
      expect(calls.some((c) => c.includes("/decide"))).toBe(false);
      expect(calls.some((c) => c.includes("/review"))).toBe(false);
    });
}

// ═══════════ ٢ · وما نُقل بقي حدًّا ═══════════

test("الحقوقُ تُقال حيث تلزم، ومعها سببُها | rights are stated where they bind",
  async ({ page }) => {
    const calls: string[] = [];
    await seedSession(page);
    await serve(page, { rightsPassed: false, consentGranted: true, calls });
    await page.goto(`/${AR}/theses/${THESIS}/journey`);

    const note = page.getByTestId("journey-rights-required");
    await expect(note).toBeVisible();
    // **ومعها سببُها**: تمنع إعلانَ الجاهزية للإرسال، لا بناءَ الورقة.
    await expect(note).toContainText("الحقوق");
    // ولا تمنع الفعلَ الرئيس.
    await expect(page.getByTestId("journey-start-paper")).toBeEnabled();
  });

test("والحقوقُ لا تُعرض حين لا تلزم | no rights prompt once they pass",
  async ({ page }) => {
    const calls: string[] = [];
    await seedSession(page);
    await serve(page, { rightsPassed: true, consentGranted: true, calls });
    await page.goto(`/${AR}/theses/${THESIS}/journey`);

    await expect(page.getByTestId("journey-start-paper")).toBeVisible();
    await expect(page.getByTestId("journey-rights-required")).toHaveCount(0);
  });

// ═══════════ ٣ · ولا مفرداتِ نظامٍ في وجه الباحث ═══════════

test("لا مفرداتِ تنقيبٍ ولا مقاطعَ في شاشة الأوراق | no mining jargon on the paper surface",
  async ({ page }) => {
    const calls: string[] = [];
    await seedSession(page);
    await serve(page, { rightsPassed: false, consentGranted: false, calls });
    await page.goto(`/${EN}/theses/${THESIS}/journey`);

    await expect(page.getByTestId("journey-start-paper")).toBeVisible();
    const body = (await page.locator("body").innerText()).toLowerCase();
    for (const jargon of ["canonical", "fact candidate", "chunk", "read_keys",
                          "auto_eligible", "mining_state"]) {
      expect(body, `مفردةُ نظامٍ عُرضت: ${jargon}`).not.toContain(jargon);
    }
  });
