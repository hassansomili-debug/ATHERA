import { expect, test, type Page } from "@playwright/test";

/**
 * فصلُ المجالات: ثلاثةُ أشياء تحمل كلمةَ «فرصة» ولا تُخلط | RC-T1C.
 *
 * **العطبُ الذي تحرسه هذه الرقعة كُشف قبل كتابة سطرٍ من الواجهة.** كان
 * المسارُ المقترحُ للاستقطاب `/{locale}/opportunities` — وهو مأخوذٌ
 * لخريطة فرص النشر: شاشةٌ علميةٌ قائمة تعرض جاهزيةَ ورقةٍ وتداخلَها
 * وبوابةَ حقوقها. فلو أُخذ لَوجد الباحثُ خلف رابطٍ يعرفه شيئًا آخر.
 *
 * فالمجالات ثلاثة:
 *
 *   `/{locale}/opportunities`                      خريطةُ فرص النشر.
 *   `/{locale}/portfolio/{id}/research-opportunities`  فجواتٌ علمية.
 *   `/{locale}/collaboration-opportunities`        **دعواتُ التعاون.**
 *
 * ويُحرس بثلاثة أشياء تُقاس في متصفّح: عنوانُ كلّ صفحة، وما **لا** يظهر
 * فيها، ووجهةُ عنصر التنقّل. **والأخيرةُ هي بيتُ العطب**: عنصرٌ يقصد
 * `opportunities` يُهبط الباحثَ على خريطة النشر وهو يطلب تعاونًا —
 * والصفحتان تعملان، فلا خطأَ يُرى ولا ٤٠٤ يُقال.
 *
 * ولا تلزمها بياناتُ استقطاب: هي عن **المسارات** لا عن الإعلانات.
 */
const AR = "ar";
const EN = "en";

const RUN = `dom-${Date.now().toString(36)}`;
const ACCOUNT = `${RUN}@example.com`;
const PASSWORD = "Domain-Guard-9f3b!";

function watch(page: Page): string[] {
  const serverErrors: string[] = [];
  page.on("response", (r) => {
    if (r.status() >= 500) serverErrors.push(`${r.status()} ${r.url()}`);
  });
  return serverErrors;
}

async function register(page: Page) {
  await page.goto(`/${EN}/register`);
  await page.locator("#reg-name").fill("Domain Guard");
  await page.locator("#reg-email").fill(ACCOUNT);
  await page.locator("#reg-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").click();
  await page.waitForURL(`**/${EN}`, { timeout: 60_000 });
}

