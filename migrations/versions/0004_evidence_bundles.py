"""Add evidence bundles and their immutable revisions.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create bundle identities and numbered revision documents."""
    op.create_table(
        "evidence_bundles",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("latest_revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "length(trim(id)) > 0", name="ck_evidence_bundles_id_nonblank"
        ),
        sa.CheckConstraint(
            "latest_revision >= 1", name="ck_evidence_bundles_latest_positive"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "evidence_bundle_revisions",
        sa.Column("bundle_id", sa.String(length=255), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("producer", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("number >= 1", name="ck_evidence_bundle_revisions_number"),
        sa.CheckConstraint(
            "origin IN ('human', 'generated')",
            name="ck_evidence_bundle_revisions_origin",
        ),
        sa.ForeignKeyConstraint(
            ["bundle_id"],
            ["evidence_bundles.id"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("bundle_id", "number"),
    )


def downgrade() -> None:
    """Drop bundle revisions before their identities."""
    op.drop_table("evidence_bundle_revisions")
    op.drop_table("evidence_bundles")
