"""تبسيط تسجيل الدخول — بلا إضعاف ما لا علاقة له بالتبسيط.

**السؤال الذي يحرسه هذا الملف:** هل صار الدخول أبسط دون أن يصير أضعف؟

فرفعُ التحقق بخطوتين عن الدخول الاعتيادي يجعل كلمة المرور الحاجز الوحيد.
وحاجزٌ واحد بلا حدّ محاولات ولا سجل يعني أن التخمين الآلي مسألة وقت.
"""
from __future__ import annotations

import inspect
import json
import pathlib

import pytest

from athera_api.routers import auth as auth_router
from athera_api.schemas.auth import LoginRequest
from athera_api.services import login_throttle

REPO = pathlib.Path(__file__).resolve().parents[3]
WEB = REPO / "apps" / "web"
LOGIN_PAGE = (WEB / "src" / "app" / "[locale]" / "login" / "page.tsx").read_text(encoding="utf-8")


# ══════════ 1. العقد: الرمز اختياري ══════════

def test_the_login_contract_does_not_require_a_verification_code():
    """§3 — ولا إخفاءَ حقلٍ بينما الخادم يشترطه."""
    field = LoginRequest.model_fields["totp_code"]
    assert not field.is_required()
    assert field.default is None
    LoginRequest(email="researcher@athera.example", password="x")  # يقبل بلا رمز


def test_mfa_is_policy_controlled_not_mandatory():
    """§2 — البنية باقية، والشرط صار سياسةً لا قاعدة."""
    from athera_api.config import Settings

    source = inspect.getsource(auth_router.login)
    assert "settings.mfa_required_for_admin_roles" in source
    assert "rbac.ADMIN_ROLE_KEYS" in source
    # ولم تُحذف البنية.
    assert hasattr(Settings(), "mfa_required_for_admin_roles")
    assert {"/api/v1/auth/mfa/enroll", "/api/v1/auth/mfa/verify"} <= _routes()


def _routes() -> set[str]:
    from athera_api.main import app

    return set(app.openapi()["paths"])


def test_a_researcher_role_never_triggers_the_mfa_gate():
    """§1 — الشرط على الأدوار الإدارية وحدها."""
    from athera_api.services import rbac

    assert "researcher" not in rbac.ADMIN_ROLE_KEYS
    assert rbac.ADMIN_ROLE_KEYS == frozenset(
        {"research_admin", "college_admin", "institution_admin", "system_admin"})


# ══════════ 2. الواجهة: الخطوة الثانية بعد طلب الخادم ══════════

def test_the_code_field_appears_only_after_the_server_asks():
    """§4 — لا يُسأل عن رمز قبل أن يقول الخادم إنه لازم."""
    assert 'step === "verification"' in LOGIN_PAGE
    assert '"auth.mfa_required"' in LOGIN_PAGE
    assert '"auth.mfa_invalid_code"' in LOGIN_PAGE
    assert 'setStep("verification")' in LOGIN_PAGE
    # والحالة الابتدائية بيانات الاعتماد وحدها.
    assert 'useState<Step>("credentials")' in LOGIN_PAGE


def test_the_default_form_asks_for_email_and_password_only():
    """§5 — لا حقل زائد في الخطوة الأولى."""
    before_step_two = LOGIN_PAGE.split('step === "verification" ? (')[0]
    assert 'autoComplete="email"' in before_step_two
    assert 'autoComplete="current-password"' in before_step_two
    assert 'autoComplete="one-time-code"' not in before_step_two


def test_failed_login_shows_one_generic_message():
    """§9 — لا تمييز بين «بريد غير موجود» و«كلمة خاطئة»."""
    assert 't("auth.genericError")' in LOGIN_PAGE
    for leak in ("emailNotFound", "wrongPassword", "userNotFound", "no_such_user"):
        assert leak not in LOGIN_PAGE, leak

    ar = json.loads((WEB / "messages" / "ar.json").read_text(encoding="utf-8"))["auth"]
    en = json.loads((WEB / "messages" / "en.json").read_text(encoding="utf-8"))["auth"]
    assert ar["genericError"] == "تعذر تسجيل الدخول. تحقق من البريد الإلكتروني وكلمة المرور."
    assert en["genericError"] == "Unable to sign in. Check your email and password."


def test_an_authenticated_visitor_is_not_shown_the_form():
    """§7 — جلسة قائمة تعني تحويلًا لا نموذجًا."""
    assert "isSignedIn()" in LOGIN_PAGE
    assert "auth.alreadySignedIn" in LOGIN_PAGE


