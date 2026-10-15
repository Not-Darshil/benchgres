#!/usr/bin/env bash
# Generate TPC-H data and the 22 queries with DuckDB.
# Usage: ./generate.sh [scale_factor]   (default 5; SF 1 ≈ 1 GB of CSV)
# Output: databases/tpch_sf<SF>/*.csv and databases/tpch_sf<SF>/queries/q01.sql..q22.sql

set -euo pipefail

SF="${1:-5}"
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="$ROOT/databases/tpch_sf$SF"
DB="$OUT/tpch.duckdb"
TABLES="region nation part supplier partsupp customer orders lineitem"

command -v duckdb >/dev/null || { echo "duckdb not found: brew install duckdb" >&2; exit 1; }

mkdir -p "$OUT/queries"
rm -f "$DB" "$DB.wal"

echo "Generating TPC-H SF $SF in $OUT ..."
{
  echo "INSTALL tpch; LOAD tpch;"
  echo "CALL dbgen(sf = $SF);"
  for t in $TABLES; do
    echo "COPY $t TO '$OUT/$t.csv' (FORMAT csv, HEADER false, DELIMITER '|');"
  done
} | duckdb "$DB"

echo "Writing the 22 queries ..."
for i in $(seq 1 22); do
  duckdb "$DB" -noheader -list \
    -c "LOAD tpch; SELECT query FROM tpch_queries() WHERE query_nr = $i;" \
    > "$OUT/queries/q$(printf '%02d' "$i").sql"
done

# The DuckDB file is only needed for generation.
rm -f "$DB" "$DB.wal"

du -sh "$OUT"/*.csv
echo "Done."
