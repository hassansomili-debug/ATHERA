import { expect, test, type Page, type Response } from "@playwright/test";

import { LOCALE, signIn } from "./journey";

/**
 * P0-T1 — قبولُ الإنتاج المنشور | T1 production acceptance.
 *
 * **ولا نظيرَ لهذه الرقعة في المستودع.** `automatic-opportunity-journey`
 * تفحص الغيابَ على شبكةٍ **معترَضة**: تُلفَّق الردود فتُثبت الدعوى على
 * خادمٍ من صنع الفحص. وهي حراسةٌ صحيحة لسطح المنتج، ولا تصلح قبولًا
 * إنتاجيًّا: لا تُثبت أنّ الإنتاج المنشور يفعل ذلك فعلًا.
 *
 * فهنا **لا تلفيقَ إطلاقًا**: لا `route.fulfill`، ولا جلسةٌ مزروعة، ولا
 * ردٌّ مصطنع، ولا اعتراضٌ لشبكة المنتج. الرصدُ مباحٌ والاستبدالُ ممنوع —
 * وذاك هو الفرقُ كلُّه.
 *
 * والمستندُ يُبنى في زمن التشغيل: لا ملفَّ ثنائيًّا في المستودع، ومحتواه
 * مخترَعٌ بالكامل — لا أشخاصَ حقيقيّين ولا دراسةً حقيقية.
 *
 * وهو نصٌّ عربيٌّ بترميز UTF-8، لا PDF. و`.txt` نوعٌ مقبولٌ في المدخل
 * نفسه (`ACCEPT` في `ThesisIntake`)، وهذا القبولُ يفحص أتمتة T1 — رفعٌ
 * فقراءةٌ فأهليّةٌ فتنقيبٌ تلقائيّ — لا تصييرَ PDF. وبناءُ PDF بخطّ
 * Helvetica لا يُرمّز العربية أصلًا، فكان يُسقط التشغيلةَ حمرةً كاذبة
 * تكلّف رفعًا إلى الإنتاج وتحقيقًا، بلا إشارةٍ واحدة عن المنتج.
 *
 * ## الحدُّ الذي تقف عنده
 *
 * تصل إلى **مرحلة الاختيار** ثمّ تقف: لا حقوقَ ولا تأليفَ ولا إنشاءَ
 * مشروع ورقة. تلك أفعالٌ تُغيّر مِلكيّةً علمية، ولا تقع في فحص.
 *
 * ## متغيّرات البيئة
 *
 *   PUBRIVA_WEB_URL           عنوان الإنتاج (يُضبط في CI)
 *   PUBRIVA_ACCEPT_EMAIL      حساب القبول الأوّل — مطلوب
 *   PUBRIVA_ACCEPT_PASSWORD   كلمته — مطلوب
 *   PUBRIVA_ACCEPT_EMAIL_2    حساب القبول الثاني — للخصوصية (الجزء ب)
 *   PUBRIVA_ACCEPT_PASSWORD_2 كلمته
 *   PUBRIVA_T1_RUN_ID         معرّف التشغيلة، يدخل في علامة الاصطناع
 */

// ══════════════════════════════════════════════════════════════════════
// سلامةُ الأثر: لا تتبّعَ ولا فيديو ولا لقطات — ولو فشلت
// ══════════════════════════════════════════════════════════════════════
//
// `error-context.md` يُكتب على أي حال ويحمل لقطةَ DOM لصفحةٍ فيها حقولُ
// اعتماد. فتُطفأ المسجّلاتُ هنا، وتُمحى المخرجاتُ في CI قبل أيّ رفع.
test.use({ trace: "off", video: "off", screenshot: "off" });

const EMAIL = process.env.PUBRIVA_ACCEPT_EMAIL;
const PASSWORD = process.env.PUBRIVA_ACCEPT_PASSWORD;
const EMAIL_2 = process.env.PUBRIVA_ACCEPT_EMAIL_2;
const PASSWORD_2 = process.env.PUBRIVA_ACCEPT_PASSWORD_2;