test("مجالاتُ «الفرص» الثلاثة لا تتداخل | the three opportunity domains stay apart",
  async ({ page }) => {
    test.setTimeout(180_000);
    const serverErrors = watch(page);
    await register(page);

    // ── ١ · خريطةُ فرص النشر باقيةٌ كما كانت ──
    //
    // **ولا بياناتِ استقطاب تُطلب لها** ولا بطاقةَ تعاونٍ تظهر فيها.
    await test.step("the publication map still renders at /opportunities", async () => {
      await page.goto(`/${AR}/opportunities`);
      await expect(page).toHaveURL(new RegExp(`/${AR}/opportunities$`));
      // عنوانُها من كتالوجها هو: «فرص النشر» — لا «الفرص البحثية».
      await expect(page.getByRole("heading", { level: 1 })).toContainText(/النشر/);
      // ولا شيءَ من مفردات الاستقطاب هنا.
      await expect(page.getByTestId("collab-tab-discover")).toHaveCount(0);
      await expect(page.locator("text=استكشاف الفرص")).toHaveCount(0);
    });

    // ── ٢ · وصفحةُ التعاون شيءٌ آخر، بعنوانٍ آخر ──
    await test.step("the collaboration page is a different domain", async () => {
      await page.goto(`/${AR}/collaboration-opportunities`);
      await expect(page).toHaveURL(new RegExp(`/${AR}/collaboration-opportunities$`));
      await expect(page.getByRole("heading", { level: 1 })).toHaveText("الفرص البحثية");
      await expect(page.getByTestId("collab-tab-discover")).toBeVisible();
      await expect(page.getByTestId("collab-tab-mine")).toBeVisible();
      // **وثلاثُ حالاتٍ لا تُطوى في واحدة**: «يُحمَّل» يظهر أوّلًا ثمّ
      // يذهب، ولا تُقال «لا فرص» قبل عودة الطلب.
      await expect(page.getByTestId("collab-loading")).toHaveCount(0, { timeout: 30_000 });
      // ولا مفرداتِ خريطة النشر هنا.
      await expect(page.locator("text=درجة الجاهزية")).toHaveCount(0);
    });

    await test.step("and in English too", async () => {
      await page.goto(`/${EN}/collaboration-opportunities`);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText("Research Opportunities");
    });

    // ── ٣ · وعنصرُ التنقّل يقصد التعاون، لا خريطةَ النشر ──
    //
    // **وهذا هو البيتُ الذي تحرسه هذه الرقعة.** والاسمُ المعروضُ واحدٌ
    // في المكانين تقريبًا، فلا يُميَّز الخطأُ بالعين: يُميَّز بالوجهة.
    await test.step("the navigation item lands on recruitment, not the publication map",
      async () => {
        await page.goto(`/${AR}`);
        const item = page.getByRole("link", { name: "الفرص البحثية" });
        await expect(item).toBeVisible();
        await item.click();
        await page.waitForURL(/\/collaboration-opportunities$/, { timeout: 30_000 });
        expect(page.url()).toContain("/collaboration-opportunities");
        expect(page.url()).not.toMatch(/\/ar\/opportunities$/);
        await expect(page.getByTestId("collab-tab-discover")).toBeVisible();
      });

    // ── ٤ · والفجواتُ العلميةُ لبحثٍ باقيةٌ في موضعها ──
    await test.step("project scientific opportunity surfaces are untouched", async () => {
      await page.goto(`/${AR}/portfolio`);
      await page.getByLabel("عنوان البحث").fill(`بحثُ فصل المجالات ${RUN}`);
      await page.getByRole("button", { name: /أنشئ البحث/ }).click();
      await page.waitForURL(/\/portfolio\/[0-9a-f-]{36}/, { timeout: 60_000 });
      const projectUrl = page.url().split("?")[0]!;

      await page.goto(`${projectUrl}/research-opportunities`);
      await expect(page.getByTestId("collab-tab-discover")).toHaveCount(0);
      await expect(page.getByTestId("project-recruitment")).toHaveCount(0);

      await page.goto(`${projectUrl}/publication-opportunities`);
      await expect(page.getByTestId("collab-tab-discover")).toHaveCount(0);
      await expect(page.getByTestId("project-recruitment")).toHaveCount(0);

      // ── ٥ · والقسمان الجديدان يعيشان في هيكل البحث نفسِه ──
      //
      // **ولا هيكلَ ثانيًا**: `?section=` هي هي، فيصحّ التحديثُ والرابطُ
      // العميقُ بلا شيءٍ يُكتب لهما.
      await page.goto(`${projectUrl}?section=opportunities`);
      await expect(page.getByTestId("project-recruitment")).toBeVisible({ timeout: 30_000 });
      await page.reload();
      await expect(page.getByTestId("project-recruitment")).toBeVisible({ timeout: 30_000 });

      await page.goto(`${projectUrl}?section=team`);
      await expect(page.getByTestId("team-my-access")).toBeVisible({ timeout: 30_000 });
      // **ولا مُنتقي بحثٍ ثانٍ داخل صفحة بحث.**
      await expect(page.getByTestId("team-project-picker")).toHaveCount(0);
      await page.reload();
      await expect(page.getByTestId("team-my-access")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("team-project-picker")).toHaveCount(0);
    });

    // ── ٦ · والوحدةُ العامّةُ للفريق باقيةٌ بمُنتقيها ──
    await test.step("the global team console keeps working, with its picker", async () => {
      for (const locale of [AR, EN]) {
        await page.goto(`/${locale}/team`);
        await expect(page.getByTestId("team-project-picker")).toBeVisible({ timeout: 30_000 });
        // **والمحرّكُ واحد**: الشاشتان تُصيَّران من `TeamWorkspace` نفسِه،
        // ووجودُ هذه البطاقة في كلتيهما هو ما يُثبت أنّه لم يُفرَّع.
        await expect(page.getByTestId("team-my-access")).toBeVisible({ timeout: 30_000 });
        await expect(page.getByTestId("invitation-accept")).toBeVisible();
      }
    });

    expect(serverErrors, "a 5xx answered somewhere in the domain walk").toEqual([]);
  });

