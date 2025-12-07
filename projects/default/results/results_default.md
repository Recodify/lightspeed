# Benchmark Results

## Metadata

- **Project**: default
- **Variant**: default
- **Workload**: basic_benchmark
- **Concurrency**: 4
- **Start Time**: 2025-12-07 14:21:21
- **End Time**: 2025-12-07 14:21:31
- **Duration**: 10.01 seconds

## Query Performance

| Query Name | Count | Errors | Error Rate | QPS | p50 (ms) | p95 (ms) | p99 (ms) | Avg Rows Read | Avg Bytes Read | Avg Memory (bytes) |
|------------|-------|--------|------------|-----|----------|----------|----------|---------------|----------------|--------------------|
| q01_simple.sql | 1753 | 0 | 0.00% | 175.14 | 9.39 | 18.20 | 27.92 | 20 | 266 | 5372052 |
| q02_aggregate.sql | 1708 | 0 | 0.00% | 170.65 | 11.46 | 21.09 | 29.01 | 20 | 426 | 5467361 |

## Summary

- **Total Queries Executed**: 3461
- **Total Errors**: 0
- **Overall Error Rate**: 0.00%
- **Overall QPS**: 345.79
