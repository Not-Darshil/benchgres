# Progress — 15 October 2026

Everything done so far on Benchgres, and where it stands against the build phases in [BENCHGRES.md](../BENCHGRES.md).

---

## 1. Summary

The database environment is complete and verified: two Postgres 17 servers in Docker (target and throwaway) with `pg_stat_statements` and HypoPG, loaded with the airlines demo (2.8 GB) and TPC-H scale factor 5 (7.3 GB). A read-only role for the agent is in place and tested. A FastAPI backend scaffold is running with health, database listing, slow-query and run endpoints, all tested against real data.

No LLM or agent logic exists yet. The next step is Phase 2.

---

## 2. Work done

### Planning and documents

- Reviewed the project plan; flagged open questions (throwaway DB cloning, HypoPG under a read-only role, benchmark noise, row ordering in rewrite checksums).
- Assessed feasibility: the core is realistic; the risky parts are rewrite quality from an 8B model and the 2–3 week timeline (4–6 weeks is more honest).
- Wrote [INTERVIEW_GUIDE.md](../INTERVIEW_GUIDE.md): pitch, walkthrough, demo script, deep-dive Q&A, numbers to fill in, limitations, resume line.

### Tools installed

| Tool | Purpose |
|---|---|
| OrbStack | Docker engine for Mac (lighter than Docker Desktop) |
| DuckDB 1.5.6 | Generates TPC-H data |
| uv 0.13.1 | Python environments; backend runs on Python 3.12 (system Python 3.15 is too new for some libraries) |
| pgAdmin 4 + PostgreSQL 18 | Installed by the user; PostgreSQL 18 came with the pgAdmin installer |

### Docker Postgres

Files: [docker-compose.yml](../docker-compose.yml), [docker/postgres/](../docker/postgres/)

| Server | Container | Port | Contents |
|---|---|---|---|
| Target | `benchgres-target` | **5434** | `demo` (airlines), `tpch` |
| Throwaway | `benchgres-throwaway` | **5433** | Empty for now |
| Local PostgreSQL 18 (not Docker) | — | 5432 | Not used by the project |

- Image: `postgres:17` plus `postgresql-17-hypopg` (HypoPG 1.4.3).
- `pg_stat_statements` preloaded, `track=all`, `track_io_timing=on`.
- Extensions installed in `template1`, so new databases get them automatically.
- Sized for a 16 GB Mac running Ollama: 4 GB memory limit and 1 GB `shared_buffers` per server, 1 GB shared memory for parallel queries.
- Ports bound to `127.0.0.1` only.
- Credentials: `postgres` / `postgres` (admin), `benchgres_ro` / `benchgres_ro` (agent, target only).

### Datasets loaded (target server)

| Database | Size | Largest tables | Indexes |
|---|---|---|---|
| `demo` — Postgres Pro airlines, 6 months (2025-09-01 version) | 2.8 GB | segments ~7.3M rows, boarding_passes ~6M, tickets ~5.6M, bookings ~2.5M | Ships with its own indexes (schema `bookings`) |
| `tpch` — TPC-H scale factor 5 | 7.3 GB | lineitem ~30M rows, orders ~7.5M, partsupp ~4M | Primary keys only, on purpose |

- TPC-H scripts in [benchmark/seed/tpch/](../benchmark/seed/tpch/): `generate.sh` (DuckDB, 33 s for SF 5), `schema.sql`, `primary_keys.sql`, `load.sh` (75 s load).
- Raw CSVs and the 22 TPC-H queries are in `databases/tpch_sf5/` (`queries/q01.sql` … `q22.sql`); the queries were checked for Postgres compatibility.
- First measured slow query: **TPC-H Q6 takes 9.8 s** with no secondary indexes.

### Read-only agent role

File: [docker/postgres/roles.sql](../docker/postgres/roles.sql)

- `benchgres_ro` has `pg_read_all_data` and `pg_read_all_stats`, `default_transaction_read_only = on`, `statement_timeout = 60s`.
- Tested: `CREATE TABLE` fails ("read-only transaction"); `hypopg_create_index` **works**. This confirms the plan's safety design: the agent can test hypothetical indexes on the target without write access.

### FastAPI backend scaffold

Folder: [server/](../server/), modelled on the MOD-Ticketing `server/` layout (`api/v1/endpoints`, `core`, `deps`, `models`, `schemas`, `services`, `utils`, Alembic).

