# N-Way Multi-Variant Comparison Implementation Plan

## Summary
Replace pairwise comparisons with a single comprehensive N-way comparison that shows all variants side-by-side with rankings and deltas relative to best performer.

**User Requirements:**
- Replace pairwise comparisons (no longer generate `comparison_v0_vs_v1.md`, etc.)
- Generate single report: `comparison_all_variants.md`
- Include both side-by-side table AND rankings
- Show deltas relative to best performer per metric

## Critical Files

### 1. `/home/sam/code/lightspeed/harness/comparator.py`
**Add new function:** `compare_all_variants(variant_results: list[tuple[str, str]], output_path: str)`

**Key components to implement:**
- Main orchestration function that loads all variant results
- Helper: `_compare_query_across_variants()` - collects metrics from all variants for single query, determines best performer
- Helper: `_calculate_rankings()` - ranks variants by average p50, p95, QPS
- Helper: `_determine_overall_winner()` - counts wins per variant
- Report generation helpers for each section

**Reuse existing:** `_load_results()` utility already handles JSON/CSV loading

### 2. `/home/sam/code/lightspeed/harness/cli.py` (lines 418-430)
**Replace pairwise loop with:**
```python
if len(run_results) > 1:
    comparison_root = run_results[0][1].parent.parent
    output_path = comparison_root / "comparison_all_variants.md"
    try:
        compare_all_variants(run_results, str(output_path))
        rel_out = output_path.relative_to(project_root.parent.parent)
        logger.info(f"N-way comparison complete: {rel_out}")
    except Exception as e:
        logger.error(f"N-way comparison failed: {e}")
```

**Add import:** `from harness.comparator import compare_all_variants`

## Report Structure

### Header
- Run metadata, variant list with paths
- Executive summary: overall winner, win distribution

### Section 1: Side-by-Side Comparison
For each query:
- Table with all variants as columns
- Core metrics: p50, p95, avg_duration, QPS
- "Best" column showing winner(s)
- Delta columns showing % from best for each variant
- Handle missing queries with "N/A"

### Section 2: Rankings
Three ranking tables:
- By average p50 latency
- By average p95 latency
- By average QPS
Each shows rank, variant, average value, delta from best

### Section 3: Interpretation Guide
Explain metrics, direction (lower/higher better), symbols

## Implementation Details

### Data Structures
```python
# Load all variants into dict
all_data: dict[str, pd.DataFrame] = {
    variant_name: _load_results(path)
    for variant_name, path in variant_results
}

# For each query, collect metrics from all variants
query_comparison = {
    'query_name': str,
    'variants_with_query': list[str],
    'metrics': {
        'p50_ms': {variant: value, ...},
        'p95_ms': {variant: value, ...},
        # ...
    },
    'best_variant': {
        'p50_ms': variant_name,
        # ...
    }
}
```

### Best Performer Logic
- **Lower is better:** p50_ms, p95_ms, avg_query_duration_ms, error_rate, avg_memory_usage
- **Higher is better:** qps
- Use `min()` or `max()` accordingly on variant values
- Handle ties: list multiple winners

### Delta Calculation
For each metric, for each variant:
```python
delta_pct = ((variant_value - best_value) / best_value) * 100
# Format: "{delta_pct:+.1f}%"
# Display "-" if variant is best
```

### Missing Query Handling
- Union all queries across variants
- For queries not in a variant: display "N/A"
- Note which variants have the query: "(variant0, variant2 only)"
- Exclude from rankings where not present

## Edge Cases

1. **Only 1 variant:** Raise `ValueError("N-way comparison requires at least 2 variants")`
2. **No common queries:** Show all queries, most cells "N/A", note in summary
3. **Ties in best performer:** List all tied variants in "Best" column
4. **Zero/invalid values:** Display value, skip delta calc (show "N/A")
5. **Missing metrics in JSON:** Log warning, skip that metric, continue

## Testing Validation

**Manual test with existing data:**
```
/home/sam/code/lightspeed/projects/keyselectionlocal/results/three/abstractbullmastiff/
```
Contains variant0, variant1, variant2 results - perfect for validation.

**Verify:**
- All 3 variants appear in report
- Rankings make sense (cross-check against existing pairwise reports)
- Deltas calculated correctly
- Table format is readable and clear
- Only `comparison_all_variants.md` generated (no pairwise files)

## Implementation Steps

1. **Add `compare_all_variants()` to comparator.py** (~300 lines)
   - Main function + helper functions
   - Report generation with all table formatting

2. **Update CLI integration** (~10 lines changed)
   - Replace loop in cli.py lines 418-430
   - Update import statement

3. **Test with real data**
   - Run against keyselectionlocal 3-variant results
   - Validate report format and correctness

4. **Commit**
   - Single commit: "replace pairwise with N-way multi-variant comparison"

---

## Mockup: N-Way Report Example (N=4)

```markdown
# N-Way Benchmark Comparison

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
```