def test_the_redirect_cannot_leave_the_site():
    """§6 — لا تحويل مفتوح."""
    assert "function safeDestination" in LOGIN_PAGE
    assert 'wanted.startsWith("//")' in LOGIN_PAGE
    assert 'wanted.startsWith("/")' in LOGIN_PAGE
    assert "/^\\/[a-z]+:/i" in LOGIN_PAGE


def test_forgot_password_does_not_pretend_a_flow_exists():
    """§12 — لا مسار استعادة في المنصّة، فلا زرّ يوهم بوجوده."""
    assert "auth.forgotPasswordUnavailable" in LOGIN_PAGE
    assert not {"/api/v1/auth/password-reset", "/api/v1/auth/forgot-password"} & _routes()


def test_sign_up_was_not_opened_by_this_change():
    """§13 — تبسيط الدخول ليس فتحًا للتسجيل."""
    assert "register" not in LOGIN_PAGE.lower()


def test_login_copy_exists_in_both_languages():
    ar = json.loads((WEB / "messages" / "ar.json").read_text(encoding="utf-8"))["auth"]
    en = json.loads((WEB / "messages" / "en.json").read_text(encoding="utf-8"))["auth"]
    for key in ("signIn", "email", "password", "submit", "forgotPassword",
                "totpHint", "showPassword", "alreadySignedIn"):
        assert ar[key] and en[key] and ar[key] != en[key], key
    assert ar["signIn"] == "تسجيل الدخول"


# ══════════ 3. ما حلّ محلّ الحاجز المرفوع ══════════

def test_repeated_failures_are_throttled():
    """§10 — الحاجز الثاني صار حدّ المحاولات، وكان غائبًا تمامًا."""
    from athera_api.errors import AtheraError

    login_throttle.reset()
    email = "attacker-probe@example.test"
    for _ in range(login_throttle.MAX_FAILURES_PER_WINDOW):
        login_throttle.check(email)
        login_throttle.record_failure(email)
    with pytest.raises(AtheraError) as err:
        login_throttle.check(email)
    assert err.value.code == "auth.too_many_attempts"
    login_throttle.reset()


def test_throttling_keys_on_email_so_unknown_accounts_are_not_distinguishable():
    """اختلاف السلوك بين بريد موجود وآخر غير موجود يجعل العدّ ممكنًا."""
    source = inspect.getsource(login_throttle.check)
    assert "email" in source
    assert "user_id" not in source
    # والخنق يسبق فحص كلمة المرور.
    login_source = inspect.getsource(auth_router.login)
    assert login_source.index("login_throttle.check") < login_source.index("verify_password")


def test_a_successful_sign_in_clears_the_counter():
    login_throttle.reset()
    email = "researcher@example.test"
    login_throttle.record_failure(email)
    login_throttle.record_success(email)
    login_throttle.check(email)  # لا يرمي
    login_throttle.reset()


def test_failed_attempts_are_audited_without_the_address():
    """محاولة فاشلة تُسجَّل — وبصمةٍ لا بريدٍ.

    وإلا صار جدول التدقيق قائمةَ عناوين لمن حاول ولم ينجح، ومنهم من لا حساب
    له أصلًا.
    """
    source = inspect.getsource(auth_router._audit_failed_login)
    assert 'action="auth.login_failed"' in source
    assert "email_fingerprint" in source
    assert "hashlib.sha256" in source
    assert '"email": email' not in source

    login_source = inspect.getsource(auth_router.login)
    assert login_source.count("_audit_failed_login") == 2


def test_password_verification_and_account_checks_are_untouched():
    """§10 — التبسيط لم يمسّ ما ليس من التحقق بخطوتين."""
    source = inspect.getsource(auth_router.login)
    assert "verify_password(user.password_hash, payload.password)" in source
    assert "not user.is_active" in source
    assert "user.logged_in" in source          # التدقيق الناجح باقٍ
    assert "tenant_id" in source               # عزل المستأجر باقٍ


def test_the_endpoint_accepts_a_payload_without_a_verification_code():
    """§15.1–2 — الحالة الطبيعية: العقد يقبل بلا رمز، ولا يكسر.

    والفحص على العقد لا على رحلة HTTP كاملة: رحلةٌ كاملة تحتاج اعتمادًا
    حقيقيًا، واختراعه في اختبار يختبر البذرة لا المنتج.
    """
    payload = LoginRequest.model_validate(
        {"email": "researcher@athera.example", "password": "correct horse"})
    assert payload.totp_code is None

    # ورمزٌ بطول خاطئ يُرفض — الاختيارية ليست تسيّبًا.
    with pytest.raises(Exception):
        LoginRequest.model_validate({"email": "researcher@athera.example",
                                     "password": "x", "totp_code": "123"})
