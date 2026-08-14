"""Lobby org profiles: cached one-line LLM descriptions of lobbying orgs.

So a visitor knows what "Jack.org" or "Imagine Canada" is. Descriptive
only; budget-gated; cached forever.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260814_0011"
down_revision = "20260813_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lobby_org_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_name", sa.String(500), nullable=False),
        sa.Column("description_en", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("model_name", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_lobby_org_profiles_org_name", "lobby_org_profiles", ["org_name"], unique=True)
    op.create_index("ix_lobby_org_profiles_status", "lobby_org_profiles", ["status"])


def downgrade() -> None:
    op.drop_index("ix_lobby_org_profiles_status", table_name="lobby_org_profiles")
    op.drop_index("ix_lobby_org_profiles_org_name", table_name="lobby_org_profiles")
    op.drop_table("lobby_org_profiles")
