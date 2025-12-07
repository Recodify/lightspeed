-- Aggregate query: Events per user with time range
SELECT
    user_id,
    count() as total_events,
    countIf(event_type = 'login') as logins,
    countIf(event_type = 'purchase') as purchases,
    min(event_time) as first_event,
    max(event_time) as last_event
FROM events
WHERE event_time >= '2024-01-01 00:00:00'
  AND event_time < '2024-01-02 00:00:00'
GROUP BY user_id
ORDER BY total_events DESC
LIMIT 100
