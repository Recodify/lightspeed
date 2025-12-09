/* Q4 — Top‑K by key */
/* KEY TYPE: LowCardinality(String) */
/* SCHEMA: timeseriesdata(name LowCardinality(String), timestamp DateTime64(3)) */

SELECT
  name,
  count() AS cnt
FROM timeseriesdata
GROUP BY name
ORDER BY cnt DESC
LIMIT 100