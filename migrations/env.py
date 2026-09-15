"""Run Alembic migrations against Benchwarmer's configured SQLite database."""

from __future__ import annotations

from alembic import context

from benchwarmer.config import BenchwarmerSettings
from benchwarmer.db import create_engine, database_url
from benchwarmer.models import Base


config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Render SQL without opening the configured database."""
    settings = BenchwarmerSettings.from_environment()
    context.configure(
        url=database_url(settings),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations through the configured private SQLite database."""
    settings = BenchwarmerSettings.from_environment()
    connectable = create_engine(settings)

    try:
        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)

            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