- **Three connections:** app storage (SQLite, so the app's own queries stay out of the target's `pg_stat_statements`), target (read-only role), throwaway (full access). Every target/throwaway connection has a 60 s statement timeout.
- **Models** (Alembic migration applied): `Run`, `RunStep` (agent action log, for the UI timeline and audit), `Recommendation` (fix, timings, approval status).
- **Endpoints**, all tested:

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/health/` | Connectivity to app storage, target, throwaway |
| `GET /api/v1/databases/` | Databases on the target with their extensions |
| `GET /api/v1/databases/slow-queries?database=…` | Top queries from `pg_stat_statements` (DML only) — the agent's first tool |
| `POST /api/v1/runs/`, `GET /api/v1/runs/`, `GET /api/v1/runs/{id}` | Create and read runs |

Run it: `cd server && source .venv/bin/activate && uvicorn app.main:app --reload` → http://localhost:8000/docs

---

## 3. Issues hit and fixes

| Issue | Cause | Fix |
|---|---|---|
| Airlines load failed immediately | The dump starts with `DROP DATABASE demo` (no `IF EXISTS`) | Create an empty `demo` database first, then load |
| Airlines `demo` had no extensions | The dump creates the database from `template0` | Installed `pg_stat_statements` and HypoPG in `demo` manually |
| `psql: command not found` | PostgreSQL 18's `bin` folder isn't on PATH | Add `/Library/PostgreSQL/18/bin` to PATH in `~/.zshrc` |
| pgAdmin on port 5432 reached the wrong server | Local PostgreSQL 18 also listens on 5432 and won | Moved the Docker target to port **5434** |
| Slow-query list showed `COPY` and `ALTER` from loading | `pg_stat_statements` tracks utility statements | Filtered to `SELECT` / `WITH` / `INSERT` / `UPDATE` / `DELETE` |

---

## 4. Decisions made

- **OrbStack** over Docker Desktop (lighter on RAM) and over Homebrew Postgres (would need HypoPG compiled by hand).
- **Postgres 17** instead of the plan's 16 (newer; HypoPG supports it).
- **pgAdmin runs locally**, connecting to Docker on localhost ports.
- **SQLite for app storage**, to keep the target's statistics clean.
- **Throwaway left empty** until the cloning approach is designed in Phase 3.
- **Backend folder named `server/`** (following the MOD-Ticketing reference), not `backend/` as in the plan.

---

## 5. Progress by phase

| Phase | Goal (from the plan) | Done | Remaining | Status |
|---|---|---|---|---|
| **1. Setup** | Docker Postgres with extensions, load TPC-H, write the slow query set, Ollama running | Docker Postgres + both extensions ✓; TPC-H SF 5 loaded ✓; airlines demo loaded ✓ (bonus); 22 TPC-H queries available ✓; read-only role ✓ | Curate a tagged slow query set (planted anti-patterns, intended cause per query); install Ollama and pull a model | **~75%** |
| **2. Basic loop** | Slow query → explain → LLM suggests an index → print it | `get_slow_queries` tool exists (as an API endpoint) | `explain_query`, plan summarizer, Ollama client, prompt, CLI script | **~10%** |
| **3. HypoPG + verify** | Hypothetical indexes, throwaway DB, real benchmarks | HypoPG confirmed working under the read-only role; throwaway server running | `hypo_index` tool; cloning data into the throwaway; `apply_on_throwaway`; `benchmark` (warm-up, median/p95) | **~10%** |
| **4. LangGraph agent** | Full graph with retries, iteration limits, structured outputs | Run / step / recommendation storage ready for it | Everything else | **~5%** |
| **5. API + UI** | FastAPI + SSE, React timeline and approval flow | FastAPI scaffold, models, migrations, health/database/slow-query/run endpoints | SSE streaming, approve/reject endpoints, React frontend | **~25%** |
| **6. Eval + polish** | Benchmark, Dexter baseline, comparison table, README, demo GIF | Interview guide written | Eval runner, Dexter install and baseline, results, README, demo | **~5%** |

**Overall: roughly 20% of the planned work.** Phase 1 is nearly done; the backend scaffold puts Phase 5 slightly ahead of its turn.

---

## 6. Next steps

1. **Finish Phase 1**
   - Install Ollama and pull a tool-calling model (`qwen3:8b` or newer).
   - Run all 22 TPC-H queries with a timeout to get baseline times; keep the slow ones.
   - Add planted anti-pattern queries (`LIKE '%x%'`, functions on columns, correlated subqueries, `SELECT *`) and tag each with its intended cause.
   - Reset `pg_stat_statements` before generating the workload.
2. **Phase 2**
   - `explain_query` tool and a plan summarizer (node types, estimated vs. actual rows, flags computed in code).
   - Ollama client and diagnosis prompt.
   - CLI script: slow query → plan summary → LLM suggestion.

---

## 7. Quick reference

```bash
# Start / stop databases
docker compose up -d
docker compose down          # keeps data
docker compose down -v       # deletes all data

# psql into the target
psql -h localhost -p 5434 -U postgres -d tpch

# Regenerate and reload TPC-H
./benchmark/seed/tpch/generate.sh 5
PSQL="docker exec -i benchgres-target psql -U postgres -q" ./benchmark/seed/tpch/load.sh 5 tpch

# Reload airlines
docker exec benchgres-target psql -U postgres -c "CREATE DATABASE demo;"
gunzip -c databases/demo-20250901-6m.sql.gz | docker exec -i benchgres-target psql -U postgres -q
docker exec benchgres-target psql -U postgres -d demo -c "CREATE EXTENSION pg_stat_statements; CREATE EXTENSION hypopg; ANALYZE;"

# Backend
cd server && source .venv/bin/activate && uvicorn app.main:app --reload
```
