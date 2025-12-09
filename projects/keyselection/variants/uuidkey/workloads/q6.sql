SELECT
  countDistinct(uuid_id) AS distinct_keys
FROM timeseriesdata
WHERE timestamp >= toDateTime('2025-12-14')
  AND timestamp <  toDateTime('2025-12-18')