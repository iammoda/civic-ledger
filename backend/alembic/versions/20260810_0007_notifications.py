"""Phase 8: in-app notifications."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260810_0007"
down_revision = "20260810_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title_en", sa.String(length=500), nullable=False),
        sa.Column("body_en", sa.Text(), nullable=True),
        sa.Column("url_path", sa.String(length=500), nullable=True),
        sa.Column("matched_follow", sa.String(length=255), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "fingerprint", name="uq_notification_user_event"),
    )
    for col in ("user_id", "kind", "is_read", "fingerprint"):
        op.create_index(f"ix_notifications_{col}", "notifications", [col])


def downgrade() -> None:
    op.drop_table("notifications")
