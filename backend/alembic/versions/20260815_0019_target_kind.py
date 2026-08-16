"""Registration target links: distinguish MPP-office vs ministry targets.

Most Ontario registrations target ministries, not backbench MPP offices —
resolving "Office of the Minister of Health" to the sitting minister puts
lobbying receipts where the power is.

Revision ID: 20260815_0019
Revises: 20260815_0018
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260815_0019"
down_revision = "20260815_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lobby_registration_mpps",
        sa.Column("target_kind", sa.String(16), nullable=False, server_default="mpp_office"),
    )
    op.create_index("ix_lobby_registration_mpps_kind", "lobby_registration_mpps", ["target_kind"])


def downgrade() -> None:
    op.drop_index("ix_lobby_registration_mpps_kind")
    op.drop_column("lobby_registration_mpps", "target_kind")
