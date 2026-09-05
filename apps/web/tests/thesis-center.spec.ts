import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * مركزُ الرسائل | The Thesis Center card — control → request → response → UI.
 *
 * **ووجودُ الزرّ ليس دليلًا على شيء.** الفحص هنا لا يكتفي برؤية عنصر: يضغط،
 * ويلتقط **الطلب** الذي خرج، ويردّ عليه ردًّا محدَّدًا، ثم يفحص **ما تغيّر
 * في البطاقة نفسها**. وثلاثُ حلقاتٍ لا اثنتان.
 *
 * ## ما تفحصه هذه الرقعة، وما لا تفحصه
 *
 * الشبكةُ معترَضة والجلسةُ مزروعة — كطبقة `product-surface` — فتعمل في كل
 * PR بلا خادمٍ خلفي وبلا اعتماد. **وهي تفحص الشاشة على عقدٍ مُعطى**: أنّ
 * البطاقة تعرض ما يقوله الخادم، وأنّ الضغطة تُخرج الطلب الصحيح، وأنّ الردّ
 * يقع في البطاقة الصحيحة.
 *
 * **ولا تفحص العزلَ بين المستأجرين** — ذاك لا يُثبَت في المتصفّح، ويُثبَت
 * في `apps/api/tests/test_at_thesis_center_stabilization.py` على قاعدةٍ
 * حيّة بمستأجرَين. والمفحوص هنا وجهُه الآخر: أنّ رفضَ الخادم بـ404 **يُقرأ
 * في بطاقته** ولا يضيع في أعلى الصفحة.
 */

const AR = "ar";
const LOADING_AR = "جارٍ التحميل…";
const APP_ORIGIN = new URL(process.env.PUBRIVA_WEB_URL ?? "http://127.0.0.1:3000").origin;

/** أسماءُ الأفعال كما في `services/thesis/card_actions.py` — مفردةٌ واحدة. */
type Primary = "review" | "process" | "reprocess" | "attach_file" | null;

interface Actions {
  primary: Primary;
  is_running: boolean;
  can_review: boolean;
  can_process: boolean;
  can_reprocess: boolean;
  can_parse: boolean;
  can_attach_file: boolean;
  can_mine: boolean;
  can_remove: boolean;
  can_trash_file: boolean;
  mining_state: "available" | "in_flight" | "no_evidence";
  mining_reason: string;
  parse_withdrawn_reason: string;
  blocked_reason: string | null;
}

interface Card {
  id: string;
  state: string;
  stateLabel: string;
  filename: string;
  fileId: string | null;
  sections: number;
  results: number;
  opportunities: number;
  minedAt: string | null;
  failureCode: string | null;
}

const NO_EVIDENCE_AR =
  "استخراج الفرص غير متاح بعد. المنقّب يقرأ الأقسام والنتائج المستخرجة، ولم يُكتب " +
  "منها شيءٌ لهذه الرسالة.";
const IN_FLIGHT_AR = "المعالجة جاريةٌ الآن — واستخراج الفرص ينتظر انتهاءها.";
const AVAILABLE_AR = "استخراج الفرص متاح: توجد عناصر مستخرجة يقرؤها المنقّب.";
const PARSE_WITHDRAWN_AR = "«تفكيك الرسالة» مسارٌ قديم بقي في الواجهة البرمجية.";

const IN_FLIGHT_STATES = new Set(["queued", "parsing", "extracting"]);
const REVIEWABLE_STATES = new Set(["awaiting_consent", "ready_for_review", "completed"]);
const RETRYABLE_STATES = new Set([
  "uploaded", "awaiting_consent", "ready_for_review", "completed", "failed",
]);

/**
 * آلةُ الحال كما يحسبها الخادم — **مُحاكاةٌ مقصودة**.
 *
 * والمقياسُ الحقيقي في `card_actions.compute`، ويحرسه فحصُ بايثون. وهذه
 * نسخةٌ للاعتراض وحده: تُعطي الشاشةَ عقدًا واقعيًّا لتُفحَص عليه.
 */
