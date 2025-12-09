/* Q7 — Mixed predicate query (count-only) */
/* KEY TYPE: UInt16 */
/* SCHEMA: timeseriesdata(id UInt16, timestamp DateTime64(3)) */

SELECT
  count() AS cnt
FROM timeseriesdata
WHERE id IN (23, 60, 768, 1695, 2115)
  AND timestamp >= toDateTime('2025-12-14')
  AND timestamp <  toDateTime('2025-12-18')