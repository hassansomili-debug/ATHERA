"""المصادقة | Authentication primitives (§36.1).

Argon2id لكلمات المرور، JWT قصير العمر للوصول، refresh token دوّار مخزّن
مجزّأً وقابلًا للإبطال، وTOTP للتحقق بخطوتين.
"""
import datetime as dt
import hashlib
import secrets
import uuid

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from typing import Final

from .config import get_settings

_ph = PasswordHasher()
_settings = get_settings()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        _ph.verify(password_hash, password)
        return True
    except VerifyMismatchError:
        return False


def needs_rehash(password_hash: str) -> bool:
    return _ph.check_needs_rehash(password_hash)


def issue_access_token(user_id: uuid.UUID, tenant_id: uuid.UUID, roles: list[str],
                       mfa_satisfied: bool) -> str:
    now = dt.datetime.now(dt.UTC)
    payload = {
        "sub": str(user_id),
        "tid": str(tenant_id),
        "roles": roles,
        "mfa": mfa_satisfied,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(seconds=_settings.access_token_ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, _settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, _settings.jwt_secret, algorithms=["HS256"])


def new_refresh_token() -> tuple[str, str]:
    """يعيد (السر الخام، التجزئة المخزّنة) — الخام لا يُحفظ أبدًا."""
    raw = secrets.token_urlsafe(48)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="ATHERA")


def verify_totp(secret: str, code: str) -> bool:
    # نافذة ±30 ثانية لاستيعاب انحراف الساعة.
    return pyotp.TOTP(secret).verify(code, valid_window=1)

# ══════════ سياسة كلمة المرور — **موضعٌ واحد** ══════════
#
# وكانت مكتوبةً في `RegisterRequest.password` وحدها (`min_length=12`). فأيّ
# مسارٍ ثانٍ — تغييرُ كلمة، أو إنشاءُ حسابٍ من مكانٍ آخر — يكتب سياسته من
# جديد، فتفترق السياستان ولا يعلم أحد أيّهما السارية. وهو الخطأ المتكرر
# نفسه: قاعدةٌ تُكتب بجانب سجلّها بدل أن تُشتقّ منه.

PASSWORD_MIN_LENGTH: Final = 12
PASSWORD_MAX_LENGTH: Final = 1024


def password_policy_error(password: str) -> str | None:
    """مفتاحُ الرفض، أو `None` إن قُبلت.

    ولا يُعاد نصّ الكلمة ولا جزءٌ منها في أي حال — الرسالة مفتاحٌ يُترجَم.
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        return "auth.password_too_short"
    # حدٌّ أعلى يمنع استنزاف المُجزِّئ بمدخلٍ ضخم.
    if len(password) > PASSWORD_MAX_LENGTH:
        return "auth.password_too_long"
    if password.strip() == "":
        return "auth.password_too_short"
    return None
