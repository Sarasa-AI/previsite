"""Document artifacts — persisted OCR and structured-extraction results.

Every uploaded document produces a traceable chain:

    File → DocumentArtifact(kind='ocr') → DocumentArtifact(kind='extraction')

The extraction artifact carries per-value provenance (page, bounding box, the
exact source text, confidence, method) so that any clinical fact rendered in the
Doctor Workspace can be traced back to the pixels it came from.
"""

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base

#: Payload schema version for ``payload_json`` — bump on breaking shape changes.
ARTIFACT_SCHEMA_VERSION = "1.0.0"


class ArtifactKind:
    """Artifact stage discriminator (string constants, not an SQL enum).

    Kept as plain strings so adding a stage never requires a DB enum migration.
    """

    OCR = "ocr"
    EXTRACTION = "extraction"


class ArtifactStatus:
    """Terminal status of a single artifact stage."""

    #: Stage ran and produced usable output.
    SUCCEEDED = "succeeded"
    #: Stage ran cleanly but found nothing (e.g. blank scan, no known analytes).
    EMPTY = "empty"
    #: Stage ran but output is not trustworthy — surface as "needs review",
    #: never as a clinical value.
    NEEDS_REVIEW = "needs_review"
    #: Stage could not run (missing engine, unreadable file, crash).
    FAILED = "failed"


class DocumentArtifact(Base):
    __tablename__ = "document_artifacts"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer, ForeignKey("sessions.id"), nullable=False, index=True
    )
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False, index=True)

    kind = Column(String(32), nullable=False, index=True)
    status = Column(String(32), nullable=False)

    engine = Column(String(64), nullable=False, server_default="")
    engine_version = Column(String(64), nullable=False, server_default="")

    page_count = Column(Integer, nullable=True)
    #: Raw OCR/text-layer output (kind='ocr'). Never shown without authorization.
    raw_text = Column(Text, nullable=True)
    #: Structured payload with provenance (kind='extraction'). JSON string.
    payload_json = Column(Text, nullable=True)
    #: Mean engine confidence in [0, 1] when the engine reports one.
    confidence = Column(Float, nullable=True)
    error_detail = Column(Text, nullable=True)

    schema_version = Column(
        String(32), nullable=False, server_default=ARTIFACT_SCHEMA_VERSION
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("Session")
    file = relationship("File")

    __table_args__ = (
        # Latest-artifact-per-file lookups dominate reads.
        Index("ix_document_artifacts_file_kind", "file_id", "kind"),
        Index("ix_document_artifacts_session_kind", "session_id", "kind"),
    )
