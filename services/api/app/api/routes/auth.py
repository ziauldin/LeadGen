from typing import Literal

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.rate_limit import client_ip, enforce, limiter
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import (
    EmailRequest,
    LoginResponse,
    MessageResponse,
    RefreshRequest,
    ResetPasswordRequest,
    Token,
    TokenRequest,
    UserLogin,
    UserRead,
    UserRegister,
)
from app.services.auth import service as auth_service
from app.services.auth import tokens
from app.services.provider_credentials.service import ensure_default_mock_credentials

router = APIRouter(prefix="/auth", tags=["auth"])


def _access_token_for(user: User) -> Token:
    return Token(
        access_token=create_access_token(user.id, token_version=user.token_version),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


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


def _clear_refresh_cookie(response: Response) -> None:
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
    user = auth_service.register_user(
        db,
        name=payload.name,
        email=str(payload.email),
        password=payload.password,
    )
    ensure_default_mock_credentials(db, user.id)
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
    user = auth_service.authenticate(db, email=str(payload.email), password=payload.password)
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
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


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
    auth_service.reset_password(db, payload.token, payload.password)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Password updated. Please sign in with your new password.")
