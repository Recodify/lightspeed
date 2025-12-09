/* Q2 — Cold key lookup (rare key) */
/* KEY TYPE: LowCardinality(String) */
/* SCHEMA: timeseriesdata(name LowCardinality(String), timestamp DateTime64(3)) */

SELECT count() AS cnt
FROM timeseriesdata
WHERE name = 'EDFT.SEXY.BUTTERFLY.ILLUSTRIOUS.MAMMOTH.ELASTIC.BUG.CAREFUL.PORCU.EDFT'