SELECT count() AS cnt
FROM timeseriesdata
WHERE uuid_id = toUUID('b710f463-a08a-4328-adce-0edb8a74f15d')
  AND timestamp >= toDateTime('2025-12-14')
  AND timestamp <  toDateTime('2025-12-18')