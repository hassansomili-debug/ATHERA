import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * مساراتُ النموذج في المتصفّح | Stage 6 — Layer A.
 *
 * **والمزوّدُ لا يُنادى هنا.** الجهازُ المحلّيّ بلا مزوّد، وتفعيلُ واحدٍ
 * لأجل فحصٍ إنفاقٌ لا برهان. فيُصطنع شيئان لا ثالث: إعلانُ الجاهزيّة
 * (`/settings/posture`) والقراءاتُ التي تُنصب بها الشاشة، ثمّ **جوابُ
 * الطلب**. وما بينهما — موضعُ النداء في المكوّن، و`apiFetch`، وسياسةُ
 * النيّة، والترويسةُ على السلك — حقيقيٌّ كلُّه.
 *
 * وأمّا أنّ التوليدَ الواحدَ لا ينادي المزوّدَ مرّتين فبرهانُه في الخادم
 * (الطبقة ب)، لا هنا: المتصفّحُ لا يرى المزوّد.
 */

const LOCALE = "ar";
const KEY = /^[A-Za-z0-9_-]{16,128}$/;

let seq = 0;

async function register(page: Page): Promise<void> {
  seq += 1;
  const email = `stage6ai-${Date.now()}-${seq}@fixtures.athera`;
  await page.goto(`/${LOCALE}/register`);
  await page.locator("#reg-name").fill("Stage Six Model");
  await page.locator("#reg-email").fill(email);
  await page.locator("#reg-password").fill("Stage6-Passw0rd!");
  await page.locator("form button[type=submit]").click();
  await page.waitForURL(new RegExp(`/${LOCALE}$`), { timeout: 60_000 });
}

const json = (status: number, body: unknown) => ({
  status, contentType: "application/json", body: JSON.stringify(body),
});

const failure = (status: number, code: string) => json(status, {
  error: { code, locale: "ar", message: "x", messages: { ar: "x", en: "x" } },
});

/** إعلانُ جاهزيّةٍ مصطنع — وهذا وحده ما يفتح البوّابة. */
async function declareModelReady(page: Page) {
  await page.route("**/api/v1/settings/posture", (route) => route.fulfill(json(200, {
    items: [
      { key: "model_provider", label: "provider", value: "openai", detail: "" },
      { key: "literature_registry", label: "lit", value: "online", detail: "" },
    ],
  })));
}

/**
 * يلتقط مفاتيح طلبٍ محميّ: الأوّلُ ٥٠٣ (غموضٌ يُبقي النيّة)، ثمّ نجاح.
 * والمفتاحُ يُسجَّل **بعد** إتمام الردّ، فلا يسبق الفحصُ الجوابَ.
 */
function twoAttempts(page: Page, glob: string, success: unknown) {
  const keys: string[] = [];
  let n = 0;
  return {
    keys,
    install: () => page.route(glob, async (route: Route) => {
      if (route.request().method() !== "POST") { await route.continue(); return; }
      n += 1;
      const key = route.request().headers()["idempotency-key"] ?? "";
      await route.fulfill(n === 1 ? failure(503, "server.error") : json(200, success));
      keys.push(key);
    }),
  };
}

