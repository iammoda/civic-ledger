"""Phase 1: pipeline schema — outcomes, deaths, roles, topics, embeddings.

- bills: legisinfo_id, text_url, status_code, is_law, outcome
- votes: yea_effect, plain_meaning_en (direction normalization slots)
- new tables: bill_deaths, person_roles, representation_events, topics,
  entity_topics, embeddings (pgvector), documents, person_stats
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "20260810_0002"
down_revision = "20260312_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- bills: lifecycle columns ---
    op.add_column("bills", sa.Column("legisinfo_id", sa.Integer(), nullable=True))
    op.add_column("bills", sa.Column("text_url", sa.String(length=500), nullable=True))
    op.add_column("bills", sa.Column("status_code", sa.String(length=64), nullable=True))
    op.add_column("bills", sa.Column("is_law", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column(
        "bills",
        sa.Column("outcome", sa.String(length=32), nullable=False, server_default="pending"),
    )
    op.create_index("ix_bills_legisinfo_id", "bills", ["legisinfo_id"])
    op.create_index("ix_bills_status_code", "bills", ["status_code"])
    op.create_index("ix_bills_outcome", "bills", ["outcome"])

    # --- votes: direction normalization slots ---
    op.add_column("votes", sa.Column("yea_effect", sa.String(length=16), nullable=True))
    op.add_column("votes", sa.Column("plain_meaning_en", sa.Text(), nullable=True))

    op.create_table(
        "bill_deaths",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bill_id", sa.Integer(), sa.ForeignKey("bills.id"), nullable=False),
        sa.Column("mechanism", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=True),
        sa.Column("occurred_on", sa.Date(), nullable=True),
        sa.Column("kill_vote_id", sa.Integer(), sa.ForeignKey("votes.id"), nullable=True),
        sa.Column("committee_id", sa.Integer(), sa.ForeignKey("committees.id"), nullable=True),
        sa.Column("attribution_en", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("bill_id"),
    )
    op.create_index("ix_bill_deaths_bill_id", "bill_deaths", ["bill_id"])
    op.create_index("ix_bill_deaths_mechanism", "bill_deaths", ["mechanism"])
    op.create_index("ix_bill_deaths_kill_vote_id", "bill_deaths", ["kill_vote_id"])
    op.create_index("ix_bill_deaths_committee_id", "bill_deaths", ["committee_id"])

    op.create_table(
        "person_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=False),
        sa.Column("role_type", sa.String(length=32), nullable=False),
        sa.Column("title_en", sa.String(length=255), nullable=False),
        sa.Column("title_fr", sa.String(length=255), nullable=True),
        sa.Column("portfolio_slug", sa.String(length=128), nullable=True),
        sa.Column("started_on", sa.Date(), nullable=True),
        sa.Column("ended_on", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("person_id", "role_type", "title_en", "started_on", name="uq_person_role"),
    )
    op.create_index("ix_person_roles_person_id", "person_roles", ["person_id"])
    op.create_index("ix_person_roles_role_type", "person_roles", ["role_type"])
    op.create_index("ix_person_roles_portfolio_slug", "person_roles", ["portfolio_slug"])
    op.create_index("ix_person_roles_is_current", "person_roles", ["is_current"])

    op.create_table(
        "representation_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=True),
        sa.Column("from_party_id", sa.Integer(), sa.ForeignKey("parties.id"), nullable=True),
        sa.Column("to_party_id", sa.Integer(), sa.ForeignKey("parties.id"), nullable=True),
        sa.Column("details_en", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("person_id", "event_type", "occurred_on", name="uq_representation_event"),
    )
    op.create_index("ix_representation_events_person_id", "representation_events", ["person_id"])
    op.create_index("ix_representation_events_event_type", "representation_events", ["event_type"])
    op.create_index("ix_representation_events_occurred_on", "representation_events", ["occurred_on"])

    op.create_table(
        "topics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name_en", sa.String(length=128), nullable=False),
        sa.Column("name_fr", sa.String(length=128), nullable=True),
        sa.Column("description_en", sa.Text(), nullable=True),
        sa.Column("aliases_en", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_topics_slug", "topics", ["slug"])

    op.create_table(
        "entity_topics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="llm"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("topic_id", "entity_type", "entity_id", name="uq_entity_topic"),
    )
    op.create_index("ix_entity_topics_topic_id", "entity_topics", ["topic_id"])
    op.create_index("ix_entity_topics_entity", "entity_topics", ["entity_type", "entity_id"])

    op.create_table(
        "embeddings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("vector", Vector(1536), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("entity_type", "entity_id", name="uq_embedding_entity"),
    )
    op.create_index("ix_embeddings_entity", "embeddings", ["entity_type", "entity_id"])
    # HNSW index for cosine similarity search.
    op.execute(
        "CREATE INDEX ix_embeddings_vector_hnsw ON embeddings "
        "USING hnsw (vector vector_cosine_ops)"
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_system", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_documents_source_system", "documents", ["source_system"])
    op.create_index("ix_documents_document_type", "documents", ["document_type"])
    op.create_index("ix_documents_entity", "documents", ["entity_type", "entity_id"])

    op.create_table(
        "person_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("people.id"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("legislature_sessions.id"), nullable=False),
        sa.Column("votes_eligible", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("votes_cast", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attendance_pct", sa.Float(), nullable=True),
        sa.Column("party_line_pct", sa.Float(), nullable=True),
        sa.Column("dissent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("computed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("person_id", "session_id", name="uq_person_stats_session"),
    )
    op.create_index("ix_person_stats_person_id", "person_stats", ["person_id"])
    op.create_index("ix_person_stats_session_id", "person_stats", ["session_id"])


def downgrade() -> None:
    op.drop_table("person_stats")
    op.drop_table("documents")
    op.drop_table("embeddings")
    op.drop_table("entity_topics")
    op.drop_table("topics")
    op.drop_table("representation_events")
    op.drop_table("person_roles")
    op.drop_table("bill_deaths")
    op.drop_column("votes", "plain_meaning_en")
    op.drop_column("votes", "yea_effect")
    op.drop_column("bills", "outcome")
    op.drop_column("bills", "is_law")
    op.drop_column("bills", "status_code")
    op.drop_column("bills", "text_url")
    op.drop_column("bills", "legisinfo_id")
