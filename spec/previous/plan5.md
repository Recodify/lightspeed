# ClickHouse Benchmark Harness – Plan5 (Reviewed & Clarified)

## Review Summary

This document captures the comprehensive review of plan4.md with all critical clarifications resolved.

**Review Score**: 9.5/10 - Ready for implementation

**Status**: All major ambiguities resolved through user clarification

---

## Major Changes from Plan4

### 1. Warmup Architecture - CRITICAL CHANGE

**Plan4 assumption**: Each worker runs warmup queries independently

**Actual requirement**: Single-threaded warmup BEFORE concurrent workers start

**Corrected implementation**:
```python
def run_workload(config, client):
    # Phase 1: Single-threaded warmup (runs BEFORE measurement)
    logger.info(f"Running {config.warmup_queries} warmup queries...")
    for i in range(config.warmup_queries):
        query = select_random_query(query_pool)
        client.execute(query)  # discard results, not recorded

    # Phase 2: Concurrent measurement phase
    logger.info(f"Starting measurement with {config.concurrency} workers...")
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
        # Each worker runs queries for duration_seconds
        futures = [executor.submit(worker_func) for _ in range(config.concurrency)]
        wait(futures, timeout=config.duration_seconds)

    end_time = time.time()
    actual_duration = end_time - start_time

    # Phase 3: Calculate metrics
    qps = total_queries / actual_duration
```

**Impact**: This ensures caches are warmed BEFORE timed measurement begins, producing accurate benchmark results.

### 2. QPS Calculation

**Resolution**: ✅ Use actual measured time from workload execution

**Implementation**:
```python
# In workload_runner.py
start_time = time.time()
# ... run concurrent workers ...
end_time = time.time()
actual_duration = end_time - start_time

# Return to reporter
return ExecutionRecords, actual_duration

# In reporter.py
qps = total_queries / actual_duration
```

**Rationale**: Accounts for actual execution time variations and excludes warmup phase.

### 3. CSV Header Handling

**Resolution**: ✅ Use ClickHouse native `CSVWithNames` format

**Implementation**:
```python
# Data loader should support format variants
if format == "CSV" and skip_rows > 0:
    # Use CSVWithNames which automatically skips header
    actual_format = "CSVWithNames"
else:
    actual_format = format

# HTTP INSERT
client.insert_stream(table, file_handle, actual_format)
```

**Config simplified**:
```yaml
data:
  load:
    - table: "trades"
      file: "trades.csv"
      format: "CSVWithNames"  # handles headers automatically
```

### 4. Workload Query File Resolution

**Resolution**: ✅ `queries[].file` is relative to `workload.path`

**Implementation**:
```python
# For workload.path = "baseline" and queries[].file = "q01_latency.sql"
# Resolution order:
1. VARIANT_ROOT/workloads/baseline/q01_latency.sql
2. PROJECT_ROOT/workloads/baseline/q01_latency.sql (fallback)
3. Error if neither exists
```

### 5. max_rows Feature

**Resolution**: ✅ Defer to Phase 3

**Rationale**: Not critical for core benchmarking. Users can manually create test subsets for Phase 1.

---

## All Resolved Issues

### Issue 1: CSV Row Skipping - RESOLVED ✅
Use ClickHouse native `CSVWithNames` format instead of client-side row skipping.

### Issue 2: max_rows Implementation - RESOLVED ✅
Defer to Phase 3 as enhancement.

### Issue 3: Workload Query Resolution - RESOLVED ✅
Queries are relative to `workload.path` with variant→project fallback.

### Issue 4: Parameter Substitution Security
**For Phase 1**: Document that Python `.format()` is safe since params are internally generated.
**For Phase 2/3**: Consider ClickHouse native parameter substitution for better security.

### Issue 5: Warmup Phase Semantics - RESOLVED ✅
**MAJOR CHANGE**: Warmup runs single-threaded BEFORE concurrent workers start.

### Issue 6: Query Log Mismatch Handling
**Current plan4**: Only handles fewer entries than executions.
**Recommendation**: Also handle duplicates (more entries than executions).

**Implementation guidance needed**:
```python
# In metrics_collector.py
expected_count = len(execution_records)
actual_count = len(query_log_entries)

if actual_count < expected_count:
    logger.warning(f"Query log missing {expected_count - actual_count} entries")
    # Keep records with missing metrics as null

if actual_count > expected_count:
    logger.warning(f"Query log has {actual_count - expected_count} duplicate entries")
    # Use QueryFinish type only
    # If multiple QueryFinish for same query_id, take the latest
```

