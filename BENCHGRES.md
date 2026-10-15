# Benchgres — Project Plan

An offline AI agent that finds slow PostgreSQL queries, diagnoses why they're slow, tests fixes safely, measures the results, and recommends only the fixes that actually help.

Everything runs locally and for free on a MacBook (M5, 16 GB RAM).

---

## 1. Why this project

- **Builds on resume experience:** SQL optimization (ASAAN: 22s → 4–5s), PostgreSQL, offline AI, FastAPI/React, SSE.
- **Genuinely agentic:** multi-step loop with real tools; the agent observes results and adapts.
- **Measurable:** produces real speedup numbers, not just chat output.
- **Offline-first:** runs with no internet, which fits the air-gapped AI niche.

---

## 1.5 Existing tools and positioning

**Different from PGTune:** PGTune is a web calculator that suggests `postgresql.conf` settings from hardware specs. It never looks at queries. This project works on the actual queries.

**Closest existing tool: Dexter** (open source, by ankane). Dexter reads `pg_stat_statements`, tests candidate indexes with HypoPG, and creates the ones that help. It does not use an LLM.

| | Dexter | This agent |
|---|---|---|
| Finds slow queries (`pg_stat_statements`) | Yes | Yes |
| Tests indexes with HypoPG | Yes | Yes |
| Index recommendations | Yes | Yes |
| Query rewrites (checked for correctness) | No | Yes |
| Diagnoses non-index causes (bad joins, stale stats, N+1) | No | Yes |
| Plain-language explanation of each fix | No | Yes |
| Verifies on a throwaway DB with real benchmarks | No (relies on planner cost estimates) | Yes |
| Human approval before applying | Optional (it can just log suggestions) | Required |
| Uses an LLM | No | Yes (local) |

**Positioning:** this is not "Dexter with an LLM." Dexter is the **baseline**; the agent's value is whatever it finds **beyond** what rule-based index advising can do, mainly query rewrites and non-index diagnoses, all verified.

Other related tools worth knowing for interviews: pganalyze Index Advisor (commercial), EverSQL (AI query optimizer, now part of Aiven).

---

## 2. What the agent does

