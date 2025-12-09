/* Q1 — Hot key point lookup within a time window */
/* KEY TYPE: LowCardinality(String) */
/* SCHEMA: timeseriesdata(name LowCardinality(String), timestamp DateTime64(3)) */

SELECT count() AS cnt
FROM timeseriesdata
WHERE name = 'EDFT.DANCING.GOOSE.NANO.SKUA.INQUISITIVE.HARRIER.LIBERAL.LABRADOR.EDFT'
  AND timestamp >= toDateTime('2025-12-14')
  AND timestamp <  toDateTime('2025-12-18')