import logging
import time
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import (
    CurrentUserResponse,
    MfaSetupVerifyRequest,
    MfaSetupVerifyResponse,
    MfaVerifyRequest,
    OtpRequestBody,
    OtpRequestResponse,
    OtpVerifyBody,
    RefreshRequest,
    Token,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.auth.security import create_access_token, verify_password
from app.core.config import settings
from app.core.rate_limiter import (
    login_attempt_key,
    mfa_verify_rate_limit,
    raise_login_lockout,
    rate_limiter,
)
from app.db.database import get_db
from app.models.user import User, UserRole
from app.services import mfa_service
from app.services import otp_service
from app.services import refresh_token_service
from app.services.audit_service import record_audit
from app.utils.national_id import validate_iranian_national_id

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _find_privileged_by_email(db: AsyncSession, email: str) -> User | None:
    normalized = email.strip().lower()
    result = await db.execute(
        select(User).where(func.lower(User.email) == normalized)
    )
    user = result.scalar_one_or_none()
    if user and user.role in (UserRole.DOCTOR, UserRole.ADMIN):
        return user
    return None


async def _find_legacy_patient_by_national_id(
    db: AsyncSession, national_id: str
) -> User | None:
    trimmed = national_id.strip()
    if not validate_iranian_national_id(trimmed):
        return None
    result = await db.execute(select(User).where(User.national_id == trimmed))
    user = result.scalar_one_or_none()
    if user and user.role == UserRole.PATIENT:
        return user
    return None


async def _reject_login_failure(
    db: AsyncSession,
    *,
    request: Request,
    login_id: str,
    user_id: int | None,
    detail: str = "Invalid credentials",
) -> None:
    client_ip = _client_ip(request)
    key = login_attempt_key(client_ip, login_id)

    await record_audit(
        db,
        action="login_failed",
        user_id=user_id,
        resource_type="user",
        resource_id=login_id[:64],
        ip_address=client_ip,
    )

    _count, newly_locked = rate_limiter.record_failure(
        key,
        max_failures=settings.auth_login_max_failures,
        window_seconds=settings.auth_login_window_seconds,
        lockout_seconds=settings.auth_login_lockout_seconds,
    )
    if newly_locked:
        await record_audit(
            db,
            action="login_lockout",
            user_id=user_id,
            resource_type="user",
            resource_id=login_id[:64],
            ip_address=client_ip,
        )
        raise_login_lockout(key)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
    )


def _token_lifetime_seconds() -> int:
    return int(settings.ACCESS_TOKEN_EXPIRE_MINUTES) * 60


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _issue_access_token(user: User) -> dict:
    expires_in = _token_lifetime_seconds()
    access_token_expires = timedelta(seconds=expires_in)
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=access_token_expires,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
    }


async def _issue_token_pair(
    db: AsyncSession,
    user: User,
    request: Request,
) -> dict:
    """Access JWT + opaque refresh token for BFF httpOnly cookies."""
    payload = _issue_access_token(user)
    raw_refresh, refresh_expires_in = await refresh_token_service.issue_refresh_token(
        db,
        user_id=user.id,
        user_agent=_user_agent(request),
        ip=_client_ip(request),
    )
    payload["refresh_token"] = raw_refresh
    payload["refresh_expires_in"] = refresh_expires_in
    return payload


def _raise_otp_error(exc: otp_service.OtpError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.code)


@router.post("/otp/request", response_model=OtpRequestResponse)
async def otp_request(
    body: OtpRequestBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Request an OTP for patient login/register/phone-link (enumeration-safe)."""
    # Constant-ish timing: always sleep a tiny amount on the hot path.
    started = time.perf_counter()
    try:
        result = await otp_service.request_otp(
            db,
            raw_phone=body.phone,
            ip=_client_ip(request),
            link_token=body.link_token,
        )
    except otp_service.OtpError as exc:
        _raise_otp_error(exc)
    elapsed = time.perf_counter() - started
    if elapsed < 0.05:
        time.sleep(0.05 - elapsed)
    return result


@router.post("/otp/verify", response_model=Token)
async def otp_verify(
    body: OtpVerifyBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Verify OTP; create patient on first success or log in / link phone."""
    started = time.perf_counter()
    try:
        user = await otp_service.verify_otp(
            db,
            raw_phone=body.phone,
            code=body.code,
            ip=_client_ip(request),
            link_token=body.link_token,
        )
    except otp_service.OtpError as exc:
        _raise_otp_error(exc)

    # Role is always patient for OTP paths; refuse if somehow not.
    if user.role != UserRole.PATIENT:
        raise HTTPException(status_code=401, detail="INVALID_OTP")

    token_payload = await _issue_token_pair(db, user, request)
    elapsed = time.perf_counter() - started
    if elapsed < 0.05:
        time.sleep(0.05 - elapsed)
    return token_payload


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserRegister,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Password self-registration is disabled — use phone OTP instead."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="REGISTER_DISABLED",
    )


