SELECT
  uuid_id,
  count() AS cnt
FROM timeseriesdata
GROUP BY uuid_id
ORDER BY cnt DESC
LIMIT 100