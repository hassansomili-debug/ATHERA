import { expect, test, type Page } from "@playwright/test";

/**
 * رحلةُ RC-0 على مكدّسٍ حقيقيّ | The RC-0 Journey, end to end, with no interception.
 *
 * **لماذا هذه الرقعة موجودة.**
 *
 * رحلةُ القبول على الإنتاج (`acceptance.spec.ts`) صارت تفحص عقدَ RC-0 —
 * لكنّها لا تستطيع إثباتَ شيءٍ حتى يُنشر الخادمُ الحامل للعقد. وبين
 * المراجعة والنشر فجوةٌ لا يملؤها شيء إن لم تُملأ هنا.
 *
 * فتُثبت هذه الرقعةُ **المفرداتِ نفسَها** على مكدّسٍ متوائم: خادمٌ حقيقيّ،
 * وقاعدةٌ حقيقية، ومتصفّحٌ حقيقيّ، **وبلا اعتراض شبكةٍ البتّة**. فإن كان
 * في العقد كسرٌ ظهر هنا قبل أن يبلغ الإنتاج.
 *
 * وهي لا تُغني عن رحلة القبول: تلك تفحص **المنشور**، وهذه تفحص **المصدر**.
 * ولكلٍّ موضعُه من دورة الحياة.
 */

const EN = "en";
const AR = "ar";

/** عنوانٌ محجوز — و`example.com` لا يصل بريدًا ولا يُنشئ حسابًا خارجيًّا. */
const RUN = `rc0-${Date.now().toString(36)}`;
const ACCOUNT = `${RUN}@example.com`;
const PASSWORD = "Rc0-Journey-9f3b!";

const PROJECT_TITLE = `بحثُ مسارٍ كامل ${RUN}`;

interface Seen {
  errors: string[];
  serverErrors: string[];
}

function watch(page: Page): Seen {
  const seen: Seen = { errors: [], serverErrors: [] };
  page.on("pageerror", (e) => seen.errors.push(String(e)));
  page.on("response", (r) => {
    if (r.status() >= 500) seen.serverErrors.push(`${r.status()} ${r.url()}`);
  });
  return seen;
}

test.describe.configure({ mode: "serial" });

let projectUrl = "";

test("١ · حسابٌ حقيقيّ بالنموذج | a real account, through the form",
  async ({ page }) => {
    const seen = watch(page);
    await page.goto(`/${EN}/register`);
    await page.locator("#reg-name").fill("RC0 Journey");
    await page.locator("#reg-email").fill(ACCOUNT);
    await page.locator("#reg-password").fill(PASSWORD);
    await page.locator("form button[type=submit]").click();
    await page.waitForURL(`**/${EN}`, { timeout: 30_000 });

    expect(seen.serverErrors, `خمسمئة في التسجيل: ${seen.serverErrors[0]}`)
      .toHaveLength(0);
    expect(seen.errors, `استثناء: ${seen.errors[0]}`).toHaveLength(0);
  });

test("٢ · بحثٌ يُنشأ بعنوانه، ويُفتح بيتُه | a project, opened at its canonical home",
  async ({ page }) => {
    await page.goto(`/${EN}/login`);
    await page.locator("input[type=email]").fill(ACCOUNT);
    await page.locator("#login-password").fill(PASSWORD);
    await page.locator("form button[type=submit]").click();
    await page.waitForURL(`**/${EN}`, { timeout: 30_000 });

    await page.goto(`/${AR}/portfolio`);
    await page.getByLabel("عنوان البحث").fill(PROJECT_TITLE);
    await page.getByRole("button", { name: /أنشئ البحث/ }).click();

    // الإنشاء يفتح بيتَ المشروع مباشرةً — ولا معرّفَ يُنسخ بيد.
    await page.waitForURL(/\/portfolio\/[0-9a-f-]{36}/, { timeout: 30_000 });
    projectUrl = page.url();
    await expect(page.getByRole("heading", { name: PROJECT_TITLE })).toBeVisible();
  });

test("٣ · والرحلةُ تصل من خادمٍ حقيقيّ | the Journey loads from a real server",
  async ({ page }) => {
    const seen = watch(page);
    await page.goto(projectUrl);

    const journey = page.getByTestId("research-journey");
    await expect(journey).toBeVisible({ timeout: 30_000 });

    // **وهذه المفرداتُ بعينها تفحصها رحلةُ القبول على الإنتاج.**
    await expect(page.getByTestId("journey-failed")).toHaveCount(0);
    await expect(page.getByTestId("journey-loading")).toHaveCount(0);
    await expect(page.getByTestId("journey-current-stage")).toHaveText("الفكرة");
    await expect(page.getByTestId("journey-next-title")).toBeVisible();
    await expect(page.getByTestId("journey-next-why")).toContainText("لا سؤالَ");
    await expect(journey.getByTestId("journey-stages").locator("> li"))
      .toHaveCount(9);
    await expect(page.locator('[data-current="true"]')).toHaveCount(1);
    await expect(page.getByTestId("journey-primary-cta")).toBeVisible();

    // **ولا نسبةَ إنجاز**، ولا خمسمئة في الطريق.
    expect(await page.locator("body").innerText()).not.toMatch(/\d+\s*%/);
    expect(seen.serverErrors, `خمسمئة: ${seen.serverErrors[0]}`).toHaveLength(0);
    expect(seen.errors, `استثناء: ${seen.errors[0]}`).toHaveLength(0);
  });

test("٤ · والفعلُ الرئيس يبلغ أدواتِ المصادر | the primary action reaches real controls",
  async ({ page }) => {
    await page.goto(projectUrl);
    await expect(page.getByTestId("research-journey")).toBeVisible({
      timeout: 30_000,
    });

    // بحثٌ خاوٍ يقف عند الفكرة؛ وقسمُ المصادر يُبلَغ بالرابط نفسِه.
    await page.goto(`${projectUrl}?section=literature`);
    await expect(
      page.getByRole("heading", { name: "أضِف مرجعًا من مكتبتك" }),
    ).toBeVisible({ timeout: 30_000 });

    // ويبقى بعد تحديث — القسمُ في الرابط لا في الذاكرة.
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "أضِف مرجعًا من مكتبتك" }),
    ).toBeVisible({ timeout: 30_000 });
  });
