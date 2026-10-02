"""Typed adapter inputs for clinical content projection.

Adapters supply only facts intentionally excluded from ClinicalContext
(demographics, session metadata, file metadata, SOAP persistence).
They must never reconstruct clinical state already on ClinicalContext.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DemographicsAdapter:
    """Patient identity excluded from ClinicalContext."""

    first_name: str = ""
    last_name: str = ""
    age: int | None = None
    sex: str = ""
    national_id: str = ""


@dataclass(frozen=True)
class SessionAdapter:
    """Session metadata for header + envelope timestamps."""

    session_id: int
    status: str = ""
    visit_type: str = ""
    # ISO-8601 from session.updated_at or created_at — deterministic for identical adapters
    generated_at: str = ""


@dataclass(frozen=True)
class DocumentAdapterItem:
    """Uploaded file metadata only."""

    file_id: int
    filename: str
    uploaded_at: str = ""
    detail: str = ""


@dataclass(frozen=True)
class SoapAdapter:
    """Persisted SOAP text / status — not clinical reasoning."""

    soap_note: str | None = None
    legacy_soap_json: str | None = None
    soap_status: str = ""


@dataclass(frozen=True)
class ClinicalContentAdapters:
    """Bundle of allowed non-ClinicalContext inputs for projection."""

    session: SessionAdapter
    demographics: DemographicsAdapter | None = None
    documents: tuple[DocumentAdapterItem, ...] = ()
    soap: SoapAdapter | None = None
