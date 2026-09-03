"""دورة حياة الجلسة في المتصفح | Browser session lifecycle (PUBRIVA P1 recovery).

**سقط قبول P1 هنا**، لا في الخادم. والخادم كان سليمًا طوال الوقت: `/refresh`
و`/register` و`/logout` قائمة وتعمل. والواجهة لم تكن تبلغ أيًّا منها.

فهذه الاختبارات تحرس الواجهة من مصدرها، وتعمل في كل PR — والقبول بمتصفّح
حقيقي في `apps/web/tests` لا يُستبدل بها، بل تسبقه.
"""
import pathlib

import pytest

WEB = pathlib.Path(__file__).resolve().parents[3] / "apps" / "web"
API_CLIENT = (WEB / "src" / "lib" / "api.ts").read_text(encoding="utf-8")
SESSION = (WEB / "src" / "lib" / "session.ts").read_text(encoding="utf-8")


# ══════════ ١. انتهاء رمز الوصول ليس نهاية الجلسة ══════════

def test_a_401_attempts_refresh_before_destroying_the_session():
    """**العيب الجذري**: كل 401 كان يمحو الجلسة ويقذف الباحث إلى الدخول.

    ورمز الوصول يعيش تسعمئة ثانية، ورمز التحديث في المخزن لم يُستعمل قط —
    فباحثٌ يكتب ورقته يُطرد كل ربع ساعة بلا سبب يفهمه.
    """
    assert "refreshOnce" in API_CLIENT, "لا محاولة تجديد إطلاقًا"
    # الترتيب هو الحكم لا الصياغة: التجديد يُحاوَل، ثم المحو إن فشل.
    handler = API_CLIENT[API_CLIENT.index("response.status === 401"):]
    refresh_at = handler.index("await refreshOnce()")
    clear_at = handler.index("clearSession();")
    assert refresh_at < clear_at, (
        "المحو يقع قبل محاولة التجديد — وهو العيب نفسه بترتيبٍ مقلوب")


def test_the_refresh_saves_both_rotated_tokens():
    """رمز التحديث يدور: حفظ الوصول وحده يترك تحديثًا مُبطَلًا في المخزن."""
    assert "saveSession(pair)" in API_CLIENT
    # الرمزان يُفحصان كلاهما قبل الحفظ — وحفظُ نصف الزوج يُبطل التجديد التالي.
    assert "pair?.access_token" in API_CLIENT
    assert "pair?.refresh_token" in API_CLIENT
    # و`saveSession` هي التي تكتب الاثنين معًا.
    assert "safeSet(REFRESH_KEY, tokens.refresh_token)" in SESSION


def test_the_original_request_is_replayed_exactly_once():
    """إعادةٌ واحدة — وإعادةٌ بلا حدّ حلقةٌ تقصف الخادم."""
    assert "alreadyRetried" in API_CLIENT
    assert "requestWithRefresh<T>(path, options, true)" in API_CLIENT


def test_token_issuing_paths_are_never_refreshed():
    """الدخول والتسجيل والتجديد والخروج لا تُجدَّد — هي مصدر الرموز."""
    for path in ("/api/v1/auth/login", "/api/v1/auth/register",
                 "/api/v1/auth/refresh", "/api/v1/auth/logout"):
        assert path in API_CLIENT, path
    assert "isAuthPath(path)" in API_CLIENT


def test_the_refresh_is_single_flight():
    """**رمزٌ يدور وطلباتٌ متوازية**: خمسة تجديدات بالرمز نفسه تُبطله أربع مرّات.

    فيفوز الأول ويفشل الباقون برمزٍ مُبطَل، فتُمحى الجلسة والباحث يعمل.
    """
    assert "let refreshInFlight" in API_CLIENT
    assert "if (!refreshInFlight)" in API_CLIENT
    assert "refreshInFlight = null" in API_CLIENT


def test_the_login_page_never_redirects_to_itself():
    """حلقةُ إعادةِ توجيهٍ لا نهاية لها أسوأ من خطأٍ صريح."""
    assert 'window.location.pathname.endsWith("/login")' in API_CLIENT


def test_a_caller_supplied_token_is_not_refreshed_on_its_owner_behalf():
    assert "const ownsSession = token === undefined;" in API_CLIENT


