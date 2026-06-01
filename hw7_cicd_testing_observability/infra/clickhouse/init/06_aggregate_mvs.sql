CREATE MATERIALIZED VIEW IF NOT EXISTS cinema.daily_user_activity_mv
TO cinema.daily_user_activity AS
SELECT
    toDate(timestamp) AS event_date,
    uniqState(user_id) AS dau_state,
    countIf(event_type = 'VIEW_STARTED')  AS started_count,
    countIf(event_type = 'VIEW_FINISHED') AS finished_count,
    avgStateIf(toInt32(ifNull(progress_seconds, 0)), event_type = 'VIEW_FINISHED' AND isNotNull(progress_seconds)) AS avg_watch_state
FROM cinema.events
GROUP BY event_date;

CREATE MATERIALIZED VIEW IF NOT EXISTS cinema.daily_movie_views_mv
TO cinema.daily_movie_views AS
SELECT
    toDate(timestamp) AS event_date,
    movie_id,
    count() AS views
FROM cinema.events
WHERE event_type = 'VIEW_STARTED'
GROUP BY event_date, movie_id;

CREATE MATERIALIZED VIEW IF NOT EXISTS cinema.user_first_seen_mv
TO cinema.user_first_seen AS
SELECT
    user_id,
    min(toDate(timestamp)) AS first_date
FROM cinema.events
GROUP BY user_id;

CREATE MATERIALIZED VIEW IF NOT EXISTS cinema.daily_user_seen_mv
TO cinema.daily_user_seen AS
SELECT
    toDate(timestamp) AS event_date,
    user_id
FROM cinema.events
GROUP BY event_date, user_id;

CREATE MATERIALIZED VIEW IF NOT EXISTS cinema.daily_device_distribution_mv
TO cinema.daily_device_distribution AS
SELECT
    toDate(timestamp) AS event_date,
    device_type,
    count() AS events,
    uniqState(user_id) AS users_state
FROM cinema.events
GROUP BY event_date, device_type;
