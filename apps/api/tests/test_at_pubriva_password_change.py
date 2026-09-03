"""تغيير كلمة المرور | Researcher-facing password change.

**كلمةُ المالك انكشفت في أثر تشغيلة، ولم يكن في المنتج بابٌ لتغييرها.**
تسجيلٌ ودخولٌ وتجديدٌ وخروج — ولا مسار. فمن انكشفت كلمته لا يملك إلا أن
يطلب من غيره، أو يترك الحساب مفتوحًا.
"""
import uuid

import pytest

from tests.conftest import requires_db


# ══════════ ١. السياسة في موضعٍ واحد ══════════

def test_the_password_policy_lives_in_one_place():
    """وكانت مكتوبةً في `RegisterRequest` وحدها، فأيّ مسارٍ ثانٍ يكتبها
    من جديد — فتفترق سياستان ولا يُعلم أيّهما السارية."""
    from athera_api.security import PASSWORD_MIN_LENGTH, password_policy_error

    assert PASSWORD_MIN_LENGTH == 12
    assert password_policy_error("x" * 11) == "auth.password_too_short"
    assert password_policy_error("x" * 12) is None
    assert password_policy_error(" " * 30) == "auth.password_too_short"
    assert password_policy_error("x" * 2000) == "auth.password_too_long"


def test_registration_and_change_share_the_same_minimum():
    from athera_api.schemas.auth import RegisterRequest
    from athera_api.security import PASSWORD_MIN_LENGTH

    field = RegisterRequest.model_fields["password"]
    minimum = next((m.min_length for m in field.metadata if hasattr(m, "min_length")), None)
    assert minimum == PASSWORD_MIN_LENGTH, (
        "حدّ التسجيل يخالف السياسة المركزية — وهو الافتراق بعينه")


def test_no_password_value_or_hash_is_ever_recorded():
    """الأثر يحمل عددًا، لا كلمةً ولا تجزئة."""
    import inspect

    from athera_api.routers import auth

    source = inspect.getsource(auth.change_password)
    assert "refresh_tokens_revoked" in source
    for leak in ("payload.new_password}", "password_hash", "state_before"):
        assert f'"{leak}"' not in source, leak
    assert "print(" not in source and "logging" not in source


def test_no_path_changes_a_password_without_proving_ownership():
    """**بابٌ خلفيّ إداريّ يُلغي معنى الكلمة نفسها.**

    والقاعدة ليست «لا مسار اسمه reset» — فالاستعادة مسارٌ مشروع. القاعدة
    أن **كل** مسارٍ يكتب `password_hash` يُثبت الملكية أولًا: إمّا بالكلمة
    الحالية، وإمّا برمزٍ وصل بريد صاحبه ويعمل مرّة واحدة. ولا ثالث.
    """
    import inspect
    import re

    from athera_api.routers import auth

    source = inspect.getsource(auth)
    # الإسناد والوسيط المسمّى معًا: `password_hash = …` و`password_hash=…`.
    writes = re.compile(r"password_hash\s*=[^=]")
    writers = [name for name, fn in vars(auth).items()
               if callable(fn) and getattr(fn, "__module__", "") == auth.__name__
               and writes.search(inspect.getsource(fn))]
    assert set(writers) == {"register", "change_password", "reset_password"}, (
        f"مسارٌ غير متوقَّع يكتب كلمة مرور: {writers}")

    # تغييرُ الكلمة يُثبت الملكية بالكلمة الحالية.
    change = inspect.getsource(auth.change_password)
    assert "verify_password(user.password_hash, payload.current_password)" in change

    # والاستعادة برمزٍ يُجزَّأ ويُبحث به، ويُستهلك مرّة.
    reset = inspect.getsource(auth.reset_password)
    assert "password_reset.hash_token(payload.token)" in reset
    assert "record.is_usable(now)" in reset
    assert "record.consumed_at = now" in reset

    # ولا مسارٌ يقبل معرّف مستخدمٍ أو بريدًا ليكتب كلمته.
    assert not re.search(r'@router\.post\("/[^"]*(admin|force|override)', source)


# ══════════ ٢. على قاعدةٍ حقيقية ══════════

async def _register(email: str, password: str):
    from httpx import ASGITransport, AsyncClient

    from athera_api.main import app

    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as client:
        r = await client.post("/api/v1/auth/register", json={
            "email": email, "password": password,
            "full_name_ar": "باحث اختبار", "preferred_locale": "ar"})
        assert r.status_code == 201, r.text
        return r.json()


