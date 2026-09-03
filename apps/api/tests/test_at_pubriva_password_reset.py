"""استعادة كلمة المرور | Password recovery — the security surface.

**الاستعادة بابٌ يُفتح بلا مصادقة.** فكل ضعفٍ فيه ضعفٌ في الحساب كلّه:
رمزٌ يعمل مرّتين، أو جوابٌ يفشي وجود الحساب، أو رمزٌ يُكتب في سجلّ — كلٌّ
منها يُسقط الحماية التي بُنيت فوقه.
"""
import datetime as dt
import uuid

import pytest

from tests.conftest import requires_db


# ══════════ ١. تصميم الرمز ══════════

def test_the_raw_token_is_never_stored_only_its_hash():
    """من قرأ الجدول لا يملك ما يُعيد به ضبط كلمة أحد."""
    from athera_api.models.identity import PasswordResetToken

    columns = {c.name for c in PasswordResetToken.__table__.columns}
    assert "token_hash" in columns
    for forbidden in ("token", "raw_token", "secret", "plaintext"):
        assert forbidden not in columns, forbidden


def test_the_token_is_cryptographically_random_and_long():
    from athera_api.services import password_reset as pr

    seen = {pr.new_token()[0] for _ in range(200)}
    assert len(seen) == 200, "تكرارٌ في التوليد — العشوائية مشبوهة"
    raw, hashed = pr.new_token()
    assert len(raw) >= 40 and len(hashed) == 64
    assert raw not in hashed


def test_the_expiry_is_short():
    from athera_api.services import password_reset as pr

    assert 15 <= pr.TOKEN_TTL_MINUTES <= 30
    now = dt.datetime.now(dt.UTC)
    assert pr.expiry(now) - now == dt.timedelta(minutes=pr.TOKEN_TTL_MINUTES)


def test_a_token_is_usable_only_once_and_only_before_expiry():
    from athera_api.models.identity import PasswordResetToken

    now = dt.datetime.now(dt.UTC)
    live = PasswordResetToken(user_id=uuid.uuid4(), token_hash="h",
                              expires_at=now + dt.timedelta(minutes=5))
    assert live.is_usable(now)

    live.consumed_at = now
    assert not live.is_usable(now), "رمزٌ مستهلَك ما زال صالحًا"

    expired = PasswordResetToken(user_id=uuid.uuid4(), token_hash="h2",
                                 expires_at=now - dt.timedelta(seconds=1))
    assert not expired.is_usable(now)

    dead = PasswordResetToken(user_id=uuid.uuid4(), token_hash="h3",
                              expires_at=now + dt.timedelta(minutes=5))
    dead.invalidated_at = now
    assert not dead.is_usable(now)


def test_the_recovery_url_carries_the_token_in_the_fragment():
    """**ما بعد `#` لا يُرسَل في طلب HTTP إطلاقًا** — لا يبلغ الخادم ولا
    سجلاته ولا ترويسة `Referer`. والرمز في `?query` يُكتب في كلٍّ منها."""
    from athera_api.services import password_reset as pr

    raw, _ = pr.new_token()
    url = pr.recovery_url(raw, "ar")
    assert f"#token={raw}" in url
    assert "?token=" not in url and f"?{raw}" not in url
    assert url.split("#")[0].endswith("/ar/reset-password")


# ══════════ ٢. حدّ البريد ══════════

def test_the_email_boundary_fails_truthfully_when_unconfigured():
    """**نجاحٌ صامت يترك الباحث ينتظر رسالةً لن تصل.**"""
    from athera_api.services import email

    assert isinstance(email.provider(), email.UnconfiguredProvider)
    assert email.is_configured() is False
    with pytest.raises(email.EmailNotConfigured):
        email.send(email.Message(to="a@b.c", subject="s", body="b"))


def test_the_console_provider_is_refused_in_production():
    """مسارُ تطويرٍ يصل الإنتاج بالسهو هو ما يجعل الاستعادة تُسرق من سجلّ."""
    from athera_api.services import email

    class _Fake:
        app_env = "production"
        email_provider = "console"

    original = email.get_settings
    email.get_settings = lambda: _Fake()  # type: ignore[assignment]
    try:
        with pytest.raises(email.EmailNotConfigured):
            email.provider()
    finally:
        email.get_settings = original  # type: ignore[assignment]


