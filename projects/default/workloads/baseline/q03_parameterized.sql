-- Parameterized query: Filter by user_id and event_type
-- Uses parameters: {user_id} and {event_type}
SELECT
    event_id,
    event_type,
    event_time,
    properties
FROM events
WHERE user_id = {user_id}
  AND event_type = '{event_type}'
ORDER BY event_time DESC
LIMIT 10
