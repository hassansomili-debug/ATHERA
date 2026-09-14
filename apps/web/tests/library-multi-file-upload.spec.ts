import { expect, test, type Page } from "@playwright/test";

/**
 * رفعٌ متعدّد في المكتبة | Library multi-file upload, on a real stack.
 *
 * **ولا اعتراضَ لنقطة الرفع في هذه الرقعة.** الطابورُ نفسه هو المقصود
 * بالإثبات: حدُّ التزامن، واستقلالُ حالة كلّ ملف، وأن سقوطَ واحدٍ لا
 * يُسقط الدفعة. ولو اعتُرض `POST /files/upload` بردٍّ مصنوع لصار الفحصُ
 * يُثبت المُعترِض لا المنتج — فيمرّ على طابورٍ معطوب.
 *
 * فالرفعُ يجري إلى خادمٍ حقيقيّ وقاعدةٍ حقيقية وتخزينٍ حقيقيّ، والملفاتُ
 * اصطناعيةٌ صغيرة لا تحمل بيانات أحد.
 *
 * والإخفاقُ الوحيد المصنوع هو ملفٌّ **يرفضه الخادم بحقّ**: امتدادٌ غير
 * مدعوم. فالرفضُ ردُّ المنتج على مُدخلٍ حقيقيّ، لا اعتراضًا يتظاهر بالرفض.
 */

const AR = "ar";
const EN = "en";

const RUN = `mfu-${Date.now().toString(36)}`;
const ACCOUNT = `${RUN}@example.com`;
const PASSWORD = "MultiFile-9f3b!";

/** ملفٌّ اصطناعيّ — والحجمُ كافٍ ليُقاس تقدّمٌ ولا يُثقل تشغيلة. */
const synthetic = (name: string, kb = 24) => ({
  name,
  mimeType: "text/plain",
  buffer: Buffer.from(`PUBRIVA multi-file test ${RUN}\n`.repeat(kb * 14), "utf-8"),
});

function watchServerErrors(page: Page): string[] {
  const seen: string[] = [];
  page.on("response", (r) => {
    if (r.status() >= 500) seen.push(`${r.status()} ${r.url()}`);
  });
  return seen;
}

/** أعلى تزامنٍ رُصد فعلًا أثناء الدفعة — يُقاس ولا يُفترض. */
async function watchPeakConcurrency(page: Page): Promise<() => number> {
  let peak = 0;
  const tick = async () => {
    try {
      const now = await page.locator('[data-upload-state="uploading"]').count();
      if (now > peak) peak = now;
    } catch {
      /* الصفحة تُغلق في آخر الفحص — ولا يُفشل القياسُ الفحص. */
    }
  };
  const timer = setInterval(() => void tick(), 60);
  // يُوقف عند انتهاء الفحص عبر الدالّة المُعادة.
  return () => {
    clearInterval(timer);
    return peak;
  };
}

test.describe.configure({ mode: "serial" });

