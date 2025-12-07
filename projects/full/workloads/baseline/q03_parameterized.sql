-- Parameterized query: Filter by event_type
-- Uses parameters: {event_type}
SELECT
    event_id,
    event_type,
    event_time,
    properties
FROM events
WHERE event_type = '{event_type}'
ORDER BY event_time DESC
LIMIT 10
