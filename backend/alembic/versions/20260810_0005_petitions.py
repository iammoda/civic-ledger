"""Phase 5: participation — e-petitions."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260810_0005"
down_revision = "20260810_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "petitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.String(length=16), nullable=False),
        sa.Column("title_en", sa.String(length=500), nullable=False),
        sa.Column("text_en", sa.Text(), nullable=True),
        sa.Column("status_en", sa.String(length=255), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("closes_at", sa.Date(), nullable=True),
        sa.Column("signature_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("keywords_en", sa.Text(), nullable=True),
        sa.Column("sponsor_name", sa.String(length=255), nullable=True),
        sa.Column("sponsor_person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("parliament_number", sa.Integer(), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("number"),
    )
    op.create_index("ix_petitions_number", "petitions", ["number"])
    op.create_index("ix_petitions_state", "petitions", ["state"])
    op.create_index("ix_petitions_closes_at", "petitions", ["closes_at"])
    op.create_index("ix_petitions_sponsor_person_id", "petitions", ["sponsor_person_id"])


def downgrade() -> None:
    op.drop_table("petitions")
