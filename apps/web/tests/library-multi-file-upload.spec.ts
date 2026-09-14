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

/**
 * يُنشئ مجلَّدًا ثم يفتحه — **بإثبات كلّ خطوةٍ لا بانتظارها**.
 *
 * وهذا موضعُ التقلقل الذي أسقط التشغيلة الأولى في CI: كان الفحص ينقر زرَّ
 * الفتح فورًا بعد الإرسال، فيتّكل على أنّ الطلب تمّ وأنّ قائمةَ المجلَّدات
 * صالحت نفسها. وعلى جهازٍ سريع يصحّ الاتّكال؛ وفي CI تأخّر أحدُهما فانتظر
 * المُحدِّدُ تسعين ثانيةً ثم سقط. **والمهلةُ الأطول لا تُصلح اتّكالًا** —
 * تؤخّر ظهوره فقط.
 *
 * فيُنتظر شاهدان صريحان: ردُّ `POST /files/folders` بـ٢٠١، ثم قراءةُ
 * `GET /files/folders` التي تليه. وعندها يكون الزرُّ موجودًا لأنّ البيانات
 * التي تُنشئه وصلت — لا لأنّ الوقت مضى.
 */
async function createAndOpenFolder(page: Page, name: string): Promise<void> {
  const created = page.waitForResponse(
    (r) => r.url().includes("/api/v1/files/folders")
           && r.request().method() === "POST" && r.status() === 201,
    { timeout: 60_000 });
  const relisted = page.waitForResponse(
    (r) => r.url().includes("/api/v1/files/folders")
           && r.request().method() === "GET" && r.status() === 200,
    { timeout: 60_000 });

  await page.getByTestId("library-new-folder").click();
  // المُحدِّدُ مقصورٌ على نموذج الإنشاء: «اسم المجلد» تُطابق نموذجَ
  // إعادة التسمية أيضًا، و`.first()` تختار بترتيب DOM لا بالقصد.
  const form = page.locator("form.form").filter({ has: page.getByLabel(/اسم المجلد/) });
  await form.getByLabel(/اسم المجلد/).fill(name);
  await form.getByRole("button", { name: /^أنشئ المجلد/ }).click();

  await created;
  await relisted;

  // والآن الزرُّ موجودٌ لأنّ صفَّه وصل — فيُنقر بلا مهلةٍ استثنائية.
  const open = page.getByLabel(`فتح المجلد: ${name}`);
  await expect(open).toBeVisible({ timeout: 30_000 });
  await open.click();

  // وشاهدُ الفتح: بطاقةُ الرفع تقول إنّ الملف ينزل في هذا الرفّ.
  await expect(page.getByText(new RegExp(name)).first())
    .toBeVisible({ timeout: 30_000 });
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

    await createAndOpenFolder(page, folder);

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

// ══ ٨ · ثلاثةُ رفعاتٍ متزامنة تصطدم بـ٤٠١، فتتقاسم تجديدًا واحدًا ══
//
// **والحدُّ يُقاس على مسار الرفع نفسه، لا على نداءٍ آخر يسبقه.**
//
// وكانت النسخةُ الأولى من هذا الفحص تُبطل الرمزَ ثم تفتح المكتبة، فتردّ
// نداءاتُ فتح الصفحة ٤٠١ ويقع التجديد قبل أن يُختار ملفٌّ واحد — فترفع
// الدفعةُ على جلسةٍ مجدَّدة سلفًا. فكان يُثبت «تجديدَ فتح الصفحة يعمل»
// ولا يُثبت شيئًا عن الرفع المتزامن.
//
// فيُجبَر هنا **طلبُ الرفع بعينه** على عبور حدّ ٤٠١: يُردّ ٤٠١ على كلّ
// طلبِ رفعٍ حتى يقع تجديدٌ ناجح، ثم يُترك الطريقُ للخادم الحقيقيّ. وهذا
// أصغرُ ما يكفي — ولا يُمسّ منطقُ المصادقة في المنتج ولا يُستنسخ:
//
//   XHR ← ٤٠١ ← `apiFetch` ← ٤٠١ ← `refreshOnce()` الواحد ← إعادةُ الطلب
//
// والتجديدُ نفسه والرفعُ الناجح يذهبان إلى الخادم الحقيقيّ.
test("ثلاثُ رفعاتٍ تصطدم بـ٤٠١ فتتقاسم تجديدًا واحدًا", async ({ page }) => {
  const NAMES = [1, 2, 3].map((n) => `${RUN}-race-${n}.txt`);

  /** طلباتُ الرفع التي رُدّت ٤٠١ قبل التجديد — مفهرسةً باسم الملف. */
  const rejected: string[] = [];
  /** طلباتُ الرفع التي بلغت الخادمَ فنجحت. */
  let stored201 = 0;
  const refreshes: string[] = [];
  let refreshed = false;

  page.on("response", (r) => {
    if (r.url().endsWith("/api/v1/auth/refresh") && r.request().method() === "POST") {
      refreshes.push(String(r.status()));
      if (r.status() === 200) refreshed = true;
    }
    if (r.url().endsWith("/api/v1/files/upload") && r.status() === 201) stored201 += 1;
  });

  await page.goto(`/${EN}/login`);
  await page.getByLabel(/email/i).fill(ACCOUNT);
  await page.locator("#login-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").click();
  await page.waitForURL(`**/${EN}`, { timeout: 60_000 });

  await page.goto(`/${AR}/library`);
  await expect(page.getByRole("button", { name: /اختر ملفات/ }))
    .toBeVisible({ timeout: 60_000 });

  // الحدُّ يُنصَب بعد أن تستقرّ الصفحة، فلا يُستهلك على نداءٍ آخر.
  await page.route("**/api/v1/files/upload", async (route) => {
    if (refreshed) {
      await route.continue();
      return;
    }
    const body = route.request().postData() ?? "";
    rejected.push(NAMES.find((n) => body.includes(n)) ?? "unknown");
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      headers: { "content-language": "ar" },
      body: JSON.stringify({
        error: {
          code: "auth.token_expired", locale: "ar",
          message: "انتهت صلاحية الجلسة، يرجى تسجيل الدخول مجددًا.",
          messages: {
            ar: "انتهت صلاحية الجلسة، يرجى تسجيل الدخول مجددًا.",
            en: "Your session has expired. Please sign in again.",
          },
        },
      }),
    });
  });

  await page.locator('input[type="file"]').first()
    .setInputFiles(NAMES.map((n) => synthetic(n, 2)));

  await expect(page.getByTestId("upload-row")).toHaveCount(3);
  await expect
    .poll(async () => await page.locator('[data-upload-state="stored"]').count(),
          { timeout: 120_000, message: "الدفعةُ لم تُحفظ بعد التجديد" })
    .toBe(3);

  // ── العدّادات، صريحةً ──
  //
  // وتُطبع كما هي: حارسٌ يفشل بـ«توقّعت 3 فوجدت 2» يترك القارئ يخمّن
  // البقيّة، والأرقامُ مطبوعةً تقول القصّة كلَّها في سطر.
  console.log(`[auth-race] initial-401=${rejected.length}`
              + ` files=${NAMES.filter((n) => rejected.includes(n)).length}`
              + ` refresh=${refreshes.length} stored201=${stored201}`);


  // ١ · كلُّ ملفٍ من الثلاثة اصطدم بـ٤٠١ على طلب رفعه هو.
  const initial = NAMES.filter((n) => rejected.includes(n));
  expect(initial, `الملفاتُ التي عبرت حدَّ ٤٠١: ${initial.join(", ")}`)
    .toHaveLength(3);
  expect(rejected, "طلبُ رفعٍ رُدّ ٤٠١ ولم يُعرف ملفُّه").not.toContain("unknown");

  // **والموجةُ الثانية جزءٌ من التصميم لا خللٌ فيه.** فمسارُ المنتج هو
  // XHR ← ٤٠١ ← `apiFetch` ← ٤٠١ ← تجديد ← إعادة. فمحاولاتُ `apiFetch`
  // تعبر الحدَّ أيضًا، وعددُها يتبع أيَّ نداءٍ أنهى التجديد أوّلًا — فيُطلب
  // الحدُّ الأدنى المؤكَّد: ثلاثةٌ على الأقل، واحدةٌ لكلّ ملف.
  expect(rejected.length,
         `طلباتُ الرفع التي عبرت حدَّ ٤٠١: ${rejected.length}`)
    .toBeGreaterThanOrEqual(3);

  // ٢ · وتجديدٌ واحد لا أكثر — وهو الحدُّ المقصود.
  expect(refreshes, `ردودُ التجديد: ${refreshes.join(", ")}`).toEqual(["200"]);

  // ٣ · وثلاثةُ رفعاتٍ نجحت على الخادم الحقيقيّ — لا أكثر، فلا تكرار.
  expect(stored201, "عددُ الرفعات الناجحة").toBe(3);

  // ٤ · والجلسةُ باقية: لا قذفَ إلى صفحة الدخول.
  expect(page.url(), "الجلسةُ ضاعت بدل أن تُجدَّد").toContain("/library");
  await expect(page.getByRole("button", { name: /اختر ملفات/ })).toBeVisible();

  // ٥ · ولا ملفَّ مكرَّرًا في المكتبة.
  for (const name of NAMES) {
    await expect
      .poll(async () =>
              await page.locator("article.card").filter({ hasText: name }).count(),
            { timeout: 30_000, message: `${name} مكرَّرٌ أو غائب` })
      .toBe(1);
  }

  // ٦ · ولا تجديدَ ثانيًا بعد أن استقرّ كلُّ شيء.
  expect(refreshes).toHaveLength(1);
});

