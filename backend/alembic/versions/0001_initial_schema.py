"""Initial schema for email-based PetroMatch MVP."""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("emails_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emails_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emails_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_skipped_duplicate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ingestion_runs_source"), "ingestion_runs", ["source"], unique=False)
    op.create_index(op.f("ix_ingestion_runs_status"), "ingestion_runs", ["status"], unique=False)

    op.create_table(
        "processed_emails",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("gmail_message_id", sa.String(length=255), nullable=False),
        sa.Column("gmail_thread_id", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("sender", sa.Text(), nullable=True),
        sa.Column("recipients", sa.JSON(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("received_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_html_body", sa.Text(), nullable=True),
        sa.Column("plain_text_body", sa.Text(), nullable=True),
        sa.Column("raw_mime", sa.Text(), nullable=True),
        sa.Column("headers", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ingested"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("extraction_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("jobs_extracted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parsing_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gmail_message_id"),
    )
    op.create_index(op.f("ix_processed_emails_gmail_message_id"), "processed_emails", ["gmail_message_id"], unique=False)
    op.create_index(op.f("ix_processed_emails_gmail_thread_id"), "processed_emails", ["gmail_thread_id"], unique=False)
    op.create_index(op.f("ix_processed_emails_extraction_status"), "processed_emails", ["extraction_status"], unique=False)
    op.create_index(op.f("ix_processed_emails_received_date"), "processed_emails", ["received_date"], unique=False)
    op.create_index(op.f("ix_processed_emails_source"), "processed_emails", ["source"], unique=False)
    op.create_index(op.f("ix_processed_emails_status"), "processed_emails", ["status"], unique=False)

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("processed_email_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("job_url", sa.Text(), nullable=True),
        sa.Column("dedupe_fingerprint", sa.String(length=255), nullable=True),
        sa.Column("job_title", sa.String(length=512), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("posted_date", sa.Date(), nullable=True),
        sa.Column("received_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("source_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["processed_email_id"], ["processed_emails.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_fingerprint"),
        sa.UniqueConstraint("job_url"),
        sa.UniqueConstraint("source", "external_id", name="uq_jobs_source_external_id"),
    )
    op.create_index(op.f("ix_jobs_company"), "jobs", ["company"], unique=False)
    op.create_index(op.f("ix_jobs_external_id"), "jobs", ["external_id"], unique=False)
    op.create_index(op.f("ix_jobs_job_title"), "jobs", ["job_title"], unique=False)
    op.create_index(op.f("ix_jobs_location"), "jobs", ["location"], unique=False)
    op.create_index(op.f("ix_jobs_posted_date"), "jobs", ["posted_date"], unique=False)
    op.create_index(op.f("ix_jobs_processed_email_id"), "jobs", ["processed_email_id"], unique=False)
    op.create_index(op.f("ix_jobs_received_date"), "jobs", ["received_date"], unique=False)
    op.create_index(op.f("ix_jobs_source"), "jobs", ["source"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_jobs_source"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_received_date"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_processed_email_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_posted_date"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_location"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_job_title"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_external_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_company"), table_name="jobs")
    op.drop_table("jobs")
    op.drop_index(op.f("ix_processed_emails_status"), table_name="processed_emails")
    op.drop_index(op.f("ix_processed_emails_source"), table_name="processed_emails")
    op.drop_index(op.f("ix_processed_emails_received_date"), table_name="processed_emails")
    op.drop_index(op.f("ix_processed_emails_extraction_status"), table_name="processed_emails")
    op.drop_index(op.f("ix_processed_emails_gmail_thread_id"), table_name="processed_emails")
    op.drop_index(op.f("ix_processed_emails_gmail_message_id"), table_name="processed_emails")
    op.drop_table("processed_emails")
    op.drop_index(op.f("ix_ingestion_runs_status"), table_name="ingestion_runs")
    op.drop_index(op.f("ix_ingestion_runs_source"), table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
