from typing import Any

from fastapi import APIRouter
from sqlalchemy import Engine, text

from app.core.database import engine as app_engine
from app.core.postgres import get_target_engine, get_throwaway_engine
from app.schemas.postgres import Health, ServerHealth

router = APIRouter()


def _check(engine: Engine, version_sql: str) -> ServerHealth:
    try:
        with engine.connect() as conn:
            return ServerHealth(ok=True, version=conn.execute(text(version_sql)).scalar())
    except Exception as exc:  # report, don't crash the health check
        return ServerHealth(ok=False, error=str(exc).splitlines()[0])


@router.get("/", response_model=Health)
def read_health() -> Any:
    """
    Check connectivity to app storage, the target server and the throwaway server.
    """
    app_version = "SELECT sqlite_version()" if app_engine.dialect.name == "sqlite" else "SELECT version()"
    return Health(
        app_db=_check(app_engine, app_version),
        target=_check(get_target_engine(), "SHOW server_version"),
        throwaway=_check(get_throwaway_engine(), "SHOW server_version"),
    )
