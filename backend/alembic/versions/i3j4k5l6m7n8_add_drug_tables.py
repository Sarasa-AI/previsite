"""add drug reference tables

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2026-07-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i3j4k5l6m7n8"
down_revision: Union[str, None] = "h2i3j4k5l6m7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "generic_drugs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("generic_name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generic_drugs_generic_name", "generic_drugs", ["generic_name"], unique=True)
    op.create_index("ix_generic_drugs_id", "generic_drugs", ["id"], unique=False)

    op.create_table(
        "brand_drugs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("brand_name", sa.String(), nullable=False),
        sa.Column("generic_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["generic_id"], ["generic_drugs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_brand_drugs_brand_name", "brand_drugs", ["brand_name"], unique=False)
    op.create_index("ix_brand_drugs_generic_id", "brand_drugs", ["generic_id"], unique=False)
    op.create_index("ix_brand_drugs_id", "brand_drugs", ["id"], unique=False)

    op.create_table(
        "drug_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alias_name", sa.String(), nullable=False),
        sa.Column("generic_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["generic_id"], ["generic_drugs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_drug_aliases_alias_name", "drug_aliases", ["alias_name"], unique=False)
    op.create_index("ix_drug_aliases_generic_id", "drug_aliases", ["generic_id"], unique=False)
    op.create_index("ix_drug_aliases_id", "drug_aliases", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_drug_aliases_id", table_name="drug_aliases")
    op.drop_index("ix_drug_aliases_generic_id", table_name="drug_aliases")
    op.drop_index("ix_drug_aliases_alias_name", table_name="drug_aliases")
    op.drop_table("drug_aliases")

    op.drop_index("ix_brand_drugs_id", table_name="brand_drugs")
    op.drop_index("ix_brand_drugs_generic_id", table_name="brand_drugs")
    op.drop_index("ix_brand_drugs_brand_name", table_name="brand_drugs")
    op.drop_table("brand_drugs")

    op.drop_index("ix_generic_drugs_id", table_name="generic_drugs")
    op.drop_index("ix_generic_drugs_generic_name", table_name="generic_drugs")
    op.drop_table("generic_drugs")
