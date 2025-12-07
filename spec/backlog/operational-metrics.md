# Operational Metrics Capture

## Rationale

Performance benchmarking that measures query latency without capturing operational resource consumption is fundamentally incomplete. A schema variant may deliver acceptable query response times during short-duration tests while accumulating merge debt, memory pressure, or disk fragmentation that renders it operationally unsustainable over days or weeks of production usage.

This phase captures the operational metrics necessary to evaluate schema sustainability under continuous load.

## Required Metrics

### 1. Disk Utilization

**Captured Metrics:**

- Total table size at rest (bytes)
- Part count per table
- Compression ratio (uncompressed / compressed)
- Part size distribution (min, max, p50, p95)

**Diagnostic Value:**

- Dictionary encoding effectiveness
- High-cardinality column issues
- Wide row inflation of granule sizes
- ORDER BY clustering efficiency

**Data Sources:**

- `system.parts`: `bytes_on_disk`, `rows`, `data_uncompressed_bytes`
- `system.tables`: `total_bytes`, `total_rows`

### 2. Merge Pressure

**Captured Metrics:**

- Merges queued (current backlog)
- Merges active (concurrent execution count)
- Merges failed (error count during run)
- Average merge duration (milliseconds)
- Maximum merge backlog age (seconds)
- Merge throughput (merges per hour)

**Diagnostic Value:**

Merge pressure is the primary indicator of schema sustainability. Excessive merge activity reveals:

- Inappropriate partitioning strategy
- Suboptimal ORDER BY key selection
- Ingestion batch sizing issues
- Unbounded part proliferation

**Data Sources:**

- `system.merges`: `elapsed`, `total_rows_count`, `progress`
- `system.part_log`: `event_type='MergeParts'`, `duration_ms`

### 3. Memory Consumption

**Captured Metrics:**

- Query pipeline memory usage (peak and average)
- Dictionary memory allocation
- Uncompressed block cache size
- Per-query memory spikes

**Diagnostic Value:**

Memory exhaustion kills ClickHouse nodes long before CPU saturation. Tracking memory consumption patterns identifies:

- Unbounded aggregation states
- Dictionary sizing issues
- Cache thrashing
- Query memory leaks

**Data Sources:**

- `system.query_log`: `memory_usage`, `peak_memory_usage`
- `system.dictionaries`: `bytes_allocated`
- `system.asynchronous_metrics`: `UncompressedCacheBytes`

### 4. CPU Utilization

**Captured Metrics:**

- Average CPU utilization over workload duration
- CPU utilization during merge operations
- Per-core load distribution (detect imbalance)

**Implementation:**

Sample `/proc/stat` at 1-second intervals during workload execution. Aggregate CPU time deltas after run completion.

**Diagnostic Value:**

ClickHouse consumes CPU primarily during merge operations, not SELECT queries. Sustained high CPU during merges indicates:

- Compression overhead
- Complex merge logic (e.g., ReplacingMergeTree deduplication)
- Excessive merge concurrency

**Note:** Absolute CPU percentages are less valuable than relative comparison between schema variants under identical workload conditions.

### 5. Disk I/O

**Captured Metrics:**

- Read bandwidth (MB/s)
- Write bandwidth (MB/s)
- I/O wait time (percentage)

**Implementation:**

Sample `/proc/diskstats` or `iostat -dx` at 1-second intervals. Calculate bandwidth deltas from sector counts.

**Diagnostic Value:**

Merge operations generate write amplification. If merges spike I/O wait time, query latency will degrade during merge windows. High read bandwidth during queries may indicate:

- Poor data locality (ORDER BY ineffective)
- Missing indexes forcing full scans
- Insufficient OS page cache

## Integration Point

Operational metrics capture occurs immediately after workload execution completes, before final reporting.

**Execution Sequence:**

1. Apply schema
2. Load data
3. Warmup phase
4. Workload execution (timed measurement)
5. **Operational metrics capture** ← inserted here
6. Report generation

**Rationale:** Metrics must be collected while the database state reflects workload impact (active parts, merge queue, memory allocation) before any cleanup or database reset.

## Output Format

### File: `resource_profile.csv`

Location: `projects/<project>/results/resource_profile_<variant>.csv`

**Structure:**

```csv
metric,value,unit
disk_used_bytes,22548234240,bytes
parts_count,6321,count
compression_ratio,4.2,ratio
avg_part_size_bytes,3567890,bytes
avg_merge_duration_ms,8512,milliseconds
max_merge_age_s,127,seconds
merges_per_hour,342,rate
peak_memory_usage_bytes,18253611008,bytes
avg_query_memory_bytes,2456780,bytes
cpu_utilization_pct,73,percent
io_read_mb_s,145.3,megabytes_per_second
io_write_mb_s,312.7,megabytes_per_second
io_wait_pct,12.4,percent
```