def test_a_204_is_not_parsed_as_json():
    """الخروج يردّ ٢٠٤، و`response.json()` يرمي عليها فيبدو النجاح عطبًا."""
    assert "response.status === 204" in API_CLIENT


# ══════════ ٢. الحدّ: لا تُصيَّر مساحة عملٍ ثم تُسحب ══════════

def test_the_application_is_protected_at_the_route_boundary():
    """**الحال المختلطة ممنوعة.** الرئيسية كانت تُصيَّر كاملةً ثم يفشل
    `usePosture` بـ401 فتختفي تحت الزائر."""
    gate = (WEB / "src" / "components" / "AuthGate.tsx").read_text(encoding="utf-8")
    layout = (WEB / "src" / "app" / "[locale]" / "layout.tsx").read_text(encoding="utf-8")
    assert "AuthGate" in layout, "الحدّ غير مركَّب في التخطيط"
    assert '"/login"' in gate and '"/register"' in gate, "الصفحتان العامتان غير مستثنيتين"
    # الحدّ يستشير الجلسة — سواء استدعاها أو مرّرها لقطةً خارجية.
    assert "isSignedIn" in gate
    # والوجهة تُحفظ: الباحث يعود إلى ما قصده لا إلى الرئيسية.
    assert "next=" in gate


def test_login_returns_the_researcher_to_the_page_they_wanted():
    login = (WEB / "src" / "app" / "[locale]" / "login" / "page.tsx").read_text(encoding="utf-8")
    assert 'get("next")' in login
    # ولا يُقبل إلا مسارٌ داخلي — وجهةٌ خارجية تفتح تحويلًا مفتوحًا.
    assert 'startsWith("/")' in login and 'startsWith("//")' in login


# ══════════ ٣. الحساب ليس طريقًا مسدودًا ══════════

def test_the_browser_has_a_working_account_creation_path():
    """`POST /auth/register` عامل في الخادم بلا بابٍ في المتصفح ليس مسارًا."""
    page = WEB / "src" / "app" / "[locale]" / "register" / "page.tsx"
    assert page.exists(), "لا صفحة إنشاء حساب"
    source = page.read_text(encoding="utf-8")
    assert "/api/v1/auth/register" in source
    assert "saveSession(tokens)" in source
    # **ولا يُعرض حقل انضمامٍ إلى مساحة قائمة**: الخادم يرفض اسمًا مأخوذًا،
    # وعرضُ الحقل يدعو إلى تخمين الأسماء — وتلك ثغرة التفويض التي أُغلقت.
    assert "tenant_slug" not in source

    login = (WEB / "src" / "app" / "[locale]" / "login" / "page.tsx").read_text(encoding="utf-8")
    assert "/register" in login, "صفحة الدخول لا تدلّ على إنشاء حساب"


def test_signing_out_revokes_the_refresh_token_at_its_source():
    """**المحو المحلي وحده ليس إبطالًا**: الرمز يبقى صالحًا عند الخادم."""
    control = (WEB / "src" / "components" / "SessionControl.tsx").read_text(encoding="utf-8")
    assert "/api/v1/auth/logout" in control
    revoke = control.index("/api/v1/auth/logout")
    clear = control.index("clearSession();")
    assert revoke < clear, "المحو يسبق الإبطال، فالرمز يبقى حيًّا"


# ══════════ ٤. لا «لم يحدث شيء» ══════════

def test_no_screen_fakes_emptiness_when_a_request_failed():
    """مكتبةٌ تقول «لا ملفات» بعد طلبٍ فاشل تكذب على صاحبها."""
    offenders = []
    for path in (WEB / "src").rglob("*.tsx"):
        text = path.read_text(encoding="utf-8")
        for marker in ("catch(() => setFiles([]))", "catch(() => setSources([]))",
                       "catch(() => setProjects([]))", "catch(() => setTheses([]))",
                       "catch(() => setTrashed([]))", "catch(() => setLibrary([]))"):
            if marker in text:
                offenders.append(f"{path.name}: {marker}")
    assert not offenders, "فشلٌ يُعرض فراغًا: " + "; ".join(offenders)