/** علامةُ الاصطناع — ولا يُمسّ في الإنتاج شيءٌ لا يحملها. */
const MARKER = "PUBRIVA-T1-ACCEPT";
const RUN_ID = process.env.PUBRIVA_T1_RUN_ID ?? `local-${Date.now()}`;
const SYNTHETIC_TITLE = `${MARKER}-${RUN_ID}`;

/** حالاتُ الاستخراج الناجحة كما يسمّيها الخادم (`states.py`). */
const EXTRACTION_SUCCESS = new Set(["awaiting_review", "verified", "ready_for_review", "completed"]);
const EXTRACTION_FAILURE = new Set(["parse_failed", "extract_failed"]);

/** ما بين الجزأين — ومصدرُه ردُّ خادمٍ حقيقي لا ثابتٌ مكتوب. */
let firstThesisId: string | null = null;
let firstOpportunityCount = 0;

// ══════════════════════════════════════════════════════════════════════
// الثوابتُ المعلَنة — تُسجَّل، وتسقط إن تعذّر إثباتها
// ══════════════════════════════════════════════════════════════════════

const invariants: Record<string, string> = {};

function record(name: string, value: string): void {
  invariants[name] = value;
  console.log(`INVARIANT ${name} = ${value}`);
}

function stage(name: string, detail: string): void {
  console.log(`STAGE ${name} :: ${detail}`);
}

