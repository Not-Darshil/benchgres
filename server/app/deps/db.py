from typing import Generator

from fastapi import HTTPException, Query
from sqlalchemy import Connection

from app.core.database import SessionLocal
from app.core.postgres import get_target_engine
from app.services import introspection


def get_db() -> Generator:
    """Yield an app-storage session and ensure it is closed after use."""
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def get_target_conn(
    database: str = Query(..., description="Database on the target server, e.g. tpch"),
) -> Generator[Connection, None, None]:
    """Yield a read-only connection to one database on the target server."""
    # Only allow databases that exist, so arbitrary names can't create engines.
    with get_target_engine().connect() as conn:
        names = {d["name"] for d in introspection.list_databases(conn)}
    if database not in names:
        raise HTTPException(status_code=404, detail=f"Database '{database}' not found on target")

    with get_target_engine(database).connect() as conn:
        yield conn
