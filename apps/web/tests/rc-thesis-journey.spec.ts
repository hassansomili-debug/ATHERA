import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import {
  expect, test,
  type APIRequestContext, type APIResponse, type Locator, type Page,
} from "@playwright/test";

/**
 * رحلةُ المرشَّح للإصدار | The release-candidate journey (Wave 1).
 *
 * **وهذه الرقعةُ وحدها لا تعترض الشبكة — وذلك سببُ وجودها.**
 *
 * كلُّ رقعةٍ أخرى في هذا المجلّد تزرع جلسةً وتعترض `**\/api/v1/**`، فتفحص
 * الواجهةَ وحدها أمام خادمٍ متخيَّل. وهي فحوصٌ صحيحة، لكنّها عمياءُ عن
 * صنفٍ كامل من الأعطاب: تلك التي تسكن **الوصلة** بين الواجهة والخادم —
 * أصلٌ لا تسمح به CORS، أو عقدٌ تغيّر في طرفٍ ولم يتغيّر في الآخر، أو
 * قاعدةٌ عند ترحيلٍ أقدم مما تطلبه الشاشة.
 *
 * وهذا بعينه ما أبلغ عنه المالك: على `/en/theses` جملةُ «Could not load
 * the data.» وفي الشريط «Sign in» في اللحظة نفسها. والنظر في الشيفرة
 * يقول شيئًا محدَّدًا جدًّا:
 *
 *     setError(err instanceof AtheraApiError ? err.localized(locale)
 *                                            : t("common.loadFailed"))
 *
 * فـ`apiFetch` يلفّ **كلَّ** ردٍّ غيرِ ناجح في `AtheraApiError` — 401 و404
 * و422 و500 سواء. فجملةُ «Could not load the data.» **لا تُعرض على ردٍّ
 * من الخادم إطلاقًا**؛ لا تُعرض إلّا حين لا يصل ردٌّ أصلًا: `fetch` نفسه
 * يُرفَض. وذلك حاجزُ شبكةٍ أو CORS أو CSP، لا عطبٌ في منطق الشاشة.
 *
 * فالمهمّة هنا أن تُقام الطبقتان معًا — واجهةُ الموجة الأولى أمام API
 * الموجة الأولى وقاعدةٍ عند 0028 — ويُسأل: **أتُنتج هذه التوليفةُ العَرَض
 * أم لا؟** فإن لم تُنتجه فالعطبُ ليس في المنتج، بل في اقتران معاينةٍ من
 * الموجة الأولى بخادمٍ ليس منها.
 *
 * ── الاثنتا عشرة دعوى ─────────────────────────────────────────────────
 *
 *   ١ تسجيلُ حسابٍ اصطناعي ثمّ دخولٌ به — بالنموذج، لا بحقنِ رمز.
 *   ٢ `/en/theses` تُحمَّل، و«Could not load the data.» غائبة.
 *   ٣ الجلسةُ متّسقة: لا صفحةٌ محميّة تعرض «Sign in» ومحتوى داخلٍ معًا.
 *   ٤ رفعُ مستندٍ تبنيه الرقعةُ بنفسها، و`POST /api/v1/theses/upload` ينجح.
 *   ٥ البطاقةُ تحمل اسمَ الملفّ حين لا عنوانَ مستخرَج — وتقول إنّه اسمُ ملفّ.
 *   ٦ الحالُ تصمد عبر إعادة التحميل — فهي في القاعدة لا في الذاكرة.
 *   ٧ الحالُ صادقة: الفشل يُرى مختلفًا عن الفراغ، ولا «٠» بلا سبب.
 *   ٨ إعادةُ المحاولة تُعرض حيث تجوز، وتُردّ ٤٠٩ حيث لا تجوز.
 *   ٩ `/ar/theses` تُصيَّر من اليمين إلى اليسار.
 *  ١٠ حالُ الجلسة واحدةٌ بالعربية والإنجليزية.
 *  ١١ لا ٥٠٠ في الرحلة كلّها — لا من الوِب ولا من الـAPI.
 *  ١٢ ولا تسرّب: حسابٌ ثانٍ لا يرى رسالةَ الأوّل، ولا رسالةٌ تعدّ لجارتها.
 *
 * ── العزل والاعتماد ───────────────────────────────────────────────────
 *
 * **لا اعتمادَ حقيقيًّا هنا بحال.** لا تُقرأ `PUBRIVA_ACCEPT_*` ولا أيُّ
 * سرّ. الحسابان يُنشآن في هذه التشغيلة على `example.com` ببادئةٍ مسجّلة
 * في `athera_api.synthetic` (`pubriva-rc`)، وكلمتُهما ثابتةُ CI معلَنة،
 * والقاعدةُ خدمةٌ في المهمّة تموت بموتها.
 */

