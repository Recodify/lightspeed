SELECT
  uuid_id,
  count() AS cnt
FROM timeseriesdata
WHERE timestamp >= toDateTime('2025-12-14')
  AND timestamp <  toDateTime('2025-12-18')
GROUP BY uuid_id