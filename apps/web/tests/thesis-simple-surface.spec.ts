import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * السطحُ البسيط | The card says three things, and the idea says what it lacks.
 *
 * **ما كانت البطاقةُ تعرضه على من رفع رسالةً.**
 *
 * عددُ الأقسام، وعددُ الفرص، وأساسُ الحقوق، وتاريخُ المناقشة، و«جاهزة
 * لمراجعتك»، وزرُّ «راجِعْ ما استخرجه PUBRIVA» فعلًا رئيسًا. وهي مفرداتُ
 * نظامٍ يقرؤها الباحثُ من بنى النظام لا من سؤاله هو — وسؤالُه واحد:
 * **أيَّ الأوراق يمكن أن تُشتقّ من رسالتي؟**
 *
 * فصارت البطاقةُ تقول ثلاثًا لا أكثر: نحلّل الآن، أو وجدنا أفكارًا،
 * أو تعذّر التحليل. والتفاصيلُ باقيةٌ كاملةً تحت «تفاصيل الاستخراج»
 * لمن أرادها — **طُويت ولم تُحذف**.
 */

const AR = "ar";
const EN = "en";

async function seedSession(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem("athera_access_token", "simple-access");
    localStorage.setItem("athera_refresh_token", "simple-refresh");
  });
}

function json(route: Route, payload: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json",
                         body: JSON.stringify(payload) });
}

function card(id: string, opts: {
  running?: boolean; failed?: boolean; found?: number;
}) {
  const found = opts.found ?? 0;
  return {
    id, title: null, degree: null,
    source_filename: `${id}.pdf`, source_file_id: `f-${id}`,
    display_title: `${id}.pdf`, title_is_extracted: false,
    processing_state: opts.running ? "extracting" : "ready_for_review",
    processing_state_label: "…", processing_attempts: 1,
    failure_code: opts.failed ? "extract_failed" : null,
    failure_message: opts.failed ? "تعذّر" : null,
    can_retry: true, retry_blocked_reason: null,
    text_layer_state: "present", ocr_state: "not_needed", ocr_available: false,
    defended_on: null, data_collected_on: null, rights_basis: null, parsed_at: null,
    sections_extracted: 12, sections_outcome: "found", sections_outcome_label: "أقسام",
    results_extracted: 0,
    opportunities_found: found,
    opportunities_outcome: found > 0 ? "found" : "completed_empty",
    opportunities_outcome_label: "اكتمل الفحص",
    opportunities_are_candidates: true,
    archived_at: null,
    actions: {
      primary: null, is_running: opts.running ?? false,
      can_review: true, can_process: false, can_reprocess: true, can_parse: false,
      can_attach_file: false, can_mine: false, can_view_opportunities: found > 0,
      can_archive: true, can_restore: false, can_trash_file: true, is_archived: false,
      lifecycle_blocked_reason: null,
      mining_state: found > 0 ? "found" : "completed_empty",
      mining_reason: "…", parse_withdrawn_reason: "…", blocked_reason: null,
    },
  };
}

async function serveTheses(page: Page, rows: unknown[]) {
  await page.route("**/api/v1/**", (route) => {
    const p = new URL(route.request().url()).pathname;
    if (p.endsWith("/posture")) return json(route, { items: [] });
    if (p.endsWith("/theses")) return json(route, rows);
    return json(route, {});
  });
}

// ═══════════ ١ · ثلاثُ حالاتٍ لا أكثر ═══════════

test("البطاقةُ تقول ما يعني الباحثَ | the card says the three things that matter",
  async ({ page }) => {
    await seedSession(page);
    await serveTheses(page, [
      card("busy", { running: true }),
      card("ready", { found: 3 }),
      card("broken", { failed: true }),
    ]);
    await page.goto(`/${EN}/theses`);

    const busy = page.getByTestId("thesis-card-busy");
    await expect(busy.getByTestId("card-headline"))
      .toContainText("PUBRIVA is analyzing your thesis");

    const ready = page.getByTestId("thesis-card-ready");
    await expect(ready.getByTestId("card-headline")).toContainText("3 paper ideas");
    // **وفعلٌ رئيسٌ واحد يقود إلى الأفكار.**
    await expect(ready.getByTestId("card-view-paper-ideas")).toBeVisible();

    const broken = page.getByTestId("thesis-card-broken");
    await expect(broken.getByTestId("card-headline"))
      .toContainText("couldn't finish analyzing");
  });

test("ولا مفرداتِ نظامٍ في المسار السويّ | no system vocabulary on the normal path",
  async ({ page }) => {
    await seedSession(page);
    await serveTheses(page, [card("ready", { found: 2 })]);
    await page.goto(`/${EN}/theses`);

    const ready = page.getByTestId("thesis-card-ready");
    await expect(ready.getByTestId("card-headline")).toBeVisible();

    // **والتفاصيلُ مطويّة**: عددُ الأقسام وأساسُ الحقوق ومراجعةُ الاستخراج.
    await expect(ready.getByTestId("card-advanced")).toBeVisible();
    await expect(ready.getByTestId("card-review")).not.toBeVisible();

    // ولا «جاهزة لمراجعتك» فعلًا رئيسًا يُعرض على من رفع رسالة.
    const shown = await ready.innerText();
    expect(shown).not.toContain("Review what PUBRIVA extracted");
  });

test("والتفاصيلُ طُويت ولم تُحذف | the details are folded, never dropped",
  async ({ page }) => {
    await seedSession(page);
    await serveTheses(page, [card("ready", { found: 1 })]);
    await page.goto(`/${AR}/theses`);

    const ready = page.getByTestId("thesis-card-ready");
    await ready.getByTestId("card-advanced").locator("summary").click();
    // **كلُّ ما كان معروضًا باقٍ لمن أراده.**
    await expect(ready.getByTestId("card-review")).toBeVisible();
    await expect(ready.getByTestId("card-advanced")).toContainText("12");
  });
