"""Alembic migration environment."""

from logging.config import fileConfig

from sqlalchemy import pool

import app.models  # noqa: F401 — register models with metadata
from alembic import context
from app.core.config import settings
from app.core.database import Base, build_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# An explicit URL (tests, one-off maintenance) wins over the application settings.
DATABASE_URL = (
    config.attributes.get("database_url")
    or context.get_x_argument(as_dictionary=True).get("url")
    or settings.database_url
)
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = build_engine(DATABASE_URL, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        if connection.dialect.name == "sqlite":
            # Batch migrations recreate tables; with foreign keys enforced, dropping the old
            # table would cascade-delete child rows. Must be set outside a transaction.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
