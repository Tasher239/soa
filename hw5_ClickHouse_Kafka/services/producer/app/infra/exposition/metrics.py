from prometheus_client import Counter, Histogram

EVENTS_PRODUCED = Counter(
    "cinema_producer_events_total",
    "Number of events successfully published to Kafka",
    ["event_type"],
)
EVENTS_FAILED = Counter(
    "cinema_producer_events_failed_total",
    "Number of events that failed to publish after retries",
    ["event_type", "reason"],
)
PUBLISH_LATENCY = Histogram(
    "cinema_producer_publish_seconds",
    "Wall-clock time to publish a single event (including retries)",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)