test("المكتبة ترفع دفعةً واحدة، والتحليل يبقى ملفًا واحدًا", async ({ page }) => {
  const serverErrors = watchServerErrors(page);

  await test.step("حسابٌ حقيقيّ يُنشأ من النموذج", async () => {
    await page.goto(`/${EN}/register`);
    await page.locator("#reg-name").fill("Multi File");
    await page.locator("#reg-email").fill(ACCOUNT);
    await page.locator("#reg-password").fill(PASSWORD);
    await page.locator("form button[type=submit]").click();
    await page.waitForURL(`**/${EN}`, { timeout: 60_000 });
  });

  // ══ ١ · مدخلُ المكتبة يقبل التعدّد، ومدخلُ التحليل لا ══
  await test.step("مدخلُ المكتبة `multiple`، ومدخلُ التحليل مفرد", async () => {
    await page.goto(`/${AR}/library`);
    const libraryInput = page.locator('input[type="file"]').first();
    await expect(libraryInput).toHaveAttribute("multiple", "");

    await page.goto(`/${AR}/analysis`);
    const analysisInput = page.locator('input[type="file"]').first();
    // **والغيابُ يُقاس.** فـ`multiple` غيرُ موجودةٍ لا فارغة.
    expect(await analysisInput.getAttribute("multiple")).toBeNull();
  });

  // ══ ٢ · خمسةُ ملفاتٍ تُختار مرّةً واحدة، فتُرفع كلُّها ══
  await test.step("خمسةُ ملفاتٍ في اختيارٍ واحد تُحفظ كلُّها", async () => {
    await page.goto(`/${AR}/library`);
    const stop = await watchPeakConcurrency(page);

    const names = [1, 2, 3, 4, 5].map((n) => `${RUN}-batch-${n}.txt`);
    await page.locator('input[type="file"]').first()
      .setInputFiles(names.map((n) => synthetic(n)));

    // خمسةُ صفوفٍ ظهرت فورًا — الطابورُ مرئيٌّ قبل أن يبدأ الرفع.
    await expect(page.getByTestId("upload-row")).toHaveCount(5);

    // ثم تستقرّ كلُّها على «تم الحفظ».
    await expect
      .poll(async () =>
              await page.locator('[data-upload-state="stored"]').count(),
            { timeout: 120_000, message: "الدفعةُ لم تستقرّ" })
      .toBe(5);

    const peak = stop();
    // ══ ٣ · ولا أكثر من ثلاثةٍ في وقتٍ واحد ══
    expect(peak, `أعلى تزامنٍ مرصود: ${peak}`).toBeLessThanOrEqual(3);
    expect(peak, "لم يُرصد رفعٌ جارٍ إطلاقًا — القياسُ لم يعمل").toBeGreaterThan(0);

    // والملخّصُ صادق: خمسةٌ من خمسة.
    await expect(page.getByTestId("upload-batch-summary")).toContainText("5 من 5");

    // وكلُّها ظهرت في المكتبة نفسها.
    for (const name of names) {
      await expect
        .poll(async () =>
                await page.locator("article.card").filter({ hasText: name }).count(),
              { timeout: 30_000, message: `${name} لم يبلغ المكتبة` })
        .toBe(1);
    }
  });

  // ══ ٤ · سقوطُ ملفٍ لا يُسقط الدفعة، وإعادةُ المحاولة لصفّه وحده ══
  await test.step("ملفٌّ يرفضه الخادم لا يمنع بقيةَ الدفعة", async () => {
    await page.goto(`/${AR}/library`);

    const good = [1, 2].map((n) => synthetic(`${RUN}-mixed-${n}.txt`));
    // امتدادٌ لا يقبله الخادم — رفضٌ حقيقيّ لا مُعترَض.
    const bad = {
      name: `${RUN}-rejected.exe`,
      mimeType: "application/octet-stream",
      buffer: Buffer.from("not a research file", "utf-8"),
    };

    await page.locator('input[type="file"]').first()
      .setInputFiles([good[0], bad, good[1]]);

    await expect(page.getByTestId("upload-row")).toHaveCount(3);

    // الصالحان حُفظا، والمرفوضُ أخفق — والدفعةُ لم تتوقّف عنده.
    await expect
      .poll(async () => {
        const stored = await page.locator('[data-upload-state="stored"]').count();
        const failed = await page.locator('[data-upload-state="failed"]').count();
        return `stored=${stored} failed=${failed}`;
      }, { timeout: 120_000, message: "الدفعةُ المختلطة لم تستقرّ" })
      .toBe("stored=2 failed=1");

    // ورسالةُ الخادم الحقيقية تُعرض — لا «فشل الطلب» عامّة.
    const failedRow = page.locator('[data-upload-state="failed"]').first();
    await expect(failedRow).toBeVisible();

    // وزرُّ إعادة المحاولة لهذا الصفّ وحده.
    const retry = page.getByTestId("upload-retry");
    await expect(retry).toHaveCount(1);
    await retry.click();

    // يُعاد فيُخفق مرّةً أخرى — فالخادم يرفضه بحقّ، ولا تكرارَ تلقائيّ بلا حدّ.
    await expect
      .poll(async () => {
        const stored = await page.locator('[data-upload-state="stored"]').count();
        const failed = await page.locator('[data-upload-state="failed"]').count();
        return `stored=${stored} failed=${failed}`;
      }, { timeout: 60_000, message: "إعادةُ المحاولة لم تستقرّ" })
      .toBe("stored=2 failed=1");
  });

  // ══ ٤ب · والدفعةُ تنزل في المجلَّد الذي يقف فيه صاحبُها ══
  await test.step("الدفعةُ كلُّها تنزل في المجلَّد الحاليّ لا في الجذر", async () => {
    const folder = `${RUN}-folder`;
    await page.goto(`/${AR}/library`);

    await page.getByRole("button", { name: /مجلد جديد/ }).first().click();
    await page.getByLabel(/اسم المجلد/).first().fill(folder);
    await page.getByRole("button", { name: /^أنشئ المجلد/ }).first().click();

    // يُفتح المجلَّد بزرِّه المعنون باسمه — لا بأوّل زرٍّ يشبهه.
    await page.getByLabel(`فتح المجلد: ${folder}`).click();

    // **والتنقّلُ حالةٌ في العميل لا مُعامِلٌ في الرابط.** فالشاهدُ ما يراه
    // الباحث: بطاقةُ الرفع تقول في أيّ مجلَّدٍ ينزل ملفُه.
    await expect(page.getByText(new RegExp(`${folder}`)).first())
      .toBeVisible({ timeout: 30_000 });

    const names = [1, 2, 3].map((n) => `${RUN}-infolder-${n}.txt`);
    await page.locator('input[type="file"]').first()
      .setInputFiles(names.map((n) => synthetic(n, 2)));

    await expect
      .poll(async () => await page.locator('[data-upload-state="stored"]').count(),
            { timeout: 120_000, message: "دفعةُ المجلَّد لم تُحفظ" })
      .toBe(3);

    // **وكلُّها هنا** — لا في الجذر، ولا مقسومةً على موضعين.
    for (const name of names) {
      await expect
        .poll(async () =>
                await page.locator("article.card").filter({ hasText: name }).count(),
              { timeout: 30_000, message: `${name} ليس في المجلَّد` })
        .toBe(1);
    }

    // والجذرُ لا يحملها.
    await page.goto(`/${AR}/library`);
    await expect
      .poll(async () =>
              await page.locator("article.card")
                .filter({ hasText: `${RUN}-infolder-` }).count(),
            { timeout: 30_000, message: "ملفاتُ المجلَّد ظهرت في الجذر" })
      .toBe(0);
  });

  // ══ ٥ · الزائدُ على عشرين يُرفض بصراحة ولا يُقتطع ══
  await test.step("واحدٌ وعشرون ملفًا تُرفض برسالةٍ تُقرأ", async () => {
    await page.goto(`/${AR}/library`);
    const many = Array.from({ length: 21 },
                            (_, i) => synthetic(`${RUN}-over-${i}.txt`, 1));
    await page.locator('input[type="file"]').first().setInputFiles(many);

    await expect(page.getByTestId("upload-too-many")).toBeVisible();
    await expect(page.getByTestId("upload-too-many")).toContainText("21");
    // ولا صفَّ واحدًا بدأ: الرفضُ كلّيّ.
    await expect(page.getByTestId("upload-row")).toHaveCount(0);
  });

  // ══ ٦ · شاشةُ التحليل تبقى كما كانت ══
  await test.step("التحليل يرفع ملفًا واحدًا بالعرض القديم", async () => {
    await page.goto(`/${AR}/analysis`);
    await page.locator('input[type="file"]').first()
      .setInputFiles(synthetic(`${RUN}-analysis.txt`));
    await expect(page.getByText("تم الحفظ")).toBeVisible({ timeout: 120_000 });
    // ولا طابورَ في العرض المفرد.
    await expect(page.getByTestId("upload-batch")).toHaveCount(0);
  });

  expect(serverErrors, `ردود ≥٥٠٠: ${serverErrors.join(", ")}`).toEqual([]);
});

