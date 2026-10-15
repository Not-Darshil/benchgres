-- Read-only role the agent uses on the target server.
-- Runs at first init (via init.sql); safe to re-run by hand.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'benchgres_ro') THEN
        CREATE ROLE benchgres_ro LOGIN PASSWORD 'benchgres_ro';
    END IF;
END
$$;

GRANT pg_read_all_data  TO benchgres_ro;  -- SELECT on every table in every database
GRANT pg_read_all_stats TO benchgres_ro;  -- full query text in pg_stat_statements

ALTER ROLE benchgres_ro SET default_transaction_read_only = on;
ALTER ROLE benchgres_ro SET statement_timeout = '60s';
