-- Example schema for benchmark testing
-- Creates a simple events table for tracking user activities

CREATE TABLE IF NOT EXISTS events (
    event_id UInt64,
    user_id UInt32,
    event_type String,
    event_time DateTime,
    properties String
) ENGINE = MergeTree()
ORDER BY (event_time, user_id)
PARTITION BY toYYYYMM(event_time)
SETTINGS index_granularity = 8192;
