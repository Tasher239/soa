from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

consumer_lag = Gauge(
    "consumer_lag",
    "Difference between Kafka topic HEAD and committed offset per partition",
    labelnames=("topic", "partition"),
)

events_processed_total = Counter(
    "events_processed_total",
    "Total events processed successfully",
    labelnames=("event_type",),
)

events_skipped_total = Counter(
    "events_skipped_total",
    "Events skipped (duplicates or out-of-order)",
    labelnames=("event_type", "reason"),
)

events_dlq_total = Counter(
    "events_dlq_total",
    "Events routed to DLQ",
    labelnames=("error_code",),
)

event_processing_duration_seconds = Histogram(
    "event_processing_duration_seconds",
    "Time spent processing a single event",
    labelnames=("event_type",),
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

cassandra_write_errors_total = Counter(
    "cassandra_write_errors_total",
    "Number of Cassandra write failures",
)


def render() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
