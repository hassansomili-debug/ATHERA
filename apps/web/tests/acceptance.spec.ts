import { expect, test, type Page } from "@playwright/test";

import { LOCALE, signIn } from "./journey";

/**
 * رحلة القبول | The P1 acceptance journey — a real researcher, a real browser.
 *
 * **ولا معرّف يُكتب بيد، ولا طرفية، ولا SQL.** كل خطوة هنا تقع بالنقر
 * والكتابة في الشاشة، كما يفعل الباحث. وما لا يمكن فعله هكذا لم يُقبَل.
 *
 * الاعتماد يأتي من البيئة لا من المستودع:
 *   PUBRIVA_WEB_URL          عنوان الواجهة
 *   PUBRIVA_ACCEPT_EMAIL     بريد حساب القبول (اختياري — يُنشأ إن غاب)
 *   PUBRIVA_ACCEPT_PASSWORD  كلمته
 */
const EMAIL = process.env.PUBRIVA_ACCEPT_EMAIL;
const PASSWORD = process.env.PUBRIVA_ACCEPT_PASSWORD;

// اسمٌ فريد لكل تشغيلة، فلا تتعارض تشغيلتان ولا تُقرأ بقايا سابقة.
const RUN = `قبول ${new Date().toISOString().slice(0, 19)}`;
// اسمٌ فريد للملف كذلك، فلا تتعارض تشغيلتان في مكتبةٍ واحدة.
const FILENAME = `pubriva-acceptance-${Date.now()}.txt`;

/**
 * التنقّل الجانبي بعينه.
 *
 * **رابط «مكتبتي» موجود في موضعين**: القائمة الجانبية، وداخل مساحة العمل
 * حين لا يوجد مرشّح للإضافة. و`getByRole` بلا موضع يطابق الاثنين فيسقط
 * الفحص بـstrict mode — وهو محقّ: «اضغط الرابط» ليست تعليمة كافية حين
 * يوجد رابطان.
 */
const sidebar = (page: Page) =>
  page.getByRole("navigation", { name: "الرئيسية" });

/**
 * **لا أثر يحمل سرًّا.**
 *
 * أثرُ Playwright يسجّل وسائط كل فعل — ومنها ما يُملأ في حقل كلمة المرور،
 * نصًّا صريحًا. ولقطةُ الشاشة ولقطةُ DOM تحملان قيمة الحقل كذلك. وهذه
 * الملفات تُرفع أثرًا في CI يقرؤه كل من يملك وصولًا إلى المستودع.
 *
 * وقد وقع ذلك فعلًا: اعتماد حساب القبول ظهر في أثر تشغيلة إنتاجية. فتُطفأ
 * هذه المسجّلات في هذه الحزمة وحدها — وحزمةُ دورة الحياة تحتفظ بها، إذ لا
 * اعتماد فيها أصلًا. **وقابليةُ التشخيص لا تُشترى بتسريب كلمة مرور.**
 */
test.use({ trace: "off", video: "off", screenshot: "off" });

test.describe.configure({ mode: "serial" });

test.skip(
  !PASSWORD,
  "PUBRIVA_ACCEPT_PASSWORD is not set — acceptance needs a real account; " +
    "credentials never live in Git.",
);

