import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * الرحلةُ التلقائية | Extraction finishes, opportunities are simply there.
 *
 * **وما تفحصه هذه الرقعة هو غيابُ الخطوات، لا حضورُها.** الرحلةُ الموعودة:
 * تُقرأ الرسالة، ثمّ يجد الباحثُ فرصًا قائمة. فلا اعتمادَ حقيقةٍ واحدة،
 * ولا زرَّ تنقيبٍ يضغطه، ولا إعادةَ اختيارٍ لرسالته في شاشةٍ أخرى.
 *
 * والشبكةُ معترَضة والجلسةُ مزروعة — كطبقة `product-surface` — فتعمل في كلّ
 * PR بلا خادمٍ خلفي وبلا اعتماد. **وهي تفحص الشاشة على عقدٍ مُعطى**: أنّ
 * البطاقة تصف ما يقوله الخادم، وأنّ الرابط يحمل الرسالة بعينها.
 */

const AR = "ar";
const THESIS = "auto-1";
const OTHER = "auto-2";

async function seedSession(page: Page) {
  await page.addInitScript(() => {
    if (sessionStorage.getItem("__seeded")) return;
    sessionStorage.setItem("__seeded", "1");
    localStorage.setItem("athera_access_token", "auto-journey-access");
    localStorage.setItem("athera_refresh_token", "auto-journey-refresh");
    localStorage.setItem("athera_token_expiry", String(Date.now() + 900_000));
  });
}

function json(route: Route, status: number, payload: unknown) {
  return route.fulfill({
    status, contentType: "application/json", body: JSON.stringify(payload),
  });
}

/** بطاقةٌ بعد أن نقّبت الأتمتةُ فوجدت — الحالُ السويّة الجديدة. */
function card(id: string, filename: string, opportunities: number) {
  const found = opportunities > 0;
  return {
    id, title: null, degree: null,
    source_filename: filename, source_file_id: `file-${id}`,
    display_title: filename, title_is_extracted: false,
    processing_state: "ready_for_review",
    processing_state_label: "جاهزة لمراجعتك",
    processing_attempts: 1,
    failure_code: null, failure_message: null,
    can_retry: false, retry_blocked_reason: null,
    text_layer_state: "not_checked", ocr_state: "unavailable", ocr_available: false,
    defended_on: null, data_collected_on: null, rights_basis: null, parsed_at: null,
    sections_extracted: 0, sections_outcome: "not_started",
    sections_outcome_label: "لم يبدأ التحليل بعد",
    results_extracted: 0,
    opportunities_found: opportunities,
    opportunities_outcome: found ? "found" : "not_started",
    opportunities_outcome_label: found ? "فرص مرشَّحة" : "لم يبدأ استخراج الفرص بعد",
    opportunities_are_candidates: true,
    archived_at: null,
    actions: {
      primary: found ? "view_opportunities" : "review",
      is_running: false,
      can_review: true,
      can_process: false, can_reprocess: false, can_parse: false,
      can_attach_file: false,
      // **لا زرَّ تنقيبٍ يدويّ**: الأتمتةُ تملكه.
      can_mine: false,
      can_view_opportunities: found,
      can_archive: true, can_restore: false, can_trash_file: true,
      is_archived: false, lifecycle_blocked_reason: null,
      mining_state: found ? "found" : "no_evidence",
      mining_reason: found
        ? "فرصُ نشرٍ مبدئيّة مشتقّة من عناصر رسالتك وحدها — قبل مقابلتها "
          + "بالأدب المنشور، وقبل أيّ حكمٍ على جِدّتها أو ترتيبها."
        // **ونصُّ الخادم كما هو** — لا صياغةٌ مخترَعة تشبهه.
        : "لم يجرِ فحصُ الفرص بعد: لا دليلَ مؤهَّل على هذه الرسالة حتى الآن. "
          + "والفحصُ يبدأ تلقائيًّا بعد قراءة الرسالة، ولا يلزمك تشغيلُه.",
      parse_withdrawn_reason: "المسارُ القديم مسحوبٌ من البطاقة.",
      blocked_reason: null,
    },
  };
}

