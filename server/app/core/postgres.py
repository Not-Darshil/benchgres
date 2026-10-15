from functools import lru_cache

from sqlalchemy import URL, Engine, create_engine

from app.core.config import settings

# One engine per (server, database). Engines are cached because every
# database on a server needs its own connection pool.


def _engine(host: str, port: int, user: str, password: str, database: str) -> Engine:
    url = URL.create(
        "postgresql+psycopg2",
        username=user,
        password=password,
        host=host,
        port=port,
        database=database,
    )
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=2,
        connect_args={
            "options": f"-c statement_timeout={settings.STATEMENT_TIMEOUT_MS}",
            "application_name": "benchgres",
        },
    )


@lru_cache
def get_target_engine(database: str = "postgres") -> Engine:
    """Read-only connection to the database being analyzed."""
    return _engine(
        settings.TARGET_HOST,
        settings.TARGET_PORT,
        settings.TARGET_USER,
        settings.TARGET_PASSWORD,
        database,
    )


@lru_cache
def get_throwaway_engine(database: str = "postgres") -> Engine:
    """Full-access connection to the throwaway copy. Never point this at the target."""
    return _engine(
        settings.THROWAWAY_HOST,
        settings.THROWAWAY_PORT,
        settings.THROWAWAY_USER,
        settings.THROWAWAY_PASSWORD,
        database,
    )