function actionsFor(card: Card): Actions {
  const inFlight = IN_FLIGHT_STATES.has(card.state);
  const hasFile = card.fileId !== null;
  const retryable = hasFile && RETRYABLE_STATES.has(card.state);
  const firstRead = retryable && card.state === "uploaded";
  const canReview = !inFlight && REVIEWABLE_STATES.has(card.state);
  const canAttach = !hasFile && !inFlight;
  const hasEvidence = card.sections > 0 || card.results > 0;
  const mining = hasEvidence ? "available" : inFlight ? "in_flight" : "no_evidence";

  let primary: Primary = null;
  if (canAttach) primary = "attach_file";
  else if (canReview) primary = "review";
  else if (firstRead) primary = "process";
  else if (retryable) primary = "reprocess";

  return {
    primary,
    is_running: inFlight,
    can_review: canReview,
    can_process: firstRead,
    can_reprocess: retryable && !firstRead,
    can_parse: false,
    can_attach_file: canAttach,
    can_mine: mining === "available" && !inFlight,
    can_remove: true,
    can_trash_file: hasFile,
    mining_state: mining as Actions["mining_state"],
    mining_reason:
      mining === "available" ? AVAILABLE_AR : mining === "in_flight" ? IN_FLIGHT_AR : NO_EVIDENCE_AR,
    parse_withdrawn_reason: PARSE_WITHDRAWN_AR,
    blocked_reason: inFlight ? card.stateLabel : null,
  };
}

function body(card: Card) {
  const found = card.opportunities > 0;
  return {
    id: card.id,
    title: null,
    title_ar: null,
    degree: null,
    source_filename: card.filename,
    source_file_id: card.fileId,
    display_title: card.filename,
    title_is_extracted: false,
    processing_state: card.state,
    processing_state_label: card.stateLabel,
    processing_attempts: 1,
    failure_code: card.failureCode,
    failure_message: card.failureCode ? "تعذّرت قراءة المستند." : null,
    can_retry: card.fileId !== null && RETRYABLE_STATES.has(card.state),
    retry_blocked_reason:
      card.state === "text_layer_missing"
        ? "المستند ممسوح ضوئيًّا بلا طبقة نصّ، ولا تتوفّر قراءة ضوئية (OCR) بعد."
        : null,
    text_layer_state: "not_checked",
    ocr_state: "unavailable",
    ocr_available: false,
    defended_on: null,
    data_collected_on: null,
    rights_basis: null,
    parsed_at: card.sections > 0 ? "2026-01-01T00:00:00Z" : null,
    sections_extracted: card.sections,
    sections_outcome: card.sections > 0 ? "found" : "not_started",
    sections_outcome_label: card.sections > 0 ? "أقسام مستخرجة" : "لم يبدأ التحليل بعد",
    results_extracted: card.results,
    opportunities_found: card.opportunities,
    opportunities_outcome: found ? "found" : card.minedAt ? "completed_empty" : "not_started",
    opportunities_outcome_label: found
      ? "فرص مرشَّحة"
      : card.minedAt
        ? "اكتمل الفحص ولم يُعثر على فرصةٍ مرشَّحة"
        : "لم يبدأ استخراج الفرص بعد",
    opportunities_mined_at: card.minedAt,
    opportunities_are_candidates: true,
    actions: actionsFor(card),
  };
}

/** الحالاتُ المستعملة في هذه الرقعة، بأسمائها كما يرسلها الخادم. */
const LABELS: Record<string, string> = {
  uploaded: "رُفع الملف",
  queued: "في انتظار الدور",
  parsing: "جارٍ قراءة المستند",
  extracting: "جارٍ استخراج بنية الرسالة",
  ready_for_review: "جاهزة لمراجعتك",
  completed: "اكتمل التحليل",
  failed: "تعذّر التحليل",
  text_layer_missing: "لا توجد طبقة نصّ في المستند",
};

function make(id: string, over: Partial<Card> = {}): Card {
  const state = over.state ?? "ready_for_review";
  return {
    id,
    state,
    stateLabel: LABELS[state] ?? state,
    filename: over.filename ?? `${id}.pdf`,
    fileId: over.fileId === undefined ? `file-${id}` : over.fileId,
    sections: over.sections ?? 0,
    results: over.results ?? 0,
    opportunities: over.opportunities ?? 0,
    minedAt: over.minedAt ?? null,
    failureCode: over.failureCode ?? null,
  };
}

