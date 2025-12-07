# Benchmark Results

## Metadata

- **Project**: default
- **Variant**: variant1
- **Workload**: basic_benchmark
- **Concurrency**: 4
- **Start Time**: 2025-12-07 14:20:47
- **End Time**: 2025-12-07 14:20:57
- **Duration**: 10.01 seconds

## Query Performance

| Query Name | Count | Errors | Error Rate | QPS | p50 (ms) | p95 (ms) | p99 (ms) | Avg Rows Read | Avg Bytes Read | Avg Memory (bytes) |
|------------|-------|--------|------------|-----|----------|----------|----------|---------------|----------------|--------------------|
| q01_simple.sql | 1698 | 0 | 0.00% | 169.70 | 9.30 | 18.36 | 25.02 | 20 | 266 | 5371351 |
| q02_aggregate.sql | 1770 | 0 | 0.00% | 176.89 | 11.41 | 20.71 | 30.67 | 20 | 426 | 5468585 |

## Summary

- **Total Queries Executed**: 3468
- **Total Errors**: 0
- **Overall Error Rate**: 0.00%
- **Overall QPS**: 346.59
