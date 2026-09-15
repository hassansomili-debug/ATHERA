import { expect, test, type Page } from "@playwright/test";

/**
 * إيقافُ المدخل وإعادتُه لا يتّكلان على قراءةٍ تتبع الكتابة | RC-T1-H1.
 *
 * **العطبُ الذي يحرسه هذا الملف أسقط بوّابةَ الدمج فعلًا.** ردَّ الخادمُ
 * ٢٠٠ على `PATCH …/access`، ثمّ قرأت الشاشةُ قائمةَ الأعضاء على الاتصال
 * نفسِه فعادت «نشِط» — فبقي زرُّ «أوقِف» ولم يظهر «أعِد» أبدًا. ولا خطأَ
 * في الخادم ولا في القاعدة: **الردُّ يسبق الإثبات** (RC-T1-H1، وهو باقٍ
 * مفتوحًا؛ هذه الرقعةُ تُغلق مظهرَه في هذا الباب لا أصلَه).
 *
 * ## ولمَ يُثبَّت القارئُ على حالٍ قديمة
 *
 * السباقُ في الإنتاج دون المليّ ثانية: يقع على مُشغِّلٍ مزدحم ولا يقع
 * على جهازٍ سريع. وفحصٌ ينتظر ويأمل ليس حارسًا — يمرّ في اليوم الذي
 * يعمل فيه ويسكت في اليوم الذي لا يعمل.
 *
 * **فيُصنع السباقُ حتميًّا**: تُثبَّت قراءةُ `GET …/members` على اللقطة
 * التي لم تَرَ التغييرَ بعد. فإن كانت الشاشةُ تبني حالَها من تلك القراءة
 * فلن ترى التغييرَ أبدًا — لا بعد ثلاثين ثانية ولا بعد ساعة — وإن كانت
 * تبني من **جواب الكتابة** فهي صحيحةٌ مهما تأخّر القارئ.
 *
 * ولا مهلةَ تُمدّ، ولا إعادةَ محاولة، ولا انتظار: الفرقُ بنيويٌّ لا زمنيّ.
 *
 * **والاعتراضُ هنا على القارئ وحده.** `PATCH` يمضي إلى الخادم الحقيقيّ
 * ويُغيّر الصفَّ فعلًا — فما يُقاس هو مصدرُ ما تعرضه الشاشة، لا تزييفُ
 * نتيجة.
 */
const AR = "ar";
const EN = "en";

const RUN = `race-${Date.now().toString(36)}`;
const PASSWORD = "Commit-Race-9f3b!";
const OWNER = `${RUN}-a@example.com`;
const MATE = `${RUN}-b@example.com`;
const PROJECT_TITLE = `بحثُ سباقِ الإثبات ${RUN}`;

interface Member {
  id: string;
  access_state: string;
  [key: string]: unknown;
}

async function register(page: Page, email: string, name: string) {
  await page.goto(`/${EN}/register`);
  await page.locator("#reg-name").fill(name);
  await page.locator("#reg-email").fill(email);
  await page.locator("#reg-password").fill(PASSWORD);
  await page.locator("form button[type=submit]").click();
  await page.waitForURL(`**/${EN}`, { timeout: 60_000 });
}

/**
 * يُثبّت قراءةَ الأعضاء على حالٍ بعينها — **محاكاةُ قارئٍ لم يَرَ الإثبات**.
 *
 * ولا يمسّ `PATCH`: يمضي إلى الخادم ويُغيّر الصفَّ حقًّا.
 */
async function pinMembersRead(
  page: Page, snapshot: Member[], memberId: string, state: string,
) {
  const body = JSON.stringify(
    snapshot.map((row) =>
      row.id === memberId ? { ...row, access_state: state } : row),
  );
  await page.route(
    (url) => url.pathname.endsWith("/members"),
    async (route) => {
      if (route.request().method() !== "GET") {
        await route.fallback();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        // الأصلانِ مختلفان (٣٠٠٠ و٨٠٠٠)، فبلا هذه الترويسة يحجب
        // المتصفّحُ الجوابَ المُلفَّق ويصير الفحصُ يقيس CORS لا المنتج.
        headers: { "Access-Control-Allow-Origin": "*" },
        body,
      });
    },
  );
}

