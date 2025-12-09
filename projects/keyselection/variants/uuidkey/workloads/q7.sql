SELECT
  count() AS cnt
FROM timeseriesdata
WHERE uuid_id IN (
    toUUID('2de101b3-5bab-4784-afcd-4334f963d603'),
    toUUID('ddff0746-9188-4a27-92a6-d095ac33c558'),
    toUUID('556f47f4-8052-4c9f-a69e-b28344db8048'),
    toUUID('3f9ce805-d3bc-4f90-853a-3e950c1ecd5d'),
    toUUID('b78936d2-d6b2-4cdc-9909-bb68bc678cc5')
  )
  AND timestamp >= toDateTime('2025-12-14')
  AND timestamp <  toDateTime('2025-12-18')