async function seedSession(page: Page) {
  await page.addInitScript(() => {
    if (sessionStorage.getItem("__seeded")) return;
    sessionStorage.setItem("__seeded", "1");
    localStorage.setItem("athera_access_token", "thesis-center-access");
    localStorage.setItem("athera_refresh_token", "thesis-center-refresh");
    localStorage.setItem("athera_token_expiry", String(Date.now() + 900_000));
  });
}

interface Server {
  cards: Map<string, Card>;
  /** كلُّ طلبٍ خرج من الشاشة — **الشاهدُ على أنّ الضغطة أرسلت شيئًا**. */
  seen: { method: string; path: string }[];
  /** مسارات تُردّ برفضٍ مقصود، ورمزُ الرفض. */
  refuse: Map<string, { status: number; code: string; message: string }>;
  /** ما يقوم على كلّ رسالة — تُقرأ في المعاينة. */
  deps: Map<string, { key: string; label: string; count: number; blocking: boolean }[]>;
}

function newServer(cards: Card[]): Server {
  return {
    cards: new Map(cards.map((c) => [c.id, c])),
    seen: [],
    refuse: new Map(),
    deps: new Map(),
  };
}

function json(route: Route, status: number, payload: unknown) {
  return route.fulfill({
    status, contentType: "application/json", body: JSON.stringify(payload),
  });
}

function error(route: Route, status: number, code: string, message: string) {
  return json(route, status, {
    error: { code, locale: AR, message, messages: { ar: message, en: message }, context: {} },
  });
}

/**
 * خادمٌ صغير في الاعتراض — **يتصرّف كالخادم الحقيقي على نقاط هذه الشاشة**.
 *
 * وردٌّ ثابت لا يثبت أنّ الشاشة تُحدِّث نفسها؛ فالحالُ هنا تتغيّر فعلًا:
 * `reprocess` تنقل الحال إلى `queued`، والتنقيبُ الأول يكتب فرصًا والثاني
 * لا يكتب شيئًا — **وهو بعينه ما يفحصه شرطُ «لا تكرار»**.
 */
async function serve(page: Page, server: Server) {
  await page.route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    server.seen.push({ method, path });

    const refusal = server.refuse.get(`${method} ${path}`);
    if (refusal) return error(route, refusal.status, refusal.code, refusal.message);

    if (path === "/api/v1/theses" && method === "GET") {
      return json(route, 200, [...server.cards.values()].map(body));
    }

    const listed = path.match(/^\/api\/v1\/theses\/([^/]+)(\/[a-z-]+)?$/);
    if (listed) {
      const [, id, tail] = listed;
      const card = server.cards.get(id);
      if (!card) {
        return error(route, 404, "thesis.not_found", "الرسالة غير موجودة.");
      }
      if (tail === "/reprocess" && method === "POST") {
        card.state = "queued";
        card.stateLabel = LABELS.queued;
        card.failureCode = null;
        return json(route, 202, { thesis_id: id, status: "queued" });
      }
      if (tail === "/mine-opportunities" && method === "POST") {
        // **إعادةُ التنقيب لا تُضاعف**: ما هو قائمٌ لا يُكتب مرّةً ثانية.
        const already = card.opportunities;
        const created = already > 0 ? 0 : 3;
        card.opportunities = already + created;
        card.minedAt = "2026-02-02T00:00:00Z";
        return json(route, 202, {
          thesis_id: id, opportunities_created: created,
          opportunities_already_present: already, kinds: ["independent_question"],
          aging: {
            data_age_years: null, literature_age_years: null,
            needs_literature_update: null, needs_reanalysis_review: null,
            note: "", note_ar: "", note_en: "",
          },
        });
      }
      if (tail === "/removal-preview" && method === "GET") {
        const deps = server.deps.get(id) ?? [];
        const blocking = deps.filter((d) => d.blocking && d.count > 0);
        return json(route, 200, {
          thesis_id: id,
          removable: blocking.length === 0,
          dependencies: deps,
          blocking,
          explanation:
            blocking.length === 0
              ? "لا شيء علميٌّ قائمٌ على هذه الرسالة."
              : "لا تُزال هذه الرسالة: يقوم عليها عملٌ علميٌّ حسمتَه بنفسك.",
          source_file_id: card.fileId,
        });
      }
      if (!tail && method === "DELETE") {
        const blocking = (server.deps.get(id) ?? []).filter((d) => d.blocking && d.count > 0);
        if (blocking.length > 0) {
          return error(route, 409, "thesis.removal_blocked",
                       "لا تُزال هذه الرسالة: يقوم عليها عملٌ علميٌّ حسمتَه بنفسك.");
        }
        server.cards.delete(id);
        return json(route, 200, { thesis_id: id, removed: true, dropped: {},
                                  audit_preserved: true });
      }
    }

    if (path.endsWith("/trash") && method === "POST") {
      return json(route, 200, { id: "f", trashed_at: "2026-02-02T00:00:00Z",
                                project_links: [] });
    }

    // كلُّ ما عدا ذلك يُجاب — نداءٌ معلَّق يُبقي «جارٍ التحميل» إلى الأبد.
    if (path === "/api/v1/settings/posture") {
      return json(route, 200, {
        tenant_name: "مركز الرسائل", locale: AR, supported_locales: ["ar", "en"],
        roles: [], items: [],
      });
    }
    if (path === "/api/v1/inbox/summary") {
      return json(route, 200, {
        pending_approvals: 0, open_alerts: 0, blocking_alerts: 0, unread_notifications: 0,
      });
    }
    return json(route, 200, []);
  });
}

