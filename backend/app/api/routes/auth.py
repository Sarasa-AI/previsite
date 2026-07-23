import logging

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import Token, UserLogin, UserRegister, UserResponse
from app.auth.security import create_access_token, get_password_hash, verify_password
from app.core.config import settings
from app.core.rate_limiter import (
    login_attempt_key,
    raise_login_lockout,
    rate_limiter,
    register_attempt_key,
)
from app.db.database import get_db
from app.models.user import User
from app.services.audit_service import record_audit
from app.utils.national_id import validate_iranian_national_id

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _internal_email(national_id: str) -> str:
    return f"patient_{national_id}@patient.local"


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _find_user_by_login(db: AsyncSession, login_id: str) -> User | None:
    trimmed = login_id.strip()
    normalized = trimmed.lower()

    if validate_iranian_national_id(trimmed):
        result = await db.execute(select(User).where(User.national_id == trimmed))
        user = result.scalar_one_or_none()
        if user:
            return user

    result = await db.execute(
        select(User).where(func.lower(User.full_name) == normalized)
    )
    user = result.scalar_one_or_none()
    if user:
        return user

    result = await db.execute(
        select(User).where(func.lower(User.email) == normalized)
    )
    user = result.scalar_one_or_none()
    if user:
        return user

    internal_email = _internal_email(trimmed)
    result = await db.execute(
        select(User).where(func.lower(User.email) == internal_email.lower())
    )
    return result.scalar_one_or_none()


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
        resource_id=login_id,
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
            resource_id=login_id,
            ip_address=client_ip,
        )
        raise_login_lockout(key)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
    )


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserRegister,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a new patient account keyed by national ID."""
    client_ip = _client_ip(request)
    reg_key = register_attempt_key(client_ip)
    if not rate_limiter.allow(
        key=reg_key,
        limit=settings.auth_register_max_requests,
        window_seconds=settings.auth_register_window_seconds,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Too many registration attempts from this IP. "
                "Please try again later."
            ),
        )

    national_id = user_data.national_id.strip()

    result = await db.execute(select(User).where(User.national_id == national_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="USER_EXISTS")

    internal_email = _internal_email(national_id)
    result = await db.execute(select(User).where(User.email == internal_email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="USER_EXISTS")

    display_name = (user_data.display_name or f"بیمار {national_id[-4:]}").strip()
    hashed_password = get_password_hash(user_data.password)

    user = User(
        email=internal_email,
        full_name=display_name,
        national_id=national_id,
        hashed_password=hashed_password,
        role=user_data.role,
        is_active=True,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


@router.post("/login", response_model=Token)
async def login(
    user_data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate a patient or doctor and return an access token.

    Note: there is no separate /api/auth/doctor-login — doctors use this same
    endpoint with their username (full_name/email). Brute-force protection
    applies to all roles.
    """
    login_id = user_data.national_id.strip()
    client_ip = _client_ip(request)
    key = login_attempt_key(client_ip, login_id)

    if rate_limiter.is_locked(key):
        raise_login_lockout(key)

    user = await _find_user_by_login(db, login_id)

    if user:
        logger.info(
            "Login lookup succeeded login_id=%r user_id=%s stored_full_name=%r email=%r role=%s",
            login_id,
            user.id,
            user.full_name,
            user.email,
            user.role.value,
        )
    else:
        logger.info("Login lookup failed: no user found for login_id=%r", login_id)

    hashed = getattr(user, "hashed_password", None) if user else None
    if not user:
        logger.warning("Login rejected: user not found for login_id=%r", login_id)
        await _reject_login_failure(db, request=request, login_id=login_id, user_id=None)

    if not hashed:
        logger.warning(
            "Login rejected: missing hashed_password for user_id=%s login_id=%r",
            user.id,
            user.full_name,
        )
        await _reject_login_failure(
            db, request=request, login_id=login_id, user_id=user.id
        )

    if not verify_password(user_data.password, hashed):
        logger.warning(
            "Login rejected: password verification failed for user_id=%s login_id=%r",
            user.id,
            user.full_name,
        )
        await _reject_login_failure(
            db, request=request, login_id=login_id, user_id=user.id
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    rate_limiter.clear(key)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=access_token_expires,
    )

    await record_audit(
        db,
        action="login",
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        ip_address=client_ip,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }
