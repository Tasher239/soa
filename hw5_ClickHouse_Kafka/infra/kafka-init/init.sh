#!/usr/bin/env bash
set -euo pipefail

BROKERS="${KAFKA_BROKERS:-kafka-1:9092,kafka-2:9092}"
PRIMARY_BROKER="${PRIMARY_BROKER:-kafka-1:9092}"
SR_URL="${SCHEMA_REGISTRY_URL:-http://schema-registry:8081}"
TOPIC="${TOPIC:-movie-events}"
PARTITIONS="${PARTITIONS:-6}"
REPLICATION_FACTOR="${REPLICATION_FACTOR:-2}"
MIN_ISR="${MIN_ISR:-1}"
SCHEMA_FILE="${SCHEMA_FILE:-/schemas/avro/movie_event.avsc}"

log() { echo "[kafka-init] $*"; }

log "Waiting for brokers [$BROKERS]..."
IFS=',' read -ra broker_arr <<< "$BROKERS"
for b in "${broker_arr[@]}"; do
  until kafka-broker-api-versions --bootstrap-server "$b" >/dev/null 2>&1; do
    log "  still waiting on $b"
    sleep 2
  done
  log "  broker $b is up"
done

log "Creating topic $TOPIC (partitions=$PARTITIONS, RF=$REPLICATION_FACTOR, MIR=$MIN_ISR)"
kafka-topics --bootstrap-server "$PRIMARY_BROKER" \
  --create --if-not-exists \
  --topic "$TOPIC" \
  --partitions "$PARTITIONS" \
  --replication-factor "$REPLICATION_FACTOR" \
  --config "min.insync.replicas=$MIN_ISR" \
  --config "retention.ms=604800000" \
  --config "compression.type=producer"

log "Describing topic:"
kafka-topics --bootstrap-server "$PRIMARY_BROKER" --describe --topic "$TOPIC"

if [[ "$REPLICATION_FACTOR" -ge 2 && "$PARTITIONS" -gt 0 ]]; then
  log "Pinning preferred replicas for $TOPIC to broker 1 first (keeps writes available when kafka-2 is paused)"
  python3 - "$TOPIC" "$PARTITIONS" >/tmp/reassignment.json <<'PY'
import json
import sys

topic = sys.argv[1]
partitions = int(sys.argv[2])
print(json.dumps({
    "version": 1,
    "partitions": [
        {"topic": topic, "partition": p, "replicas": [1, 2]}
        for p in range(partitions)
    ],
}))
PY
  kafka-reassign-partitions --bootstrap-server "$PRIMARY_BROKER" \
    --reassignment-json-file /tmp/reassignment.json \
    --execute || true

  python3 - "$TOPIC" "$PARTITIONS" >/tmp/leader-election.json <<'PY'
import json
import sys

topic = sys.argv[1]
partitions = int(sys.argv[2])
print(json.dumps({
    "partitions": [
        {"topic": topic, "partition": p}
        for p in range(partitions)
    ],
}))
PY
  kafka-leader-election --bootstrap-server "$PRIMARY_BROKER" \
    --election-type PREFERRED \
    --path-to-json-file /tmp/leader-election.json || true

  log "Topic after preferred leader election:"
  kafka-topics --bootstrap-server "$PRIMARY_BROKER" --describe --topic "$TOPIC"
fi

log "Waiting for Schema Registry at $SR_URL..."
until curl -fsS "$SR_URL/subjects" >/dev/null 2>&1; do
  sleep 2
done

log "Setting global compatibility to BACKWARD"
curl -fsS -X PUT -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data '{"compatibility":"BACKWARD"}' \
  "$SR_URL/config" >/dev/null || true

SUBJECT="${TOPIC}-value"
log "Registering Avro schema at subject=$SUBJECT from $SCHEMA_FILE"
if [[ ! -f "$SCHEMA_FILE" ]]; then
  log "ERROR: schema file missing: $SCHEMA_FILE"
  exit 1
fi

# Build Schema Registry payload: {"schema": "<escaped JSON string>", "schemaType": "AVRO"}
payload=$(python3 - "$SCHEMA_FILE" <<'PY'
import json
import pathlib
import sys

schema_path = pathlib.Path(sys.argv[1])
print(json.dumps({"schema": schema_path.read_text(), "schemaType": "AVRO"}))
PY
)

curl -fsS -X POST \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data "$payload" \
  "$SR_URL/subjects/$SUBJECT/versions"

echo
log "Subject compatibility set to BACKWARD"
curl -fsS -X PUT -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data '{"compatibility":"BACKWARD"}' \
  "$SR_URL/config/$SUBJECT" >/dev/null

log "Current versions for $SUBJECT:"
curl -fsS "$SR_URL/subjects/$SUBJECT/versions"
echo
log "Kafka init finished successfully."
