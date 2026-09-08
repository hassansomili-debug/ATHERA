import { expect, test, type Locator, type Page, type Route } from "@playwright/test";

/**
 * ردٌّ بائت لا يكتب فوق شاشةٍ حاضرة | No stale load overwrites current state.
 *
 * **العطبُ كما وقع في الإنتاج.** رُصد في قبول الموجة 1.1: يُفتح مركزُ
 * الرسائل فينطلق طلبُ عرض «الكلّ»، ويُبدَّل العرضُ إلى «المؤرشفة» قبل أن
 * يستقرّ الأوّل. فيمضي الطلبان معًا، ويصل «الكلّ» أخيرًا فيكتب صفوفَه فوق
 * صفوف «المؤرشفة»: القائمةُ المنسدلة تقول عرضًا والصفوفُ تقول آخر.
 *
 * ## لماذا هذه الرقعة حتميّة، ولا تنتظر بعدّاد
 *
 * الترتيبُ هنا **مصنوع لا مرصود**: الشبكةُ معترَضة، وكلُّ ردٍّ يُحتجز عند
 * الاعتراض حتى تُطلقه الرقعةُ بنفسها. فيقع «وصل الثاني قبل الأول» بأمرٍ
 * منّا، لا بحظِّ توقيتٍ يختلف بين جهازٍ وجهاز. ولا نوم، ولا `retries`
 * تُخفي تقطّعًا.
 *
 * **والنفيُ وحده يُقاس بمهلة.** إثباتُ «لم يظهر صفُّ الطلب البائت» لا يُقال
 * إلّا بانتظارٍ محدود، وهو انتظارٌ يلي **إطلاقًا حتميًّا** لذلك الردّ
 * وانتظارَ وصولِه على الشبكة — لا سكونًا على أمل.
 *
 * والجلسةُ مزروعة والشبكةُ معترَضة — فلا خادمَ خلفي ولا اعتمادَ إنتاج.
 */

const AR = "ar";

interface Outcome {
  status: number;
  body: unknown;
}

/** طلبٌ مُحتجَز عند الاعتراض — يبقى معلّقًا حتى تُطلقه الرقعة. */
interface Held {
  url: string;
  release: (outcome: Outcome) => void;
}

async function seedSession(page: Page) {
  await page.addInitScript(() => {
    if (sessionStorage.getItem("__seeded")) return;
    sessionStorage.setItem("__seeded", "1");
    localStorage.setItem("athera_access_token", "stale-load-access");
    localStorage.setItem("athera_refresh_token", "stale-load-refresh");
    localStorage.setItem("athera_token_expiry", String(Date.now() + 900_000));
  });
}

function json(route: Route, status: number, payload: unknown) {
  return route.fulfill({
    status, contentType: "application/json", body: JSON.stringify(payload),
  });
}

/** جسمُ خطأٍ بالشكل الذي تفهمه `AtheraApiError`. */
function failure() {
  const message = "تعذّر التحميل.";
  return {
    error: {
      code: "server_error", locale: AR, message,
      messages: { ar: message, en: "Load failed." }, context: {},
    },
  };
}

/**
 * اعتراضٌ يحتجز مسارًا بعينه ويجيب ما عداه إجابةً حميدة.
 *
 * `held` يمتلئ بترتيب **خروج** الطلبات، وتُطلقها الرقعةُ بأيّ ترتيب شاءت —
 * وفي ذلك بالضبط تُصنع المسابقة.
 */
async function serve(page: Page, holdPath: string, held: Held[]) {
  await page.route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());

    if (url.pathname === holdPath && route.request().method() === "GET") {
      const outcome = await new Promise<Outcome>((release) => {
        held.push({ url: route.request().url(), release });
      });
      return json(route, outcome.status, outcome.body);
    }

    // كلُّ ما عدا ذلك يُجاب — نداءٌ معلَّق يُبقي «جارٍ التحميل» إلى الأبد.
    if (url.pathname === "/api/v1/settings/posture") {
      return json(route, 200, {
        tenant_name: "قياس", locale: AR, supported_locales: ["ar", "en"],
        roles: [], items: [],
      });
    }
    if (url.pathname === "/api/v1/inbox/summary") {
      return json(route, 200, {
        pending_approvals: 0, open_alerts: 0, blocking_alerts: 0, unread_notifications: 0,
      });
    }
    return json(route, 200, []);
  });
}

/** ينتظر **خروجَ** العدد المطلوب من الطلبات — شرطٌ يُستقصى، لا مدّةٌ تُنام. */
async function awaitHeld(held: Held[], count: number) {
  await expect.poll(() => held.length, { timeout: 20_000 }).toBeGreaterThanOrEqual(count);
}

/**
 * **هل ظهر شيءٌ كان يجب ألّا يظهر؟**
 *
 * تُستعمل بعد إطلاقٍ حتميّ لردٍّ بائت وانتظارِ وصوله؛ فالمهلةُ هنا نافذةُ
 * رصدٍ للنفي، لا انتظارًا لحدثٍ متوقَّع.
 */
