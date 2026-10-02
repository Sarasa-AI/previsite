"""P3 foundation: Organization, profiles, family, Encounter

Revision ID: x8g9h0i1j2k3
Revises: w7f8g9h0i1j2
Create Date: 2026-10-02
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "x8g9h0i1j2k3"
down_revision: Union[str, None] = "w7f8g9h0i1j2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Keep in sync with app.models.organization — do not import ORM here.
DEFAULT_ORGANIZATION_ID = uuid.UUID("5c0a1d7e-4b3f-5a61-9c2e-1f0a6d8b7e41")
DEFAULT_ORGANIZATION_SLUG = "previsit"
DEFAULT_ORGANIZATION_NAME = "PreVisit"

_UUID = sa.Uuid(as_uuid=True)


def _column_names(table: str) -> set[str]:
    bind = op.get_bind()
    return {col["name"] for col in sa.inspect(bind).get_columns(table)}


def _index_names(table: str) -> set[str]:
    bind = op.get_bind()
    return {idx["name"] for idx in sa.inspect(bind).get_indexes(table)}


def _constraint_names(table: str) -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    names: set[str] = set()
    for ck in insp.get_check_constraints(table):
        if ck.get("name"):
            names.add(ck["name"])
    for uq in insp.get_unique_constraints(table):
        if uq.get("name"):
            names.add(uq["name"])
    for fk in insp.get_foreign_keys(table):
        if fk.get("name"):
            names.add(fk["name"])
    return names


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _ensure_org_column(table: str, col: str = "organization_id") -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if table not in tables:
        return
    existing = _column_names(table)
    if col in existing:
        return
    op.add_column(table, sa.Column(col, _UUID, nullable=True))
    op.create_foreign_key(
        f"fk_{table}_{col}_organizations",
        table,
        "organizations",
        [col],
        ["id"],
    )
    idx = f"ix_{table}_{col}"
    if idx not in _index_names(table):
        op.create_index(idx, table, [col])


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    dialect = bind.dialect.name

    if "organizations" not in tables:
        op.create_table(
            "organizations",
            sa.Column("id", _UUID, nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("slug", sa.String(length=64), nullable=False),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_organizations_deleted_at", "organizations", ["deleted_at"])

    indexes = _index_names("organizations")
    if "uq_organizations_slug_live" not in indexes:
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_organizations_slug_live "
                "ON organizations (slug) WHERE deleted_at IS NULL"
            )
        )

    # Seed default organization
    exists = bind.execute(
        sa.text("SELECT 1 FROM organizations WHERE slug = :slug LIMIT 1"),
        {"slug": DEFAULT_ORGANIZATION_SLUG},
    ).fetchone()
    if not exists:
        bind.execute(
            sa.text(
                """
                INSERT INTO organizations (id, name, slug, is_default, created_at, updated_at)
                VALUES (:id, :name, :slug, :is_default, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {
                "id": str(DEFAULT_ORGANIZATION_ID),
                "name": DEFAULT_ORGANIZATION_NAME,
                "slug": DEFAULT_ORGANIZATION_SLUG,
                "is_default": True,
            },
        )

    tables = set(sa.inspect(bind).get_table_names())
    if "organization_memberships" not in tables:
        op.create_table(
            "organization_memberships",
            sa.Column("id", _UUID, nullable=False),
            sa.Column("organization_id", _UUID, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "organization_id",
                "user_id",
                name="uq_organization_memberships_org_user",
            ),
        )
        op.create_index(
            "ix_organization_memberships_organization_id",
            "organization_memberships",
            ["organization_id"],
        )
        op.create_index(
            "ix_organization_memberships_user_id",
            "organization_memberships",
            ["user_id"],
        )

    tables = set(sa.inspect(bind).get_table_names())
    if "patient_profiles" not in tables:
        op.create_table(
            "patient_profiles",
            sa.Column("id", _UUID, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("first_name", sa.String(), nullable=True),
            sa.Column("last_name", sa.String(), nullable=True),
            sa.Column("date_of_birth", sa.Date(), nullable=True),
            sa.Column("age_years", sa.Integer(), nullable=True),
            sa.Column("sex", sa.String(length=32), nullable=True),
            sa.Column("weight_kg", sa.Float(), nullable=True),
            sa.Column("height_cm", sa.Float(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
        )
        op.create_index("ix_patient_profiles_user_id", "patient_profiles", ["user_id"])
        op.create_index(
            "ix_patient_profiles_deleted_at", "patient_profiles", ["deleted_at"]
        )

    tables = set(sa.inspect(bind).get_table_names())
    if "doctor_profiles" not in tables:
        op.create_table(
            "doctor_profiles",
            sa.Column("id", _UUID, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("medical_council_number", sa.String(length=64), nullable=True),
            sa.Column("specialty", sa.String(length=128), nullable=True),
            sa.Column("verification_status", sa.String(length=32), nullable=False),
            sa.Column("verified_by_user_id", sa.Integer(), nullable=True),
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["verified_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
        )
        op.create_index("ix_doctor_profiles_user_id", "doctor_profiles", ["user_id"])
        op.create_index(
            "ix_doctor_profiles_deleted_at", "doctor_profiles", ["deleted_at"]
        )

    doctor_indexes = _index_names("doctor_profiles")
    if "uq_doctor_profiles_council_live" not in doctor_indexes:
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_doctor_profiles_council_live "
                "ON doctor_profiles (medical_council_number) "
                "WHERE medical_council_number IS NOT NULL AND deleted_at IS NULL"
            )
        )

    tables = set(sa.inspect(bind).get_table_names())
    if "family_groups" not in tables:
        op.create_table(
            "family_groups",
            sa.Column("id", _UUID, nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_family_groups_owner_user_id", "family_groups", ["owner_user_id"]
        )
        op.create_index("ix_family_groups_deleted_at", "family_groups", ["deleted_at"])

    fg_indexes = _index_names("family_groups")
    if "uq_family_groups_one_live_owner" not in fg_indexes:
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_family_groups_one_live_owner "
                "ON family_groups (owner_user_id) WHERE deleted_at IS NULL"
            )
        )

    tables = set(sa.inspect(bind).get_table_names())
    if "family_members" not in tables:
        op.create_table(
            "family_members",
            sa.Column("id", _UUID, nullable=False),
            sa.Column("family_group_id", _UUID, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("display_name", sa.String(length=200), nullable=False),
            sa.Column("relationship_to_owner", sa.String(length=32), nullable=False),
            sa.Column("date_of_birth", sa.Date(), nullable=True),
            sa.Column("sex", sa.String(length=32), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["family_group_id"], ["family_groups.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_family_members_family_group_id", "family_members", ["family_group_id"]
        )
        op.create_index("ix_family_members_user_id", "family_members", ["user_id"])
        op.create_index("ix_family_members_deleted_at", "family_members", ["deleted_at"])

    fm_indexes = _index_names("family_members")
    if "uq_family_members_user_live" not in fm_indexes:
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_family_members_user_live "
                "ON family_members (user_id) "
                "WHERE user_id IS NOT NULL AND deleted_at IS NULL"
            )
        )

    tables = set(sa.inspect(bind).get_table_names())
    if "encounters" not in tables:
        op.create_table(
            "encounters",
            sa.Column("id", _UUID, nullable=False),
            sa.Column("organization_id", _UUID, nullable=False),
            sa.Column("subject_user_id", sa.Integer(), nullable=True),
            sa.Column("subject_family_member_id", _UUID, nullable=True),
            sa.Column("initiated_by_user_id", sa.Integer(), nullable=False),
            sa.Column("doctor_user_id", sa.Integer(), nullable=True),
            sa.Column("consent_user_id", sa.Integer(), nullable=False),
            sa.Column("consent_snapshot", _json_type(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("chief_complaint", sa.Text(), nullable=True),
            sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("accepted_by_user_id", sa.Integer(), nullable=True),
            sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("signed_by_user_id", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint(
                "(subject_user_id IS NOT NULL AND subject_family_member_id IS NULL) "
                "OR (subject_user_id IS NULL AND subject_family_member_id IS NOT NULL)",
                name="ck_encounters_subject_xor",
            ),
            sa.CheckConstraint(
                "status <> 'signed' OR (signed_at IS NOT NULL AND signed_by_user_id IS NOT NULL)",
                name="ck_encounters_signed_requires_signer",
            ),
            sa.CheckConstraint(
                "status <> 'accepted' OR (accepted_at IS NOT NULL AND accepted_by_user_id IS NOT NULL)",
                name="ck_encounters_accepted_requires_acceptor",
            ),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["subject_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["subject_family_member_id"], ["family_members.id"]),
            sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["doctor_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["consent_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["accepted_by_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["signed_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_encounters_org_status", "encounters", ["organization_id", "status"]
        )
        op.create_index("ix_encounters_subject_user", "encounters", ["subject_user_id"])
        op.create_index(
            "ix_encounters_subject_family_member",
            "encounters",
            ["subject_family_member_id"],
        )
        op.create_index("ix_encounters_doctor_user", "encounters", ["doctor_user_id"])
        op.create_index(
            "ix_encounters_initiated_by_user_id", "encounters", ["initiated_by_user_id"]
        )
        op.create_index(
            "ix_encounters_consent_user_id", "encounters", ["consent_user_id"]
        )
        op.create_index("ix_encounters_deleted_at", "encounters", ["deleted_at"])

    # Nullable FKs on sessions + clinical children
    tables = set(sa.inspect(bind).get_table_names())
    if "sessions" in tables:
        sess_cols = _column_names("sessions")
        if "encounter_id" not in sess_cols:
            op.add_column(
                "sessions", sa.Column("encounter_id", _UUID, nullable=True)
            )
            op.create_foreign_key(
                "fk_sessions_encounter_id_encounters",
                "sessions",
                "encounters",
                ["encounter_id"],
                ["id"],
                ondelete="RESTRICT",
            )
            if "ix_sessions_encounter_id" not in _index_names("sessions"):
                op.create_index(
                    "ix_sessions_encounter_id", "sessions", ["encounter_id"]
                )
        if "organization_id" not in sess_cols:
            op.add_column(
                "sessions", sa.Column("organization_id", _UUID, nullable=True)
            )
            op.create_foreign_key(
                "fk_sessions_organization_id_organizations",
                "sessions",
                "organizations",
                ["organization_id"],
                ["id"],
            )
            if "ix_sessions_organization_id" not in _index_names("sessions"):
                op.create_index(
                    "ix_sessions_organization_id", "sessions", ["organization_id"]
                )

    for child in (
        "messages",
        "files",
        "intakes",
        "summaries",
        "document_artifacts",
        "clinical_findings",
        "risk_signals",
        "recommendations",
        "workflow_events",
    ):
        _ensure_org_column(child)

    # --- Backfill ---
    if "users" in tables:
        # Patient profiles
        patients = bind.execute(
            sa.text(
                """
                SELECT id, first_name, last_name, age, sex, weight, height
                FROM users
                WHERE lower(CAST(role AS VARCHAR)) = 'patient'
                  AND id NOT IN (SELECT user_id FROM patient_profiles)
                """
            )
        ).fetchall()
        for row in patients:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO patient_profiles (
                        id, user_id, first_name, last_name, age_years, sex,
                        weight_kg, height_cm, created_at, updated_at
                    ) VALUES (
                        :id, :user_id, :first_name, :last_name, :age_years, :sex,
                        :weight_kg, :height_cm, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": row[0],
                    "first_name": row[1],
                    "last_name": row[2],
                    "age_years": row[3],
                    "sex": row[4],
                    "weight_kg": row[5],
                    "height_cm": row[6],
                },
            )

        # Doctor profiles
        doctors = bind.execute(
            sa.text(
                """
                SELECT id, medical_council_license, specialty, verification_status,
                       verified_by, verified_at
                FROM users
                WHERE lower(CAST(role AS VARCHAR)) = 'doctor'
                  AND id NOT IN (SELECT user_id FROM doctor_profiles)
                """
            )
        ).fetchall()
        for row in doctors:
            status = row[3] or "pending"
            if hasattr(status, "value"):
                status = status.value
            status = str(status).lower()
            if status not in ("pending", "verified", "suspended"):
                status = "pending"
            bind.execute(
                sa.text(
                    """
                    INSERT INTO doctor_profiles (
                        id, user_id, medical_council_number, specialty,
                        verification_status, verified_by_user_id, verified_at,
                        created_at, updated_at
                    ) VALUES (
                        :id, :user_id, :mcn, :specialty, :status, :verified_by,
                        :verified_at, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": row[0],
                    "mcn": row[1],
                    "specialty": row[2],
                    "status": status,
                    "verified_by": row[4],
                    "verified_at": row[5],
                },
            )

        # Memberships for doctors and admins
        staff = bind.execute(
            sa.text(
                """
                SELECT id, lower(CAST(role AS VARCHAR)) AS role
                FROM users
                WHERE lower(CAST(role AS VARCHAR)) IN ('doctor', 'admin')
                """
            )
        ).fetchall()
        for row in staff:
            existing_m = bind.execute(
                sa.text(
                    """
                    SELECT 1 FROM organization_memberships
                    WHERE organization_id = :org_id AND user_id = :user_id
                    LIMIT 1
                    """
                ),
                {"org_id": str(DEFAULT_ORGANIZATION_ID), "user_id": row[0]},
            ).fetchone()
            if existing_m:
                continue
            bind.execute(
                sa.text(
                    """
                    INSERT INTO organization_memberships (
                        id, organization_id, user_id, role, status,
                        created_at, updated_at
                    ) VALUES (
                        :id, :org_id, :user_id, :role, 'active',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "org_id": str(DEFAULT_ORGANIZATION_ID),
                    "user_id": row[0],
                    "role": row[1],
                },
            )

    # Encounters from sessions
    if "sessions" in tables and "encounter_id" in _column_names("sessions"):
        sessions = bind.execute(
            sa.text(
                """
                SELECT id, patient_id, doctor_id, status, initial_complaint, created_at
                FROM sessions
                WHERE encounter_id IS NULL
                """
            )
        ).fetchall()
        status_map = {
            "active": "intake",
            "pending_review": "awaiting_clinician",
            "completed": "closed",
            "cancelled": "cancelled",
        }
        for row in sessions:
            sess_id, patient_id, doctor_id, status, complaint, created_at = row
            status_val = status.value if hasattr(status, "value") else str(status)
            status_val = status_val.lower()
            enc_status = status_map.get(status_val, "intake")
            enc_id = uuid.uuid4()
            bind.execute(
                sa.text(
                    """
                    INSERT INTO encounters (
                        id, organization_id, subject_user_id, subject_family_member_id,
                        initiated_by_user_id, doctor_user_id, consent_user_id,
                        consent_snapshot, status, chief_complaint, opened_at,
                        created_at, updated_at
                    ) VALUES (
                        :id, :org_id, :subject_user_id, NULL,
                        :initiated_by, :doctor_id, :consent_user,
                        NULL, :status, :complaint, :opened_at,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": str(enc_id),
                    "org_id": str(DEFAULT_ORGANIZATION_ID),
                    "subject_user_id": patient_id,
                    "initiated_by": patient_id,
                    "doctor_id": doctor_id,
                    "consent_user": patient_id,
                    "status": enc_status,
                    "complaint": complaint,
                    "opened_at": created_at,
                },
            )
            bind.execute(
                sa.text(
                    """
                    UPDATE sessions
                    SET encounter_id = :enc_id, organization_id = :org_id
                    WHERE id = :sess_id
                    """
                ),
                {
                    "enc_id": str(enc_id),
                    "org_id": str(DEFAULT_ORGANIZATION_ID),
                    "sess_id": sess_id,
                },
            )

    # Propagate organization_id to children
    for child in (
        "messages",
        "files",
        "intakes",
        "summaries",
        "document_artifacts",
        "clinical_findings",
        "risk_signals",
        "recommendations",
        "workflow_events",
    ):
        if child not in set(sa.inspect(bind).get_table_names()):
            continue
        if "organization_id" not in _column_names(child):
            continue
        bind.execute(
            sa.text(
                f"""
                UPDATE {child} AS c
                SET organization_id = s.organization_id
                FROM sessions AS s
                WHERE c.session_id = s.id
                  AND c.organization_id IS NULL
                  AND s.organization_id IS NOT NULL
                """
            )
            if dialect == "postgresql"
            else sa.text(
                f"""
                UPDATE {child}
                SET organization_id = (
                    SELECT s.organization_id FROM sessions s
                    WHERE s.id = {child}.session_id
                )
                WHERE organization_id IS NULL
                  AND EXISTS (
                    SELECT 1 FROM sessions s
                    WHERE s.id = {child}.session_id
                      AND s.organization_id IS NOT NULL
                  )
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    for child in (
        "workflow_events",
        "recommendations",
        "risk_signals",
        "clinical_findings",
        "document_artifacts",
        "summaries",
        "intakes",
        "files",
        "messages",
    ):
        if child not in tables:
            continue
        cols = _column_names(child)
        if "organization_id" in cols:
            try:
                op.drop_constraint(
                    f"fk_{child}_organization_id_organizations",
                    child,
                    type_="foreignkey",
                )
            except Exception:
                pass
            idx = f"ix_{child}_organization_id"
            if idx in _index_names(child):
                op.drop_index(idx, table_name=child)
            op.drop_column(child, "organization_id")

    if "sessions" in tables:
        cols = _column_names("sessions")
        for col, fk, idx in (
            (
                "encounter_id",
                "fk_sessions_encounter_id_encounters",
                "ix_sessions_encounter_id",
            ),
            (
                "organization_id",
                "fk_sessions_organization_id_organizations",
                "ix_sessions_organization_id",
            ),
        ):
            if col in cols:
                try:
                    op.drop_constraint(fk, "sessions", type_="foreignkey")
                except Exception:
                    pass
                if idx in _index_names("sessions"):
                    op.drop_index(idx, table_name="sessions")
                op.drop_column("sessions", col)

    for table in (
        "encounters",
        "family_members",
        "family_groups",
        "doctor_profiles",
        "patient_profiles",
        "organization_memberships",
        "organizations",
    ):
        if table in set(sa.inspect(bind).get_table_names()):
            op.drop_table(table)
