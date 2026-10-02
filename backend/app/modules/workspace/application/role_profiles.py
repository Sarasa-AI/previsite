"""Role profile clamps — queue/visibility/cognitive budget only."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.workspace.domain.enums import ClinicalObjectId, RoleProfile


@dataclass(frozen=True)
class RoleClamp:
    story_enabled: bool
    max_primary: int
    max_expanded: int
    queue_cap: int
    soap_deferred: bool
    suppress_objects: frozenset[ClinicalObjectId]
    pin_allergy_chip: bool
    timeline_always_compressed: bool
    trust_uncertainty_boost: bool
    elevate_documents: bool
    elevate_missing_data: bool
    snapshot_standard: bool
    red_flags_boost: float
    critical_labs_boost: float


_ROLE_CLAMPS: dict[RoleProfile, RoleClamp] = {
    RoleProfile.DOCTOR: RoleClamp(
        story_enabled=True,
        max_primary=7,
        max_expanded=2,
        queue_cap=8,
        soap_deferred=False,
        suppress_objects=frozenset(),
        pin_allergy_chip=True,
        timeline_always_compressed=False,
        trust_uncertainty_boost=False,
        elevate_documents=False,
        elevate_missing_data=False,
        snapshot_standard=False,
        red_flags_boost=1.0,
        critical_labs_boost=1.0,
    ),
    RoleProfile.RESIDENT: RoleClamp(
        story_enabled=True,
        max_primary=7,
        max_expanded=2,
        queue_cap=8,
        soap_deferred=False,
        suppress_objects=frozenset(),
        pin_allergy_chip=True,
        timeline_always_compressed=False,
        trust_uncertainty_boost=True,
        elevate_documents=False,
        elevate_missing_data=False,
        snapshot_standard=False,
        red_flags_boost=1.0,
        critical_labs_boost=1.0,
    ),
    RoleProfile.NURSE: RoleClamp(
        story_enabled=False,
        max_primary=6,
        max_expanded=2,
        queue_cap=6,
        soap_deferred=True,
        suppress_objects=frozenset({ClinicalObjectId.STORY}),
        pin_allergy_chip=True,
        timeline_always_compressed=False,
        trust_uncertainty_boost=False,
        elevate_documents=False,
        elevate_missing_data=False,
        snapshot_standard=False,
        red_flags_boost=1.0,
        critical_labs_boost=1.0,
    ),
    RoleProfile.EMERGENCY: RoleClamp(
        story_enabled=False,
        max_primary=5,
        max_expanded=1,
        queue_cap=5,
        soap_deferred=True,
        suppress_objects=frozenset({ClinicalObjectId.STORY}),
        pin_allergy_chip=False,
        timeline_always_compressed=True,
        trust_uncertainty_boost=False,
        elevate_documents=False,
        elevate_missing_data=False,
        snapshot_standard=False,
        red_flags_boost=1.3,
        critical_labs_boost=1.3,
    ),
    RoleProfile.TELEHEALTH: RoleClamp(
        story_enabled=True,
        max_primary=7,
        max_expanded=2,
        queue_cap=8,
        soap_deferred=False,
        suppress_objects=frozenset(),
        pin_allergy_chip=True,
        timeline_always_compressed=False,
        trust_uncertainty_boost=False,
        elevate_documents=True,
        elevate_missing_data=True,
        snapshot_standard=True,
        red_flags_boost=1.0,
        critical_labs_boost=1.0,
    ),
}


def role_clamp(role: RoleProfile) -> RoleClamp:
    return _ROLE_CLAMPS[role]
