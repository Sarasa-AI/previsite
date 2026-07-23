import logging
import re

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import Token, UserLogin, UserRegister, UserResponse
from app.auth.security import create_access_token, get_password_hash, verify_password
from app.core.config import settings
from app.db.database import get_db
from app.models.user import User, UserRole
from app.services.audit_service import record_audit
from app.utils.national_id import validate_iranian_national_id

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _internal_email(national_id: str) -> str:
    return f"patient_{national_id}@patient.local"


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


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new patient account keyed by national ID."""
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
    """Authenticate a user and return an access token."""
    login_id = user_data.national_id.strip()
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not hashed:
        logger.warning(
            "Login rejected: missing hashed_password for user_id=%s login_id=%r",
            user.id,
            user.full_name,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not verify_password(user_data.password, hashed):
        logger.warning(
            "Login rejected: password verification failed for user_id=%s login_id=%r",
            user.id,
            user.full_name,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=access_token_expires,
    )

    client_ip = request.client.host if request.client else None
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
