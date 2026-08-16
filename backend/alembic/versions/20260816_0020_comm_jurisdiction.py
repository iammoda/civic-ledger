"""Lobby communications: jurisdiction marker (federal vs BC).

BC's Lobbying Activity Reports are per-meeting logs like Ottawa's, so they
share the lobby_communications table — jurisdiction_code keeps explorers
and aggregates honest about whose registry a row came from.

Revision ID: 20260816_0020
Revises: 20260815_0019
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260816_0020"
down_revision = "20260815_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lobby_communications",
        sa.Column("jurisdiction_code", sa.String(8), nullable=False, server_default="ca"),
    )
    op.create_index("ix_lobby_communications_jurisdiction", "lobby_communications", ["jurisdiction_code"])


def downgrade() -> None:
    op.drop_index("ix_lobby_communications_jurisdiction")
    op.drop_column("lobby_communications", "jurisdiction_code")
