/* Q6 — Distinct keys over a big slice */
/* KEY TYPE: UInt16 */
/* SCHEMA: timeseriesdata(id UInt16, timestamp DateTime64(3)) */

SELECT
  countDistinct(id) AS distinct_keys
FROM timeseriesdata
WHERE timestamp >= toDateTime('2025-12-14')
  AND timestamp <  toDateTime('2025-12-18')