async function appearedWithin(target: Locator, ms: number): Promise<boolean> {
  return target.first()
    .waitFor({ state: "visible", timeout: ms })
    .then(() => true, () => false);
}

function auditEvent(id: string, action: string, seq: number) {
  return {
    id, occurred_at: "2026-02-02T00:00:00Z", actor_user_id: null,
    actor_kind: "researcher", action, object_type: "thesis",
    object_id: null, reason: null, chain_seq: seq,
    hash: `${id}0123456789abcdef`,
  };
}

test.beforeEach(async ({ page }) => {
  await seedSession(page);
});

// ═════════ ١ · سباقُ الاعتماديات ═════════

test("a superseded response cannot overwrite the current dependency's rows", async ({ page }) => {
  const held: Held[] = [];
  await serve(page, "/api/v1/audit/events", held);

  await page.goto(`/${AR}/audit`);
  // الجيلُ الأول: بلا مرشِّح.
  await awaitHeld(held, 1);
  expect(new URL(held[0].url).searchParams.get("object_type")).toBeNull();

  // الجيلُ الثاني يبدأ **قبل أن ينتهي الأول** — وهو شرطُ العقد بعينه.
  await page.locator("#audit-object-type").fill("manuscript");
  await awaitHeld(held, 2);
  expect(new URL(held[1].url).searchParams.get("object_type")).toBe("manuscript");

  // يصل الثاني أولًا…
  held[1].release({ status: 200, body: [auditEvent("b", "manuscript.created", 2)] });
  await expect(page.getByText("manuscript.created")).toBeVisible();

  // …ثمّ يصل الأول متأخّرًا. وهنا كان يكتب فوقه.
  const stale = page.waitForResponse(
    (r) => r.url() === held[0].url && r.request().method() === "GET");
  held[0].release({ status: 200, body: [auditEvent("a", "thesis.archived", 1)] });
  await stale;

  expect(await appearedWithin(page.getByText("thesis.archived"), 3_000),
         "الردُّ البائت كتب صفوفَه فوق الجيل الحاضر").toBe(false);
  await expect(page.getByText("manuscript.created"),
               "صفوفُ الجيل الحاضر اختفت").toBeVisible();
  // **الشاشةُ تصف نفسها بصدق**: المرشِّحُ المعروض هو مرشِّحُ الصفوف.
  await expect(page.locator("#audit-object-type")).toHaveValue("manuscript");
});

// ═════════ ٢ · فكُّ التركيب ═════════

test("a load that finishes after unmount commits nothing and raises nothing", async ({ page }) => {
  const held: Held[] = [];
  const crashes: string[] = [];
  const complaints: string[] = [];
  page.on("pageerror", (e) => crashes.push(String(e)));
  page.on("console", (m) => {
    if (m.type() !== "error") return;
    const text = m.text();
    // تحذيرُ React المعروف عن الكتابة بعد فكّ التركيب — هو المقصود بالرصد.
    if (/unmount|not mounted|state update/i.test(text)) complaints.push(text);
  });

  await serve(page, "/api/v1/audit/events", held);
  await page.goto(`/${AR}/audit`);
  await awaitHeld(held, 1);

  // انتقالٌ داخل التطبيق — فكُّ تركيبٍ حقيقيّ، والمستندُ باقٍ لتُرصد آثارُه.
  await page.locator(`a[href="/${AR}/theses"]`).first().click();
  await expect(page).toHaveURL(new RegExp(`/${AR}/theses$`));

  const late = page.waitForResponse(
    (r) => r.url() === held[0].url && r.request().method() === "GET");
  held[0].release({ status: 200, body: [auditEvent("a", "thesis.archived", 1)] });
  await late;

  expect(await appearedWithin(page.getByText("thesis.archived"), 3_000),
         "شاشةٌ فُكّ تركيبُها كتبت صفوفَها في شاشةٍ أخرى").toBe(false);
  expect(crashes, "انكسرت الصفحة بعد فكّ التركيب").toEqual([]);
  expect(complaints, "كتابةُ حالةٍ بعد فكّ التركيب").toEqual([]);
});

// ═════════ ٣ · سباقُ الخطأ — أكثرُ ما يُنسى ═════════

