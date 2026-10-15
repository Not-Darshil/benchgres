-- Runs once, when the data volume is first created.
-- Installing the extensions in template1 means every database created later
-- (tpch, demo, ...) gets them automatically.

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS hypopg;

\connect template1
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS hypopg;
