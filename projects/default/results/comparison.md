# Benchmark Comparison

**Baseline (A):** `projects/default/results/benchmark_results.csv`

**Comparison (B):** `projects/default/results/variant1_results.csv`

## Performance Comparison

| Query | A p50 (ms) | B p50 (ms) | Δ p50 | A p95 (ms) | B p95 (ms) | Δ p95 | A QPS | B QPS | Δ QPS |
|-------|------------|------------|-------|------------|------------|-------|-------|-------|-------|
| q01_simple.sql | 10.20 | 9.32 | -8.63% | 19.61 | 16.77 | -14.48% | 163.10 | 175.29 | +7.47% |
| q02_aggregate.sql | 12.03 | 11.30 | -6.07% | 21.05 | 20.54 | -2.42% | 163.00 | 177.19 | +8.71% |

## Interpretation

- **Positive Δ p50/p95**: Latency increased (slower)
- **Negative Δ p50/p95**: Latency decreased (faster)
- **Positive Δ QPS**: Throughput increased (better)
- **Negative Δ QPS**: Throughput decreased (worse)
- **new**: Query only in comparison (B)
- **removed**: Query only in baseline (A)
- **+∞**: Baseline value was zero
