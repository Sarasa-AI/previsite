from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.models.user import User, UserRole
from app.schemas.patient import PatientProfileResponse, PatientProfileUpdate, user_to_profile
from app.utils.national_id import validate_iranian_national_id

router = APIRouter(prefix="/api/patients", tags=["patients"])


def _require_patient(current_user: User) -> None:
    if current_user.role != UserRole.PATIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only patients have a demographic profile",
        )


@router.get("/me/profile", response_model=PatientProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    _require_patient(current_user)
    return user_to_profile(current_user)


@router.patch("/me/profile", response_model=PatientProfileResponse)
async def update_my_profile(
    data: PatientProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_patient(current_user)

    if data.national_id is not None and not validate_iranian_national_id(data.national_id):
        raise HTTPException(status_code=400, detail="INVALID_NATIONAL_ID")

    if data.national_id and data.national_id != current_user.national_id:
        result = await db.execute(
            select(User).where(
                User.national_id == data.national_id,
                User.id != current_user.id,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="USER_EXISTS")

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(current_user, field, value)

    if current_user.first_name and current_user.last_name:
        current_user.full_name = f"{current_user.first_name} {current_user.last_name}".strip()

    await db.commit()
    await db.refresh(current_user)
    return user_to_profile(current_user)
