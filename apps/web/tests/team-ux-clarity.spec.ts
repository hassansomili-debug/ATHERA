import { expect, test, type Browser, type Page } from "@playwright/test";

/**
 * تجربةُ فريق البحث — **أفعالُ باحثٍ لا عناوينُ أقسام** (RC-T1C UX-1).
 *
 * ## ما رُدَّ، وما يُقاس
 *
 * ردَّ المالكُ شاشةَ الفريق بعد استعمالٍ يدويّ: «تغيّرت إدارةُ الفريق،
 * لكنّ التجربةَ سيّئةٌ وغيرُ واضحة». ولم يكن العطبُ في صلاحيةٍ ولا في
 * RLS: كانت الشاشةُ تعرض نموذجَ البيانات كلَّه في عمودٍ واحد — تسعُ
 * صلاحياتٍ وأدوارُ CRediT وحالُ التأليف والموافقةِ وطريقتُها على بطاقة
 * **كلِّ** عضو.
 *
 * **وفحصٌ يتأكّد أنّ العنوانَ موجود لا يقيس ذلك.** فما يُقاس هنا أفعال:
 * هل يجد صاحبُ البحث «دعوة باحث» في أوّل شاشة؟ وهل يصل إلى صلاحيّات
 * عضوٍ في نقرتين؟ وهل تبقى بطاقةُ العضو **خاليةً** من التفصيل الذي
 * أُخرِج منها؟
 *
 * ## والدعوى البنيويّة هي التي تعُضّ
 *
 * ثلاثُ دعاوى لا تمرّ إن عاد التصميمُ القديم:
 *
 *   ١ بطاقةُ العضو لا تحمل أسماءَ الصلاحيات ولا أدوارَ CRediT ولا حالَ
 *     الموافقة — وهي موجودةٌ كلُّها في اللوح.
 *   ٢ قسمُ فريقِ البحث لا يحمل صندوقَ قبولِ دعوةٍ برمز — والقبولُ في
 *     الشاشة العامّة حيث يملكه صاحبُه.
 *   ٣ «ما ينتظرني» لا يُرسم أصلًا حين لا ينتظر شيء.
 *
 * ## ولا تُضعَف دعوى أمانٍ من أجل شكل
 *
 * فغير المدير لا يرى زرَّ دعوةٍ ولا إدارةَ عضو — **ولا زرًّا معطَّلًا
 * يوهمه أنّه يقدر**. وإخفاءُ الزرّ تحسينُ عرضٍ لا حدُّ أمان: الخادمُ هو
 * الحدُّ، ويُفحص في `tests/test_at_rc_t1c_my_research.py`.
 */
const AR = "ar";
const EN = "en";

const RUN = `teamux-${Date.now().toString(36)}`;
const PASSWORD = "Team-Ux-Clarity-9f3b!";
const OWNER = `${RUN}-a@example.com`;
const MATE = `${RUN}-b@example.com`;
const PROJECT_TITLE = `بحثُ وضوحِ الفريق ${RUN}`;
const MATE_NAME = "زميلٌ مدعوّ";
const CONTRIBUTOR = "مساهمٌ بلا حساب";

/** نصوصٌ لا يجوز أن تعود إلى بطاقة العضو — من كتالوج العربيّة بنصِّه. */
const DETAIL_ONLY_AR = [
  "إدارة المصادر",          // اسمُ صلاحية
  "الاطّلاع على البحث",      // اسمُ صلاحيةٍ أخرى
  "عضو فريق، وليس مؤلفًا",   // حالُ تأليف
  "الوصول والصلاحيات",       // عنوانُ قسمٍ في اللوح
];

async function register(page: Page, email: string, name: string) {
  await page.goto(`/${EN}/register`);
  await page.locator("#reg-name").fill(name);
  await page.locator("#reg-email").fill(email);
  await page.locator("#reg-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").click();
  await page.waitForURL(`**/${EN}`, { timeout: 60_000 });
}

/** معرّفُ العضو الذي دورُه كذا — **من سمةٍ تُقرأ لا من نصٍّ يُرشَّح به**. */
async function memberIdByRole(page: Page, role: string): Promise<string> {
  const card = page.locator(`[data-member-role="${role}"]`).first();
  await expect(card).toBeVisible({ timeout: 30_000 });
  return (await card.getAttribute("data-testid"))!.replace("team-member-", "");
}

async function memberIdByName(page: Page, name: string): Promise<string> {
  const card = page.locator('[data-testid^="team-member-"]')
    .filter({ hasText: name }).first();
  await expect(card).toBeVisible({ timeout: 30_000 });
  return (await card.getAttribute("data-testid"))!.replace("team-member-", "");
}

/** يفتح لوحَ العضو ويتحقّق أنّه فُتح فعلًا. */
async function manage(page: Page, memberId: string) {
  await page.getByTestId(`team-manage-${memberId}`).click();
  await expect(page.getByTestId(`team-member-detail-${memberId}`))
    .toBeVisible({ timeout: 30_000 });
}

/** لا تمريرَ أفقيًّا — **والقياسُ على الوثيقة لا على العين**. */
async function noOverflow(page: Page, where: string) {
  const overflow = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    view: window.innerWidth,
  }));
  expect(overflow.scroll, `${where}: الصفحة تتمدّد أفقيًّا`)
    .toBeLessThanOrEqual(overflow.view + 1);
}

