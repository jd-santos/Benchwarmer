"""Add durable import attempts.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _validation_trigger(name: str, event: str) -> str:
    return f"""
        CREATE TRIGGER {name}
        BEFORE {event} ON import_batches
        FOR EACH ROW
        BEGIN
            SELECT CASE WHEN NEW.cursor_before IS NOT NULL
                AND json_valid(NEW.cursor_before) = 0
                THEN RAISE(ABORT, 'invalid import cursor') END;
            SELECT CASE WHEN NEW.cursor_before IS NOT NULL AND (
                json_type(NEW.cursor_before) <> 'object'
                OR json_type(NEW.cursor_before, '$.schema_version') <> 'integer'
                OR json_extract(NEW.cursor_before, '$.schema_version') <> 1
                OR (SELECT count(*) FROM json_each(NEW.cursor_before)) <> 2
                OR (SELECT count(*) FROM json_each(NEW.cursor_before)
                    WHERE key = 'schema_version') <> 1
                OR (SELECT count(*) FROM json_each(NEW.cursor_before)
                    WHERE key = 'value') <> 1
                OR EXISTS (SELECT 1 FROM json_each(NEW.cursor_before)
                    WHERE key NOT IN ('schema_version', 'value'))
                OR length(CAST(NEW.cursor_before AS BLOB)) > 16384
            ) THEN RAISE(ABORT, 'invalid import cursor') END;

            SELECT CASE WHEN NEW.cursor_after IS NOT NULL
                AND json_valid(NEW.cursor_after) = 0
                THEN RAISE(ABORT, 'invalid import cursor') END;
            SELECT CASE WHEN NEW.cursor_after IS NOT NULL AND (
                json_type(NEW.cursor_after) <> 'object'
                OR json_type(NEW.cursor_after, '$.schema_version') <> 'integer'
                OR json_extract(NEW.cursor_after, '$.schema_version') <> 1
                OR (SELECT count(*) FROM json_each(NEW.cursor_after)) <> 2
                OR (SELECT count(*) FROM json_each(NEW.cursor_after)
                    WHERE key = 'schema_version') <> 1
                OR (SELECT count(*) FROM json_each(NEW.cursor_after)
                    WHERE key = 'value') <> 1
                OR EXISTS (SELECT 1 FROM json_each(NEW.cursor_after)
                    WHERE key NOT IN ('schema_version', 'value'))
                OR length(CAST(NEW.cursor_after AS BLOB)) > 16384
            ) THEN RAISE(ABORT, 'invalid import cursor') END;

            SELECT CASE WHEN NEW.observed_coverage IS NOT NULL
                AND json_valid(NEW.observed_coverage) = 0
                THEN RAISE(ABORT, 'invalid import coverage') END;
            SELECT CASE WHEN NEW.observed_coverage IS NOT NULL AND (
                json_type(NEW.observed_coverage) <> 'object'
                OR json_type(NEW.observed_coverage, '$.schema_version') <> 'integer'
                OR json_extract(NEW.observed_coverage, '$.schema_version') <> 1
                OR json_type(NEW.observed_coverage, '$.dimensions') <> 'object'
                OR (SELECT count(*) FROM json_each(NEW.observed_coverage)) <> 2
                OR (SELECT count(*) FROM json_each(NEW.observed_coverage)
                    WHERE key = 'schema_version') <> 1
                OR (SELECT count(*) FROM json_each(NEW.observed_coverage)
                    WHERE key = 'dimensions') <> 1
                OR EXISTS (SELECT 1 FROM json_each(NEW.observed_coverage)
                    WHERE key NOT IN ('schema_version', 'dimensions'))
                OR (SELECT count(*) FROM json_each(
                    NEW.observed_coverage, '$.dimensions')) > 64
                OR EXISTS (
                    SELECT 1 FROM json_each(
                        NEW.observed_coverage, '$.dimensions')
                    GROUP BY key HAVING count(*) <> 1
                )
                OR EXISTS (
                    SELECT 1 FROM json_each(
                        NEW.observed_coverage, '$.dimensions')
                    WHERE length(trim(key)) = 0 OR length(key) > 128
                )
                OR EXISTS (
                    SELECT 1 FROM json_each(
                        NEW.observed_coverage, '$.dimensions')
                    WHERE type <> 'text'
                    OR value NOT IN (
                        'available', 'partial', 'unavailable', 'unknown', 'redacted'
                    )
                )
            ) THEN RAISE(ABORT, 'invalid import coverage') END;
        END
    """


def upgrade() -> None:
    """Create durable, source-linked import attempts."""
    op.create_table(
        "import_batches",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("cursor_before", sa.JSON(), nullable=True),
        sa.Column("cursor_after", sa.JSON(), nullable=True),
        sa.Column("observed_coverage", sa.JSON(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "length(trim(id)) > 0", name="ck_import_batches_id_nonblank"
        ),
        sa.CheckConstraint(
            "length(trim(source_id)) > 0",
            name="ck_import_batches_source_id_nonblank",
        ),
        sa.CheckConstraint(
            "length(trim(idempotency_key)) > 0",
            name="ck_import_batches_idempotency_key_nonblank",
        ),
        sa.CheckConstraint(
            "outcome IN ('failed', 'partial', 'succeeded')",
            name="ck_import_batches_outcome",
        ),
        sa.CheckConstraint(
            "completed_at >= started_at",
            name="ck_import_batches_timestamp_order",
        ),
        sa.CheckConstraint(
            "error_summary IS NULL OR "
            "(length(trim(error_summary)) > 0 AND length(error_summary) <= 2000)",
            name="ck_import_batches_error_summary",
        ),
        sa.CheckConstraint(
            "(outcome = 'failed' AND error_summary IS NOT NULL) OR "
            "(outcome = 'partial') OR "
            "(outcome = 'succeeded' AND error_summary IS NULL)",
            name="ck_import_batches_error_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "idempotency_key",
            name="uq_import_batches_source_idempotency_key",
        ),
    )
    op.create_index(
        "ix_import_batches_source_id", "import_batches", ["source_id"], unique=False
    )
    op.execute(_validation_trigger("import_batches_validate_insert", "INSERT"))
    op.execute(
        _validation_trigger(
            "import_batches_validate_update",
            "UPDATE OF cursor_before, cursor_after, observed_coverage",
        )
    )


def downgrade() -> None:
    """Remove durable import attempts."""
    op.execute("DROP TRIGGER import_batches_validate_update")
    op.execute("DROP TRIGGER import_batches_validate_insert")
    op.drop_index("ix_import_batches_source_id", table_name="import_batches")
    op.drop_table("import_batches")
