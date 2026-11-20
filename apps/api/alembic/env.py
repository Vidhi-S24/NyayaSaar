"""
Alembic environment configuration.
Supports both online (direct DB) and offline (SQL script) modes.
Imports all models so autogenerate can detect them.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure the app package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import Base and all models so alembic sees the metadata
from app.db.base import Base  # noqa: E402
import app.db.models.user  # noqa: F401, E402
import app.db.models.case  # noqa: F401, E402
import app.db.models.document  # noqa: F401, E402
import app.db.models.workflow  # noqa: F401, E402

config = context.config

# Override sqlalchemy.url from environment variable if set
db_sync_url = os.environ.get("DATABASE_SYNC_URL", "")
if db_sync_url:
    config.set_main_option("sqlalchemy.url", db_sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL script)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (direct DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
