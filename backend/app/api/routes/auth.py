import logging
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import timedelta

from app.db.database import get_db
from app.models.user import User, UserRole
from app.auth.schemas import UserRegister, UserLogin, Token, UserResponse
from app.auth.security import get_password_hash, verify_password, create_access_token
from app.core.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)

DOCTOR_LOGIN_USERNAME = "bagherzade"
DOCTOR_LOGIN_PASSWORD = "0808"


def _internal_email(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_") or "user"
    return f"{slug}@patient.local"


def _find_user_by_login_name(db: Session, name: str) -> User | None:
    trimmed = name.strip()
    normalized = trimmed.lower()

    user = (
        db.query(User)
        .filter(func.lower(User.full_name) == normalized)
        .first()
    )
    if user:
        return user

    user = (
        db.query(User)
        .filter(func.lower(User.email) == normalized)
        .first()
    )
    if user:
        return user

    internal_email = _internal_email(trimmed)
    return db.query(User).filter(func.lower(User.email) == internal_email.lower()).first()


@router.post("/register", response_model=UserResponse)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user account for the MVP flow."""
    name = user_data.name.strip()
    existing_user = (
        db.query(User)
        .filter(func.lower(User.full_name) == name.lower())
        .first()
    )
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Name already registered"
        )

    internal_email = _internal_email(name)
    if db.query(User).filter(User.email == internal_email).first():
        raise HTTPException(
            status_code=400,
            detail="Name already registered"
        )

    hashed_password = get_password_hash(user_data.password)

    user = User(
        email=internal_email,
        full_name=name,
        hashed_password=hashed_password,
        role=user_data.role,
        is_active=True
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=Token)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """Authenticate a user and return an access token."""
    name = user_data.name.strip()
    user = _find_user_by_login_name(db, name)

    if user:
        logger.info(
            "Login lookup succeeded name=%r user_id=%s stored_full_name=%r email=%r role=%s",
            name,
            user.id,
            user.full_name,
            user.email,
            user.role.value,
        )
    else:
        logger.info("Login lookup failed: no user found for name=%r", name)

    if (
        name.lower() == DOCTOR_LOGIN_USERNAME
        and user_data.password == DOCTOR_LOGIN_PASSWORD
        and (not user or user.role != UserRole.DOCTOR)
    ):
        user = db.query(User).filter(User.email == f"{DOCTOR_LOGIN_USERNAME}@doctor.com").first()
        if not user:
            user = User(
                email=f"{DOCTOR_LOGIN_USERNAME}@doctor.com",
                full_name=DOCTOR_LOGIN_USERNAME,
                hashed_password=get_password_hash(DOCTOR_LOGIN_PASSWORD),
                role=UserRole.DOCTOR,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(
                "Login auto-provisioned doctor account user_id=%s email=%r",
                user.id,
                user.email,
            )

    hashed = getattr(user, "hashed_password", None) if user else None
    if not user:
        logger.warning("Login rejected: user not found for name=%r", name)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid name or password",
        )
    if not hashed:
        logger.warning(
            "Login rejected: missing hashed_password for user_id=%s name=%r",
            user.id,
            user.full_name,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid name or password",
        )
    if not verify_password(user_data.password, hashed):
        logger.warning(
            "Login rejected: password verification failed for user_id=%s name=%r",
            user.id,
            user.full_name,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid name or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    access_token_expires = timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=access_token_expires,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