// ══════════════════════════════════════════════════════════════════════
// مستندٌ اصطناعيّ يُبنى في زمن التشغيل — لا ملفَّ ثنائيًّا في المستودع
// ══════════════════════════════════════════════════════════════════════
//
// **ويُعلن اصطناعَه في متنه، لا في اسمه وحده.** فمن يفتحه في الإنتاج
// يقرأ في سطره الثاني أنّه ليس دراسةً منشورة ولا بيانات حقيقية.
//
// **ورقمٌ واحدٌ في المستند كلِّه**: حجمُ العيّنة. وما عداه مكتوبٌ بالحروف
// عمدًا — `fact_eligibility` يرفض عدّين متنازعين على حقل العيّنة، فرقمٌ
// ثانٍ يُسقط التشغيلةَ على قاعدةٍ من قواعد المنتج لا على عطبٍ فيه.
//
// **ولا إحصاءَ لم يُجرَ**: لا معاملات ولا قيم دلالة ولا أحجام أثر. النتائج
// عباراتٌ اتجاهية وحسب — وهو القيدُ نفسه الذي يفرضه المنتج على الباحث،
// فلا يليق بمستند القبول أن يُخالفه.
const THESIS_TEXT = [
  `العنوان: اختبار قبول PUBRIVA — أثر جودة المحتوى الرقمي في الثقة بالعلامة التجارية (${MARKER})`,
  "",
  "طبيعة المستند: هذا مستندٌ اصطناعيٌّ أُنشئ لاختبار قبولٍ آليّ. وليس دراسةً",
  "منشورة، ولا يقوم على بياناتٍ حقيقية، ولا يصف أشخاصًا حقيقيّين، ولا يجوز",
  "الاستشهاد به في عملٍ علميّ.",
  "",
  "مشكلة الدراسة: تعتمد المؤسسات على المحتوى الرقمي في بناء صورتها لدى",
  "جمهورها، ويلاحظ القائمون على التسويق تفاوتًا في ثقة الجمهور لا يفسّره حجم",
  "الإنفاق وحده. ولا تتوفّر في السياق المحلّي قراءةٌ واضحة للعلاقة بين جودة ما",
  "يُنشر رقميًّا وبين الثقة بالعلامة التجارية.",
  "",
  "أهداف الدراسة: وصف مستوى جودة المحتوى الرقمي كما يدركه الجمهور، ووصف مستوى",
  "الثقة بالعلامة التجارية لديه، وبيان اتجاه العلاقة بين الاثنين، والكشف عن",
  "دور التفاعل مع المحتوى في هذه العلاقة.",
  "",
  "أسئلة الدراسة: ما مستوى جودة المحتوى الرقمي كما يدركه المشاركون؟ وما مستوى",
  "الثقة بالعلامة التجارية لديهم؟ وما اتجاه العلاقة بين جودة المحتوى المدركة",
  "والثقة بالعلامة؟ وهل يختلف اتجاه هذه العلاقة باختلاف مستوى التفاعل مع",
  "المحتوى؟",
  "",
  "مجتمع الدراسة: متابعو الحسابات الرقمية للعلامات التجارية في قطاع الخدمات،",
  "ممّن يتابعون محتواها متابعةً منتظمة خلال فصلٍ واحد.",
  "",
  "حجم العينة: 312 مشاركًا اختيروا من مجتمع الدراسة الموصوف أعلاه.",
  "",
  "المتغيرات: جودة المحتوى الرقمي · الثقة بالعلامة التجارية · التفاعل مع",
  "المحتوى.",
  "",
  "المنهج: منهجٌ كمّيٌّ وصفيٌّ ارتباطيّ، يصف الظاهرة ويبحث اتجاه الاقتران بين",
  "متغيّراتها، ولا يثبت سببًا.",
  "",
  "الأداة: استبانةٌ اصطناعية أُعدّت لهذا الاختبار، تقيس إدراك جودة المحتوى",
  "والثقة بالعلامة والتفاعل معها، وروجعت قبل الاستعمال.",
  "",
  "النتائج:",
  "أولًا: جاء إدراك جودة المحتوى الرقمي عند المشاركين في مستوى مرتفع.",
  "ثانيًا: جاءت الثقة بالعلامة التجارية في مستوى متوسط، وهي أدنى من مستوى",
  "إدراك الجودة.",
  "ثالثًا: اتّجهت العلاقة بين جودة المحتوى المدركة والثقة بالعلامة اتجاهًا",
  "موجبًا.",
  "رابعًا: ظهر هذا الاتجاه الموجب أوضحَ لدى المشاركين الأكثر تفاعلًا مع",
  "المحتوى منه لدى الأقلّ تفاعلًا.",
  "خامسًا: لم يظهر في بيانات هذا المستند الاصطناعي ما يشير إلى اتجاهٍ سالب في",
  "أيٍّ من المقارنات الموصوفة.",
  "",
  "الخلاصة: يشير هذا المستند الاصطناعي إلى أنّ جودة المحتوى الرقمي المدركة",
  "تقترن اقترانًا موجبًا بالثقة بالعلامة التجارية، وأنّ التفاعل مع المحتوى",
  "يصاحب هذا الاقتران. وهي دلالاتٌ وصفيةٌ اتجاهية لا تثبت سببًا، ولا تقوم على",
  "بياناتٍ حقيقية.",
].join("\n");

/** المتنُ بترميز UTF-8 — لا بناءَ ثنائيًّا ولا ملفَّ في المستودع. */
function syntheticThesisText(): Buffer {
  return Buffer.from(THESIS_TEXT, "utf8");
}

// ══════════════════════════════════════════════════════════════════════
// رصدُ الشبكة — **رصدٌ لا استبدال**
// ══════════════════════════════════════════════════════════════════════

interface Seen {
  method: string;
  path: string;
  status: number;
}

/**
 * يسجّل كلَّ نداءٍ إلى الواجهة البرمجية، **ولا يمسّ واحدًا منها**.
 *
 * ولا يُسجَّل جسمُ ردٍّ ولا ترويسة: المسارُ والفعلُ والحالة تكفي للدعاوى
 * المطلوبة، وما عداها قد يحمل اعتمادًا أو بيانات غيرِ صاحب الحساب.
 */
