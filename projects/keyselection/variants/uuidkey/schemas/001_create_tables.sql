-- Example schema for benchmark testing
-- Creates a simple events table for tracking user activities

CREATE TABLE IF NOT EXISTS timeseriesdata (
    uuid_id UUID,
    timestamp DateTime64(3)
) ENGINE = MergeTree()
ORDER BY (uuid_id, timestamp)
PARTITION BY toYYYYMM(timestamp)
SETTINGS index_granularity = 8192
