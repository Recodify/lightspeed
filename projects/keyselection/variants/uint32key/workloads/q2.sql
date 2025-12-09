/* Q2 — Cold key lookup (rare key) */
/* KEY TYPE: UInt16 */
/* SCHEMA: timeseriesdata(id UInt16, timestamp DateTime64(3)) */

SELECT count() AS cnt
FROM timeseriesdata
WHERE id = 1391