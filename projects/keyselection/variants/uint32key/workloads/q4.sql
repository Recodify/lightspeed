/* Q4 — Top‑K by key */
/* KEY TYPE: UInt16 */
/* SCHEMA: timeseriesdata(id UInt16, timestamp DateTime64(3)) */

SELECT
  id,
  count() AS cnt
FROM timeseriesdata
GROUP BY id
ORDER BY cnt DESC
LIMIT 100