/* Q1 — Hot key point lookup within a time window */
/* KEY TYPE: UInt16 */
/* SCHEMA: timeseriesdata(id UInt16, timestamp DateTime64(3)) */

SELECT count() AS cnt
FROM timeseriesdata
WHERE id = 68
  AND timestamp >= toDateTime('2025-12-14')
  AND timestamp <  toDateTime('2025-12-18')