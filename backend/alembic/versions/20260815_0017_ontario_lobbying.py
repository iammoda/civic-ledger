"""Ontario lobbyist registry: registrations + MPP target links.

Ontario publishes *registrations* (who is registered to lobby which
ministries/offices about what) — not per-meeting communication logs like
the federal registry. Different meaning, different table.

Revision ID: 20260815_0017
Revises: 20260814_0016
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260815_0017"
down_revision = "20260814_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lobby_registrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("jurisdiction_code", sa.String(8), nullable=False, server_default="on"),
        # e.g. CL10523-20260811037393 — unique per filing.
        sa.Column("registration_number", sa.String(64), nullable=False),
        sa.Column("lobbyist_number", sa.String(32), nullable=True),
        sa.Column("lobbyist_name", sa.String(255), nullable=True),
        sa.Column("firm_name", sa.String(255), nullable=True),
        # consultant | in_house_organization | in_house_persons
        sa.Column("lobbyist_type", sa.String(32), nullable=False),
        sa.Column("client_name", sa.String(255), nullable=True),
        sa.Column("client_description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("initial_filing_date", sa.Date(), nullable=True),
        sa.Column("last_amendment_date", sa.Date(), nullable=True),
        sa.Column("subject_matters", sa.Text(), nullable=True),
        sa.Column("goals", sa.Text(), nullable=True),
        sa.Column("target_ministries", sa.Text(), nullable=True),
        sa.Column("target_mpp_offices", sa.Text(), nullable=True),
        sa.Column("techniques", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("registration_number", name="uq_lobby_registration_number"),
    )
    for col in ("jurisdiction_code", "client_name", "firm_name", "status", "last_amendment_date"):
        op.create_index(f"ix_lobby_registrations_{col}", "lobby_registrations", [col])

    op.create_table(
        "lobby_registration_mpps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "registration_id",
            sa.Integer(),
            sa.ForeignKey("lobby_registrations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=False),
        # The riding string as filed, e.g. "Niagara West" — provenance.
        sa.Column("riding_as_filed", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("registration_id", "person_id", name="uq_lobby_registration_mpp"),
    )
    op.create_index("ix_lobby_registration_mpps_person", "lobby_registration_mpps", ["person_id"])
    op.create_index("ix_lobby_registration_mpps_registration", "lobby_registration_mpps", ["registration_id"])


def downgrade() -> None:
    op.drop_table("lobby_registration_mpps")
    op.drop_table("lobby_registrations")
