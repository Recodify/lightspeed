# Benchmark Results

## Metadata

- **Project**: default
- **Variant**: variant1
- **Workload**: variant1_benchmark
- **Concurrency**: 4
- **Start Time**: 2025-12-07 12:17:55
- **End Time**: 2025-12-07 12:18:05
- **Duration**: 10.01 seconds

## Query Performance

| Query Name | Count | Errors | Error Rate | QPS | p50 (ms) | p95 (ms) | p99 (ms) | Avg Rows Read | Avg Bytes Read | Avg Memory (bytes) |
|------------|-------|--------|------------|-----|----------|----------|----------|---------------|----------------|--------------------|
| q01_simple.sql | 1754 | 0 | 0.00% | 175.29 | 9.32 | 16.77 | 24.85 | 20 | 266 | 5372326 |
| q02_aggregate.sql | 1773 | 0 | 0.00% | 177.19 | 11.30 | 20.54 | 28.18 | 20 | 426 | 5468819 |

## Summary

- **Total Queries Executed**: 3527
- **Total Errors**: 0
- **Overall Error Rate**: 0.00%
- **Overall QPS**: 352.49
