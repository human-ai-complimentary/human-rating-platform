from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool
from sqlmodel import SQLModel

from config import get_settings

# Ensure all SQLModel classes are registered before Alembic runs.
# Import the models module so all SQLModel table classes get registered
# with SQLModel.metadata, which Alembic uses for autogenerate.
import models  # noqa: F401

config = context.config

if (
    config.config_file_name is not None
    and Path(config.config_file_name).exists()
    and config.get_section("loggers") is not None
):
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _resolve_sqlalchemy_url() -> str:
    configured_url = config.get_main_option("sqlalchemy.url")
    if configured_url:
        return configured_url
    return get_settings().sync_database_url


def run_migrations_offline() -> None:
    url = _resolve_sqlalchemy_url()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _resolve_sqlalchemy_url()

    connectable = create_engine(url, poolclass=pool.NullPool, future=True)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