### Issue 7: QPS Calculation - RESOLVED ✅
Use actual measured time from workload execution (not config value).

### Issue 8: ExecutionRecord Missing Field
**Current plan4 fields**:
- `query_name`, `query_id`, `started_at`, `finished_at`, `duration_ms`, `success`, `error_message`

**Recommendation**: Add `executed_sql` field for debugging

```python
@dataclass
class ExecutionRecord:
    query_id: str
    query_name: str
    executed_sql: str      # NEW: actual SQL after parameter substitution
    started_at: datetime
    finished_at: datetime
    duration_ms: float
    success: bool
    error_message: str | None
```

### Issue 9: Comparator Delta Calculation Edge Cases
**Missing edge cases**:
- Division by zero when baseline value is 0
- Query exists in only one variant

**Recommendation**:
```python
# For delta calculation
if baseline == 0:
    delta = "N/A" if comparison == 0 else "+∞"
else:
    delta = ((comparison - baseline) / baseline) * 100

# For missing queries
if query not in variant_b:
    mark as "missing" in comparison table
```

### Issue 10: Validation Command Scope
**Minimal validation** (Phase 1):
- Config structure validation
- File existence checks
- ClickHouse connectivity test

**Enhanced validation** (Phase 2):
- SQL syntax validation
- Config value sanity checks (e.g., concurrency > 0)
- Workload path consistency

---

## Strengths of Plan4

1. **Clear multi-project architecture** - Projects isolate different benchmarking contexts
2. **Explicit path resolution rules** - No ambiguity about which files are used
3. **Strict validation requirements** - Fail early with clear errors
4. **Phased implementation plan** - Practical breakdown into deliverable phases
5. **"No silent degradation" policy** - Explicit error handling requirement
6. **Production-ready logging** - Comprehensive logging requirements
7. **Exit code discipline** - Suitable for CI/CD automation

---

## Structural Recommendations

### 1. Config Schema Validation

Add Pydantic models for config validation:

```python
from pydantic import BaseModel, Field

class ClickHouseConfig(BaseModel):
    host: str
    port: int = Field(ge=1, le=65535)
    database: str
    connection_pool_size: int = Field(ge=1, le=1000, default=20)
    timeout_seconds: int = Field(ge=1, default=300)

class WorkloadConfig(BaseModel):
    name: str
    path: str
    queries: List[QuerySpec]
    concurrency: int = Field(ge=1)
    duration_seconds: int = Field(ge=1)
    warmup_queries: int = Field(ge=0, default=0)
    # ... etc
```

### 2. Utils Module Scope

**Recommended contents for `utils.py`**:
- Path resolution helpers
- Percentile calculation (using numpy or pandas)
- Duration formatting (ms → human readable)
- CSV escaping/sanitization
- Logging setup function

### 3. Exceptions Module Design

**Recommended custom exceptions for `exceptions.py`**:
```python
class HarnessError(Exception):
    """Base exception for all harness errors"""

class ValidationError(HarnessError):
    """Config or file validation failed"""

class SchemaLoadError(HarnessError):
    """Schema application failed"""

class DataLoadError(HarnessError):
    """Data loading failed"""

class WorkloadAbortedError(HarnessError):
    """Workload exceeded error threshold"""

class MetricsCollectionError(HarnessError):
    """Failed to collect metrics from query_log"""
```

---

## Missing Features (Acceptable for Phase 1)

### 1. Results Metadata
Include metadata in CSV/Markdown output:
- Timestamp of run
- Git commit hash (if in repo)
- Variant name
- ClickHouse version
- Workload config summary

**Useful for**: Traceability and reproducibility

### 2. Graceful Shutdown
Handle interruption (Ctrl+C) gracefully:
- Signal handling
- Complete current queries before shutdown
- Optionally collect partial metrics

**Recommended**: Add in Phase 2

### 3. Progress Reporting
During workload execution:
- Progress bar with `--progress` flag
- Periodic logging (every 10s) with `--verbose`
- Real-time query count

**Recommended**: Add in Phase 2

### 4. Concurrent Variant Benchmarks
Run multiple variants in one command:
```bash
python -m harness.cli full-run --config config.yml --variants variant_a,variant_b
```

**Recommended**: Phase 3 enhancement

---

## Implementation Guidance

### Phase 1: Core End-to-End Harness

