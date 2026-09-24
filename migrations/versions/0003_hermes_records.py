"""Add source-native and normalized conversation records.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create immutable snapshot references and source-native records."""
    op.create_table(
        "native_snapshots",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("import_batch_id", sa.String(length=255), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("byte_length", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(id)) > 0", name="ck_native_snapshots_id_nonblank"
        ),
        sa.CheckConstraint(
            "length(trim(content_sha256)) = 64",
            name="ck_native_snapshots_hash_length",
        ),
        sa.CheckConstraint(
            "byte_length >= 0", name="ck_native_snapshots_byte_length_nonnegative"
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["import_batches.id"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id", "content_sha256", name="uq_native_snapshots_source_hash"
        ),
    )
    op.create_index("ix_native_snapshots_source_id", "native_snapshots", ["source_id"])
    op.create_index(
        "ix_native_snapshots_import_batch_id",
        "native_snapshots",
        ["import_batch_id"],
    )

    op.create_table(
        "native_sessions",
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("native_id", sa.String(length=255), nullable=False),
        sa.Column("parent_native_id", sa.String(length=255), nullable=True),
        sa.Column("source_version", sa.String(length=255), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("application_version", sa.String(length=255), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("snapshot_id", sa.String(length=255), nullable=False),
        sa.Column(
            "source_present", sa.Boolean(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "length(trim(native_id)) > 0", name="ck_native_sessions_id_nonblank"
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["native_snapshots.id"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("source_id", "native_id"),
    )

    op.create_table(
        "native_messages",
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("native_id", sa.String(length=255), nullable=False),
        sa.Column("native_order", sa.Integer(), nullable=False),
        sa.Column("session_native_id", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("tool_call_id", sa.String(length=255), nullable=True),
        sa.Column("tool_name", sa.String(length=255), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("source_timestamp", sa.Float(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("snapshot_id", sa.String(length=255), nullable=False),
        sa.Column(
            "source_present", sa.Boolean(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "length(trim(native_id)) > 0", name="ck_native_messages_id_nonblank"
        ),
        sa.CheckConstraint(
            "length(trim(session_native_id)) > 0",
            name="ck_native_messages_session_nonblank",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["native_snapshots.id"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_id", "session_native_id"],
            ["native_sessions.source_id", "native_sessions.native_id"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("source_id", "native_id"),
    )
    op.create_index(
        "ix_native_messages_source_session",
        "native_messages",
        ["source_id", "session_native_id", "native_order"],
    )

    op.create_table(
        "native_usages",
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("session_native_id", sa.String(length=255), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("billing_provider", sa.String(length=255), nullable=False),
        sa.Column("billing_base_url", sa.String(length=1024), nullable=False),
        sa.Column("billing_mode", sa.String(length=255), nullable=False),
        sa.Column("task", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("snapshot_id", sa.String(length=255), nullable=False),
        sa.Column(
            "source_present", sa.Boolean(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "length(trim(session_native_id)) > 0",
            name="ck_native_usages_session_nonblank",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["native_snapshots.id"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_id", "session_native_id"],
            ["native_sessions.source_id", "native_sessions.native_id"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "source_id",
            "session_native_id",
            "model",
            "billing_provider",
            "billing_base_url",
            "billing_mode",
            "task",
        ),
    )

    op.create_table(
        "conversation_revisions",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("native_id", sa.String(length=255), nullable=False),
        sa.Column("revision", sa.String(length=64), nullable=False),
        sa.Column("snapshot_id", sa.String(length=255), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(id)) > 0", name="ck_conversation_revisions_id_nonblank"
        ),
        sa.CheckConstraint(
            "length(trim(native_id)) > 0",
            name="ck_conversation_revisions_native_id_nonblank",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["native_snapshots.id"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "native_id",
            "revision",
            name="uq_conversation_revisions_source_native_revision",
        ),
    )
    op.create_index(
        "ix_conversation_revisions_source_id",
        "conversation_revisions",
        ["source_id"],
    )

    op.create_table(
        "source_presence",
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("batch_id", sa.String(length=255), nullable=False),
        sa.Column("subject_kind", sa.String(length=64), nullable=False),
        sa.Column("native_id", sa.String(length=255), nullable=False),
        sa.Column("present", sa.Boolean(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["import_batches.id"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("source_id", "batch_id", "subject_kind", "native_id"),
    )

    op.create_table(
        "source_import_states",
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("adapter_version", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("cursor", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(adapter_version)) > 0",
            name="ck_source_import_states_adapter_nonblank",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("source_id"),
    )


def downgrade() -> None:
    """Remove source-native and normalized conversation records."""
    op.drop_table("source_import_states")
    op.drop_table("source_presence")
    op.drop_index(
        "ix_conversation_revisions_source_id", table_name="conversation_revisions"
    )
    op.drop_table("conversation_revisions")
    op.drop_table("native_usages")
    op.drop_index("ix_native_messages_source_session", table_name="native_messages")
    op.drop_table("native_messages")
    op.drop_table("native_sessions")
    op.drop_index("ix_native_snapshots_import_batch_id", table_name="native_snapshots")
    op.drop_index("ix_native_snapshots_source_id", table_name="native_snapshots")
    op.drop_table("native_snapshots")
