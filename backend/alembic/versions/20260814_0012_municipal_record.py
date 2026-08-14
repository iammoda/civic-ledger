"""Municipal meeting record: meetings, attendance, motions, conflict
declarations (eScribe minutes + Toronto/Vancouver open data)."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260814_0012"
down_revision = "20260814_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meetings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chamber_id", sa.Integer(), sa.ForeignKey("chambers.id"), nullable=False),
        sa.Column("body_name", sa.String(255), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meeting_date", sa.Date(), nullable=False),
        sa.Column("source_system", sa.String(32), nullable=False, server_default="escribe"),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("minutes_url", sa.String(500), nullable=True),
        sa.Column("minutes_parsed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_system", "source_id", name="uq_meeting_source"),
    )
    op.create_index("ix_meetings_chamber_id", "meetings", ["chamber_id"])
    op.create_index("ix_meetings_meeting_date", "meetings", ["meeting_date"])

    op.create_table(
        "meeting_attendance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="present"),
        sa.Column("source_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("meeting_id", "person_id", name="uq_attendance_meeting_person"),
    )
    op.create_index("ix_meeting_attendance_meeting_id", "meeting_attendance", ["meeting_id"])
    op.create_index("ix_meeting_attendance_person_id", "meeting_attendance", ["person_id"])

    op.create_table(
        "motions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolution_number", sa.String(64), nullable=True),
        sa.Column("item_number", sa.String(64), nullable=True),
        sa.Column("item_title", sa.String(500), nullable=True),
        sa.Column("text_en", sa.Text(), nullable=False, server_default=""),
        sa.Column("mover_person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("seconder_person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("result", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("vote_id", sa.Integer(), sa.ForeignKey("votes.id"), nullable=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("meeting_id", "sequence", name="uq_motion_meeting_sequence"),
    )
    op.create_index("ix_motions_meeting_id", "motions", ["meeting_id"])
    op.create_index("ix_motions_resolution_number", "motions", ["resolution_number"])
    op.create_index("ix_motions_mover_person_id", "motions", ["mover_person_id"])
    op.create_index("ix_motions_seconder_person_id", "motions", ["seconder_person_id"])
    op.create_index("ix_motions_vote_id", "motions", ["vote_id"])

    op.create_table(
        "conflict_declarations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("meeting_id", sa.Integer(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("person_name", sa.String(255), nullable=True),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("meeting_id", "person_name", "note", name="uq_declaration_meeting_person_note"),
    )
    op.create_index("ix_conflict_declarations_meeting_id", "conflict_declarations", ["meeting_id"])
    op.create_index("ix_conflict_declarations_person_id", "conflict_declarations", ["person_id"])


def downgrade() -> None:
    op.drop_table("conflict_declarations")
    op.drop_table("motions")
    op.drop_table("meeting_attendance")
    op.drop_table("meetings")
