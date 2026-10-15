# Benchgres

An offline AI agent that finds slow PostgreSQL queries, works out why they're slow, tests fixes safely, and recommends only the fixes that benchmarks prove faster.

Everything runs locally: Postgres in Docker, a local LLM through Ollama, and no cloud services.

> **Status: early development.** The database environment and backend scaffold work; the agent itself (LLM, diagnosis, verification loop) is not built yet. See [Roadmap](#roadmap).

---

## How it works

1. **Find** the most expensive queries in `pg_stat_statements`.
2. **Inspect** schemas, indexes, table sizes and the query plan.
3. **Diagnose** the cause: missing index, bad join order, stale statistics, `LIKE '%x%'`, correlated subqueries, N+1 patterns.
4. **Propose** fixes: new indexes, query rewrites, `ANALYZE`.
5. **Test without risk** using [HypoPG](https://github.com/HypoPG/hypopg) hypothetical indexes, which the planner sees but are never built.
6. **Verify** the best candidates on a throwaway copy of the database: apply, re-run, measure.
7. **Report** before/after timings, the SQL to apply, and trade-offs.
8. **Wait for approval.** Nothing touches the target database without a human saying yes.

```
React UI  ──REST/SSE──►  FastAPI  ──►  LangGraph agent  ──►  Ollama (local LLM)
                                            │
                                            ├──► Target DB    (read-only role)
                                            └──► Throwaway DB (copy, full access)
```

### Compared with Dexter

[Dexter](https://github.com/ankane/dexter) already reads `pg_stat_statements` and tests indexes with HypoPG, without an LLM. Benchgres uses Dexter as its **baseline**. The goal is to measure what an agent adds beyond rule-based index advice: verified query rewrites, non-index diagnoses, and plain-language explanations.

### Safety

- The agent connects to the target as `benchgres_ro`: read-only, with a 60 s statement timeout.
- All DDL runs only on the throwaway server.
- Query rewrites must return identical results before they are recommended.
- Every agent step is logged.

---

## Getting started

### Requirements

- Docker ([OrbStack](https://orbstack.dev) works well on macOS)
- [uv](https://docs.astral.sh/uv/) and Python 3.12
- [DuckDB](https://duckdb.org) CLI, to generate TPC-H data
- `psql` (optional)
- About 25 GB of free disk and 16 GB of RAM

### 1. Start Postgres

```bash
docker compose up -d
```

This starts two Postgres 17 servers with `pg_stat_statements` and HypoPG, bound to localhost:

| Server | Container | Port |
|---|---|---|
| Target (analyzed by the agent) | `benchgres-target` | 5434 |
| Throwaway (fixes are applied and benchmarked here) | `benchgres-throwaway` | 5433 |

Admin login: `postgres` / `postgres`. Agent login (target): `benchgres_ro` / `benchgres_ro`. These are local development credentials only.

### 2. Load the datasets

**TPC-H (scale factor 5, ~7 GB in Postgres).** Only primary keys are created, so queries are slow on purpose.

```bash
./benchmark/seed/tpch/generate.sh 5
PSQL="docker exec -i benchgres-target psql -U postgres -q" ./benchmark/seed/tpch/load.sh 5 tpch
```

**Postgres Pro airlines demo (6 months, ~2.8 GB).** Download `demo-20250901-6m.sql.gz` from the [Postgres Pro demo database page](https://postgrespro.com/community/demodb) into `databases/`, then:

```bash
docker exec benchgres-target psql -U postgres -c "CREATE DATABASE demo;"
gunzip -c databases/demo-20250901-6m.sql.gz | docker exec -i benchgres-target psql -U postgres -q
docker exec benchgres-target psql -U postgres -d demo -c "CREATE EXTENSION pg_stat_statements; CREATE EXTENSION hypopg; ANALYZE;"
```

The dump drops and recreates `demo` from `template0`, which is why the database is created first and the extensions are added afterwards.

### 3. Run the backend

```bash
cd server
uv venv --python 3.12
uv pip install -r requirements.txt
cp .env.example .env
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/health/` | Connectivity to app storage, target and throwaway |
| `GET /api/v1/databases/` | Databases on the target and their extensions |
| `GET /api/v1/databases/slow-queries?database=tpch` | Top queries from `pg_stat_statements` |
| `POST /api/v1/runs/`, `GET /api/v1/runs/`, `GET /api/v1/runs/{id}` | Create and read agent runs |

---

## Project structure

```
.
├── docker-compose.yml       # target + throwaway Postgres servers
├── docker/postgres/         # image with HypoPG, init scripts, read-only role
├── benchmark/seed/tpch/     # TPC-H generation and loading
├── server/                  # FastAPI backend (SQLite app storage, Alembic)
│   └── app/
│       ├── api/v1/endpoints/
│       ├── core/            # settings, database connections
│       ├── models/          # Run, RunStep, Recommendation
│       ├── schemas/
│       └── services/        # Postgres introspection
├── databases/               # generated data and dumps (not in git)
├── progress/                # dated progress notes
└── BENCHGRES.md             # full project plan
```

---

## Roadmap

| Phase | Goal | Status |
|---|---|---|
| 1. Setup | Docker Postgres with extensions, datasets, slow query set, Ollama | Mostly done |
| 2. Basic loop | Slow query → plan summary → LLM suggests a fix | Not started |
| 3. HypoPG + verify | Hypothetical indexes, throwaway copy, real benchmarks | Not started |
| 4. LangGraph agent | Full graph with retries and iteration limits | Not started |
| 5. API + UI | SSE streaming, React timeline, approval flow | Backend scaffold done |
| 6. Evaluation | Benchmark against Dexter, results table | Not started |

The full plan is in [BENCHGRES.md](BENCHGRES.md).

## Results

Benchmark results against Dexter will be published here once the evaluation runs. No numbers yet.
