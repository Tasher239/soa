CREATE TABLE IF NOT EXISTS cinema.events
(
    event_id         UUID,
    user_id          String,
    movie_id         String,
    event_type       LowCardinality(String),
    event_date       Date MATERIALIZED toDate(timestamp),
    timestamp        DateTime64(6, 'UTC'),
    device_type      LowCardinality(String),
    session_id       String,
    progress_seconds Nullable(Int32),
    search_query     Nullable(String),
    client_version   Nullable(String),
    ingested_at      DateTime DEFAULT now()
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event_date, user_id, timestamp, event_id)
TTL toDateTime(timestamp) + INTERVAL 365 DAY
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS cinema.events_kafka_errors
(
    topic       String,
    partition   Int64,
    offset      Int64,
    raw_message String,
    error       String,
    ingested_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY ingested_at
TTL ingested_at + INTERVAL 7 DAY;
