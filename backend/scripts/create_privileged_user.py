#!/usr/bin/env python3
"""Operator-only CLI to create doctor or admin accounts.

Public registration always creates patients. Privileged accounts must be
created via this script (or the existing seed-doctor path for the default
doctor). There is no HTTP endpoint for privileged account creation.

Usage examples:
  python scripts/create_privileged_user.py --role doctor --username bagherzade2
  python scripts/create_privileged_user.py --role admin --email admin@clinic.local \\
      --display-name "Clinic Admin" --password '...'
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import logging
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import func, select  # noqa: E402

from app.auth.security import get_password_hash  # noqa: E402
from app.db.database import get_async_session  # noqa: E402
from app.models.user import DoctorVerificationStatus, User, UserRole  # noqa: E402
from app.utils.national_id import validate_iranian_national_id  # noqa: E402

logger = logging.getLogger(__name__)

PRIVILEGED_ROLES = {UserRole.DOCTOR.value, UserRole.ADMIN.value}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a doctor or admin user (operator only).",
    )
    parser.add_argument(
        "--role",
        required=True,
        choices=sorted(PRIVILEGED_ROLES),
        help="Privileged role to create (doctor or admin).",
    )
    parser.add_argument(
        "--username",
        default=None,
        help="Login username stored as full_name (required for doctors if no email).",
    )
    parser.add_argument(
        "--email",
        default=None,
        help="Email address. Defaults to {username}@doctor.com for doctors.",
    )
    parser.add_argument(
        "--display-name",
        default=None,
        help="Display name (defaults to username or email local-part).",
    )
    parser.add_argument(
        "--national-id",
        default=None,
        help="Optional Iranian national ID (validated if provided).",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Password (min 8 chars). Prompted interactively if omitted.",
    )
    parser.add_argument(
        "--license-number",
        default=None,
        help="Medical council license number (doctors).",
    )
    parser.add_argument(
        "--specialty",
        default=None,
        help="Clinical specialty label (doctors).",
    )
    parser.add_argument(
        "--verified",
        action="store_true",
        help="Mark doctor as verified (default: pending verification).",
    )
    return parser.parse_args(argv)


def _resolve_password(raw: str | None) -> str:
    if raw is not None:
        password = raw
    else:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            raise SystemExit("Passwords do not match.")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters.")
    return password


def _resolve_identity(args: argparse.Namespace) -> tuple[str, str, str | None]:
    username = (args.username or "").strip() or None
    email = (args.email or "").strip().lower() or None
    display_name = (args.display_name or "").strip() or None
    national_id = (args.national_id or "").strip() or None

    if national_id is not None and not validate_iranian_national_id(national_id):
        raise SystemExit("Invalid Iranian national ID.")

    if args.role == UserRole.DOCTOR.value:
        if not username and not email:
            raise SystemExit("Doctor creation requires --username and/or --email.")
        if not email:
            email = f"{username}@doctor.com"
        if not display_name:
            display_name = username or email.split("@", 1)[0]
    else:
        if not email:
            raise SystemExit("Admin creation requires --email.")
        if not display_name:
            display_name = username or email.split("@", 1)[0]

    if len(display_name) < 2:
        raise SystemExit("Display name must be at least 2 characters.")

    return email, display_name, national_id


async def create_privileged_user(
    *,
    role: str,
    email: str,
    display_name: str,
    password: str,
    national_id: str | None = None,
    license_number: str | None = None,
    specialty: str | None = None,
    verified: bool = False,
) -> User:
    if role not in PRIVILEGED_ROLES:
        raise ValueError(f"Refusing non-privileged role: {role}")

    user_role = UserRole.DOCTOR if role == UserRole.DOCTOR.value else UserRole.ADMIN

    async with get_async_session() as db:
        existing_email = await db.execute(
            select(User).where(func.lower(User.email) == email.lower())
        )
        if existing_email.scalar_one_or_none():
            raise SystemExit(f"Refusing to overwrite existing user with email={email}")

        if national_id:
            existing_nid = await db.execute(
                select(User).where(User.national_id == national_id)
            )
            if existing_nid.scalar_one_or_none():
                raise SystemExit(
                    f"Refusing to overwrite existing user with national_id={national_id}"
                )

        # Doctors historically log in by full_name; refuse collisions.
        existing_name = await db.execute(
            select(User).where(func.lower(User.full_name) == display_name.lower())
        )
        if existing_name.scalar_one_or_none():
            raise SystemExit(
                f"Refusing to overwrite existing user with display_name={display_name}"
            )

        verification_status = None
        if user_role == UserRole.DOCTOR:
            verification_status = (
                DoctorVerificationStatus.VERIFIED
                if verified
                else DoctorVerificationStatus.PENDING
            )

        user = User(
            email=email,
            full_name=display_name,
            national_id=national_id,
            hashed_password=get_password_hash(password),
            role=user_role,
            is_active=True,
            medical_council_license=(license_number or None),
            specialty=(specialty or None),
            verification_status=verification_status,
        )
        db.add(user)
        await db.flush()
        from app.services.platform_identity_service import (
            ensure_doctor_profile,
            ensure_staff_membership,
        )

        if user_role == UserRole.DOCTOR:
            await ensure_doctor_profile(db, user)
        await ensure_staff_membership(db, user)
        await db.commit()
        await db.refresh(user)
        return user


async def _async_main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    email, display_name, national_id = _resolve_identity(args)
    password = _resolve_password(args.password)
    license_number = (args.license_number or "").strip() or None
    specialty = (args.specialty or "").strip() or None
    user = await create_privileged_user(
        role=args.role,
        email=email,
        display_name=display_name,
        password=password,
        national_id=national_id,
        license_number=license_number,
        specialty=specialty,
        verified=bool(args.verified),
    )
    status_suffix = ""
    if user.role == UserRole.DOCTOR and user.verification_status is not None:
        status_suffix = f" verification_status={user.verification_status.value}"
    print(
        f"Created {user.role.value} user id={user.id} email={user.email} "
        f"display_name={user.full_name}{status_suffix}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    return asyncio.run(_async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
