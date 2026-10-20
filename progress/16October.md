# Progress — 16 October 2026

Work done today on Benchgres (renamed from PgTune Agent), and where it stands against the build phases in [BENCHGRES.md](../BENCHGRES.md). Previous log: [15October.md](15October.md).

---

## 1. Summary

The project is now called **Benchgres**, with the rename carried through code, config, Docker and the read-only role, and the data moved without loss. A README and `.gitignore` are in place. The first **plain baseline of all 22 TPC-H queries** is done: 9 queries take 6–18 s, and Q17 and Q20 time out at 300 s. A bug in Q11 was found and fixed.

Still no LLM or agent logic. Ollama is deliberately postponed until the Phase 1 query work is finished.

---

## 2. Work done

### Review of the plan and progress log

Checked [BENCHGRES.md](../BENCHGRES.md) and [15October.md](15October.md) against the code; the progress log was accurate. Gaps found that neither document covered:

| Gap | Why it matters | Planned fix |
|---|---|---|
| `pg_stat_statements` stores normalized queries (`$1`, `$2`) | They can't be run with `EXPLAIN ANALYZE` or benchmarked | `EXPLAIN (GENERIC_PLAN)` for plans; map each stored query back to its concrete SQL file for timings |
| "Skip `ANALYZE`" won't produce stale stats | Autovacuum analyzes tables on its own after a load | `ALTER TABLE … SET (autovacuum_enabled = false)`, then change the data |
| 60 s timeout | Some baselines can't be measured | Longer timeout for benchmarks (baseline runner uses 300 s) |
| Memory: 2 × 4 GB containers + ~6 GB model + macOS ≈ 16 GB | Swapping would distort timings | Unload the model (`keep_alive: 0`) before benchmarks; stop the throwaway server when not needed |
| Throwaway server is empty | Phase 3 needs a copy | Re-run the seed scripts against port 5433 (~75 s for TPC-H) |
| HypoPG indexes exist only within one connection | A connection pool would lose them | `hypo_index` must hold one connection for create + `EXPLAIN` |
| Agent's own catalog queries will appear in the slow-query list | Noise in `get_slow_queries` | Filter on `userid <> 'benchgres_ro'::regrole` |
| Dexter creates real indexes and reads `pg_stat_statements` where it runs | Can't run it on the target | Run Dexter on the throwaway after replaying the workload there; reset between Dexter and agent runs |
| N+1 shows up as a fast query with a huge call count | Can't be found from slow queries alone | Small workload script that calls one query in a loop |
| Rewrite checksums | Floating-point totals and `LIMIT` without `ORDER BY` | Round floats; compare with `EXCEPT ALL` in both directions |

### Project renamed to Benchgres

- Candidates checked on GitHub and PyPI:

