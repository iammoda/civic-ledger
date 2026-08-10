"""Phase 4: accounts — better-auth core tables + profiles + follows.

better-auth (Next.js) owns user/session/account/verification; FastAPI
reads the session table to authenticate API calls. Column names must
match better-auth's camelCase defaults exactly.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260810_0004"
down_revision = "20260810_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("emailVerified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("image", sa.Text(), nullable=True),
        sa.Column("createdAt", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updatedAt", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "session",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("userId", sa.Text(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("expiresAt", sa.DateTime(), nullable=False),
        sa.Column("ipAddress", sa.Text(), nullable=True),
        sa.Column("userAgent", sa.Text(), nullable=True),
        sa.Column("createdAt", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updatedAt", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("token"),
    )
    op.create_index("ix_session_userId", "session", ["userId"])
    op.create_index("ix_session_token", "session", ["token"])

    op.create_table(
        "account",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("userId", sa.Text(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("accountId", sa.Text(), nullable=False),
        sa.Column("providerId", sa.Text(), nullable=False),
        sa.Column("accessToken", sa.Text(), nullable=True),
        sa.Column("refreshToken", sa.Text(), nullable=True),
        sa.Column("accessTokenExpiresAt", sa.DateTime(), nullable=True),
        sa.Column("refreshTokenExpiresAt", sa.DateTime(), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("idToken", sa.Text(), nullable=True),
        sa.Column("password", sa.Text(), nullable=True),
        sa.Column("createdAt", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updatedAt", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_account_userId", "account", ["userId"])

    op.create_table(
        "verification",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("identifier", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("expiresAt", sa.DateTime(), nullable=False),
        sa.Column("createdAt", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updatedAt", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_verification_identifier", "verification", ["identifier"])

    # --- App-owned personalization tables ---
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.String(length=64), primary_key=True),
        sa.Column("riding_name", sa.String(length=255), nullable=True),
        sa.Column("province_code", sa.String(length=8), nullable=True),
        sa.Column("mp_person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("reading_level", sa.String(length=16), nullable=False, server_default="standard"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_user_profiles_mp_person_id", "user_profiles", ["mp_person_id"])

    op.create_table(
        "user_follows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("target_ref", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "target_type", "target_ref", name="uq_user_follow"),
    )
    op.create_index("ix_user_follows_user_id", "user_follows", ["user_id"])
    op.create_index("ix_user_follows_target_type", "user_follows", ["target_type"])


def downgrade() -> None:
    op.drop_table("user_follows")
    op.drop_table("user_profiles")
    op.drop_table("verification")
    op.drop_table("account")
    op.drop_table("session")
    op.drop_table("user")
