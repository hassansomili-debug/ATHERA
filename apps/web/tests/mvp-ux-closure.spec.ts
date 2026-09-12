import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * إغلاقُ الرحلة | Three dead ends on the researcher's path.
 *
 * **١ · مخطوطةٌ بُنيت ولا بابَ إلى استوديوها.** شاشةُ المخطوطات كانت
 * تعرض بوّابةَ G9 وحدها: «افحص الجاهزية» و«اعتمد G9». فمن بنى ورقته
 * يقف أمام فحصِ جاهزيةٍ لا أمام ورقته — والاستوديو قائمٌ في
 * `/{id}/studio` منذ حين، ولا رابطَ إليه.
 *
 * **٢ · ومراجعةُ الأدلّة تبدو بوّابة.** «٣٤ بانتظارك» و«راجِعْ التالي»
 * يقرؤها من رفع رسالته شرطًا يجب أن يعبُره قبل أن تتكوّن فكرةُ ورقة.
 * وليست كذلك: التنقيبُ يعمل على الاستخراج المؤهَّل بلا قرارٍ لكلّ حقل.
 *
 * **٣ · وبطاقتان تعملان معًا.** التعطيلُ كان مقصورًا على البطاقة العاملة،
 * فتُعرض واحدةٌ تقول «نبني الخيط الذهبيّ…» وأخرى زرُّها مضيءٌ يُنقر.
 */

const AR = "ar";
const EN = "en";
const MANUSCRIPT = "ms-7";
const THESIS = "th-7";

async function seedSession(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem("athera_access_token", "ux-closure");
    localStorage.setItem("athera_refresh_token", "ux-closure");
  });
}

function json(route: Route, payload: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json",
                         body: JSON.stringify(payload) });
}

/**
 * قشرةُ التطبيق: الوضعُ والوارد — **وليسا تفصيلًا**.
 *
 * ردُّ `{}` عليهما يُسقط الشريطَ والقائمة، فتنهار الشجرةُ ويقرأ الباحثُ
 * «This page couldn't load» — وهو عطبُ التجهيزة لا عطبُ الشاشة.
 */
function shell(route: Route, path: string): boolean {
  if (path === "/api/v1/settings/posture") {
    json(route, { tenant_name: "مركز", locale: "ar",
                  supported_locales: ["ar", "en"], roles: [], items: [] });
    return true;
  }
  if (path === "/api/v1/inbox/summary") {
    json(route, { pending_approvals: 0, open_alerts: 0, blocking_alerts: 0,
                  unread_notifications: 0 });
    return true;
  }
  return false;
}

// ═══════════ أ + ب · المخطوطة: بابٌ إلى الاستوديو، وG9 مطويّة ═══════════

async function serveManuscripts(page: Page) {
  await page.route("**/api/v1/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (shell(route, path)) return;
    if (path.endsWith("/manuscripts")) {
      return json(route, [{
        id: MANUSCRIPT, title: "ورقة من نتيجةٍ مستخرَجة", status: "drafting",
        language: "ar", current_version_label: "v1", g9_approved_at: null,
      }]);
    }
    if (path.includes("/studio") || path.endsWith(`/manuscripts/${MANUSCRIPT}`)) {
      return json(route, {
        manuscript_id: MANUSCRIPT, title: "ورقة من نتيجةٍ مستخرَجة",
        approved_sections: 0, enabled_sections: 2,
        sections: [
          { section_key: "introduction", label: "المقدّمة", enabled: true,
            status: "draft", approved: false },
          { section_key: "methods", label: "المنهج", enabled: true,
            status: "draft", approved: false },
        ],
      });
    }
    return json(route, {});
  });
}