async function serve(page: Page, opportunities: number) {
  await page.route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;

    if (path === "/api/v1/theses" && route.request().method() === "GET") {
      return json(route, 200, [
        card(THESIS, "الرسالة الأولى.pdf", opportunities),
        card(OTHER, "الرسالة الثانية.pdf", 0),
      ]);
    }
    if (path.endsWith("/publication-map")) {
      // **الشكلُ هو العقد.** `PublicationMapResponse.overlap` كائنٌ لا
      // قائمة (`OverlapMatrixResponse` — `schemas/thesis.py:371,320`)،
      // والخادمُ يبنيه دائمًا. وردٌّ مُلفَّق يخالف العقدَ ليس اختبارًا
      // للمنتج: هو عطبٌ يُنسب إلى المنتج ظلمًا.
      return json(route, 200, {
        thesis_id: THESIS,
        title: "الرسالة الأولى.pdf",
        opportunities: [],
        overlap: { thesis_id: THESIS, pairs: [], alerts: 0, note_ar: "", note_en: "" },
        gate_summary: {},
      });
    }
    if (path === "/api/v1/settings/posture") {
      return json(route, 200, {
        tenant_name: "الرحلة", locale: AR, supported_locales: ["ar", "en"],
        roles: [], items: [],
      });
    }
    if (path === "/api/v1/inbox/summary") {
      return json(route, 200, {
        pending_approvals: 0, open_alerts: 0, blocking_alerts: 0,
        unread_notifications: 0,
      });
    }
    return json(route, 200, []);
  });
}

/**
 * ما يقوله الفحصُ حين يسقط — **لا مهلةٌ صامتة**.
 *
 * وسقطت هذه الرقعةُ مرّةً بأنّ عنصرًا ظهر ثمّ اختفى في أجزاء من الثانية:
 * ‏`toBeVisible` نجحت و`toHaveValue` لم تجد شيئًا. والسجلُّ يقول «لم يوجد»
 * ولا يقول **لماذا** — أهو تنقّلٌ إلى الدخول، أم انكسارُ تصيير، أم إخفاءُ
 * حارسِ الجلسة. فتُلتقط الشواهدُ الثلاثة ويُطبع أيّها وقع.
 */
interface Watch {
  console: string[];
  errors: string[];
  urls: string[];
}

function watch(page: Page): Watch {
  const w: Watch = { console: [], errors: [], urls: [] };
  page.on("console", (m) => {
    if (m.type() === "error") w.console.push(m.text().slice(0, 200));
  });
  page.on("pageerror", (e) => w.errors.push(String(e).slice(0, 200)));
  page.on("framenavigated", (frame) => {
    if (frame === page.mainFrame()) w.urls.push(frame.url());
  });
  return w;
}

async function report(page: Page, w: Watch, stage: string) {
  console.log(`\n── ${stage} ──`);
  console.log("   final url    :", page.url());
  console.log("   navigations  :", w.urls.join(" -> ") || "none");
  console.log("   selects in dom:", await page.locator("select").count());
  console.log("   picker in dom :", await page.getByTestId("thesis-picker").count());
  console.log("   page errors  :", w.errors.join(" | ") || "none");
  console.log("   console errs :", w.console.slice(-4).join(" | ") || "none");
}

test.beforeEach(async ({ page }) => {
  await seedSession(page);
});

test("a mined thesis offers its opportunities, and never a mining button", async ({ page }) => {
  await serve(page, 3);
  await page.goto(`/${AR}/theses`);

  const target = page.getByTestId(`thesis-card-${THESIS}`);
  await expect(target).toBeVisible();

  // **العددُ واقعةٌ محفوظة** — لا وعدٌ ولا زرٌّ يَعِد به.
  await expect(target).toContainText("3");

  // **ولا زرَّ تنقيبٍ يدويّ في الحال السويّة.**
  await expect(target.getByTestId("card-mine")).toHaveCount(0);

  // **والتحفّظُ في متن العبارة**: مبدئيّة، وقبل أيّ مقابلةٍ أو حكمِ جِدّة.
  const note = target.getByTestId("card-mining-note");
  await expect(note).toBeVisible();
  await expect(note).toContainText("مبدئيّة");
  await expect(note).toContainText("قبل");
});

