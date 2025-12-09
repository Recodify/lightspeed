/* Q3 — Group by key over a large window (count-only) */
/* KEY TYPE: LowCardinality(String) */
/* SCHEMA: timeseriesdata(name LowCardinality(String), timestamp DateTime64(3)) */

SELECT
  name,
  count() AS cnt
FROM timeseriesdata
WHERE timestamp >= toDateTime('2025-12-14')
  AND timestamp <  toDateTime('2025-12-18')
GROUP BY name