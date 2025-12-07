## 400 bad request when trying to fetch results from a long run

in metrics_collector we currently do:


```sql
 SELECT
            query_id,
            query_duration_ms,
            read_rows,
            read_bytes,
            result_rows,
            result_bytes,
            memory_usage
        FROM system.query_log
        WHERE type = 'QueryFinish'
            AND query_id IN ({query_ids_clause})
            AND event_time >= toDateTime('{start_time_str}')
            AND event_time <= toDateTime('{end_time_str}')
        ORDER BY event_time DESC
```

this works fine if the number of query_ids is below a certain threshold. Works for for say 4 concurrent works on a 10 second duration.
However if we increase duration to 60seconds, there are so many query ids, that clickhouse throws a 400, when we execute the above query.