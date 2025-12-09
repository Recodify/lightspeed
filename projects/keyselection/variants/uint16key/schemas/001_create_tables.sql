-- Example schema for benchmark testing
-- Creates a simple events table for tracking user activities

CREATE TABLE IF NOT EXISTS timeseriesdata (
    id UInt16,
    timestamp DateTime64(3)
) ENGINE = MergeTree()
ORDER BY (id, timestamp)
PARTITION BY toYYYYMM(timestamp)
SETTINGS index_granularity = 8192