test("أ · من قائمة المخطوطات إلى الاستوديو | the list opens the Paper Studio",
  async ({ page }) => {
    await seedSession(page);
    await serveManuscripts(page);
    await page.goto(`/${EN}/manuscripts`);

    const open = page.getByTestId(`manuscript-open-studio-${MANUSCRIPT}`);
    await expect(open).toBeVisible();
    await expect(open).toHaveText("Open Paper Studio");
    // **والرابطُ يقصد الاستوديو بعينه** — لا شاشةَ جاهزيةٍ ولا قائمةً أخرى.
    await expect(open).toHaveAttribute(
      "href", `/${EN}/manuscripts/${MANUSCRIPT}/studio`);

    await open.click();
    await expect(page).toHaveURL(
      new RegExp(`/${EN}/manuscripts/${MANUSCRIPT}/studio$`));
    // ومُصفِّحُ الأقسام حاضر — أي أنّ الوجهة هي الاستوديو فعلًا.
    // **ويُطلب باسمه**: الصفحةُ فيها ملاحةُ التطبيق أيضًا، فـ`navigation`
    // وحدها تُطابق اثنتين.
    await expect(page.getByRole("navigation", { name: "الأقسام" })
      .or(page.getByRole("navigation", { name: "Sections" }))).toBeVisible();
  });

test("أ′ · وبالعربية أيضًا | and in Arabic", async ({ page }) => {
  await seedSession(page);
  await serveManuscripts(page);
  await page.goto(`/${AR}/manuscripts`);

  const open = page.getByTestId(`manuscript-open-studio-${MANUSCRIPT}`);
  await expect(open).toHaveText("افتح استوديو الورقة");
  await expect(open).toHaveAttribute(
    "href", `/${AR}/manuscripts/${MANUSCRIPT}/studio`);
});

test("ب · وG9 ليست الفعلَ الرئيس | G9 is not the primary action",
  async ({ page }) => {
    await seedSession(page);
    await serveManuscripts(page);
    await page.goto(`/${EN}/manuscripts`);

    // **مطويّةٌ لا محذوفة**: أزرارُها موجودةٌ وغيرُ ظاهرةٍ حتى تُفتح.
    await expect(page.getByTestId(`manuscript-check-${MANUSCRIPT}`))
      .not.toBeVisible();
    await expect(page.getByTestId(`manuscript-approve-g9-${MANUSCRIPT}`))
      .not.toBeVisible();

    const advanced = page.getByTestId(`manuscript-advanced-${MANUSCRIPT}`);
    await expect(advanced).toBeVisible();
    await expect(advanced).toContainText("Advanced / Publication readiness");

    // **ولا تُحذف البوّابة**: تُفتح فتظهر كاملةً — منطقُها لم يُمسّ.
    await advanced.locator("summary").click();
    await expect(page.getByTestId(`manuscript-check-${MANUSCRIPT}`)).toBeVisible();
    await expect(page.getByTestId(`manuscript-approve-g9-${MANUSCRIPT}`)).toBeVisible();
  });

// ═══════════ ج · المراجعةُ تقول إنّها اختيارية ═══════════

async function serveReview(page: Page) {
  await page.route("**/api/v1/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (shell(route, path)) return;
    if (path.endsWith("/consent")) {
      return json(route, {
        file_id: "f-1", state: "granted",
        capability: "thesis_extraction_external_c2", max_classification: "C2",
        provider: "null", model: null, title: "إذن", body: "نصّ الإذن",
      });
    }
    if (path.includes("/review")) {
      return json(route, {
        thesis_id: THESIS, thesis_title: "رسالة", source_filename: "t.pdf",
        sections: [{
          key: "metadata", label: "بيانات الرسالة",
          fields: [{
            id: "cand-title", field_key: "title_ar", label: "العنوان",
            value: "عنوانٌ مستخرَج", status: "unverified",
            extraction_status: "found", extraction_confidence: 0.94,
            quote: "عنوانٌ مستخرَج", locator: "p.1", decided_at: null,
            edited_by_human: false, conflict_with: null, decidable: true,
          }],
        }],
        total: 34, reviewable_total: 34,
        approved: 0, rejected: 0, unknown: 0, pending: 34, note: "",
      });
    }
    return json(route, {});
  });
}

