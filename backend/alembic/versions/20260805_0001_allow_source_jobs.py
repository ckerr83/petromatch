"""allow non-email source jobs

Revision ID: 20260805_0001
Revises: d467377c0b1b
Create Date: 2026-08-05 10:05:00.000000
"""
from alembic import op


revision = "20260805_0001"
down_revision = "d467377c0b1b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("jobs", "processed_email_id", nullable=True)


def downgrade() -> None:
    op.alter_column("jobs", "processed_email_id", nullable=False)
