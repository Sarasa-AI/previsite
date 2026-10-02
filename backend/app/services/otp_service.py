"""OTP challenge lifecycle — request, verify, rate limits, audit-safe phone refs."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import create_access_token, decode_access_token
from app.core.config import settings
from app.core.rate_limiter import rate_limiter
from app.models.otp_challenge import OtpChallenge
from app.models.user import User, UserRole
from app.services.audit_service import record_audit
from app.services.sms import get_sms_provider
from app.utils.phone import (
    mask_phone_for_log,
    normalize_iranian_mobile,
    phone_email_local_part,
    phone_last3,
)

logger = logging.getLogger(__name__)

PURPOSE_LOGIN = "login"
PURPOSE_REGISTER = "register"
PURPOSE_LINK_PHONE = "link_phone"
LINK_TOKEN_PURPOSE = "phone_link"
LINK_TOKEN_MINUTES = 10
OTP_TEMPLATE_KEY = "otp_login"


class OtpError(Exception):
    def __init__(self, code: str, status_code: int = 400) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(code)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_otp_code(code: str) -> str:
    key = (settings.secret_key or "").encode("utf-8")
    return hmac.new(key, code.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_otp_code(code: str, code_hash: str) -> bool:
    return hmac.compare_digest(hash_otp_code(code), code_hash)


def phone_audit_ref(phone_e164: str) -> str:
    """Last 3 digits + keyed hash — never store full phone in audit rows."""
    key = (settings.secret_key or "").encode("utf-8")
    digest = hmac.new(key, phone_e164.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
    return f"{phone_last3(phone_e164)}:{digest}"


def generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def create_phone_link_token(*, user_id: int) -> str:
    return create_access_token(
        {"sub": str(user_id), "purpose": LINK_TOKEN_PURPOSE},
        expires_delta=timedelta(minutes=LINK_TOKEN_MINUTES),
    )


def decode_phone_link_token(token: str) -> int | None:
    payload = decode_access_token(token)
    if not payload or payload.get("purpose") != LINK_TOKEN_PURPOSE:
        return None
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None


def _otp_phone_key(phone: str) -> str:
    return f"otp:phone:{phone}"


def _otp_ip_key(ip: str | None) -> str:
    return f"otp:ip:{ip or 'unknown'}"


def _otp_phone_day_key(phone: str) -> str:
    day = _now().strftime("%Y-%m-%d")
    return f"otp:phone_day:{phone}:{day}"


def _otp_cooldown_key(phone: str) -> str:
    return f"otp:cooldown:{phone}"


async def _audit(
    db: AsyncSession,
    *,
    action: str,
    phone: str,
    user_id: int | None,
    ip: str | None,
) -> None:
    await record_audit(
        db,
        action=action,
        user_id=user_id,
        resource_type="otp",
        resource_id=phone_audit_ref(phone),
        ip_address=ip,
    )


async def find_user_by_phone(db: AsyncSession, phone: str) -> User | None:
    result = await db.execute(select(User).where(User.phone == phone))
    return result.scalar_one_or_none()


def _check_request_limits(phone: str, ip: str | None) -> str | None:
    """Return an error code if rate-limited, else None."""
    if not rate_limiter.allow(
        key=_otp_phone_key(phone),
        limit=settings.otp_request_per_phone_limit,
        window_seconds=settings.otp_request_per_phone_window_seconds,
    ):
        return "OTP_RATE_LIMITED"
    if not rate_limiter.allow(
        key=_otp_ip_key(ip),
        limit=settings.otp_request_per_ip_limit,
        window_seconds=settings.otp_request_per_ip_window_seconds,
    ):
        return "OTP_RATE_LIMITED"
    if not rate_limiter.allow(
        key=_otp_phone_day_key(phone),
        limit=settings.otp_phone_daily_cap,
        window_seconds=86400,
    ):
        return "OTP_RATE_LIMITED"
    # Cooldown: allow at most 1 successful send per cooldown window.
    if not rate_limiter.allow(
        key=_otp_cooldown_key(phone),
        limit=1,
        window_seconds=settings.otp_resend_cooldown_seconds,
    ):
        return "OTP_COOLDOWN"
    return None


async def request_otp(
    db: AsyncSession,
    *,
    raw_phone: str,
    ip: str | None,
    link_token: str | None = None,
) -> dict[str, Any]:
    """Create an OTP challenge and send via SMS provider.

    Response shape is identical for known/unknown phones (enumeration-safe).
    """
    if not settings.otp_login_enabled:
        raise OtpError("OTP_DISABLED", status_code=403)

    phone = normalize_iranian_mobile(raw_phone)
    if not phone:
        raise OtpError("INVALID_PHONE", status_code=400)

    link_user_id: int | None = None
    purpose = PURPOSE_LOGIN
    if link_token:
        link_user_id = decode_phone_link_token(link_token)
        if link_user_id is None:
            raise OtpError("INVALID_LINK_TOKEN", status_code=401)
        purpose = PURPOSE_LINK_PHONE
    else:
        existing = await find_user_by_phone(db, phone)
        purpose = PURPOSE_LOGIN if existing else PURPOSE_REGISTER

    limit_code = _check_request_limits(phone, ip)
    if limit_code:
        await _audit(
            db,
            action="otp_rate_limited",
            phone=phone,
            user_id=link_user_id,
            ip=ip,
        )
        raise OtpError(limit_code, status_code=429)

    code = generate_otp_code()
    challenge = OtpChallenge(
        id=str(uuid.uuid4()),
        phone=phone,
        code_hash=hash_otp_code(code),
        purpose=purpose,
        expires_at=_now() + timedelta(seconds=settings.otp_ttl_seconds),
        attempt_count=0,
        request_ip=ip,
    )
    db.add(challenge)
    await db.commit()

    # Send after commit; never include code in logs outside TestSmsProvider.
    try:
        provider = get_sms_provider()
        provider.send(phone, OTP_TEMPLATE_KEY, {"code": code})
    except Exception:
        logger.exception(
            "SMS send failed for phone=%s (code not logged)",
            mask_phone_for_log(phone),
        )

    await _audit(
        db,
        action="otp_requested",
        phone=phone,
        user_id=link_user_id,
        ip=ip,
    )

    # Same shape regardless of account existence.
    return {
        "success": True,
        "cooldown_seconds": settings.otp_resend_cooldown_seconds,
        "expires_in": settings.otp_ttl_seconds,
    }


async def verify_otp(
    db: AsyncSession,
    *,
    raw_phone: str,
    code: str,
    ip: str | None,
    link_token: str | None = None,
) -> User:
    """Verify OTP and return the authenticated/created/linked patient user."""
    if not settings.otp_login_enabled:
        raise OtpError("OTP_DISABLED", status_code=403)

    phone = normalize_iranian_mobile(raw_phone)
    if not phone:
        raise OtpError("INVALID_PHONE", status_code=400)

    normalized_code = (code or "").strip()
    if not normalized_code.isdigit() or len(normalized_code) != 6:
        raise OtpError("INVALID_OTP", status_code=400)

    link_user_id: int | None = None
    if link_token:
        link_user_id = decode_phone_link_token(link_token)
        if link_user_id is None:
            raise OtpError("INVALID_LINK_TOKEN", status_code=401)

    result = await db.execute(
        select(OtpChallenge)
        .where(
            OtpChallenge.phone == phone,
            OtpChallenge.consumed_at.is_(None),
        )
        .order_by(OtpChallenge.created_at.desc())
        .limit(1)
    )
    challenge = result.scalar_one_or_none()

    if not challenge:
        await _audit(db, action="otp_failed", phone=phone, user_id=link_user_id, ip=ip)
        raise OtpError("INVALID_OTP", status_code=401)

    expires = challenge.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < _now():
        await _audit(db, action="otp_failed", phone=phone, user_id=link_user_id, ip=ip)
        raise OtpError("OTP_EXPIRED", status_code=401)

    if challenge.attempt_count >= settings.otp_max_attempts:
        await _audit(db, action="otp_locked", phone=phone, user_id=link_user_id, ip=ip)
        raise OtpError("OTP_LOCKED", status_code=429)

    if not verify_otp_code(normalized_code, challenge.code_hash):
        challenge.attempt_count = int(challenge.attempt_count or 0) + 1
        await db.commit()
        if challenge.attempt_count >= settings.otp_max_attempts:
            await _audit(
                db, action="otp_locked", phone=phone, user_id=link_user_id, ip=ip
            )
            raise OtpError("OTP_LOCKED", status_code=429)
        await _audit(db, action="otp_failed", phone=phone, user_id=link_user_id, ip=ip)
        raise OtpError("INVALID_OTP", status_code=401)

    challenge.consumed_at = _now()
    await db.commit()

    if link_token and link_user_id is not None:
        user = await _link_phone_to_user(db, user_id=link_user_id, phone=phone)
    else:
        user = await find_user_by_phone(db, phone)
        if user is None:
            user = await _create_patient_for_phone(db, phone=phone)
        elif user.role != UserRole.PATIENT:
            await _audit(
                db, action="otp_failed", phone=phone, user_id=user.id, ip=ip
            )
            raise OtpError("INVALID_OTP", status_code=401)

    if not user.is_active:
        raise OtpError("ACCOUNT_INACTIVE", status_code=403)

    await _audit(db, action="otp_verified", phone=phone, user_id=user.id, ip=ip)
    return user


async def _create_patient_for_phone(db: AsyncSession, *, phone: str) -> User:
    local = phone_email_local_part(phone)
    email = f"patient_{local}@patient.local"
    # Collision guard (extremely unlikely with E.164 uniqueness).
    existing = await db.execute(select(User).where(func.lower(User.email) == email.lower()))
    if existing.scalar_one_or_none():
        email = f"patient_{local}_{uuid.uuid4().hex[:8]}@patient.local"

    user = User(
        email=email,
        full_name=f"بیمار {phone_last3(phone)}",
        national_id=None,
        phone=phone,
        hashed_password=None,
        role=UserRole.PATIENT,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    from app.services.platform_identity_service import ensure_patient_profile

    await ensure_patient_profile(db, user)
    await db.commit()
    await db.refresh(user)
    return user


async def _link_phone_to_user(
    db: AsyncSession, *, user_id: int, phone: str
) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or user.role != UserRole.PATIENT:
        raise OtpError("INVALID_LINK_TOKEN", status_code=401)

    taken = await find_user_by_phone(db, phone)
    if taken and taken.id != user.id:
        raise OtpError("PHONE_IN_USE", status_code=409)

    user.phone = phone
    await db.commit()
    await db.refresh(user)
    return user
