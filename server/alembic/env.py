import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# ── Make sure `app` package is importable from here ──────────────────────────
# Adds the `server/` directory (parent of `alembic/`) to sys.path so that
# `from app.xxx import yyy` works without installing the package.
BASE_DIR = Path(__file__).resolve().parent.parent  # server/
sys.path.insert(0, str(BASE_DIR))

# ── Alembic Config object ─────────────────────────────────────────────────────
config = context.config

# ── Logging ───────────────────────────────────────────────────────────────────
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import all models so Alembic can detect them for autogenerate ─────────────
from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402
from app import models  # noqa: E402, F401

# ── Use the same DATABASE_URL as the app (.env or environment) ───────────────
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Set the target metadata for autogenerate
target_metadata = Base.metadata

# SQLite can't ALTER most things in place; batch mode rebuilds the table instead.
render_as_batch = settings.DATABASE_URL.startswith("sqlite")


# ── Offline migrations ────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine.
    Calls to context.execute() emit SQL to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=render_as_batch,
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online migrations ─────────────────────────────────────────────────────────
def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates an Engine and associates a connection with the context.
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
            render_as_batch=render_as_batch,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