test.describe("Stage 6 — model routes carry one key across a retry", () => {
  test("/ai/ask reuses its key on retry and mints a new one for a new question",
    async ({ page }) => {
      await register(page);
      await declareModelReady(page);
      // الجسمُ بعقدِ `AiAnswer` كاملًا — وجوابٌ ناقصٌ يُسقط البطاقةَ عند
      // العرض، فيبدو العطبُ في المفتاح وهو في الفحص.
      const ask = twoAttempts(page, "**/api/v1/ai/ask", {
        answer: "جوابٌ مقترَح", status: "ok", evidence_state: "none",
        capabilities_used: [], limitations: [], recommended_next_actions: [],
        attachment: null, intent: "ask", search_performed: false,
        references: [], provider_statuses: [], project: null,
      });
      await ask.install();

      await page.goto(`/${LOCALE}/ai`);
      const box = page.locator("textarea").first();
      await box.waitFor({ state: "visible", timeout: 30_000 });
      const send = page.locator("button.ai-send");
      // الزرُّ يُفتح بالسؤالِ لا بالجاهزيّة وحدَها — فيُكتب أوّلًا.
      await box.fill("ما أثر التدخل على النتيجة الأولية؟");
      await expect(send).toBeEnabled({ timeout: 30_000 });
      await send.click();
      await expect.poll(() => ask.keys.length, { timeout: 30_000 }).toBe(1);
      await send.click();
      await expect.poll(() => ask.keys.length, { timeout: 30_000 }).toBe(2);

      expect(ask.keys[0]).toMatch(KEY);
      expect(ask.keys[1], "إعادةُ السؤالِ نفسِه ولّدت مفتاحًا ثانيًا")
        .toBe(ask.keys[0]);

      // **سؤالٌ آخرُ نيّةٌ أخرى** — ولو في اللحظة نفسِها.
      await box.fill("وما حدودُ هذا الاستنتاج على عيّنةٍ أصغر؟");
      await send.click();
      await expect.poll(() => ask.keys.length, { timeout: 30_000 }).toBe(3);
      expect(ask.keys[2]).not.toBe(ask.keys[0]);
    });

  test("a manuscript section draft reuses its key on retry", async ({ page }) => {
    await register(page);
    await declareModelReady(page);
    const id = "9f1b0f3e-0000-4000-8000-000000000001";
    await page.route(`**/api/v1/manuscripts/${id}/overview`, (route) =>
      route.fulfill(json(200, {
        manuscript_id: id, title_ar: "مخطوطة", version_label: "v1",
        sections: [{ section_key: "methods", title_ar: "المنهج", enabled: true,
                     status: "not_started", claims: 0, grounded_claims: 0,
                     literature: "ready", purpose_ar: "" }],
        approved_sections: 0, enabled_sections: 1, pending_literature: [],
        issues: [], blocking: 0, note: "",
      })));
    await page.route(`**/api/v1/manuscripts/${id}/sections/methods/drafting-context`,
      (route) => route.fulfill(json(200, {
        manuscript_id: id, section_key: "methods", sufficient: true,
        evidence_count: 3, roles: {}, missing_roles: [], fingerprint: "f",
        consent_state: "granted", provider: "openai", model: "x", evidence: [],
        analysis_outputs: [], redacted_statistics: [], message: "", next_steps: [],
      })));
    await page.route(`**/api/v1/manuscripts/${id}/sections/methods`, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill(failure(404, "drafting.no_draft")); return;
      }
      await route.continue();
    });
    const draft = twoAttempts(page,
      `**/api/v1/manuscripts/${id}/sections/methods/draft`,
      { section_key: "methods", text_ar: "نصّ", review_status: "draft" });
    await draft.install();

    await page.goto(`/${LOCALE}/manuscripts/${id}/studio`);
    await page.getByRole("button", { name: /المنهج/ }).first().click();
    const button = page.getByRole("button", { name: /صياغة|صغ|مسودة/ }).last();
    await button.waitFor({ state: "visible", timeout: 30_000 });
    await button.click();
    await expect.poll(() => draft.keys.length, { timeout: 30_000 }).toBe(1);
    await expect(button).toBeEnabled({ timeout: 30_000 });
    await button.click();
    await expect.poll(() => draft.keys.length, { timeout: 30_000 }).toBe(2);

    expect(draft.keys[0]).toMatch(KEY);
    expect(draft.keys[1], "إعادةُ صياغةِ القسمِ نفسِه ولّدت مفتاحًا ثانيًا")
      .toBe(draft.keys[0]);
  });

  test("publication opportunities reuse their key on retry", async ({ page }) => {
    await register(page);
    await declareModelReady(page);
    const id = "9f1b0f3e-0000-4000-8000-000000000002";
    await page.route(`**/api/v1/projects/${id}/publication-context`, (route) =>
      route.fulfill(json(200, {
        project_id: id, sufficient: true, evidence_count: 6, missing_roles: [],
        consent_state: "granted", consent_stale: false, provider: "openai",
        fingerprint: "f", message: "", roles: {},
      })));
    const listing = {
      opportunities: [], generated_at: null, context_fingerprint: "f", stale: false,
    };
    const gen = { keys: [] as string[] };
    let n = 0;
    await page.route(`**/api/v1/projects/${id}/publication-opportunities`,
      async (route) => {
        if (route.request().method() !== "POST") {
          await route.fulfill(json(200, listing)); return;
        }
        n += 1;
        const key = route.request().headers()["idempotency-key"] ?? "";
        await route.fulfill(n === 1 ? failure(503, "server.error") : json(200, listing));
        gen.keys.push(key);
      });

    const generate = () => page.locator("button.primary-action").first();
    const open = async () => {
      await generate().waitFor({ state: "visible", timeout: 30_000 });
      await expect(generate()).toBeEnabled({ timeout: 30_000 });
    };

    await page.goto(`/${LOCALE}/portfolio/${id}/publication-opportunities`);
    await open();
    await generate().click();
    await expect.poll(() => gen.keys.length, { timeout: 30_000 }).toBe(1);

    // **والزرُّ باقٍ بعد الإخفاق** (المرحلة ٨): كان يختفي فيلتفّ هذا الفحصُ
    // بإعادة تحميل الصفحة. والإعادةُ الآن من الشاشة نفسِها، بالمفتاح نفسِه.
    await open();
    await generate().click();
    await expect.poll(() => gen.keys.length, { timeout: 30_000 }).toBe(2);

    expect(gen.keys[0]).toMatch(KEY);
    expect(gen.keys[1], "إعادةُ التوليدِ ولّدت مفتاحًا ثانيًا").toBe(gen.keys[0]);
  });

  test("the thesis golden thread reuses its key on retry", async ({ page }) => {
    await register(page);
    await declareModelReady(page);
    const thesis = "9f1b0f3e-0000-4000-8000-000000000003";
    const opp = "9f1b0f3e-0000-4000-8000-000000000004";
    await page.route(`**/api/v1/theses/${thesis}/journey`, (route) =>
      route.fulfill(json(200, {
        thesis_id: thesis, state: "opportunities_ready", blocking_reasons: [],
        current_blocking_reasons: [], can_build_paper: true, thread_ready: false,
        can_build_thread: true, opportunities: 1, states: ["proposed"],
      })));
    await page.route(`**/api/v1/theses/${thesis}/publication-map`, (route) =>
      route.fulfill(json(200, { opportunities: [{
        id: opp, working_title: "فرصةٌ للنشر", paper_kind_label: "أصيل",
        research_question_ar: "سؤال", readiness_outcome_label: null,
        salami_alert: false, provenance_count: 2, planning_status: "proposed",
        context_complete: true, missing_context: [],
      }] })));
    await page.route(`**/api/v1/theses/${thesis}/opportunities/${opp}/select`,
      (route) => route.fulfill(json(200, { id: opp, planning_status: "selected" })));
    await page.route(`**/api/v1/theses/${thesis}/opportunities/${opp}/build-paper`,
      (route) => route.fulfill(json(200, {
        project_id: "9f1b0f3e-0000-4000-8000-000000000005",
        outline_id: "9f1b0f3e-0000-4000-8000-000000000006",
        manuscript_id: "9f1b0f3e-0000-4000-8000-000000000007",
        thread_id: null, created: [], reused: [], pending: [], state: "ready",
      })));
    const thread = twoAttempts(page,
      `**/api/v1/theses/${thesis}/opportunities/${opp}/thread`, { elements: [] });
    await thread.install();

    await page.goto(`/${LOCALE}/theses/${thesis}/journey`);
    await page.getByTestId("journey-start-paper").first().click();
    const build = page.getByTestId("journey-build-thread").first();
    await build.waitFor({ state: "visible", timeout: 30_000 });
    await build.click();
    await expect.poll(() => thread.keys.length, { timeout: 30_000 }).toBe(1);
    await expect(build).toBeEnabled({ timeout: 30_000 });
    await build.click();
    await expect.poll(() => thread.keys.length, { timeout: 30_000 }).toBe(2);

    expect(thread.keys[0]).toMatch(KEY);
    expect(thread.keys[1], "إعادةُ بناءِ الخيطِ ولّدت مفتاحًا ثانيًا")
      .toBe(thread.keys[0]);
  });
});