// ══ ٩ · التنقّلُ أثناء الدفعة لا يُظهر ملفاتِ رفٍّ في رفٍّ آخر ══
//
// **والوجهةُ صحيحةٌ أصلًا — المعروضُ هو ما كان يكذب.**
//
// `folder_id` مثبَّتٌ وقتَ الاختيار، فالخادمُ يُنزل كلَّ ملفٍ في مجلَّده. لكنّ
// الإدراج المتفائل كان يضع الملفَّ المكتمل في **القائمة المعروضة** أيًّا
// كانت: فمن اختار عشرةً في «أ» ثم فتح «ب» وهي تُرفع رأى ملفاتَ «أ» تظهر
// في «ب» — بطاقاتٌ كاملة بأفعالها في نطاقٍ لا تنتمي إليه، ثم تمحوها
// المصالحةُ بعد ثوانٍ.
//
// **والفحصُ ينظر أثناء الجريان لا بعد الاستقرار.** مصالحةُ آخر الدفعة
// تُصلح المعروضَ في كلّ الأحوال، فلو فُحص بعدها لمرّ العطبُ كما هو.
test("دفعةُ رفٍّ لا تظهر في رفٍّ آخر أثناء جريانها", async ({ page }) => {
  const A = `${RUN}-A`;
  const B = `${RUN}-B`;
  const NAMES = [1, 2, 3, 4, 5, 6].map((n) => `${RUN}-crossfolder-${n}.txt`);

  await page.goto(`/${EN}/login`);
  await page.getByLabel(/email/i).fill(ACCOUNT);
  await page.locator("#login-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").click();
  await page.waitForURL(`**/${EN}`, { timeout: 60_000 });

  await page.goto(`/${AR}/library`);
  await createAndOpenFolder(page, A);
  // يُعاد إلى الجذر ليُنشأ «ب» بجانب «أ» لا داخله.
  await page.goto(`/${AR}/library`);
  await createAndOpenFolder(page, B);

  // ── الدفعةُ تبدأ في «أ» ──
  await page.goto(`/${AR}/library`);
  await page.getByLabel(`فتح المجلد: ${A}`).click();
  await expect(page.getByText(new RegExp(A)).first()).toBeVisible({ timeout: 30_000 });

  // **ويُبطَّأ الرفعُ ليبقى جاريًا أثناء التنقّل** — تأخيرٌ في الشبكة لا
  // اعتراضٌ للردّ: الطلبُ يمضي إلى الخادم الحقيقيّ ويُحفظ فعلًا.
  await page.route("**/api/v1/files/upload", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1_200));
    await route.continue();
  });

  await page.locator('input[type="file"]').first()
    .setInputFiles(NAMES.map((n) => synthetic(n, 2)));
  await expect(page.getByTestId("upload-row")).toHaveCount(6);

  // ── يُنتقل إلى «ب» والدفعةُ ما زالت تجري ──
  await expect
    .poll(async () => await page.locator('[data-upload-state="uploading"]').count(),
          { timeout: 30_000, message: "لم يبدأ رفعٌ إطلاقًا" })
    .toBeGreaterThan(0);

  // **والتنقّلُ داخل الصفحة لا بإعادة تحميلها.** `goto` يُعيد بناء الصفحة
  // فيُلغي الدفعةَ الجارية — وهي بعينها موضوعُ الفحص. فيُستعمل مسارُ
  // الباحث: خُطوةُ الجذر في شريط المسار، ثم فتحُ «ب».
  await page.getByLabel("فتح المجلد: مكتبتي").click();
  await page.getByLabel(`فتح المجلد: ${B}`).click();
  await expect(page.getByText(new RegExp(B)).first()).toBeVisible({ timeout: 30_000 });

  // **وهنا الفحص:** ما بقي من الدفعة يكتمل ونحن في «ب» — فلا بطاقةَ من
  // ملفات «أ» تظهر هنا، ولا للحظةٍ واحدة. ويُراقَب حتى تستقرّ الدفعةُ كلُّها.
  let leaked = "";
  for (let i = 0; i < 40; i += 1) {
    const cards = await page.locator("article.card")
      .filter({ hasText: `${RUN}-crossfolder-` }).count();
    if (cards > 0) {
      leaked = `ظهرت ${cards} بطاقةً من ملفات «أ» في «ب»`;
      break;
    }
    const settled = await page.locator('[data-upload-state="stored"]').count();
    if (settled === 6) break;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  expect(leaked, leaked || "لا تسريب").toBe("");

  // والدفعةُ اكتملت فعلًا — فالفحصُ لم يمرّ لأنّ شيئًا لم يقع.
  await expect
    .poll(async () => await page.locator('[data-upload-state="stored"]').count(),
          { timeout: 120_000, message: "الدفعةُ لم تكتمل" })
    .toBe(6);

  // و«ب» ما زال خاليًا من ملفات «أ» بعد الاستقرار والمصالحة.
  await expect
    .poll(async () =>
            await page.locator("article.card")
              .filter({ hasText: `${RUN}-crossfolder-` }).count(),
          { timeout: 30_000, message: "المصالحةُ أدخلت ملفاتِ «أ» إلى «ب»" })
    .toBe(0);

  // ── والعودةُ إلى «أ» تجدها كلَّها ──
  await page.unroute("**/api/v1/files/upload");
  await page.goto(`/${AR}/library`);
  await page.getByLabel(`فتح المجلد: ${A}`).click();
  for (const name of NAMES) {
    await expect
      .poll(async () =>
              await page.locator("article.card").filter({ hasText: name }).count(),
            { timeout: 60_000, message: `${name} ليس في «أ»` })
      .toBe(1);
  }

  // ── والجذرُ لا يحملها ──
  await page.goto(`/${AR}/library`);
  await expect
    .poll(async () =>
            await page.locator("article.card")
              .filter({ hasText: `${RUN}-crossfolder-` }).count(),
          { timeout: 30_000, message: "ملفاتُ «أ» ظهرت في الجذر" })
    .toBe(0);
});

