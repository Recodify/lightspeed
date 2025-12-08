-- Template used when data.load_method = 'script'
-- {table}, {file_path}, and {format} are populated by the harness
INSERT INTO {table}
SELECT
    event_id,
    user_id,
    event_type,
    parseDateTimeBestEffort(event_time) AS event_time,
    properties
FROM file('{file_path}', '{format}');