// ── العناوين: الوِب والـAPI أصلان مختلفان، وذلك مقصود ────────────────────
//
// **وهو الشرطُ الذي يجعل هذه الرحلة تفحص CORS فعلًا.** لو خُدم الاثنان من
// أصلٍ واحد لمرّ كلُّ شيء ولو كانت القائمة فارغة، ولَما فحصت الرحلةُ
// الوصلةَ التي انكسرت في المعاينة.
const APP_ORIGIN = new URL(process.env.PUBRIVA_WEB_URL ?? "http://127.0.0.1:3000").origin;
const API_ORIGIN = new URL(
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000").origin;

const EN = "en";
const AR = "ar";

/** النصُّ الذي أبلغ عنه المالك — بحرفه من `messages/*.json`. */
const LOAD_FAILED_EN = "Could not load the data.";
const LOAD_FAILED_AR = "تعذّر تحميل البيانات.";

const SIGN_IN_EN = "Sign in";
const SIGN_IN_AR = "تسجيل الدخول";
const SIGN_OUT_EN = "Sign out";
const SIGN_OUT_AR = "تسجيل الخروج";

const THESES_TITLE_EN = "Thesis library";
const THESES_TITLE_AR = "مكتبة الرسائل";

/** ما يقوله الخادم حين يُعرض اسمُ ملفٍّ لا عنوانًا (`theses.identifiedByFilename`). */
const BY_FILENAME_EN = "Title not extracted yet · shown by file name";

/** حالاتٌ مستقرّة — عندها يتوقّف العمل، فتصحّ المقارنة عبر إعادة التحميل. */
const TERMINAL_STATE_LABELS_EN = [
  "File uploaded", "Awaiting your approval", "Ready for review",
  "Analysis complete", "Analysis failed", "The document has no text layer",
];

/** حالاتٌ يجري فيها عملٌ الآن — لا يُقاس عليها استقرار. */
const IN_FLIGHT_STATE_LABELS_EN = [
  "Queued", "Reading the document", "Extracting the thesis structure",
];

// ── فعلُ القراءة الذي **توجبه** الحال ──────────────────────────────────
//
// **وثلاثةُ أفعالٍ لا واحد**، ولكلٍّ حالُه (Wave 1.1، §A):
//
//   • «Read the thesis» — رُفع الملفّ ولم تبدأ قراءتُه بعد. وأوّلُ قراءةٍ
//     ليست إعادةً؛ وتسميتُها «أعد المحاولة» تجعل الباحث يظنّ أنّه أضاع شيئًا.
//   • «Read it again» — قُرئ المستند وانتهى بلا فشل، فالقراءةُ الثانية
//     إعادةُ قراءةٍ لا إصلاحُ عطب.
//   • «Try again» — **سقطت القراءة وللسقوط سبب مسمّى**، فيُعرض إصلاحُها.
//
// وكانت هذه الدعوى تطلب «Try again» على المستند النصّي أيًّا كانت حاله —
// فمرّت حين كان الزرّ واحدًا لكلّ الحالات، وسقطت حين صار لكلّ حالٍ فعلُها.
// **ولا تُصلَح بتبديل السلسلة ولا بتعبيرٍ يقبل الاثنين**: كلاهما يُبطل ما
// جاءت تفحصه. فتُسأل الحالُ أوّلًا، ثمّ يُطلب الفعلُ الذي توجبه هي.
const FIRST_READ_EN = "Read the thesis";
const REREAD_EN = "Read it again";
const RETRY_EN = "Try again";
const READ_ACTIONS_EN = [FIRST_READ_EN, REREAD_EN, RETRY_EN] as const;

/** `null` = **لا فعلَ قراءةٍ على هذه الحال**، ويقوم مقامَه سببٌ مكتوب. */
const READ_ACTION_FOR_STATE_EN: Record<string, string | null> = {
  "File uploaded": FIRST_READ_EN,
  "Awaiting your approval": REREAD_EN,
  "Ready for review": REREAD_EN,
  "Analysis complete": REREAD_EN,
  "Analysis failed": RETRY_EN,
  // لا OCR بعد، وإعادةُ القراءة تُنتج النتيجة نفسها حرفًا بحرف.
  "The document has no text layer": null,
};

/**
 * يفحص أنّ البطاقة تعرض **الفعل الذي توجبه حالُها وحده**.
 *
 * والنصفُ الثاني هو الذي يحمل الوزن: الفعلان الآخران **غائبان**. فحصٌ يطلب
 * الحاضرَ ولا ينفي غيره يمرّ على بطاقةٍ تعرض الثلاثة معًا.
 */
async function expectReadAction(card: Locator, state: string): Promise<string | null> {
  expect(Object.keys(READ_ACTION_FOR_STATE_EN),
         `حالٌ لا يعرفها جدولُ الأفعال — الدعوى تفحص شيئًا لم يُقصد: ${state}`)
    .toContain(state);
  const expected = READ_ACTION_FOR_STATE_EN[state]!;
  for (const label of READ_ACTIONS_EN) {
    const control = card.getByRole("button", { name: label, exact: true });
    if (label === expected) {
      await expect(control, `الحال «${state}» توجب «${label}» ولا زرَّ به`).toBeVisible();
    } else {
      await expect(control, `الحال «${state}» تعرض «${label}» وهو ليس فعلَها`)
        .toHaveCount(0);
    }
  }
  return expected;
}

// ── الحسابان الاصطناعيّان ─────────────────────────────────────────────
//
// البادئة `pubriva-rc` مسجّلة في `athera_api.synthetic`، والنطاق
// `example.com` محجوز. وحارسُ `test_the_browser_journey_uses_the_registered_marker`
// يقرأ هذا السطر ويقابله بالسجلّ — فلا تفترق علامةٌ عن مصدرها.
/**
 * **حالةُ الرحلة تعيش في ملفّ لا في ذاكرة العامل.**
 *
 * وهذا ليس زخرفًا: Playwright **يُنهي عمليّةَ العامل بعد كلّ فشل** ويبدأ
 * أخرى نظيفة. فأوّلُ صياغةٍ هنا احتفظت بالرموز وبعدّادات الأخطاء في
 * متغيّراتٍ على مستوى الوحدة — فلمّا سقط الرفع أُعيد تحميل الوحدة، فصارت
 * الجلسات `null` فسقطت دعاوى لا علاقة لها بالرفع، **و — وهو الأسوأ —
 * فرغت قائمةُ الـ٥٠٠ فأخضرّت الدعوى ١١ على خمسمئةٍ وقعت في التشغيلة
 * نفسها.** حارسٌ يُصفَّر بالفشل الذي جاء ليحرس منه ليس حارسًا.
 *
 * والملفّ في مجلّد النظام المؤقّت لا في `test-results`: مخرجاتُ الرقعة
 * تُرفع عند الفشل، ولا داعيَ لأن يُرفع معها رمزُ جلسةٍ ولو كان اصطناعيًّا.
 */
//
// واسمُ الملفّ يحمل رقمَ التشغيلة حيث يوجد: تشغيلتان على آلةٍ واحدة لا
// ترثان جلساتِ بعضهما، فتحاول الثانيةُ تسجيلَ بريدٍ مسجَّل وتسقط بلا سبب.
const STATE_PATH = join(
  tmpdir(), `pubriva-rc-journey-${process.env.GITHUB_RUN_ID ?? "local"}.json`);

interface JourneyState {
  stamp: string;
  born: number;
  a: Session | null;
  b: Session | null;
  theses: Record<string, string>;
  serverErrors: string[];
  pageErrors: string[];
  requestFailures: string[];
}

/** حالةٌ من تشغيلةٍ قديمة لا تُورَّث — ساعةٌ حدٌّ كافٍ، وCI عذراءُ أصلًا. */
const STALE_AFTER_MS = 60 * 60 * 1000;

function readState(): JourneyState | null {
  try {
    if (!existsSync(STATE_PATH)) return null;
    const parsed = JSON.parse(readFileSync(STATE_PATH, "utf8")) as JourneyState;
    if (!parsed?.stamp || Date.now() - parsed.born > STALE_AFTER_MS) return null;
    return parsed;
  } catch {
    return null;
  }
}

const RESTORED = readState();

const STAMP = RESTORED?.stamp ?? `${Date.now()}-${Math.floor(Math.random() * 1e6)}`;

/**
 * الخاتمةُ تحمل تمييزَ الحساب، **والبادئةُ تبقى بادئةَ السجلّ**.
 *
 * أوّلُ صياغةٍ هنا كتبت `pubriva-rc-a-${STAMP}` — فصارت البادئة المقروءة
 * `pubriva-rc-a`، وهي ليست في السجلّ. وأسقط الحارسُ البناء وكان محقًّا:
 * صفٌّ بهذه العلامة لا يتعرّف عليه أيُّ تقرير تنظيف. فالتمييز في الخاتمة.
 */
const stampFor = (who: string) => `${STAMP}-${who}`;
const ACCOUNT_A = `pubriva-rc-${stampFor("a")}@example.com`;
const ACCOUNT_B = `pubriva-rc-${stampFor("b")}@example.com`;

/** كلمةُ CI معلَنة — لا سرَّ لها، والقاعدةُ تموت مع المهمّة. */
const CI_PASSWORD = "rc-journey-ci-only-not-a-real-secret";

const TEXT_PDF_NAME = `rc-thesis-with-text-${STAMP}.pdf`;
const SCANNED_PDF_NAME = `rc-thesis-scanned-${STAMP}.pdf`;
/** **مسبارٌ خارج المتصفّح — واسمُه خاصٌّ به.**
 *
 * أُضيف حين كان الرفع يردّ ٥٠٠: خمسمئةٌ من خارج `CORSMiddleware` تصل
 * المتصفّحَ بلا ترويسة أصل، فيحجبها ولا يرى JS رمزًا. ولمّا صحّ الرفع
 * صار المسبارُ يُنشئ رسالةً حقيقيّة — فازدوجت البطاقةُ باسمٍ واحد،
 * وصارت الرسائلُ أربعًا وهي تُعدّ ثلاثًا. فله اسمُه، ويُعدّ معها. */
const PROBE_PDF_NAME = `rc-thesis-probe-${STAMP}.pdf`;

/** بحثٌ مُسجَّلٌ يدويًّا بلا ملفّ — نظيرُ «الفراغ» في الدعوى السابعة. */
const MANUAL_TITLE_AR = `رسالةٌ مسجّلة يدويًّا ${STAMP}`;

// ══════════════════════════════════════════════════════════════════════
// حالةٌ مشتركة عبر الرحلة
// ══════════════════════════════════════════════════════════════════════
//
// **الإعادةُ مُطفأة**: إعادةُ رحلةٍ نصفُها وقع تُنتج فشلًا لا يصف شيئًا.
//
// و**التسلسلُ داخل المجموعات لا فوقها**. كلُّ مجموعةٍ متسلسلةٌ في ذاتها،
// فسقوطُ أولى دعاويها لا يُغرق ما بعدها بأخطاءٍ مشتقّة. أمّا بين المجموعات
// فلا تسلسل: عطبٌ في الرفع لا يجوز أن يُسكت الاتجاهَ ولا العزلَ ولا الجلسة
// — فيصير التقريرُ «واحدةٌ سقطت وثمانٍ مجهولة»، وذلك أسوأ من فشلٍ صريح.
test.describe.configure({ retries: 0 });

interface Session { access: string; refresh: string; expiry: string }

const sessions: Record<"a" | "b", Session | null> = {
  a: RESTORED?.a ?? null, b: RESTORED?.b ?? null,
};
/** معرّفاتُ الرسائل كما ردّها الخادم — تُقرأ من الـAPI لا تُخمَّن من الشاشة. */
const theses: Record<string, string> = RESTORED?.theses ?? {};

/**
 * كلُّ ردٍّ ≥٥٠٠ يُلتقط من **الأصلين معًا**، ويُحكم عليه في الدعوى ١١.
 *
 * ورقعاتُ السطح تراقب أصل الوِب وحده — يكفيها، فخادمُها متخيَّل. وهنا
 * الخادم حقيقي، ومراقبةُ أصله هي الغاية: خمسمئةٌ من الـAPI هي بالضبط ما
 * لا يظهر في أيّ فحصٍ آخر.
 */
const serverErrors: string[] = RESTORED?.serverErrors ?? [];
const pageErrors: string[] = RESTORED?.pageErrors ?? [];

/**
 * **وطلبٌ يُرفض على مستوى الشبكة لا يظهر ردًّا البتّة** — فيُلتقط وحده.
 *
 * وهذه ليست زيادةً احتياطية، بل الثقب الذي مرّ منه العَرَض المُبلَّغ عنه:
 * استثناءٌ غيرُ ملتقَط في نقطةٍ يردّ عليه Starlette بخمسمئة **من خارج
 * `CORSMiddleware`**، فتخرج الاستجابة بلا `Access-Control-Allow-Origin`،
 * فيحجبها المتصفّح. ولا يرى JS رمزًا ولا يرى `page.on("response")` ردًّا:
 * يُرفض `fetch` نفسه، فتقول الشاشة «Could not load the data.» — وهي
 * الجملةُ بعينها. فمراقبةُ الـ٥٠٠ وحدها كانت ستُخضِرّ هذه الدعوى على
 * خمسمئةٍ وقعت فعلًا.
 */
const requestFailures: string[] = RESTORED?.requestFailures ?? [];

function persist(): void {
  const state: JourneyState = {
    stamp: STAMP, born: RESTORED?.born ?? Date.now(),
    a: sessions.a, b: sessions.b, theses,
    serverErrors, pageErrors, requestFailures,
  };
  writeFileSync(STATE_PATH, JSON.stringify(state), "utf8");
}

/**
 * ردٌّ جاء من خارج المتصفّح — **ويُحسب في الدعوى ١١ كما يُحسب ما رآه**.
 *
 * فـ`APIRequestContext` لا يمرّ بـ`page.on("response")`؛ وخمسمئةٌ التقطها
 * سؤالٌ مباشر خمسمئةٌ وقعت على الخادم، ولا فرق.
 */
function note(response: APIResponse, what: string): APIResponse {
  if (response.status() >= 500) {
    serverErrors.push(`${response.status()} ${what} ${response.url()}`);
  }
  return response;
}

function watch(page: Page): void {
  page.on("pageerror", (error) => pageErrors.push(String(error)));
  page.on("response", (response) => {
    const origin = new URL(response.url()).origin;
    if (origin !== APP_ORIGIN && origin !== API_ORIGIN) return;
    if (response.status() >= 500) {
      serverErrors.push(`${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });
  page.on("requestfailed", (request) => {
    const origin = new URL(request.url()).origin;
    if (origin !== APP_ORIGIN && origin !== API_ORIGIN) return;
    // **واستباقُ Next المُجهَض ليس فشلًا.** يجلب الإطارُ مكوّنَ الخادم
    // مسبقًا (`?_rsc=`) ثمّ يُجهضه متى تنقّل المستخدم أو خرج الرابط من
    // النظر — فـ`ERR_ABORTED` عليه سلوكٌ لا عطب، ولا يراه الباحث.
    // ويبقى ما عداه محسوبًا: فشلُ CORS يصل `ERR_FAILED` لا `ERR_ABORTED`،
    // وهو بعينه ما يُنتج «Could not load the data.» — فلا يُبتلع.
    const aborted = request.failure()?.errorText === "net::ERR_ABORTED";
    if (aborted && request.url().includes("_rsc=")) return;
    requestFailures.push(
      `${request.method()} ${request.url()} — ${request.failure()?.errorText ?? "?"}`);
  });
}

test.beforeEach(async ({ page }) => {
  watch(page);
});

// **بعد كلّ دعوى، لا بعد الرحلة.** الحفظُ في النهاية وحدها يضيع بأوّل فشل
// — وهو الفشل الذي نريد أن نتذكّره.
test.afterEach(() => {
  persist();
});

// ══════════════════════════════════════════════════════════════════════
// مستنداتٌ تبنيها الرقعةُ بنفسها — لا ملفَّ ثابتًا في المستودع
// ══════════════════════════════════════════════════════════════════════
//
// **والبصمةُ تُفحص على الخادم**: `storage.validate_content` تشترط أن يبدأ
// المرفوع بـ`%PDF-`، فلا يمرّ نصٌّ يُسمّي نفسه PDF. فيُبنى مستندٌ صحيح
// البنية: كتالوجٌ وصفحةٌ وخطٌّ ومجرى محتوى، ومرجعٌ متقاطع بإزاحاتٍ محسوبة.
function buildPdf(contentStream: string): Buffer {
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] " +
      "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${contentStream.length} >>\nstream\n${contentStream}endstream`,
  ];
  let pdf = "%PDF-1.4\n";
  const offsets: number[] = [];
  objects.forEach((body, index) => {
    offsets.push(pdf.length);
    pdf += `${index + 1} 0 obj\n${body}\nendobj\n`;
  });
  const xref = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const offset of offsets) pdf += `${String(offset).padStart(10, "0")} 00000 n \n`;
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\n` +
         `startxref\n${xref}\n%%EOF\n`;
  return Buffer.from(pdf, "latin1");
}

/** مستندٌ فيه طبقةُ نصّ — `pypdf` يقرأ منه كلامًا. */
function pdfWithText(): Buffer {
  return buildPdf(
    "BT /F1 18 Tf 72 720 Td (PUBRIVA release-candidate synthetic thesis body) Tj ET\n");
}

/**
 * مستندٌ بلا طبقةِ نصّ — نظيرُ الرسالة الممسوحة ضوئيًّا.
 *
 * وهو الطرفُ الذي يُثبت الدعويين ٧ و٨: حالُ فشلٍ **مسمّاة** لا صفرٌ صامت،
 * وإعادةُ محاولةٍ **مرفوضة بـ٤٠٩** لأنّ إعادة قراءته تُنتج ما أنتجته.
 */
function pdfWithoutText(): Buffer {
  return buildPdf("q 0 0 0 rg 100 100 220 320 re f Q\n");
}

// ══════════════════════════════════════════════════════════════════════
// أدواتٌ صغيرة
// ══════════════════════════════════════════════════════════════════════

/** يزرع جلسةً **حقيقية** — رموزٌ أصدرها الخادم في الدعوى الأولى، لا مصطنعة. */
async function useSession(page: Page, which: "a" | "b"): Promise<void> {
  const session = sessions[which];
  expect(session, `جلسةُ الحساب ${which} لم تُصدَر بعد`).not.toBeNull();
  await page.addInitScript((s) => {
    localStorage.setItem("athera_access_token", s.access);
    localStorage.setItem("athera_refresh_token", s.refresh);
    localStorage.setItem("athera_token_expiry", s.expiry);
  }, session as Session);
}

async function readSession(page: Page): Promise<Session> {
  return page.evaluate(() => ({
    access: localStorage.getItem("athera_access_token") ?? "",
    refresh: localStorage.getItem("athera_refresh_token") ?? "",
    expiry: localStorage.getItem("athera_token_expiry") ?? "",
  }));
}

/** قراءةُ قائمة الرسائل من الـAPI مباشرةً — للتحقّق ممّا تراه القاعدة. */
async function listTheses(request: APIRequestContext, which: "a" | "b") {
  const response = note(await request.get(`${API_ORIGIN}/api/v1/theses?limit=25`, {
    headers: {
      Authorization: `Bearer ${sessions[which]?.access}`,
      "Accept-Language": EN,
    },
  }), "GET /api/v1/theses");
  expect(response.status(), "GET /api/v1/theses").toBe(200);
  return (await response.json()) as Array<Record<string, unknown>>;
}

/** بطاقةُ رسالةٍ على الشاشة، تُعرَف بالنصّ الذي يميّزها. */
function cardWith(page: Page, needle: string) {
  return page.locator("article.card").filter({ hasText: needle });
}

/**
 * سطرُ الحال في البطاقة — **يُنتقى بنصّه لا بترتيبه**.
 *
 * أوّلُ `.metric-label` في البطاقة هو سطرُ الدرجة لا سطرُ الحال؛ وفحصٌ
 * يقرأ «الأوّل» يقرأ الدرجة ويحكم بها على المعالجة — فيصير أخضرَ على
 * شيءٍ لم يُسأل عنه.
 */
function stateLine(page: Page, needle: string) {
  return cardWith(page, needle).locator(".metric-label", { hasText: "Status:" });
}

/**
 * اسمُ الحال المكتوب على البطاقة الآن — **مقروءًا من موضعٍ واحد**.
 *
 * وصياغتان لقصّ «Status:» ولاحقةِ المحاولات تفترقان بأول تعديل، فتقرأ
 * إحداهما «Ready for review · Processing attempts: 2» حالًا قائمةً بذاتها.
 */
async function stateLabel(page: Page, needle: string): Promise<string> {
  const line = (await stateLine(page, needle).textContent()) ?? "";
  return line.replace(/^Status:\s*/, "").split(" · ")[0].trim();
}

/** ينتظر أن تستقرّ حالُ البطاقة — بإعادة تحميلٍ لا باستطلاعٍ في الذاكرة. */
async function waitForTerminalState(page: Page, needle: string): Promise<string> {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    await page.reload();
    const card = cardWith(page, needle);
    await expect(card).toHaveCount(1);
    const label = await stateLabel(page, needle);
    if (TERMINAL_STATE_LABELS_EN.includes(label)) return label;
    expect(IN_FLIGHT_STATE_LABELS_EN, `حالٌ غير معروفة على البطاقة: ${label}`)
      .toContain(label);
    await page.waitForTimeout(1000);
  }
  throw new Error(`الحال لم تستقرّ لـ${needle} — بقيت جاريةً بعد ثلاثين محاولة`);
}

// ══════════════════════════════════════════════════════════════════════
// ١ — حسابٌ اصطناعي يُسجَّل، ثمّ يُدخَل به
// ══════════════════════════════════════════════════════════════════════
test.describe("المكدّس يقوم والجلسةُ تعمل | the stack answers", () => {
test.describe.configure({ mode: "serial" });

test("١ · حسابٌ اصطناعي يُنشأ بالنموذج ثمّ يُدخَل به | register, then sign in", async ({
  page,
}) => {
  // **بالنموذج لا بحقنِ رمز.** حقنُ الرمز يتخطّى بالضبط ما انكسر في
  // المعاينة: طلبَ تسجيلٍ يعبر أصلين. فإن كان الحاجز قائمًا سقطت هذه
  // الدعوى أوّلًا، وهو الترتيب الصحيح للخبر.
  await page.goto(`/${EN}/register`);
  await page.locator("#reg-name").fill("RC Journey");
  await page.locator("#reg-email").fill(ACCOUNT_A);
  await page.locator("#reg-password").fill(CI_PASSWORD);
  await page.locator("form button[type=submit]").click();

  await page.waitForURL(`**/${EN}`, { timeout: 30_000 });
  sessions.a = await readSession(page);
  expect(sessions.a.access, "التسجيل لم يُصدر رمزًا — الطلب لم يصل أو رُدّ").not.toBe("");

  // ثمّ الخروج والدخول من جديد: التسجيل بابٌ، والدخول بابٌ آخر — ومن فحص
  // أحدهما لم يفحص الآخر.
  await page.evaluate(() => localStorage.clear());
  await page.goto(`/${EN}/login`);
  await page.locator("input[type=email]").fill(ACCOUNT_A);
  await page.locator("#login-password").fill(CI_PASSWORD);
  await page.locator("form button[type=submit]").click();
  await page.waitForURL(`**/${EN}`, { timeout: 30_000 });

  const afterLogin = await readSession(page);
  expect(afterLogin.access, "الدخول لم يُصدر رمزًا").not.toBe("");
  sessions.a = afterLogin;

  // والحسابُ الثاني يُنشأ الآن ليُستعمل في الدعوى ١٢ — مستأجرٌ آخر تمامًا.
  const second = await page.context().newPage();
  watch(second);
  await second.goto(`/${EN}/register`);
  await second.locator("#reg-name").fill("RC Journey Neighbour");
  await second.locator("#reg-email").fill(ACCOUNT_B);
  await second.locator("#reg-password").fill(CI_PASSWORD);
  await second.locator("form button[type=submit]").click();
  await second.waitForURL(`**/${EN}`, { timeout: 30_000 });
  sessions.b = await readSession(second);
  expect(sessions.b.access, "الحساب الثاني لم يُنشأ").not.toBe("");
  await second.close();
});

// ══════════════════════════════════════════════════════════════════════
// ٢ + ٣ — الصفحةُ تُحمَّل، والجلسةُ متّسقة
// ══════════════════════════════════════════════════════════════════════
test("٢·٣ · /en/theses تُحمَّل والجلسةُ متّسقة | loads, and the shell agrees", async ({
  page,
}) => {
  await useSession(page, "a");
  await page.goto(`/${EN}/theses`);

  // العنوانُ يظهر: الصفحةُ عبرت `AuthGate` فعلًا — لا هيكلٌ فارغ.
  await expect(page.getByRole("heading", { name: THESES_TITLE_EN })).toBeVisible();

  // **الدعوى ٢** — الجملةُ التي أبلغ عنها المالك. وهي لا تُعرض إلّا حين
  // يُرفض `fetch` نفسه؛ فغيابُها يعني أنّ الطلب وصل ورُدّ عليه.
  await expect(page.getByText(LOAD_FAILED_EN, { exact: true })).toHaveCount(0);

  // وانتهاءُ التحميل يُثبت أنّ ردًّا وصل: «جارٍ التحميل…» تختفي عند
  // `finally` وحدها. فبقاؤها فشلٌ صامت لا يقوله غيابُ نصّ الخطأ.
  await expect(page.getByText("Loading…", { exact: true })).toHaveCount(0);

  // **الدعوى ٣** — لا «Sign in» ومحتوى داخلٍ في الشاشة نفسها.
  const sessionLink = page.locator(".session-link");
  await expect(sessionLink).toHaveText(SIGN_OUT_EN);
  await expect(page.getByText(SIGN_IN_EN, { exact: true })).toHaveCount(0);
});

});

// ══════════════════════════════════════════════════════════════════════
// ٧أ — رسالةٌ بلا ملفّ: «لم يبدأ» ليست فشلًا، ولا صفرًا صامتًا
// ══════════════════════════════════════════════════════════════════════
//
// **ومجموعتُها مستقلّة عن الرفع عمدًا.** هي نصفُ الدعوى السابعة — طرفُ
// «الفراغ» الذي يُقابَل به طرفُ «الفشل» — ولا تحتاج ملفًّا ولا تخزينًا.
// فلو عُلّقت بسلسلة الرفع لسقطت معها، ولَما عُرف أصلًا أهذا الطرفُ سليم.
test.describe("رسالةٌ بلا ملفّ | a thesis with no file", () => {
test.describe.configure({ mode: "serial" });

test("٧أ · التسجيلُ اليدوي يقول «لم يبدأ» لا «٠» | manual registration says why, not zero",
  async ({ page }) => {
    await useSession(page, "a");
    await page.goto(`/${EN}/theses`);
    await expect(page.getByRole("heading", { name: THESES_TITLE_EN })).toBeVisible();

    const registered = page.waitForResponse(
      (r) => r.url() === `${API_ORIGIN}/api/v1/theses` && r.request().method() === "POST",
      { timeout: 60_000 },
    );
    await page.getByLabel("Thesis title in Arabic").fill(MANUAL_TITLE_AR);
    await page.getByRole("button", { name: "Register the thesis" }).click();
    expect((await registered).status(), "POST /api/v1/theses").toBe(201);

    await page.reload();
    const card = cardWith(page, MANUAL_TITLE_AR);
    await expect(card).toHaveCount(1);

    const body = (await card.innerText()).trim();
    // **«لم يبدأ التحليل» لا «٠ أقسام».** ستُّ حالاتٍ تُنتج الصفر ومعناها
    // مختلف؛ فالسببُ يُقال، والرقمُ لا يُعرض إلّا حين يكون العدُّ قد وقع.
    expect(body).toContain("Analysis has not started");
    expect(body).toContain("Opportunity mining has not started");
    expect(body, `بطاقةٌ تعرض «٠ أقسام» بلا سبب:\n${body}`)
      .not.toMatch(/Sections extracted:\s*0(\D|$)/);
    expect(body, `بطاقةٌ تعرض «٠ فرص» بلا سبب:\n${body}`)
      .not.toMatch(/Opportunities found:\s*0(\D|$)/);

    // ولا زرَّ إعادةٍ يَعِد بما لا ملفَّ له — **ومعه سببُه مكتوبًا**.
    await expect(card.getByRole("button", { name: "Try again" })).toHaveCount(0);
    expect(body).toContain("No file is attached to this thesis.");
  });
});

// ══════════════════════════════════════════════════════════════════════
// **الرحلةُ مجموعاتٌ لا سلسلةٌ واحدة.**
//
// كانت الرقعةُ كلُّها `describe` واحدًا متسلسلًا، فسقوطُ الرفع كان
// يُسكت الدعاوى التي لا علاقةَ لها به — الاتجاهُ والجلسةُ والعزل —
// فيصير التقريرُ «واحدةٌ سقطت وثمانٍ لم تُقَل». وذلك أسوأ من فشلٍ
// صريح: عطبٌ واحد يُخفي حالَ المنتج كلَّه.
//
// فما يعتمد على الرفع في مجموعته، وما لا يعتمد عليه في مجموعته —
// **ولا تُضعَّف دعوى واحدة**: كلُّها باقيةٌ بحرفها.
// ══════════════════════════════════════════════════════════════════════
test.describe("رفعُ رسالةٍ وقراءتُها | the upload chain", () => {
test.describe.configure({ mode: "serial" });

// ══════════════════════════════════════════════════════════════════════
// ٤ + ٥ — الرفع ينجح، والبطاقةُ تحمل اسمَ الملفّ
// ══════════════════════════════════════════════════════════════════════
test("٤·٥ · الرفع ينجح والبطاقةُ تحمل اسمَ الملفّ | upload succeeds, filename fallback", async ({
  page, request,
}) => {
  // **الرمزُ يُسأل عنه مباشرةً أوّلًا — ثمّ يُقاد المتصفّح.**
  //
  // ولهذا الترتيبِ سبب: خمسمئةٌ تخرج من خارج `CORSMiddleware` تصل المتصفّحَ
  // بلا ترويسة أصلٍ، فيحجبها ولا يرى JS رمزًا ولا ترى الرقعةُ ردًّا — فيقول
  // الفحصُ «انتهت المهلة» عن عطبٍ رمزُه معروف. والسؤالُ من خارج المتصفّح
  // يقرأ الرمز كما هو، فيصير سطرُ الفشل يقول العطبَ لا يصف انتظارًا.
  const direct = note(await request.post(`${API_ORIGIN}/api/v1/theses/upload`, {
    headers: { Authorization: `Bearer ${sessions.a?.access}`, "Accept-Language": EN },
    multipart: {
      upload: {
        name: PROBE_PDF_NAME, mimeType: "application/pdf", buffer: pdfWithText(),
      },
    },
  }), "POST /api/v1/theses/upload");
  expect(direct.status(), "POST /api/v1/theses/upload (بلا متصفّح)").toBe(202);

  await useSession(page, "a");
  await page.goto(`/${EN}/theses`);
  await expect(page.getByRole("heading", { name: THESES_TITLE_EN })).toBeVisible();

  // **الرفعُ يُقاس بردّ الخادم لا بتبدّل الشاشة.** شاشةٌ تقول «تمّ» على
  // طلبٍ لم يُردّ عليه هي بعينها العطبُ الذي تحرسه هذه الرحلة.
  const uploaded = page.waitForResponse(
    (response) =>
      response.url() === `${API_ORIGIN}/api/v1/theses/upload` &&
      response.request().method() === "POST",
    { timeout: 60_000 },
  );
  await page.locator("input[type=file]").setInputFiles({
    name: TEXT_PDF_NAME, mimeType: "application/pdf", buffer: pdfWithText(),
  });
  const response = await uploaded;
  expect(response.status(), "POST /api/v1/theses/upload").toBe(202);

  // والمستندُ الثاني — بلا طبقةِ نصّ — يُرفع الآن ليُقارَن به لاحقًا.
  const scanned = page.waitForResponse(
    (r) => r.url() === `${API_ORIGIN}/api/v1/theses/upload` && r.request().method() === "POST",
    { timeout: 60_000 },
  );
  await page.locator("input[type=file]").setInputFiles({
    name: SCANNED_PDF_NAME, mimeType: "application/pdf", buffer: pdfWithoutText(),
  });
  expect((await scanned).status(), "POST /api/v1/theses/upload (scanned)").toBe(202);

  // **الدعوى ٥** — لا عنوانَ مستخرَجًا، فالهويّة اسمُ الملفّ، **ويُقال
  // إنّه اسمُ ملفّ**. وهذان شرطان لا واحد: اسمٌ بلا إقرارٍ بمصدره ادّعاءُ
  // استخراجٍ لم يقع.
  await page.reload();
  const card = cardWith(page, TEXT_PDF_NAME);
  await expect(card).toHaveCount(1);
  await expect(card.getByText(BY_FILENAME_EN, { exact: true })).toBeVisible();
});

// ══════════════════════════════════════════════════════════════════════
// ٦ — الحالُ تصمد عبر إعادة التحميل
// ══════════════════════════════════════════════════════════════════════
test("٦ · الحالُ تصمد عبر إعادة التحميل | the processing state survives a reload", async ({
  page,
}) => {
  await useSession(page, "a");
  await page.goto(`/${EN}/theses`);
  await expect(page.getByRole("heading", { name: THESES_TITLE_EN })).toBeVisible();

  // تُنتظر حالٌ مستقرّة أوّلًا: مقارنةُ حالٍ جاريةٍ عبر إعادة تحميلٍ تقيس
  // مرورَ الزمن لا صمودَ الحال.
  const settled = await waitForTerminalState(page, TEXT_PDF_NAME);
  const scannedState = await waitForTerminalState(page, SCANNED_PDF_NAME);

  // **والحال في القاعدة (ترحيل 0027) لا في ذاكرة الصفحة.** فإعادةُ تحميلٍ
  // كاملة — لا تنقّلٌ داخل العميل — هي الفحص الصحيح.
  await page.goto(`/${EN}/theses`);
  await expect(page.getByRole("heading", { name: THESES_TITLE_EN })).toBeVisible();
  await expect(stateLine(page, TEXT_PDF_NAME)).toContainText(settled);
  await expect(stateLine(page, SCANNED_PDF_NAME)).toContainText(scannedState);

  // والمستندُ الممسوح لا بدّ أن ينتهي إلى «لا طبقة نصّ» بعينها: هي أساسُ
  // الدعويين ٧ و٨، ولو انتهى إلى غيرها لفحصتا شيئًا آخر بلا أن يُقال.
  expect(scannedState, "المستندُ بلا نصّ لم يُصنَّف «لا طبقة نصّ»")
    .toBe("The document has no text layer");
});

// ══════════════════════════════════════════════════════════════════════
// ٧ — الحالُ صادقة: الفشلُ ليس فراغًا، ولا «٠» بلا سبب
// ══════════════════════════════════════════════════════════════════════
test("٧ · الفشلُ يُرى مختلفًا عن الفراغ، ولا صفرَ صامت | failed ≠ empty, no bare zero", async ({
  page,
}) => {
  await useSession(page, "a");
  await page.goto(`/${EN}/theses`);
  await expect(page.getByRole("heading", { name: THESES_TITLE_EN })).toBeVisible();

  const scanned = cardWith(page, SCANNED_PDF_NAME);
  const manual = cardWith(page, MANUAL_TITLE_AR);
  await expect(scanned).toHaveCount(1);
  await expect(manual).toHaveCount(1);

  const scannedText = (await scanned.innerText()).trim();
  const manualText = (await manual.innerText()).trim();

  // **حالُ فشلٍ مسمّاة، لا صمت.** وهي تحمل سببها نصًّا.
  expect(scannedText).toContain("The document has no text layer");
  expect(scannedText).toContain("No readable text layer");

  // **وحالُ «لم يبدأ» ليست فشلًا** — رسالةٌ بلا ملفّ لم يُطلب لها شيء.
  expect(manualText).toContain("Analysis has not started");

  // والفرقُ يُرى: لا يجوز أن تحمل بطاقةُ الفراغ نصَّ الفشل ولا العكس.
  expect(manualText).not.toContain("No readable text layer");
  expect(scannedText).not.toContain("Analysis has not started");

  // **ولا «٠» بلا سبب — في أيّ بطاقة.** العددُ لا يُعرض إلّا حين يكون
  // العدُّ قد وقع؛ وما لم يقع يُقال بسببه لا برقمٍ صفريّ.
  const cards = page.locator("article.card");
  const count = await cards.count();
  expect(count, "لا بطاقاتٍ على الشاشة — الرحلة لم تصل هنا").toBeGreaterThanOrEqual(3);
  for (let index = 0; index < count; index += 1) {
    const body = (await cards.nth(index).innerText()).trim();
    expect(body, `بطاقةٌ تعرض «٠ أقسام» بلا سبب:\n${body}`)
      .not.toMatch(/Sections extracted:\s*0(\D|$)/);
    expect(body, `بطاقةٌ تعرض «٠ فرص» بلا سبب:\n${body}`)
      .not.toMatch(/Opportunities found:\s*0(\D|$)/);
  }
});

// ══════════════════════════════════════════════════════════════════════
// ٨ — إعادةُ المحاولة: معروضةٌ حيث تجوز، ومردودةٌ ٤٠٩ حيث لا تجوز
// ══════════════════════════════════════════════════════════════════════
test("٨ · إعادةُ المحاولة تُعرض وتُردّ ٤٠٩ | retry offered where allowed, 409 where not",
  async ({ page, request }) => {
    await useSession(page, "a");
    await page.goto(`/${EN}/theses`);
    await expect(page.getByRole("heading", { name: THESES_TITLE_EN })).toBeVisible();

    // معرّفاتُ الرسائل من الـAPI: الشاشةُ لا تعرضها، والتخمينُ من DOM هشّ.
    for (const row of await listTheses(request, "a")) {
      const filename = row.source_filename as string | null;
      if (filename) theses[filename] = row.id as string;
      else theses[MANUAL_TITLE_AR] = row.id as string;
    }
    expect(theses[TEXT_PDF_NAME], "لم تُعرف رسالةُ المستند النصّي").toBeTruthy();
    expect(theses[SCANNED_PDF_NAME], "لم تُعرف رسالةُ المستند الممسوح").toBeTruthy();

    // ــ حيث تجوز: **الفعلُ الذي توجبه الحال، لا أيُّ فعل** ــ
    //
    // والحالُ تُقرأ من البطاقة أوّلًا ثمّ يُطلب فعلُها من الجدول. ولو ثُبِّتت
    // سلسلةٌ بعينها هنا لصار الفحص هشًّا في الاتجاه الآخر: مستندٌ نصّيّ
    // سقطت قراءتُه في بيئةٍ ما ينتهي إلى «Analysis failed» بحقّ، وفعلُه
    // حينها «Try again» لا «Read it again» — والدعوى تُسائل الحال، لا الحظّ.
    const withText = cardWith(page, TEXT_PDF_NAME);
    const textState = await stateLabel(page, TEXT_PDF_NAME);
    const offered = await expectReadAction(withText, textState);
    expect(offered, `مستندٌ نصّيّ في حال «${textState}» ولا فعلَ قراءةٍ عليه`)
      .not.toBeNull();

    // ــ وحيث لا تجوز: لا زرَّ **من الثلاثة**، وسببٌ مكتوب مكانه ــ
    //
    // وزرٌّ مُطفأ بلا تفسير كان سيمرّ على فحصٍ يسأل «أغائبٌ هو؟» وحده،
    // فيُسأل الأمران: غيابُ الوعد، وحضورُ سببه.
    const scanned = cardWith(page, SCANNED_PDF_NAME);
    const scannedState = await stateLabel(page, SCANNED_PDF_NAME);
    expect(scannedState, "المستندُ بلا نصّ لم يعد «لا طبقة نصّ» — الدعوى تفحص غيرَ ما قُصد")
      .toBe("The document has no text layer");
    expect(await expectReadAction(scanned, scannedState),
           "مستندٌ ممسوح ضوئيًّا عُرض عليه فعلُ قراءةٍ يُعيد النتيجة نفسها")
      .toBeNull();
    await expect(scanned.getByText("The document has no text layer", { exact: false }).first())
      .toBeVisible();

    // **والرفضُ يقع على الخادم لا في الشاشة وحدها.** شاشةٌ تُخفي زرًّا
    // وخادمٌ يقبل الطلب حارسٌ واحدٌ لا اثنان: من نادى النقطة مباشرةً مرّ.
    const refused = note(await request.post(
      `${API_ORIGIN}/api/v1/theses/${theses[SCANNED_PDF_NAME]}/reprocess`,
      { headers: { Authorization: `Bearer ${sessions.a?.access}`, "Accept-Language": EN } },
    ), "POST reprocess (scanned)");
    expect(refused.status(), "reprocess على مستندٍ ممسوح").toBe(409);
    const body = await refused.json();
    expect(body?.error?.code).toBe("thesis.retry_needs_ocr");

    // ــ وحيث تجوز: تُقبل، **وواحدةٌ فقط** حين تُضغط مرّتين ــ
    //
    // **والطلبان يُرسلان معًا لا بالتتابع.** بالتتابع يكون الفحصُ سباقًا مع
    // المهمّة الخلفية: لو انتهت بين الطلبين لقُبل الثاني بحقّ، فيسقط الفحص
    // على سلوكٍ صحيح. وبإرسالهما معًا تحكم القاعدةُ بينهما — الحجزُ شرطٌ في
    // عبارة الكتابة نفسها — فأحدُهما يصيب صفًّا والآخر يصيب صفرًا.
    const headers = {
      Authorization: `Bearer ${sessions.a?.access}`, "Accept-Language": EN,
    };
    const url = `${API_ORIGIN}/api/v1/theses/${theses[TEXT_PDF_NAME]}/reprocess`;
    const pair = (await Promise.all([
      request.post(url, { headers }), request.post(url, { headers }),
    ])).map((r) => note(r, "POST reprocess"));
    const statuses = pair.map((r) => r.status()).sort();
    expect(statuses, "ضغطتان على «أعد القراءة» — واحدةٌ تُقبل وواحدةٌ تُردّ")
      .toEqual([202, 409]);
    const refusedTwin = pair.find((r) => r.status() === 409)!;
    expect((await refusedTwin.json())?.error?.code).toBe("thesis.processing_in_flight");
  });

});

// ══════════════════════════════════════════════════════════════════════
// ٩ + ١٠ — العربيةُ من اليمين، وحالُ الجلسة واحدةٌ باللغتين
// ══════════════════════════════════════════════════════════════════════
test.describe("اللغتان | both locales", () => {
test.describe.configure({ mode: "serial" });
test("٩·١٠ · /ar/theses من اليمين، والجلسةُ واحدةٌ باللغتين | RTL, and one session state",
  async ({ page }) => {
    await useSession(page, "a");
    await page.goto(`/${AR}/theses`);

    await expect(page.getByRole("heading", { name: THESES_TITLE_AR })).toBeVisible();

    // **الاتجاهُ على `<html>` لا مرآةٌ في CSS** — ويُقرأ من المتصفّح
    // محسوبًا، لا من الوسم: وسمٌ مكتوبٌ تُبطله قاعدةُ نمطٍ لاحقة.
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.locator("html")).toHaveAttribute("lang", AR);
    const computed = await page.evaluate(() => getComputedStyle(document.body).direction);
    expect(computed, "جسمُ الصفحة لا يُصيَّر من اليمين").toBe("rtl");

    // ولا تمريرَ أفقيًّا: صفحةٌ عربيةٌ تُدفع خارج الشاشة ليست RTL صحيحة.
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, "المستند يمرَّر أفقيًّا").toBeLessThanOrEqual(1);

    // والجملةُ العربية المقابلة غائبةٌ أيضًا — العطبُ لو كان لظهر باللغتين.
    await expect(page.getByText(LOAD_FAILED_AR, { exact: true })).toHaveCount(0);

    // **الدعوى ١٠** — حالٌ واحدة لا حالان.
    await expect(page.locator(".session-link")).toHaveText(SIGN_OUT_AR);
    await expect(page.getByText(SIGN_IN_AR, { exact: true })).toHaveCount(0);

    await page.goto(`/${EN}/theses`);
    await expect(page.locator(".session-link")).toHaveText(SIGN_OUT_EN);
    await expect(page.getByText(SIGN_IN_EN, { exact: true })).toHaveCount(0);
    await expect(page.getByText(LOAD_FAILED_EN, { exact: true })).toHaveCount(0);
  });

});

// ══════════════════════════════════════════════════════════════════════
// ١٢ — لا تسرّب: بين مستأجرين، ولا بين رسالتين في مستأجرٍ واحد
// ══════════════════════════════════════════════════════════════════════
test.describe("العزل | isolation", () => {
test.describe.configure({ mode: "serial" });
test("١٢أ · الجارُ لا يرى شيئًا من رسائل جاره | the neighbour sees nothing",
  async ({ page, request }) => {
    // ــ الجارُ لا يرى شيئًا: لا في الشاشة ولا في الـAPI ــ
    await useSession(page, "b");
    await page.goto(`/${EN}/theses`);
    await expect(page.getByRole("heading", { name: THESES_TITLE_EN })).toBeVisible();
    await expect(page.getByText(LOAD_FAILED_EN, { exact: true })).toHaveCount(0);

    // «لا رسائل بعد» تُقال **بعد** أن يُردّ الطلب — والشاشة تحرس ذلك
    // بـ`loaded`. فظهورُها هنا خبرٌ عن قائمةٍ وصلت فارغة.
    await expect(page.getByText("No theses yet.", { exact: true })).toBeVisible();
    for (const needle of [TEXT_PDF_NAME, SCANNED_PDF_NAME, MANUAL_TITLE_AR]) {
      await expect(page.getByText(needle, { exact: false })).toHaveCount(0);
    }

    expect(await listTheses(request, "b"), "الجارُ يرى رسائلَ ليست له").toEqual([]);

    // **والقراءةُ بالمعرّف تُردّ.** قائمةٌ فارغة تُثبت أنّ الترشيح واقع؛
    // ولا تُثبت أنّ الوصولَ بالمعرّف ممنوع — وهما بابان.
    //
    // والمعرّفُ يُقرأ من قائمة صاحبه الآن، لا من حالةٍ ملأتها دعوى أخرى:
    // فحصُ العزل لا يجوز أن يتوقّف على نجاح الرفع.
    const own = await listTheses(request, "a");
    expect(own.length, "الحسابُ الأوّل بلا رسالةٍ واحدة").toBeGreaterThanOrEqual(1);
    const target = own[0].id as string;
    const stolen = note(await request.get(
      `${API_ORIGIN}/api/v1/theses/${target}/extraction`,
      { headers: { Authorization: `Bearer ${sessions.b?.access}`, "Accept-Language": EN } },
    ), "GET extraction (neighbour)");
    expect([403, 404], `الجارُ بلغ رسالةَ غيره بـ${stolen.status()}`)
      .toContain(stolen.status());
  });

// ــ ولا تسرّبَ بين رسالتين في المستأجر الواحد ــ
//
// **وRLS لا تحمي هنا**: الرسالتان لمستأجرٍ واحد. فالشرط في `WHERE` هو
// الحارس وحده — وهو عطبٌ وقع في هذا المنتج من قبل. والفحصُ أن عدَّ كلِّ
// بطاقةٍ يخصّها هي، لا جارتها.
test("١٢ب · لا تعدّ رسالةٌ ما لجارتها | one thesis never counts its neighbour rows",
  async ({ request }) => {
    const own = await listTheses(request, "a");
    const byName = new Map(own.map((row) =>
      [(row.source_filename as string | null) ?? MANUAL_TITLE_AR, row]));

    // الرسالةُ المسجّلة يدويًّا بلا ملفّ: لا يجوز أن تلتقط أقسامَ جارتها.
    const manual = byName.get(MANUAL_TITLE_AR);
    expect(manual, "الرسالةُ اليدوية غائبة").toBeTruthy();
    expect(manual?.sections_extracted, "رسالةٌ بلا ملفّ تعدّ أقسامًا").toBe(0);
    expect(manual?.sections_outcome).toBe("not_started");
    expect(manual?.opportunities_found, "رسالةٌ بلا ملفّ تعدّ فرصًا").toBe(0);

    // والمستندُ الممسوح لم يُقرأ منه شيء، فلا أقسامَ له مهما جاورته رسالة.
    expect(own.length,
      "الأربع — مسبارٌ ورفعتان وتسجيلٌ يدويّ").toBe(4);
    const scanned = byName.get(SCANNED_PDF_NAME);
    expect(scanned?.sections_extracted, "مستندٌ بلا نصّ يعدّ أقسامًا").toBe(0);
    expect(scanned?.processing_state).toBe("text_layer_missing");
  });

});

// ══════════════════════════════════════════════════════════════════════
// ١١ — ولا خمسمئةٌ في الرحلة كلّها
// ══════════════════════════════════════════════════════════════════════
//
// **وهي آخرُ دعوى عمدًا**: تحكم على ما جمعته الرحلةُ كلُّها قبلها. ولو
// وُضعت أوّلًا لحكمت على لا شيء وقالت «أخضر».
test("١١ · لا ٥٠٠ في الرحلة كلّها | no 5xx anywhere in the journey", async () => {
  expect(serverErrors, "ردودٌ ≥٥٠٠ في الرحلة").toEqual([]);

  // **وخمسمئةٌ تُحجب ليست خمسمئةً غائبة.** استجابةٌ تخرج من خارج
  // `CORSMiddleware` تصل بلا ترويسة أصل، فيحجبها المتصفّح ولا تُحسب ردًّا.
  // فلو اكتفت هذه الدعوى بعدّ الـ٥٠٠ لأخضرّت على خمسمئةٍ وقعت — وهي
  // الحالُ التي تُنتج «Could not load the data.» عند الباحث.
  expect(requestFailures, "طلباتٌ رُفضت قبل أن تصير ردًّا").toEqual([]);

  expect(pageErrors, "استثناءاتٌ في المتصفّح أثناء الرحلة").toEqual([]);
});
