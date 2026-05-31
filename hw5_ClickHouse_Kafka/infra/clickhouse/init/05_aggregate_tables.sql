CREATE TABLE IF NOT EXISTS cinema.daily_user_activity
(
    event_date        Date,
    dau_state         AggregateFunction(uniq, String),
    started_count     SimpleAggregateFunction(sum, UInt64),
    finished_count    SimpleAggregateFunction(sum, UInt64),
    avg_watch_state   AggregateFunction(avg, Int32)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY event_date;

CREATE TABLE IF NOT EXISTS cinema.daily_movie_views
(
    event_date Date,
    movie_id   String,
    views      UInt64
)
ENGINE = SummingMergeTree((views))
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, movie_id);

CREATE TABLE IF NOT EXISTS cinema.user_first_seen
(
    user_id    String,
    first_date SimpleAggregateFunction(min, Date)
)
ENGINE = AggregatingMergeTree
ORDER BY user_id;

CREATE TABLE IF NOT EXISTS cinema.daily_user_seen
(
    event_date Date,
    user_id    String
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, user_id);

CREATE TABLE IF NOT EXISTS cinema.daily_device_distribution
(
    event_date  Date,
    device_type LowCardinality(String),
    events      SimpleAggregateFunction(sum, UInt64),
    users_state AggregateFunction(uniq, String)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, device_type);
