import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * التوليدُ الساقطُ يُعاد من الشاشة نفسِها | Stage 8 — planning retry UX.
 *
 * **وكان الزرُّ يختفي.** إخفاقُ التوليد وإخفاقُ التحميل كانا حالًا واحدة
 * (`failed`)، وقسمُ التوليد لا يُعرض إلّا لـ`ready|generating` — فمزوّدٌ تعثّر
 * مرّةً يترك الباحثَ أمام جملة خطأٍ بلا فعل، ولا سبيلَ إلّا إعادةُ تحميل
 * الصفحة. وفحصُ المرحلة ٦ نفسُه كان يلتفّ على ذلك بـ`page.reload()`.
 *
 * والمقاييسُ هنا: الخطأُ ظاهر، والزرُّ باقٍ، والإعادةُ **بالمفتاح نفسِه**
 * بلا إعادة تحميل، والنجاحُ يحسم النيّة فتأخذ النيّةُ التاليةُ مفتاحًا جديدًا.
 *
 * والطبقة A كما في المرحلة ٦: الجاهزيّةُ والسياقُ والجوابُ النهائيُّ مصطنعة،
 * **والطلبُ نفسُه يخرج من `apiFetch` في المكوّن الحقيقيّ**.
 */

const KEY = /^[A-Za-z0-9_-]{16,128}$/;
const PROJECT = "9f1b0f3e-0000-4000-8000-0000000000a8";
const OPPORTUNITY = "9f1b0f3e-0000-4000-8000-0000000000b8";

let seq = 0;

async function register(page: Page, locale = "ar"): Promise<void> {
  seq += 1;
  const email = `stage8-${Date.now()}-${seq}@fixtures.athera`;
  await page.goto(`/${locale}/register`);
  await page.locator("#reg-name").fill("Stage Eight");
  await page.locator("#reg-email").fill(email);
  await page.locator("#reg-password").fill("Stage8-Passw0rd!");
  await page.locator("form button[type=submit]").click();
  await page.waitForURL(new RegExp(`/${locale}$`), { timeout: 60_000 });
}

const json = (status: number, body: unknown) => ({
  status, contentType: "application/json", body: JSON.stringify(body),
});
const failure = (status: number, code: string, ar = "تعذّر", en = "Failed") => json(status, {
  error: { code, locale: "ar", message: ar, messages: { ar, en } },
});

async function declareModelReady(page: Page) {
  await page.route("**/api/v1/settings/posture", (route) => route.fulfill(json(200, {
    items: [
      { key: "model_provider", label: "provider", value: "openai", detail: "" },
      { key: "literature_registry", label: "lit", value: "online", detail: "" },
    ],
  })));
}

interface ContextShape { sufficient: boolean; consent_state: string }

/** السياقُ يُقرأ من دالّةٍ حيّة — فيتغيّر بعد الإخفاق إن شاء الفحص. */
async function serveContext(page: Page, current: () => ContextShape) {
  await page.route(`**/api/v1/projects/${PROJECT}/publication-context`, (route) =>
    route.fulfill(json(200, {
      project_id: PROJECT, evidence_count: 6, missing_roles: [], consent_stale: false,
      provider: "openai", fingerprint: "f", message: "", roles: {}, ...current(),
    })));
}

const opportunity = (status: "proposed" | "selected") => ({
  id: OPPORTUNITY, working_title_ar: "أثر التعلّم النشط", working_title_en: null,
  research_question_ar: "ما الأثر؟", opportunity_kind: "independent_question",
  paper_kind: "extraction", status: "candidate", planning_status: status,
  evidence_readiness_score: 60, literature_validation_status: "pending",
  journal_validation_status: "pending", salami_alert: false,
  proposed_contribution_ar: null, claim_boundaries_ar: null, limitations_ar: null,
  missing_requirements: [], evidence_count: 3, proposal_notice: "اقتراح",
});

const listing = (items: unknown[]) => ({
  project_id: PROJECT, opportunities: items, generated_at: null,
  context_fingerprint: "f", stale: false,
});

