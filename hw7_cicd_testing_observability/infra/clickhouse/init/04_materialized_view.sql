CREATE MATERIALIZED VIEW IF NOT EXISTS cinema.events_mv TO cinema.events AS
SELECT
    event_id,
    user_id,
    movie_id,
    event_type,
    timestamp,
    device_type,
    session_id,
    progress_seconds,
    search_query,
    client_version
FROM cinema.events_kafka
WHERE length(_error) = 0;

CREATE MATERIALIZED VIEW IF NOT EXISTS cinema.events_kafka_errors_mv TO cinema.events_kafka_errors AS
SELECT
    _topic       AS topic,
    _partition   AS partition,
    _offset      AS offset,
    _raw_message AS raw_message,
    _error       AS error
FROM cinema.events_kafka
WHERE length(_error) > 0;
