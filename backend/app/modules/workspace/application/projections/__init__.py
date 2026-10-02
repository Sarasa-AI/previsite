"""Clinical content projection package — Workspace presentation only."""

from app.modules.workspace.application.projections.adapters import (
    ClinicalContentAdapters,
    DemographicsAdapter,
    DocumentAdapterItem,
    SessionAdapter,
    SoapAdapter,
)
from app.modules.workspace.application.projections.project_clinical_content import (
    project_clinical_content,
)

__all__ = [
    "ClinicalContentAdapters",
    "DemographicsAdapter",
    "DocumentAdapterItem",
    "SessionAdapter",
    "SoapAdapter",
    "project_clinical_content",
]