// ══ ٧ · الإنجليزية تُصيَّر، والعرضُ يصمد على ٣٧٥px ══
test("الإنجليزية وعرضُ الهاتف", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });

  await page.goto(`/${EN}/login`);
  // بالمعرّفات لا بالتسمية: «Password» تُطابق المدخلَ وزرَّ الإظهار معًا.
  await page.getByLabel(/email/i).fill(ACCOUNT);
  await page.locator("#login-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").click();
  await page.waitForURL(`**/${EN}`, { timeout: 60_000 });

  await page.goto(`/${EN}/library`);
  // النصُّ الإنجليزيّ من الكتالوج لا من المكوّن.
  await expect(page.getByRole("button", { name: /Choose files/ })).toBeVisible();

  const names = Array.from({ length: 6 },
                           (_, i) => `${RUN}-a-very-long-synthetic-filename-${i}.txt`);
  await page.locator('input[type="file"]').first()
    .setInputFiles(names.map((n) => synthetic(n, 2)));

  await expect(page.getByTestId("upload-row")).toHaveCount(6);
  await expect(page.getByTestId("upload-batch-summary")).toBeVisible();

  // **ولا تمريرَ أفقيًّا**: أسماءٌ طويلة في ستّة صفوف على شاشةٍ ضيّقة.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, "الصفحةُ تُدفع خارج الشاشة على ٣٧٥px").toBeLessThanOrEqual(1);

  await expect
    .poll(async () => await page.locator('[data-upload-state="stored"]').count(),
          { timeout: 120_000 })
    .toBe(6);

  await expect(page.getByTestId("upload-batch-summary")).toContainText("6 of 6");
});

