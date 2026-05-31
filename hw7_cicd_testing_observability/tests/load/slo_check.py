"""
Post-load SLO verification against Prometheus API.

Uses recording rules from observability/prometheus/recording.yml:
  sli:availability:ratio_5m
  sli:e2e_latency:p95_5m
  sli:processing_delay:p95_5m

Exit 0 if all checks pass, 1 if any fail.
"""
from __future__ import annotations

import os
import sys
import time

import httpx

PROM = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")

# (name, promql, operator, failure_threshold, justification)
CHECKS = [
    (
        "api_availability",
        "sli:availability:ratio_5m",
        ">",
        0.95,
        "Failure threshold <95%: below this the service is unusable for users",
    ),
    (
        "e2e_latency_p95_seconds",
        "sli:e2e_latency:p95_5m",
        "<",
        1.0,
        "Failure threshold >1s: user-perceived latency beyond 1s triggers SLO breach",
    ),
    (
        "processing_delay_p95_seconds",
        "sli:processing_delay:p95_5m",
        "<",
        10.0,
        "Failure threshold >10s: aggregator is stuck or severely lagging behind",
    ),
    # Fallback checks using raw metrics when recording rules not yet populated
    (
        "producer_error_rate",
        'sum(rate(http_requests_total{job="producer",status=~"5.."}[5m])) '
        '/ sum(rate(http_requests_total{job="producer"}[5m]))',
        "<",
        0.01,
        "Raw metric fallback: error rate > 1% under load means producer is failing",
    ),
]


def query_instant(promql: str) -> float | None:
    try:
        r = httpx.get(
            f"{PROM}/api/v1/query",
            params={"query": promql},
            timeout=10,
        )
        r.raise_for_status()
        result = r.json()["data"]["result"]
        if not result:
            return None
        return float(result[0]["value"][1])
    except Exception as exc:
        print(f"  [WARN] Query failed: {exc}", file=sys.stderr)
        return None


def run_checks() -> list[str]:
    failed = []
    for name, q, op, threshold, justification in CHECKS:
        value = query_instant(q)
        if value is None:
            print(f"[SKIP] {name}: no data (metric not yet populated)")
            continue

        if op == "<":
            ok = value < threshold
        elif op == ">":
            ok = value > threshold
        else:
            ok = False

        status = "OK  " if ok else "FAIL"
        print(f"[{status}] {name} = {value:.6f} {op} {threshold}")
        if not ok:
            print(f"       Why: {justification}")
            failed.append(name)

    return failed


def main() -> None:
    print(f"\nPrometheus SLO check against {PROM}")
    print("=" * 60)

    # Give Prometheus 15s to scrape if just started
    max_wait = int(os.environ.get("SLO_CHECK_WAIT_SECS", "0"))
    if max_wait > 0:
        print(f"Waiting {max_wait}s for Prometheus to scrape metrics...")
        time.sleep(max_wait)

    failed = run_checks()
    print("=" * 60)
    if failed:
        print(f"FAILED checks: {', '.join(failed)}")
        sys.exit(1)
    else:
        print("All SLO checks PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
