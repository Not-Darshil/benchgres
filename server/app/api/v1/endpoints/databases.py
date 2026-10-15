from typing import Any, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Connection

from app import deps
from app.core.postgres import get_target_engine
from app.schemas.postgres import Database, SlowQuery
from app.services import introspection

router = APIRouter()


@router.get("/", response_model=List[Database])
def read_databases() -> Any:
    """
    List databases on the target server with their installed extensions.
    """
    with get_target_engine().connect() as conn:
        databases = introspection.list_databases(conn)
    for db in databases:
        with get_target_engine(db["name"]).connect() as conn:
            db["extensions"] = introspection.get_extensions(conn)
    return databases


@router.get("/slow-queries", response_model=List[SlowQuery])
def read_slow_queries(
    limit: int = Query(10, ge=1, le=100),
    order_by: str = Query("total_time", pattern="^(total_time|mean_time|calls)$"),
    conn: Connection = Depends(deps.get_target_conn),
) -> Any:
    """
    Top statements for one database from pg_stat_statements.
    """
    return introspection.get_slow_queries(conn, limit=limit, order_by=order_by)
