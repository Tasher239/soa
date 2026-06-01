.PHONY: up down restart build test-unit test-int test-e2e test-all load slo-check alert-error alert-down logs ps

COMPOSE = docker compose
PROMETHEUS_URL ?= http://localhost:9090
PRODUCER_URL ?= http://localhost:8000

up:
	$(COMPOSE) up -d --build
	@echo "Waiting for services to be healthy..."
	@timeout 240 bash -c 'until $(COMPOSE) ps | grep -E "producer.*healthy"; do sleep 5; done'
	@echo "Stack is up. URLs:"
	@echo "  Producer API: http://localhost:8000/docs"
	@echo "  Aggregator API: http://localhost:8001/docs"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Grafana: http://localhost:3000 (admin/admin)"
	@echo "  Alertmanager: http://localhost:9093"

down:
	$(COMPOSE) down -v

restart: down up

build:
	$(COMPOSE) build --parallel

test-unit:
	pip install -q services/shared/ fastapi httpx pytest pytest-asyncio prometheus-client
	pytest tests/unit -v --tb=short

test-int:
	$(COMPOSE) up -d kafka-1 kafka-2 kafka-3 schema-registry kafka-init \
		clickhouse postgres minio minio-init aggregator-migrate producer aggregator
	@timeout 180 bash -c 'until $(COMPOSE) ps | grep -E "producer.*healthy" && $(COMPOSE) ps | grep -E "aggregator.*healthy"; do sleep 5; done'
	pip install -q services/shared/ httpx pytest pytest-asyncio clickhouse-connect asyncpg "confluent-kafka[avro,schemaregistry]"
	PRODUCER_URL=http://localhost:8000 \
	AGGREGATOR_URL=http://localhost:8001 \
	CLICKHOUSE_HOST=localhost CLICKHOUSE_PORT=8123 \
	POSTGRES_DSN=[Secrets52]:[Secrets53]:[Secrets54]:[Secrets55]/cinema \
	KAFKA_BOOTSTRAP_SERVERS=localhost:19092 \
	SCHEMA_REGISTRY_URL=http://localhost:8081 \
	pytest tests/integration -v --tb=short

test-e2e:
	$(COMPOSE) up -d kafka-1 kafka-2 kafka-3 schema-registry kafka-init \
		clickhouse postgres minio minio-init aggregator-migrate producer aggregator
	@timeout 180 bash -c 'until $(COMPOSE) ps | grep -E "producer.*healthy" && $(COMPOSE) ps | grep -E "aggregator.*healthy"; do sleep 5; done'
	pip install -q services/shared/ httpx pytest pytest-asyncio clickhouse-connect asyncpg
	PRODUCER_URL=http://localhost:8000 \
	AGGREGATOR_URL=http://localhost:8001 \
	CLICKHOUSE_HOST=localhost CLICKHOUSE_PORT=8123 \
	POSTGRES_DSN=[Secrets56]:[Secrets57]:[Secrets58]:[Secrets59]/cinema \
	pytest tests/e2e -v --tb=short

test-all: test-unit test-int test-e2e

load:
	mkdir -p artifacts
	docker run --rm \
		--network host \
		-e PRODUCER_URL=$(PRODUCER_URL) \
		-v "$(CURDIR)/tests/load:/scripts" \
		-v "$(CURDIR)/artifacts:/out" \
		-w /out \
		grafana/k6:0.55.0 run /scripts/k6_load.js

slo-check:
	pip install -q httpx
	PROMETHEUS_URL=$(PROMETHEUS_URL) python tests/load/slo_check.py

alert-error:
	@echo "Generating 5xx errors for HighErrorRate alert demo..."
	docker run --rm --network host grafana/k6:0.55.0 run - <<'EOF'
	import http from 'k6/http'; import { sleep } from 'k6';
	export const options = { vus: 5, duration: '6m' };
	export default function() { http.get('http://localhost:8000/nonexistent'); sleep(0.1); }
	EOF

alert-down:
	@echo "Stopping aggregator for TargetDown alert demo (restore with: make up)..."
	$(COMPOSE) stop aggregator
	@echo "Aggregator stopped. Alertmanager should fire TargetDown within 1 minute."
	@echo "Restore with: docker compose start aggregator"

logs:
	$(COMPOSE) logs -f producer aggregator

ps:
	$(COMPOSE) ps