/** طلباتُ التوليد: كلُّ مفتاحٍ يُسجَّل بعد إتمام الردّ، بترتيبٍ يحدّده الفحص. */
function generation(page: Page, answers: Array<(r: Route) => Promise<void>>) {
  const keys: string[] = [];
  let n = 0;
  return {
    keys,
    install: (initial: unknown[]) => page.route(
      `**/api/v1/projects/${PROJECT}/publication-opportunities`, async (route) => {
        if (route.request().method() !== "POST") {
          await route.fulfill(json(200, listing(initial))); return;
        }
        const key = route.request().headers()["idempotency-key"] ?? "";
        const answer = answers[Math.min(n, answers.length - 1)];
        n += 1;
        await answer(route);
        keys.push(key);
      }),
  };
}

const cta = (page: Page) => page.getByTestId("planning-generate");

/**
 * خطأُ الصفحة نفسِها — **لا `getByRole("alert")`**: Next.js يحقن مُعلِنَ
 * مساراتٍ بالدور نفسِه (`#__next-route-announcer__`)، فيصير «لا تنبيه»
 * كذبًا دائمًا و«التنبيه يقول كذا» غامضًا بين عنصرين.
 */
const pageError = (page: Page) => page.locator("p.error-text[role=alert]");

async function openPlanning(page: Page, locale = "ar") {
  await page.goto(`/${locale}/portfolio/${PROJECT}/publication-opportunities`);
}

test.describe("Stage 8 — a failed generation keeps its retry, and its key", () => {
  test("503 → error + Retry → same key without reload → success → a new deliberate key",
    async ({ page }) => {
      await register(page);
      await declareModelReady(page);
      await serveContext(page, () => ({ sufficient: true, consent_state: "granted" }));
      const gen = generation(page, [
        (r) => r.fulfill(failure(503, "server.error", "تعذّر الوصول إلى المزوّد")),
        (r) => r.fulfill(json(200, listing([opportunity("proposed")]))),
        (r) => r.fulfill(json(200, listing([opportunity("proposed")]))),
      ]);
      await gen.install([]);
      await openPlanning(page);

      await expect(cta(page)).toHaveText("ابنِ فرص النشر", { timeout: 30_000 });
      await cta(page).click();
      await expect.poll(() => gen.keys.length, { timeout: 30_000 }).toBe(1);

      // ══ الخطأُ ظاهرٌ **والزرُّ باقٍ** — وكان يختفي ══
      await expect(pageError(page)).toContainText("تعذّر الوصول إلى المزوّد");
      await expect(cta(page)).toBeVisible();
      await expect(cta(page)).toHaveText("أعد محاولة التوليد");
      await expect(cta(page)).toBeEnabled();

      // ══ الإعادةُ بلا إعادة تحميل — **بالمفتاح نفسِه** ══
      const before = page.url();
      await cta(page).click();
      await expect.poll(() => gen.keys.length, { timeout: 30_000 }).toBe(2);
      expect(page.url(), "أُعيد تحميلُ الصفحة").toBe(before);
      expect(gen.keys[0]).toMatch(KEY);
      expect(gen.keys[1], "الإعادةُ بعد ٥٠٣ ولّدت مفتاحًا جديدًا").toBe(gen.keys[0]);

      // ══ والنجاحُ يحسم: الشاشةُ «جاهزة»، والخطأُ ذهب ══
      await expect(cta(page)).toHaveText("أعِد البناء", { timeout: 30_000 });
      await expect(pageError(page)).toHaveCount(0);

      // ══ والبناءُ المقصودُ بعد النجاح نيّةٌ جديدة ══
      await cta(page).click();
      await expect.poll(() => gen.keys.length, { timeout: 30_000 }).toBe(3);
      expect(gen.keys[2]).toMatch(KEY);
      expect(gen.keys[2], "بناءٌ مقصودٌ بعد النجاح حمل المفتاحَ المحسوم").not.toBe(gen.keys[0]);
    });

  test("a stale consent returns the page to the consent screen, not to a dead Retry",
    async ({ page }) => {
      await register(page);
      await declareModelReady(page);
      let consent = "granted";
      await serveContext(page, () => ({ sufficient: true, consent_state: consent }));
      const gen = generation(page, [async (r) => {
        consent = "absent";           // الإذنُ صار بائتًا عند الخادم
        await r.fulfill(failure(403, "planning.consent_required", "لم تأذن بعد"));
      }]);
      await gen.install([]);
      await openPlanning(page);

      await cta(page).click();
      await expect.poll(() => gen.keys.length, { timeout: 30_000 }).toBe(1);
      await expect(pageError(page)).toContainText("لم تأذن بعد");
      await expect(page.getByText("استخدام الذكاء الاصطناعي لبناء فرص النشر"))
        .toBeVisible({ timeout: 30_000 });
      await expect(cta(page), "زرُّ إعادةٍ على إذنٍ بائت").toHaveCount(0);
    });

  test("the insufficient-evidence screen is unchanged — no generate action at all",
    async ({ page }) => {
      await register(page);
      await declareModelReady(page);
      await serveContext(page, () => ({ sufficient: false, consent_state: "granted" }));
      const gen = generation(page, [(r) => r.fulfill(json(200, listing([])))]);
      await gen.install([]);
      await openPlanning(page);
      await expect(page.getByText("لا توجد معرفة موثقة كافية لبناء فرصة نشر بعد."))
        .toBeVisible({ timeout: 30_000 });
      await expect(cta(page)).toHaveCount(0);
      expect(gen.keys).toHaveLength(0);
    });

  test("the consent screen is unchanged — consent first, no generate action",
    async ({ page }) => {
      await register(page);
      await declareModelReady(page);
      await serveContext(page, () => ({ sufficient: true, consent_state: "absent" }));
      const gen = generation(page, [(r) => r.fulfill(json(200, listing([])))]);
      await gen.install([]);
      await openPlanning(page);
      await expect(page.getByText("استخدام الذكاء الاصطناعي لبناء فرص النشر"))
        .toBeVisible({ timeout: 30_000 });
      await expect(cta(page)).toHaveCount(0);
    });

  test("the retry label is bilingual", async ({ page }) => {
    await register(page, "en");
    await declareModelReady(page);
    await serveContext(page, () => ({ sufficient: true, consent_state: "granted" }));
    const gen = generation(page, [(r) => r.fulfill(failure(503, "server.error"))]);
    await gen.install([]);
    await openPlanning(page, "en");
    await cta(page).click();
    await expect.poll(() => gen.keys.length, { timeout: 30_000 }).toBe(1);
    await expect(cta(page)).toHaveText("Retry generation");
  });
});

