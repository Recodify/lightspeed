# Benchmark Results

## Metadata

- **Project**: default
- **Variant**: default
- **Workload**: basic_benchmark
- **Concurrency**: 4
- **Start Time**: 2025-12-07 15:35:04
- **End Time**: 2025-12-07 15:35:14
- **Duration**: 10.01 seconds

## Query Performance

| Query Name | Count | Errors | Error Rate | QPS | p50 (ms) | p95 (ms) | p99 (ms) | Avg Rows Read | Avg Bytes Read | Avg Memory (bytes) |
|------------|-------|--------|------------|-----|----------|----------|----------|---------------|----------------|--------------------|
| q01_simple.sql | 1577 | 0 | 0.00% | 157.54 | 10.26 | 21.55 | 30.69 | 20 | 266 | 5371606 |
| q02_aggregate.sql | 1567 | 0 | 0.00% | 156.54 | 12.46 | 23.56 | 32.43 | 20 | 426 | 5467781 |

## Summary

- **Total Queries Executed**: 3144
- **Total Errors**: 0
- **Overall Error Rate**: 0.00%
- **Overall QPS**: 314.09
