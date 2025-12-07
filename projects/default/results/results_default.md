# Benchmark Results

## Metadata

- **Project**: default
- **Variant**: default
- **Workload**: basic_benchmark
- **Concurrency**: 4
- **Start Time**: 2025-12-07 15:40:31
- **End Time**: 2025-12-07 15:40:41
- **Duration**: 10.01 seconds

## Query Performance

| Query Name | Count | Errors | Error Rate | QPS | p50 (ms) | p95 (ms) | p99 (ms) | Avg Rows Read | Avg Bytes Read | Avg Memory (bytes) |
|------------|-------|--------|------------|-----|----------|----------|----------|---------------|----------------|--------------------|
| q01_simple.sql | 1773 | 0 | 0.00% | 177.14 | 8.81 | 17.81 | 24.80 | 20 | 266 | 5371750 |
| q02_aggregate.sql | 1836 | 0 | 0.00% | 183.43 | 10.88 | 20.85 | 27.64 | 20 | 426 | 5468118 |

## Summary

- **Total Queries Executed**: 3609
- **Total Errors**: 0
- **Overall Error Rate**: 0.00%
- **Overall QPS**: 360.58
