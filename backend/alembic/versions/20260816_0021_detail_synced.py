"""Lobby registrations: detail_synced — two-phase Ontario crawling.

The Ontario registry has no export, so registrations are collected in two
phases: the grid walk stores stub rows immediately (client/lobbyist/firm/
type/date are all in the grid), then the slow per-registration detail
fetches fill in goals/subjects/targets. detail_synced marks phase two.

Revision ID: 20260816_0021
Revises: 20260816_0020
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260816_0021"
down_revision = "20260816_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing rows all came through the detail path — mark them synced.
    op.add_column(
        "lobby_registrations",
        sa.Column("detail_synced", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_lobby_registrations_detail_synced", "lobby_registrations", ["detail_synced"])


def downgrade() -> None:
    op.drop_index("ix_lobby_registrations_detail_synced")
    op.drop_column("lobby_registrations", "detail_synced")