// ══ ٨ · تجديدٌ واحد في الطيران مهما تعدّدت ردود ٤٠١ ══
test("٤٠١ متزامنة تُنتج تجديدًا واحدًا، ثم ترفع الدفعة", async ({ page }) => {
  const refreshCalls: number[] = [];
  page.on("request", (r) => {
    if (r.url().endsWith("/api/v1/auth/refresh") && r.method() === "POST") {
      refreshCalls.push(Date.now());
    }
  });

  await page.goto(`/${EN}/login`);
  // بالمعرّفات لا بالتسمية: «Password» تُطابق المدخلَ وزرَّ الإظهار معًا.
  await page.getByLabel(/email/i).fill(ACCOUNT);
  await page.locator("#login-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").click();
  await page.waitForURL(`**/${EN}`, { timeout: 60_000 });

  /**
   * **رمزُ وصولٍ باطل ورمزُ تحديثٍ صالح.**
   *
   * و`getAccessToken` تقرأ ذاكرةَ الوحدة قبل المخزن، فإبطالُ المخزن وحده
   * لا يكفي — إعادةُ التحميل تُفرّغ الذاكرة فيُقرأ الباطل.
   *
   * وما رُصد فعلًا في سجلّ الخادم أقوى من المقصود: **ثلاثةُ ٤٠١ على
   * `POST /files/upload` نفسه، وتجديدٌ واحد في السجلّ كلِّه، وثلاثةُ ملفاتٍ
   * حُفظت**. وهذا هو الحدُّ بعينه: رفعٌ متزامن برمزٍ منتهٍ يتقاسم تجديدًا
   * واحدًا، فلا يُبطل رمزُ تحديثٍ أخاه ولا تُمحى جلسةٌ صالحة.
   *
   * والعددُ يُقاس على الطلبات لا على مصدرها: أيًّا كان أوّلُ من ردّ ٤٠١ —
   * نداءُ فتح الصفحة أو الرفعُ — فالتجديدُ واحد.
   */
  await page.evaluate(() => {
    window.localStorage.setItem("athera_access_token", "not-a-valid-jwt");
    window.localStorage.setItem("athera_token_expiry", String(Date.now() + 600_000));
  });

  refreshCalls.length = 0;
  await page.goto(`/${AR}/library`);

  // الجلسةُ صمدت: القائمةُ ظهرت بلا قذفٍ إلى صفحة الدخول.
  await expect(page.getByRole("button", { name: /اختر ملفات/ }))
    .toBeVisible({ timeout: 60_000 });
  expect(page.url(), "الجلسةُ ضاعت بدل أن تُجدَّد").toContain("/library");

  // **وتجديدٌ واحد لا أكثر** — والحارسُ الوحيد في الطيران يُثبت نفسه هنا.
  // ولا صفر: لو لم يُجدَّد شيءٌ لكانت النداءات نجحت، فلا يكون الفحصُ فحصًا.
  expect(refreshCalls.length,
         `عددُ نداءات التجديد: ${refreshCalls.length}`).toBe(1);

  // ثم ترفع الدفعةُ على الجلسة المجدَّدة.
  const names = [1, 2, 3].map((n) => `${RUN}-refresh-${n}.txt`);
  await page.locator('input[type="file"]').first()
    .setInputFiles(names.map((n) => synthetic(n, 2)));
  await expect
    .poll(async () => await page.locator('[data-upload-state="stored"]').count(),
          { timeout: 120_000, message: "الدفعةُ بعد التجديد لم تُحفظ" })
    .toBe(3);

  // ولم يُجدَّد ثانيةً بلا داعٍ.
  expect(refreshCalls.length).toBe(1);
});