**Deliver**:
- Repository layout as specified in plan4
- Config loading with Pydantic validation
- ClickHouse client with connection pooling (httpx)
- Schema loader with project + variant resolution
- Data loader with HTTP streaming
- **Workload runner with**:
  - **Single-threaded warmup BEFORE measurement** (CRITICAL)
  - Concurrent workers using ThreadPoolExecutor
  - `query_id` tracking for each execution
  - ExecutionRecord with `executed_sql` field
- Metrics collector using `system.query_log` and `query_id`
- Reporter that writes CSV with:
  - count, errors, error_rate, qps, p50, p95, p99
  - **QPS calculated from actual measured duration**
- CLI with: `validate`, `init-db`, `load-data`, `run-workload`, `full-run`

**Acceptance criteria**:
- Running `full-run` with example config yields valid CSV
- Failures produce clear messages and non-zero exit codes
- Warmup runs before concurrent measurement
- QPS reflects actual execution time

### Phase 2: Usability and Interpretation

**Add**:
- Markdown summary output in reporter
- `compare` command and comparator.py
- Parameterization via parameter_generator.py
- Weighted query selection in workload runner
- `--dry-run` flag
- Enhanced logging with progress reporting
- Graceful shutdown handling

**Acceptance**:
- CSV and Markdown both produced
- Two variants can be compared with single command
- Query parameters work correctly

### Phase 3: Refinements and Extensions

**Possible additions**:
- `max_rows` for data loading
- Database naming isolation for runs
- Improved query log mismatch warnings
- Richer metrics in reports
- Results metadata
- Concurrent variant benchmarking

---

## Critical Implementation Notes

1. **Query ID tracking**: Always set `query_id` when executing queries, store in `ExecutionRecord`, use for joining with `system.query_log`

2. **Warmup BEFORE measurement**:
   - Run warmup queries single-threaded
   - Start timing AFTER warmup completes
   - Only record metrics from measurement phase

3. **Async query_log handling**:
   - Wait `query_log_wait_seconds` after workload completes (default 10s)
   - Or poll until expected count reached (max 60s timeout)
   - Warn if counts don't match

4. **Connection pooling**:
   - Use `httpx.Client()` with `limits=httpx.Limits(max_connections=20)`
   - Reuse client across all workers

5. **Error handling**:
   - Schema/data errors: Fail fast by default
   - Workload errors: Log and continue, track in ExecutionRecord
   - Abort if `max_errors` threshold exceeded

6. **Logging**:
   - Use Python `logging` module
   - `--verbose` flag for DEBUG level
   - Log: project/variant selection, resolved paths, connection status, schema execution, data load progress, workload timing, query execution counts

7. **QPS calculation**:
   - Always use actual measured time from workload
   - `qps = total_queries / actual_duration`
   - Do NOT use config `duration_seconds`

---

## Path Resolution Rules (from Plan4)

### Schemas
Schema files are applied in two layers:

1. **Project-wide schemas first:**
   - `PROJECT_ROOT/schemas/*.sql` sorted by filename
   - Optional, may be empty

2. **Variant-specific schemas next:**
   - `VARIANT_ROOT/schemas/*.sql` sorted by filename
   - Optional, may be empty

Execution order: always project level, then variant level.

### Data
For each configured `data.load` entry with `file: "<name>"`:

1. First try variant-specific:
   - `VARIANT_ROOT/data/<file>`

2. If not found, fallback to project-wide:
   - `PROJECT_ROOT/data/<file>`

If neither exists, abort with validation error.

### Workloads
For each configured query file in `workload.queries`:

1. Try `VARIANT_ROOT/workloads/<path>/<file>`
2. If not found, try `PROJECT_ROOT/workloads/<path>/<file>`
3. If not found, validation must fail

All queries must be resolvable before running workload.

### Results
`metrics.output_csv` and `metrics.output_md` are relative to `PROJECT_ROOT` unless absolute paths.

---

## Repository Structure (from Plan4)

```
ch-harness/
  pyproject.toml
  README.md

  harness/
    __init__.py
    config.py
    clickhouse_client.py
    schema_loader.py
    data_loader.py
    workload_runner.py
    metrics_collector.py
    reporter.py
    comparator.py
    parameter_generator.py
    utils.py
    exceptions.py
    cli.py

  projects/
    default/
      configs/
        example_basic.yml
        example_weighted.yml
        example_params.yml

      # project wide shared assets
      schemas/
      data/
      workloads/

      variants/
        default/
          schemas/
            001_create_tables.sql
            002_indexes.sql
          data/
            trades.csv

        variant_a/
          schemas/
            001_create_tables.sql
          data/
            trades.csv
            prices.parquet

      results/
        .gitkeep

    project_A/
      configs/
      schemas/
      data/
      workloads/
      variants/
      results/
```

