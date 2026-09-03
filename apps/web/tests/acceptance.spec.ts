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
// مرجعٌ حقيقي بـDOI ثابت: الرحلة تستورده بنفسها، فلا تتّكئ على مكتبةٍ مأهولة.
const DOI = "10.1037/0022-0663.99.1.83";
const DOC_NAME = `pubriva-doc-${Date.now()}.txt`;
/**
 * وثيقةٌ **تركيبية** بالكامل — لا محتوى بحثٍ شخصي ولا بيانات أحد.
 * وصياغتها تشبه رسالةً علمية لتُنتج مرشّحين عند الاستخراج.
 */
const DOC_TEXT = [
  "مشكلة الدراسة: يعاني طلاب المرحلة الثانوية من ضعف في التفكير الناقد.",
  "سؤال الدراسة: ما أثر برنامج تدريبي قائم على التعلّم النشط في التفكير الناقد؟",
  "منهج الدراسة: منهج شبه تجريبي بتصميم المجموعتين مع قياس قبلي وبعدي.",
  "عيّنة الدراسة: تكوّنت العيّنة من 60 طالبًا وُزّعوا عشوائيًّا على مجموعتين.",
  "أداة الدراسة: اختبار التفكير الناقد المقنّن، وبلغ ثبات الأداة 0.87.",
  "النتائج: وُجد فرق دال إحصائيًّا لصالح المجموعة التجريبية.",
  "حدود الدراسة: اقتصرت على مدارس حكومية في مدينة واحدة خلال فصل دراسي.",
].join("\n");
// وعنوانه يُقرأ من الشاشة بعد الاستيراد — لا يُخمَّن ولا يُكتب معرّفه.

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
  /**
   * **مهلةُ هذه الرحلة وحدها — لا مهلةُ الحزم كلها.**
   *
   * سبعَ عشرةَ خطوةً في فحصٍ واحد، وفيها معالجةُ مستندٍ حقيقية وجولةُ
   * ذهابٍ وإياب إلى نموذج. والمهلة العامة تسعون ثانية، فكان الفحص يُقتل
   * عند الخطوة الرابعة عشرة — **لا لأن شيئًا فشل، بل لأن الوقت نفد**.
   * فبدا الرفعُ ساقطًا وهو لم يُفحص أصلًا.
   *
   * وترفعُ المهلة العامة تُبطئ إخفاق حزمتَي دورة الحياة والاستعادة —
   * وهما سريعتان بلا اعتماد — فيصير كل عطبٍ فيهما بطيء الظهور. فتُرفع
   * هنا وحدها.
   *
   * **وليست بلا حدّ**: خمس عشرة دقيقة ظرفُ تنفيذٍ مشروع لهذه الرحلة، لا
   * أكثر. والحدودُ الحقيقية للإخفاق تبقى في مهلة كل عملية على حدة —
   * وهذه لا تفعل إلا أن تمنع قتلَ الرحلة قبل أن تبلغ آخرها.
   */
  test.setTimeout(15 * 60 * 1000);

  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  let projectUrl = "";
  let sourceTitle = "";

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
  // ── ١١–١٢: مرجعٌ يُستورد ثم يُربط، ويأتي «محفوظًا فقط» ──
  //
  // **ولا يُقبل «النصّ ظاهر» بديلًا عن «الفعل وقع».** الخطوة السابقة كانت
  // تثبت أن القسم يقول قاعدته — وتلك جملةٌ في الشاشة لا رحلةُ باحث.
  await test.step("import a reference into My Library through the UI", async () => {
    await sidebar(page).getByRole("link", { name: "مكتبتي" }).click();
    await page.waitForURL(/\/library/);

    // DOI ثابت ومعروف — والاستيراد يقع من الشاشة لا من الـAPI.
    await page.getByLabel(/DOI/i).first().fill(DOI);
    await page.getByRole("button", { name: /استيراد|Import/ }).click();

    // إمّا استُورد الآن، وإمّا كان مستوردًا من تشغيلةٍ سابقة — وكلاهما
    // يترك المرجع في المكتبة، وهو الشرط. والفشل يُعلَن ولا يُبتلع.
    const imported = page.locator("article.card").filter({ hasText: DOI }).first();
    await expect(
      imported.or(page.getByTestId("library-source-error")),
    ).toBeVisible({ timeout: 90_000 });
    // والفشل يُعلَن ولا يُبتلع: إن ظهر الخطأ سقطت الخطوة هنا بنصّه.
    await expect(imported, "the DOI import did not produce a source card")
      .toBeVisible({ timeout: 30_000 });

    // العنوان يُقرأ من الشاشة، وبه يُطابَق المرجع لاحقًا — لا بمعرّف.
    sourceTitle = (await imported.locator("strong").first().innerText()).trim();
    expect(sourceTitle.length, "the imported source has no title").toBeGreaterThan(3);
  });

  await test.step("link that reference to the project, defaulting to saved_only", async () => {
    await page.goto(projectUrl);
    await page.getByRole("button", { name: "الأدبيات والمراجع" }).click();
    await expect(page.getByText(/الاستيراد ليس حكمًا بأن المرجع دليل/)).toBeVisible();

    // المرشّح يُعرَّف بعنوانه — **ولا معرّف يُكتب بيد**.
    const candidate = page
      .locator("article.card")
      .filter({ hasText: sourceTitle })
      .first();
    await expect(candidate).toBeVisible({ timeout: 30_000 });

    // **الزرّ يُطلب باسمه المُعلَن لا برسمه.** رسمُه «+»، واسمه المُعلَن
    // لقارئ الشاشة «أضِف مرجعًا من مكتبتك: <عنوان المرجع>» — وهو الصواب:
    // زرٌّ اسمه «+» لا يقول لأعمى ما يفعل. فكان الفحص يطلب الرسم فلا يجده،
    // ويُتّهم المنتج بعيبٍ هو فيه محسِن.
    const addButton = candidate.getByRole("button", {
      name: /أضِف مرجعًا من مكتبتك:/,
    });
    await expect(addButton).toBeVisible({ timeout: 30_000 });
    await expect(addButton).toBeEnabled();

    // **وما يُثبت الربط هو ردّ الخادم، لا ما تعرضه الشاشة عن نفسها.**
    const linkResponse = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        response.url().includes("/api/v1/workspace/projects/") &&
        response.url().endsWith("/sources"),
      { timeout: 60_000 },
    );
    await addButton.click();
    const response = await linkResponse;
    expect(response.status(), "linking the source did not return 201").toBe(201);

    // والحال الافتراضية تُقرأ من جسم الردّ — لا تُفترض في العميل.
    const linkedBody = await response.json();
    expect(linkedBody.use_state, "the server did not default to saved_only")
      .toBe("saved_only");
    expect(linkedBody.decided_at, "a fresh link already carries a decision")
      .toBeNull();

    // ثم يُرى في الشاشة كما أعاده الخادم.
    const linked = page.locator("article.card").filter({ hasText: sourceTitle }).first();
    await expect(linked).toBeVisible({ timeout: 30_000 });

    const saved = linked.getByRole("button", { name: "محفوظ فقط" });
    await expect(saved).toBeVisible({ timeout: 30_000 });
    await expect(saved).toHaveAttribute("aria-pressed", "true");
    await expect(
      linked.getByRole("button", { name: "مُدرَج دليلًا" }),
    ).toHaveAttribute("aria-pressed", "false");
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
  // ── ١٤–١٦: مستندٌ يُرفع ثم يُعالَج ثم تُراجَع معرفته ──
  await test.step("upload a parseable synthetic document", async () => {
    await sidebar(page).getByRole("link", { name: "مكتبتي" }).click();
    await page.waitForURL(/\/library/);
    await page.locator('input[type="file"]').setInputFiles({
      name: DOC_NAME,
      mimeType: "text/plain",
      buffer: Buffer.from(DOC_TEXT, "utf-8"),
    });
    await expect(page.getByText("تم الحفظ")).toBeVisible({ timeout: 60_000 });

    // الحال تُقرأ كما هي: «مخزَّن» لا «مُحلَّل».
    const card = page.locator("article.card").filter({ hasText: DOC_NAME }).first();
    await expect(card).toBeVisible({ timeout: 30_000 });
    await expect(card.getByText("لم تُعالَج بعد")).toBeVisible({ timeout: 30_000 });
  });

  await test.step("start document processing from the browser", async () => {
    const card = page.locator("article.card").filter({ hasText: DOC_NAME }).first();
    // **زرٌّ حقيقي، لا استدعاء.** وغيابه فشلٌ لا تخطٍّ.
    const process = card.getByRole("button", { name: "معالجة المستند" });
    await expect(process, "no processing control for a parseable document").toBeVisible();
    await process.click();

    // ولا انتظارٌ بزمنٍ ثابت: تُنتظر حالٌ **مُعلَنة** من الحالات الصادقة.
    const settled = card.getByText(
      /بانتظار مراجعتك|مُعالَج|ينتظر إذن القراءة|تعذّرت المعالجة/,
    );
    await expect(settled, "processing never reached a declared state")
      .toBeVisible({ timeout: 180_000 });

    // فشلُ المعالجة يُعلَن فشلًا — لا يُبتلع ولا يُقرأ نجاحًا.
    expect(await card.innerText(), "document processing failed")
      .not.toContain("تعذّرت المعالجة");

    // **DIC2: إذنُ الاستخراج الخارجي، حدٌّ علمي قائم بذاته.**
    // القراءة المحلية والاستخراج الحتمي تمّا ولم يغادرا الخادم؛ وما يتجاوزه
    // يحتاج إذنًا صريحًا. فإن وقفت المعالجة عنده مُنح **من المتصفح**.
    if ((await card.innerText()).includes("ينتظر إذن القراءة")) {
      await card.getByRole("link", { name: "افتح المراجعة" }).click();
      await page.waitForURL(/\/theses/);
      const grant = page.getByTestId("dic2-grant");
      await expect(grant, "no DIC2 consent control while awaiting consent")
        .toBeVisible({ timeout: 30_000 });
      await grant.click();
      await expect(page.getByTestId("dic2-grant")).toBeHidden({ timeout: 60_000 });

      await sidebar(page).getByRole("link", { name: "مكتبتي" }).click();
      await page.waitForURL(/\/library/);
      const back = page.locator("article.card").filter({ hasText: DOC_NAME }).first();
      await expect(back.getByText(/بانتظار مراجعتك|مُعالَج/))
        .toBeVisible({ timeout: 180_000 });
    }
  });

  await test.step("review the extracted knowledge and approve one fact", async () => {
    const card = page.locator("article.card").filter({ hasText: DOC_NAME }).first();
    await card.getByRole("link", { name: "افتح المراجعة" }).click();
    await page.waitForURL(/\/theses/);

    // شاشة المراجعة تُفتح على الرسالة المستخرَجة من هذا المستند.
    const open = page.getByRole("link", { name: /راجع|مراجعة/ }).first();
    if (await open.count()) await open.click();
    await page.waitForURL(/\/review/, { timeout: 30_000 });

    // **اعتمادٌ واحد على الأقل** — والزرّ إن غاب فذلك فشلٌ يُعلَن.
    const approve = page.getByRole("button", { name: "اعتمد" }).first();
    await expect(approve, "no candidate was available to approve")
      .toBeVisible({ timeout: 60_000 });
    await approve.click();
    await expect(page.getByText(/معتمَدة|اعتُمدت|approved/i).first())
      .toBeVisible({ timeout: 30_000 });
  });

  // ── ١٧–٢٠: سؤالُ بُبريفا AI، وإذن DCC2 مستقلّ عن DIC2 ──
  await test.step("PUBRIVA AI answers with no contract markup", async () => {
    await page.goto(`/${LOCALE}`);
    const ask = page.getByRole("textbox").first();
    const question = "ما الفرق بين المنهج الوصفي وشبه التجريبي؟";
    await ask.fill(question);

    // **الإرسال بالزرّ لا بمفتاح الإدخال.** الحقل `textarea` بلا نموذج ولا
    // معالج مفاتيح، فالضغط على Enter يُدخل سطرًا ولا يرسل شيئًا.
    const send = page.getByRole("button", { name: "ابدأ" });
    await expect(send).toBeEnabled({ timeout: 15_000 });
    await send.click();

    // **إذن المحادثة (DCC2) منفصل عن إذن الاستخراج (DIC2).** فاعتمادُ
    // معرفةٍ من مستند لا يأذن بإرسالها إلى مزوّد لأجل سؤال — إذنان لا
    // يُدمجان ولا يُمنح أحدهما سلفًا.
    const consent = page.getByRole("button", { name: "السماح والإجابة" });
    const answer = page.getByTestId("ai-answer");
    await expect(answer.or(consent)).toBeVisible({ timeout: 180_000 });

    if (await consent.count()) {
      await consent.click();
      // والسؤال الأصلي يُعاد بعد الإذن — لا يُطلب من الباحث كتابته ثانية.
      await expect(answer).toBeVisible({ timeout: 180_000 });
    }

    await expect(answer).toBeVisible({ timeout: 180_000 });
    const text = (await page.getByTestId("ai-answer-text").innerText()).trim();
    expect(text.length, "the answer was empty").toBeGreaterThan(20);
    for (const markup of ["</answer_ar>", "<answer_ar>", "<citations>", "</citations>",
                          "</invoke>", "<invoke"]) {
      expect(text, `contract markup leaked: ${markup}`).not.toContain(markup);
    }
  });

  // ── ٢١–٢٢: خروجٌ ثم دخولٌ ثانٍ ──
  await test.step("sign out, prove server-side revocation, sign back in", async () => {
    // الرمز يُلتقط قبل الخروج ليُختبر بعده — **والمحو المحلي ليس إبطالًا**.
    const refresh = await page.evaluate(() =>
      localStorage.getItem("athera_refresh_token"),
    );
    expect(refresh, "no refresh token before sign-out").toBeTruthy();

    await page.getByRole("button", { name: /خروج|sign out/i }).click();
    await page.waitForURL(/\/login/, { timeout: 30_000 });

    // ٢٢أ — الجلسة المحلية مُسحت.
    expect(await page.evaluate(() => localStorage.getItem("athera_access_token"))).toBeNull();
    expect(await page.evaluate(() => localStorage.getItem("athera_refresh_token"))).toBeNull();

    // ٢٢ب — والرمز مُبطَل **عند الخادم**: من نسخه لا يستطيع إصدار وصولٍ به.
    const revoked = await page.request.post(
      `${process.env.PUBRIVA_API_URL ?? "https://athera-api.fly.dev"}/api/v1/auth/refresh`,
      { data: { refresh_token: refresh }, failOnStatusCode: false },
    );
    expect(revoked.status(), "the refresh token survived sign-out").toBe(401);

    // ٢٣ — ودخولٌ ثانٍ ينجح.
    await signIn(page, EMAIL!, PASSWORD!);
    await expect(page).not.toHaveURL(/\/login/);
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