test("الإيقافُ والإعادةُ يُرسمان من جواب الكتابة، لا من قراءةٍ بعدها",
  async ({ browser }) => {
    test.setTimeout(240_000);

    const ownerCtx = await browser.newContext();
    const mateCtx = await browser.newContext();
    const owner = await ownerCtx.newPage();
    const mate = await mateCtx.newPage();
    const serverErrors: string[] = [];
    for (const page of [owner, mate]) {
      page.on("response", (r) => {
        if (r.status() >= 500) serverErrors.push(`${r.status()} ${r.url()}`);
      });
    }

    await register(owner, OWNER, "Race Owner");
    await register(mate, MATE, "Race Mate");

    // ── بحثٌ وعضوٌ حقيقيّ: يُدعى بالبريد ويقبل بحسابه ──
    await owner.goto(`/${AR}/portfolio`);
    await owner.getByLabel("عنوان البحث").fill(PROJECT_TITLE);
    await owner.getByRole("button", { name: /أنشئ البحث/ }).click();
    await owner.waitForURL(/\/portfolio\/[0-9a-f-]{36}/, { timeout: 60_000 });
    const projectUrl = owner.url().split("?")[0]!;

    await owner.goto(`${projectUrl}?section=team`);
    await expect(owner.getByTestId("team-my-access")).toBeVisible({ timeout: 30_000 });
    await owner.getByLabel("الاسم كما يُنشر").first().fill("زميلٌ يُوقَف");
    await owner.getByLabel("البريد").first().fill(MATE);
    await owner.getByRole("button", { name: "أرسل الدعوة" }).click();
    const tokenBox = owner.getByTestId("team-token").locator("code");
    await expect(tokenBox).toBeVisible({ timeout: 30_000 });
    const token = (await tokenBox.innerText()).trim();

    await mate.goto(`/${AR}/team`);
    await mate.getByTestId("invitation-token-input").fill(token);
    await mate.getByTestId("invitation-accept-submit").click();
    await expect(mate.getByTestId("invitation-accept").locator(".badge-ok"))
      .toBeVisible({ timeout: 30_000 });

    // ── لقطةُ الأعضاء كما يراها الخادم الآن ──
    await owner.goto(`${projectUrl}?section=team`);
    const card = owner.locator('[data-testid^="team-member-"]')
      .filter({ hasText: "زميلٌ يُوقَف" }).first();
    await expect(card).toBeVisible({ timeout: 30_000 });
    const memberId = (await card.getAttribute("data-testid"))!
      .replace("team-member-", "");
    await expect(owner.getByTestId(`team-suspend-${memberId}`)).toBeVisible();

    const token2 = await owner.evaluate(() =>
      localStorage.getItem("athera_access_token"));
    const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
    const projectId = projectUrl.split("/").pop()!;
    const snapshot: Member[] = await (await owner.request.get(
      `${api}/api/v1/projects/${projectId}/members`,
      { headers: { Authorization: `Bearer ${token2}` } })).json();
    expect(snapshot.some((m) => m.id === memberId)).toBe(true);

    // ══ ١ · الإيقاف: القارئُ مُثبَّتٌ على «نشِط» ══
    //
    // فلو رُسم الزرّان من القراءة لَبقي «أوقِف» إلى الأبد.
    await pinMembersRead(owner, snapshot, memberId, "active");
    await owner.getByTestId(`team-suspend-${memberId}`).click();
    await expect(
      owner.getByTestId(`team-restore-${memberId}`),
      "الشاشةُ لم تعرض «أعِد» بعد إيقافٍ ردّه الخادمُ ناجحًا — "
      + "فهي ما زالت تبني حالَها من قراءةٍ تتبع الكتابة",
    ).toBeVisible({ timeout: 15_000 });
    await expect(owner.getByTestId(`team-suspend-${memberId}`)).toHaveCount(0);

    // ══ ٢ · والإعادة: القارئُ مُثبَّتٌ على «موقوف» ══
    await owner.unroute((url) => url.pathname.endsWith("/members"));
    await pinMembersRead(owner, snapshot, memberId, "suspended");
    await owner.getByTestId(`team-restore-${memberId}`).click();
    await expect(
      owner.getByTestId(`team-suspend-${memberId}`),
      "الشاشةُ لم تعرض «أوقِف» بعد إعادةٍ ردّها الخادمُ ناجحة",
    ).toBeVisible({ timeout: 15_000 });
    await expect(owner.getByTestId(`team-restore-${memberId}`)).toHaveCount(0);

    // ══ ٣ · والحقيقةُ في الخادم تطابق ما عُرض ══
    //
    // فالاعتراضُ كان على القارئ وحده: الكتابةُ وقعت فعلًا.
    await owner.unroute((url) => url.pathname.endsWith("/members"));
    const after: Member[] = await (await owner.request.get(
      `${api}/api/v1/projects/${projectId}/members`,
      { headers: { Authorization: `Bearer ${token2}` } })).json();
    expect(after.find((m) => m.id === memberId)?.access_state).toBe("active");

    expect(serverErrors, "a 5xx answered during the race check").toEqual([]);
    await ownerCtx.close();
    await mateCtx.close();
  });
