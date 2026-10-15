#!/usr/bin/env bash
# Load generated TPC-H CSVs into PostgreSQL.
# Usage: ./load.sh [scale_factor] [database]   (defaults: 5, tpch)
#
# Set PSQL to choose how psql is run (connection to the server, not the database):
#   PSQL="psql -h localhost -p 5434 -U postgres"              (local client, default)
#   PSQL="docker exec -i benchgres-target psql -U postgres"   (psql inside Docker)
# Data is streamed through stdin, so it works for both.

set -euo pipefail

SF="${1:-5}"
DBNAME="${2:-tpch}"
PSQL="${PSQL:-psql -h localhost -p 5434 -U postgres}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
DATA="$ROOT/databases/tpch_sf$SF"
TABLES="region nation part supplier partsupp customer orders lineitem"

[ -f "$DATA/lineitem.csv" ] || { echo "No data in $DATA. Run ./generate.sh $SF first." >&2; exit 1; }

echo "Creating database $DBNAME ..."
$PSQL -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $DBNAME;"
$PSQL -v ON_ERROR_STOP=1 -c "CREATE DATABASE $DBNAME;"

$PSQL -v ON_ERROR_STOP=1 -d "$DBNAME" < "$HERE/schema.sql"

for t in $TABLES; do
  echo "Loading $t ..."
  $PSQL -v ON_ERROR_STOP=1 -d "$DBNAME" \
    -c "\copy $t FROM pstdin WITH (FORMAT csv, DELIMITER '|')" < "$DATA/$t.csv"
done

echo "Adding primary keys ..."
$PSQL -v ON_ERROR_STOP=1 -d "$DBNAME" < "$HERE/primary_keys.sql"

echo "Running ANALYZE ..."
$PSQL -v ON_ERROR_STOP=1 -d "$DBNAME" -c "ANALYZE;"

$PSQL -d "$DBNAME" -c "SELECT relname AS table, n_live_tup AS rows, pg_size_pretty(pg_total_relation_size(relid)) AS size
                       FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC;"
echo "Done."