**Metadata Header:**

Prepend metadata as CSV comments:

```csv
# project: default
# variant: variant_a
# workload_start_epoch_ms: 1234567890123
# workload_duration_secs: 120.456
# clickhouse_version: 24.3.1.2672
metric,value,unit
...
```

### Comparison Output

**Command:**

```bash
python -m harness.cli compare-resources \
  projects/default/results/resource_profile_baseline.csv \
  projects/default/results/resource_profile_variant_a.csv \
  --output projects/default/results/resource_comparison.md
```

**File: `resource_comparison.csv`**

```csv
metric,baseline,variant_a,delta_pct,unit
disk_used_bytes,22548234240,14567890123,-35.4,bytes
parts_count,6321,1780,-71.8,count
avg_merge_duration_ms,8512,1252,-85.3,milliseconds
cpu_utilization_pct,73,41,-43.8,percent
peak_memory_usage_bytes,18253611008,21567890123,+18.2,bytes
```

**Markdown Output: `resource_comparison.md`**

```markdown
# Resource Profile Comparison

## Baseline vs. variant_a

| Metric | Baseline | Variant A | Δ % | Unit |
|--------|----------|-----------|-----|------|
| Disk Usage | 21.0 GB | 13.6 GB | **-35.4%** | bytes |
| Parts Count | 6,321 | 1,780 | **-71.8%** | count |
| Avg Merge Duration | 8,512 ms | 1,252 ms | **-85.3%** | milliseconds |
| CPU Utilization | 73% | 41% | **-43.8%** | percent |
| Peak Memory | 17.0 GB | 20.1 GB | **+18.2%** | bytes |

## Summary

Variant A reduces disk footprint by 35% and part count by 72%, resulting in 85% faster merges and 44% lower CPU consumption. Memory usage increased 18%, indicating higher compression overhead or larger dictionaries. Overall: **operationally superior** despite modest memory increase.
```

## Implementation: `metrics_collector.py` Extension

**New Function:**

```python
def collect_operational_metrics(client: ClickHouseClient, config: Config) -> dict:
    """
    Capture operational resource metrics after workload completion.

    Returns dict with keys:
    - disk_used_bytes
    - parts_count
    - compression_ratio
    - avg_merge_duration_ms
    - max_merge_age_s
    - cpu_utilization_pct
    - io_read_mb_s
    - etc.
    """
```

**Data Collection:**

1. Query `system.parts` for disk and compression metrics
2. Query `system.part_log` for merge statistics (filter by workload time window)
3. Read `/proc/stat` snapshots collected during workload
4. Read `/proc/diskstats` snapshots collected during workload
5. Query `system.asynchronous_metrics` for memory and cache state

**Sampling Architecture:**

Background thread during workload execution:

```python
def system_metrics_sampler(interval_seconds: float, stop_event: threading.Event):
    """
    Sample /proc/stat and /proc/diskstats at regular intervals.
    Store snapshots for post-workload aggregation.
    """
    samples = []
    while not stop_event.is_set():
        samples.append({
            'timestamp': time.time(),
            'cpu': read_proc_stat(),
            'disk': read_proc_diskstats()
        })
        time.sleep(interval_seconds)
    return samples
```

Start sampler before workload, stop after workload completes, aggregate deltas in `collect_operational_metrics()`.

## Critical Design Principle

**Absolute values are irrelevant. Relative comparison is everything.**

A standalone metric like "node CPU at 73%" provides no actionable insight.

The value emerges from comparison:

> Variant X produced 2.1× merge volume while maintaining identical QPS, increasing memory consumption by 48% and CPU utilization by 31% compared to baseline.

This transforms performance evaluation from anecdotal observation to budget justification.

## Why This Matters

Query latency benchmarks measure immediate response characteristics. Operational metrics measure **sustained viability**.

A schema can deliver sub-20ms p95 latency during a 2-minute benchmark while:

- Accumulating 10,000+ small parts requiring multi-hour merge operations
- Leaking 200MB of memory per million rows ingested
- Generating 4× write amplification that saturates disk I/O under production load

These failure modes are invisible to pure latency benchmarking. They manifest hours or days after deployment, often catastrophically (OOM crashes, query timeouts during merge storms, disk exhaustion).

**Operational metrics make sustainability measurable.**

Without this phase: benchmarking illusions.

With this phase: benchmarking reality.