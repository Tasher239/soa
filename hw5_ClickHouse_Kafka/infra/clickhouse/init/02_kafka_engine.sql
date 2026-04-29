CREATE TABLE IF NOT EXISTS cinema.events_kafka
(
    event_id         UUID,
    user_id          String,
    movie_id         String,
    event_type       LowCardinality(String),
    timestamp        DateTime64(6, 'UTC'),
    device_type      LowCardinality(String),
    session_id       String,
    progress_seconds Nullable(Int32),
    search_query     Nullable(String),
    client_version   Nullable(String)
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list             = 'kafka-1:9092,kafka-2:9092,kafka-3:9092',
    kafka_topic_list              = 'movie-events',
    kafka_group_name              = 'clickhouse-ingestor',
    kafka_format                  = 'AvroConfluent',
    format_avro_schema_registry_url = 'http://schema-registry:8081',
    kafka_num_consumers           = 3,
    kafka_thread_per_consumer     = 1,
    kafka_max_block_size          = 65536,
    kafka_flush_interval_ms       = 1000,
    kafka_handle_error_mode       = 'stream';