for (const [locale, needle] of [
  [EN, "not required to generate paper ideas"],
  [AR, "ليست مطلوبة لتوليد أفكار الأوراق"],
] as const) {
  test(`ج · المراجعةُ اختيارية ويُقال ذلك (${locale}) | review says it is optional`,
    async ({ page }) => {
      await seedSession(page);
      await serveReview(page);
      await page.goto(`/${locale}/theses/${THESIS}/review`);

      const banner = page.getByTestId("review-optional-banner");
      await expect(banner).toBeVisible();
      await expect(banner).toContainText(needle);
      // **وتُقال في الصدر** — قبل أيّ عدٍّ ينتظر الباحث.
      await expect(banner).toContainText(
        locale === EN ? "Optional evidence review" : "مراجعة اختيارية للأدلة");
    });
}

// ═══════════ د + هـ · لا فعلان متوازيان ═══════════

/** خادمٌ متخيَّل يُبطئ فعلًا واحدًا، فيُقاس ما يقع أثناءه. */
async function serveJourney(page: Page, opts: { hold: (release: () => void) => void }) {
  let released = false;
  const wait = new Promise<void>((resolve) => opts.hold(() => { released = true; resolve(); }));
  let built = false;

  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();

    if (path.endsWith("/select") && method === "POST") return json(route, {});
    if (path.endsWith("/build-paper") && method === "POST") {
      // **يُحبس الطلبُ عمدًا** — فتُقاس الشاشةُ أثناء عملٍ يجري.
      await wait;
      built = true;
      return json(route, { project_id: "p", outline_id: "o",
                           manuscript_id: MANUSCRIPT, created: [], reused: [] }, 201);
    }
    if (path.endsWith("/journey")) {
      return json(route, {
        thesis_id: THESIS, state: built ? "manuscript_created" : "opportunities_ready",
        opportunities: 2, blocking_reasons: [], current_blocking_reasons: [],
        can_build_paper: true, can_build_thread: false, thread_ready: false,
        project_exists: built, outline_exists: built, manuscript_exists: built,
        states: [],
      });
    }
    if (path.endsWith("/publication-map")) {
      return json(route, { opportunities: ["a", "b"].map((k) => ({
        id: `op-${k}`, working_title: `فكرة ${k}`, paper_kind_label: "امتداد",
        research_question_ar: null, readiness_outcome_label: null,
        salami_alert: false, provenance_count: 1, planning_status: "proposed",
        context_complete: false, missing_context: ["sample"],
      })) });
    }
    if (shell(route, path)) return;
    return json(route, {});
  });
  return { isReleased: () => released };
}

test("د + هـ · فعلٌ جارٍ يقفل البقيّة ثمّ يفكّها | an in-flight action locks the others",
  async ({ page }) => {
    await seedSession(page);
    let release = () => {};
    await serveJourney(page, { hold: (r) => { release = r; } });
    await page.goto(`/${AR}/theses/${THESIS}/journey`);

    const first = page.getByTestId("opportunity-card-op-a")
      .getByTestId("journey-start-paper");
    const second = page.getByTestId("opportunity-card-op-b")
      .getByTestId("journey-start-paper");

    await expect(first).toBeEnabled();
    await expect(second).toBeEnabled();

    // ── يبدأ الأوّل، ويبقى الطلبُ محبوسًا ──
    await first.click();

    // **د · والبطاقةُ الأخرى تُقفل** — لا زرٌّ مضيءٌ بجوار عملٍ يجري.
    await expect(second).toBeDisabled();
    await expect(first).toBeDisabled();

    // ── ثمّ يُفكّ الحبس ──
    release();

    // **هـ · وتعود الأفعالُ السويّة** — القفلُ لحظةٌ لا سياسة.
    await expect(second).toBeEnabled({ timeout: 15_000 });
  });