async function openTheses(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("response", (r) => {
    if (new URL(r.url()).origin === APP_ORIGIN && r.status() >= 500) {
      errors.push(`${r.status()} ${r.url()}`);
    }
  });
  await page.goto(`/${AR}/theses`);
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
  await expect(page.getByText(LOADING_AR)).toHaveCount(0, { timeout: 20_000 });
  return errors;
}

/** البطاقة بعينها — **والتحديدُ داخلها دائمًا**: الشاشة تحمل بطاقاتٍ كثيرة. */
function cardOf(page: Page, id: string) {
  return page.getByTestId(`thesis-card-${id}`);
}

test.beforeEach(async ({ page }) => {
  await seedSession(page);
});

test.describe("the card offers only what the server accepts", () => {
  test("a queued thesis carries no legacy parse, no mine and no retry", async ({ page }) => {
    const server = newServer([make("queued-one", { state: "queued" })]);
    await serve(page, server);
    const errors = await openTheses(page);

    const card = cardOf(page, "queued-one");
    await expect(card).toBeVisible();
    // **العطبُ الأصلي**: زرُّ «تفكيك الرسالة» كان يُعرض على كلّ بطاقة.
    await expect(card.getByRole("button", { name: "تفكيك الرسالة", exact: true }))
      .toHaveCount(0);
    await expect(card.getByTestId("card-mine")).toHaveCount(0);
    await expect(card.getByTestId("card-reprocess")).toHaveCount(0);
    await expect(card.getByTestId("card-process")).toHaveCount(0);
    // ولا تُترك بلا خبر: ما يجري يُقال.
    await expect(card.getByTestId("card-running")).toContainText("في انتظار الدور");
    expect(errors).toEqual([]);
  });

  for (const state of ["parsing", "extracting"]) {
    test(`a thesis being ${state} shows progress and no dead action`, async ({ page }) => {
      const server = newServer([make(`busy-${state}`, { state, sections: 4 })]);
      await serve(page, server);
      await openTheses(page);

      const card = cardOf(page, `busy-${state}`);
      await expect(card.getByTestId("card-running")).toBeVisible();
      // ولو كان عند المنقّب دليل، فالعملُ الجاري يمنع الطلب — والخادم يردّ 409.
      await expect(card.getByTestId("card-mine")).toHaveCount(0);
      await expect(card.getByTestId("card-reprocess")).toHaveCount(0);
      // **ولا فعلَ مخفيّ**: لا زرَّ في البطاقة يُخرج طلبَ معالجة. والعدُّ
      // على الكتابات وحدها — القراءاتُ تقع من تلقاء الشاشة.
      await card.getByTestId("card-menu").click();
      await expect(card.getByTestId("menu-reprocess")).toHaveCount(0);
      expect(server.seen.filter((r) => r.method !== "GET")).toEqual([]);
    });
  }

  test("a manually registered thesis with no file is offered an attachment, never parse",
    async ({ page }) => {
      const server = newServer([
        make("manual-one", { state: "uploaded", fileId: null, filename: "بلا ملفّ" }),
      ]);
      await serve(page, server);
      await openTheses(page);

      const card = cardOf(page, "manual-one");
      await expect(card.getByRole("button", { name: "تفكيك الرسالة", exact: true }))
        .toHaveCount(0);
      await expect(card.getByTestId("card-process")).toHaveCount(0);
      await expect(card.getByTestId("card-attach-file"))
        .toHaveText("أرفق ملفّ الرسالة");
      // ولا «انقل الملفّ إلى السلّة» على رسالةٍ لا ملفّ لها.
      await card.getByTestId("card-menu").click();
      await expect(card.getByTestId("menu-trash-file")).toHaveCount(0);
      await expect(card.getByTestId("menu-remove")).toBeVisible();
    });

  /**
   * **ثلاثةُ أفعالٍ لا واحد، ولكلِّ حالٍ فعلُها** (Wave 1.1، §A).
   *
   * ورحلةُ المرشَّح للإصدار تفحص هذا على مكدّسٍ حقيقيّ، لكنّها لا تصنع
   * «سقطت القراءة» متى شاءت: المستندُ النصّيّ يُقرأ فينجح. **فالفرعُ الذي
   * لا تبلغه هي يُثبَت هنا** — حيث تُبنى الحالُ الثلاث حرفًا بحرف.
   *
   * والنصفُ الثاني هو الذي يحمل الوزن: الفعلان الآخران **غائبان**. فحصٌ
   * يطلب الحاضر ولا ينفي غيره يمرّ على بطاقةٍ تعرض الثلاثة معًا — وهو
   * بعينه ما كانت عليه البطاقة قبل هذه الموجة.
   */
  const READ_ACTIONS_AR = ["اقرأ الرسالة", "أعد القراءة", "أعد المحاولة"] as const;

  interface ReadActionCase {
    id: string;
    card: Card;
    expected: (typeof READ_ACTIONS_AR)[number];
    why: string;
  }

  const READ_ACTION_CASES: ReadActionCase[] = [
    {
      id: "never-read",
      card: make("never-read", { state: "uploaded" }),
      expected: "اقرأ الرسالة",
      why: "أوّلُ قراءةٍ ليست إعادة",
    },
    {
      id: "read-once",
      card: make("read-once", { state: "ready_for_review" }),
      expected: "أعد القراءة",
      why: "قُرئ فنجح — فالثانيةُ إعادةُ قراءةٍ لا إصلاحُ عطب",
    },
    {
      id: "read-failed",
      card: make("read-failed", { state: "failed", failureCode: "parse_failed" }),
      expected: "أعد المحاولة",
      why: "سقطت القراءة وللسقوط سبب — فيُعرض إصلاحُها",
    },
  ];

  for (const { id, card, expected, why } of READ_ACTION_CASES) {
    test(`the ${id} state offers exactly «${expected}» and neither of the others`,
      async ({ page }) => {
        await serve(page, newServer([card]));
        await openTheses(page);

        const article = cardOf(page, id);
        for (const label of READ_ACTIONS_AR) {
          const control = article.getByRole("button", { name: label, exact: true });
          if (label === expected) {
            await expect(control, `${why} — ولا زرَّ به`).toBeVisible();
          } else {
            await expect(control, `«${label}» معروضٌ وهو ليس فعلَ هذه الحال`)
              .toHaveCount(0);
          }
        }
      });
  }

  test("a scanned document is offered nothing and told why", async ({ page }) => {
    const server = newServer([
      make("scanned-one", { state: "text_layer_missing", failureCode: null }),
    ]);
    await serve(page, server);
    await openTheses(page);

    const card = cardOf(page, "scanned-one");
    await expect(card.getByTestId("card-reprocess")).toHaveCount(0);
    await expect(card.getByTestId("card-retry-blocked")).toContainText("OCR");
  });
});

