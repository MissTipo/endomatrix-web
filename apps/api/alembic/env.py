"""
alembic/env.py

Alembic migration environment.

Reads DATABASE_URL from the environment. Imports the shared SQLAlchemy
metadata from infrastructure.orm.tables so Alembic can generate and
apply migrations against the real schema.

To generate a new migration after changing tables.py:
    alembic revision --autogenerate -m "describe your change"

To apply all pending migrations:
    alembic upgrade head

To roll back one step:
    alembic downgrade -1
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the api/ package importable from the alembic/ directory
api_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(api_root))

# Load .env from apps/api/ automatically so DATABASE_URL does not need
# to be manually exported in the shell before running alembic commands.
try:
    from dotenv import load_dotenv
    load_dotenv(api_root / ".env")
except ImportError:
    pass  # python-dotenv not installed — fall back to shell environment

from infrastructure.orm.tables import metadata  # noqa: E402

config = context.config

# Wire in DATABASE_URL. Fail with a clear message if it is missing.
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError(
        "DATABASE_URL is not set.\n"
        "Either:\n"
        "  1. Copy apps/api/.env.example to apps/api/.env and fill in the value, or\n"
        "  2. Export it in your shell: export DATABASE_URL=postgresql+psycopg2://..."
    )
config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def run_migrations_offline() -> None:
    """
    Run migrations without a live DB connection.
    Produces a SQL script instead of executing directly.
    """
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
    """
    Run migrations against a live database connection.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
