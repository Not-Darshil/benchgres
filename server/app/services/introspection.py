from typing import Any

from sqlalchemy import Connection, text

# Read-only queries against the target server's catalogs and statistics.
# These become the agent's first tools (get_slow_queries, get_table_info, ...).

SLOW_QUERY_ORDER = {
    "total_time": "total_exec_time",
    "mean_time": "mean_exec_time",
    "calls": "calls",
}


def list_databases(conn: Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT datname AS name, pg_database_size(datname) AS size_bytes
            FROM pg_database
            WHERE NOT datistemplate
            ORDER BY datname
            """
        )
    )
    return [dict(r._mapping) for r in rows]


def get_extensions(conn: Connection) -> dict[str, str]:
    rows = conn.execute(text("SELECT extname, extversion FROM pg_extension"))
    return {r.extname: r.extversion for r in rows}


def get_slow_queries(conn: Connection, limit: int, order_by: str) -> list[dict[str, Any]]:
    """Top statements for the current database from pg_stat_statements."""
    column = SLOW_QUERY_ORDER[order_by]  # allowlisted, safe to interpolate
    rows = conn.execute(
        text(
            f"""
            SELECT s.queryid::text AS queryid,
                   s.query,
                   s.calls,
                   round(s.total_exec_time::numeric, 2) AS total_time_ms,
                   round(s.mean_exec_time::numeric, 2)  AS mean_time_ms,
                   s.rows,
                   s.shared_blks_hit,
                   s.shared_blks_read
            FROM pg_stat_statements s
            JOIN pg_database d ON d.oid = s.dbid
            WHERE d.datname = current_database()
              -- Only queries the agent can tune; skips COPY, DDL, ANALYZE, etc.
              AND s.query ~* '^\\s*(select|with|insert|update|delete)\\M'
              AND s.query NOT ILIKE '%pg_stat_statements%'
              AND s.query NOT ILIKE '%pg_catalog%'
            ORDER BY s.{column} DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    )
    return [dict(r._mapping) for r in rows]