test.describe("mining is offered only where the miner has something to read", () => {
  test("a thesis read by the modern pipeline is told mining is not ready, with a reason",
    async ({ page }) => {
      // **الرسالةُ التي كشفت العطب**: جاهزةٌ للمراجعة، ولا قسم ولا نتيجة.
      const server = newServer([make("modern-one", { state: "ready_for_review" })]);
      await serve(page, server);
      await openTheses(page);

      const card = cardOf(page, "modern-one");
      await expect(card.getByTestId("card-mine")).toHaveCount(0);
      await expect(card.getByTestId("card-mining-note"))
        .toContainText("استخراج الفرص غير متاح بعد");
      // ولا يُقال ذلك زرًّا مطفأً: لا زرَّ أصلًا.
      await expect(card.getByRole("button", { name: "استخراج الفرص", exact: true }))
        .toHaveCount(0);
    });

  test("mining dispatches once and a repeat request creates no duplicate",
    async ({ page }) => {
      const server = newServer([
        make("mine-one", { state: "ready_for_review", sections: 2, results: 1 }),
      ]);
      await serve(page, server);
      await openTheses(page);

      const card = cardOf(page, "mine-one");
      await expect(card.getByTestId("card-mine")).toBeVisible();

      const first = page.waitForResponse((r) =>
        r.url().includes("/mine-opportunities") && r.request().method() === "POST");
      await card.getByTestId("card-mine").click();
      expect((await (await first).json()).opportunities_created).toBe(3);
      await expect(card).toContainText("فرص مكتشفة: 3");
      await expect(card.getByTestId("card-notice")).toBeVisible();

      // **الضغطة الثانية**: الخادم يجد ما هو قائم فلا يكتب — والعدد لا يتضاعف.
      const second = page.waitForResponse((r) =>
        r.url().includes("/mine-opportunities") && r.request().method() === "POST");
      await card.getByTestId("card-mine").click();
      const payload = await (await second).json();
      expect(payload.opportunities_created).toBe(0);
      expect(payload.opportunities_already_present).toBe(3);
      await expect(card).toContainText("فرص مكتشفة: 3");
      await expect(card).not.toContainText("فرص مكتشفة: 6");
    });
});

