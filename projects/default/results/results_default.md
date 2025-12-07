# Benchmark Results

## Metadata

- **Project**: default
- **Variant**: default
- **Workload**: basic_benchmark
- **Concurrency**: 4
- **Start Time**: 2025-12-07 14:52:46
- **End Time**: 2025-12-07 14:52:56
- **Duration**: 10.01 seconds

## Query Performance

| Query Name | Count | Errors | Error Rate | QPS | p50 (ms) | p95 (ms) | p99 (ms) | Avg Rows Read | Avg Bytes Read | Avg Memory (bytes) |
|------------|-------|--------|------------|-----|----------|----------|----------|---------------|----------------|--------------------|
| q01_simple.sql | 1592 | 0 | 0.00% | 159.07 | 9.86 | 20.58 | 28.98 | 20 | 266 | 5371946 |
| q02_aggregate.sql | 1588 | 0 | 0.00% | 158.67 | 12.50 | 23.91 | 32.28 | 20 | 426 | 5468483 |

## Summary

- **Total Queries Executed**: 3180
- **Total Errors**: 0
- **Overall Error Rate**: 0.00%
- **Overall QPS**: 317.75
