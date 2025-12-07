# Benchmark Results

## Metadata

- **Project**: default
- **Variant**: variant1
- **Workload**: basic_benchmark
- **Concurrency**: 4
- **Start Time**: 2025-12-07 15:39:34
- **End Time**: 2025-12-07 15:39:44
- **Duration**: 10.01 seconds

## Query Performance

| Query Name | Count | Errors | Error Rate | QPS | p50 (ms) | p95 (ms) | p99 (ms) | Avg Rows Read | Avg Bytes Read | Avg Memory (bytes) |
|------------|-------|--------|------------|-----|----------|----------|----------|---------------|----------------|--------------------|
| q01_simple.sql | 1510 | 0 | 0.00% | 150.82 | 10.82 | 23.59 | 33.28 | 20 | 266 | 5371723 |
| q02_aggregate.sql | 1427 | 0 | 0.00% | 142.53 | 13.06 | 27.61 | 37.75 | 20 | 426 | 5468186 |

## Summary

- **Total Queries Executed**: 2937
- **Total Errors**: 0
- **Overall Error Rate**: 0.00%
- **Overall QPS**: 293.35
