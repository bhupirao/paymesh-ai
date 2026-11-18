#!/usr/bin/env bash
set -euo pipefail

# A fresh, explicitly marked PostgreSQL cluster. No cleanup SQL or record deletion.
for variable in PAYMESH_DB_URL SPRING_DATASOURCE_URL SPRING_DATASOURCE_USERNAME \
  SPRING_DATASOURCE_PASSWORD SPRING_DATASOURCE_TYPE SPRING_PROFILES_ACTIVE; do
  if [[ -n "${!variable:-}" ]]; then
    printf 'Refusing inherited database/profile override: %s\n' "$variable" >&2
    exit 1
  fi
done

if command -v pg_config >/dev/null 2>&1; then
  pg_bindir=$(pg_config --bindir)
  if [[ -x "$pg_bindir/initdb" ]]; then PATH="$pg_bindir:$PATH"; export PATH; fi
fi

test_tmp_base=${TMPDIR:-/tmp}
test_root=$(mktemp -d "${test_tmp_base%/}/paymesh-isolated-test.XXXXXX")
test_port=${PAYMESH_ISOLATED_TEST_PORT:-55441}
if [[ ! "$test_port" =~ ^[0-9]+$ ]] || [[ "$test_port" == 5432 ]]; then
  echo 'Choose an isolated TCP port other than 5432' >&2
  exit 1
fi
test_database="paymesh_isolated_$(date +%s)_$$"
printf '%s\n' "$test_database" > "$test_root/.paymesh-isolated-test"
initdb -D "$test_root/data" -A trust -U paymesh_test --locale=C -E UTF8 > "$test_root/initdb.log"
pg_ctl -D "$test_root/data" -l "$test_root/postgres.log" \
  -o "-h 127.0.0.1 -p $test_port -k $test_root" start
stop_test_database() {
  if pg_ctl -D "$test_root/data" status >/dev/null 2>&1; then
    pg_ctl -D "$test_root/data" stop -m fast
  fi
  printf 'Isolated database files retained at %s\n' "$test_root"
}
trap stop_test_database EXIT
createdb -h 127.0.0.1 -p "$test_port" -U paymesh_test "$test_database"
actual_directory=$(psql -X -h 127.0.0.1 -p "$test_port" -U paymesh_test -d "$test_database" -Atc 'SHOW data_directory')
if [[ "$actual_directory" != "$test_root/data" ]]; then
  echo 'Database isolation verification failed' >&2
  exit 1
fi
export PAYMESH_DB_URL="jdbc:postgresql://127.0.0.1:$test_port/$test_database"
export PAYMESH_DB_USER=paymesh_test
export PAYMESH_DB_PASSWORD=isolated-test-only
export PAYMESH_TEST_DB_DATA_DIRECTORY="$test_root/data"
export PAYMESH_SETTLEMENT_SCHEDULING_ENABLED=false
printf 'Verified isolated database: %s (data directory %s)\n' "$PAYMESH_DB_URL" "$actual_directory"
# Bound retained application contexts/pools as additive integration suites grow.
# Eight default 10-connection pools leave headroom in the isolated 100-client cluster.
mvn clean test -Dspring.test.context.cache.maxSize=8
