"""Initial V0/V1 schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260312_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jurisdictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.Column("name_fr", sa.String(length=255), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_jurisdictions_code", "jurisdictions", ["code"])

    op.create_table(
        "chambers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("jurisdiction_id", sa.Integer(), sa.ForeignKey("jurisdictions.id"), nullable=False),
        sa.Column("slug", sa.String(length=32), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.Column("name_fr", sa.String(length=255), nullable=True),
        sa.Column("is_elected", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("jurisdiction_id", "slug", name="uq_chamber_jurisdiction_slug"),
    )
    op.create_index("ix_chambers_jurisdiction_id", "chambers", ["jurisdiction_id"])
    op.create_index("ix_chambers_slug", "chambers", ["slug"])

    op.create_table(
        "legislature_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("jurisdiction_id", sa.Integer(), sa.ForeignKey("jurisdictions.id"), nullable=False),
        sa.Column("parliament_number", sa.Integer(), nullable=False),
        sa.Column("session_number", sa.Integer(), nullable=False),
        sa.Column("started_on", sa.Date(), nullable=True),
        sa.Column("ended_on", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "jurisdiction_id",
            "parliament_number",
            "session_number",
            name="uq_session_jurisdiction_numbers",
        ),
    )
    op.create_index("ix_legislature_sessions_jurisdiction_id", "legislature_sessions", ["jurisdiction_id"])

    op.create_table(
        "parties",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("jurisdiction_id", sa.Integer(), sa.ForeignKey("jurisdictions.id"), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.Column("name_fr", sa.String(length=255), nullable=True),
        sa.Column("short_name", sa.String(length=64), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("jurisdiction_id", "slug", name="uq_party_jurisdiction_slug"),
    )
    op.create_index("ix_parties_jurisdiction_id", "parties", ["jurisdiction_id"])
    op.create_index("ix_parties_short_name", "parties", ["short_name"])
    op.create_index("ix_parties_slug", "parties", ["slug"])

    op.create_table(
        "people",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chamber_id", sa.Integer(), sa.ForeignKey("chambers.id"), nullable=True),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("given_name", sa.String(length=128), nullable=True),
        sa.Column("family_name", sa.String(length=128), nullable=True),
        sa.Column("honorific", sa.String(length=64), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("website_url", sa.String(length=500), nullable=True),
        sa.Column("bio_en", sa.Text(), nullable=True),
        sa.Column("bio_fr", sa.Text(), nullable=True),
        sa.Column("source_system", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_people_chamber_id", "people", ["chamber_id"])
    op.create_index("ix_people_full_name", "people", ["full_name"])
    op.create_index("ix_people_slug", "people", ["slug"])

    op.create_table(
        "person_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=False),
        sa.Column("party_id", sa.Integer(), sa.ForeignKey("parties.id"), nullable=True),
        sa.Column("chamber_id", sa.Integer(), sa.ForeignKey("chambers.id"), nullable=True),
        sa.Column("riding_name", sa.String(length=255), nullable=True),
        sa.Column("region_name", sa.String(length=255), nullable=True),
        sa.Column("province_code", sa.String(length=8), nullable=True),
        sa.Column("role_title", sa.String(length=255), nullable=True),
        sa.Column("started_on", sa.Date(), nullable=True),
        sa.Column("ended_on", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_person_memberships_person_id", "person_memberships", ["person_id"])
    op.create_index("ix_person_memberships_party_id", "person_memberships", ["party_id"])
    op.create_index("ix_person_memberships_chamber_id", "person_memberships", ["chamber_id"])

    op.create_table(
        "bills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("legislature_sessions.id"), nullable=False),
        sa.Column("chamber_id", sa.Integer(), sa.ForeignKey("chambers.id"), nullable=False),
        sa.Column("sponsor_person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("number", sa.String(length=64), nullable=False),
        sa.Column("short_title_en", sa.String(length=500), nullable=True),
        sa.Column("short_title_fr", sa.String(length=500), nullable=True),
        sa.Column("title_en", sa.String(length=500), nullable=False),
        sa.Column("title_fr", sa.String(length=500), nullable=True),
        sa.Column("status_en", sa.String(length=255), nullable=True),
        sa.Column("status_fr", sa.String(length=255), nullable=True),
        sa.Column("bill_type", sa.String(length=32), nullable=False),
        sa.Column("is_omnibus", sa.Boolean(), nullable=False),
        sa.Column("introduced_on", sa.Date(), nullable=True),
        sa.Column("legisinfo_url", sa.String(length=500), nullable=True),
        sa.Column("summary_source_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("session_id", "number", "chamber_id", name="uq_bill_session_number_chamber"),
    )
    op.create_index("ix_bills_session_id", "bills", ["session_id"])
    op.create_index("ix_bills_chamber_id", "bills", ["chamber_id"])
    op.create_index("ix_bills_sponsor_person_id", "bills", ["sponsor_person_id"])
    op.create_index("ix_bills_number", "bills", ["number"])

    op.create_table(
        "bill_text_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bill_id", sa.Integer(), sa.ForeignKey("bills.id"), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_bill_text_sources_bill_id", "bill_text_sources", ["bill_id"])

    op.create_table(
        "votes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("legislature_sessions.id"), nullable=False),
        sa.Column("chamber_id", sa.Integer(), sa.ForeignKey("chambers.id"), nullable=False),
        sa.Column("bill_id", sa.Integer(), sa.ForeignKey("bills.id"), nullable=True),
        sa.Column("number", sa.String(length=64), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("description_en", sa.Text(), nullable=False),
        sa.Column("description_fr", sa.Text(), nullable=True),
        sa.Column("result", sa.String(length=32), nullable=True),
        sa.Column("yea_total", sa.Integer(), nullable=False),
        sa.Column("nay_total", sa.Integer(), nullable=False),
        sa.Column("paired_total", sa.Integer(), nullable=False),
        sa.Column("vote_type", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("session_id", "chamber_id", "number", name="uq_vote_session_chamber_number"),
    )
    op.create_index("ix_votes_session_id", "votes", ["session_id"])
    op.create_index("ix_votes_chamber_id", "votes", ["chamber_id"])
    op.create_index("ix_votes_bill_id", "votes", ["bill_id"])
    op.create_index("ix_votes_number", "votes", ["number"])
    op.create_index("ix_votes_occurred_on", "votes", ["occurred_on"])

    op.create_table(
        "ballots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vote_id", sa.Integer(), sa.ForeignKey("votes.id"), nullable=False),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=False),
        sa.Column("ballot", sa.String(length=32), nullable=False),
        sa.Column("party_slug", sa.String(length=64), nullable=True),
        sa.Column("broke_party_line", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("vote_id", "person_id", name="uq_ballot_vote_person"),
    )
    op.create_index("ix_ballots_vote_id", "ballots", ["vote_id"])
    op.create_index("ix_ballots_person_id", "ballots", ["person_id"])

    op.create_table(
        "committees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chamber_id", sa.Integer(), sa.ForeignKey("chambers.id"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("legislature_sessions.id"), nullable=True),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.Column("name_fr", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("chamber_id", "slug", name="uq_committee_chamber_slug"),
    )
    op.create_index("ix_committees_chamber_id", "committees", ["chamber_id"])
    op.create_index("ix_committees_session_id", "committees", ["session_id"])
    op.create_index("ix_committees_slug", "committees", ["slug"])

    op.create_table(
        "committee_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("committee_id", sa.Integer(), sa.ForeignKey("committees.id"), nullable=False),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("committee_id", "person_id", name="uq_committee_membership"),
    )
    op.create_index("ix_committee_memberships_committee_id", "committee_memberships", ["committee_id"])
    op.create_index("ix_committee_memberships_person_id", "committee_memberships", ["person_id"])

    op.create_table(
        "committee_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("committee_id", sa.Integer(), sa.ForeignKey("committees.id"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("title_en", sa.String(length=500), nullable=False),
        sa.Column("title_fr", sa.String(length=500), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_committee_events_committee_id", "committee_events", ["committee_id"])

    op.create_table(
        "debates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chamber_id", sa.Integer(), sa.ForeignKey("chambers.id"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("legislature_sessions.id"), nullable=True),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("title_en", sa.String(length=500), nullable=True),
        sa.Column("title_fr", sa.String(length=500), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("chamber_id", "occurred_on", name="uq_debate_chamber_date"),
    )
    op.create_index("ix_debates_chamber_id", "debates", ["chamber_id"])
    op.create_index("ix_debates_session_id", "debates", ["session_id"])
    op.create_index("ix_debates_occurred_on", "debates", ["occurred_on"])

    op.create_table(
        "speeches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("debate_id", sa.Integer(), sa.ForeignKey("debates.id"), nullable=False),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("heading_en", sa.String(length=255), nullable=True),
        sa.Column("heading_fr", sa.String(length=255), nullable=True),
        sa.Column("topic_slug", sa.String(length=255), nullable=True),
        sa.Column("content_en", sa.Text(), nullable=False),
        sa.Column("content_fr", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("debate_id", "sequence", name="uq_speech_debate_sequence"),
    )
    op.create_index("ix_speeches_debate_id", "speeches", ["debate_id"])
    op.create_index("ix_speeches_person_id", "speeches", ["person_id"])

    op.create_table(
        "analysis_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bill_id", sa.Integer(), sa.ForeignKey("bills.id"), nullable=True),
        sa.Column("debate_id", sa.Integer(), sa.ForeignKey("debates.id"), nullable=True),
        sa.Column("analysis_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("citations", sa.JSON(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("bill_id", "debate_id", "analysis_type", "language", name="uq_analysis_scope_type_language"),
    )
    op.create_index("ix_analysis_results_bill_id", "analysis_results", ["bill_id"])
    op.create_index("ix_analysis_results_debate_id", "analysis_results", ["debate_id"])
    op.create_index("ix_analysis_results_analysis_type", "analysis_results", ["analysis_type"])

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("job_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ingestion_runs_source_name", "ingestion_runs", ["source_name"])


def downgrade() -> None:
    op.drop_index("ix_ingestion_runs_source_name", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
    op.drop_index("ix_analysis_results_analysis_type", table_name="analysis_results")
    op.drop_index("ix_analysis_results_debate_id", table_name="analysis_results")
    op.drop_index("ix_analysis_results_bill_id", table_name="analysis_results")
    op.drop_table("analysis_results")
    op.drop_index("ix_speeches_person_id", table_name="speeches")
    op.drop_index("ix_speeches_debate_id", table_name="speeches")
    op.drop_table("speeches")
    op.drop_index("ix_debates_occurred_on", table_name="debates")
    op.drop_index("ix_debates_session_id", table_name="debates")
    op.drop_index("ix_debates_chamber_id", table_name="debates")
    op.drop_table("debates")
    op.drop_index("ix_committee_events_committee_id", table_name="committee_events")
    op.drop_table("committee_events")
    op.drop_index("ix_committee_memberships_person_id", table_name="committee_memberships")
    op.drop_index("ix_committee_memberships_committee_id", table_name="committee_memberships")
    op.drop_table("committee_memberships")
    op.drop_index("ix_committees_slug", table_name="committees")
    op.drop_index("ix_committees_session_id", table_name="committees")
    op.drop_index("ix_committees_chamber_id", table_name="committees")
    op.drop_table("committees")
    op.drop_index("ix_ballots_person_id", table_name="ballots")
    op.drop_index("ix_ballots_vote_id", table_name="ballots")
    op.drop_table("ballots")
    op.drop_index("ix_votes_occurred_on", table_name="votes")
    op.drop_index("ix_votes_number", table_name="votes")
    op.drop_index("ix_votes_bill_id", table_name="votes")
    op.drop_index("ix_votes_chamber_id", table_name="votes")
    op.drop_index("ix_votes_session_id", table_name="votes")
    op.drop_table("votes")
    op.drop_index("ix_bill_text_sources_bill_id", table_name="bill_text_sources")
    op.drop_table("bill_text_sources")
    op.drop_index("ix_bills_number", table_name="bills")
    op.drop_index("ix_bills_sponsor_person_id", table_name="bills")
    op.drop_index("ix_bills_chamber_id", table_name="bills")
    op.drop_index("ix_bills_session_id", table_name="bills")
    op.drop_table("bills")
    op.drop_index("ix_person_memberships_chamber_id", table_name="person_memberships")
    op.drop_index("ix_person_memberships_party_id", table_name="person_memberships")
    op.drop_index("ix_person_memberships_person_id", table_name="person_memberships")
    op.drop_table("person_memberships")
    op.drop_index("ix_people_slug", table_name="people")
    op.drop_index("ix_people_full_name", table_name="people")
    op.drop_index("ix_people_chamber_id", table_name="people")
    op.drop_table("people")
    op.drop_index("ix_parties_slug", table_name="parties")
    op.drop_index("ix_parties_short_name", table_name="parties")
    op.drop_index("ix_parties_jurisdiction_id", table_name="parties")
    op.drop_table("parties")
    op.drop_index("ix_legislature_sessions_jurisdiction_id", table_name="legislature_sessions")
    op.drop_table("legislature_sessions")
    op.drop_index("ix_chambers_slug", table_name="chambers")
    op.drop_index("ix_chambers_jurisdiction_id", table_name="chambers")
    op.drop_table("chambers")
    op.drop_index("ix_jurisdictions_code", table_name="jurisdictions")
    op.drop_table("jurisdictions")