@requires_db
@pytest.mark.asyncio
async def test_changing_the_password_revokes_every_refresh_token(db_ready):
    """**التغيير يُبطل ما مضى.** ولو بقي رمز التجديد صالحًا لظلّ من نسخه
    قادرًا على إصدار رموز وصولٍ بعد التغيير — والتغيير حينئذٍ طمأنينةٌ
    كاذبة."""
    from httpx import ASGITransport, AsyncClient

    from athera_api.main import app

    email = f"pw-{uuid.uuid4().hex[:10]}@fixtures.athera"
    old, new = "correct-horse-battery", "battery-staple-correct-9"
    pair = await _register(email, old)

    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as client:
        auth = {"authorization": f"Bearer {pair['access_token']}"}

        # الرمز يعمل قبل التغيير.
        before = await client.post("/api/v1/auth/refresh",
                                   json={"refresh_token": pair["refresh_token"]})
        assert before.status_code == 200
        rotated = before.json()["refresh_token"]

        changed = await client.post("/api/v1/auth/change-password", headers=auth,
                                    json={"current_password": old, "new_password": new})
        assert changed.status_code == 204, changed.text

        # وبعده لا يعمل — ولا الأصلي ولا المُدوَّر.
        for token in (pair["refresh_token"], rotated):
            after = await client.post("/api/v1/auth/refresh",
                                      json={"refresh_token": token})
            assert after.status_code == 401, "رمز تجديدٍ نجا من تغيير الكلمة"


@requires_db
@pytest.mark.asyncio
async def test_the_new_password_works_and_the_old_one_does_not(db_ready):
    from httpx import ASGITransport, AsyncClient

    from athera_api.main import app

    email = f"pw-{uuid.uuid4().hex[:10]}@fixtures.athera"
    old, new = "correct-horse-battery", "battery-staple-correct-9"
    pair = await _register(email, old)

    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as client:
        auth = {"authorization": f"Bearer {pair['access_token']}"}
        assert (await client.post("/api/v1/auth/change-password", headers=auth,
                                  json={"current_password": old,
                                        "new_password": new})).status_code == 204

        assert (await client.post("/api/v1/auth/login",
                                  json={"email": email, "password": old})).status_code == 401
        ok = await client.post("/api/v1/auth/login",
                               json={"email": email, "password": new})
        assert ok.status_code == 200, ok.text


@requires_db
@pytest.mark.asyncio
async def test_a_wrong_current_password_changes_nothing(db_ready):
    from httpx import ASGITransport, AsyncClient

    from athera_api.main import app

    email = f"pw-{uuid.uuid4().hex[:10]}@fixtures.athera"
    old = "correct-horse-battery"
    pair = await _register(email, old)

    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as client:
        auth = {"authorization": f"Bearer {pair['access_token']}"}
        bad = await client.post("/api/v1/auth/change-password", headers=auth,
                                json={"current_password": "not-the-password",
                                      "new_password": "battery-staple-correct-9"})
        assert bad.status_code == 403
        assert bad.json()["error"]["code"] == "auth.current_password_wrong"
        # والكلمة القديمة ما زالت تعمل: لم يقع تغيير.
        assert (await client.post("/api/v1/auth/login",
                                  json={"email": email, "password": old})).status_code == 200


@requires_db
@pytest.mark.asyncio
async def test_a_weak_new_password_is_refused_by_the_central_policy(db_ready):
    from httpx import ASGITransport, AsyncClient

    from athera_api.main import app

    email = f"pw-{uuid.uuid4().hex[:10]}@fixtures.athera"
    old = "correct-horse-battery"
    pair = await _register(email, old)

    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as client:
        auth = {"authorization": f"Bearer {pair['access_token']}"}
        weak = await client.post("/api/v1/auth/change-password", headers=auth,
                                 json={"current_password": old, "new_password": "short"})
        assert weak.status_code == 422
        assert weak.json()["error"]["code"] == "auth.password_too_short"


@requires_db
@pytest.mark.asyncio
async def test_an_unauthenticated_caller_cannot_change_a_password(db_ready):
    from httpx import ASGITransport, AsyncClient

    from athera_api.main import app

    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as client:
        r = await client.post("/api/v1/auth/change-password",
                              json={"current_password": "x" * 12,
                                    "new_password": "y" * 12})
        assert r.status_code in (401, 403)