1. **Find** the most expensive queries from `pg_stat_statements`.
2. **Inspect** table schemas, existing indexes, table sizes, and the query plan (`EXPLAIN (ANALYZE, BUFFERS)`).
3. **Diagnose** the likely cause: missing index, sequential scan on a large table, bad join order, stale statistics, N+1 pattern, unnecessary `SELECT *`, and so on.
4. **Hypothesize** fixes: new indexes, query rewrites, `ANALYZE`.
5. **Test risk-free** with **HypoPG** (hypothetical indexes the planner can see but that aren't actually built).
6. **Verify** the best candidates on a **throwaway copy** of the database: apply the fix, re-run, measure.
7. **Report** each query's before/after timings, the SQL to apply, and trade-offs (index size, write overhead).
8. **Wait for approval:** nothing is applied to the target database without the user approving it.

---

## 3. Stack (all free)

| Part | Choice | Notes |
|---|---|---|
| LLM | Qwen3 8B or Llama 3.1 8B (4-bit) via **Ollama** | ~5–6 GB RAM. Check for newer tool-calling models in the 7–14B range before starting. |
| Agent framework | **LangGraph** | State machine with explicit nodes and loops |
| Backend | **FastAPI** | REST plus **SSE** to stream agent steps |
| Frontend | **React** (Vite) | Live step timeline, query diff view, approve/reject buttons |
| Database | **PostgreSQL 16+** in Docker | Extensions: `pg_stat_statements`, `hypopg` |
| App storage | SQLite or a separate Postgres schema | Stores runs, steps, recommendations, eval results |
| Test data | Postgres Pro airlines → **TPC-H** → **JOB (IMDb)** | Seed with intentionally slow queries (see section 6.5) |

---

## 4. Architecture

```
React UI  ──REST/SSE──►  FastAPI  ──►  LangGraph agent  ──►  Ollama (local LLM)
                                            │
                                            ├──► Target DB   (read-only role)
                                            └──► Throwaway DB (copy, full access)
```

### Agent graph (LangGraph nodes)

```
collect_slow_queries
      │
      ▼
for each query:
  inspect_plan ──► diagnose ──► propose_fixes ──► test_hypothetical (HypoPG)
                                     ▲                     │
                                     └── not improved ─────┤
                                                           ▼ improved
                                              verify_on_throwaway_db
                                                           │
                                                           ▼
                                                    record_result
      │
      ▼
write_report ──► await_human_approval ──► (optional) apply_to_target
```

Set a **max iteration limit per query** (e.g. 3 attempts) so the agent can't loop forever.

---

## 5. Agent tools

| Tool | What it does | DB access |
|---|---|---|
| `get_slow_queries(limit)` | Top queries by total/mean time from `pg_stat_statements` | Read-only |
| `get_table_info(table)` | Columns, types, row count, size, existing indexes | Read-only |
| `explain_query(sql, analyze)` | Returns the plan as JSON | Read-only (`ANALYZE` only on the throwaway DB) |
| `hypo_index(ddl)` | Creates a HypoPG hypothetical index, re-runs `EXPLAIN`, returns the cost change | Read-only-safe |
| `apply_on_throwaway(ddl)` | Applies a real index or change on the throwaway copy | Throwaway only |
| `benchmark(sql, runs)` | Runs the query N times and returns median/p95 timing | Throwaway only |
| `rewrite_query(sql)` | LLM proposes an equivalent faster query; results are compared row-by-row for correctness | Throwaway only |

**Important:** have the LLM work from a **compact summary** of the plan (node types, row estimates vs. actuals, costs), not raw JSON. Small models handle summaries much better.

---

## 6. Safety rules

- The target DB connection uses a **read-only Postgres role**.
- All DDL (index creation, schema changes) runs **only on the throwaway copy**.
- Query rewrites must return **identical results** (row count plus checksum) before they're recommended.
- **Human approval** is required before anything touches the target DB.
- **Timeouts** on every query (`statement_timeout`) so a bad plan can't hang the system.
- Every step is logged: what the agent did and why.

---

## 6.5 Test datasets

No database is "slow" by itself. Queries get slow when a large dataset meets missing indexes or bad query patterns. Use large, realistic open datasets and plant those problems on purpose.

### Main datasets

| Dataset | Size | Why it's useful |
|---|---|---|
| **TPC-H** (generated with `dbgen`) | Scale factor 1 ≈ 1 GB; 10 ≈ 10 GB | Standard benchmark: 22 complex analytical queries with joins and aggregations. Ships without useful indexes. Start at SF 1; use SF 5–10 for properly slow queries. |
| **Join Order Benchmark (JOB)** on IMDb data | ~4 GB | 113 queries known to make the Postgres planner misjudge row counts and pick bad join orders. Ideal for the non-index causes Dexter can't handle. IMDb data is for non-commercial use only. |
| **Postgres Pro "airlines" demo DB** | small / medium / big (~2.5 GB) | Realistic flight-booking schema made for learning Postgres. Easy to load; natural slow queries on bookings, tickets and flights. |
| **Stack Exchange data dump** | A few GB (smaller site, e.g. dba.stackexchange) to 100+ GB (Stack Overflow) | Real messy data, text search, `LIKE` patterns, uneven data distribution. Use a smaller site; full Stack Overflow is too big for 16 GB RAM. |

### Also worth knowing

- **TPC-DS:** 99 queries, more complex than TPC-H. A stretch benchmark once TPC-H works.
- **MusicBrainz:** official Postgres dump of a real production music database with a large schema.
- **OpenStreetMap** via `osm2pgsql` (a country or city extract): PostGIS spatial queries. Connects to GeoServer experience.
- **NYC Taxi trips:** one huge table with millions of rows; good for time-range scans and index choices.
- **Employees sample DB:** ~300k employees, 2.8M salary rows. Medium-sized and easy to start with.

**Too small to be slow** (fine for testing code, useless for benchmarks): Pagila, Chinook, Northwind, pgbench default tables.

### Suggested path

1. **Postgres Pro airlines (medium):** get the agent loop working quickly.
2. **TPC-H at SF 5–10:** main benchmark and the Dexter comparison.
3. **JOB on IMDb:** hard cases that show what the agent does beyond indexes.

All three fit on a 512 GB disk and run on 16 GB RAM. With Postgres, Docker and the LLM running at once, keep TPC-H at SF 10 or below.

### Making queries slow on purpose

- Don't create secondary indexes (only primary keys).
- Plant anti-patterns: `SELECT *`, correlated subqueries, `LIKE '%x%'`, functions on indexed columns (`WHERE lower(email) = ...`), N+1 loops.
- Skip `ANALYZE` on some tables so their statistics go stale.
- Tag each planted query with its intended cause, so the evaluation can check whether the agent diagnosed it correctly.

---

## 7. Evaluation

Build a fixed benchmark so results are reproducible:

- **20–30 slow queries** across categories: missing index, bad join, `LIKE '%x%'`, correlated subquery, N+1, missing `ANALYZE`.
- For each, record: baseline time, agent's fix, new time, correct (yes/no).

**Metrics to report:**
- Queries improved (X of Y)
- Median and best speedup
- Regressions (fixes that made things worse)
- False recommendations (fixes that didn't help)
- Average agent steps and time per query
- Comparison: 8B vs. 14B model (optional)

### Baseline: Dexter vs. agent

Run **Dexter on the same benchmark** and compare side by side:

| Metric | Dexter | Agent |
|---|---|---|
| Queries improved (of Y) | | |
| Median speedup | | |
| Regressions | | |
| Queries only one tool fixed | | |
| Indexes created (fewer is better at equal speedup) | | |
| Time per query | | |

Break down **where the agent won and lost**:
- Queries fixed only by a rewrite (Dexter can't do these)
- Queries where Dexter's index matched or beat the agent
- Cases where the agent was wrong or slower

An honest result is fine. "Dexter matches the agent on index-only queries; the agent adds wins on rewrite-type queries" is a strong, credible finding.

Save results as a table in the README; this is what makes the project credible.

---

## 8. Project structure

```
benchgres/
├── docker-compose.yml        # postgres (target) + postgres (throwaway)
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app, SSE endpoint
│   │   ├── agent/
│   │   │   ├── graph.py      # LangGraph definition
│   │   │   ├── nodes.py      # inspect, diagnose, propose, verify...
│   │   │   ├── tools.py      # DB tools listed above
│   │   │   └── prompts.py
│   │   ├── db/
│   │   │   ├── target.py     # read-only connection
│   │   │   └── throwaway.py  # clone + full-access connection
│   │   └── models.py         # runs, steps, recommendations
│   └── pyproject.toml
├── frontend/                 # React + Vite
├── benchmark/
│   ├── seed/                 # TPC-H generation / data loading
│   ├── queries/              # slow query set
│   └── run_eval.py
└── README.md                 # setup, demo GIF, eval results table
```

---

## 9. Build phases

| Phase | Goal | Est. time |
|---|---|---|
| **1. Setup** | Docker Postgres with extensions, load TPC-H, write the slow query set, Ollama running | 2–3 days |
| **2. Basic loop** | CLI script: slow query → explain → LLM suggests an index → print it | 2–3 days |
| **3. HypoPG + verify** | Hypothetical index testing, throwaway DB, real benchmarks | 3–4 days |
| **4. LangGraph agent** | Full graph with retries, iteration limits, structured outputs | 3–4 days |
| **5. API + UI** | FastAPI + SSE, React timeline and approval flow | 3–4 days |
| **6. Eval + polish** | Run the benchmark, run Dexter as the baseline, comparison table, README, demo GIF | 3–4 days |

**Total:** about 2–3 weeks of evenings. Phase 2 alone is a working demo, so ship early and iterate.

---

## 10. Setup cheatsheet

```bash
# Local LLM
brew install ollama
ollama pull qwen3:8b          # or llama3.1:8b

# Postgres with extensions (use an image that includes hypopg, or install it in a custom Dockerfile)
docker compose up -d

# Inside Postgres
CREATE EXTENSION pg_stat_statements;
CREATE EXTENSION hypopg;
-- also set in postgresql.conf: shared_preload_libraries = 'pg_stat_statements'
```

---

## 11. Stretch goals

- Detect **unused or duplicate indexes** and recommend dropping them.
- **Config tuning** suggestions (`work_mem`, `shared_buffers`) based on workload.
- **Write-overhead estimate** for each new index.
- Export the report as **PDF/Markdown**.
- **MCP server** version so other AI tools can call the agent.
- Compare a **local model vs. a cloud model** on the same benchmark.

---

## 12. Resume bullet (fill in with real numbers only)

> **Benchgres (LangGraph, Ollama, FastAPI, PostgreSQL):** Built an offline agent that diagnoses slow queries via `EXPLAIN ANALYZE`, tests indexes with HypoPG, and verifies fixes on a throwaway database copy; improved **X of Y** benchmark queries with **Z× median speedup** using a local 8B LLM, fixing **N queries** that the rule-based baseline (Dexter) could not.

---

## 13. Interview talking points

- Why HypoPG before real indexes (cost and safety)
- How you stop the agent from looping or hallucinating fixes (iteration limits, verification step)
- How you check that query rewrites are correct (result checksums)
- Why the plan is summarized before it goes to the LLM (small model context and reasoning limits)
- Trade-offs of indexes (read speed vs. write overhead and storage)
- What failed during evaluation and what you changed
- How the agent compares to Dexter, and when you would just use Dexter instead