def test_a_message_never_prints_its_body():
    """تمثيلُ الكائن يظهر في آثار الاستثناءات — والجسم يحمل رابط الاستعادة."""
    from athera_api.services.email import Message

    m = Message(to="a@b.c", subject="s", body="https://x/#token=SECRET")
    assert "SECRET" not in repr(m)
    assert "[redacted]" in repr(m)


def test_no_reset_secret_is_logged_or_audited():
    import inspect

    from athera_api.routers import auth

    for fn in (auth.forgot_password, auth.reset_password):
        source = inspect.getsource(fn)
        assert "logger.info(raw" not in source
        for leak in ("raw}", "raw)", "token=%s", "url"):
            assert f"logger.error({leak}" not in source
        # الأثر يحمل حقائق لا أسرارًا.
        assert "payload.new_password" not in source.split("audit.record")[-1]
        assert "raw" not in source.split("audit.record")[-1]


# ══════════ ٣. المسار على قاعدةٍ حقيقية ══════════

async def _client():
    from httpx import ASGITransport, AsyncClient

    from athera_api.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def _register(client, email: str, password: str):
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": password,
        "full_name_ar": "باحث اختبار", "preferred_locale": "ar"})
    assert r.status_code == 201, r.text
    return r.json()


async def _live_token_hash_for(user_email: str) -> str | None:
    from sqlalchemy import select

    from athera_api.db import system_session
    from athera_api.models.identity import PasswordResetToken, User

    async with system_session() as session:
        user = (await session.execute(
            select(User).where(User.email == user_email))).scalar_one()
        row = (await session.execute(
            select(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id,
                   PasswordResetToken.consumed_at.is_(None),
                   PasswordResetToken.invalidated_at.is_(None))
            .order_by(PasswordResetToken.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        return row.token_hash if row else None


@requires_db
@pytest.mark.asyncio
async def test_known_and_unknown_emails_are_indistinguishable(db_ready):
    """**فرقٌ في الجواب يجعل هذا المسار أداة تعداد حسابات.**"""
    from athera_api.services.password_reset import reset_rate_limits

    reset_rate_limits()
    known = f"pr-{uuid.uuid4().hex[:10]}@fixtures.athera"
    async with await _client() as client:
        await _register(client, known, "correct-horse-battery")
        a = await client.post("/api/v1/auth/forgot-password", json={"email": known})
        b = await client.post("/api/v1/auth/forgot-password",
                              json={"email": f"absent-{uuid.uuid4().hex[:8]}@fixtures.athera"})

    assert a.status_code == b.status_code == 200
    assert a.json() == b.json(), "الجوابان مختلفان — وجود الحساب مُفشى"
    assert "إذا كان البريد مرتبطًا بحساب" in a.json()["message_ar"]


@requires_db
@pytest.mark.asyncio
async def test_the_endpoint_never_returns_the_token(db_ready):
    from athera_api.services.password_reset import reset_rate_limits

    reset_rate_limits()
    email = f"pr-{uuid.uuid4().hex[:10]}@fixtures.athera"
    async with await _client() as client:
        await _register(client, email, "correct-horse-battery")
        r = await client.post("/api/v1/auth/forgot-password", json={"email": email})

    body = r.text
    stored = await _live_token_hash_for(email)
    assert stored is not None, "لم يُنشأ رمز لحسابٍ قائم"
    assert stored not in body
    assert "token" not in r.json(), "الرمز يعود في الاستجابة"


@requires_db
@pytest.mark.asyncio
async def test_a_valid_token_resets_the_password_and_cannot_be_reused(db_ready):
    from athera_api.services import password_reset as pr

    pr.reset_rate_limits()
    email = f"pr-{uuid.uuid4().hex[:10]}@fixtures.athera"
    old, new = "correct-horse-battery", "battery-staple-correct-9"

    async with await _client() as client:
        pair = await _register(client, email, old)
        # رمزٌ خام يُولَّد هنا ويُزرع بتجزئته — كما يفعل مسار البريد تمامًا.
        raw, token_hash = pr.new_token()
        await _seed_token(email, token_hash, pr.expiry(dt.datetime.now(dt.UTC)))

        first = await client.post("/api/v1/auth/reset-password",
                                  json={"token": raw, "new_password": new})
        assert first.status_code == 204, first.text

        # **مرّة واحدة.**
        again = await client.post("/api/v1/auth/reset-password",
                                  json={"token": raw, "new_password": "third-password-x"})
        assert again.status_code == 400
        assert again.json()["error"]["code"] == "auth.reset_token_invalid"

        # الكلمة القديمة سقطت، والجديدة تعمل.
        assert (await client.post("/api/v1/auth/login",
                                  json={"email": email, "password": old})).status_code == 401
        ok = await client.post("/api/v1/auth/login",
                               json={"email": email, "password": new})
        assert ok.status_code == 200, ok.text

        # وكل رمز تجديد سابق أُبطل.
        stale = await client.post("/api/v1/auth/refresh",
                                  json={"refresh_token": pair["refresh_token"]})
        assert stale.status_code == 401, "رمز تجديدٍ نجا من إعادة الضبط"


async def _seed_token(user_email: str, token_hash: str, expires_at,
                      created_at=None) -> None:
    from sqlalchemy import select

    from athera_api.db import system_session
    from athera_api.models.identity import PasswordResetToken, User

    async with system_session() as session:
        user = (await session.execute(
            select(User).where(User.email == user_email))).scalar_one()
        row = PasswordResetToken(user_id=user.id, token_hash=token_hash,
                                 expires_at=expires_at)
        if created_at is not None:
            # القيد يشترط `expires_at > created_at`؛ فرمزٌ منتهٍ يُصنع
            # بإنشاءٍ أقدم لا بانتهاءٍ يسبق إنشاءه.
            row.created_at = created_at
        session.add(row)


@requires_db
@pytest.mark.asyncio
async def test_an_expired_token_is_refused(db_ready):
    from athera_api.services import password_reset as pr

    pr.reset_rate_limits()
    email = f"pr-{uuid.uuid4().hex[:10]}@fixtures.athera"
    async with await _client() as client:
        await _register(client, email, "correct-horse-battery")
        raw, token_hash = pr.new_token()
        now = dt.datetime.now(dt.UTC)
        await _seed_token(email, token_hash,
                          expires_at=now - dt.timedelta(minutes=1),
                          created_at=now - dt.timedelta(minutes=30))

        r = await client.post("/api/v1/auth/reset-password",
                              json={"token": raw, "new_password": "battery-staple-9x"})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "auth.reset_token_invalid"


@requires_db
@pytest.mark.asyncio
async def test_a_malformed_or_unknown_token_is_refused(db_ready):
    async with await _client() as client:
        for token in ("", "not-a-token", "x" * 200):
            r = await client.post("/api/v1/auth/reset-password",
                                  json={"token": token,
                                        "new_password": "battery-staple-9x"})
            assert r.status_code in (400, 422), token


@requires_db
@pytest.mark.asyncio
async def test_a_second_request_invalidates_the_earlier_token(db_ready):
    """رابطٌ قديم في بريدٍ مسروق لا يبقى صالحًا بعد أن طلب صاحبه غيره."""
    from athera_api.services import password_reset as pr

    pr.reset_rate_limits()
    email = f"pr-{uuid.uuid4().hex[:10]}@fixtures.athera"
    async with await _client() as client:
        await _register(client, email, "correct-horse-battery")
        await client.post("/api/v1/auth/forgot-password", json={"email": email})
        first_hash = await _live_token_hash_for(email)
        await client.post("/api/v1/auth/forgot-password", json={"email": email})
        second_hash = await _live_token_hash_for(email)

    assert first_hash and second_hash and first_hash != second_hash
    # والأول لم يعد حيًّا.
    from sqlalchemy import select

    from athera_api.db import system_session
    from athera_api.models.identity import PasswordResetToken

    async with system_session() as session:
        row = (await session.execute(select(PasswordResetToken).where(
            PasswordResetToken.token_hash == first_hash))).scalar_one()
        assert row.invalidated_at is not None, "الرمز الأول ما زال حيًّا"


@requires_db
@pytest.mark.asyncio
async def test_reset_uses_the_central_policy_and_needs_no_session(db_ready):
    from athera_api.services import password_reset as pr

    pr.reset_rate_limits()
    email = f"pr-{uuid.uuid4().hex[:10]}@fixtures.athera"
    async with await _client() as client:
        await _register(client, email, "correct-horse-battery")
        raw, token_hash = pr.new_token()
        await _seed_token(email, token_hash, pr.expiry(dt.datetime.now(dt.UTC)))

        # **بلا ترويسة مصادقة** — الاستعادة لمن لا يستطيع الدخول.
        weak = await client.post("/api/v1/auth/reset-password",
                                 json={"token": raw, "new_password": "short"})
        assert weak.status_code == 422
        assert weak.json()["error"]["code"] == "auth.password_too_short"


@requires_db
@pytest.mark.asyncio
async def test_reset_preserves_mfa_roles_and_memberships(db_ready):
    """**استعادةُ كلمةٍ تستعيد عامل معرفةٍ واحدًا، ولا تُسقط عاملًا ثانيًا.**

    ولو أسقطت التحقق بخطوتين لصارت طريقًا إلى تجاوزه: يسرق المهاجم البريد
    فيتجاوز العاملين معًا.
    """
    from sqlalchemy import func, select

    from athera_api.db import system_session
    from athera_api.models.identity import Membership, MfaFactor, User
    from athera_api.services import password_reset as pr

    pr.reset_rate_limits()
    email = f"pr-{uuid.uuid4().hex[:10]}@fixtures.athera"
    async with await _client() as client:
        pair = await _register(client, email, "correct-horse-battery")
        auth = {"authorization": f"Bearer {pair['access_token']}"}
        enrolled = await client.post("/api/v1/auth/mfa/enroll", headers=auth)
        assert enrolled.status_code == 200, enrolled.text

        async with system_session() as session:
            user = (await session.execute(
                select(User).where(User.email == email))).scalar_one()
            before_mfa = (await session.execute(select(func.count(MfaFactor.id)).where(
                MfaFactor.user_id == user.id))).scalar_one()
            before_members = (await session.execute(
                select(Membership.tenant_id, Membership.role_id)
                .where(Membership.user_id == user.id))).all()

        raw, token_hash = pr.new_token()
        await _seed_token(email, token_hash, pr.expiry(dt.datetime.now(dt.UTC)))
        r = await client.post("/api/v1/auth/reset-password",
                              json={"token": raw, "new_password": "battery-staple-9x"})
        assert r.status_code == 204, r.text

        async with system_session() as session:
            after_mfa = (await session.execute(select(func.count(MfaFactor.id)).where(
                MfaFactor.user_id == user.id))).scalar_one()
            after_members = (await session.execute(
                select(Membership.tenant_id, Membership.role_id)
                .where(Membership.user_id == user.id))).all()

    assert after_mfa == before_mfa, "إعادة الضبط مسّت التحقق بخطوتين"
    assert sorted(map(str, after_members)) == sorted(map(str, before_members)), (
        "إعادة الضبط غيّرت الأدوار أو العضويات")


@requires_db
@pytest.mark.asyncio
async def test_no_reset_secret_reaches_the_audit_payload(db_ready):
    from sqlalchemy import select

    from athera_api.db import system_session
    from athera_api.models.audit import AuditEvent
    from athera_api.services import password_reset as pr

    pr.reset_rate_limits()
    email = f"pr-{uuid.uuid4().hex[:10]}@fixtures.athera"
    async with await _client() as client:
        await _register(client, email, "correct-horse-battery")
        raw, token_hash = pr.new_token()
        await _seed_token(email, token_hash, pr.expiry(dt.datetime.now(dt.UTC)))
        assert (await client.post("/api/v1/auth/reset-password",
                                  json={"token": raw,
                                        "new_password": "battery-staple-9x"})).status_code == 204

    async with system_session() as session:
        rows = (await session.execute(
            select(AuditEvent).where(
                AuditEvent.action == "auth.password_reset_completed")
            .order_by(AuditEvent.occurred_at.desc()).limit(5))).scalars().all()
    blob = " ".join(str(r.state_after) + str(r.state_before) for r in rows)
    assert raw not in blob and token_hash not in blob
    assert "battery-staple-9x" not in blob