@router.post("/login", response_model=Token)
async def login(
    user_data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate doctor/admin by email, or legacy patient by national ID.

    Full-name login is removed for all roles. Patients without a linked phone
    who use legacy password login receive PHONE_LINK_REQUIRED (no session).
    """
    email = (user_data.email or "").strip()
    national_id = (user_data.national_id or "").strip()
    client_ip = _client_ip(request)

    # Prefer email path (doctors/admins). Never resolve by full_name.
    if email:
        login_id = email.lower()
        key = login_attempt_key(client_ip, login_id)
        if rate_limiter.is_locked(key):
            raise_login_lockout(key)

        user = await _find_privileged_by_email(db, email)
        if not user:
            await _reject_login_failure(
                db, request=request, login_id=login_id, user_id=None
            )

        hashed = user.hashed_password
        if not hashed or not verify_password(user_data.password, hashed):
            await _reject_login_failure(
                db, request=request, login_id=login_id, user_id=user.id
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        rate_limiter.clear(key)
        return await _finish_privileged_login(db, user, request, client_ip)

    # Legacy patient national-ID + password (transition only).
    if not settings.legacy_patient_password_login_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="LEGACY_LOGIN_DISABLED",
        )

    login_id = national_id
    key = login_attempt_key(client_ip, login_id)
    if rate_limiter.is_locked(key):
        raise_login_lockout(key)

    user = await _find_legacy_patient_by_national_id(db, national_id)
    if not user:
        await _reject_login_failure(
            db, request=request, login_id=login_id, user_id=None
        )

    hashed = user.hashed_password
    if not hashed or not verify_password(user_data.password, hashed):
        await _reject_login_failure(
            db, request=request, login_id=login_id, user_id=user.id
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    rate_limiter.clear(key)

    if not user.phone:
        link_token = otp_service.create_phone_link_token(user_id=user.id)
        return {
            "token_type": "bearer",
            "phone_link_required": True,
            "code": "PHONE_LINK_REQUIRED",
            "link_token": link_token,
        }

    token_payload = await _issue_token_pair(db, user, request)
    await record_audit(
        db,
        action="login",
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        ip_address=client_ip,
    )
    return token_payload


async def _finish_privileged_login(
    db: AsyncSession,
    user: User,
    request: Request,
    client_ip: str | None,
) -> dict:
    if mfa_service.user_requires_mfa(user):
        if user.mfa_enabled and user.mfa_secret:
            mfa_token = mfa_service.create_mfa_challenge_token(
                user_id=user.id,
                purpose="mfa_verify",
            )
            return {
                "token_type": "bearer",
                "mfa_required": True,
                "mfa_token": mfa_token,
            }

        secret = mfa_service.generate_totp_secret()
        challenge_id = await mfa_service.create_setup_challenge(
            db, user_id=user.id, secret=secret
        )
        setup_token = mfa_service.create_mfa_challenge_token(
            user_id=user.id,
            purpose="mfa_setup",
            challenge_id=challenge_id,
        )
        otpauth_uri = mfa_service.build_otpauth_uri(
            secret=secret,
            account_name=user.full_name or user.email,
        )
        return {
            "token_type": "bearer",
            "mfa_setup_required": True,
            "setup_token": setup_token,
            "otpauth_uri": otpauth_uri,
        }

    token_payload = await _issue_token_pair(db, user, request)
    await record_audit(
        db,
        action="login",
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        ip_address=client_ip,
    )
    return token_payload


@router.post("/mfa/setup/verify", response_model=MfaSetupVerifyResponse)
async def mfa_setup_verify(
    body: MfaSetupVerifyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Complete doctor MFA enrollment after scanning QR / entering first TOTP."""
    if not mfa_service.mfa_feature_enabled():
        raise HTTPException(status_code=404, detail="MFA is disabled")

    payload = mfa_service.decode_mfa_challenge_token(
        body.setup_token, expected_purpose="mfa_setup"
    )
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired setup token")

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid setup token")

    challenge_id = payload.get("challenge_id")
    if not challenge_id or not isinstance(challenge_id, str):
        raise HTTPException(status_code=401, detail="Invalid setup token")

    secret = await mfa_service.load_setup_challenge_secret(
        db, challenge_id=challenge_id, user_id=user_id
    )
    if not secret:
        raise HTTPException(status_code=401, detail="Invalid or expired setup token")

    if not mfa_service.verify_totp(secret, body.code):
        raise HTTPException(status_code=401, detail="Invalid MFA code")

    if not await mfa_service.mark_setup_challenge_consumed(
        db, challenge_id=challenge_id, user_id=user_id
    ):
        raise HTTPException(status_code=401, detail="Invalid or expired setup token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not mfa_service.privileged_mfa_enrollment_role(user):
        raise HTTPException(status_code=401, detail="Invalid setup token")

    backup_codes = mfa_service.generate_backup_codes()
    user.mfa_secret = mfa_service.encrypt_mfa_secret_for_storage(secret)
    user.mfa_enabled = True
    user.mfa_backup_codes_hash = mfa_service.serialize_backup_hashes(backup_codes)
    await db.commit()

    await record_audit(
        db,
        action="mfa_enabled",
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        ip_address=_client_ip(request),
    )

    token_payload = await _issue_token_pair(db, user, request)
    return {
        **token_payload,
        "backup_codes": backup_codes,
    }


@router.get("/me", response_model=CurrentUserResponse)
async def current_user_me(
    current_user: User = Depends(get_current_user),
) -> CurrentUserResponse:
    """Return the authenticated user's non-sensitive identity fields."""
    return CurrentUserResponse(
        id=current_user.id,
        role=current_user.role,
        display_name=current_user.full_name,
    )


@router.post("/mfa/verify", response_model=Token)
async def mfa_verify(
    body: MfaVerifyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(mfa_verify_rate_limit),
):
    """Second-factor login for doctors with MFA already enabled."""
    if not mfa_service.mfa_feature_enabled():
        raise HTTPException(status_code=404, detail="MFA is disabled")

    payload = mfa_service.decode_mfa_challenge_token(
        body.mfa_token, expected_purpose="mfa_verify"
    )
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired MFA token")

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid MFA token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if (
        not user
        or not mfa_service.privileged_mfa_enrollment_role(user)
        or not user.mfa_enabled
        or not user.mfa_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid MFA token")

    try:
        plaintext_secret = mfa_service.decrypt_mfa_secret_from_storage(user.mfa_secret)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid MFA token")

    code = body.code.strip()
    if plaintext_secret and mfa_service.verify_totp(plaintext_secret, code):
        if mfa_service.maybe_reencrypt_legacy_mfa_secret(user):
            await db.commit()
    else:
        consumed, updated = mfa_service.consume_backup_code(
            user.mfa_backup_codes_hash, code
        )
        if not consumed:
            raise HTTPException(status_code=401, detail="Invalid MFA code")
        user.mfa_backup_codes_hash = updated
        if mfa_service.maybe_reencrypt_legacy_mfa_secret(user):
            await db.commit()
        else:
            await db.commit()

    await record_audit(
        db,
        action="login",
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        ip_address=_client_ip(request),
    )
    return await _issue_token_pair(db, user, request)


@router.post("/refresh", response_model=Token)
async def refresh_tokens(
    body: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Rotate refresh token and issue a new short-lived access JWT.

    BFF must set both cookies from the JSON response; refresh_token must
    never be exposed to browser JavaScript.
    """
    try:
        new_refresh, refresh_expires_in, user_id = (
            await refresh_token_service.rotate_refresh_token(
                db,
                raw_token=body.refresh_token,
                user_agent=_user_agent(request),
                ip=_client_ip(request),
            )
        )
    except refresh_token_service.RefreshTokenReuseError as exc:
        await record_audit(
            db,
            action=refresh_token_service.AUDIT_REFRESH_TOKEN_REUSE,
            user_id=exc.user_id,
            resource_type="refresh_token",
            resource_id="reuse",
            ip_address=_client_ip(request),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reuse detected",
        )
    except refresh_token_service.RefreshTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    payload = _issue_access_token(user)
    payload["refresh_token"] = new_refresh
    payload["refresh_expires_in"] = refresh_expires_in
    return payload


@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Revoke the current refresh-token family (if provided)."""
    raw: str | None = None
    try:
        payload = await request.json()
        if isinstance(payload, dict):
            candidate = payload.get("refresh_token")
            if isinstance(candidate, str) and candidate.strip():
                raw = candidate.strip()
    except Exception:
        raw = None

    if raw:
        await refresh_token_service.revoke_current_family_from_token(
            db, raw_token=raw
        )
        await record_audit(
            db,
            action="logout",
            user_id=None,
            resource_type="refresh_token",
            resource_id="family",
            ip_address=_client_ip(request),
        )
    return {"success": True}


@router.post("/logout-all")
async def logout_all(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke all refresh-token families for the authenticated user."""
    await refresh_token_service.revoke_all_for_user(db, user_id=current_user.id)
    await record_audit(
        db,
        action="logout_all",
        user_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
        ip_address=_client_ip(request),
    )
    return {"success": True}