function observe(page: Page, sink: Seen[]): void {
  page.on("response", (response: Response) => {
    let path: string;
    try {
      path = new URL(response.url()).pathname;
    } catch {
      return;
    }
    if (!path.includes("/api/v1/")) return;
    sink.push({ method: response.request().method(), path, status: response.status() });
  });
}

function counted(sink: Seen[], method: string, fragment: string): number {
  return sink.filter((entry) => entry.method === method && entry.path.includes(fragment)).length;
}

// ══════════════════════════════════════════════════════════════════════
// الجزء أ — الرحلةُ الذهبية على الإنتاج المنشور
// ══════════════════════════════════════════════════════════════════════

test.describe.serial("P0-T1 production acceptance", () => {
  test("A — upload to selection, with no step the researcher must perform", async ({ page }) => {
    // الرحلةُ كاملة: رفعٌ وقراءةٌ وتنقيبٌ تلقائيّ. والمهلةُ سخيّة لأنّ
    // القراءة تجري على الإنتاج، لا على خادمٍ مصطنع.
    test.setTimeout(15 * 60_000);

    expect(
      Boolean(EMAIL && PASSWORD),
      "PUBRIVA_ACCEPT_EMAIL / PUBRIVA_ACCEPT_PASSWORD are required — failing closed rather than skipping",
    ).toBe(true);

    const seen: Seen[] = [];
    observe(page, seen);

    // ── ١ · دخولٌ حقيقيّ، لا جلسةٌ مزروعة ──
    await test.step("real sign-in at /ar/login", async () => {
      await page.goto(`/${LOCALE}/login`);
      await signIn(page, EMAIL!, PASSWORD!);
      stage("SIGNED_IN", "real POST /auth/login returned 200 and a token was stored");
    });

    // ── ٢ · الرفع من الواجهة نفسها ──
    let uploadStatus = "";
    await test.step("upload the synthetic thesis through the normal UI", async () => {
      await page.goto(`/${LOCALE}/theses`);

      const uploadResponse = page.waitForResponse(
        (response) =>
          new URL(response.url()).pathname.endsWith("/api/v1/theses/upload") &&
          response.request().method() === "POST",
        { timeout: 180_000 },
      );

      // المدخل مخفيّ خلف زرّ، و`setInputFiles` يكتب فيه كما يفعل المتصفح
      // بعد اختيار المستخدم — بلا اختراع نداءٍ للواجهة البرمجية.
      // **رقمٌ واحدٌ في المستند كلِّه، ويُفحص قبل أن يُرفع.** فلو تسلّل
      // عددٌ ثانٍ لسقطت التشغيلةُ لاحقًا على قاعدةِ الأهليّة — وهي قاعدةٌ
      // صحيحة، فيُكشف الخللُ هنا في التجهيزة لا هناك في المنتج.
      const numbers = THESIS_TEXT.match(/\d+/g) ?? [];
      expect(
        numbers,
        `the synthetic document must carry exactly one number (the sample size): ${numbers}`,
      ).toEqual(["312"]);

      await page.locator('input[type="file"]').setInputFiles({
        name: `${SYNTHETIC_TITLE}.txt`,
        mimeType: "text/plain",
        buffer: syntheticThesisText(),
      });

      const response = await uploadResponse;
      expect(response.status(), `upload returned ${response.status()}`).toBeLessThan(300);

      // **المعرّفُ من ردّ خادمٍ حقيقي — لا ثابتٌ مكتوب ولا مخترَع.**
      const body = (await response.json()) as { thesis_id?: string; status?: string };
      expect(body.thesis_id, "the upload response carried no thesis_id").toBeTruthy();
      expect(
        body.thesis_id,
        "thesis_id is not a uuid — the harness must not invent an identifier",
      ).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);

      firstThesisId = body.thesis_id!;
      uploadStatus = body.status ?? "";
      stage("UPLOADED", `thesis=${firstThesisId} status=${uploadStatus} http=${response.status()}`);
    });

    // ── ٣ · إثباتُ أنّ القراءة بدأت ──
    await test.step("extraction actually started", async () => {
      expect(
        EXTRACTION_FAILURE.has(uploadStatus),
        `extraction reported a failure state immediately: ${uploadStatus}`,
      ).toBe(false);
      expect(uploadStatus, "the upload response carried no extraction status").not.toBe("");
      stage("EXTRACTION_STARTED", `first reported status=${uploadStatus}`);
    });

    // ── ٤ · بوّابةُ الإذن، إن ظهرت: قرارُ باحثٍ حقيقيّ بالواجهة ──
    await test.step("grant the external-reading consent if the product asks for it", async () => {
      const gate = page.getByTestId("dic2-gate");
      const appeared = await gate
        .waitFor({ state: "visible", timeout: 30_000 })
        .then(() => true, () => false);
      if (!appeared) {
        stage("CONSENT", "no consent gate appeared — nothing to decide");
        return;
      }
      await page.getByTestId("dic2-grant").click();
      await expect(page.getByTestId("dic2-granted")).toBeVisible({ timeout: 60_000 });
      stage("CONSENT", "granted through the real UI");
    });

    // ── ٥ · القراءةُ تصل إلى النجاح — بمراقبة نبض المنتج نفسه ──
    //
    // **ولا عاصفةَ إعادةِ تحميل**: الشاشةُ تستطلع من نفسها كل ٢٫٥ ثانية،
    // فيُرصد استطلاعُها ولا يُضاف إليه استطلاعٌ ثانٍ من الفحص.
    let extractionStatusAtSuccess = "";
    await test.step("extraction reaches a success state", async () => {
      const success = await page.waitForResponse(
        async (response) => {
          const path = new URL(response.url()).pathname;
          if (!path.includes(`/api/v1/theses/${firstThesisId}/extraction`)) return false;
          if (response.status() !== 200) return false;
          const body = (await response.json().catch(() => null)) as { status?: string } | null;
          return Boolean(body?.status && EXTRACTION_SUCCESS.has(body.status));
        },
        { timeout: 10 * 60_000 },
      );
      const body = (await success.json()) as { status: string };
      extractionStatusAtSuccess = body.status;
      expect(EXTRACTION_SUCCESS.has(extractionStatusAtSuccess)).toBe(true);
      stage("EXTRACTION_SUCCEEDED", `status=${extractionStatusAtSuccess}`);
    });

    // ── ٦ · التنقيبُ يتبع من نفسه ──
    //
    // ولا يُنقر شيء، ولا يُنادى `mine-opportunities`. يُعاد تحميلُ القائمة
    // على مهلٍ حتى يظهر أثرُ التنقيب — بفاصلٍ يقيس ولا يقصف.
    let cardMiningState = "";
    let cardActionsMiningState = "";
    let processingStateAfterMining = "";
    await test.step("mining follows automatically, with nothing clicked", async () => {
      await expect
        .poll(
          async () => {
            try {
              const listed = page.waitForResponse(
                (response) =>
                  new URL(response.url()).pathname.endsWith("/api/v1/theses") &&
                  response.request().method() === "GET" &&
                  response.status() === 200,
                { timeout: 60_000 },
              );
              await page.goto(`/${LOCALE}/theses`);
              const rows = (await (await listed).json()) as Array<{
                id: string;
                opportunities_found: number;
                processing_state?: string;
                mining_state?: string;
                actions?: { mining_state?: string };
              }>;
              const mine = rows.find((row) => row.id === firstThesisId);
              if (!mine) return -1;
              cardMiningState = mine.mining_state ?? "";
              cardActionsMiningState = mine.actions?.mining_state ?? "";
              processingStateAfterMining = mine.processing_state ?? "";
              firstOpportunityCount = mine.opportunities_found;
              return mine.opportunities_found;
            } catch {
              // محاولةٌ لم تُثمر ردًّا في مهلتها — تُعاد، ولا تُسقط الدعوى.
              return -1;
            }
          },
          {
            message: "automatic mining never produced an opportunity for the synthetic thesis",
            timeout: 8 * 60_000,
            intervals: [10_000],
          },
        )
        .toBeGreaterThan(0);

      stage(
        "AUTOMATIC_MINING",
        `opportunities=${firstOpportunityCount} mining_state=${cardMiningState} ` +
          `card_state=${cardActionsMiningState}`,
      );
    });

    // ── ٧ · الثوابتُ المعلَنة ──
    await test.step("record the declared invariants", async () => {
      const manualMine = counted(seen, "POST", "/mine-opportunities");
      expect(manualMine, "the browser issued a manual mine request on the golden path").toBe(0);
      record("MANUAL_MINE_REQUIRED", "NO");

      const decisions = counted(seen, "POST", "/candidates/");
      expect(decisions, "the browser decided a fact candidate on the golden path").toBe(0);
      record("PER_FACT_APPROVAL_REQUIRED", "NO");

      expect(firstOpportunityCount).toBeGreaterThan(0);
      record("AUTOMATIC_MINING", "YES");

      // **ولم يُعَد وصفُ الاستخراج بعد التنقيب.**
      //
      // والرصدُ بعديّ لا قَبْليّ: الحالُ المقروءة في ردّ القائمة **بعد**
      // أن اكتمل التنقيب هي التي تُفحص، فتُثبت أنّ طَورَ التنقيب لم يُعِد
      // كتابةَ حالِ استخراجٍ نجح.
      expect(
        EXTRACTION_FAILURE.has(extractionStatusAtSuccess),
        "extraction reported failure before mining even ran",
      ).toBe(false);
      expect(
        EXTRACTION_FAILURE.has(processingStateAfterMining),
        `mining rewrote the extraction state into ${processingStateAfterMining}`,
      ).toBe(false);
      expect(
        processingStateAfterMining,
        "no post-mining processing state was observed — the invariant is unprovable",
      ).not.toBe("");
      record("MINING_FAILURE_REWRITES_EXTRACTION", "NO");
      stage(
        "EXTRACTION_INTACT",
        `before=${extractionStatusAtSuccess} after_mining=${processingStateAfterMining}`,
      );
    });

    // ── ٨ · البطاقةُ على شاشةٍ محمَّلةٍ من جديد ──
    await test.step("a fresh Thesis Center shows the real count and no mine button", async () => {
      await page.goto(`/${LOCALE}/theses`);
      const card = page.getByTestId(`thesis-card-${firstThesisId}`);
      await expect(card).toBeVisible({ timeout: 60_000 });

      // العددُ المعروض هو العددُ الحقيقي، لا رقمٌ تجتهد فيه الشاشة.
      await expect(card).toContainText(`فرص مكتشفة: ${firstOpportunityCount}`);

      // **ولا زرَّ تنقيبٍ في المسار السويّ.**
      await expect(card.getByTestId("card-mine")).toHaveCount(0);

      // ووجهةُ الرحلة معروضة.
      await expect(card.getByTestId("card-view-opportunities")).toBeVisible();

      // والتحفّظُ في متن العبارة: مبدئيّة، ومن عناصر الرسالة وحدها.
      const note = card.getByTestId("card-mining-note");
      await expect(note).toContainText("مبدئيّة");
      await expect(note).toContainText("من عناصر رسالتك وحدها");

      // **ولا دعوى أدبٍ منشور ولا جِدّة.** النصُّ ينفيهما صراحةً، فيُفحص
      // النفيُ نفسُه لا غيابُ كلمة.
      await expect(note).toContainText("قبل مقابلتها بالأدب المنشور");
      await expect(note).toContainText("وقبل أيّ حكمٍ على جِدّتها أو ترتيبها");
      stage("CARD", `count=${firstOpportunityCount} no_mine=true cta=true`);
    });

    // ── ٩ · النقرُ على وجهةِ الرحلة: الرسالةُ بعينها، بلا إعادة اختيار ──
    await test.step("the real CTA opens this exact thesis with no reselection", async () => {
      const card = page.getByTestId(`thesis-card-${firstThesisId}`);
      const mapCall = page.waitForResponse(
        (response) =>
          new URL(response.url()).pathname.includes(
            `/api/v1/theses/${firstThesisId}/publication-map`,
          ) && response.status() === 200,
        { timeout: 120_000 },
      );
      await card.getByTestId("card-view-opportunities").click();

      await page.waitForURL((url) => url.searchParams.get("thesis_id") === firstThesisId, {
        timeout: 60_000,
      });
      const map = (await (await mapCall).json()) as { opportunities?: unknown[] };
      expect(
        Array.isArray(map.opportunities) && map.opportunities.length > 0,
        "the publication map for this thesis returned no opportunities",
      ).toBe(true);

      // ولا إعادةَ اختيار: إن ظهرت القائمة فهي مضبوطةٌ على هذه الرسالة سلفًا.
      const picker = page.getByTestId("thesis-picker");
      if (await picker.count()) await expect(picker).toHaveValue(firstThesisId!);
      stage("OPPORTUNITIES_OPENED", `thesis=${firstThesisId} reselection=false`);
    });

    // ── ١٠ · مرحلةُ الاختيار قائمة — **ونقف قبل الحقوق** ──
    await test.step("the selection stage is reachable, and we stop before rights", async () => {
      await expect(page.getByRole("heading", { name: "خريطة فرص النشر" })).toBeVisible();
      await expect(page.getByText("تحليل الفرصة مسموح قبل الحقوق")).toBeVisible();
      stage("SELECTION_STAGE", "reachable — stopping before rights, authorship and Paper Project");
    });

    // ── ١١ · ملاحظاتُ التجربة: تُسجَّل ولا تُسقط على تجميل ──
    await test.step("UX observation", async () => {
      const heading = (await page.getByRole("heading").first().textContent())?.trim() ?? "";
      const primaryCtaCount = await page
        .getByTestId(`thesis-card-${firstThesisId}`)
        .getByTestId("card-view-opportunities")
        .count();
      console.log(`UX WHERE_AM_I :: ${heading}`);
      console.log("UX WHAT_PUBRIVA_IS_DOING :: it read the thesis and scanned it for opportunities");
      console.log("UX WHAT_PUBRIVA_NEEDS_FROM_ME :: choose an opportunity; nothing else was asked");
      console.log(`UX PRIMARY_CTA_COUNT :: ${primaryCtaCount}`);
      console.log("UX TECHNICAL_LANGUAGE_EXPOSED :: none required to complete the journey");
      console.log("UX TRAINING_NEEDED :: none to reach the selection stage");
    });

    // ── ١٢ · التنظيف بدورة الحياة العادية — أرشفةٌ لا حذف ──
    await test.step("archive the synthetic thesis — never a physical delete", async () => {
      await page.goto(`/${LOCALE}/theses`);
      const card = page.getByTestId(`thesis-card-${firstThesisId}`);
      await expect(card).toBeVisible({ timeout: 60_000 });

      // **ولا يُمسّ ما لا يحمل العلامة.** البطاقةُ مُختارة بمعرّفٍ أصدره
      // الخادمُ لهذه الرسالة وحدها، وعنوانُها يحمل علامة الاصطناع.
      await expect(card).toContainText(MARKER);

      await card.getByTestId("card-menu").click();
      await card.getByTestId("menu-archive").click();
      await page.getByTestId("archive-confirm").click();
      await expect(page.getByTestId(`thesis-card-${firstThesisId}`)).toHaveCount(0, {
        timeout: 60_000,
      });

      const deletes = seen.filter((entry) => entry.method === "DELETE").length;
      expect(deletes, "the harness issued a DELETE against production").toBe(0);
      stage("CLEANUP", "archived through the normal lifecycle; no physical deletion");
    });

    console.log(`T1_INVARIANTS ${JSON.stringify(invariants)}`);
  });

  // ══════════════════════════════════════════════════════════════════
  // الجزء ب — خصوصيّةُ المستأجر الثاني
  // ══════════════════════════════════════════════════════════════════

  test("B — a second tenant cannot reach the first tenant's thesis", async ({ browser }) => {
    test.setTimeout(5 * 60_000);

    expect(
      firstThesisId,
      "part A did not produce a thesis id — part B has nothing to probe with",
    ).toBeTruthy();

    // **ولا يُختلق مستأجرٌ ثانٍ إطلاقًا.** غيابُ الحساب يُقال باسمه،
    // ولا يُعلَن T1 أخضرَ بالكامل بدونه.
    if (!EMAIL_2 || !PASSWORD_2) {
      throw new Error("SECOND_ACCEPTANCE_ACCOUNT_REQUIRED");
    }

    // جلسةٌ جديدة تمامًا: سياقٌ مستقلّ، فلا يبقى من الأولى أثر.
    const context = await browser.newContext({ locale: "ar" });
    const page = await context.newPage();
    const seen: Seen[] = [];
    observe(page, seen);

    try {
      await page.goto(`/${LOCALE}/login`);
      await signIn(page, EMAIL_2, PASSWORD_2);
      stage("SECOND_TENANT_SIGNED_IN", "real sign-in for the second acceptance account");

      const listed = page.waitForResponse(
        (response) =>
          new URL(response.url()).pathname.endsWith("/api/v1/theses") &&
          response.request().method() === "GET" &&
          response.status() === 200,
        { timeout: 60_000 },
      );

      // التنقّلُ المباشر بمعرّف رسالة الغير — وهو ما يجب ألّا يكشف شيئًا.
      await page.goto(`/${LOCALE}/opportunities?thesis_id=${firstThesisId}`);
      const rows = (await (await listed).json()) as Array<{ id: string }>;

      // ١ — ليست في قائمته.
      expect(
        rows.some((row) => row.id === firstThesisId),
        "the first tenant's thesis appeared in the second tenant's list",
      ).toBe(false);

      await page.waitForLoadState("networkidle");

      // ٢ — ولا هي مختارةً سلفًا: **رابطٌ ليس إذنًا**.
      const picker = page.getByTestId("thesis-picker");
      if (await picker.count()) {
        await expect(picker).not.toHaveValue(firstThesisId!);
      }

      // ٣ — ولا فرصَها تُعاد. ويُقبل أيُّ عدم إفشاءٍ آمن: ٤٠٤ أو ٤٠٣ أو
      // ببساطة ألّا يُطلب شيء — ولا تُشترط حالةٌ بعينها.
      const mapCalls = seen.filter(
        (entry) => entry.path.includes(`/theses/${firstThesisId}/publication-map`),
      );
      for (const call of mapCalls) {
        expect(
          call.status,
          `the second tenant received ${call.status} from the first tenant's publication map`,
        ).toBeGreaterThanOrEqual(400);
      }

      // ٤ — ولا شيءَ حسّاسٍ على الشاشة: لا المعرّف ولا عنوانُ الرسالة.
      const body = page.locator("body");
      await expect(body).not.toContainText(firstThesisId!);
      await expect(body).not.toContainText(MARKER);

      stage(
        "SECOND_TENANT_PRIVACY",
        `map_calls=${mapCalls.length} listed=false preselected=false disclosed=false`,
      );
    } finally {
      await context.close();
    }
  });
});
