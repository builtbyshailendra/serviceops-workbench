#!/usr/bin/env bash
# A throwaway PostgreSQL for local development, separate from any other server.
#
#   scripts/dev-postgres.sh start    # create (first time) and start on port 5433
#   scripts/dev-postgres.sh stop
#   scripts/dev-postgres.sh status
#
# Needs initdb, pg_ctl, psql and createdb from PostgreSQL 14 or newer.
# Set PG_BIN if they aren't on PATH, and PGDATA_DIR to keep the data elsewhere.
# It trusts local connections and listens on 127.0.0.1 only: fine for a laptop, never for a server.
set -euo pipefail

PORT="${PGPORT:-5433}"
DATA="${PGDATA_DIR:-$(cd "$(dirname "$0")/.." && pwd)/.pgdata}"
BIN="${PG_BIN:+$PG_BIN/}"

case "${1:-}" in
  start)
    if [ ! -f "$DATA/PG_VERSION" ]; then
      echo "Creating a new database cluster in $DATA"
      "${BIN}initdb" -D "$DATA" -U postgres -A trust --encoding UTF8 --no-locale > /dev/null
    fi
    # The server outlives this script. Without the redirects it inherits this
    # shell's output pipe, and whatever reads that pipe waits forever.
    "${BIN}pg_ctl" -D "$DATA" -l "$DATA/server.log" -w \
      -o "-p $PORT -c listen_addresses=127.0.0.1" start > /dev/null 2>&1 < /dev/null \
      || { echo "PostgreSQL didn't start. See $DATA/server.log" >&2; exit 1; }
    echo "PostgreSQL is running on 127.0.0.1:$PORT"
    for db in serviceops serviceops_test; do
      if ! "${BIN}psql" -h 127.0.0.1 -p "$PORT" -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$db'" | grep -q 1; then
        "${BIN}createdb" -h 127.0.0.1 -p "$PORT" -U postgres "$db"
        echo "Created database $db"
      fi
    done
    echo "DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:$PORT/serviceops"
    ;;
  stop)
    "${BIN}pg_ctl" -D "$DATA" -w stop
    ;;
  status)
    "${BIN}pg_ctl" -D "$DATA" status
    ;;
  *)
    echo "usage: $0 start|stop|status" >&2
    exit 2
    ;;
esac
