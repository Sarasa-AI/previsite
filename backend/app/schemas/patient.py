from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.services.narrative_utils import sex_label_fa


class PatientProfileResponse(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    national_id: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=0, le=150)
    sex: Optional[str] = None
    weight: Optional[float] = Field(default=None, gt=0)
    height: Optional[float] = Field(default=None, gt=0)
    is_complete: bool = False

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("sex")
    def serialize_sex(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return sex_label_fa(value)


class PatientProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    national_id: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=0, le=150)
    sex: Optional[str] = None
    weight: Optional[float] = Field(default=None, gt=0)
    height: Optional[float] = Field(default=None, gt=0)


def profile_is_complete(profile: PatientProfileResponse) -> bool:
    return all(
        [
            profile.first_name,
            profile.last_name,
            profile.national_id,
            profile.age is not None,
            profile.sex,
            profile.weight is not None and profile.weight > 0,
            profile.height is not None and profile.height > 0,
        ]
    )


def user_to_profile(user) -> PatientProfileResponse:
    profile = PatientProfileResponse(
        first_name=user.first_name,
        last_name=user.last_name,
        national_id=user.national_id,
        age=user.age,
        sex=user.sex,
        weight=user.weight,
        height=user.height,
    )
    profile.is_complete = profile_is_complete(profile)
    return profile