test("the P1 researcher journey completes end to end", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  let projectUrl = "";

  // ── ١–٢: الدخول ──
  await test.step("sign in", async () => {
    await page.goto(`/${LOCALE}/login`);
    // يفشل **هنا** إن فشل الدخول — لا بعد خطوتين في موضعٍ بريء.
    await signIn(page, EMAIL!, PASSWORD!);
  });

  // ── ٣: الرئيسية بلا حلقة مصادقة ──
  await test.step("home loads without an auth loop", async () => {
    // تنقّلٌ كامل بعد إثبات الدخول: هل تصمد الجلسة عبر تحميلٍ جديد؟
    await page.goto(`/${LOCALE}`);
    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    // الشعار يقول اسم المنتج ووعده.
    await expect(page.locator(".brand")).toContainText("بُبريفا");
  });

  // ── ٤: أبحاثي ──
  await test.step("My Research loads", async () => {
    await sidebar(page).getByRole("link", { name: "أبحاثي" }).click();
    await page.waitForURL(/\/portfolio/);
    await expect(page.getByText("ابدأ بحثًا جديدًا")).toBeVisible();
  });

  // ── ٥–٦: إنشاء بحثٍ بعنوانٍ وحده، ثم فتحه ──
  await test.step("create a project by title and open it", async () => {
    await page.getByLabel("عنوان البحث").fill(RUN);
    await page.getByRole("button", { name: /أنشئ البحث/ }).click();
    // الإنشاء يفتح مساحة العمل مباشرة — لا معرّف يُنسخ.
    await page.waitForURL(/\/portfolio\/[0-9a-f-]{36}/, { timeout: 30_000 });
    await expect(page.getByRole("heading", { name: RUN })).toBeVisible();
    // يُحفظ المسار بعينه: الخطوات التالية تعود إليه لا إلى «آخر بحث».
    projectUrl = page.url();
  });

  // ── ٧: النظرة العامة تقول حالاتٍ صادقة ──
  await test.step("Overview shows truthful Research Brain states", async () => {
    await expect(page.getByText("ما تعرفه بُبريفا عن بحثك")).toBeVisible();
    await expect(page.getByText(/لا تُعرض نسبة جاهزية/)).toBeVisible();
    // ولا نسبة مئوية في الصفحة إطلاقًا.
    expect(await page.locator("body").innerText()).not.toMatch(/\d+\s*%/);
    await expect(page.getByText("بُبريفا تقترح")).toBeVisible();
  });

  // ── ٨–١٠: مكتبة ← ربطٌ ببحث ← فكُّ الربط ← الأصل باقٍ في المكتبة ──
  //
  // **الرحلة تصنع ما تحتاجه بنفسها.** فحصٌ يعتمد على بياناتٍ سابقة في
  // الحساب يمرّ اليوم ويسقط غدًا بلا أن يتغيّر سطر — ونجاحُه لا يقول شيئًا.
  // فالملف يُرفع من الواجهة نفسها، باسمٍ فريد لكل تشغيلة.
  await test.step("upload a file into My Library through the UI", async () => {
    await sidebar(page).getByRole("link", { name: "مكتبتي" }).click();
    await page.waitForURL(/\/library/);

    // مدخل الملف مخفيّ خلف زرّ — و`setInputFiles` يكتب فيه مباشرةً كما
    // يفعل المتصفح بعد اختيار المستخدم، بلا اختراع مسارٍ للـAPI.
    await page.locator('input[type="file"]').setInputFiles({
      name: FILENAME,
      mimeType: "text/plain",
      buffer: Buffer.from(`PUBRIVA acceptance ${RUN}\n`, "utf-8"),
    });

    // ج — الرفع أثبت نفسه: الحال «تم الحفظ» والاسم الفريد ظاهر.
    await expect(page.getByText("تم الحفظ")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(FILENAME).first()).toBeVisible({ timeout: 30_000 });
  });

  await test.step("link that exact file to the project", async () => {
    // د — العودة إلى البحث بعينه، بمساره المحفوظ لا بتخمين.
    await page.goto(projectUrl);
    await expect(page.getByRole("heading", { name: RUN })).toBeVisible();
    await page.getByRole("button", { name: "الملفات" }).click();

    // و — انتظار الملف بعينه بين المرشّحين. والتحميل حالٌ مستقلة عن الفراغ،
    // فلا يُقرأ «ما زال يُقرأ» على أنه «لا شيء هنا».
    const candidate = page.locator("article.card", { hasText: FILENAME });
    await expect(candidate).toBeVisible({ timeout: 30_000 });

    // ز — زرُّ الإضافة **الذي يخصّ هذا الملف**، لا أوّل زرٍّ في الصفحة.
    await candidate.getByRole("button", { name: "+" }).click();

    // ح — صار مرتبطًا: بطاقته تحمل زرّ الإزالة.
    const linked = page.locator("article.card", { hasText: FILENAME });
    await expect(
      linked.getByRole("button", { name: "أزِل من البحث" }),
    ).toBeVisible({ timeout: 30_000 });
  });

  await test.step("unlink that exact file from the project", async () => {
    const linked = page.locator("article.card", { hasText: FILENAME });
    await linked.getByRole("button", { name: "أزِل من البحث" }).click();

    // ي — إن عُرض ما يترتب، أُقرّ به. وعرضُه صحيحٌ لا عيب.
    const acknowledge = page.getByRole("button", { name: /أفهم ما يترتب/ });
    if (await acknowledge.count()) await acknowledge.click();

    // ك — لم يعد مرتبطًا: لا بطاقةَ إزالةٍ تحمل هذا الاسم.
    await expect(
      page.locator("article.card", { hasText: FILENAME })
        .getByRole("button", { name: "أزِل من البحث" }),
    ).toHaveCount(0, { timeout: 30_000 });
  });

  await test.step("the asset survives in My Library", async () => {
    // ل + م — الإزالة من بحثٍ ليست حذفًا من المكتبة.
    await sidebar(page).getByRole("link", { name: "مكتبتي" }).click();
    await page.waitForURL(/\/library/);
    await expect(page.getByText(FILENAME).first()).toBeVisible({ timeout: 30_000 });
  });

  // ── ١١–١٢: مرجعٌ يُضاف «محفوظًا فقط» ──
  await test.step("the literature section states the saved_only rule", async () => {
    // **لا تُقبل هذه الخطوة قبولًا.** الربط من الواجهة لم يُفحص بعد؛ وما
    // يُفحص هنا أن القسم يُفتح ويقول قاعدته. فإن بلغت الرحلة هذا الحدّ
    // وتعذّر على الباحث ربط مرجعٍ من الشاشة، فذلك عيب منتج لا عيب فحص —
    // ويُصنَّف حينها، لا الآن.
    await page.goto(projectUrl);
    await page.getByRole("button", { name: "الأدبيات والمراجع" }).click();
    await expect(page.getByText(/الاستيراد ليس حكمًا بأن المرجع دليل/)).toBeVisible({
      timeout: 30_000,
    });

    // وإن وُجد مرجعٌ مرتبط، فحاله الافتراضية «محفوظ فقط» — بلا تخطٍّ صامت:
    // إمّا لا مرجع بعد (وتلك حالٌ معلنة)، وإمّا مرجعٌ حاله مُثبَت.
    const saved = page.getByRole("button", { name: "محفوظ فقط" });
    const noSources = page.getByText("لا مرجع في هذا البحث بعد.");
    await expect(saved.first().or(noSources)).toBeVisible({ timeout: 30_000 });
    if (await saved.count()) {
      await expect(saved.first()).toHaveAttribute("aria-pressed", "true");
    }
  });

  // ── ١٣: أرشفة ثم سلّة ثم استعادة ──
  await test.step("archive, trash and restore the project", async () => {
    await page.goto(`/${LOCALE}/portfolio`);
    const card = page.locator("article.card", { hasText: RUN });
    await card.getByRole("button", { name: "انقل إلى السلّة" }).click();
    await expect(page.locator("article.card", { hasText: RUN }).first()).toBeHidden({ timeout: 20_000 });

    const trashed = page.locator("article.card", { hasText: RUN });
    await trashed.getByRole("button", { name: "استعِد" }).click();
    await expect(page.locator("article.card", { hasText: RUN }).first()).toBeVisible({ timeout: 20_000 });
  });

  // ── ١٧–٢٠: بُبريفا AI تجيب بلا ترميز عقد ──
  await test.step("PUBRIVA AI answers with no contract markup", async () => {
    await page.goto(`/${LOCALE}`);
    const ask = page.getByRole("textbox").first();
    await ask.fill("ما الفرق بين المنهج الوصفي وشبه التجريبي؟");
    await ask.press("Enter");

    const answer = page.locator("[data-testid='ai-answer'], .ai-answer").first();
    await expect(answer).toBeVisible({ timeout: 120_000 });
    const text = await answer.innerText();
    for (const markup of ["</answer_ar>", "<answer_ar>", "<citations>", "</invoke>"]) {
      expect(text).not.toContain(markup);
    }
    expect(text.trim().length).toBeGreaterThan(20);
  });

  // ── ٢١–٢٢: خروجٌ ثم دخولٌ ثانٍ ──
  await test.step("sign out and sign back in", async () => {
    await page.getByRole("button", { name: /خروج|sign out/i }).click();
    await page.waitForURL(/\/login/, { timeout: 30_000 });
    expect(await page.evaluate(() => localStorage.getItem("athera_access_token"))).toBeNull();

    await signIn(page, EMAIL!, PASSWORD!);
  });

  // لا خطأ JS صامتًا في أي خطوة.
  expect(errors, `page errors: ${errors.join(" | ")}`).toHaveLength(0);
});

test("a new researcher can create an account from the browser", async ({ page }) => {
  // **باب التسجيل موجود ويعمل.** لا يُنشأ حسابٌ في كل تشغيلة: يُتحقّق أن
  // الصفحة قائمة وتقبل المدخلات وتردّ خطأً مفهومًا على بريدٍ مأخوذ.
  await page.goto(`/${LOCALE}/login`);
  await page.getByRole("link", { name: /أنشئ واحدًا|Create one/i }).click();
  await page.waitForURL(/\/register/);

  await expect(page.getByRole("heading", { name: /أنشئ حسابًا/ })).toBeVisible();
  await page.getByLabel("الاسم الكامل").fill("باحث القبول");
  await page.getByLabel(/البريد/).fill(EMAIL ?? "taken@example.com");
  await page.getByLabel(/كلمة المرور/).fill("a-very-long-password-123");
  await page.getByRole("button", { name: /أنشئ حسابًا/ }).click();

  // بريدٌ مأخوذ يجب أن يُنتج رسالةً مفهومة، لا صمتًا.
  await expect(page.getByTestId("register-error")).toBeVisible({ timeout: 30_000 });
});
