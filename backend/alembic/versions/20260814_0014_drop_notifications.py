"""Remove the orphaned notifications/follows subsystem.

Sign-in was removed by design (anonymous platform); the hourly matcher was
still writing notifications no endpoint could read. Delete the dead tables:
user_profiles, user_follows, notifications.

Revision ID: 20260814_0014
Revises: 20260814_0013
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260814_0014"
down_revision = "20260814_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("user_follows")
    op.drop_table("user_profiles")


def downgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.String(64), primary_key=True),
        sa.Column("riding_name", sa.String(255), nullable=True),
        sa.Column("province_code", sa.String(8), nullable=True),
        sa.Column("mp_person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("reading_level", sa.String(16), nullable=False, server_default="standard"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_user_profiles_mp_person_id", "user_profiles", ["mp_person_id"])
    op.create_table(
        "user_follows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(16), nullable=False),
        sa.Column("target_ref", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "target_type", "target_ref", name="uq_user_follow"),
    )
    op.create_index("ix_user_follows_user_id", "user_follows", ["user_id"])
    op.create_index("ix_user_follows_target_type", "user_follows", ["target_type"])
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title_en", sa.String(500), nullable=False),
        sa.Column("body_en", sa.Text(), nullable=True),
        sa.Column("url_path", sa.String(500), nullable=True),
        sa.Column("matched_follow", sa.String(255), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "fingerprint", name="uq_notification_user_event"),
    )
    for col in ("user_id", "kind", "is_read", "fingerprint"):
        op.create_index(f"ix_notifications_{col}", "notifications", [col])