test("٣٧٥px: لا فيضٌ أفقيّ في أسطح التعاون | no horizontal overflow at 375px",
  async ({ browser }) => {
    test.setTimeout(180_000);
    const context = await browser.newContext({ viewport: { width: 375, height: 800 } });
    const page = await context.newPage();
    const serverErrors = watch(page);

    // الدخولُ بالحساب الذي سجّله الفحصُ الأوّل — **وبلا انتظارِ شكلِ رابط
    // وحده**: يُنتظر ردُّ الدخول أوّلًا، فلا يُقاس تحويلٌ لم يقع بعد.
    await page.goto(`/${EN}/login`);
    const answered = page.waitForResponse(
      (r) => r.url().endsWith("/api/v1/auth/login") && r.request().method() === "POST",
      { timeout: 60_000 },
    );
    await page.locator('form input[type=email]').fill(ACCOUNT);
    await page.locator("#login-password").fill(PASSWORD);
    await page.locator("form button[type=submit]").click();
    expect((await answered).status()).toBe(200);
    await page.waitForURL(`**/${EN}`, { timeout: 60_000 });

    await page.goto(`/${AR}/portfolio`);
    await page.waitForSelector("h1");
    const projectLink = page.locator('a[href*="/portfolio/"]').first();
    const href = await projectLink.getAttribute("href");
    const projectUrl = href ?? "";

    /**
     * **والفيضُ يُقاس لا يُنظر إليه.** فصفحةٌ تبدو سليمةً في لقطةٍ قد
     * تدفع المستندَ أفقيًّا بعنصرٍ واحدٍ عريض — ورمزُ دعوةٍ طويلٌ هو
     * أوّلُ من يفعلها.
     */
    async function noOverflow(label: string) {
      const overflow = await page.evaluate(() => {
        const el = document.documentElement;
        return { scroll: el.scrollWidth, client: el.clientWidth };
      });
      expect(
        overflow.scroll,
        `${label}: the document scrolls horizontally (${overflow.scroll} > ${overflow.client})`,
      ).toBeLessThanOrEqual(overflow.client + 1);
    }

    const surfaces: [string, string][] = [
      ["My Research", `/${AR}/portfolio`],
      ["global opportunities", `/${AR}/collaboration-opportunities`],
      ["project team", `${projectUrl}?section=team`],
      ["project opportunities", `${projectUrl}?section=opportunities`],
      ["global team", `/${AR}/team`],
      // ومدخلُ البيانات الذي يستعمله المتعاونُ الخارجيّ (0036) — قسمًا
      // في صفحة البحث وشاشةً قائمة. **ولا إعادةَ تصميمٍ لها هنا**: يُقاس
      // ألّا تدفع الصفحةَ أفقيًّا على هاتف، لا غير.
      ["project data section", `${projectUrl}?section=data`],
      ["analysis screen", `/${AR}/analysis`],
    ];
    for (const [label, url] of surfaces) {
      await page.goto(url);
      await page.waitForSelector("h1, h2");
      await noOverflow(label);
    }

    // ونموذجُ الإعلان مفتوحًا — **أكثرُ ما يُفيض هو نموذجٌ مفتوح**.
    await page.goto(`${projectUrl}?section=opportunities`);
    await page.getByTestId("opportunity-new").click();
    await expect(page.getByTestId("opportunity-create-submit")).toBeVisible();
    await noOverflow("opportunity form");

    // ومُنتقي الصلاحيات في الفريق.
    await page.goto(`${projectUrl}?section=team`);
    await expect(page.getByTestId("team-my-access")).toBeVisible({ timeout: 30_000 });
    await noOverflow("team with permission controls");

    // وتبويبُ «طلباتي».
    await page.goto(`/${AR}/collaboration-opportunities`);
    await page.getByTestId("collab-tab-mine").click();
    await expect(page.getByTestId("collab-mine")).toBeVisible();
    await noOverflow("my applications");

    expect(serverErrors, "a 5xx answered during the 375px walk").toEqual([]);
    await context.close();
  });
