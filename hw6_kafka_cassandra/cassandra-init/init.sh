#!/bin/sh
set -e

CASSANDRA_HOST="${CASSANDRA_HOST:-cassandra-1}"

echo "[init] waiting for ${CASSANDRA_HOST}:9042"
for i in $(seq 1 60); do
  if cqlsh "${CASSANDRA_HOST}" 9042 -e "DESCRIBE CLUSTER" >/dev/null 2>&1; then
    echo "[init] connected to ${CASSANDRA_HOST}"
    break
  fi
  echo "[init] attempt ${i}: not ready, sleeping 3s"
  sleep 3
done

echo "[init] applying /schema.cql"
cqlsh "${CASSANDRA_HOST}" 9042 -f /schema.cql
echo "[init] done"
