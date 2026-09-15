"""Add configured source identities.

Revision ID: 0001
Revises:
Create Date: 2026-09-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create durable configured source identities."""
    op.create_table(
        "sources",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=128), nullable=False),
        sa.Column("scope_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("configured_coverage", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(id)) > 0", name="ck_sources_id_nonblank"),
        sa.CheckConstraint("length(trim(kind)) > 0", name="ck_sources_kind_nonblank"),
        sa.CheckConstraint(
            "length(trim(scope_id)) > 0", name="ck_sources_scope_id_nonblank"
        ),
        sa.CheckConstraint(
            "length(trim(display_name)) > 0", name="ck_sources_display_name_nonblank"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "scope_id", name="uq_sources_kind_scope_id"),
    )
    op.execute(
        """
        CREATE TRIGGER sources_configured_coverage_validate_insert
        BEFORE INSERT ON sources
        FOR EACH ROW WHEN NEW.configured_coverage IS NOT NULL
        BEGIN
            SELECT CASE WHEN json_valid(NEW.configured_coverage) = 0
                THEN RAISE(ABORT, 'invalid configured coverage') END;
            SELECT CASE WHEN json_type(NEW.configured_coverage) <> 'object'
                THEN RAISE(ABORT, 'invalid configured coverage') END;
            SELECT CASE WHEN json_type(NEW.configured_coverage, '$.schema_version')
                <> 'integer'
                OR json_extract(NEW.configured_coverage, '$.schema_version') <> 1
                THEN RAISE(ABORT, 'invalid configured coverage') END;
            SELECT CASE WHEN json_type(NEW.configured_coverage, '$.dimensions')
                <> 'object'
                THEN RAISE(ABORT, 'invalid configured coverage') END;
            SELECT CASE WHEN (SELECT count(*) FROM json_each(NEW.configured_coverage))
                <> 2
                OR (SELECT count(*) FROM json_each(NEW.configured_coverage)
                    WHERE key = 'schema_version') <> 1
                OR (SELECT count(*) FROM json_each(NEW.configured_coverage)
                    WHERE key = 'dimensions') <> 1
                OR EXISTS (
                    SELECT 1 FROM json_each(NEW.configured_coverage)
                    WHERE key NOT IN ('schema_version', 'dimensions')
                )
                THEN RAISE(ABORT, 'invalid configured coverage') END;
            SELECT CASE WHEN (
                SELECT count(*)
                FROM json_each(NEW.configured_coverage, '$.dimensions')
            ) > 64
                OR EXISTS (
                    SELECT 1 FROM json_each(NEW.configured_coverage, '$.dimensions')
                    GROUP BY key HAVING count(*) <> 1
                )
                OR EXISTS (
                    SELECT 1 FROM json_each(NEW.configured_coverage, '$.dimensions')
                    WHERE length(trim(key)) = 0 OR length(key) > 128
                )
                OR EXISTS (
                    SELECT 1 FROM json_each(NEW.configured_coverage, '$.dimensions')
                    WHERE type <> 'text'
                    OR value NOT IN ('available', 'partial', 'unavailable', 'unknown')
                )
                THEN RAISE(ABORT, 'invalid configured coverage') END;
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER sources_configured_coverage_validate_update
        BEFORE UPDATE OF configured_coverage ON sources
        FOR EACH ROW WHEN NEW.configured_coverage IS NOT NULL
        BEGIN
            SELECT CASE WHEN json_valid(NEW.configured_coverage) = 0
                THEN RAISE(ABORT, 'invalid configured coverage') END;
            SELECT CASE WHEN json_type(NEW.configured_coverage) <> 'object'
                THEN RAISE(ABORT, 'invalid configured coverage') END;
            SELECT CASE WHEN json_type(NEW.configured_coverage, '$.schema_version')
                <> 'integer'
                OR json_extract(NEW.configured_coverage, '$.schema_version') <> 1
                THEN RAISE(ABORT, 'invalid configured coverage') END;
            SELECT CASE WHEN json_type(NEW.configured_coverage, '$.dimensions')
                <> 'object'
                THEN RAISE(ABORT, 'invalid configured coverage') END;
            SELECT CASE WHEN (SELECT count(*) FROM json_each(NEW.configured_coverage))
                <> 2
                OR (SELECT count(*) FROM json_each(NEW.configured_coverage)
                    WHERE key = 'schema_version') <> 1
                OR (SELECT count(*) FROM json_each(NEW.configured_coverage)
                    WHERE key = 'dimensions') <> 1
                OR EXISTS (
                    SELECT 1 FROM json_each(NEW.configured_coverage)
                    WHERE key NOT IN ('schema_version', 'dimensions')
                )
                THEN RAISE(ABORT, 'invalid configured coverage') END;
            SELECT CASE WHEN (
                SELECT count(*)
                FROM json_each(NEW.configured_coverage, '$.dimensions')
            ) > 64
                OR EXISTS (
                    SELECT 1 FROM json_each(NEW.configured_coverage, '$.dimensions')
                    GROUP BY key HAVING count(*) <> 1
                )
                OR EXISTS (
                    SELECT 1 FROM json_each(NEW.configured_coverage, '$.dimensions')
                    WHERE length(trim(key)) = 0 OR length(key) > 128
                )
                OR EXISTS (
                    SELECT 1 FROM json_each(NEW.configured_coverage, '$.dimensions')
                    WHERE type <> 'text'
                    OR value NOT IN ('available', 'partial', 'unavailable', 'unknown')
                )
                THEN RAISE(ABORT, 'invalid configured coverage') END;
        END
        """
    )


def downgrade() -> None:
    """Remove configured source identities."""
    op.execute("DROP TRIGGER sources_configured_coverage_validate_update")
    op.execute("DROP TRIGGER sources_configured_coverage_validate_insert")
    op.drop_table("sources")
