"""Time a folder of queries against a database, with no fixes applied.

Each query gets one warm-up run, then N timed runs. If the warm-up times out,
the timed runs are skipped. Results are written as JSON and printed as a table.

Usage (from the repo root, with the server venv):
    server/.venv/bin/python benchmark/run_baseline.py \
        --queries databases/tpch_sf5/queries --database tpch \
        --out benchmark/results/baseline_tpch_sf5.json --reset-stats
"""

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

SETTINGS = [
    "server_version",
    "shared_buffers",
    "work_mem",
    "effective_cache_size",
    "max_parallel_workers_per_gather",
    "jit",
]


def connect(args):
    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        dbname=args.database,
        application_name="benchgres-baseline",
        options=f"-c statement_timeout={args.timeout * 1000}",
    )
    conn.autocommit = True
    return conn


def run_once(cur, sql):
    """Run a query and return (elapsed ms, row count), including fetching rows."""
    start = time.perf_counter()
    cur.execute(sql)
    rows = cur.fetchall()
    return (time.perf_counter() - start) * 1000, len(rows)


def bench_query(conn, sql, runs):
    result = {"status": "ok", "warmup_ms": None, "runs_ms": [], "rows": None, "error": None}
    with conn.cursor() as cur:
        try:
            result["warmup_ms"], result["rows"] = run_once(cur, sql)
            for _ in range(runs):
                ms, _ = run_once(cur, sql)
                result["runs_ms"].append(ms)
        except psycopg2.errors.QueryCanceled:
            result["status"] = "timeout"
        except psycopg2.Error as e:
            result["status"] = "error"
            result["error"] = str(e).strip()
    if result["runs_ms"]:
        result["median_ms"] = statistics.median(result["runs_ms"])
        result["min_ms"] = min(result["runs_ms"])
        result["max_ms"] = max(result["runs_ms"])
    return result


def fmt(ms):
    return "—" if ms is None else f"{ms / 1000:.2f}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--queries", required=True, type=Path, help="Folder of .sql files")
    parser.add_argument("--database", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5434)
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--password", default="postgres")
    parser.add_argument("--runs", type=int, default=3, help="Timed runs after the warm-up")
    parser.add_argument("--timeout", type=int, default=300, help="Per-query timeout in seconds")
    parser.add_argument("--only", nargs="*", help="Query names to run, e.g. q01 q06")
    parser.add_argument("--reset-stats", action="store_true", help="Reset pg_stat_statements first")
    args = parser.parse_args()

    files = sorted(args.queries.glob("*.sql"))
    if args.only:
        files = [f for f in files if f.stem in args.only]

    conn = connect(args)
    with conn.cursor() as cur:
        if args.reset_stats:
            cur.execute("SELECT pg_stat_statements_reset()")
        settings = {}
        for name in SETTINGS:
            cur.execute(f"SHOW {name}")
            settings[name] = cur.fetchone()[0]

    report = {
        "database": args.database,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runs": args.runs,
        "timeout_s": args.timeout,
        "settings": settings,
        "queries": {},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)

    print(f"{'query':<6} {'status':<8} {'warm-up s':>10} {'median s':>9} {'min s':>7} {'max s':>7} {'rows':>6}", flush=True)
    for f in files:
        r = bench_query(conn, f.read_text(), args.runs)
        report["queries"][f.stem] = r
        args.out.write_text(json.dumps(report, indent=2))  # save after each query
        print(
            f"{f.stem:<6} {r['status']:<8} {fmt(r['warmup_ms']):>10} {fmt(r.get('median_ms')):>9} "
            f"{fmt(r.get('min_ms')):>7} {fmt(r.get('max_ms')):>7} {r['rows'] if r['rows'] is not None else '—':>6}"
            + (f"  {r['error']}" if r["error"] else ""),
            flush=True,
        )

    report["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    args.out.write_text(json.dumps(report, indent=2))
    conn.close()


if __name__ == "__main__":
    main()