@pytest.mark.parametrize("testid", ["login-error", "register-error", "ai-error", "ai-answer"])
def test_every_critical_surface_is_addressable_and_announced(testid):
    """الخطأ يُعلَن `role="alert"` فيقرؤه قارئ الشاشة، ويُمسك في المتصفح."""
    found = any(f'data-testid="{testid}"' in p.read_text(encoding="utf-8")
                for p in (WEB / "src").rglob("*.tsx"))
    assert found, f"لا مِقبض ثابت لـ{testid}"


# ══════════ ٥. حزمة القبول موجودة ولا تُستبدل ══════════

def test_the_browser_acceptance_harness_exists():
    assert (WEB / "playwright.config.ts").exists()
    assert (WEB / "tests" / "auth-refresh.spec.ts").exists()
    assert (WEB / "tests" / "acceptance.spec.ts").exists()
    workflow = (WEB.parents[1] / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "playwright install" in workflow, "لا متصفّح في CI"


def test_no_credential_is_committed_in_the_acceptance_suite():
    """الاعتماد يأتي من البيئة — ولا يسكن المستودع."""
    source = (WEB / "tests" / "acceptance.spec.ts").read_text(encoding="utf-8")
    assert "process.env.PUBRIVA_ACCEPT_PASSWORD" in source
    for leak in ("password:", "Passw0rd", "hunter2"):
        assert leak not in source, leak


# ══════════ ٦. حزمة القبول تُثبت الدخول، ولا تكتفي بشكل الرابط ══════════

def test_the_acceptance_suite_proves_login_by_the_server_response():
    """**عيبٌ كشفه أول تشغيلٍ على الإنتاج.**

    كان الفحص ينتظر `new RegExp("/ar(\\?|$|/)")` على الرابط كاملًا،
    و`/ar/login?next=%2Far` يطابقها — بل و`/ar/portfolio`. فيمرّ الشرط
    والصفحة ما زالت على الدخول، ويُعلَن نجاح خطوةٍ لم تقع.

    وأسوأ من ذلك: الفحص كان يبدأ التنقّل قبل أن يردّ الدخول، فيُجهض الطلب
    ويُعيد `AuthGate` التوجيه — **فيُتّهم المنتج بعيبٍ صنعه الفحص**.
    """
    journey = (WEB / "tests" / "journey.ts").read_text(encoding="utf-8")
    acceptance = (WEB / "tests" / "acceptance.spec.ts").read_text(encoding="utf-8")

    # ١ — يُنتظر ردّ الخادم، وتُفحص حالته.
    assert "waitForResponse" in journey
    assert '"/api/v1/auth/login"' in journey
    assert "response.status()" in journey

    # ٢ — المسار يُطابَق بالضبط، لا بنمطٍ فضفاض.
    assert "url.pathname === `/${LOCALE}`" in journey

    # ٣ — والرمز محفوظ فعلًا.
    assert "athera_access_token" in journey

    # ٤ — ولا يعود النمط الفضفاض إلى حزمة القبول.
    assert "(\\?|$|/)" not in acceptance, (
        "النمط الفضفاض عاد إلى acceptance.spec.ts — وهو يقبل صفحة الدخول")
    # وكلا الدخولين يمرّان بالمُثبِت نفسه.
    assert acceptance.count("signIn(page") == 2, (
        "أحد الدخولين لا يمرّ بالمُثبِت المشترك")


def test_the_post_login_predicate_is_guarded_where_it_always_runs():
    """الحارس في الحزمة التي تعمل بلا حساب — لا في التي تُتخطّى بدونه."""
    lifecycle = (WEB / "tests" / "auth-refresh.spec.ts").read_text(encoding="utf-8")
    assert "isSignedInDestination" in lifecycle
    assert "never accepts the login page" in lifecycle


# ══════════ ٧. خطوات ٨–١٠: تصنع حالها، ولا تُتخطّى بصمت ══════════

def test_the_file_journey_creates_its_own_fixture_through_the_ui():
    """**فحصٌ يتّكئ على بياناتٍ سابقة يمرّ اليوم ويسقط غدًا بلا سبب.**

    ونجاحُه لا يقول شيئًا: قد يكون مرّ لأن الحساب صادف أن فيه ملفًا.
    فالرحلة ترفع ملفها بنفسها من الواجهة، باسمٍ فريد لكل تشغيلة.
    """
    spec = (WEB / "tests" / "acceptance.spec.ts").read_text(encoding="utf-8")
    assert "setInputFiles" in spec, "الرفع لا يمرّ بواجهة اختيار الملف"
    assert "FILENAME" in spec and "Date.now()" in spec, "لا اسم فريد لكل تشغيلة"
    # ولا يُصنع الحال باستدعاء الـAPI من الفحص.
    assert "/api/v1/files/upload" not in spec, "الفحص يصنع الحال بالـAPI لا بالمتصفح"


def test_no_acceptance_step_can_be_silently_skipped():
    """خطوةٌ إلزامية إمّا تنجح وإمّا تسقط — و«لم يوجد الزرّ فمرّ» ليست نتيجة."""
    spec = (WEB / "tests" / "acceptance.spec.ts").read_text(encoding="utf-8")
    assert "if (await add.count())" not in spec, "تخطٍّ صامت لخطوة الربط"
    # الربط وفكّه يستهدفان الملف بعينه لا أوّل بطاقة في الصفحة.
    assert ".first()).click()" not in spec
    assert 'hasText: FILENAME' in spec, "الاستهداف ليس بالملف بعينه"


def test_navigation_links_are_scoped_to_their_landmark():
    """«اضغط الرابط» ليست تعليمة كافية حين يوجد رابطان بالاسم نفسه."""
    spec = (WEB / "tests" / "acceptance.spec.ts").read_text(encoding="utf-8")
    for ambiguous in ('page.getByRole("link", { name: "مكتبتي" })',
                      'page.getByRole("link", { name: "أبحاثي" })'):
        assert ambiguous not in spec, f"رابط تنقّل بلا موضع: {ambiguous}"
    assert 'getByRole("navigation", { name: "الرئيسية" })' in spec


# ══════════ ٨. التحميل ليس فراغًا ولا عطبًا ══════════

def test_the_project_files_pane_tells_loading_from_empty():
    """**عيبٌ يراه الباحث**: القائمتان تبدآن `[]` وتُملآن بعد رحلةٍ إلى
    الخادم، فتقول الشاشة «لا ملف مرتبط» و«لا ملفات لإضافتها» قبل أن يصل
    الجواب — وهي دعوى عن حال البحث لم تُفحص بعد.
    """
    page = (WEB / "src" / "app" / "[locale]" / "portfolio" / "[projectId]"
            / "page.tsx").read_text(encoding="utf-8")
    for state, setter in (("filesLoad", "setFilesLoad"), ("libraryLoad", "setLibraryLoad")):
        assert f'{state} === "loading"' in page, f"{state}: لا فرق بين التحميل والفراغ"
        assert f'{setter}("failed")' in page, f"{state}: لا يميّز العطب"
        assert f'{setter}("ready")' in page, f"{state}: لا حال استقرار"
    for testid in ("files-loading", "library-loading", "files-empty", "library-empty"):
        assert f'data-testid="{testid}"' in page, testid


def test_the_two_navigation_landmarks_have_distinct_names():
    """معلمان بالاسم نفسه يربكان قارئ الشاشة كما يربكان الفحص."""
    page = (WEB / "src" / "app" / "[locale]" / "portfolio" / "[projectId]"
            / "page.tsx").read_text(encoding="utf-8")
    nav = (WEB / "src" / "components" / "SideNav.tsx").read_text(encoding="utf-8")
    assert 'aria-label={t("nav.dashboard")}' in nav
    assert 'aria-label={t("project.sectionsLabel")}' in page
    # ولا يُسمّى معلَمٌ باسم عنصرٍ بداخله.
    assert 'aria-label={t("project.overview")}' not in page


def test_the_acceptance_suite_records_no_artifact_that_could_hold_a_secret():
    """**سرٌّ ظهر في أثر تشغيلة إنتاجية.**

    أثرُ Playwright يسجّل وسائط كل فعل — ومنها ما يُملأ في حقل كلمة المرور
    نصًّا صريحًا؛ ولقطتا الشاشة وDOM تحملان قيمة الحقل. وتُرفع هذه أثرًا في
    CI يقرؤه كل ذي وصول. **وقابليةُ التشخيص لا تُشترى بتسريب كلمة مرور.**
    """
    spec = (WEB / "tests" / "acceptance.spec.ts").read_text(encoding="utf-8")
    assert 'test.use({ trace: "off", video: "off", screenshot: "off" });' in spec, (
        "حزمة القبول تسجّل آثارًا قد تحمل الاعتماد")


def test_credentialed_acceptance_is_gated_behind_an_explicit_opt_in():
    """**الدمج ليس إذنًا.** بعد تسرّب الاعتماد في أثر تشغيلة، لا يعمل شيء
    باعتمادٍ حتى يُضبط متغيّرٌ قصدًا — بعد التدوير وبعد حسابٍ مخصَّص."""
    workflow = (WEB.parents[1] / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "vars.PUBRIVA_ACCEPT_READY == 'true'" in workflow, "لا بوّابة قبل التشغيل باعتماد"
    # وسببُ عدم التشغيل يُقال، ولا يُقرأ الصمت نجاحًا.
    assert "browser acceptance is NOT verified while this gate is closed" in workflow


# ══════════ ٩. ربطُ مرجعٍ بالبحث: مسارٌ في الخادم بلا بابٍ في المتصفح ══════════

WORKSPACE_PAGE = (WEB / "src" / "app" / "[locale]" / "portfolio" / "[projectId]"
                  / "page.tsx").read_text(encoding="utf-8")


def test_the_researcher_can_link_a_library_source_from_the_browser():
    """**`POST …/sources` كان عاملًا بلا نافذةٍ تبلغه.**

    فالباحث يرى مراجعه في مكتبته ولا يستطيع أن ينسبها إلى بحثه — والمسار
    الوحيد إليها كان استدعاءً مباشرًا للـAPI. وذلك ليس منتجًا.
    """
    client = (WEB / "src" / "lib" / "workspace.ts").read_text(encoding="utf-8")
    assert "export const linkSource" in client
    assert "export const listLibrarySources" in client

    assert "addSource" in WORKSPACE_PAGE, "لا فعل ربطٍ في الشاشة"
    assert "availableSources" in WORKSPACE_PAGE, "لا قائمة مرشّحين"
    assert 't("project.addSource")' in WORKSPACE_PAGE


def test_the_source_picker_never_asks_for_an_identifier():
    """يُختار المرجع بعنوانه وبياناته — **والباحث لا ينسخ UUID أبدًا**."""
    assert "source.title" in WORKSPACE_PAGE
    assert "source.publication_year" in WORKSPACE_PAGE
    # ولا حقل إدخالٍ لمعرّف مصدر.
    assert "asset_id" not in WORKSPACE_PAGE, "الشاشة تطلب معرّفًا بيد الباحث"


def test_an_empty_library_is_never_a_silent_pass():
    """فراغُ المكتبة حالٌ تُقال ومعها طريق — لا شاشةٌ صامتة."""
    assert 'data-testid="no-candidate-sources"' in WORKSPACE_PAGE
    assert 't("project.importSourceCta")' in WORKSPACE_PAGE
    assert 'sourcesLoad === "loading"' in WORKSPACE_PAGE, "التحميل يُعرض فراغًا"


def test_the_default_use_state_comes_from_the_server_not_the_screen():
    """**الاستيراد ليس حكمًا بالصلاحية دليلًا**، والحال يقرّرها الخادم.

    فلو كتبتها الواجهة من عندها لأخفت تغيّرها يومًا، ولقال الفحص «محفوظ
    فقط» عن علاقةٍ ليست كذلك.
    """
    client = (WEB / "src" / "lib" / "workspace.ts").read_text(encoding="utf-8")
    link = client[client.index("export const linkSource"):]
    assert '"saved_only"' not in link.split("apiFetch")[0], "الواجهة تفترض الحال الابتدائية"


# ══════════ ١٠. رحلة القبول تفحص فعلًا لا نصًّا ══════════

ACCEPTANCE = (WEB / "tests" / "acceptance.spec.ts").read_text(encoding="utf-8")


def test_the_literature_step_performs_the_workflow_not_the_rule_text():
    """**«النصّ ظاهر» ليست «الفعل وقع».** الصياغة السابقة كانت تثبت أن
    القسم يقول قاعدته — وتلك جملةٌ في الشاشة لا رحلةُ باحث."""
    assert "import a reference into My Library through the UI" in ACCEPTANCE
    assert "link that reference to the project, defaulting to saved_only" in ACCEPTANCE
    # الاستيراد من الشاشة لا من الـAPI.
    assert "/api/v1/sources/import" not in ACCEPTANCE
    # والحال الافتراضية تُفحص على العنصر بعينه.
    assert 'toHaveAttribute("aria-pressed", "true")' in ACCEPTANCE
    assert "sourceTitle" in ACCEPTANCE, "المطابقة ليست بالعنوان المقروء من الشاشة"


def test_the_ai_step_submits_through_the_button_the_product_provides():
    """الحقل `textarea` بلا نموذج ولا معالج مفاتيح — فالضغط على Enter
    يُدخل سطرًا ولا يرسل شيئًا، وكان الفحص ينتظر جوابًا لسؤالٍ لم يُرسَل."""
    ai = ACCEPTANCE[ACCEPTANCE.index("PUBRIVA AI answers"):]
    assert 'getByRole("button", { name: "ابدأ" })' in ai
    assert "toBeEnabled" in ai, "لا إثبات أن الزرّ صالح للضغط"
    assert 'press("Enter")' not in ai, "الإرسال ما زال بمفتاح الإدخال"
    for markup in ("</answer_ar>", "<citations>", "</invoke>"):
        assert markup in ai, markup


# ══════════ ١١. الرحلة تغطّي ما نقص: معالجةٌ ومراجعةٌ وإذنان وخروج ══════════

def test_the_journey_covers_document_processing_and_review():
    """١٤–١٦ كانت غائبة عن الرحلة كلها — فما لم يُفحص لا يُقال إنه يعمل."""
    assert "upload a parseable synthetic document" in ACCEPTANCE
    assert "start document processing from the browser" in ACCEPTANCE
    assert "review the extracted knowledge and approve one fact" in ACCEPTANCE
    # الوثيقة تركيبية بالكامل، تُصنع في الذاكرة.
    assert "DOC_TEXT" in ACCEPTANCE and "Buffer.from(DOC_TEXT" in ACCEPTANCE


def test_processing_states_are_asserted_truthfully_and_never_by_sleeping():
    """`stored` و`processing` و`awaiting consent` و`awaiting review` و
    `completed` و`failed` ستُّ حالات — ولا تُجمع في واحدة."""
    assert "لم تُعالَج بعد" in ACCEPTANCE
    assert "ينتظر إذن القراءة" in ACCEPTANCE
    assert "بانتظار مراجعتك" in ACCEPTANCE
    assert "تعذّرت المعالجة" in ACCEPTANCE, "الفشل غير مُختبَر"
    # ولا انتظارٌ بزمنٍ ثابت حيث توجد حالٌ تُنتظر.
    assert "waitForTimeout" not in ACCEPTANCE


def test_dic2_and_dcc2_are_separate_boundaries_in_the_journey():
    """**إذنان لا يُدمجان**: اعتمادُ معرفةٍ من مستند لا يأذن بإرسالها إلى
    مزوّد لأجل سؤال."""
    assert 'getByTestId("dic2-grant")' in ACCEPTANCE, "DIC2 غير مُغطّى"
    assert "السماح والإجابة" in ACCEPTANCE, "DCC2 غير مُغطّى"
    # ولا يُمنح أحدهما سلفًا في الشيفرة.
    web_src = "\n".join(p.read_text(encoding="utf-8") for p in (WEB / "src").rglob("*.tsx"))
    assert "decision=grant" not in web_src.replace(
        'chat-consent?decision=grant', ''), "إذنٌ يُمنح سلفًا"


def test_the_journey_proves_server_side_logout_not_only_a_local_clear():
    """**المحو المحلي ليس إبطالًا**: من نسخ الرمز يظل قادرًا بدونه."""
    out = ACCEPTANCE[ACCEPTANCE.index("sign out, prove server-side revocation"):]
    assert "athera_refresh_token" in out
    assert "/api/v1/auth/refresh" in out
    assert "toBe(401)" in out, "لا إثبات أن الرمز مُبطَل عند الخادم"
    assert "signIn(page" in out, "لا دخول ثانٍ بعد الخروج"


def test_the_password_change_ui_exists_for_the_researcher():
    """كلمةٌ انكشفت بلا بابٍ لتغييرها ليست مشكلةً أمنية وحدها — بل نقصُ منتج."""
    page = (WEB / "src" / "components" / "ChangePassword.tsx").read_text(encoding="utf-8")
    assert "/api/v1/auth/change-password" in page
    assert "clearSession()" in page, "الجلسة لا تُمحى بعد التغيير"
    settings = (WEB / "src" / "app" / "[locale]" / "settings"
                / "page.tsx").read_text(encoding="utf-8")
    assert "ChangePassword" in settings, "الشاشة غير مركَّبة في الإعدادات"


# ══════════ ١٢. الاستعادة: واجهةٌ وآليّاتٌ بلا سرٍّ في أثر ══════════

def test_the_recovery_routes_exist_and_are_public():
    web = WEB / "src" / "app" / "[locale]"
    assert (web / "forgot-password" / "page.tsx").exists()
    assert (web / "reset-password" / "page.tsx").exists()
    gate = (WEB / "src" / "components" / "AuthGate.tsx").read_text(encoding="utf-8")
    for route in ("/forgot-password", "/reset-password"):
        assert route in gate, f"{route} محجوب خلف المصادقة — ومن نسي كلمته لا يدخل"
    login = (web / "login" / "page.tsx").read_text(encoding="utf-8")
    assert "/forgot-password" in login, "لا باب إلى الاستعادة من صفحة الدخول"


def test_the_reset_page_never_shows_or_keeps_the_token():
    """**ما بعد `#` لا يُرسَل في طلب HTTP** — ويُنزع بعد قراءته."""
    page = (WEB / "src" / "app" / "[locale]" / "reset-password"
            / "page.tsx").read_text(encoding="utf-8")
    assert "window.location.hash" in page, "الرمز لا يُقرأ من الجزء"
    assert "history.replaceState" in page, "الرمز يبقى في شريط العنوان والتاريخ"
    # **والالتقاط يسبق النزع.** واشتقاقُه من الرابط عند كل تصيير يجعله
    # يختفي بعد النزع، فيُقال للباحث «لا رمز» وهو يحمله.
    assert "let captured" in page, "الرمز يُشتقّ من الرابط لا يُلتقط مرّة"
    # ولا يُعرض في أي حقلٍ أو نصّ.
    assert "value={token}" not in page
    # ولا دخول تلقائيّ بعد النجاح.
    assert "saveSession" not in page, "دخولٌ تلقائيّ يجعل سرقة الرابط سرقة جلسة"
    assert "clearSession()" in page


def test_recovery_browser_tests_upload_no_credential_bearing_artifact():
    spec = (WEB / "tests" / "recovery.spec.ts").read_text(encoding="utf-8")
    assert 'test.use({ trace: "off", video: "off", screenshot: "off" });' in spec
    # ولا رمز استعادةٍ حقيقي في الحزمة.
    assert "PUBRIVA_ACCEPT_PASSWORD" not in spec


def test_no_acceptance_artifact_can_reach_the_upload():
    """**المسجّلات مُطفأة لا تكفي.** `error-context.md` يُكتب على أي حال
    ويحمل لقطة DOM لصفحةٍ فيها حقول اعتماد. فتُمحى مخرجات رحلة القبول قبل
    أي رفع — ويبقى سجل الطرفية، وهو يكفي لمعرفة أين سقطت."""
    workflow = (WEB.parents[1] / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    upload = workflow.index("name: playwright-report")
    acceptance = workflow.index("Acceptance journey (real browser")
    assert upload < acceptance, "الرفع يقع بعد رحلة القبول فيلتقط مخرجاتها"
    assert "Destroy acceptance artifacts before any upload" in workflow
    assert "rm -rf apps/web/playwright-report apps/web/test-results" in workflow