test.describe("every action reports inside its own card", () => {
  test("the review CTA leads to the review screen for that thesis", async ({ page }) => {
    const server = newServer([
      make("review-one", { state: "ready_for_review" }),
      make("review-two", { state: "ready_for_review" }),
    ]);
    await serve(page, server);
    await openTheses(page);

    await cardOf(page, "review-two").getByTestId("card-review").click();
    await expect(page).toHaveURL(new RegExp(`/${AR}/theses/review-two/review$`));
  });

  test("reprocess dispatches and the card's state visibly changes", async ({ page }) => {
    const server = newServer([make("retry-one", { state: "failed", failureCode: "parse_failed" })]);
    await serve(page, server);
    await openTheses(page);

    const card = cardOf(page, "retry-one");
    await expect(card).toContainText("تعذّر التحليل");

    const sent = page.waitForResponse((r) =>
      r.url().includes("/retry-one/reprocess") && r.request().method() === "POST");
    await card.getByTestId("card-reprocess").click();
    expect((await sent).status()).toBe(202);

    // **الشاهدُ في البطاقة لا في الطلب وحده**: الحال تغيّرت في الشاشة.
    await expect(card).toContainText("في انتظار الدور");
    await expect(card.getByTestId("card-notice")).toBeVisible();
    await expect(card.getByTestId("card-reprocess")).toHaveCount(0);
  });

  test("a failed action shows its error inside the right card and nowhere else",
    async ({ page }) => {
      // **العطبُ الذي يُغلق هنا**: خبرُ الفشل كان في أعلى الصفحة، فمن ضغط
      // البطاقة الثالثة لم يعرف أيَّ بطاقةٍ سقطت.
      const server = newServer([
        make("ok-one", { state: "failed", failureCode: "parse_failed" }),
        make("bad-one", { state: "failed", failureCode: "parse_failed" }),
        make("ok-two", { state: "failed", failureCode: "parse_failed" }),
      ]);
      server.refuse.set("POST /api/v1/theses/bad-one/reprocess", {
        status: 409, code: "thesis.processing_in_flight",
        message: "المعالجة جارية على هذه الرسالة الآن.",
      });
      await serve(page, server);
      await openTheses(page);

      await cardOf(page, "bad-one").getByTestId("card-reprocess").click();

      await expect(cardOf(page, "bad-one").getByTestId("card-error"))
        .toContainText("المعالجة جارية على هذه الرسالة الآن.");
      await expect(cardOf(page, "ok-one").getByTestId("card-error")).toHaveCount(0);
      await expect(cardOf(page, "ok-two").getByTestId("card-error")).toHaveCount(0);
    });

  test("a refusal on a thesis this account cannot touch is read in its own card",
    async ({ page }) => {
      // **العزلُ نفسه يُثبَت على قاعدةٍ حيّة في حزمة الـAPI** — والمفحوص
      // هنا وجهُه الآخر: ردُّ 404 يُعرض حيث ضُغط، لا في أعلى الصفحة.
      const server = newServer([make("foreign-one", { state: "failed",
                                                      failureCode: "parse_failed" })]);
      server.refuse.set("POST /api/v1/theses/foreign-one/reprocess", {
        status: 404, code: "thesis.not_found", message: "الرسالة غير موجودة.",
      });
      await serve(page, server);
      await openTheses(page);

      await cardOf(page, "foreign-one").getByTestId("card-reprocess").click();
      await expect(cardOf(page, "foreign-one").getByTestId("card-error"))
        .toContainText("الرسالة غير موجودة.");
    });
});