test("a stale failure never replaces the current generation's valid rows", async ({ page }) => {
  const held: Held[] = [];
  await serve(page, "/api/v1/audit/events", held);

  await page.goto(`/${AR}/audit`);
  await awaitHeld(held, 1);
  await page.locator("#audit-object-type").fill("manuscript");
  await awaitHeld(held, 2);

  // الجيلُ الحاضر ينجح…
  held[1].release({ status: 200, body: [auditEvent("b", "manuscript.created", 2)] });
  await expect(page.getByText("manuscript.created")).toBeVisible();

  // …والجيلُ البائت **يفشل** بعده. ومسارُ الخطأ هو الذي يُنسى تبويبُه:
  // رسالةُ فشلٍ عن طلبٍ لا يخصّ الشاشة، تمحو صفوفًا صحيحة بحمرةٍ كاذبة.
  const stale = page.waitForResponse(
    (r) => r.url() === held[0].url && r.request().method() === "GET");
  held[0].release({ status: 500, body: failure() });
  await stale;

  expect(await appearedWithin(page.locator(".error"), 3_000),
         "فشلٌ بائت عُرض على الباحث").toBe(false);
  await expect(page.getByText("manuscript.created"),
               "فشلٌ بائت محا صفوفًا صحيحة").toBeVisible();
});

// ═════════ ٤ · مركزُ الرسائل — العطبُ الأصلي ═════════

interface Row {
  id: string;
  filename: string;
  archived: boolean;
}

/** صفٌّ كامل بالشكل الذي ترسله الواجهة البرمجية — لا حقلَ ناقص. */
function thesis(row: Row) {
  return {
    id: row.id,
    title: null,
    degree: null,
    source_filename: row.filename,
    source_file_id: `file-${row.id}`,
    display_title: row.filename,
    title_is_extracted: false,
    processing_state: "ready_for_review",
    processing_state_label: "جاهزة لمراجعتك",
    processing_attempts: 1,
    failure_code: null,
    failure_message: null,
    can_retry: false,
    retry_blocked_reason: null,
    text_layer_state: "not_checked",
    ocr_state: "unavailable",
    ocr_available: false,
    defended_on: null,
    data_collected_on: null,
    rights_basis: null,
    parsed_at: null,
    sections_extracted: 0,
    sections_outcome: "not_started",
    sections_outcome_label: "لم يبدأ التحليل بعد",
    results_extracted: 0,
    opportunities_found: 0,
    opportunities_outcome: "not_started",
    opportunities_outcome_label: "لم يبدأ استخراج الفرص بعد",
    opportunities_are_candidates: true,
    archived_at: row.archived ? "2026-02-02T00:00:00Z" : null,
    actions: {
      primary: "review",
      is_running: false,
      can_review: true,
      can_process: false,
      can_reprocess: false,
      can_parse: false,
      can_attach_file: false,
      can_mine: false,
      can_archive: !row.archived,
      can_restore: row.archived,
      can_trash_file: !row.archived,
      is_archived: row.archived,
      lifecycle_blocked_reason: null,
      mining_state: "no_evidence",
      mining_reason:
        "لم يجرِ فحصُ الفرص بعد: لا دليلَ مؤهَّل على هذه الرسالة حتى الآن. "
        + "والفحصُ يبدأ تلقائيًّا بعد قراءة الرسالة، ولا يلزمك تشغيلُه.",
      parse_withdrawn_reason: "المسار القديم مسحوبٌ من البطاقة.",
      blocked_reason: null,
    },
  };
}

test("the Thesis Center dropdown and its rows always describe the same view", async ({ page }) => {
  const held: Held[] = [];
  await serve(page, "/api/v1/theses", held);

  await page.goto(`/${AR}/theses`);
  // عرضُ «الكلّ» انطلق ولمّا يستقرّ.
  await awaitHeld(held, 1);
  expect(new URL(held[0].url).searchParams.get("view")).toBeNull();

  // يُبدَّل العرضُ **قبل استقراره** — وهو تسلسلُ الإنتاج بعينه.
  await page.locator("#thesis-view").selectOption("archived");
  await awaitHeld(held, 2);
  expect(new URL(held[1].url).searchParams.get("view")).toBe("archived");

  // تستقرّ «المؤرشفة» أوّلًا.
  held[1].release({
    status: 200,
    body: [thesis({ id: "arch-1", filename: "ARCHIVED-ROW.pdf", archived: true })],
  });
  await expect(page.getByTestId("thesis-card-arch-1")).toBeVisible();

  // ثمّ يصل ردُّ «الكلّ» متأخّرًا — **هنا كان يكتب فوقها**.
  const stale = page.waitForResponse(
    (r) => r.url() === held[0].url && r.request().method() === "GET");
  held[0].release({
    status: 200,
    body: [thesis({ id: "live-1", filename: "ACTIVE-ROW.pdf", archived: false })],
  });
  await stale;

  expect(await appearedWithin(page.getByTestId("thesis-card-live-1"), 3_000),
         "صفوفُ «الكلّ» كُتبت تحت اسم «المؤرشفة»").toBe(false);
  await expect(page.getByTestId("thesis-card-arch-1"),
               "صفوفُ «المؤرشفة» مُحيت بردٍّ بائت").toBeVisible();
  // **الشرطُ الذي يصف العطب**: المنسدلةُ والصفوفُ تصفان عرضًا واحدًا.
  await expect(page.locator("#thesis-view")).toHaveValue("archived");
});