---

## Config Format (Enhanced from Plan4)

```yaml
project: "default"
variant: "variant_a"

clickhouse:
  host: "localhost"
  port: 8123
  user: "default"
  password: ""
  database: "bench"
  connection_pool_size: 20
  timeout_seconds: 300

schema:
  fail_on_error: true
  fresh: true

data:
  load_method: "http"  # Only HTTP for Phase 1
  truncate_before_load: true
  load:
    - table: "trades"
      file: "trades.csv"
      format: "CSVWithNames"  # Use ClickHouse native header handling
    - table: "prices"
      file: "prices.parquet"
      format: "Parquet"

workload:
  name: "baseline"
  path: "baseline"  # queries are relative to this path
  queries:
    - file: "q01_latency.sql"  # resolves to workloads/baseline/q01_latency.sql
      weight: 10
    - file: "q02_throughput.sql"
      weight: 2

  concurrency: 8
  duration_seconds: 120
  ramp_up_seconds: 10
  warmup_queries: 20  # runs BEFORE concurrent measurement
  think_time_ms: 50
  max_errors: 100
  query_timeout_seconds: 60

  parameters:
    user_id:
      type: random_int
      min: 1
      max: 1000
    date:
      type: random_choice
      values: ["2024-01-01", "2024-06-01", "2024-12-01"]

metrics:
  use_query_log: true
  query_log_wait_seconds: 10
  output_csv: "results/baseline_variant_a.csv"
  output_md:  "results/baseline_variant_a.md"
```

---

## CLI Commands (from Plan4)

```bash
# Validate config without execution
python -m harness.cli validate --config projects/default/configs/example.yml

# Run with dry-run
python -m harness.cli full-run --config projects/default/configs/example.yml --dry-run

# Full run with fresh database
python -m harness.cli full-run --config projects/default/configs/example.yml --verbose

# Individual commands
python -m harness.cli init-db --config projects/default/configs/example.yml
python -m harness.cli load-data --config projects/default/configs/example.yml
python -m harness.cli run-workload --config projects/default/configs/example.yml

# Compare results
python -m harness.cli compare \
  projects/default/results/baseline_variant_a.csv \
  projects/default/results/baseline_variant_b.csv \
  --output projects/default/results/baseline_compare.md
```

**Global flags**:
- `--config <path>`: Path to YAML config
- `--verbose`: Enable DEBUG logging
- `--dry-run`: Validate without executing (for `full-run`)

---

## Dependencies (from Plan4)

```toml
[project]
name = "ch-harness"
version = "0.1.0"
dependencies = [
    "httpx>=0.27.0",      # ClickHouse HTTP client with connection pooling
    "pyyaml>=6.0",        # Config parsing
    "pydantic>=2.0.0",    # Config validation
    "pandas>=2.0.0",      # Percentile calculations
    "pyarrow>=14.0.0",    # Parquet support
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "black>=24.0.0",
    "ruff>=0.1.0",
]
```

---

## Summary of Key Decisions

| Topic | Decision | Rationale |
|-------|----------|-----------|
| Warmup timing | Single-threaded BEFORE workers | Ensures accurate cache warming |
| QPS calculation | Actual measured time | More accurate than config value |
| CSV headers | ClickHouse CSVWithNames | Native, efficient, no client-side parsing |
| Query resolution | Relative to workload.path | Clean separation, follows directory structure |
| max_rows | Defer to Phase 3 | Not critical for v1 |
| Parameter substitution | Python .format() for Phase 1 | Safe for internal params, document limitation |
| Validation scope | Minimal for Phase 1 | File existence + connectivity |
| Query log mismatches | Handle both directions | Robust error reporting |

---

## Final Assessment

**Status**: ✅ **READY FOR IMPLEMENTATION**

**Overall Score**: 9.5/10

**All critical ambiguities resolved**:
- Warmup architecture clarified (major change)
- QPS calculation defined precisely
- CSV handling simplified
- Query file resolution explicit
- Feature scope for Phase 1 finalized

**Remaining minor items** (can be addressed during implementation):
- Query log duplicate handling details
- ExecutionRecord schema update
- Comparator edge case handling
- Utils/exceptions module contents

**Recommendation**: Begin Phase 1 implementation following this plan. The specification is production-ready with clear requirements and well-defined error handling.