test("the card opens this thesis, with no reselection", async ({ page }) => {
  await serve(page, 3);
  await page.goto(`/${AR}/theses`);

  // **والوجهةُ صارت شاشةَ أفكار الأوراق** (تبسيطُ السطح): هناك العنوانُ
  // والتسويغُ واكتمالُ السياق و«ابدأ هذه الورقة» — لا خريطةُ نشرٍ عامّة.
  const open = page.getByTestId(`thesis-card-${THESIS}`)
    .getByTestId("card-view-paper-ideas");
  await expect(open).toBeVisible();
  // **الرابطُ يحمل الرسالة بعينها** — لا شاشةٌ تُعيد السؤال.
  await expect(open).toHaveAttribute("href", `/${AR}/theses/${THESIS}/journey`);

  await open.click();
  await expect(page).toHaveURL(new RegExp(`/${AR}/theses/${THESIS}/journey$`));

  // **والشاشةُ مقصورةٌ على تلك الرسالة، فلا سؤالَ يُعاد أصلًا.**
  // وكانت تفتح خريطةَ نشرٍ عامّة ومعها منتقي رسائل يُضبط على المعرّف؛
  // والمنتقي نفسُه دليلُ أنّ الشاشةَ تحتمل غيرَها. وهذه لا تحتمل.
  await expect(page.getByTestId("thesis-picker")).toHaveCount(0);
  await expect(page.getByTestId("thesis-journey")).toBeVisible();
});

test("a thesis the researcher does not own is never preselected", async ({ page }) => {
  const w = watch(page);
  await serve(page, 3);

  // **ومعامل الرابط ليس إذنًا.** معرّفٌ ليس في قائمة صاحب الجلسة يسقط إلى
  // الأولى بلا خطأ — ولا يكشف وجودَ رسالةٍ ولا غيابَها.
  //
  // **والزيارةُ المباشرة هي المقصودة**: هكذا يصل رابطٌ يُلصَق أو يُشارَك.
  await page.goto(`/${AR}/opportunities?thesis_id=00000000-0000-0000-0000-000000000000`);

  // ولا يُقاس شيءٌ قبل أن تستقرّ الشاشة: `networkidle` تنتظر ما بعد الترطيب
  // من طلباتٍ وتنقّلاتِ حارسِ الجلسة، فلا يُقرأ عنصرٌ في طريقه إلى الزوال.
  await page.waitForLoadState("networkidle");

  const picker = page.getByTestId("thesis-picker");
  const settled = await picker.waitFor({ state: "visible", timeout: 15_000 })
    .then(() => true, () => false);
  if (!settled) await report(page, w, "unowned-id/no-picker");
  expect(settled, "قائمةُ اختيار الرسالة لم تستقرّ على الشاشة").toBe(true);

  // **ولا يُختار ما لا يملكه**: يسقط إلى أولى قائمته هو.
  await expect(picker).toHaveValue(THESIS);
  // ولا يُكشف شيءٌ عن المعرّف المطلوب — لا في الصفحة ولا في رسالة خطأ.
  await expect(page.locator("body")).not.toContainText("00000000-0000-0000-0000-000000000000");
});

test("a thesis with nothing mined shows no opportunity link", async ({ page }) => {
  await serve(page, 0);
  await page.goto(`/${AR}/theses`);

  const target = page.getByTestId(`thesis-card-${THESIS}`);
  await expect(target).toBeVisible();
  await expect(target.getByTestId("card-view-paper-ideas")).toHaveCount(0);
  // ولا زرَّ تنقيبٍ أيضًا: الأتمتةُ تملكه، ولم تجد بعد.
  await expect(target.getByTestId("card-mine")).toHaveCount(0);
});
