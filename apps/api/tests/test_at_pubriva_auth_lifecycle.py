"""دورة حياة الجلسة في المتصفح | Browser session lifecycle (PUBRIVA P1 recovery).

**سقط قبول P1 هنا**، لا في الخادم. والخادم كان سليمًا طوال الوقت: `/refresh`
و`/register` و`/logout` قائمة وتعمل. والواجهة لم تكن تبلغ أيًّا منها.

فهذه الاختبارات تحرس الواجهة من مصدرها، وتعمل في كل PR — والقبول بمتصفّح
حقيقي في `apps/web/tests` لا يُستبدل بها، بل تسبقه.
"""
import pathlib

import pytest

from tests.tsscan import code_lines

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
    ai = ACCEPTANCE[ACCEPTANCE.index("PUBRIVA AI reaches approved knowledge"):]
    assert 'getByRole("button", { name: "ابدأ" })' in ai
    assert "toBeEnabled" in ai, "لا إثبات أن الزرّ صالح للضغط"
    assert 'press("Enter")' not in ai, "الإرسال ما زال بمفتاح الإدخال"
    for markup in ("</answer_ar>", "<citations>", "</invoke>"):
        assert markup in ai, markup


# ══════════ ١١. الرحلة تغطّي ما نقص: معالجةٌ ومراجعةٌ وإذنان وخروج ══════════

def test_the_journey_covers_document_processing_and_review():
    """١٤–١٦ كانت غائبة عن الرحلة كلها — فما لم يُفحص لا يُقال إنه يعمل."""
    assert "upload a parseable synthetic document" in ACCEPTANCE
    assert "start document processing, reaching a decision state" in ACCEPTANCE
    assert "grant DIC2 in the browser when processing waits for it" in ACCEPTANCE
    assert "review the extracted knowledge and approve one fact" in ACCEPTANCE
    # الوثيقة تركيبية بالكامل، تُصنع في الذاكرة.
    assert "DOC_TEXT" in ACCEPTANCE and "Buffer.from(DOC_TEXT" in ACCEPTANCE


def test_processing_states_are_asserted_by_contract_not_translated_prose():
    """**عيبٌ أوقف الرحلة ثلاث دقائق على حالٍ لا تُكتب في تلك الشاشة.**

    كان الفحص يطابق نصًّا مترجَمًا، فأخذ «ينتظر إذن القراءة» من شاشة
    الذكاء وانتظرها في شاشة المكتبة — وهي تكتب «بانتظار موافقتك للمتابعة».
    والمعالجة كانت قد تمّت.

    فالحال تُقرأ من عقدها: `data-processing-state` — اسمٌ قانونيّ واحد لا
    يتغيّر بتحسين صياغة ولا يختلف بين شاشتين.
    """
    assert "data-processing-state" in ACCEPTANCE, "الحال ما زالت تُقرأ من النصّ"
    # ولا قائمةُ نصوصٍ مترجَمة تُكتب باليد في الفحص.
    for prose in ("ينتظر إذن القراءة", "قيد المعالجة", "لم تُعالَج بعد",
                  "تعذّرت المعالجة"):
        assert prose not in ACCEPTANCE, f"نصٌّ مترجَم يُطابَق في الفحص: {prose}"
    # والحالات القانونية الخمس مذكورة بأسمائها.
    for canonical in ("not_processed", "parsing", "extracting", "awaiting_consent",
                      "awaiting_review", "completed", "parse_failed", "extract_failed"):
        assert canonical in ACCEPTANCE, canonical
    # **والإخفاق إخفاق**: لا يُقرأ وصولًا إلى حالٍ نهائية.
    assert "document processing failed in state" in ACCEPTANCE
    # ولا انتظارٌ بزمنٍ ثابت حيث توجد حالٌ تُنتظر.
    assert "waitForTimeout" not in ACCEPTANCE


def test_awaiting_consent_is_not_presented_as_processing():
    """**انتظارُ الباحث ليس معالجةً جارية.**

    فقولُ «قيد المعالجة» حين يكون النظام هو المنتظِر يجعل الباحث ينتظر
    النظام — والنظام ينتظره — فلا يتحرّك أحد. والحالات الخمس تُميَّز:
    معالجةٌ جارية، وانتظارُ إذن، وانتظارُ مراجعة، وتمامٌ، وإخفاق.
    """
    import json
    import re

    page = (WEB / "src" / "app" / "[locale]" / "library"
            / "page.tsx").read_text(encoding="utf-8")
    block = page[page.index("const PROCESSING_LABEL"):page.index("};", page.index("const PROCESSING_LABEL"))]
    mapping = dict(re.findall(r'(\w+):\s*"([\w.]+)"', block))

    assert mapping["awaiting_consent"] == "library.awaitingConsent", (
        "انتظارُ الإذن ما زال يُعرض «قيد المعالجة»")
    assert mapping["awaiting_review"] == "library.needsReview"
    assert mapping["completed"] == "library.processed"
    assert mapping["not_processed"] == "library.notProcessed"
    # وتشارُكُ التحليل والاستخراج لافتةَ «قيد المعالجة» مشروع: كلاهما جارٍ.
    assert mapping["parsing"] == mapping["extracting"] == "library.processing"
    # والإخفاقان يبقيان إخفاقًا.
    assert mapping["parse_failed"] == mapping["extract_failed"] == "library.failedState"

    # ولكل حالٍ نصُّها بلغتَيها.
    for locale in ("ar", "en"):
        catalog = json.loads((WEB / "messages" / f"{locale}.json").read_text(encoding="utf-8"))
        lib = catalog["library"]
        for key in ("awaitingConsent", "needsReview", "processed", "notProcessed",
                    "processing", "failedState"):
            assert lib.get(key, "").strip(), f"{locale}: library.{key} فارغ"
        assert lib["awaitingConsent"] != lib["processing"], (
            f"{locale}: انتظارُ الإذن ونصُّ المعالفة سواء")


