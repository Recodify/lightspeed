 N-Way Benchmark Comparison

**Run**: abstractbullmastiff
**Config**: three
**Variants Compared**: 4 variants

| Variant | Results Path |
|---------|--------------|
| baseline | `/path/to/results/three/abstractbullmastiff/baseline/results.json` |
| optimized_index | `/path/to/results/three/abstractbullmastiff/optimized_index/results.json` |
| partitioned | `/path/to/results/three/abstractbullmastiff/partitioned/results.json` |
| compressed | `/path/to/results/three/abstractbullmastiff/compressed/results.json` |

---

## Executive Summary

**Overall Winner**: optimized_index (wins 12/15 queries on p50 latency)

**Win Distribution** (based on p50 latency):
- optimized_index: 12 queries (80.0%)
- partitioned: 2 queries (13.3%)
- baseline: 1 query (6.7%)
- compressed: 0 queries (0.0%)

---

## Section 1: Side-by-Side Performance Comparison

### Query: q01_agg_max.sql
*(Available in: baseline, optimized_index, partitioned, compressed)*

| Metric | baseline | optimized_index | partitioned | compressed | Best | Δ (baseline) | Δ (optimized_index) | Δ (partitioned) | Δ (compressed) |
|--------|----------|-----------------|-------------|------------|------|--------------|---------------------|-----------------|----------------|
| p50 (ms) | 8.52 | 7.21 | 8.45 | 9.12 | optimized_index | +18.2% | - | +17.2% | +26.5% |
| p95 (ms) | 14.58 | 12.34 | 14.23 | 15.67 | optimized_index | +18.2% | - | +15.3% | +27.0% |
| Avg (ms) | 4.08 | 3.45 | 4.02 | 4.38 | optimized_index | +18.3% | - | +16.5% | +27.0% |
| QPS | 429.24 | 506.12 | 437.89 | 398.76 | optimized_index | -15.2% | - | -13.5% | -21.2% |

**Winner for this query**: optimized_index

---

### Query: q02_point_lookup.sql
*(Available in: baseline, optimized_index, partitioned)*

| Metric | baseline | optimized_index | partitioned | compressed | Best | Δ (baseline) | Δ (optimized_index) | Δ (partitioned) | Δ (compressed) |
|--------|----------|-----------------|-------------|------------|------|--------------|---------------------|-----------------|----------------|
| p50 (ms) | 2.15 | 0.98 | 2.08 | N/A | optimized_index | +119.4% | - | +112.2% | N/A |
| p95 (ms) | 3.42 | 1.56 | 3.21 | N/A | optimized_index | +119.2% | - | +105.8% | N/A |
| Avg (ms) | 1.87 | 0.89 | 1.79 | N/A | optimized_index | +110.1% | - | +101.1% | N/A |
| QPS | 1245.67 | 2784.32 | 1298.45 | N/A | optimized_index | -55.3% | - | -53.4% | N/A |

**Winner for this query**: optimized_index

---

### Query: q03_scan_range.sql
*(Available in: baseline, optimized_index, partitioned, compressed)*

| Metric | baseline | optimized_index | partitioned | compressed | Best | Δ (baseline) | Δ (optimized_index) | Δ (partitioned) | Δ (compressed) |
|--------|----------|-----------------|-------------|------------|------|--------------|---------------------|-----------------|----------------|
| p50 (ms) | 156.34 | 142.12 | 98.45 | 167.89 | partitioned | +58.8% | +44.3% | - | +70.5% |
| p95 (ms) | 234.56 | 218.34 | 156.78 | 252.12 | partitioned | +49.6% | +39.3% | - | +60.8% |
| Avg (ms) | 134.23 | 128.45 | 89.34 | 145.67 | partitioned | +50.2% | +43.8% | - | +63.1% |
| QPS | 45.67 | 50.23 | 72.34 | 41.23 | partitioned | -36.9% | -30.6% | - | -43.0% |

**Winner for this query**: partitioned

---

### Query: q04_aggregation.sql
*(Available in: baseline, optimized_index, compressed)*

| Metric | baseline | optimized_index | partitioned | compressed | Best | Δ (baseline) | Δ (optimized_index) | Δ (partitioned) | Δ (compressed) |
|--------|----------|-----------------|-------------|------------|------|--------------|---------------------|-----------------|----------------|
| p50 (ms) | 45.67 | 42.34 | N/A | 43.12 | optimized_index | +7.9% | - | N/A | +1.8% |
| p95 (ms) | 67.89 | 63.45 | N/A | 64.23 | optimized_index | +7.0% | - | N/A | +1.2% |
| Avg (ms) | 38.45 | 35.67 | N/A | 36.89 | optimized_index | +7.8% | - | N/A | +3.4% |
| QPS | 156.78 | 168.34 | N/A | 163.45 | optimized_index | -6.9% | - | N/A | -2.9% |

**Winner for this query**: optimized_index

---

## Section 2: Rankings

### Ranking by p50 Latency (Average Across All Queries)

| Rank | Variant | Avg p50 (ms) | Relative to Best |
|------|---------|--------------|------------------|
| 1 | optimized_index | 48.16 | - |
| 2 | partitioned | 54.33 | +12.8% |
| 3 | baseline | 53.17 | +10.4% |
| 4 | compressed | 56.30 | +16.9% |

### Ranking by p95 Latency (Average Across All Queries)

| Rank | Variant | Avg p95 (ms) | Relative to Best |
|------|---------|--------------|------------------|
| 1 | optimized_index | 73.92 | - |
| 2 | partitioned | 81.31 | +10.0% |
| 3 | baseline | 80.11 | +8.4% |
| 4 | compressed | 86.01 | +16.4% |

### Ranking by QPS (Average Across All Queries)

| Rank | Variant | Avg QPS | Relative to Best |
|------|---------|---------|------------------|
| 1 | optimized_index | 682.50 | - |
| 2 | partitioned | 602.17 | -11.8% |
| 3 | baseline | 469.34 | -31.2% |
| 4 | compressed | 401.36 | -41.2% |

---

## Interpretation Guide

### Metrics
- **p50 (ms)**: Median query latency - 50% of queries complete faster
- **p95 (ms)**: 95th percentile latency - only 5% of queries are slower
- **Avg (ms)**: Average query duration across all executions
- **QPS**: Queries per second (throughput)

### Performance Direction
- **Latency** (p50, p95, Avg): Lower is better
- **Throughput** (QPS): Higher is better

### Symbols
- **N/A**: Query not available in this variant
- **-**: This variant is the best performer
- **Δ (delta)**: Percentage difference from best performer
  - Positive Δ in latency = slower (worse)
  - Negative Δ in latency = faster (better)
  - Positive Δ in QPS = higher throughput (better)
  - Negative Δ in QPS = lower throughput (worse)