// ══ ١٠ · حدُّ التنقّل نفسه: رفعٌ يكتمل في لحظة العبور من «أ» إلى «ب» ══
//
// **والنافذةُ التي تُغلق هنا أضيقُ من سابقتها.**
//
// كان المرجعُ يُضبط في `useEffect` بعد تغيّر `folderId`، والأثرُ يجري بعد
// الإيداع — فتبقى لحظةٌ: التنقّلُ بدأ، والمرجعُ ما زال «أ»، ورفعٌ من «أ»
// يكتمل فيها فيُدرَج في القائمة التي تصير «ب». وصارت النيّةُ تُسجَّل
// تزامنيًّا في `openFolder` قبل `setFolderId`، فلا تتعلّق الصحّةُ بتوقيت أثر.
//
// **والفحصُ يمسك اللحظةَ بيده ولا ينتظرها.** طلبُ رفعٍ واحد يُحتجز مفتوحًا،
// فلا يكتمل حتى يُفرَج عنه؛ ويُفرَج عنه بعد إطلاق نقرة التنقّل مباشرةً —
// لا بعد نومٍ مقدَّر. فالتوقيتُ مصنوعٌ لا مُتَمنّى.
test("رفعٌ يكتمل عند عبور الحدّ لا يظهر في الرفّ الجديد", async ({ page }) => {
  const A = `${RUN}-bA`;
  const B = `${RUN}-bB`;
  const HELD = `${RUN}-boundary-held.txt`;
  const NAMES = [HELD, `${RUN}-boundary-2.txt`, `${RUN}-boundary-3.txt`];

  await page.goto(`/${EN}/login`);
  await page.getByLabel(/email/i).fill(ACCOUNT);
  await page.locator("#login-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").click();
  await page.waitForURL(`**/${EN}`, { timeout: 60_000 });

  await page.goto(`/${AR}/library`);
  await createAndOpenFolder(page, A);
  await page.goto(`/${AR}/library`);
  await createAndOpenFolder(page, B);

  // ── الدفعةُ تبدأ في «أ» ──
  await page.goto(`/${AR}/library`);
  await page.getByLabel(`فتح المجلد: ${A}`).click();
  await expect(page.getByText(new RegExp(A)).first()).toBeVisible({ timeout: 30_000 });

  // **احتجازُ إتمامٍ واحد.** الطلبُ يمضي إلى الخادم الحقيقيّ ويُحفظ فعلًا —
  // المحتجَزُ هو لحظةُ وصول ردّه إلى المتصفّح، وهي بالضبط لحظةُ الإدراج.
  let release!: () => void;
  const released = new Promise<void>((resolve) => { release = resolve; });
  let captured!: () => void;
  const inFlight = new Promise<void>((resolve) => { captured = resolve; });
  let heldOnce = false;

  await page.route("**/api/v1/files/upload", async (route) => {
    const body = route.request().postData() ?? "";
    if (!heldOnce && body.includes(HELD)) {
      heldOnce = true;
      captured();
      await released;
    }
    await route.continue();
  });

  await page.locator('input[type="file"]').first()
    .setInputFiles(NAMES.map((n) => synthetic(n, 2)));
  await expect(page.getByTestId("upload-row")).toHaveCount(3);

  // الطلبُ المحتجَز صار في الطيران — واللحظةُ صارت في يد الفحص.
  await inFlight;

  // ── العبور: «أ» ← الجذر ← «ب»، بالمسار الحقيقيّ داخل الصفحة ──
  await page.getByLabel("فتح المجلد: مكتبتي").click();
  const entering = page.getByLabel(`فتح المجلد: ${B}`).click();

  // **ويُفرَج عنه عند الحدّ** — قبل أن يُعوَّل على أيّ أثرٍ سلبيّ.
  release();
  await entering;

  await expect(page.getByText(new RegExp(B)).first()).toBeVisible({ timeout: 30_000 });

  // ── ولا بطاقةَ من «أ» تظهر في «ب»، ولا للحظة ──
  let leaked = "";
  for (let i = 0; i < 60; i += 1) {
    const cards = await page.locator("article.card")
      .filter({ hasText: `${RUN}-boundary-` }).count();
    if (cards > 0) {
      leaked = `ظهرت ${cards} بطاقةً من «أ» في «ب» عند الحدّ`;
      break;
    }
    if (await page.locator('[data-upload-state="stored"]').count() === 3) break;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  expect(leaked, leaked || "لا تسريب عند الحدّ").toBe("");

  // والدفعةُ اكتملت فعلًا — فالفحصُ لم يمرّ لأنّ شيئًا لم يقع.
  await expect
    .poll(async () => await page.locator('[data-upload-state="stored"]').count(),
          { timeout: 120_000, message: "الدفعةُ لم تكتمل" })
    .toBe(3);

  // و«ب» نظيفٌ بعد الاستقرار والمصالحة أيضًا.
  await expect
    .poll(async () =>
            await page.locator("article.card")
              .filter({ hasText: `${RUN}-boundary-` }).count(),
          { timeout: 30_000, message: "المصالحةُ أدخلت ملفاتِ «أ» إلى «ب»" })
    .toBe(0);

  // ── والعودةُ إلى «أ» تجدها كلَّها، ومنها المحتجَز ──
  await page.unroute("**/api/v1/files/upload");
  await page.goto(`/${AR}/library`);
  await page.getByLabel(`فتح المجلد: ${A}`).click();
  for (const name of NAMES) {
    await expect
      .poll(async () =>
              await page.locator("article.card").filter({ hasText: name }).count(),
            { timeout: 60_000, message: `${name} ليس في «أ»` })
      .toBe(1);
  }

  // ── والجذرُ نظيف ──
  await page.goto(`/${AR}/library`);
  await expect
    .poll(async () =>
            await page.locator("article.card")
              .filter({ hasText: `${RUN}-boundary-` }).count(),
          { timeout: 30_000, message: "ملفاتُ «أ» ظهرت في الجذر" })
    .toBe(0);
});
