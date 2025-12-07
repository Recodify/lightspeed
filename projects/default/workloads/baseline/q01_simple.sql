-- Simple query: Count events by type
SELECT
    event_type,
    count() as event_count
FROM events
GROUP BY event_type
ORDER BY event_count DESC
