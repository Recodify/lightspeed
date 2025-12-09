/* Q6 — Distinct keys over a big slice */
/* KEY TYPE: LowCardinality(String) */
/* SCHEMA: timeseriesdata(name LowCardinality(String), timestamp DateTime64(3)) */

SELECT
  countDistinct(name) AS distinct_keys
FROM timeseriesdata
WHERE timestamp >= toDateTime('2025-12-14')
  AND timestamp <  toDateTime('2025-12-18')