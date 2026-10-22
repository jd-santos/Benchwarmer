"""Record run provenance on bundle revisions and a creation request id.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add optional provenance to revisions and an idempotency key to bundles."""
    with op.batch_alter_table("evidence_bundle_revisions") as batch:
        batch.add_column(sa.Column("provenance", sa.JSON(), nullable=True))
    with op.batch_alter_table("evidence_bundles") as batch:
        batch.add_column(sa.Column("request_id", sa.String(length=255), nullable=True))
        batch.create_index(
            "ix_evidence_bundles_request_id", ["request_id"], unique=True
        )


def downgrade() -> None:
    """Drop the idempotency key and provenance columns."""
    with op.batch_alter_table("evidence_bundles") as batch:
        batch.drop_index("ix_evidence_bundles_request_id")
        batch.drop_column("request_id")
    with op.batch_alter_table("evidence_bundle_revisions") as batch:
        batch.drop_column("provenance")