async function enrol(browser: Browser, email: string, name: string) {
  const context = await browser.newContext({
    // الحافظةُ تُمنح لأنّ «نسخ الرمز» فعلٌ يُقاس، لا نصٌّ يُقرأ.
    permissions: ["clipboard-read", "clipboard-write"],
  });
  const page = await context.newPage();
  const serverErrors: string[] = [];
  page.on("response", (r) => {
    if (r.status() >= 500) serverErrors.push(`${r.status()} ${r.url()}`);
  });
  await register(page, email, name);
  return { context, page, serverErrors };
}

test("فريقُ البحث: يُفهم في شاشة، ويُدار في نقرتين، ولا يُفشي تفصيلَه",
  async ({ browser }) => {
    test.setTimeout(420_000);

    const owner = await enrol(browser, OWNER, "Team Owner");
    const mate = await enrol(browser, MATE, "Team Mate");
    let projectUrl = "";
    let teamUrl = "";

    // ═════════ ١ · البحثُ، ثمّ قسمُ الفريق ═════════
    await test.step("صاحبُ البحث يُنشئ بحثًا ويفتح فريقَه", async () => {
      await owner.page.goto(`/${AR}/portfolio`);
      await owner.page.getByLabel("عنوان البحث").fill(PROJECT_TITLE);
      await owner.page.getByRole("button", { name: /أنشئ البحث/ }).click();
      await owner.page.waitForURL(/\/portfolio\/[0-9a-f-]{36}/, { timeout: 60_000 });
      projectUrl = owner.page.url().split("?")[0]!;
      teamUrl = `${projectUrl}?section=team`;
      await owner.page.goto(teamUrl);
      await expect(owner.page.getByTestId("team-workspace"))
        .toHaveAttribute("data-team-mode", "project", { timeout: 30_000 });
    });

    // ═════════ ٢ · خمسُ ثوانٍ: ما يُفهم بلا نقرة ═════════
    await test.step("الأعضاءُ هو البابُ الافتراضيّ، ودعوةُ باحثٍ فعلٌ أوّل",
      async () => {
        // **الأبوابُ ثلاثة، والمفتوحُ «الأعضاء».**
        await expect(owner.page.getByTestId("team-tab-members"))
          .toHaveAttribute("aria-selected", "true", { timeout: 30_000 });
        await expect(owner.page.getByTestId("team-panel-members")).toBeVisible();
        await expect(owner.page.getByTestId("team-tab-invitations")).toBeVisible();
        await expect(owner.page.getByTestId("team-tab-history")).toBeVisible();

        // ودعوةُ باحثٍ زرٌّ ظاهرٌ بلا تنقّل ولا حَدر.
        await expect(owner.page.getByTestId("team-invite-open")).toBeVisible();

        // **ووصلتي سطرٌ لا بطاقةٌ تطبع صلاحيّاتي التسع.**
        await expect(owner.page.getByTestId("team-my-access")).toBeVisible();
        await expect(owner.page.getByTestId("team-my-access")).toContainText("مالك");
        await expect(owner.page.getByTestId("team-my-access-detail")).toHaveCount(0);
        // وتُفتح عند الطلب وحده.
        await owner.page.getByTestId("team-my-access-toggle").click();
        await expect(owner.page.getByTestId("team-my-access-detail"))
          .toContainText("إدارة الفريق");
        await owner.page.getByTestId("team-my-access-toggle").click();
        await expect(owner.page.getByTestId("team-my-access-detail")).toHaveCount(0);

        // **ولا «ما ينتظرني» فارغًا**: بحثٌ جديدٌ لا بندَ فيه، فلا قسمَ له.
        await expect(owner.page.getByTestId("team-attention")).toHaveCount(0);

        // **ولا صندوقَ قبولِ دعوةٍ في قسم بحثٍ** — القبولُ شخصيٌّ ومحلُّه العامّة.
        await expect(owner.page.getByTestId("invitation-accept")).toHaveCount(0);
        await expect(owner.page.getByTestId("team-project-picker")).toHaveCount(0);

        // ولا سجلَّ ولا قراراتٍ في الشاشة الافتراضيّة.
        await expect(owner.page.getByTestId("team-activity")).toHaveCount(0);
        await expect(owner.page.getByTestId("team-decisions")).toHaveCount(0);
      });

    // ═════════ ٣ · دعوةُ باحثٍ: نافذةٌ، ثمّ رمزٌ يُنسخ مرّةً ═════════
    let inviteToken = "";
    await test.step("الدعوةُ تُتمّ في نافذةٍ واحدة، ورمزُها يُعرض ويُنسخ", async () => {
      await owner.page.getByTestId("team-invite-open").click();
      const dialog = owner.page.getByTestId("team-invite-dialog");
      await expect(dialog).toBeVisible({ timeout: 30_000 });
      // نافذةٌ لها اسمٌ مُعلَن — لا «حوارٌ» بلا عنوان.
      await expect(dialog).toHaveAttribute("aria-modal", "true");

      await owner.page.locator("#team-invite-name").fill(MATE_NAME);
      await owner.page.locator("#team-invite-email").fill(MATE);
      await owner.page.locator("#team-invite-role").selectOption("statistician");
      await owner.page.getByTestId("team-invite-submit").click();

      // **إعلانُ النجاح نافذةٌ لا بطاقةٌ تُدسّ في أسفل صفحة.**
      const token = owner.page.getByTestId("team-token");
      await expect(token).toBeVisible({ timeout: 30_000 });
      await expect(token).toContainText("مرّةً واحدةً");
      inviteToken = (await token.locator("code").innerText()).trim();
      expect(inviteToken.length).toBeGreaterThan(16);

      // **والنسخُ يعمل فعلًا** — لا زرٌّ يقول «تم النسخ» ولا ينسخ.
      await owner.page.getByTestId("team-token-copy").click();
      await expect(owner.page.getByTestId("team-token")).toContainText("تم النسخ");
      const clipped = await owner.page.evaluate(() => navigator.clipboard.readText());
      expect(clipped.trim()).toBe(inviteToken);

      await owner.page.getByTestId("team-token-done").click();
      await expect(owner.page.getByTestId("team-token")).toHaveCount(0);

      // والدعوةُ تظهر في بابها — لا مخلوطةً بالأعضاء.
      await owner.page.getByTestId("team-tab-invitations").click();
      const row = owner.page.locator('[data-testid^="team-invitation-"]')
        .filter({ hasText: MATE });
      await expect(row).toBeVisible({ timeout: 30_000 });
      await expect(owner.page.getByTestId("team-panel-members")).toHaveCount(0);
    });

    // ═════════ ٤ · مساهمٌ بلا حساب: إجراءٌ إضافيّ لا منافسٌ للدعوة ═════════
    await test.step("إضافةُ مساهمٍ بلا حساب مطويّةٌ تحت «إجراءات إضافية»",
      async () => {
        // **ولا يُعرض متساويًا مع دعوة باحث**: مطويٌّ حتى يُطلب.
        await expect(owner.page.getByTestId("team-advanced-panel")).toHaveCount(0);
        await owner.page.getByTestId("team-advanced-toggle").click();
        const panel = owner.page.getByTestId("team-advanced-panel");
        await expect(panel).toBeVisible({ timeout: 30_000 });
        await expect(panel).toContainText("بدون حساب");

        await owner.page.locator("#team-contributor-name").fill(CONTRIBUTOR);
        // ودورُ CRediT يُختار يدويًّا — ولا يُقترح من نشاطٍ في المنصّة.
        await panel.locator('input[type="checkbox"]').first().check();
        await owner.page.getByTestId("team-add-contributor").click();

        await owner.page.getByTestId("team-tab-members").click();
        await expect(
          owner.page.locator('[data-testid^="team-member-"]').filter({ hasText: CONTRIBUTOR }),
        ).toBeVisible({ timeout: 30_000 });
      });

    // ═════════ ٥ · الكشفُ التدريجيّ — وهذه الدعوى هي التي تعُضّ ═════════
    await test.step("بطاقةُ العضو تقول اسمًا ودورًا وحالًا — ولا تُفشي التفصيل",
      async () => {
        const id = await memberIdByName(owner.page, CONTRIBUTOR);
        const card = owner.page.getByTestId(`team-member-${id}`);

        // ما **يجب** أن يُقرأ بلا نقرة.
        await expect(card).toContainText(CONTRIBUTOR);
        await expect(card).toContainText("نشِط");
        await expect(card.getByTestId(`team-manage-${id}`)).toBeVisible();
        // ومؤشِّراتٌ تُعَدّ ولا تُسرَد.
        await expect(card).toContainText("مساهمات CRediT:");

        // **وما لا يجوز أن يُقرأ عليها** — وهو ما كان يُطبع كلُّه.
        for (const needle of DETAIL_ONLY_AR) {
          await expect(
            card,
            `بطاقةُ العضو عادت تطبع «${needle}» — والكشفُ التدريجيّ انتقض`,
          ).not.toContainText(needle);
        }
        // ولا محرّرَ صلاحياتٍ ولا مُنتقي دورٍ ولا أزرارَ مدخلٍ على البطاقة.
        await expect(card.locator('[data-testid^="team-role-"]')).toHaveCount(0);
        await expect(card.locator('[data-testid^="team-permission-"]')).toHaveCount(0);
        await expect(card.locator('[data-testid^="team-suspend-"]')).toHaveCount(0);
        await expect(card.locator('[data-testid^="team-remove-"]')).toHaveCount(0);
      });

    // ═════════ ٦ · والتفصيلُ كاملٌ في موضعه ═════════
    await test.step("لوحُ العضو: الوصولُ، ثمّ المساهمةُ، ثمّ التأليفُ والموافقة",
      async () => {
        const id = await memberIdByName(owner.page, CONTRIBUTOR);
        await manage(owner.page, id);

        // ── الوصول: الدورُ والصلاحيةُ مفصولتان، والفرقُ مقول ──
        const accessPanel = owner.page.getByTestId(`team-member-panel-access-${id}`);
        await expect(accessPanel).toBeVisible();
        await expect(accessPanel).toContainText("الدورُ موقعٌ في الفريق");
        await expect(owner.page.getByTestId(`team-role-${id}`)).toBeVisible();
        await expect(owner.page.getByTestId(`team-member-permissions-${id}`)).toBeVisible();

        // ── المساهمةُ العلمية: CRediT هنا لا على البطاقة ──
        await owner.page.getByTestId("team-member-tab-contribution").click();
        await expect(owner.page.getByTestId(`team-member-credit-${id}`))
          .toBeVisible({ timeout: 30_000 });

        // ── التأليفُ والموافقة: هنا وحدَه ──
        await owner.page.getByTestId("team-member-tab-authorship").click();
        await expect(owner.page.getByTestId(`team-member-authorship-${id}`))
          .toContainText("ليس مؤلفًا", { timeout: 30_000 });
        await expect(owner.page.getByTestId(`team-member-consent-${id}`)).toBeVisible();

        // **والبطاقةُ خلفَ اللوح ما زالت خاليةً من هذا كلِّه.**
        await owner.page.getByTestId(`team-member-detail-${id}-close`).click();
        await expect(owner.page.getByTestId(`team-member-detail-${id}`)).toHaveCount(0);
        await expect(owner.page.getByTestId(`team-member-${id}`))
          .not.toContainText("ليس مؤلفًا");
      });

    // ═════════ ٧ · الصلاحيةُ تُحرَّر، والدورُ لا يُمسّ ═════════
    await test.step("تحريرُ صلاحيةٍ مُجمَّعةٍ بالغرض لا يغيّر الدور", async () => {
      const id = await memberIdByName(owner.page, CONTRIBUTOR);
      await manage(owner.page, id);
      const roleBefore = await owner.page.getByTestId(`team-role-${id}`).inputValue();

      await owner.page.getByTestId(`team-edit-permissions-${id}`).click();
      const editor = owner.page.getByTestId(`team-permission-editor-${id}`);
      await expect(editor).toBeVisible({ timeout: 30_000 });
      // **والتجميعُ عرضٌ**: المفاتيحُ مفاتيحُ الخادم بنصِّها.
      await expect(editor.locator("legend")).not.toHaveCount(0);
      await owner.page.getByTestId(`team-permission-${id}-view_project`).check();
      await owner.page.getByTestId(`team-permission-${id}-manage_sources`).check();
      await owner.page.getByTestId(`team-permission-save-${id}`).click();
      // ويُغلق المحرّرُ بقبول الخادم لا بضغط الزرّ.
      await expect(editor).toHaveCount(0, { timeout: 30_000 });
      await expect(owner.page.getByTestId(`team-role-${id}`)).toHaveValue(roleBefore);
      await expect(owner.page.getByTestId(`team-member-permissions-${id}`))
        .toContainText("إدارة المصادر");
    });

    // ═════════ ٨ · الإيقافُ والإعادةُ من جواب الكتابة — لا من قراءةٍ بعدها ═════════
    await test.step("الإيقافُ يُرى فورًا، والإعادةُ كذلك — وRC-T1C لم يرتدّ",
      async () => {
        const id = await memberIdByName(owner.page, CONTRIBUTOR);
        await expect(owner.page.getByTestId(`team-member-detail-${id}`)).toBeVisible();

        await owner.page.getByTestId(`team-suspend-${id}`).click();
        await expect(
          owner.page.getByTestId(`team-restore-${id}`),
          "الإيقافُ لم يُرسَم من جواب الكتابة",
        ).toBeVisible({ timeout: 30_000 });
        await expect(owner.page.getByTestId(`team-suspend-${id}`)).toHaveCount(0);
        // والبطاقةُ تقرأ الصفَّ نفسَه، فتتبع اللوحَ بلا قراءةٍ ثانية.
        await expect(owner.page.getByTestId(`team-member-${id}`))
          .toHaveAttribute("data-member-access", "suspended");

        await owner.page.getByTestId(`team-restore-${id}`).click();
        await expect(owner.page.getByTestId(`team-suspend-${id}`))
          .toBeVisible({ timeout: 30_000 });
        await expect(owner.page.getByTestId(`team-member-${id}`))
          .toHaveAttribute("data-member-access", "active");
      });

    // ═════════ ٩ · الإزالةُ تُؤكَّد، ولا يُقال «حذف» ═════════
    await test.step("الإزالةُ تطلب تأكيدًا يقول ما يبقى", async () => {
      const id = await memberIdByName(owner.page, CONTRIBUTOR);
      await owner.page.getByTestId(`team-remove-${id}`).click();
      const confirm = owner.page.getByTestId(`team-remove-confirm-${id}`);
      await expect(confirm).toBeVisible({ timeout: 30_000 });
      // **ولا تُدَّعى حذفٌ**: المساهمةُ والتاريخُ يبقيان.
      await expect(confirm).toContainText("لا تُحذف مساهماتُه السابقة");
      // ويُرجَع عنها بلا أثر.
      await expect(confirm.getByRole("button")).not.toHaveCount(0);
      await owner.page.getByTestId(`team-remove-confirm-${id}-close`).click();
      await expect(confirm).toHaveCount(0);
      await expect(owner.page.getByTestId(`team-member-${id}`))
        .toHaveAttribute("data-member-access", "active");
      await owner.page.getByTestId(`team-member-detail-${id}-close`).click();
    });

    // ═════════ ١٠ · السجلّ: وقائعُ وقراراتٌ في بابهما ═════════
    await test.step("السجلُّ بابٌ فيه فرعان، ولا يشغل شاشةَ الأعضاء", async () => {
      await owner.page.getByTestId("team-tab-history").click();
      await expect(owner.page.getByTestId("team-activity")).toBeVisible({ timeout: 30_000 });
      // ووقائعُ حقيقيّةٌ وقعت: دعوةٌ، وإضافةُ مساهم، وإيقافٌ وإعادة.
      await expect(owner.page.getByTestId("team-activity").locator("article.card").first())
        .toBeVisible();
      await owner.page.getByTestId("team-history-tab-decisions").click();
      await expect(owner.page.getByTestId("team-decisions")).toBeVisible({ timeout: 30_000 });
      await expect(owner.page.getByTestId("team-activity")).toHaveCount(0);

      // والعودةُ إلى الأعضاء تُخرج السجلَّ من الشاشة.
      await owner.page.getByTestId("team-tab-members").click();
      await expect(owner.page.getByTestId("team-panel-history")).toHaveCount(0);
    });

    // ═════════ ١١ · القبولُ الشخصيّ في الشاشة العامّة ═════════
    await test.step("الزميلُ يجد «الانضمام إلى فريق بحث» في /team ويقبل بحسابه",
      async () => {
        await mate.page.goto(`/${AR}/team`);
        const accept = mate.page.getByTestId("invitation-accept");
        await expect(accept).toBeVisible({ timeout: 30_000 });
        await expect(accept).toContainText("الانضمام إلى فريق بحث");
        await mate.page.getByTestId("invitation-token-input").fill(inviteToken);
        await mate.page.getByTestId("invitation-accept-submit").click();
        await expect(accept.locator(".badge-ok")).toBeVisible({ timeout: 30_000 });

        // والهيئةُ العامّة تنتقي البحثَ، ثمّ تُعرض بالبنية نفسِها.
        await mate.page.goto(`/${AR}/team`);
        await expect(mate.page.getByTestId("team-workspace"))
          .toHaveAttribute("data-team-mode", "global", { timeout: 30_000 });
        await expect(mate.page.getByTestId("team-project-picker")).toBeVisible();
        await expect(mate.page.getByTestId("team-tab-members")).toBeVisible();
      });

    // ═════════ ١٢ · غيرُ المدير: يقرأ ولا يُوهَم ═════════
    await test.step("المتعاونُ يرى الفريقَ ولا يرى أدواتَ ما لا يملك", async () => {
      await mate.page.goto(teamUrl);
      await expect(mate.page.getByTestId("team-my-access"))
        .toContainText("متعاون", { timeout: 30_000 });

      // **ولا زرًّا معطَّلًا يوهمه**: غائبٌ لا مُعطَّل.
      await expect(mate.page.getByTestId("team-invite-open")).toHaveCount(0);
      await expect(mate.page.getByTestId("team-tab-invitations")).toHaveCount(0);
      await expect(mate.page.locator('[data-testid^="team-manage-"]')).toHaveCount(0);
      await expect(mate.page.locator('[data-testid^="team-role-"]')).toHaveCount(0);
      await expect(mate.page.locator('[data-testid^="team-edit-permissions-"]')).toHaveCount(0);
      await expect(mate.page.locator('[data-testid^="team-suspend-"]')).toHaveCount(0);
      await expect(mate.page.locator('[data-testid^="team-remove-"]')).toHaveCount(0);
      await expect(mate.page.getByRole("button", { name: "أرسل الدعوة" })).toHaveCount(0);

      // ويقرأ الأعضاءَ والسجلّ.
      await expect(mate.page.locator('[data-testid^="team-member-"]').first())
        .toBeVisible({ timeout: 30_000 });
      await expect(mate.page.getByTestId("team-tab-history")).toBeVisible();
    });

    // ═════════ ١٣ · ٣٧٥px والعربيّةُ والإنجليزيّة ═════════
    await test.step("٣٧٥px: لا تمريرَ أفقيًّا في أيّ من الأسطح", async () => {
      await owner.page.setViewportSize({ width: 375, height: 720 });
      for (const locale of [AR, EN]) {
        const url = `${projectUrl.replace(`/${AR}/`, `/${locale}/`)}?section=team`;
        await owner.page.goto(url);
        await expect(owner.page.getByTestId("team-panel-members"))
          .toBeVisible({ timeout: 30_000 });
        await noOverflow(owner.page, `${locale} · الأعضاء`);

        const id = await memberIdByRole(owner.page, "statistician");
        await manage(owner.page, id);
        await noOverflow(owner.page, `${locale} · لوحُ العضو`);
        await owner.page.getByTestId(`team-edit-permissions-${id}`).click();
        await expect(owner.page.getByTestId(`team-permission-editor-${id}`)).toBeVisible();
        await noOverflow(owner.page, `${locale} · محرّرُ الصلاحيات`);
        // وأزرارُ اللوح داخلَ الشاشة لا خارجها.
        const save = owner.page.getByTestId(`team-permission-save-${id}`);
        const box = (await save.boundingBox())!;
        expect(box.x, `${locale} · زرُّ الحفظ خارج الشاشة`).toBeGreaterThanOrEqual(0);
        expect(box.x + box.width).toBeLessThanOrEqual(375 + 1);
        await owner.page.getByTestId(`team-member-detail-${id}-close`).click();

        await owner.page.getByTestId("team-invite-open").click();
        await expect(owner.page.getByTestId("team-invite-dialog")).toBeVisible();
        await noOverflow(owner.page, `${locale} · نافذةُ الدعوة`);
        await owner.page.getByTestId("team-invite-dialog-close").click();

        await owner.page.getByTestId("team-tab-invitations").click();
        await expect(owner.page.getByTestId("team-panel-invitations")).toBeVisible();
        await noOverflow(owner.page, `${locale} · الدعوات`);

        await owner.page.getByTestId("team-tab-history").click();
        await expect(owner.page.getByTestId("team-panel-history")).toBeVisible();
        await noOverflow(owner.page, `${locale} · السجل`);
      }

      // والشاشةُ العامّة كذلك.
      await mate.page.setViewportSize({ width: 375, height: 720 });
      for (const locale of [AR, EN]) {
        await mate.page.goto(`/${locale}/team`);
        await expect(mate.page.getByTestId("team-project-picker"))
          .toBeVisible({ timeout: 30_000 });
        await noOverflow(mate.page, `${locale} · الفريقُ العامّ`);
      }
    });

    // ═════════ ١٤ · والإنجليزيّةُ نصٌّ من الكتالوج لا ترجمةٌ في الشيفرة ═════════
    await test.step("الإنجليزيّة: أسماءُ الأبواب والأفعال من كتالوجها", async () => {
      await owner.page.setViewportSize({ width: 1280, height: 800 });
      await owner.page.goto(`${projectUrl.replace(`/${AR}/`, `/${EN}/`)}?section=team`);
      await expect(owner.page.getByTestId("team-tab-members"))
        .toHaveText("Members", { timeout: 30_000 });
      await expect(owner.page.getByTestId("team-tab-invitations")).toHaveText("Invitations");
      await expect(owner.page.getByTestId("team-tab-history")).toHaveText("History");
      await expect(owner.page.getByTestId("team-invite-open")).toHaveText("Invite a researcher");
      await expect(owner.page.getByTestId("team-my-access"))
        .toContainText("You are the project owner");
      const id = await memberIdByRole(owner.page, "statistician");
      await manage(owner.page, id);
      await expect(owner.page.getByTestId("team-member-tab-access"))
        .toHaveText("Access & permissions");
      await expect(owner.page.getByTestId("team-member-tab-contribution"))
        .toHaveText("Scientific contribution");
      await expect(owner.page.getByTestId("team-member-tab-authorship"))
        .toHaveText("Authorship & consent");
    });

    // ═════════ ١٥ · الطبقةُ تُغلق بلوحة المفاتيح ═════════
    await test.step("Escape تُغلق اللوح، والتركيزُ يعود إلى زرّه", async () => {
      const id = await memberIdByRole(owner.page, "statistician");
      await expect(owner.page.getByTestId(`team-member-detail-${id}`)).toBeVisible();
      await owner.page.keyboard.press("Escape");
      await expect(owner.page.getByTestId(`team-member-detail-${id}`)).toHaveCount(0);
      await expect(owner.page.getByTestId(`team-manage-${id}`)).toBeFocused();
    });

    for (const person of [owner, mate]) {
      expect(person.serverErrors, "a 5xx answered during the Team UX journey").toEqual([]);
      await person.context.close();
    }
  });

