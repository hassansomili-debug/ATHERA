import { expect, test, type BrowserContext, type Page } from "@playwright/test";

/**
 * التعاونُ البحثيُّ عبر ثلاث مؤسسات — **بمتصفّحٍ حقيقيّ وبلا اعتراض**.
 *
 * وما تُثبته هذه الرحلةُ ليس شاشةً تُصيَّر: هو أنّ **السلسلةَ تتّصل**.
 * فقد تصحّ كلُّ نقطةٍ وحدها ولا يعمل المنتج: يُنشر الإعلانُ فلا يُكتشف،
 * أو يُكتشف فلا يُتقدَّم إليه، أو يُدعى المرشَّحُ فلا يقدر على القبول، أو
 * يقبل فلا يجد البحثَ في أيّ شاشة.
 *
 * **ثلاثُ مؤسساتٍ لا واحدة:**
 *
 *   «أ»  صاحبُ البحث — والبحثُ X في مستأجره.
 *   «ب»  باحثٌ يكتشف ويتقدّم ويُقبَل — ولا انتماءَ له في «أ» أبدًا.
 *   «ج»  مديرٌ **خارجيّ** يُدير الاختيار — ولا انتماءَ له في «أ» أبدًا.
 *
 * ولكلٍّ سياقُ متصفّحٍ خاصّ: الرموزُ في `localStorage`، وسياقٌ واحدٌ
 * لثلاثة أشخاص يعني جلسةً تُدهس أختَها ويصير الفحصُ يقيس نفسَه.
 *
 * ## ولا رمزَ يُختلق
 *
 * رمزُ الدعوةِ **يُقرأ من الشاشة التي رآها المدير**. ولو اعتُرضت نقطةُ
 * الدعوة وأُخذ الرمزُ من جوابها لَأثبت الفحصُ المُعترِضَ لا المنتج: أنّ
 * المديرَ يرى الرمزَ هو نصفُ الميزة، وأنّ الباحثَ يقدر على لصقه نصفُها
 * الآخر.
 *
 * ## وثلاثةُ حدودٍ تُفحص لا تُفترض
 *
 *   ١ **لا انتماءَ تنظيميًّا** يُنشأ في مستأجر «أ» لأحدٍ منهما.
 *   ٢ **الدورُ ليس صلاحية**: منحٌ واحدٌ يفتح بابًا بلا أن يمسّ الدور.
 *   ٣ **ولا كذبةَ ذاكرة**: الإيقافُ يُقفل البابَ في الطلب التالي، بلا
 *     خروجٍ ولا تجديدِ رمزٍ ولا مهلة.
 */
const AR = "ar";
const EN = "en";

const RUN = `rct1c-${Date.now().toString(36)}`;
const PASSWORD = "Collab-Journey-9f3b!";

const OWNER = `${RUN}-a@example.com`;
const RESEARCHER = `${RUN}-b@example.com`;
const MANAGER = `${RUN}-c@example.com`;

const PROJECT_TITLE = `بحثُ التعاون عبر المؤسسات ${RUN}`;
const POST_TITLE = `مطلوب باحث مساعد لمراجعة الدراسات السابقة ${RUN}`;
const POST_BODY =
  "مطلوب باحث للمساعدة في مراجعة الدراسات السابقة وتنظيم الأدلة العلمية.";

interface Person {
  context: BrowserContext;
  page: Page;
  email: string;
  serverErrors: string[];
}

async function enrol(
  browser: Parameters<Parameters<typeof test>[1]>[0]["browser"],
  email: string,
  name: string,
): Promise<Person> {
  const context = await browser.newContext();
  const page = await context.newPage();
  const serverErrors: string[] = [];
  page.on("response", (r) => {
    if (r.status() >= 500) serverErrors.push(`${r.status()} ${r.url()}`);
  });
  // **والتسجيلُ يُنشئ مؤسسةً لكلّ حساب** — فثلاثةُ تسجيلاتٍ ثلاثُ مؤسسات
  // حقيقية، لا ثلاثةَ مستخدمين في مؤسسةٍ واحدة.
  await page.goto(`/${EN}/register`);
  await page.locator("#reg-name").fill(name);
  await page.locator("#reg-email").fill(email);
  await page.locator("#reg-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").click();
  await page.waitForURL(`**/${EN}`, { timeout: 60_000 });
  return { context, page, email, serverErrors };
}

