# Benchmark Results

## Metadata

- **Project**: default
- **Variant**: default
- **Workload**: basic_benchmark
- **Concurrency**: 4
- **Start Time**: 2025-12-07 15:27:47
- **End Time**: 2025-12-07 15:27:57
- **Duration**: 10.00 seconds

## Query Performance

| Query Name | Count | Errors | Error Rate | QPS | p50 (ms) | p95 (ms) | p99 (ms) | Avg Rows Read | Avg Bytes Read | Avg Memory (bytes) |
|------------|-------|--------|------------|-----|----------|----------|----------|---------------|----------------|--------------------|
| q01_simple.sql | 1710 | 0 | 0.00% | 170.95 | 9.17 | 17.89 | 25.70 | 20 | 266 | 5372038 |
| q02_aggregate.sql | 1812 | 0 | 0.00% | 181.15 | 11.26 | 20.33 | 28.90 | 20 | 426 | 5468507 |

## Summary

- **Total Queries Executed**: 3522
- **Total Errors**: 0
- **Overall Error Rate**: 0.00%
- **Overall QPS**: 352.09