const NAMESPACE = "pubriva.idempotency.v1";
const pendingKeys = (page: Page) => page.evaluate((ns) => {
  const raw = window.sessionStorage.getItem(ns);
  return raw ? Object.values(JSON.parse(raw) as Record<string, { key: string }>)
    .map((r) => r.key) : [];
}, NAMESPACE);
const newGeneration = (page: Page) => page.getByTestId("planning-new-generation");

test.describe("Stage 8 — a retry that cannot help is not offered as a retry", () => {
  test("external_result_unknown: no same-key Retry, the key stays pending, "
    + "and only an explicit new generation mints K2", async ({ page }) => {
    await register(page);
    await declareModelReady(page);
    await serveContext(page, () => ({ sufficient: true, consent_state: "granted" }));
    const gen = generation(page, [
      (r) => r.fulfill(failure(409, "idempotency.external_result_unknown",
        "قد تكون المحاولةُ السابقةُ نُفّذت")),
      (r) => r.fulfill(json(200, listing([opportunity("proposed")]))),
    ]);
    await gen.install([]);
    await openPlanning(page);
    await cta(page).click();
    await expect.poll(() => gen.keys.length, { timeout: 30_000 }).toBe(1);

    await expect(pageError(page)).toContainText("قد تكون المحاولةُ السابقةُ نُفّذت");
    await expect(cta(page), "زرُّ إعادةٍ بالمفتاح نفسِه على أثرٍ لا يُعرف").toHaveCount(0);
    await expect(newGeneration(page)).toHaveText("ابدأ توليدًا جديدًا");
    await expect(page.getByTestId("planning-unknown-note")).toBeVisible();
    // لا طلبَ ثانيًا تلقائيًّا — والنيّةُ K1 باقيةٌ معلَّقة.
    await page.waitForTimeout(1500);
    expect(gen.keys).toHaveLength(1);
    expect(await pendingKeys(page), "حُرّرت النيّةُ بلا قرار").toContain(gen.keys[0]);

    await newGeneration(page).click();
    await expect.poll(() => gen.keys.length, { timeout: 30_000 }).toBe(2);
    expect(gen.keys[1]).toMatch(KEY);
    expect(gen.keys[1], "التوليدُ الجديدُ الصريحُ حمل المفتاحَ القديم").not.toBe(gen.keys[0]);
  });

  test("intent_expired: no network, no same-key Retry, explicit restart mints a new key",
    async ({ page }) => {
      await register(page);
      await declareModelReady(page);
      await serveContext(page, () => ({ sufficient: true, consent_state: "granted" }));
      const posts = { n: 0 };
      page.on("request", (req) => {
        if (req.method() === "POST" && req.url().endsWith("/publication-opportunities")) {
          posts.n += 1;
        }
      });
      const gen = generation(page, [
        (r) => r.fulfill(failure(503, "server.error")),
        (r) => r.fulfill(json(200, listing([]))),
      ]);
      await gen.install([]);
      await openPlanning(page);
      await cta(page).click();
      await expect.poll(() => gen.keys.length, { timeout: 30_000 }).toBe(1);
      await expect(cta(page)).toHaveText("أعد محاولة التوليد");

      // النيّةُ تشيخ بعد الأفق الآمن.
      await page.evaluate((ns) => {
        const all = JSON.parse(window.sessionStorage.getItem(ns) ?? "{}");
        for (const row of Object.values(all) as Array<{ createdAt: number }>) {
          row.createdAt = Date.now() - 23.5 * 60 * 60 * 1000;
        }
        window.sessionStorage.setItem(ns, JSON.stringify(all));
      }, NAMESPACE);
      await cta(page).click();
      await expect(newGeneration(page)).toBeVisible({ timeout: 30_000 });
      await expect(cta(page)).toHaveCount(0);
      expect(posts.n, "طلبٌ خرج على نيّةٍ منقضية").toBe(1);

      await newGeneration(page).click();
      await expect.poll(() => gen.keys.length, { timeout: 30_000 }).toBe(2);
      expect(gen.keys[1]).not.toBe(gen.keys[0]);
    });

  test("idempotency.in_progress keeps Retry and reuses K1", async ({ page }) => {
    await register(page);
    await declareModelReady(page);
    await serveContext(page, () => ({ sufficient: true, consent_state: "granted" }));
    const gen = generation(page, [
      (r) => r.fulfill(failure(409, "idempotency.in_progress")),
      (r) => r.fulfill(json(200, listing([]))),
    ]);
    await gen.install([]);
    await openPlanning(page);
    await cta(page).click();
    await expect.poll(() => gen.keys.length, { timeout: 30_000 }).toBe(1);
    await expect(cta(page)).toHaveText("أعد محاولة التوليد");
    await expect(newGeneration(page)).toHaveCount(0);
    await cta(page).click();
    await expect.poll(() => gen.keys.length, { timeout: 30_000 }).toBe(2);
    expect(gen.keys[1]).toBe(gen.keys[0]);
  });

  test("no cryptographic entropy: no generation CTA and no protected POST",
    async ({ page }) => {
      await register(page);
      await page.addInitScript(() => {
        // `subtle` باقٍ للبصمة؛ مولّدا العشوائيّة وحدَهما يُنزعان.
        Object.defineProperty(Crypto.prototype, "randomUUID",
          { value: undefined, configurable: true });
        Object.defineProperty(Crypto.prototype, "getRandomValues",
          { value: undefined, configurable: true });
      });
      await declareModelReady(page);
      await serveContext(page, () => ({ sufficient: true, consent_state: "granted" }));
      const posts = { n: 0 };
      page.on("request", (req) => {
        if (req.method() === "POST" && req.url().endsWith("/publication-opportunities")) {
          posts.n += 1;
        }
      });
      const gen = generation(page, [(r) => r.fulfill(json(200, listing([])))]);
      await gen.install([]);
      await openPlanning(page);
      await cta(page).click();
      await expect(pageError(page)).toContainText("عشوائيّةً معمّاة", { timeout: 30_000 });
      await expect(cta(page), "زرُّ توليدٍ يَعِد بما تمنعه البيئة").toHaveCount(0);
      await expect(newGeneration(page)).toHaveCount(0);
      await page.waitForTimeout(1000);
      expect(posts.n, "طلبٌ محميٌّ خرج بلا عشوائيّةٍ معمّاة").toBe(0);
    });
});

