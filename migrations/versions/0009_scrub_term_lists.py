"""Add named, versioned scrub term lists.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create immutable term list versions keyed by name and version."""
    op.create_table(
        "scrub_term_lists",
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("terms", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_scrub_term_lists_name"),
        sa.CheckConstraint("version >= 1", name="ck_scrub_term_lists_version"),
        sa.PrimaryKeyConstraint("name", "version"),
    )


def downgrade() -> None:
    """Drop the term lists; the terms are operator data and are not kept."""
    op.drop_table("scrub_term_lists")