/**
 * معرّفُ العضوِ الذي دورُه المحفوظ كذا — **من قيمة المُنتقي لا من نصّ**.
 *
 * ولا يُرشَّح ببطاقةٍ «فيها اسمُ الدور»: مُنتقي الدور يحمل **كلَّ** الأدوار
 * خياراتٍ في كلّ بطاقة، فترشيحٌ بالنصّ يطابق الفريقَ كلَّه. وقد وقع ذلك
 * فعلًا في أوّل تشغيلةٍ لهذه الرحلة: أُخذ صاحبُ البحث على أنه المحلّل.
 */
async function memberWithRole(page: Page, role: string): Promise<string> {
  const card = page.locator(`[data-member-role="${role}"]`).first();
  await expect(card).toBeVisible({ timeout: 30_000 });
  return (await card.getAttribute("data-testid"))!.replace("team-member-", "");
}

/**
 * يفتح لوحَ العضو — **وأدواتُ الإدارة كلُّها فيه** بعد RC-T1C UX-1.
 *
 * فبطاقةُ العضو تقول اسمًا ودورًا وحالًا وحدها، والدورُ والصلاحياتُ
 * وأزرارُ المدخل تُفتح عند الطلب. وما تغيّر طريقُ الوصول لا الدعوى:
 * الصلاحيةُ تُمنح بلا أن يُمسّ الدور، والإيقافُ يبيت في الطلب التالي.
 */
async function manage(page: Page, memberId: string) {
  await page.getByTestId(`team-manage-${memberId}`).click();
  await expect(page.getByTestId(`team-member-detail-${memberId}`))
    .toBeVisible({ timeout: 30_000 });
}

/**
 * عنوانُ الـAPI للتهيئة — **ولا يُستعمل في الرحلة نفسِها**.
 *
 * فما يُقاس هو المتصفّحُ والمنتج؛ وما يُهيَّأ بالـAPI هو ما **لا واجهةَ
 * له في هذا الإصدار لأحد**: إنشاءُ مجموعةِ بياناتٍ ونسخةٍ مشتقّة. ولا
 * شاشةَ إنشاءٍ لها في المنتج — لا للمتعاون ولا لصاحب البحث — فتهيئتُها
 * بالـAPI تصريحٌ بالحدّ لا تزييفٌ لرحلة.
 */
const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function tokenOf(page: Page): Promise<string> {
  const token = await page.evaluate(() =>
    localStorage.getItem("athera_access_token"));
  expect(token, "no access token in this browser context").toBeTruthy();
  return token!;
}