| Name | Result |
|---|---|
| Querysmith | Mostly NL2SQL repos; rejected |
| pgVerdict | Taken by [Svaca33/pgverdict](https://github.com/Svaca33/pgverdict), a Postgres MCP server with a verification loop (very similar idea; created Aug 2026, also on PyPI). **Worth adding to the "Existing tools" section next to Dexter.** |
| Planwise | 282 repos, taken on PyPI |
| Benchproof | Free on PyPI, 2 small unrelated repos |
| **Benchgres** | **0 repos, free on PyPI — chosen** |
| ImpGres, Provegres, Verigres, Plangres, Tunegres | Also free; not chosen |

- What was renamed:

| Where | Old | New |
|---|---|---|
| Plan document | `PGTUNE_AGENT.md` | [BENCHGRES.md](../BENCHGRES.md) |
| Docs (plan, interview guide, progress log) | "PgTune Agent" | "Benchgres" |
| Compose project | `pgtune` (from the folder name) | `name: benchgres` in [docker-compose.yml](../docker-compose.yml) |
| Containers | `pgtune-target`, `pgtune-throwaway` | `benchgres-target`, `benchgres-throwaway` |
| Image | `pgtune-postgres:17` | `benchgres-postgres:17` |
| Volumes | `pgtune_pgdata_*` | `benchgres_pgdata_*` |
| Read-only role | `pgtune_ro` / `pgtune_ro` | `benchgres_ro` / `benchgres_ro` (renamed in place on the target, settings kept) |
| App storage | `server/pgtune.db` | `server/benchgres.db` |
| Backend | `application_name=pgtune`, "PgTune Agent API" | `benchgres`, "Benchgres API" |

- The two remaining mentions of "PGTune" (BENCHGRES.md line 20, INTERVIEW_GUIDE.md line 149) are intentional: they refer to the separate PGTune config calculator.
- **Data move:** stopped the stack, created the new volumes with `docker compose create`, copied the data with an Alpine container (13.9 GB, ~38 s, sizes matched), started under the new names.
- **Verified afterwards:** `tpch` (7.3 GB) and `demo` (2.8 GB) present; health, slow-query and runs endpoints work; the earlier run record survived; `benchgres_ro` can't create tables; HypoPG still works under it.

### README and .gitignore

- [README.md](../README.md): what Benchgres does, architecture, comparison with Dexter, safety rules, setup steps (Docker, both datasets, backend), endpoints, project structure, roadmap. Results section says "no numbers yet" on purpose.
- [.gitignore](../.gitignore): `databases/` (large and reproducible), `RESUME_ANALYSIS.md` and `INTERVIEW_GUIDE.md` (personal notes), Python environment and caches, `.env` files (keeps `.env.example`), SQLite files, frontend build output, benchmark logs (results JSON is kept), editor and OS files.

### Ollama: decided to wait

Not installed yet. It's needed from Phase 2 onward; the rest of Phase 1 doesn't need it. When installing, check the Ollama library for newer 7–9B tool-calling models before pulling `qwen3:8b`. An 8B model is the practical limit on 16 GB alongside both Postgres servers.

### Baseline benchmark of TPC-H

- New script: [benchmark/run_baseline.py](../benchmark/run_baseline.py). Runs a folder of `.sql` files with one warm-up run plus N timed runs, a per-query timeout, and an optional `pg_stat_statements` reset. It records server settings and saves JSON after every query.
- Run on the **target** as `postgres`, primary keys only, 3 timed runs, 300 s timeout, `pg_stat_statements` reset at the start.
- Settings: Postgres 17.11, `shared_buffers` 1 GB, `work_mem` 32 MB, `effective_cache_size` 3 GB, `max_parallel_workers_per_gather` 2, JIT on.
- Results: [benchmark/results/baseline_tpch_sf5.json](../benchmark/results/baseline_tpch_sf5.json)

| Query | Warm-up | Median | Range | Rows | Group |
|---|---|---|---|---|---|
| **Q17** | — | **timeout (> 300 s)** | — | — | Correlated subquery |
| **Q20** | — | **timeout (> 300 s)** | — | — | Correlated subquery |
| Q18 | 19.70 s | 18.27 s | 16.85–18.92 | 100 | Slow |
| Q09 | 13.97 s | 13.12 s | 13.04–13.49 | 175 | Slow |
| Q21 | 9.86 s | 13.06 s | 10.85–15.04 | 100 | Slow |
| Q04 | 9.30 s | 11.03 s | 10.95–12.52 | 5 | Slow |
| Q03 | 8.79 s | 10.42 s | 9.74–10.79 | 10 | Slow |
| Q05 | 9.37 s | 9.47 s | 9.24–10.09 | 5 | Slow |
| Q08 | 5.23 s | 9.20 s | 7.74–9.65 | 2 | Slow |
| Q07 | 10.11 s | 8.31 s | 6.30–9.29 | 4 | Slow |
| Q12 | 5.18 s | 6.70 s | 6.28–7.84 | 2 | Slow |
| Q01 | 4.03 s | 3.65 s | 3.53–3.81 | 4 | Medium |
| Q19 | 1.85 s | 3.38 s | 2.88–3.93 | 1 | Medium |
| Q10 | 8.08 s | 2.23 s | 1.62–3.33 | 20 | Medium |
| Q13 | 2.80 s | 1.78 s | 1.77–1.81 | 43 | Medium |
| Q15 | 0.73 s | 0.74 s | 0.74–0.74 | 1 | Fast |
| Q06 | 1.35 s | 0.75 s | 0.73–0.87 | 1 | Fast |
| Q14 | 5.31 s | 0.74 s | 0.71–1.17 | 1 | Fast |
| Q16 | 0.72 s | 0.53 s | 0.53–0.54 | 27,724 | Fast |
| Q02 | 2.27 s | 0.51 s | 0.50–0.64 | 100 | Fast |
| Q22 | 1.76 s | 0.42 s | 0.33–0.42 | 7 | Fast |
| Q11 | 0.78 s | 0.26 s | 0.25–0.28 | 4,606 | Fast (re-run after fix) |

**What the numbers say**
- **11 targets for the agent:** the 9 slow queries plus Q17 and Q20.
- **Q17 and Q20 are the showcase.** Postgres can't decorrelate their subqueries, so they time out; a pre-aggregating rewrite should bring them to seconds. That is exactly the kind of fix Dexter can't make.
- **The 7 fast queries** are control cases: the agent should leave them alone.

---

## 3. Issues hit and fixes

| Issue | Cause | Fix |
|---|---|---|
| Renaming the compose project would orphan the 14 GB of data | Docker names volumes after the project | Created new volumes, copied the data with the servers stopped, kept the old volumes as a backup |
| Alpine copy command blocked by a safety check | It included an `rm -rf` cleanup step | Dropped the cleanup; confirmed the new volumes were empty first |
| Q11 returned 0 rows | DuckDB writes the SF 1 threshold (`0.0001`); the spec uses `0.0001 / SF` | Set SF 5 file to `0.00002`; [generate.sh](../benchmark/seed/tpch/generate.sh) now scales it for any SF; re-ran Q11 (4,606 rows) |
| Benchmark task reported "failed" (exit code 1) | `tee` to `benchmark/results/…log` started before the script created the folder | Benchmark itself completed; the JSON is the record. Folder exists now. |
| `load.sh` comment misaligned | Side effect of the rename | Re-aligned |

---

## 4. Decisions made

- **Name: Benchgres.** Free on GitHub and PyPI; "bench" points at the selling point (fixes proven by benchmarks).
- **Project folder left as `pgtune/`** for now, because `server/.venv` records absolute paths. Renaming means moving the folder and rebuilding the venv.
- **Old Docker volumes and image kept** as a backup until the new setup is confirmed.
- **Ollama postponed** until the Phase 1 query work is done.
- **Baselines run on the target**, since the throwaway is still empty. This also filled the target's `pg_stat_statements` with exactly the TPC-H workload.
- **Warm-cache timings** are the reported number (median of the timed runs); cold timings are much slower (Q6: 9.8 s cold vs 0.75 s warm).
- **Personal notes kept out of git** (`RESUME_ANALYSIS.md`, `INTERVIEW_GUIDE.md`).

---

## 5. Progress by phase

| Phase | Goal | Done | Remaining | Status |
|---|---|---|---|---|
| **1. Setup** | Docker Postgres with extensions, load TPC-H, write the slow query set, Ollama running | Everything from 15 Oct; **TPC-H baselines measured**; slow targets identified; Q11 fixed | Planted anti-pattern queries with intended-cause tags; stale-stats and N+1 setups; Ollama + model | **~85%** |
| **2. Basic loop** | Slow query → explain → LLM suggests a fix → print it | `get_slow_queries` endpoint | `explain_query`, plan summarizer, Ollama client, prompt, CLI script | **~10%** |
| **3. HypoPG + verify** | Hypothetical indexes, throwaway DB, real benchmarks | HypoPG works under `benchgres_ro`; baseline runner exists and can be reused for benchmarks | `hypo_index`; load data into the throwaway; `apply_on_throwaway`; more timed runs and p95 | **~15%** |
| **4. LangGraph agent** | Full graph with retries, iteration limits, structured outputs | Run / step / recommendation storage | Everything else | **~5%** |
| **5. API + UI** | FastAPI + SSE, React timeline and approval flow | Backend scaffold and endpoints | SSE, approve/reject, React frontend | **~25%** |
| **6. Eval + polish** | Benchmark, Dexter baseline, comparison table, README, demo GIF | README written; baseline runner and first results | Dexter run, eval runner, results table, demo | **~10%** |

**Overall: roughly 25% of the planned work.**

---

## 6. Next steps

1. **Finish Phase 1**
   - Try the Q17 rewrite by hand to measure the size of the win.
   - Write planted anti-pattern queries (`LIKE '%x%'`, functions on columns, `SELECT *`, correlated subqueries) on `tpch` and `demo`; tag each with its intended cause.
   - Stale stats: disable autovacuum on chosen tables, then change their data.
   - N+1: a small script that calls one query in a loop.
   - Install Ollama and pull a tool-calling model.
2. **Benchmark method**
   - Raise timed runs to 5–7 per query; report median and p95.
   - Decide how to report Q17/Q20 (one long run for a real baseline, or "at least N×").
   - Keep JIT and parallel settings identical across all comparisons.
3. **Housekeeping**
   - Update [BENCHGRES.md](../BENCHGRES.md): Postgres 17, `server/` folder, 4–6 week timeline, pgverdict in "Existing tools", the gaps in section 2 above.
   - Delete the old volumes and image once satisfied (commands below).
   - Update any saved pgAdmin connection that used `pgtune_ro`.
   - `git init` and check `git status` that nothing large is tracked.
   - `start.md` duplicates the README and can go; `databases/db.md` is empty.

---

## 7. Quick reference

```bash
# Start / stop databases
docker compose up -d
docker compose down          # keeps data
docker compose down -v       # deletes all data

# psql into the target
psql -h localhost -p 5434 -U postgres -d tpch

# Baseline benchmark (all queries, or --only q17 q20)
server/.venv/bin/python benchmark/run_baseline.py \
  --queries databases/tpch_sf5/queries --database tpch \
  --out benchmark/results/baseline_tpch_sf5.json --reset-stats

# Backend
cd server && source .venv/bin/activate && uvicorn app.main:app --reload

# Remove the pre-rename backup once satisfied
docker volume rm pgtune_pgdata_target pgtune_pgdata_throwaway
docker rmi pgtune-postgres:17
```