/* ════════════════════════════════════════════════════════════════════════
   ثلاثُ دعاوى أُضيفت بعد مراجعةٍ مستقلّة سبقت مراجعةَ المالك اليدويّة
   ════════════════════════════════════════════════════════════════════════ */

/** صاحبُ بحثٍ ومعه أبحاثٌ فيها مساهمٌ مُميَّزٌ بالاسم — للتفريق بلا لبس. */
async function ownerWithProjects(
  browser: Browser, tag: string, titles: string[],
): Promise<{
  context: Awaited<ReturnType<Browser["newContext"]>>;
  page: Page;
  serverErrors: string[];
  projects: { title: string; id: string; url: string; contributor: string }[];
}> {
  const person = await enrol(browser, `${tag}@example.com`, `Owner ${tag}`);
  const projects: { title: string; id: string; url: string; contributor: string }[] = [];
  for (const title of titles) {
    await person.page.goto(`/${AR}/portfolio`);
    await person.page.getByLabel("عنوان البحث").fill(title);
    await person.page.getByRole("button", { name: /أنشئ البحث/ }).click();
    await person.page.waitForURL(/\/portfolio\/[0-9a-f-]{36}/, { timeout: 60_000 });
    const url = person.page.url().split("?")[0]!;
    const id = url.split("/").pop()!;
    const contributor = `مساهمُ ${title}`;

    // مساهمٌ باسمٍ يخصّ هذا البحثَ وحده — فالتسرّبُ يُرى بالعين.
    await person.page.goto(`${url}?section=team`);
    await person.page.getByTestId("team-tab-invitations").click();
    await person.page.getByTestId("team-advanced-toggle").click();
    await person.page.locator("#team-contributor-name").fill(contributor);
    await person.page.getByTestId("team-add-contributor").click();
    await person.page.getByTestId("team-tab-members").click();
    await expect(
      person.page.locator('[data-testid^="team-member-"]').filter({ hasText: contributor }),
    ).toBeVisible({ timeout: 30_000 });

    projects.push({ title, id, url, contributor });
  }
  return { ...person, projects };
}