test.describe("removal previews before it drops anything", () => {
  test("a disposable thesis is previewed, confirmed and then gone", async ({ page }) => {
    const server = newServer([
      make("drop-me", { state: "uploaded" }),
      make("keep-me", { state: "uploaded" }),
    ]);
    server.deps.set("drop-me", [
      { key: "sections", label: "أقسام مستخرجة", count: 0, blocking: false },
    ]);
    await serve(page, server);
    await openTheses(page);

    const card = cardOf(page, "drop-me");
    await card.getByTestId("card-menu").click();
    await card.getByTestId("menu-remove").click();

    await expect(card.getByTestId("removal-preview")).toBeVisible();
    await expect(card.getByTestId("removal-no-dependencies")).toBeVisible();

    const deleted = page.waitForResponse((r) =>
      r.url().endsWith("/api/v1/theses/drop-me") && r.request().method() === "DELETE");
    await card.getByTestId("removal-confirm").click();
    expect((await deleted).status()).toBe(200);

    await expect(cardOf(page, "drop-me")).toHaveCount(0);
    // **ولا تُمسّ جارتُها** — الإزالة فعلٌ على بطاقةٍ واحدة.
    await expect(cardOf(page, "keep-me")).toBeVisible();
  });

  test("removal is refused with a named explanation when work rests on the thesis",
    async ({ page }) => {
      const server = newServer([make("busy-thesis", { state: "completed", sections: 3 })]);
      server.deps.set("busy-thesis", [
        { key: "sections", label: "أقسام مستخرجة", count: 3, blocking: false },
        { key: "publication_opportunities", label: "فرص نشرٍ مرشَّحة", count: 2,
          blocking: true },
      ]);
      await serve(page, server);
      await openTheses(page);

      const card = cardOf(page, "busy-thesis");
      await card.getByTestId("card-menu").click();
      await card.getByTestId("menu-remove").click();

      const preview = card.getByTestId("removal-preview");
      await expect(preview).toContainText("فرص نشرٍ مرشَّحة: 2");
      await expect(preview).toContainText("يمنع الإزالة");
      await expect(card.getByTestId("removal-refused")).toBeVisible();
      // **ولا زرَّ يَعِد بحذفٍ سيُردّ** — والإزالة لا تُعرض فعلًا هنا.
      await expect(card.getByTestId("removal-confirm")).toHaveCount(0);

      // ولا طلبَ حذفٍ خرج أصلًا.
      expect(server.seen.filter((r) => r.method === "DELETE")).toEqual([]);
      await expect(cardOf(page, "busy-thesis")).toBeVisible();
    });

  test("trashing the source file is a separate action from removing the record",
    async ({ page }) => {
      const server = newServer([make("with-file", { state: "uploaded" })]);
      await serve(page, server);
      await openTheses(page);

      const card = cardOf(page, "with-file");
      await card.getByTestId("card-menu").click();
      await expect(card.getByTestId("menu-remove")).toBeVisible();
      await expect(card.getByTestId("menu-trash-file")).toBeVisible();

      const trashed = page.waitForResponse((r) =>
        r.url().includes("/api/v1/files/") && r.url().endsWith("/trash"));
      await card.getByTestId("menu-trash-file").click();
      expect((await trashed).status()).toBe(200);

      await expect(card.getByTestId("card-notice")).toContainText("سلّة المكتبة");
      // **والسجلُّ باقٍ**: نقلُ الملفّ لم يُزل البطاقة.
      await expect(cardOf(page, "with-file")).toBeVisible();
      expect(server.seen.filter((r) => r.method === "DELETE")).toEqual([]);
    });
});
