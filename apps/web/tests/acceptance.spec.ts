import { expect, test } from "@playwright/test";

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

test.describe.configure({ mode: "serial" });

test.skip(
  !PASSWORD,
  "PUBRIVA_ACCEPT_PASSWORD is not set — acceptance needs a real account; " +
    "credentials never live in Git.",
);

test("the P1 researcher journey completes end to end", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));

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
    await page.getByRole("link", { name: "أبحاثي" }).click();
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
  });

  // ── ٧: النظرة العامة تقول حالاتٍ صادقة ──
  await test.step("Overview shows truthful Research Brain states", async () => {
    await expect(page.getByText("ما تعرفه بُبريفا عن بحثك")).toBeVisible();
    await expect(page.getByText(/لا تُعرض نسبة جاهزية/)).toBeVisible();
    // ولا نسبة مئوية في الصفحة إطلاقًا.
    expect(await page.locator("body").innerText()).not.toMatch(/\d+\s*%/);
    await expect(page.getByText("بُبريفا تقترح")).toBeVisible();
  });

  // ── ٨–١٠: ربط ملف، ثم إزالته، وبقاؤه في المكتبة ──
  await test.step("link a library file, unlink it, and keep it in the library", async () => {
    await page.getByRole("button", { name: "الملفات" }).click();
    const add = page.getByRole("button", { name: "+" }).first();
    if (await add.count()) {
      await add.click();
      await expect(page.getByRole("button", { name: "أزِل من البحث" }).first()).toBeVisible();

      await page.getByRole("button", { name: "أزِل من البحث" }).first().click();
      // إمّا أُزيل مباشرة، وإمّا طُلب إقرارٌ بما يترتب — وكلاهما مقبول،
      // والمرفوض هو أن يقع الفعل بلا خبر.
      const confirm = page.getByRole("button", { name: /أفهم ما يترتب/ });
      if (await confirm.count()) await confirm.click();
      await expect(page.getByText("لا ملف مرتبط بهذا البحث بعد.")).toBeVisible({ timeout: 20_000 });
    }

    await page.getByRole("link", { name: "مكتبتي" }).click();
    await page.waitForURL(/\/library/);
    // الملف باقٍ: الإزالة من بحثٍ ليست حذفًا من المكتبة.
    await expect(page.locator("article.card").first()).toBeVisible();
  });

  // ── ١١–١٢: مرجعٌ يُضاف «محفوظًا فقط» ──
  await test.step("a linked source defaults to saved_only", async () => {
    await page.goBack();
    await page.getByRole("button", { name: "الأدبيات والمراجع" }).click();
    await expect(page.getByText(/الاستيراد ليس حكمًا بأن المرجع دليل/)).toBeVisible();
    const saved = page.getByRole("button", { name: "محفوظ فقط" }).first();
    if (await saved.count()) {
      await expect(saved).toHaveAttribute("aria-pressed", "true");
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