test("تبديلُ البحث لا يعرض صفوفَ بحثٍ تحت اسم بحثٍ آخر", async ({ browser }) => {
  test.setTimeout(300_000);
  const tag = `swap-${Date.now().toString(36)}`;
  const owner = await ownerWithProjects(browser, tag, [`ألف ${tag}`, `باء ${tag}`]);
  const [alpha, beta] = owner.projects;
  const page = owner.page;

  // ── «أ» معروضٌ ومستقرّ ──
  await page.goto(`/${AR}/team`);
  await expect(page.getByTestId("team-project-picker")).toBeVisible({ timeout: 30_000 });
  await page.getByTestId("team-project-picker").selectOption(alpha!.id);
  await expect(
    page.locator('[data-testid^="team-member-"]').filter({ hasText: alpha!.contributor }),
  ).toBeVisible({ timeout: 30_000 });

  // ── يُحتجَز جوابُ أعضاء «ب» احتجازًا حتميًّا: لا مهلةَ ولا رجاء ──
  let release: (() => void) | null = null;
  let seen: (() => void) | null = null;
  let held = false;
  const requested = new Promise<void>((resolve) => { seen = resolve; });
  await page.route(`**/api/v1/projects/${beta!.id}/members`, async (route) => {
    // والتحقيقُ المسبق (OPTIONS) يمضي: المحتجَزُ هو القراءةُ نفسُها.
    // **واحتجازٌ واحدٌ لا دائم**: قراءةٌ ثانيةٌ تمضي، فلا يُلغى المسارُ
    // وهو يحتجز طلبًا — وذاك يُفقد الطلبَ ويُسقط الفحصَ بعلّةٍ من أدواته.
    if (route.request().method() !== "GET" || held) {
      await route.continue();
      return;
    }
    held = true;
    seen?.();
    await new Promise<void>((resolve) => { release = resolve; });
    await route.continue();
  });

  await page.getByTestId("team-project-picker").selectOption(beta!.id);
  await requested;

  // ══ في نافذةِ الاحتجاز: المُنتقي يقول «ب»، ولا شيءَ من «أ» معروض ══
  await test.step("في نافذة الطلب: لا صفَّ من البحث السابق", async () => {
    await expect(page.getByTestId("team-project-picker")).toHaveValue(beta!.id);

    // **الدعوى الأولى أوّلًا**: لا صفَّ من «أ» يُقرأ تحت اسم «ب». وتُقدَّم
    // على دعوى الانتظار عمدًا — فالضررُ هو الصفُّ الكاذب، لا غيابُ دوّارة.
    await expect(
      page.locator('[data-testid^="team-member-"]').filter({ hasText: alpha!.contributor }),
      "أعضاءُ البحث السابق معروضون تحت اسم البحث الجديد",
    ).toHaveCount(0);
    await expect(page.locator('[data-testid^="team-member-"]')).toHaveCount(0);
    await expect(page.getByTestId("team-my-access")).toHaveCount(0);
    await expect(page.getByTestId("team-summary")).toHaveCount(0);
    await expect(page.getByTestId("team-attention")).toHaveCount(0);

    // ثمّ يُقال للباحث إنّ القراءةَ جارية — فلا شاشةٌ خاليةٌ بلا سبب.
    await expect(page.getByTestId("team-loading")).toBeVisible();

    // **ولا فعلٌ يُمكَّن على صفوفٍ لا تخصّ المعروض.**
    await expect(page.locator('[data-testid^="team-manage-"]')).toHaveCount(0);
    await expect(page.getByTestId("team-invite-open")).toHaveCount(0);

    // وبابُ الدعوات غائبٌ أصلًا: صلاحيةُ «أ» لا تُقرأ إذنًا على «ب».
    await expect(page.getByTestId("team-tab-invitations")).toHaveCount(0);
    await expect(page.locator('[data-testid^="team-invitation-"]')).toHaveCount(0);

    // **والسجلُّ يُفتح فيُرى خاليًا** — لا وقائعَ «أ» ولا قراراتُه. وهذا
    // أقوى من غيابِ اللوحة: اللوحةُ معروضةٌ ولا صفَّ فيها من بحثٍ آخر.
    await page.getByTestId("team-tab-history").click();
    const activity = page.getByTestId("team-activity");
    await expect(activity).toBeVisible();
    await expect(activity.locator("article.card")).toHaveCount(0);
    await page.getByTestId("team-history-tab-decisions").click();
    const ledger = page.getByTestId("team-decisions");
    await expect(ledger).toBeVisible();
    await expect(ledger.locator("article.card")).toHaveCount(0);
  });

  // ══ ويُفرَج، فيظهر «ب» وحدَه ══
  release!();
  await page.getByTestId("team-tab-members").click();
  await expect(
    page.locator('[data-testid^="team-member-"]').filter({ hasText: beta!.contributor }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(
    page.locator('[data-testid^="team-member-"]').filter({ hasText: alpha!.contributor }),
  ).toHaveCount(0);
  await expect(page.getByTestId("team-my-access")).toBeVisible();

  expect(owner.serverErrors, "a 5xx answered during the project switch").toEqual([]);
  await owner.context.close();
});

test("دعوةٌ مردودةٌ تُقرأ داخل نافذتها، وحقولُها باقيةٌ لتُصحَّح",
  async ({ browser }) => {
    test.setTimeout(300_000);
    const tag = `rej-${Date.now().toString(36)}`;
    const owner = await ownerWithProjects(browser, tag, [`ردّ ${tag}`]);
    const page = owner.page;
    const project = owner.projects[0]!;
    const invitee = `${tag}-mate@example.com`;

    await page.goto(`${project.url}?section=team`);
    await expect(page.getByTestId("team-panel-members")).toBeVisible({ timeout: 30_000 });

    // ── دعوةٌ أولى تنجح، فتصير الثانيةُ إلى البريد نفسِه مردودةً بحقّ ──
    await page.getByTestId("team-invite-open").click();
    await page.locator("#team-invite-name").fill("زميلٌ أوّل");
    await page.locator("#team-invite-email").fill(invitee);
    await page.getByTestId("team-invite-submit").click();
    await expect(page.getByTestId("team-token")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("team-token-done").click();

    // ── والردُّ ردُّ خادمٍ حقيقيّ: `team.invitation_already_live` (٤٠٩) ──
    await page.getByTestId("team-invite-open").click();
    const dialog = page.getByTestId("team-invite-dialog");
    await expect(dialog).toBeVisible({ timeout: 30_000 });
    await page.locator("#team-invite-name").fill("زميلٌ مكرَّر");
    await page.locator("#team-invite-email").fill(invitee);
    await page.locator("#team-invite-role").selectOption("statistician");
    await page.getByTestId("team-invite-submit").click();

    // **العلّةُ داخلَ النافذة** — لا في الصفحة خلفها.
    const inside = dialog.getByTestId("team-invite-error");
    await expect(
      inside,
      "رسالةُ الرفض ليست داخل النافذة — فهي مرسومةٌ خلف ما ينظر إليه المدير",
    ).toBeVisible({ timeout: 30_000 });
    await expect(inside).toContainText("توجد دعوة قائمة لهذا البريد");
    // ولها دلالةُ تنبيهٍ تُسمَع.
    await expect(inside).toHaveAttribute("role", "alert");

    // والنافذةُ باقية، ولا رمزَ يُعلَن، والحقولُ كما كُتبت.
    await expect(dialog).toBeVisible();
    await expect(page.getByTestId("team-token")).toHaveCount(0);
    await expect(page.locator("#team-invite-name")).toHaveValue("زميلٌ مكرَّر");
    await expect(page.locator("#team-invite-email")).toHaveValue(invitee);
    await expect(page.locator("#team-invite-role")).toHaveValue("statistician");

    // ── ويُصحَّح البريدُ فتنجح، فتُمحى العلّةُ ويُعلَن الرمز ──
    await page.locator("#team-invite-email").fill(`${tag}-other@example.com`);
    await page.getByTestId("team-invite-submit").click();
    await expect(page.getByTestId("team-token")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("team-invite-error")).toHaveCount(0);
    await expect(page.getByTestId("team-token").locator("code")).not.toBeEmpty();
    await page.getByTestId("team-token-done").click();

    expect(owner.serverErrors, "a 5xx answered during the rejection check").toEqual([]);
    await owner.context.close();
  });

test("الأعلى يملك Escape: التأكيدُ يُغلق وحدَه، ثمّ اللوح", async ({ browser }) => {
  test.setTimeout(300_000);
  const tag = `esc-${Date.now().toString(36)}`;
  const owner = await ownerWithProjects(browser, tag, [`طبقات ${tag}`]);
  const page = owner.page;
  const project = owner.projects[0]!;

  await page.goto(`${project.url}?section=team`);
  const id = await memberIdByName(page, project.contributor);
  await manage(page, id);
  const drawer = page.getByTestId(`team-member-detail-${id}`);
  const confirm = page.getByTestId(`team-remove-confirm-${id}`);

  await page.getByTestId(`team-remove-${id}`).click();
  await expect(confirm).toBeVisible({ timeout: 30_000 });

  // ══ و`Tab` محصورٌ في الأعلى وحده ══
  //
  // فلو بلغ المفتاحُ سطحَ اللوح لَطبّق فخَّه هو، فسحب التركيزَ إلى لوحٍ
  // محجوبٍ بنافذةٍ فوقه — أي مستعملٌ يكتب في ما لا يرى.
  for (let step = 0; step < 7; step += 1) await page.keyboard.press("Tab");
  const trapped = await page.evaluate((selector) => {
    const box = document.querySelector(selector);
    return Boolean(box && document.activeElement && box.contains(document.activeElement));
  }, `[data-testid="team-remove-confirm-${id}"]`);
  expect(trapped, "التركيزُ خرج من نافذة التأكيد وهي مفتوحة").toBe(true);

  // ══ ضغطةٌ أولى: التأكيدُ وحدَه يُغلق، واللوحُ باقٍ ══
  await page.keyboard.press("Escape");
  await expect(confirm).toHaveCount(0);
  await expect(
    drawer,
    "ضغطةُ Escape أغلقت اللوحَ مع نافذته — فالأسفلُ يسمع مفتاحَ الأعلى",
  ).toBeVisible();
  await expect(page.getByTestId(`team-remove-${id}`)).toBeFocused();

  // ══ وضغطةٌ ثانية: اللوحُ يُغلق، والتركيزُ يعود إلى زرّ «إدارة» ══
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
  await expect(page.getByTestId(`team-manage-${id}`)).toBeFocused();

  // **ولا عضوٌ أُزيل**: المفتاحُ يُغلق ولا يُنفّذ.
  await expect(page.getByTestId(`team-member-${id}`))
    .toHaveAttribute("data-member-access", "active");

  expect(owner.serverErrors, "a 5xx answered during the overlay check").toEqual([]);
  await owner.context.close();
});