/** المهلةُ المحلّية للتاريخ — بصيغة حقل `datetime-local`. */
function localStamp(offsetMinutes: number): string {
  const when = new Date(Date.now() + offsetMinutes * 60_000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}` +
    `T${pad(when.getHours())}:${pad(when.getMinutes())}`
  );
}

test("الرحلةُ الذهبية للتعاون البحثيّ عبر ثلاث مؤسسات | the three-tenant collaboration journey",
  async ({ browser }) => {
    test.setTimeout(600_000);

    const owner = await enrol(browser, OWNER, "Owner A");
    const researcher = await enrol(browser, RESEARCHER, "Researcher B");
    const manager = await enrol(browser, MANAGER, "External Manager C");

    let projectUrl = "";
    let invitationToken = "";

    // ═════════ تهيئة · بحثٌ في «أ»، ومديرٌ خارجيٌّ من «ج» ═════════
    //
    // **والمديرُ الخارجيُّ يُصنع بالمنتج لا بتجهيزة**: يدعوه صاحبُ البحث
    // من قسم الفريق، ويقبل هو بالرمز، ثمّ يُمنح `manage_team` صريحًا —
    // ثلاثُ خطواتٍ كلُّها في المتصفّح.
    await test.step("A creates Project X", async () => {
      await owner.page.goto(`/${AR}/portfolio`);
      await owner.page.getByLabel("عنوان البحث").fill(PROJECT_TITLE);
      await owner.page.getByRole("button", { name: /أنشئ البحث/ }).click();
      await owner.page.waitForURL(/\/portfolio\/[0-9a-f-]{36}/, { timeout: 60_000 });
      projectUrl = owner.page.url().split("?")[0]!;
      await expect(owner.page.getByRole("heading", { name: PROJECT_TITLE })).toBeVisible();
    });

    await test.step("A invites C from Tenant C into the project team", async () => {
      await owner.page.goto(`${projectUrl}?section=team`);
      await expect(owner.page.getByTestId("team-my-access")).toBeVisible({ timeout: 30_000 });
      await owner.page.getByTestId("team-invite-open").click();
      await expect(owner.page.getByTestId("team-invite-dialog"))
        .toBeVisible({ timeout: 30_000 });
      await owner.page.locator("#team-invite-name").fill("مديرٌ خارجيّ");
      await owner.page.locator("#team-invite-email").fill(MANAGER);
      await owner.page.getByTestId("team-invite-submit").click();
      const token = owner.page.getByTestId("team-token").locator("code");
      await expect(token).toBeVisible({ timeout: 30_000 });
      const managerToken = (await token.innerText()).trim();
      expect(managerToken.length).toBeGreaterThan(16);
      await owner.page.getByTestId("team-token-done").click();

      // ويقبل «ج» بحسابه — **والقبولُ شخصيّ**.
      await manager.page.goto(`/${AR}/team`);
      await manager.page.getByTestId("invitation-token-input").fill(managerToken);
      await manager.page.getByTestId("invitation-accept-submit").click();
      await expect(manager.page.getByTestId("invitation-accept").locator(".badge-ok"))
        .toBeVisible({ timeout: 30_000 });
    });

    await test.step("A grants C manage_team explicitly — without touching the role",
      async () => {
        await owner.page.goto(`${projectUrl}?section=team`);
        const card = owner.page.locator('[data-testid^="team-member-"]')
          .filter({ hasText: "مديرٌ خارجيّ" }).first();
        await expect(card).toBeVisible({ timeout: 30_000 });
        const memberId = (await card.getAttribute("data-testid"))!.replace("team-member-", "");
        await manage(owner.page, memberId);
        const roleBefore = await owner.page.getByTestId(`team-role-${memberId}`).inputValue();
        expect(roleBefore).toBe("co_author");

        await owner.page.getByTestId(`team-edit-permissions-${memberId}`).click();
        await owner.page.getByTestId(`team-permission-${memberId}-manage_team`).check();
        await owner.page.getByTestId(`team-permission-${memberId}-view_project`).check();
        await owner.page.getByTestId(`team-permission-${memberId}-manage_sources`).check();
        await owner.page.getByTestId(`team-permission-save-${memberId}`).click();
        await expect(owner.page.getByTestId(`team-permission-editor-${memberId}`))
          .toHaveCount(0, { timeout: 30_000 });

        // **والدورُ كما كان.** والصلاحيةُ صفٌّ يُكتب، لا دورٌ يُفسَّر.
        await expect(owner.page.getByTestId(`team-role-${memberId}`))
          .toHaveValue(roleBefore, { timeout: 30_000 });
      });

    // ═════════ الخطوة أ · صاحبُ البحث ينشر إعلانًا ═════════
    let opportunityId = "";
    await test.step("STEP A — the owner creates and publishes a recruitment posting",
      async () => {
        await owner.page.goto(`${projectUrl}?section=opportunities`);
        await expect(owner.page.getByTestId("project-recruitment")).toBeVisible({ timeout: 30_000 });
        await owner.page.getByTestId("opportunity-new").click();

        await owner.page.locator("#new-title").fill(POST_TITLE);
        await owner.page.locator("#new-description").fill(POST_BODY);
        await owner.page.locator("#new-openings").fill("2");
        // **والتوقيتُ يُرسل واعيًا بمنطقته** — لا نصًّا ساذجًا يُقرأ UTC.
        await owner.page.locator("#new-starts").fill(localStamp(-60));
        await owner.page.locator("#new-ends").fill(localStamp(60 * 24 * 30));
        await owner.page.getByTestId("opportunity-create-submit").click();

        const card = owner.page.locator('[data-testid^="opportunity-"]')
          .filter({ hasText: POST_TITLE }).first();
        await expect(card).toBeVisible({ timeout: 30_000 });

        // **ومسودّةٌ ليست إعلانًا منشورًا** — والحالةُ النافذةُ تقول ذلك.
        const created = owner.page.locator('[data-testid^="opportunity-status-"]').first();
        await expect(created).toHaveText("مسودّة");

        const cards = owner.page.locator('[data-testid^="opportunity-publish-"]');
        opportunityId = (await cards.first().getAttribute("data-testid"))!
          .replace("opportunity-publish-", "");
        await owner.page.getByTestId(`opportunity-publish-${opportunityId}`).click();
        await expect(owner.page.getByTestId(`opportunity-status-${opportunityId}`))
          .toHaveText("متاحة", { timeout: 30_000 });
      });

    // ═════════ الخطوة ب · باحثٌ من «ب» يكتشف ويتقدّم ═════════
    await test.step("STEP B — researcher B discovers it through navigation and applies",
      async () => {
        await researcher.page.goto(`/${AR}`);
        await researcher.page.getByRole("link", { name: "الفرص البحثية" }).click();
        // **ولا يهبط على خريطة فرص النشر.**
        await researcher.page.waitForURL(/\/collaboration-opportunities$/, { timeout: 30_000 });
        expect(researcher.page.url()).not.toMatch(/\/ar\/opportunities$/);

        const card = researcher.page.getByTestId(`collab-card-${opportunityId}`);
        await expect(card).toBeVisible({ timeout: 30_000 });
        await expect(card).toContainText(POST_TITLE);

        await researcher.page.getByTestId(`collab-open-${opportunityId}`).click();
        await researcher.page.waitForURL(new RegExp(`/collaboration-opportunities/${opportunityId}$`));
        await expect(researcher.page.getByTestId("detail-status")).toHaveText("متاحة");

        await researcher.page.getByTestId("apply-message")
          .fill("أودّ المشاركةَ في مراجعة الدراسات السابقة.");
        await researcher.page.getByTestId("apply-submit").click();
        await expect(researcher.page.getByTestId("apply-confirmed")).toBeVisible({ timeout: 30_000 });

        await researcher.page.goto(`/${AR}/collaboration-opportunities`);
        await researcher.page.getByTestId("collab-tab-mine").click();
        const mine = researcher.page.locator('[data-testid^="application-status-"]').first();
        await expect(mine).toHaveText("قيد النظر", { timeout: 30_000 });
      });

    // ═════════ الخطوة ج · المديرُ الخارجيُّ يختار ═════════
    let applicationId = "";
    await test.step("STEP C — external manager C sees Project X in My Research and selects B",
      async () => {
        // **«أبحاثي» عند «ج» تحتوي البحثَ X** — وهو في مؤسسةٍ أخرى.
        await manager.page.goto(`/${AR}/portfolio`);
        const listed = manager.page.locator("article.card").filter({ hasText: PROJECT_TITLE });
        await expect(listed).toBeVisible({ timeout: 30_000 });
        // ووسمُ «متعاون» لا وسمُ ملكيّة.
        await expect(listed).toContainText("متعاون");

        await manager.page.goto(`${projectUrl}?section=opportunities`);
        await manager.page.getByTestId(`opportunity-applicants-${opportunityId}`).click();
        const applicant = manager.page.locator('[data-testid^="applicant-status-"]').first();
        await expect(applicant).toBeVisible({ timeout: 30_000 });
        applicationId = (await applicant.getAttribute("data-testid"))!
          .replace("applicant-status-", "");

        await manager.page.getByTestId(`applicant-shortlist-${applicationId}`).click();
        await expect(manager.page.getByTestId(`applicant-status-${applicationId}`))
          .toHaveText("في القائمة المختصرة", { timeout: 30_000 });

        // ── الدعوةُ: دورٌ وصلاحياتٌ صريحة، ولا هويّةَ في النموذج ──
        await manager.page.getByTestId(`applicant-invite-${applicationId}`).click();
        await manager.page.getByTestId(`invite-role-${applicationId}`).selectOption("statistician");
        await manager.page.getByTestId("invite-permission-view_project").check();
        await manager.page.getByTestId("invite-permission-manage_data").check();
        for (const withheld of ["manage_sources", "manage_team", "manage_submission"]) {
          await manager.page.getByTestId(`invite-permission-${withheld}`).uncheck();
        }
        await manager.page.getByTestId(`invite-submit-${applicationId}`).click();

        // **والرمزُ يُقرأ من الشاشة التي رآها المدير** — لا من جوابٍ يُعترض.
        const shown = manager.page.getByTestId("recruitment-token-value");
        await expect(shown).toBeVisible({ timeout: 30_000 });
        invitationToken = (await shown.innerText()).trim();
        expect(invitationToken.length).toBeGreaterThan(16);
      });

    // ═════════ الخطوة د · المرشَّحُ يقبل ═════════
    await test.step("STEP D — candidate B accepts with the manager's token", async () => {
      await researcher.page.goto(`/${AR}/collaboration-opportunities`);
      await researcher.page.getByTestId("collab-tab-mine").click();
      await expect(researcher.page.getByTestId(`application-status-${applicationId}`))
        .toHaveText("مدعوّ", { timeout: 30_000 });
      // **و«مدعوّ» ليس «دعوةً قابلةً للاستعمال»** — والحالان يُعرضان معًا.
      await expect(researcher.page.getByTestId(`invitation-usable-${applicationId}`))
        .toHaveText("الدعوةُ قابلةٌ للاستعمال");

      const panel = researcher.page.getByTestId(`invitation-${applicationId}`)
        .getByTestId("invitation-token-input");
      await panel.fill(invitationToken);
      await researcher.page.getByTestId(`invitation-${applicationId}`)
        .getByTestId("invitation-accept-submit").click();

      await researcher.page.reload();
      await researcher.page.getByTestId("collab-tab-mine").click();
      await expect(researcher.page.getByTestId(`membership-${applicationId}`))
        .toBeVisible({ timeout: 30_000 });
    });

    // ═════════ الخطوة هـ · البحثُ الأصليُّ يُفتح ═════════
    await test.step("STEP E — B opens the original Project X from My Research", async () => {
      await researcher.page.goto(`/${AR}/portfolio`);
      const listed = researcher.page.locator("article.card").filter({ hasText: PROJECT_TITLE });
      await expect(listed).toBeVisible({ timeout: 30_000 });
      await expect(listed).toContainText("متعاون");

      await researcher.page.goto(projectUrl);
      // **ولا بحثٌ منسوخ**: المعرّفُ هو هو، والعنوانُ هو هو.
      await expect(researcher.page.getByRole("heading", { name: PROJECT_TITLE }))
        .toBeVisible({ timeout: 30_000 });
      // **والرحلةُ العلميةُ مشتركة** — لا رحلةَ متعاونٍ ولا اكتمالٌ خاصّ به.
      await expect(researcher.page.getByTestId("research-journey"))
        .toBeVisible({ timeout: 60_000 });
      await expect(researcher.page.getByTestId("journey-failed")).toHaveCount(0);

      await researcher.page.goto(`${projectUrl}?section=team`);
      const mine = researcher.page.getByTestId("team-my-access");
      await expect(mine).toBeVisible({ timeout: 30_000 });
      await expect(mine).toContainText("متعاون");
      // ودورُه في الفريق `statistician` — ولا تأليفَ ولا CRediT.
      // **ولا مُنتقي أدوارٍ في صفحةِ «ب» أصلًا** (لا `manage_team` له).
      await expect(researcher.page.locator('[data-testid^="team-role-"]')).toHaveCount(0);
      const myCard = researcher.page.locator('[data-member-role="statistician"]').first();
      await expect(myCard).toBeVisible({ timeout: 30_000 });
      await expect(myCard).toContainText("محلل إحصائي");
      // **والتأليفُ ليس على البطاقة** (RC-T1C UX-1): غيابُ التأليف لا يحتاج
      // تحذيرًا على كلّ بطاقة، ومحلُّه قسمُ «التأليف والموافقة» في اللوح.
      await expect(myCard).not.toContainText("عضو فريق، وليس مؤلفًا");
    });

    // ═════════ الخطوة و · الدورُ ليس صلاحية ═════════
    await test.step("STEP F — permission, not role, decides — and one grant changes it",
      async () => {
        // **ولا تُعرض له أدواتُ ما لا يملك.** فقبل المنح لا زرَّ إدارةِ
        // فريقٍ ولا نموذجَ دعوة في قسم الفريق.
        await researcher.page.goto(`${projectUrl}?section=team`);
        await expect(researcher.page.getByTestId("team-my-access")).toBeVisible({ timeout: 30_000 });
        await expect(researcher.page.locator('[data-testid^="team-edit-permissions-"]'))
          .toHaveCount(0);
        await expect(researcher.page.getByRole("button", { name: "أرسل الدعوة" }))
          .toHaveCount(0);
        await expect(researcher.page.getByTestId("recruitment-needs-manage-team")).toHaveCount(0);

        // ولا إدارةَ فرصٍ بحثية: `manage_team` غائبة.
        await researcher.page.goto(`${projectUrl}?section=opportunities`);
        await expect(researcher.page.getByTestId("recruitment-needs-manage-team"))
          .toBeVisible({ timeout: 30_000 });
        await expect(researcher.page.getByTestId("opportunity-new")).toHaveCount(0);

        // ولا إدارةَ مصادر: أدواتُ الإضافة **لا تُعرض**، والعلّةُ تُقال
        // باسمها. والخادمُ هو الحدُّ — ويُثبَت ذلك بطلبٍ حقيقيّ في
        // `tests/test_at_rc_t1c_my_research.py::test_18`؛ وهذه الشاشةُ
        // تُثبت أنّها لا تَعِد بما لا يقع.
        await researcher.page.goto(`${projectUrl}?section=literature`);
        await expect(researcher.page.getByTestId("sources-read-only"))
          .toBeVisible({ timeout: 30_000 });

        // ── ومنحٌ واحدٌ صريح من المديرِ الخارجيّ، بلا تغييرِ دور ──
        await manager.page.goto(`${projectUrl}?section=team`);
        const bId = await memberWithRole(manager.page, "statistician");
        await manage(manager.page, bId);

        await manager.page.getByTestId(`team-edit-permissions-${bId}`).click();
        await manager.page.getByTestId(`team-permission-${bId}-manage_sources`).check();
        await manager.page.getByTestId(`team-permission-save-${bId}`).click();
        await expect(manager.page.getByTestId(`team-permission-editor-${bId}`))
          .toHaveCount(0, { timeout: 30_000 });
        await expect(manager.page.getByTestId(`team-role-${bId}`)).toHaveValue("statistician");

        // **وبابُ المصادر يُفتح فورًا** — بلا خروجٍ ولا تجديدِ رمزٍ ولا
        // مهلةِ ذاكرة. والدورُ لم يُمسّ، والصلاحيةُ وحدها تغيّرت.
        await researcher.page.goto(`${projectUrl}?section=team`);
        // **وصلاحيّاتي خلف «عرض صلاحياتي»** لا مطبوعةً في صدر الشاشة
        // (RC-T1C UX-1) — والدعوى كما هي: المنحُ يُرى بلا خروجٍ ولا مهلة.
        await expect(researcher.page.getByTestId("team-my-access-toggle"))
          .toBeVisible({ timeout: 30_000 });
        await researcher.page.getByTestId("team-my-access-toggle").click();
        await expect(researcher.page.getByTestId("team-my-access-detail"))
          .toContainText("إدارة المصادر", { timeout: 30_000 });
        await researcher.page.goto(`${projectUrl}?section=literature`);
        await expect(researcher.page.getByTestId("sources-read-only"))
          .toHaveCount(0, { timeout: 30_000 });
      });

    // ═════════ الخطوة ز · الإيقافُ والاستعادة ═════════
    await test.step("STEP G — suspension bites on the next request; restore returns access",
      async () => {
        await manager.page.goto(`${projectUrl}?section=team`);
        const bId = await memberWithRole(manager.page, "statistician");
        await manage(manager.page, bId);
        await manager.page.getByTestId(`team-suspend-${bId}`).click();
        await expect(manager.page.getByTestId(`team-restore-${bId}`))
          .toBeVisible({ timeout: 30_000 });

        // **ولا كذبةَ ذاكرة**: الرمزُ نفسُه، والبابُ أُقفل.
        await researcher.page.goto(`/${AR}/portfolio`);
        await expect(researcher.page.locator("article.card").filter({ hasText: PROJECT_TITLE }))
          .toHaveCount(0, { timeout: 30_000 });

        await manager.page.getByTestId(`team-restore-${bId}`).click();
        await expect(manager.page.getByTestId(`team-suspend-${bId}`))
          .toBeVisible({ timeout: 30_000 });

        await researcher.page.goto(`/${AR}/portfolio`);
        await expect(researcher.page.locator("article.card").filter({ hasText: PROJECT_TITLE }))
          .toBeVisible({ timeout: 30_000 });
        await researcher.page.goto(projectUrl);
        await expect(researcher.page.getByRole("heading", { name: PROJECT_TITLE }))
          .toBeVisible({ timeout: 30_000 });
      });

    // ═════════ الخطوة ح · بياناتُ البحث المشتركة ═════════
    //
    // **وهذا هو ما فتحه الترحيل 0036.** قبله كان `/projects/{id}/access`
    // يقول للإحصائيّ إنّه يحمل إدارةَ البيانات، ثمّ لا تُفتح له شاشةٌ
    // واحدة: مساراتُ التحليل لا تحمل معرّفَ البحث، ومنها ما لا يعرفه حتى
    // يقرأ الكيان — والقراءةُ في مستأجر البيت ترى صفرَ صفوف.
    await test.step("STEP H — the external statistician works on the project's data",
      async () => {
        // ── تهيئة: مجموعةٌ ونسخةٌ مشتقّة، بالـAPI ──
        //
        // **ولا شاشةَ إنشاءٍ لهما في المنتج لأحد** (أربعُ نداءاتٍ فقط في
        // شاشة التحليل: قائمتان وتجميدٌ واعتماد). فتُهيَّآن هكذا، ويبقى
        // **الفعلُ المقيس** — التجميد — في المتصفّح.
        const ownerToken = await tokenOf(owner.page);
        const headers = {
          Authorization: `Bearer ${ownerToken}`,
          "Content-Type": "application/json",
        };
        const projectId = projectUrl.split("/").pop()!;

        const created = await owner.page.request.post(
          `${API}/api/v1/analysis/datasets`,
          { headers, data: {
              project_id: projectId, name_ar: `بياناتُ المشترك ${RUN}`,
              classification: "C3", raw_label: "الرفع الأول",
              raw_checksum: "a".repeat(64), row_count: 50 } });
        expect(created.status(), await created.text()).toBe(201);
        const raw = await created.json();

        const derived = await owner.page.request.post(
          `${API}/api/v1/analysis/datasets/${raw.dataset_id}/versions`,
          { headers, data: {
              parent_version_id: raw.id, state: "cleaned", label: "منقّاة",
              checksum: "c".repeat(64), change_note_ar: "حذف صفوف ناقصة",
              row_count: 48 } });
        expect(derived.status(), await derived.text()).toBe(201);

        // ── ومن هنا: متصفّحٌ فقط ──
        //
        // **والطريقُ هو طريقُ المنتج القائم**: قسمُ البيانات في صفحة
        // البحث يفتح شاشةَ التحليل — لا شاشةٌ ثانيةٌ للمتعاونين.
        await researcher.page.goto(`${projectUrl}?section=data`);
        // **ورابطُ صفحةِ البحث نفسِه** — لا رابطُ القائمة الجانبية: المقصودُ
        // إثباتُ أنّ الطريقَ من داخل البحث يبلغ الشاشةَ القائمة.
        const toLink = researcher.page.locator("#main-content a.action")
          .filter({ hasText: "البيانات والتحليل" });
        await expect(toLink).toBeVisible({ timeout: 30_000 });
        await toLink.click();
        await researcher.page.waitForURL(/\/analysis$/, { timeout: 30_000 });

        // مجموعةُ البحث المشترك ظاهرةٌ له — وهي في مؤسسةٍ أخرى.
        const card = researcher.page.locator("article.card")
          .filter({ hasText: `بياناتُ المشترك ${RUN}` });
        await expect(card).toBeVisible({ timeout: 30_000 });

        // **فعلٌ حقيقيٌّ بإدارة البيانات: التجميد** — من الشاشة، بلا اعتراض.
        const freeze = card.getByRole("button", { name: /جمّد|Freeze/ }).first();
        await expect(freeze).toBeVisible();
        await freeze.click();
        await expect(card.locator(".badge-ok").first())
          .toBeVisible({ timeout: 30_000 });
      });

    // ═════════ الخطوة ط · نزعُ إدارة البيانات وإعادتها ═════════
    await test.step("STEP I — revoking manage_data closes the data door, not the project",
      async () => {
        // والنزعُ من شاشة الفريق — **بالمتصفّح**، وبلا تغييرِ دور.
        await manager.page.goto(`${projectUrl}?section=team`);
        const bId = await memberWithRole(manager.page, "statistician");
        await manage(manager.page, bId);
        await manager.page.getByTestId(`team-edit-permissions-${bId}`).click();
        await manager.page.getByTestId(`team-permission-${bId}-manage_data`).uncheck();
        await manager.page.getByTestId(`team-permission-save-${bId}`).click();
        await expect(manager.page.getByTestId(`team-permission-editor-${bId}`))
          .toHaveCount(0, { timeout: 30_000 });
        await expect(manager.page.getByTestId(`team-role-${bId}`))
          .toHaveValue("statistician");

        // **والبابُ يُقفل في الطلب التالي** — ولا خروجٌ ولا تجديدُ رمز.
        await researcher.page.goto(`/${AR}/analysis`);
        await expect(researcher.page.locator("article.card")
          .filter({ hasText: `بياناتُ المشترك ${RUN}` }))
          .toHaveCount(0, { timeout: 30_000 });

        // والبحثُ باقٍ: «أبحاثي» تعرضه، والرحلةُ تُفتح.
        await researcher.page.goto(`/${AR}/portfolio`);
        await expect(researcher.page.locator("article.card")
          .filter({ hasText: PROJECT_TITLE })).toBeVisible({ timeout: 30_000 });
        await researcher.page.goto(projectUrl);
        await expect(researcher.page.getByTestId("research-journey"))
          .toBeVisible({ timeout: 60_000 });

        // ── وتُعاد الصلاحيةُ، فيعود البابُ — والدورُ كما كان ──
        await manager.page.goto(`${projectUrl}?section=team`);
        const again = await memberWithRole(manager.page, "statistician");
        await manage(manager.page, again);
        await manager.page.getByTestId(`team-edit-permissions-${again}`).click();
        await manager.page.getByTestId(`team-permission-${again}-manage_data`).check();
        await manager.page.getByTestId(`team-permission-save-${again}`).click();
        await expect(manager.page.getByTestId(`team-permission-editor-${again}`))
          .toHaveCount(0, { timeout: 30_000 });

        await researcher.page.goto(`/${AR}/analysis`);
        await expect(researcher.page.locator("article.card")
          .filter({ hasText: `بياناتُ المشترك ${RUN}` }))
          .toBeVisible({ timeout: 30_000 });
      });

    // ═════════ وما لا يقع أبدًا ═════════
    await test.step("owner lifecycle controls never appear on a collaborator card",
      async () => {
        for (const person of [researcher, manager]) {
          await person.page.goto(`/${AR}/portfolio`);
          const card = person.page.locator("article.card").filter({ hasText: PROJECT_TITLE });
          await expect(card).toBeVisible({ timeout: 30_000 });
          // **وزرُّ حذفٍ على بحثِ غيرك ليس زرًّا لا يعمل: هو دعوى ملكيّة.**
          await expect(card.locator('[data-testid^="project-trash-"]')).toHaveCount(0);
          await expect(card.getByRole("button", { name: "نقل إلى السلّة" })).toHaveCount(0);
        }
        // وعلى بطاقة صاحبِه يظهر.
        await owner.page.goto(`/${AR}/portfolio`);
        const ownerCard = owner.page.locator("article.card").filter({ hasText: PROJECT_TITLE });
        await expect(ownerCard.locator('[data-testid^="project-trash-"]')).toHaveCount(1);
      });

    for (const person of [owner, researcher, manager]) {
      expect(person.serverErrors, `a 5xx answered for ${person.email}`).toEqual([]);
      await person.context.close();
    }
  });
