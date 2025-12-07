# Benchmark Results

## Metadata

- **Project**: default
- **Variant**: default
- **Workload**: basic_benchmark
- **Concurrency**: 4
- **Start Time**: 2025-12-07 12:12:44
- **End Time**: 2025-12-07 12:12:54
- **Duration**: 10.00 seconds

## Query Performance

| Query Name | Count | Errors | Error Rate | QPS | p50 (ms) | p95 (ms) | p99 (ms) | Avg Rows Read | Avg Bytes Read | Avg Memory (bytes) |
|------------|-------|--------|------------|-----|----------|----------|----------|---------------|----------------|--------------------|
| q01_simple.sql | 1709 | 0 | 0.00% | 170.85 | 9.50 | 17.33 | 23.06 | 20 | 266 | 5372254 |
| q02_aggregate.sql | 1794 | 0 | 0.00% | 179.35 | 11.32 | 19.94 | 28.25 | 20 | 426 | 5468774 |

## Summary

- **Total Queries Executed**: 3503
- **Total Errors**: 0
- **Overall Error Rate**: 0.00%
- **Overall QPS**: 350.19