def test_the_state_element_exposes_the_canonical_state():
    """النصّ للإنسان، والسمة للآلة — ولا معرّف يُكشف لأجل فحص."""
    page = (WEB / "src" / "app" / "[locale]" / "library"
            / "page.tsx").read_text(encoding="utf-8")
    assert 'data-processing-state={file.processing_status}' in page
    # ولا تُكشف معرّفات داخلية في سمات الفحص.
    assert "data-file-id" not in page and "data-thesis-id" not in page


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


# ══════════ ١٣. النطاق القانوني: pubriva.com وحده ══════════

CANONICAL_HOST = "https://pubriva.com"


def test_the_acceptance_journey_targets_the_researchers_domain():
    """**القبول يفحص ما يستعمله الباحث** — لا اسم استضافة يصادف أن يخدمه."""
    workflow = (WEB.parents[1] / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert f"PUBRIVA_WEB_URL: {CANONICAL_HOST}" in workflow
    assert "PUBRIVA_WEB_URL: https://athera-bay.vercel.app" not in workflow


def test_the_pages_declare_the_canonical_origin():
    """بلا `metadataBase` تشتقّ Next الروابط المطلقة من اسم الاستضافة الذي
    صادف أن خدم الطلب — فتُعلن الصفحة اسمًا ليس هو المنتج أصلًا لنفسها."""
    layout = (WEB / "src" / "app" / "[locale]" / "layout.tsx").read_text(encoding="utf-8")
    assert f'metadataBase: new URL("{CANONICAL_HOST}")' in layout
    assert "canonical: `/${active}`" in layout, "الأصل يُشتقّ من لغةٍ غير متحقَّق منها"


def test_no_user_facing_code_points_at_a_vercel_hostname():
    """**ولا يُرسَل باحثٌ قصدًا إلى اسم استضافة.**

    والاستثناء الوحيد المقبول هو ما يصف الإعداد أو يختبر تحليله — لا ما
    يُبنى منه رابطٌ يُعطى لباحث.
    """
    from tests.tsscan import code_lines

    offenders = []
    for path in list((WEB / "src").rglob("*.tsx")) + list((WEB / "src").rglob("*.ts")):
        for number, line in code_lines(path.read_text(encoding="utf-8")):
            if "vercel.app" in line:
                offenders.append(f"{path.relative_to(WEB)}:{number}")
    assert not offenders, "شيفرة واجهة تشير إلى اسم استضافة: " + "; ".join(offenders)


def test_only_the_named_legacy_host_redirects_never_previews():
    """**توجيهُ `*.vercel.app` يُبطل المعاينات.**

    أسماء المعاينات تتغيّر مع كل فرع؛ وتوجيهها إلى الإنتاج يجعل فرعًا
    يُفحص وهو يعرض `main` — فيُقال إنه سليم وهو لم يُرَ. فيُسمّى المضيف
    الواحد المقصود، ويبقى ما عداه.
    """
    config = (WEB / "next.config.mjs").read_text(encoding="utf-8")
    assert 'const LEGACY_HOST = "athera-bay.vercel.app"' in config
    assert '"*.vercel.app"' not in config and "'*.vercel.app'" not in config
    assert 'type: "host", value: LEGACY_HOST' in config
    assert "permanent: true" in config
    # والمسار يُحفظ في الوجهة.
    assert "${CANONICAL_ORIGIN}/:path*" in config


# ══════════ ١٤. كل شاشة تقول عطبها هي ══════════

def test_no_screen_reports_another_screens_failure():
    """**عيبٌ رآه المالك في الإنتاج**: صفحة «نسيت كلمتي» تقول «تعذّر تسجيل
    الدخول».

    وخمس شاشات كانت تسقط إلى المفتاح نفسه — تسجيلٌ واستعادةٌ وتعيينٌ وتغيير
    — وواحدةٌ فقط كانت محقّة. فرسالةٌ تصف فعلًا لم يقع تُربك الباحث وتُخفي
    الفعل الذي فشل.
    """
    import json

    from tests.tsscan import code_lines

    catalog = json.loads((WEB / "messages" / "ar.json").read_text(encoding="utf-8"))["auth"]
    # **المفتاح العام نُزع نزعًا**: ما دام موجودًا يبقى بابًا يسقط إليه أي
    # مسارٍ جديد فيقول لباحثٍ يستعيد كلمته «تعذّر تسجيل الدخول».
    assert "genericError" not in catalog, "المفتاح العام ما زال موجودًا"
    for key in ("signInFailed", "registerFailed", "forgotFailed",
                "resetFailed", "changeFailed"):
        assert key in catalog, key
        assert catalog[key].strip(), key

    expected = {
        "login/page.tsx": "auth.signInFailed",
        "register/page.tsx": "auth.registerFailed",
        "forgot-password/page.tsx": "auth.forgotFailed",
        "reset-password/page.tsx": "auth.resetFailed",
        "ChangePassword.tsx": "auth.changeFailed",
    }
    for suffix, key in expected.items():
        matches = [p for p in (WEB / "src").rglob("*.tsx") if str(p).endswith(suffix)]
        assert matches, suffix
        source = matches[0].read_text(encoding="utf-8")
        assert f't("{key}")' in source, f"{suffix} لا يستعمل {key}"
        # ولا تقول شاشةٌ عطبَ غيرها.
        for other in set(expected.values()) - {key}:
            assert f't("{other}")' not in source, f"{suffix} يقول {other}"

    # ولا مفتاح عام يعود من باب آخر.
    for path in (WEB / "src").rglob("*.tsx"):
        for _n, line in code_lines(path.read_text(encoding="utf-8")):
            assert "auth.genericError" not in line, str(path.relative_to(WEB))


def test_recovery_routes_never_tear_down_a_session():
    """**من نسي كلمته ليس داخلًا.** ولو عُومل مسارا الاستعادة كغيرهما
    لمحيا الجلسة عند أي ردٍّ يشبه الرفض، وقذفا الباحث إلى صفحة الدخول وهو
    في منتصف استعادته."""
    for path in ("/api/v1/auth/forgot-password", "/api/v1/auth/reset-password"):
        assert f'"{path}"' in API_CLIENT, path
    auth_block = API_CLIENT[API_CLIENT.index("const AUTH_PATHS"):
                            API_CLIENT.index("const isAuthPath")]
    for path in ("forgot-password", "reset-password", "login", "register",
                 "refresh", "logout"):
        assert path in auth_block, path
    # **و`change-password` ليس منها**: مسارٌ مُصادَق يصحّ فيه التجديد المعتاد.
    assert "change-password" not in auth_block


# ══════════ ١٥. الزرّ يُطلب باسمه المُعلَن لا برسمه ══════════

def test_the_source_add_control_is_found_by_its_accessible_name():
    """**عيبُ فحصٍ اتُّهم به المنتج وهو فيه محسِن.**

    زرُّ إضافة المرجع رسمُه «+»، واسمه المُعلَن لقارئ الشاشة «أضِف مرجعًا
    من مكتبتك: <العنوان>». وكان الفحص يطلب الرسم، فلا يجده، فيسقط —
    والاسمُ المُعلَن هو الصواب: زرٌّ اسمه «+» لا يقول لأعمى ما يفعل.

    فيُمنع أن يعود الفحص إلى طلب الرسم في قسم المراجع.
    """
    source = (WEB / "tests" / "acceptance.spec.ts").read_text(encoding="utf-8")
    block = source[source.index("link that reference to the project"):
                   source.index("archive, trash and restore")]
    assert 'name: /أضِف مرجعًا من مكتبتك:/' in block, "الزرّ يُطلب برسمه لا باسمه"
    assert 'getByRole("button", { name: "+" })' not in block, "الرسم عاد"
    # والاسم المُعلَن ما زال في المنتج — ولا يُضعَف لأجل فحص.
    page = (WEB / "src" / "app" / "[locale]" / "portfolio" / "[projectId]"
            / "page.tsx").read_text(encoding="utf-8")
    assert 'aria-label={`${t("project.addSource")}: ${source.title}`}' in page, (
        "اسم الزرّ المُعلَن أُزيل — وذلك إضعافُ إتاحةٍ لأجل فحص")


def test_the_link_is_proven_by_the_server_response_not_the_screen():
    """**والحال الافتراضية تُقرأ من ردّ الخادم.** فلو كتبتها الواجهة من
    عندها لقال الفحص «محفوظ فقط» عن علاقةٍ ليست كذلك."""
    source = (WEB / "tests" / "acceptance.spec.ts").read_text(encoding="utf-8")
    block = source[source.index("link that reference to the project"):
                   source.index("archive, trash and restore")]
    assert "waitForResponse" in block
    assert "endsWith(\"/sources\")" in block
    assert "toBe(201)" in block
    assert 'linkedBody.use_state' in block and '.toBe("saved_only")' in block


# ══════════ ١٦. ظرفُ تنفيذ الرحلة ══════════

def test_the_p1_journey_has_its_own_execution_envelope():
    """**الرحلة كانت تُقتل قبل أن تبلغ آخرها.**

    سبعَ عشرةَ خطوةً في فحصٍ واحد، وفيها معالجةُ مستندٍ حقيقية وجولةٌ إلى
    نموذج — والمهلة العامة تسعون ثانية. فسقط الفحص عند الخطوة الرابعة عشرة
    **لا لأن شيئًا فشل بل لأن الوقت نفد**، فبدا الرفعُ ساقطًا وهو لم يُفحص.

    والمهلة هنا لا تُعرّف حدّ الإخفاق: حدودُه في مهلة كل عملية على حدة.
    وهذه لا تفعل إلا أن تمنع القتل المبكر.
    """
    import re

    spec = (WEB / "tests" / "acceptance.spec.ts").read_text(encoding="utf-8")
    config = (WEB / "playwright.config.ts").read_text(encoding="utf-8")

    match = re.search(r"test\.setTimeout\(([^)]+)\)", spec)
    assert match, "رحلة P1 بلا ظرف تنفيذ خاص بها"
    envelope = eval(match.group(1).replace("_", ""))  # noqa: S307 - ثابت في مستودعنا

    default_match = re.search(r"^\s*timeout:\s*([0-9_]+),", config, re.M)
    assert default_match, "لا مهلة عامة في الإعداد"
    default = int(default_match.group(1).replace("_", ""))

    assert envelope > default * 5, (
        f"ظرف الرحلة {envelope}ms ليس أكبر بوضوح من العام {default}ms")
    # **وليست بلا حدّ**: مهلةٌ مفتوحة تُبقي إخفاقًا معلّقًا حتى تُقتل المهمّة.
    assert envelope <= 30 * 60 * 1000, "ظرفٌ مفتوح عمليًّا"


def test_raising_the_journey_envelope_did_not_slow_the_fast_suites():
    """حزمتا دورة الحياة والاستعادة سريعتان بلا اعتماد — ورفعُ المهلة
    العامة يجعل كل عطبٍ فيهما بطيء الظهور."""
    config = (WEB / "playwright.config.ts").read_text(encoding="utf-8")
    assert "timeout: 90_000," in config, "المهلة العامة رُفعت للحزم كلها"
    for suite in ("auth-refresh.spec.ts", "recovery.spec.ts"):
        source = (WEB / "tests" / suite).read_text(encoding="utf-8")
        assert "test.setTimeout" not in source, f"{suite} رُفعت مهلته بلا داعٍ"


def test_the_journey_still_has_no_unbounded_or_sleeping_waits():
    """الظرفُ الأوسع لا يعني انتظارًا بلا حدّ ولا نومًا ثابتًا."""
    spec = (WEB / "tests" / "acceptance.spec.ts").read_text(encoding="utf-8")
    assert "waitForTimeout" not in spec, "نومٌ ثابت حيث توجد حالٌ تُنتظر"
    # وكل انتظارٍ للشبكة محدود.
    for chunk in spec.split("waitForResponse")[1:]:
        head = chunk[:400]
        assert "timeout:" in head, "انتظارُ شبكةٍ بلا حدّ"


def test_the_consent_gate_has_exactly_one_definition():
    """**بابٌ واحد لا نسختان.**

    كان زرّ الإذن يعيش داخل مكوّن الرفع وحده، فمن رفع مستنده من «مكتبتي»
    لم يجد له بابًا أصلًا. والعلاج الخاطئ أن يُنسخ الزرّ إلى الشاشة الأخرى —
    فتفترق النسختان عند أول تعديل، ويصير الحدّ العلمي شيئين يُسمّيان باسم
    واحد. فالتعريف واحد يُركَّب حيث يقف الباحث.
    """
    owners = [
        path
        for path in (WEB / "src").rglob("*.tsx")
        if any('data-testid="dic2-grant"' in line for _, line in
               code_lines(path.read_text(encoding="utf-8")))
    ]
    assert [p.name for p in owners] == ["Dic2Consent.tsx"], (
        f"حدّ DIC2 معرَّف في أكثر من موضع: {[p.name for p in owners]}")


def test_the_dic2_gate_is_mounted_where_the_library_sends_the_researcher():
    """**الطلب يُعلَن فيُستجاب.**

    المكتبة تقول «بانتظار موافقتك للمتابعة» وتحيل إلى مراجعة الرسالة. فإن
    لم تكن البوابة مركَّبة هناك، فالباحث يصل إلى شاشةٍ تطلب منه شيئًا لا
    يستطيع فعله — وطلبٌ بلا باب أسوأ من ألا يُطلب.
    """
    review = (WEB / "src" / "app" / "[locale]" / "theses" / "[thesisId]"
              / "review" / "page.tsx").read_text(encoding="utf-8")
    code = "\n".join(line for _, line in code_lines(review))
    assert "Dic2Consent" in code, "صفحة المراجعة بلا بوابة إذن"
    assert "thesisId={thesisId}" in code, "البوابة غير مقيّدة برسالة الصفحة"


def test_the_library_links_to_the_exact_thesis_not_to_a_list():
    """**رسالته هو، لا قائمةٌ يبحث فيها.**

    المعرّف معروفٌ في البطاقة، فالرابط يقصده. وإحالةٌ إلى قائمةٍ تجعل الباحث
    يتعرّف على مستنده بين بطاقاتٍ متشابهة — وهو ما لا يُطلب من أحد.
    """
    library = (WEB / "src" / "app" / "[locale]" / "library"
               / "page.tsx").read_text(encoding="utf-8")
    code = "\n".join(line for _, line in code_lines(library))
    assert "theses/${file.thesis_id}/review" in code, "رابط المراجعة غير مقيّد بالرسالة"


def test_the_journey_reaches_review_by_the_researchers_own_path():
    """الرحلة تصل إلى المراجعة كما يصل الباحث: من بطاقة مستنده — لا بأخذ
    أول رابطٍ نصُّه «راجع» في قائمةٍ راكمت رسائل تشغيلاتٍ سابقة."""
    spec = (WEB / "tests" / "acceptance.spec.ts").read_text(encoding="utf-8")
    code = "\n".join(line for _, line in code_lines(spec))
    assert 'getByRole("link", { name: /راجع|مراجعة/ }).first()' not in code, (
        "الرحلة تفتح أول مراجعةٍ تجدها")
    assert code.count(r"waitForURL(/\/theses\/[^/]+\/review/") >= 2, (
        "الرحلة لا تتحقّق أنها في مراجعة رسالةٍ بعينها")
    assert "dic2-granted" in code, "الرحلة لا تُثبت أن الإذن مُنح فعلًا"


def test_approved_knowledge_is_reachable_from_the_browser():
    """**ما اعتُمد يجب أن يُسأل عنه.**

    الباحث يعالج مستنده ويعتمد منه معلومات، ثم يفتح بُبريفا AI فيجد مرفقًا
    يقبل رفعًا جديدًا وحده — والنسخة الجديدة غير مقروءة، فلا معلومة معتمَدة
    فيها. فكانت المعرفة تُعتمد ثم لا يبلغها سؤال أبدًا: عملٌ يُطلب من الباحث
    ولا يُستعمل.
    """
    library = (WEB / "src" / "app" / "[locale]" / "library"
               / "page.tsx").read_text(encoding="utf-8")
    lib_code = "\n".join(line for _, line in code_lines(library))
    assert "/ai?file=${file.id}" in lib_code, "لا طريق من المستند إلى السؤال عنه"

    ai_input = (WEB / "src" / "components" / "AtheraAiInput.tsx").read_text(encoding="utf-8")
    ai_code = "\n".join(line for _, line in code_lines(ai_input))
    assert "attachFileId" in ai_code, "المرفق لا يأتي إلا من قرص الباحث"
    assert "/api/v1/files/${attachFileId}" in ai_code, "اسم المرفق يُخمَّن لا يُقرأ"

    page = (WEB / "src" / "app" / "[locale]" / "ai" / "page.tsx").read_text(encoding="utf-8")
    page_code = "\n".join(line for _, line in code_lines(page))
    assert "attachFileId={attachFileId}" in page_code, "شاشة الذكاء تتجاهل المستند المُحال إليها"
    assert 'get("file")' in page_code, "الإحالة لا تُقرأ من الرابط"


def test_dcc2_is_proven_as_a_boundary_of_its_own():
    """**إذنان لا يُدمجان.** واعتمادُ معرفةٍ من مستند (DIC2) لا يأذن بإرسالها
    إلى مزوّد لأجل سؤال (DCC2). والرحلة تُثبت الحدّ الثاني مطلوبًا بعد منح
    الأول — لا «إن ظهر»: شرطٌ يبتلع غيابَ الحدّ يجعل انهيارَ الحدّين نجاحًا.
    """
    spec = (WEB / "tests" / "acceptance.spec.ts").read_text(encoding="utf-8")
    code = "\n".join(line for _, line in code_lines(spec))
    assert "if (await consent.count())" not in code, "حدّ DCC2 يُفحص شرطيًّا"
    assert 'name: "السماح والإجابة"' in code, "الرحلة لا تمسّ حدّ المحادثة"
    assert "ai-attachment" in code, "الرحلة تسأل بلا مرفق فلا تبلغ المعرفة المعتمَدة"
    # ولا يُمنح أحدهما سلفًا في الشيفرة.
    ai_input = (WEB / "src" / "components" / "AtheraAiInput.tsx").read_text(encoding="utf-8")
    ai_code = "\n".join(line for _, line in code_lines(ai_input))
    assert "chat-consent?decision=grant" in ai_code, "إذن المحادثة لا يُطلب صراحةً"
    assert 'needs === "chat_consent"' in ai_code, "الواجهة لا تحترم حدّ المحادثة"


def test_the_approval_is_read_from_its_contract_not_from_translated_prose():
    """**«معتمَد» و«معتمَدة» فرقُ حرفٍ في ترجمة، لا فرقٌ في ما وقع.**

    وكان إثبات الاعتماد يطابق نصًّا لا تكتبه الشاشة أصلًا، بينما سطر
    الحصيلة يحمل كلمة «معتمَد» في كل زيارة — فحصٌ يمرّ على شاشةٍ لم يُعتمد
    فيها شيء، أو يسقط وقد اعتُمد. فالحال تُقرأ من سمتها.
    """
    review = (WEB / "src" / "app" / "[locale]" / "theses" / "[thesisId]"
              / "review" / "page.tsx").read_text(encoding="utf-8")
    assert "data-candidate-status={field.status}" in "\n".join(
        line for _, line in code_lines(review)), "حال المرشّح بلا عقد يُقرأ"

    spec = (WEB / "tests" / "acceptance.spec.ts").read_text(encoding="utf-8")
    code = "\n".join(line for _, line in code_lines(spec))
    assert 'getByText(/معتمَدة|اعتُمدت|approved/i)' not in code, "النصّ المترجَم ما زال دليلًا"
    # **والاعتماد يُقاس بالحصيلة.** إعادةُ العثور على البطاقة باسم حقلها
    # تلتبس: الأسماء تتكرّر، فتُقرأ بطاقةٌ غير التي نُقر عليها.
    assert "data-review-approved" in code, "الاعتماد لا يُقاس برقمٍ لا يلتبس"
    assert 'filter({ hasText: field }).first()' not in code, "البطاقة تُلتمس باسمها ثانيةً"
    assert "decide=[" in code, "حالُ نداء القرار لا تُذكر مع الإخفاق"


def test_the_library_keeps_reading_state_while_work_is_running():
    """**المعالجة تجري والبطاقة واقفة.**

    الحال كانت تُقرأ مرّتين ثم لا تُقرأ أبدًا: الخادم يقرأ المستند ويستخرج
    منه ثم يقف عند حدّ الإذن، والشاشة باقية على «قيد المعالجة» حتى يعيد
    الباحث تحميلها بنفسه — وهو لا يعرف أن عليه ذلك. فظنّ أن مستنده عالق،
    والمنتج هو من ينتظره.
    """
    library = (WEB / "src" / "app" / "[locale]" / "library"
               / "page.tsx").read_text(encoding="utf-8")
    code = "\n".join(line for _, line in code_lines(library))
    assert "RUNNING.has(file.processing_status)" in code, "الشاشة لا تُعيد قراءة حالٍ جارية"
    assert "window.setTimeout(" in code and "loadFiles();" in code, "لا إعادة قراءة مجدولة"
    assert "window.clearTimeout" in code, "مؤقّتٌ بلا تنظيف"
    # **ويقف عند حالٍ مستقرّة** — لا قصفَ للـAPI بعد انتهاء العمل. والشرط
    # صار يشمل ما طُلبت معالجته أيضًا، فيُقرأ من متغيّره لا من صيغته.
    assert "if (!watching) return;" in code, "الاستطلاع بلا شرطٍ يوقفه"
    assert "const watching = files.some(" in code, "الشرط لا يُشتقّ من القائمة"


def test_the_running_states_and_their_label_cannot_drift():
    """**سجلّان يصفان الشيء نفسه.**

    `RUNNING` تقول أيّ الحالات ما زال فيها عمل، و`PROCESSING_LABEL` تقول
    أيّها يُسمّى «قيد المعالجة». فإن افترقا صارت حالٌ تُعرض جاريةً ولا
    تُستطلَع — أو تُستطلَع أبدًا وهي مستقرّة. وهو الخطأ المتكرّر نفسه:
    قيمةٌ تُكتب بجانب سجلّها بدل أن تُشتقّ منه.
    """
    import re

    library = (WEB / "src" / "app" / "[locale]" / "library"
               / "page.tsx").read_text(encoding="utf-8")
    code = "\n".join(line for _, line in code_lines(library))

    running = set(re.findall(r'"([a-z_]+)"', re.search(
        r"const RUNNING: ReadonlySet<string> = new Set\(\[([^\]]*)\]\)", code).group(1)))
    labels = dict(re.findall(r"(\w+):\s*\"(library\.\w+)\"", re.search(
        r"const PROCESSING_LABEL: Record<string, string> = \{([^}]*)\}", code).group(1)))

    assert running, "لا حالات جارية معرَّفة"
    assert running <= set(labels), f"حالٌ جارية بلا نصّ يُعرض: {running - set(labels)}"
    processing_labelled = {state for state, key in labels.items()
                           if key == "library.processing"}
    assert running == processing_labelled, (
        f"سجلّا الحالة افترقا: جارية {sorted(running)} · "
        f"معروضة «قيد المعالجة» {sorted(processing_labelled)}")


def test_a_thesis_without_a_file_shows_no_gate_and_no_alarm():
    """**غيابُ ملفٍ ليس عطبًا.**

    البوابة صارت تُركَّب في كل مراجعة رسالة، ومن سجّل رسالته يدويًّا لا
    مستند له يُستخرَج منه — فيردّ الخادم `thesis.no_file` بحقّ. ولو عُومل
    ذلك خطأً لظهرت لافتةٌ حمراء على شاشةٍ لم يقع فيها شيء، **وحارسٌ يصرخ
    بلا سبب يُطفَأ ثم لا يحرس شيئًا.**
    """
    gate = (WEB / "src" / "components" / "Dic2Consent.tsx").read_text(encoding="utf-8")
    code = "\n".join(line for _, line in code_lines(gate))
    assert 'err.payload.code === "thesis.no_file"' in code, "غيابُ الملف يُعرض خطأً"
    # وما عدا ذلك يُقال — لا يُبتلع كل خطأ.
    assert "setError(err instanceof AtheraApiError" in code, "الأخطاء الأخرى تُبتلع"


def test_a_late_library_answer_cannot_overwrite_a_newer_one():
    """**جوابٌ متأخّر لا يمحو جوابًا أحدث منه.**

    صار للمكتبة استطلاعٌ دوري، فصارت قراءتان تجريان معًا: واحدة يطلقها
    الاستطلاع وأخرى يطلقها رفعُ ملفٍ للتوّ، ولا ترتيب بين ردَّيهما. فإن وصل
    ردُّ الاستطلاع — وقد صدر قبل الرفع ولا يعرف بالملف — بعد ردّ الرفع، حلّت
    القائمة الأقدم محلّ الأحدث: يرفع الباحث ملفه، يرى «تم الحفظ»، ثم لا يجد
    الملف في مكتبته. وقد وقع ذلك في الإنتاج فعلًا.
    """
    library = (WEB / "src" / "app" / "[locale]" / "library"
               / "page.tsx").read_text(encoding="utf-8")
    code = "\n".join(line for _, line in code_lines(library))
    assert "latest.current += 1" in code, "القراءات بلا ترتيب"
    assert "if (ticket === latest.current) setFiles(next)" in code, (
        "ردٌّ قديم ما زال يُعرض")


def test_the_library_wait_is_bounded():
    """تشغيلةٌ ماتت في منتصفها تترك حالًا «جارية» لا تنتهي — ولولا حدٌّ
    لظلّت الشاشة تسأل عنها ما دامت مفتوحة. **والانتظار المفتوح ليس صبرًا.**"""
    library = (WEB / "src" / "app" / "[locale]" / "library"
               / "page.tsx").read_text(encoding="utf-8")
    code = "\n".join(line for _, line in code_lines(library))
    assert "polls.current >= MAX_POLLS" in code, "استطلاعٌ بلا حدّ"
    import re
    cap = int(re.search(r"const MAX_POLLS = (\d+);", code).group(1))
    assert 0 < cap <= 500, f"حدُّ الاستطلاع {cap} ليس حدًّا"


def test_a_missing_document_is_reported_with_what_was_rendered():
    """«العنصر غير موجود» لا تفرّق بين قائمةٍ لم تُعرض وقائمةٍ عُرضت بلا
    هذا الملف — وهما عطبان مختلفان. فيُذكر العدد مع الغياب، والعدد لا
    يحمل اسمًا ولا سرًّا."""
    spec = (WEB / "tests" / "acceptance.spec.ts").read_text(encoding="utf-8")
    code = "\n".join(line for _, line in code_lines(spec))
    assert "listCalls=[" in code, "الغياب يُبلَّغ بلا سياق"
    # والسياق يُطبع فعلًا: `toMatchObject` تطبع المفاتيح المقارَنة وحدها.
    assert "toMatchObject({ mine:" not in code, "السياق يُجمع ثم لا يُطبع"
    # ولا أجسام ولا روابط في الدليل — الطريقة والحال فقط.
    assert "r.request().method()}:${r.status()}" in code, "الدليل يحمل أكثر مما يلزم"


def test_the_ai_answer_is_read_after_consent_and_proved_grounded():
    """**المقروء بعد الإذن لا قبله.**

    بطاقةُ الجواب معروضة قبل الإذن أيضًا، وفيها القيد معلنًا. فلو قُرئت
    فورَ النقر لقُرئ نصُّ ما قبل الإذن — يطول عشرين حرفًا ولا يحمل ترميزًا،
    فيمرّ الفحص **وهو لم يفحص جوابًا**.

    و«مسنود بدليل موثّق» تفرّق بينهما: الخادم لا يقولها إلا حين يُبنى الجواب
    على معرفةٍ اعتمدها الباحث، وقبل الإذن تُفرَّغ تلك المعرفة فيقول «اقتراح
    نموذج — لا دليل».
    """
    spec = (WEB / "tests" / "acceptance.spec.ts").read_text(encoding="utf-8")
    code = "\n".join(line for _, line in code_lines(spec))
    ai = code[code.index("PUBRIVA AI reaches approved knowledge"):]
    assert "toBeHidden" in ai, "الجواب يُقرأ قبل أن تسقط البوابة"
    assert "مسنود بدليل موثّق" in ai, "لا إثبات أن الجواب مسنود لا مقترَح"
    # وقبل الإذن: الحدّ أمسك فعلًا — لا مجرّد أن زرًّا ظهر.
    assert "اقتراح نموذج" in ai, "لا إثبات أن المعرفة لم تُرسل قبل الإذن"
    assert "not.toBe(refusal)" in ai, "لا إثبات أن عمليةً جديدة جرت بعد الإذن"
    # والنصّ يُقرأ مرّتين قصدًا: مرّةً قبل الإذن ليُحفظ نصُّ الرفض، ومرّةً
    # بعد سقوط البوابة ليُقرأ الجواب. فالمقارنة على **آخر** قراءة.
    assert ai.rindex("ai-answer-text") > ai.index("toBeHidden"), (
        "الجواب النهائي يُقرأ قبل سقوط البوابة")
    assert ai.index("refusal") < ai.index("consent.click()"), (
        "نصّ الرفض يُلتقط بعد منح الإذن، فلا يفرّق شيئًا")


def test_the_upload_step_proves_the_library_not_the_uploader():
    """**«رُفع إلى مكتبتي» تُثبَت في المكتبة.**

    شارةُ النجاح تحمل اسم الملف («✓ تم الحفظ — اسم الملف»)، وكان الفحص
    يطلب الاسم في الصفحة كلها — فيجده في الشارة ويمضي. فمكتبةٌ لا تُحدَّث
    بعد الرفع كانت تمرّ سنينًا: الادّعاء أن الملف صار في المكتبة، والدليل
    أن الرافع يقول إنه رفع.
    """
    spec = (WEB / "tests" / "acceptance.spec.ts").read_text(encoding="utf-8")
    code = "\n".join(line for _, line in code_lines(spec))
    upload = code[code.index("upload a file into My Library"):
                  code.index("link that exact file to the project")]
    assert "getByText(FILENAME)" not in upload, "الاسم يُطلب في الصفحة كلها"
    assert 'locator("article.card").filter({ hasText: FILENAME })' in upload, (
        "الرفع لا يُثبَت في قائمة المكتبة")


def test_the_file_add_control_is_named_by_what_it_does():
    """**زرٌّ اسمه «+» لا يقول لأعمى ما يفعل** (A11Y-1).

    وفي قسم الملفات زرٌّ لكل ملف، كلّها بالاسم نفسه — فلا يُميَّز بينها
    بالسمع إطلاقًا. والنمط الصحيح كان بجانبه: زرُّ إضافة المرجع يحمل الفعل
    واسم المرجع منذ البداية.

    والرسمُ «+» باقٍ كما هو: هذا إصلاحُ اسمٍ مُعلَن لا إعادةُ تصميم.
    """
    project = (WEB / "src" / "app" / "[locale]" / "portfolio" / "[projectId]"
               / "page.tsx").read_text(encoding="utf-8")
    code = "\n".join(line for _, line in code_lines(project))
    assert 't("project.addFile")}: ${file.original_filename}' in code, (
        "زرّ إضافة الملف بلا اسمٍ يخصّ ملفه")

    # والفحص يتبع الاسم المُعلَن — لا يُبقي على الرسم بعد أن تغيّر.
    spec = (WEB / "tests" / "acceptance.spec.ts").read_text(encoding="utf-8")
    spec_code = "\n".join(line for _, line in code_lines(spec))
    assert 'getByRole("button", { name: "+" })' not in spec_code, (
        "الرحلة ما زالت تطلب الزرّ برسمه")
    assert "/^أضِف ملفًّا من مكتبتك:/" in spec_code, "الرحلة لا تطلبه باسمه المُعلَن"


def test_a_requested_processing_keeps_being_watched():
    """**طلبُ المعالجة سببٌ للمراقبة، لا الحالُ المعروضة وحدها.**

    الاستطلاع كان يدور ما دام في القائمة ملفٌ في حالٍ جارية. وطلبُ المعالجة
    يُنشئ التشغيلة في مهمّةٍ خلفية، فالقراءة التي تلي الطلب قد تسبقها فتعود
    بـ`not_processed` — وليست حالًا جارية، فلا يدور الاستطلاع ولا تُقرأ
    الحال ثانيةً أبدًا. فتبقى البطاقة تقول «لم تُعالَج بعد» وقد بدأت
    معالجتها، إلى أن يعيد الباحث التحميل بنفسه.
    """
    library = (WEB / "src" / "app" / "[locale]" / "library"
               / "page.tsx").read_text(encoding="utf-8")
    code = "\n".join(line for _, line in code_lines(library))
    assert "requested.current.add(file.id)" in code, "الطلب لا يُسجَّل"
    assert 'requested.current.has(file.id) && file.processing_status === "not_processed"' in code, (
        "الطلب لا يُبقي المراقبة")
    # والحدّ باقٍ: مراقبةٌ بلا نهاية ليست صبرًا.
    assert "polls.current >= MAX_POLLS" in code, "المراقبة بلا حدّ"


def test_a_stuck_processing_state_says_which_question_failed():
    """«ما زالت `not_processed`» لا تقول: هل لم تبدأ المعالجة، أم بدأت ولم
    تُقرأ؟ سؤالان مختلفان وعلاجان مختلفان — فيُذكر مع الحال هل قُبل الطلب،
    وكم قراءةً جرت بعده، وهل تقول الشاشة خطأً. والمعرّف لا يُسجَّل."""
    spec = (WEB / "tests" / "acceptance.spec.ts").read_text(encoding="utf-8")
    code = "\n".join(line for _, line in code_lines(spec))
    assert "process=[" in code and "listCalls=" in code, "الحال العالقة تُبلَّغ بلا سياق"
    assert 'path.startsWith("/api/v1/theses/process-file/")' in code, "طلب المعالجة لا يُرصد"
    assert "r.request().method()}:${r.status()}" in code, "الدليل يحمل أكثر مما يلزم"


def test_a_consent_granted_elsewhere_is_seen_in_the_library():
    """**إذنٌ يُمنح في شاشةٍ أخرى يجب أن يُرى في هذه.**

    الباحث يمنح الإذن في صفحة مراجعة الرسالة ثم يعود إلى مكتبته، والخادم
    يكون قد استأنف فعلًا — قِيس في الإنتاج فمضى `parsing` ← `extracting` ←
    `awaiting_review` في خمسٍ وثلاثين ثانية. والبطاقة كانت تبقى «بانتظار
    موافقتك للمتابعة»: تطلب منه إذنًا **قد منحه**، إلى أن يعيد التحميل
    بنفسه.

    و`awaiting_consent` حالٌ مستقرّة بحقّ وقد تدوم أيامًا، فاستطلاعُها
    دائمًا قصفٌ بلا سبب. فالترقّب محدودٌ بميزانية تُمنح عند العودة إلى
    الشاشة وتُستهلك بالقراءة.
    """
    library = (WEB / "src" / "app" / "[locale]" / "library"
               / "page.tsx").read_text(encoding="utf-8")
    code = "\n".join(line for _, line in code_lines(library))
    assert 'file.processing_status === "awaiting_consent" && consentWatch.current > 0' in code, (
        "الشاشة لا ترى إذنًا مُنح في غيرها")
    assert "consentWatch.current -= 1" in code, "الترقّب لا يُستهلك، فهو بلا نهاية"
    assert 'document.addEventListener("visibilitychange"' in code, (
        "العودة إلى الشاشة ليست سببَ قراءة")
    assert 'document.removeEventListener("visibilitychange"' in code, "مستمعٌ بلا تنظيف"

    import re
    budget = int(re.search(r"const CONSENT_WATCH_POLLS = (\d+);", code).group(1))
    # يكفي الخمسَ والثلاثين ثانية المقيسة، ولا يمتدّ بلا حدّ.
    assert 14 <= budget <= 48, f"ميزانية الترقّب {budget} لا تناسب ما قيس"