test.describe("Stage 8 — the outline build carries one key per intent", () => {
  async function selectedWorkspace(page: Page) {
    await declareModelReady(page);
    await serveContext(page, () => ({ sufficient: true, consent_state: "granted" }));
    const gen = generation(page, [(r) => r.fulfill(json(200, listing([])))]);
    await gen.install([opportunity("selected")]);
    await openPlanning(page);
    await page.getByRole("button", { name: "هيكل الورقة", exact: true })
      .click({ timeout: 30_000 });
    return page.getByRole("button", { name: "ابنِ هيكل الورقة" });
  }

  const outlineBody = (id: string) => ({
    id, opportunity_id: OPPORTUNITY, article_type: "extraction", sections: [],
    status: "draft", note: "هيكلٌ لا نصّ",
  });

  function outlineCalls(page: Page, answers: Array<(r: Route, n: number) => Promise<void>>) {
    const keys: string[] = [];
    let n = 0;
    return {
      keys,
      install: () => page.route(
        `**/api/v1/projects/${PROJECT}/publication-opportunities/${OPPORTUNITY}/outline`,
        async (route) => {
          if (route.request().method() !== "POST") { await route.continue(); return; }
          const key = route.request().headers()["idempotency-key"] ?? "";
          const answer = answers[Math.min(n, answers.length - 1)];
          n += 1;
          await answer(route, n);
          keys.push(key);
        }),
    };
  }

  test("an ambiguous outline reply is retried with the same key, then a new build mints another",
    async ({ page }) => {
      await register(page);
      const calls = outlineCalls(page, [
        (r) => r.abort("connectionfailed"),
        (r) => r.fulfill(json(200, outlineBody("11111111-0000-4000-8000-000000000001"))),
        (r) => r.fulfill(json(200, outlineBody("11111111-0000-4000-8000-000000000002"))),
      ]);
      await calls.install();
      const build = await selectedWorkspace(page);

      await build.click();
      await expect.poll(() => calls.keys.length, { timeout: 30_000 }).toBe(1);
      await expect(build).toBeEnabled({ timeout: 30_000 });
      await build.click();
      await expect.poll(() => calls.keys.length, { timeout: 30_000 }).toBe(2);
      expect(calls.keys[0]).toMatch(KEY);
      expect(calls.keys[1], "الإعادةُ بعد انقطاعٍ ولّدت مفتاحًا جديدًا").toBe(calls.keys[0]);
      await expect(pageError(page)).toHaveCount(0);

      await build.click();
      await expect.poll(() => calls.keys.length, { timeout: 30_000 }).toBe(3);
      expect(calls.keys[2], "بناءٌ مقصودٌ بعد النجاح حمل مفتاحًا محسومًا")
        .not.toBe(calls.keys[0]);
    });

  test("a 401 on the outline refreshes the session and retries with the same key",
    async ({ page }) => {
      await register(page);
      await page.route("**/api/v1/auth/refresh", (route) => route.continue());
      const calls = outlineCalls(page, [
        (r) => r.fulfill(failure(401, "auth.expired")),
        (r) => r.fulfill(json(200, outlineBody("22222222-0000-4000-8000-000000000001"))),
      ]);
      await calls.install();
      const build = await selectedWorkspace(page);

      await build.click();
      await expect.poll(() => calls.keys.length, { timeout: 30_000 }).toBe(2);
      expect(calls.keys[0]).toMatch(KEY);
      expect(calls.keys[1], "التجديدُ ولّد مفتاحًا جديدًا").toBe(calls.keys[0]);
    });
});
