"""Phase 6: money & integrity — lobbying, contributions, flags, corrections."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260810_0006"
down_revision = "20260810_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("normalized_name", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("normalized_name"),
    )
    op.create_index("ix_organizations_name", "organizations", ["name"])
    op.create_index("ix_organizations_normalized_name", "organizations", ["normalized_name"])

    op.create_table(
        "lobby_communications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_ref", sa.String(length=64), nullable=False),
        sa.Column("comm_date", sa.Date(), nullable=True),
        sa.Column("client_org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("client_name", sa.String(length=500), nullable=True),
        sa.Column("registrant_name", sa.String(length=255), nullable=True),
        sa.Column("dpoh_name", sa.String(length=255), nullable=False),
        sa.Column("dpoh_title", sa.String(length=500), nullable=True),
        sa.Column("institution", sa.String(length=255), nullable=True),
        sa.Column("dpoh_person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("subjects", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source_ref", "dpoh_name", name="uq_lobby_comm_ref_dpoh"),
    )
    for col in ("source_ref", "comm_date", "client_org_id", "dpoh_name", "dpoh_person_id"):
        op.create_index(f"ix_lobby_communications_{col}", "lobby_communications", [col])

    op.create_table(
        "contributions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contributor_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_contributor", sa.String(length=255), nullable=False),
        sa.Column("contributor_city", sa.String(length=128), nullable=True),
        sa.Column("contributor_province", sa.String(length=8), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("received_on", sa.Date(), nullable=True),
        sa.Column("recipient_name", sa.String(length=255), nullable=False),
        sa.Column("recipient_party", sa.String(length=255), nullable=True),
        sa.Column("recipient_person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("recipient_type", sa.String(length=32), nullable=True),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source_fingerprint"),
    )
    for col in ("contributor_name", "normalized_contributor", "received_on", "recipient_name", "recipient_person_id"):
        op.create_index(f"ix_contributions_{col}", "contributions", [col])

    op.create_table(
        "integrity_flags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("detector", sa.String(length=64), nullable=False),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("bill_id", sa.Integer(), sa.ForeignKey("bills.id"), nullable=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("headline_en", sa.String(length=500), nullable=False),
        sa.Column("detail_en", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending_review"),
        sa.Column("reviewed_by", sa.String(length=255), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("fingerprint"),
    )
    for col in ("detector", "person_id", "bill_id", "organization_id", "status", "fingerprint"):
        op.create_index(f"ix_integrity_flags_{col}", "integrity_flags", [col])

    op.create_table(
        "corrections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("page_url", sa.String(length=1000), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("contact", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_corrections_status", "corrections", ["status"])


def downgrade() -> None:
    op.drop_table("corrections")
    op.drop_table("integrity_flags")
    op.drop_table("contributions")
    op.drop_table("lobby_communications")
    op.drop_table("organizations")
