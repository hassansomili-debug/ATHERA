"""عقود المصادقة | Auth contracts."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, description="12 حرفًا على الأقل | minimum 12 characters")
    full_name_ar: str = Field(min_length=2, max_length=255)
    full_name_en: str | None = Field(default=None, max_length=255)
    preferred_locale: str = Field(default="ar", pattern="^(ar|en)$")
    tenant_slug: str | None = None
    tenant_name_ar: str | None = None
    tenant_name_en: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_slug: str | None = None
    totp_code: str | None = Field(default=None, min_length=6, max_length=6)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    mfa_required: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """تغيير كلمة المرور — **بالكلمة الحالية، لا بغيرها**.

    ولا يوجد مسار إداريّ يتجاوزها: بابٌ خلفيّ للإدارة يُلغي معنى الكلمة
    نفسها، ويجعل كل حسابٍ مفتوحًا لمن يملك دورًا.

    والطول الأدنى يُفرض في الخدمة من `security.password_policy_error` —
    موضعٌ واحد يشترك فيه التسجيل والتغيير، فلا تفترق سياستان.
    """

    current_password: str
    new_password: str


class MfaEnrollResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MfaVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class MeResponse(BaseModel):
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    email: EmailStr
    full_name: str
    full_name_ar: str
    full_name_en: str | None
    preferred_locale: str
    roles: list[str]
    mfa_enabled: bool
