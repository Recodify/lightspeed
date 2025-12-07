# Benchmark Results

## Metadata

- **Project**: default
- **Variant**: variant1
- **Workload**: basic_benchmark
- **Concurrency**: 4
- **Start Time**: 2025-12-07 14:53:14
- **End Time**: 2025-12-07 14:53:24
- **Duration**: 10.01 seconds

## Query Performance

| Query Name | Count | Errors | Error Rate | QPS | p50 (ms) | p95 (ms) | p99 (ms) | Avg Rows Read | Avg Bytes Read | Avg Memory (bytes) |
|------------|-------|--------|------------|-----|----------|----------|----------|---------------|----------------|--------------------|
| q01_simple.sql | 1629 | 0 | 0.00% | 162.75 | 9.88 | 19.70 | 27.03 | 20 | 266 | 5372115 |
| q02_aggregate.sql | 1673 | 0 | 0.00% | 167.15 | 12.01 | 21.54 | 28.60 | 20 | 426 | 5468720 |

## Summary

- **Total Queries Executed**: 3302
- **Total Errors**: 0
- **Overall Error Rate**: 0.00%
- **Overall QPS**: 329.90
