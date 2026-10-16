from typing import Literal

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.rate_limit import client_ip, enforce, limiter
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    CodeRequest,
    DeleteAccountRequest,
    DisableTwoFactorRequest,
    EmailRequest,
    LoginResponse,
    MessageResponse,
    MfaLoginRequest,
    RecoveryCodes,
    RefreshRequest,
    ResetPasswordRequest,
    SessionRead,
    Token,
    TokenRequest,
    TwoFactorSetup,
    TwoFactorStatus,
    UserLogin,
    UserRead,
    UserRegister,
)
from app.services.auth import account, mfa, protection, sessions, tokens
from app.services.auth import service as auth_service
from app.services.workspaces.service import create_personal_workspace

router = APIRouter(prefix="/auth", tags=["auth"])


def _access_token_for(user: User) -> Token:
    return Token(
        access_token=create_access_token(user.id, token_version=user.token_version),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


SESSION_HINT_COOKIE = "lg_session"


def _set_refresh_cookie(response: Response, raw: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=raw,
        max_age=settings.jwt_refresh_token_expire_days * 86_400,
        path=settings.refresh_cookie_path,
        domain=settings.refresh_cookie_domain,
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.refresh_cookie_samesite,  # type: ignore[arg-type]
    )
    # A non-secret hint so the web app's middleware can send signed-out visitors to /login
    # (the refresh cookie itself is only sent to /api/auth).
    response.set_cookie(
        key=SESSION_HINT_COOKIE,
        value="1",
        max_age=settings.jwt_refresh_token_expire_days * 86_400,
        path="/",
        domain=settings.refresh_cookie_domain,
        secure=settings.cookie_secure,
        httponly=False,
        samesite="lax",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_HINT_COOKIE,
        path="/",
        domain=settings.refresh_cookie_domain,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=settings.refresh_cookie_path,
        domain=settings.refresh_cookie_domain,
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.refresh_cookie_samesite,  # type: ignore[arg-type]
    )


def _refresh_token_from(request: Request, payload: RefreshRequest | None) -> str:
    cookie = request.cookies.get(settings.refresh_cookie_name)
    if cookie:
        # Cookie-based refresh must come from our own frontend code, not a cross-site form.
        if request.headers.get("x-requested-with") is None:
            raise PermissionDeniedError("Missing X-Requested-With header")
        return cookie
    if payload and payload.refresh_token:
        return payload.refresh_token
    raise AuthenticationError("Session expired. Please sign in again.")


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
def register(request: Request, payload: UserRegister, db: Session = Depends(get_db)) -> User:
    protection.verify_captcha(payload.captcha_token, remote_ip=client_ip(request))
    protection.ensure_password_not_breached(payload.password)
    user = auth_service.register_user(
        db,
        name=payload.name,
        email=str(payload.email),
        password=payload.password,
    )
    create_personal_workspace(db, user)
    return user


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
def login(
    request: Request,
    response: Response,
    payload: UserLogin,
    delivery: Literal["cookie", "body"] = "cookie",
    db: Session = Depends(get_db),
) -> LoginResponse:
    enforce("30/hour", "login-email", str(payload.email).lower())
    if auth_service.needs_captcha(db, str(payload.email)):
        protection.verify_captcha(payload.captcha_token, remote_ip=client_ip(request))
    user = auth_service.authenticate(db, email=str(payload.email), password=payload.password)
    from app.services.sso.service import password_login_blocked

    blocked = password_login_blocked(db, user)
    if blocked is not None:
        raise AuthenticationError(
            f"Your organisation requires signing in with {blocked.display_name}.",
            extra={"code": "sso_required"},
        )
    if mfa.is_enabled(user):
        return LoginResponse(mfa_required=True, mfa_token=mfa.issue_mfa_token(user))
    return _complete_login(request, response, db, user, delivery)


def _complete_login(
    request: Request,
    response: Response,
    db: Session,
    user: User,
    delivery: str,
) -> LoginResponse:
    raw, _ = tokens.issue_refresh_token(
        db,
        user,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    access = _access_token_for(user)
    if delivery == "body":
        # For non-browser clients (CLI, mobile). Browsers get an httpOnly cookie instead.
        return LoginResponse(**access.model_dump(), refresh_token=raw)
    _set_refresh_cookie(response, raw)
    return LoginResponse(**access.model_dump())


@router.post("/login/2fa", response_model=LoginResponse)
@limiter.limit("10/minute")
def login_two_factor(
    request: Request,
    response: Response,
    payload: MfaLoginRequest,
    delivery: Literal["cookie", "body"] = "cookie",
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Second sign-in step: a code from the authenticator app, or a recovery code."""
    user = mfa.read_mfa_token(db, payload.mfa_token)
    enforce("10/15minutes", "mfa-login", str(user.id))
    if not mfa.verify_code(db, user, payload.code):
        raise AuthenticationError("That code isn't right. Try the latest code from your app.")
    return _complete_login(request, response, db, user, delivery)


@router.post("/refresh", response_model=LoginResponse)
@limiter.limit("60/minute")
def refresh(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    db: Session = Depends(get_db),
) -> LoginResponse:
    raw = _refresh_token_from(request, payload)
    try:
        user, new_raw = tokens.rotate_refresh_token(
            db,
            raw,
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except AuthenticationError:
        _clear_refresh_cookie(response)
        raise
    access = _access_token_for(user)
    if request.cookies.get(settings.refresh_cookie_name):
        _set_refresh_cookie(response, new_raw)
        return LoginResponse(**access.model_dump())
    return LoginResponse(**access.model_dump(), refresh_token=new_raw)


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    db: Session = Depends(get_db),
) -> MessageResponse:
    raw = request.cookies.get(settings.refresh_cookie_name) or (
        payload.refresh_token if payload else None
    )
    if raw:
        tokens.revoke_refresh_token(db, raw)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Signed out")


@router.post("/logout-all", response_model=MessageResponse)
def logout_all(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    auth_service.logout_everywhere(db, current_user)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Signed out on all devices")


@router.get("/me", response_model=UserRead)
def me(request: Request, current_user: User = Depends(get_current_user)) -> UserRead:
    user = UserRead.model_validate(current_user)
    user.impersonation = getattr(request.state, "impersonation", None)
    return user


@router.post("/verify-email", response_model=UserRead)
@limiter.limit("20/hour")
def verify_email(request: Request, payload: TokenRequest, db: Session = Depends(get_db)) -> User:
    return auth_service.verify_email(db, payload.token)


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    enforce("3/hour", "resend-verification", str(current_user.id))
    auth_service.send_verification(db, current_user)
    return MessageResponse(message="If your email isn't confirmed yet, we've sent a new link.")


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/hour")
def forgot_password(
    request: Request,
    payload: EmailRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    protection.verify_captcha(payload.captcha_token, remote_ip=client_ip(request))
    enforce("3/hour", "forgot-password", str(payload.email).lower())
    auth_service.request_password_reset(db, str(payload.email))
    return MessageResponse(
        message="If an account exists for that email, a reset link is on its way."
    )


@router.post("/reset-password", response_model=MessageResponse)
@limiter.limit("10/hour")
def reset_password(
    request: Request,
    response: Response,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    protection.ensure_password_not_breached(payload.password)
    auth_service.reset_password(db, payload.token, payload.password)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Password updated. Please sign in with your new password.")


@router.post("/change-password", response_model=LoginResponse)
@limiter.limit("10/hour")
def change_password(
    request: Request,
    response: Response,
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Change the password and sign out every other device. This device stays signed in."""
    protection.ensure_password_not_breached(payload.new_password)
    auth_service.change_password(
        db, current_user, current=payload.current_password, new=payload.new_password
    )
    return _complete_login(request, response, db, current_user, "cookie")


# --- Two-factor authentication -----------------------------------------------------------------


@router.get("/2fa", response_model=TwoFactorStatus)
def two_factor_status(current_user: User = Depends(get_current_user)) -> TwoFactorStatus:
    return TwoFactorStatus(
        enabled=mfa.is_enabled(current_user),
        recovery_codes_left=mfa.recovery_codes_left(current_user),
    )


@router.post("/2fa/setup", response_model=TwoFactorSetup)
def two_factor_setup(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TwoFactorSetup:
    return TwoFactorSetup(**mfa.begin_setup(db, current_user))


@router.post("/2fa/enable", response_model=RecoveryCodes)
@limiter.limit("10/minute")
def two_factor_enable(
    request: Request,
    payload: CodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecoveryCodes:
    return RecoveryCodes(recovery_codes=mfa.enable(db, current_user, payload.code))


@router.post("/2fa/disable", response_model=MessageResponse)
@limiter.limit("10/minute")
def two_factor_disable(
    request: Request,
    payload: DisableTwoFactorRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    mfa.disable(db, current_user, password=payload.password, code=payload.code)
    return MessageResponse(message="Two-factor authentication is off")


@router.post("/2fa/recovery-codes", response_model=RecoveryCodes)
@limiter.limit("5/hour")
def two_factor_recovery_codes(
    request: Request,
    payload: CodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecoveryCodes:
    return RecoveryCodes(
        recovery_codes=mfa.regenerate_recovery_codes(db, current_user, payload.code)
    )


# --- Sessions and account ----------------------------------------------------------------------


@router.get("/sessions", response_model=list[SessionRead])
def list_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SessionRead]:
    current = sessions.family_of(db, request.cookies.get(settings.refresh_cookie_name))
    return [
        SessionRead(**vars(item))
        for item in sessions.list_sessions(db, current_user.id, current_family=current)
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    sessions.revoke_session(db, current_user.id, session_id)


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/hour")
def delete_my_account(
    request: Request,
    response: Response,
    payload: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Permanently delete the signed-in account (and workspaces only they belong to)."""
    if not verify_password(payload.password, current_user.hashed_password):
        raise AuthenticationError("Password is incorrect")
    if mfa.is_enabled(current_user) and not (
        payload.code and mfa.verify_code(db, current_user, payload.code)
    ):
        raise AuthenticationError("Enter a current two-factor code")
    account.delete_account(db, current_user)
    _clear_refresh_cookie(response)
