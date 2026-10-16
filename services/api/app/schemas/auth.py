from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole


class UserRegister(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    captcha_token: str | None = Field(default=None, max_length=4096)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    captcha_token: str | None = Field(default=None, max_length=4096)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth2 token type, not a secret
    expires_in: int


class RefreshRequest(BaseModel):
    """Non-browser clients may send the refresh token in the body instead of the cookie."""

    refresh_token: str | None = Field(default=None, max_length=200)


class LoginResponse(BaseModel):
    """Tokens after sign-in, or ``mfa_required`` with a short-lived ``mfa_token`` when the
    account has two-factor authentication and a code is still needed."""

    access_token: str | None = None
    token_type: str = "bearer"  # noqa: S105 - OAuth2 token type, not a secret
    expires_in: int | None = None
    refresh_token: str | None = None
    mfa_required: bool = False
    mfa_token: str | None = None


class MfaLoginRequest(BaseModel):
    mfa_token: str = Field(min_length=10, max_length=2000)
    code: str = Field(min_length=6, max_length=20)


class TwoFactorStatus(BaseModel):
    enabled: bool
    recovery_codes_left: int


class TwoFactorSetup(BaseModel):
    secret: str
    otpauth_uri: str
    qr_code: str


class CodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=20)


class DisableTwoFactorRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=6, max_length=20)


class RecoveryCodes(BaseModel):
    recovery_codes: list[str]


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class SessionRead(BaseModel):
    id: str
    signed_in_at: datetime
    last_active_at: datetime
    ip: str | None
    user_agent: str | None
    current: bool


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    code: str | None = Field(default=None, max_length=20)


class TokenRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class EmailRequest(BaseModel):
    email: EmailStr
    captcha_token: str | None = Field(default=None, max_length=4096)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: UserRole
    email_verified_at: datetime | None = None
    mfa_enabled: bool = False
    is_superuser: bool = False
    created_at: datetime
    # Set while a platform admin is viewing the app as this user.
    impersonation: dict[str, Any] | None = None
