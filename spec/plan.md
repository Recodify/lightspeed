# ClickHouse Benchmark Harness – Specification

## Overview

A Python-based benchmarking harness for ClickHouse that supports:

- Multiple independent projects under a single tool
- Schema variants with shared and per-variant assets
- Repeatable, trustworthy performance measurements
- Comparison of results across schema variants

## Repository Structure

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
    <project_name>/
      configs/
        example_basic.yml
        example_weighted.yml
        example_params.yml

      schemas/           # Optional: project-wide schemas
      data/              # Optional: project-wide data
      workloads/         # Project-wide workloads
        baseline/
          q01_latency.sql
          q02_throughput.sql
        heavy/
          q01_full_scan.sql

      variants/
        <variant_name>/
          schemas/
            001_create_tables.sql
            002_indexes.sql
          data/
            trades.csv
            prices.parquet
          workloads/    # Optional: variant-specific overrides
            baseline/
              q01_latency.sql

      results/
        .gitkeep
```

## Configuration Format

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
  timeout_seconds: 300  # Default timeout for schema, data, and metrics operations

schema:
  fail_on_error: true
  fresh: true

data:
  load_method: "http"
  truncate_before_load: true
  load:
    - table: "trades"
      file: "trades.csv"
      format: "CSVWithNames"
    - table: "prices"
      file: "prices.parquet"
      format: "Parquet"

workload:
  name: "baseline"
  path: "baseline"

  # Optional: If omitted, all *.sql files in workloads/<path>/ are auto-discovered with weight=1
  queries:
    - file: "q01_latency.sql"
      weight: 10
    - file: "q02_throughput.sql"
      weight: 1

  concurrency: 8
  duration_seconds: 120
  ramp_up_seconds: 10
  warmup_queries: 20
  think_time_ms: 50
  max_errors: 100
  query_timeout_seconds: 60  # Overrides clickhouse.timeout_seconds for workload queries only

  # Optional: Query parameterization
  parameters:
    user_id:
      type: random_int
      min: 1
      max: 1000
    date:
      type: random_choice
      values: ["2024-01-01", "2024-06-01", "2024-12-31"]

metrics:
  use_query_log: true
  query_log_wait_seconds: 10
  output_csv: "results/baseline_variant_a.csv"
  output_md:  "results/baseline_variant_a.md"
```

## Path Resolution Rules

Let:
- `PROJECT_ROOT = projects/<project>`
- `VARIANT_ROOT = projects/<project>/variants/<variant>`

### Schemas

Schema files are applied in two layers:

1. **Project-wide schemas** (optional):
   - `PROJECT_ROOT/schemas/*.sql` sorted by filename

2. **Variant-specific schemas** (optional):
   - `VARIANT_ROOT/schemas/*.sql` sorted by filename

Execution order: always project-wide first, then variant-specific.

Each `.sql` file is executed as a single statement via HTTP (no splitting by semicolons).

### Data Files

For each `data.load` entry with `file: "<name>"`:

1. Try variant-specific: `VARIANT_ROOT/data/<file>`
2. If not found, try project-wide: `PROJECT_ROOT/data/<file>`
3. If neither exists, validation fails

### Workload Queries

#### Explicit Mode

When `workload.queries` is specified:

```yaml
workload:
  path: "baseline"
  queries:
    - file: "q01_latency.sql"
      weight: 10
```

For each query, resolve `file` relative to `workload.path`:

1. Try variant-specific: `VARIANT_ROOT/workloads/<path>/<file>`
2. If not found, try project-wide: `PROJECT_ROOT/workloads/<path>/<file>`
3. If neither exists, validation fails

#### Auto-Discovery Mode

When `workload.queries` is absent or empty, auto-discover all `.sql` files:

1. Scan `VARIANT_ROOT/workloads/<path>/*.sql`
2. Scan `PROJECT_ROOT/workloads/<path>/*.sql`
3. If same filename exists in both, variant version takes precedence
4. Treat all discovered queries with `weight: 1`

### Results

`metrics.output_csv` and `metrics.output_md` are relative to `PROJECT_ROOT` unless absolute paths.

## Module Specifications

### config.py

**Responsibilities:**

- Load YAML config into typed structures (use Pydantic for validation)
- Compute `PROJECT_ROOT` and `VARIANT_ROOT` from `project` and `variant`
- Validate:
  - Project and variant directories exist
  - ClickHouse connectivity (`SELECT 1`)
  - Schema, data, and workload files exist per resolution rules
- Provide clear error messages and non-zero exit codes on validation failure

### clickhouse_client.py

**Implementation:**

Use `httpx.Client` with connection pooling.

**Functions:**

```python
execute(sql: str, params: dict | None = None, settings: dict | None = None) -> list[dict]
execute_no_result(sql: str, params: dict | None = None, settings: dict | None = None) -> None
insert_stream(table: str, file_handle, fmt: str, settings: dict | None = None) -> None
```

**Features:**

- Support passing ClickHouse settings including `query_id`
- Configure connection pool size from config
- Handle query timeouts via `httpx.Timeout`

**Client initialization:**

The harness uses **two separate httpx clients** to handle different timeout requirements:

1. **Default client** for schema, data, and metrics operations:
   - Uses `clickhouse.timeout_seconds` (typically 300s for long-running operations)
   - Shared across schema_loader, data_loader, metrics_collector

2. **Workload client** for benchmark query execution:
   - Uses `workload.query_timeout_seconds` (typically 60s for fast-fail on stuck queries)
   - Created specifically by workload_runner

**Default client configuration:**

```python
import httpx

default_timeout = httpx.Timeout(
    connect=10.0,
    read=config.clickhouse.timeout_seconds,  # e.g., 300s
    write=10.0,
    pool=10.0
)

default_client = httpx.Client(
    timeout=default_timeout,
    limits=httpx.Limits(max_connections=config.clickhouse.connection_pool_size)
)
```

**Workload client configuration** (in workload_runner.py):

```python
workload_timeout = httpx.Timeout(
    connect=10.0,
    read=config.workload.query_timeout_seconds,  # e.g., 60s
    write=10.0,
    pool=10.0
)

workload_client = httpx.Client(
    timeout=workload_timeout,
    limits=httpx.Limits(max_connections=config.clickhouse.connection_pool_size)
)
```

### schema_loader.py

**Behavior:**

If `schema.fresh` is true:
1. `DROP DATABASE IF EXISTS <database>`
2. `CREATE DATABASE <database>`

Then:
1. Apply all `PROJECT_ROOT/schemas/*.sql` sorted lexically
2. Apply all `VARIANT_ROOT/schemas/*.sql` sorted lexically

**Execution:**

- Read each file entirely and send as single statement over HTTP
- No splitting by semicolons

**Error handling:**

- If statement fails and `fail_on_error` is true:
  - Log failing file and error
  - Abort with non-zero exit code
- If `fail_on_error` is false:
  - Log error but continue
  - Summarize failed files at end

### data_loader.py

**Implementation:**

Load data via HTTP INSERT only.

For each `data.load` entry:

1. Resolve file path using variant→project fallback
2. If `truncate_before_load` is true: `TRUNCATE TABLE <table>`
3. Open file
4. For CSV with headers, use `CSVWithNames` format (ClickHouse handles header skipping natively)
    - For CSV, the harness assumes files have headers and uses CSVWithNames. Header skipping is handled by ClickHouse and no client-side row skipping is required.
5. Stream file via:
   ```sql
   INSERT INTO <table> FORMAT <format>
   ```
   with file as HTTP request body
6. Log per table:
   - Table name
   - Approximate bytes sent
   - Duration
   - Success or failure

Any failure aborts the process with clear error.

### parameter_generator.py

**Supported parameter types:**

```yaml
parameters:
  user_id:
    type: random_int
    min: 1
    max: 1000
  date:
    type: random_choice
    values: ["2024-01-01", "2024-06-01", "2024-12-31"]
```

**Function:**

```python
def generate_params(param_config: dict) -> dict:
    """
    Returns dict like {"user_id": 123, "date": "2024-06-01"}
    """
```

**Query substitution:**

Use Python `.format()`:

```sql
SELECT * FROM trades WHERE user_id = {user_id} AND trade_date = toDate('{date}')
```

```python
executed_sql = query_template.format(**params)
```

### workload_runner.py

**Architecture:**

Three phases:
1. Load queries (explicit or auto-discovered)
2. Warmup (single-threaded, not measured)
3. Measurement (concurrent workers, timed)

**Warmup Phase:**

```python
# Run BEFORE starting measurement timer
for i in range(config.warmup_queries):
    query = select_random_query(query_pool)
    params = generate_params(config.parameters)
    sql = query_template.format(**params)
    client.execute(sql)  # discard results
```

**Measurement Phase:**

```python
workload_start_epoch_ms = time.time() * 1000

# Run concurrent workers
with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
    futures = [executor.submit(worker_func) for _ in range(config.concurrency)]
    # ... collect results

workload_end_epoch_ms = time.time() * 1000
workload_elapsed_secs = (workload_end_epoch_ms - workload_start_epoch_ms) / 1000.0
```

**Worker Function:**

Each worker:

1. Selects query according to weight (weighted random selection)
2. Generates parameters
3. Creates unique `query_id = f"{query_name}_{uuid.uuid4()}"`
4. Records start time
5. Executes via `client.execute(sql, settings={'query_id': query_id})`
6. Records end time and duration
7. Handles timeouts and errors
8. Sleeps for `think_time_ms` between queries
9. Continues until `duration_seconds` elapsed

**Query Timeout Handling:**

```python
try:
    result = client.execute(sql, settings={'query_id': query_id})
    success = True
    error_message = None
except httpx.ReadTimeout:
    success = False
    error_message = f"Query timeout after {config.query_timeout_seconds}s"
except Exception as e:
    success = False
    error_message = str(e)
```

**ExecutionRecord:**

```python
@dataclass
class ExecutionRecord:
    query_id: str              # For joining with query_log
    query_name: str            # Filename
    executed_sql: str          # Actual SQL after parameter substitution
    started_at: datetime
    finished_at: datetime
    duration_ms: float
    success: bool
    error_message: str | None
```

**Abort Policy:**

Maintain shared error counter. If total failures exceed `max_errors`, abort all workers.

**Return Value:**

```python
{
    'records': List[ExecutionRecord],
    'workload_start_epoch_ms': float,
    'workload_end_epoch_ms': float,
    'workload_elapsed_secs': float
}
```

### metrics_collector.py

**Tasks:**

1. Sleep `metrics.query_log_wait_seconds` after workload completes
2. Query `system.query_log`:
   - Filter by `type = 'QueryFinish'`
   - Filter by `query_id IN (...)` for all recorded query_ids
3. Extract per row:
   - `query_id`
   - `query_duration_ms`
   - `read_rows`
   - `read_bytes`
   - `result_rows`
   - `result_bytes`
   - `memory_usage`
4. Return mapping: `query_id -> metrics dict`

**Mismatch Handling:**

- If fewer query_ids found than executions:
  - Log warning with expected vs actual counts
  - Keep records with missing metrics (mark query_log fields as null)
- If more query_ids found than executions:
  - Log warning about duplicates
  - Use `QueryFinish` entries only
  - If multiple `QueryFinish` for same query_id, take latest

### reporter.py

**Input:**

- List of `ExecutionRecord`
- Query log metrics mapping
- Workload timing metadata

**Per-query Statistics:**

- Count of executions
- Error count
- Error rate: `errors / count`
- QPS: `count / workload_elapsed_secs`
- Latency percentiles: p50, p95, p99 (from `ExecutionRecord.duration_ms`)
- Average `read_rows`, `read_bytes`, `memory_usage` from query_log

**CSV Output:**

```csv
query_name,count,errors,error_rate,qps,p50_ms,p95_ms,p99_ms,avg_read_rows,avg_read_bytes,avg_memory_usage
```

Prepend metadata as comments:

```csv
# workload_start_epoch_ms: 1234567890123
# workload_end_epoch_ms: 1234567890243
# workload_elapsed_secs: 120.123
# project: default
# variant: variant_a
query_name,count,...
```

**Markdown Output:**

```markdown
# Benchmark Results: baseline (variant_a)

## Run Metadata
- **Workload Duration**: 120.123 seconds
- **Start Time**: 2024-01-15 14:30:00.123 UTC
- **Project**: default
- **Variant**: variant_a
- **Concurrency**: 8

## Query Performance

| Query | Count | QPS | p50 (ms) | p95 (ms) | p99 (ms) | Errors | Avg rows read |
|-------|-------|-----|----------|----------|----------|--------|---------------|
| q01   | 1000  | 8.3 | 12       | 25       | 40       | 0      | 1.2M          |
```

**Critical Requirement:**

QPS must be calculated as:

```python
qps = count_successful_queries / workload_elapsed_secs
```

Where `workload_elapsed_secs` is actual measured time from workload execution, **never** the configured `duration_seconds`.

### comparator.py

**Command:**

```bash
python -m harness.cli compare \
  projects/default/results/baseline_variant_a.csv \
  projects/default/results/baseline_variant_b.csv \
  --output projects/default/results/comparison.md
```

**Tasks:**

1. Load both CSV files
2. Join on `query_name`
3. Compute per query:
   - p50 delta percentage
   - p95 delta percentage
   - QPS delta percentage

**Output (Markdown):**

```markdown
| Query | A p50 (ms) | B p50 (ms) | Δ p50 (%) | A QPS | B QPS | Δ QPS (%) |
|-------|------------|------------|-----------|-------|-------|-----------|
| q01   | 12         | 8          | -33.3     | 80    | 120   | +50.0     |
```

**Edge Cases:**

- If baseline value is 0:
  ```python
  delta = "N/A" if comparison == 0 else "+∞"
  ```
- If query exists in only one variant, mark as "missing"

### cli.py

**Commands:**

- `validate`: Load config, check connectivity, verify files exist
- `init-db`: Run schema loader
- `load-data`: Run data loader
- `run-workload`: Run workload, collect metrics, generate reports
- `full-run`: Execute validate → init-db (if fresh) → load-data → run-workload
- `compare`: Compare two result CSVs

**Global Flags:**

- `--config <path>`: Path to YAML config
- `--verbose`: Enable DEBUG logging
- `--dry-run`: Validate without executing (for `full-run`)

**Exit Codes:**

All commands return non-zero exit codes on failure for CI/CD compatibility.

## Configuration Details

### Timeout Configuration

The harness uses two distinct timeout settings:

**1. `clickhouse.timeout_seconds` (default: 300s)**

**Purpose:** Default timeout for schema loading, data loading, and metrics collection.

**Usage:**
- Schema DDL execution (CREATE TABLE, CREATE INDEX, etc.)
- Data ingestion via HTTP INSERT
- Querying `system.query_log` for metrics

**Rationale:** These operations can be long-running (large data loads, complex schema changes) and should not be aggressively timed out.

**2. `workload.query_timeout_seconds` (default: 60s)**

**Purpose:** Enforce hard per-query timeout during benchmark workload execution.

**Behavior:**
- If benchmark query exceeds this threshold, client aborts the request
- Execution is marked as failed in `ExecutionRecord`
- Worker continues to next query (does not block)

**Protects Against:**
- Lock contention stalling queries
- Memory pressure causing slowdowns
- Merge operations blocking reads
- Unbounded execution collapsing throughput

**Example:**

Without timeout: Worker thread stuck on 120s query → throughput collapses
With timeout: Query aborted at 60s → marked failed → worker continues

**Why separate timeouts?**

Schema/data operations need generous timeouts (300s+), while benchmark queries should fail fast (60s) to prevent worker stalls and maintain realistic throughput measurements.

### think_time_ms

**Purpose:** Model real-world pacing between queries.

**Formula:** `QPS = concurrency / (average_query_RTT + think_time)`

**Simulates:**

- User think time
- Service queueing time
- Application-level backoffs

**Examples:**

Web workload simulation:

```yaml
concurrency: 50
think_time_ms: 500  # User reads page, thinks, clicks
# Result: ~100 ops/sec sustained
```

Microservice workload:

```yaml
concurrency: 20
think_time_ms: 30  # Service waits on downstream
# Result: Traffic-realistic throttling
```

**Implementation:**

```python
def worker_func():
    while should_continue():
        execute_query(...)
        if config.think_time_ms > 0:
            time.sleep(config.think_time_ms / 1000.0)
```

### QPS Calculation

**Mandatory Approach:**

QPS must always be calculated using actual measured elapsed time, never the configured `duration_seconds`.

**Rationale:**

Real workloads have timing variations:
- Worker thread scheduling jitter
- Thread shutdown delays
- Python GC pauses
- Network latency variation

Even if configured for 120s, actual runtime varies: 119.3s, 121.8s, 118.9s

**Impact of Incorrect Calculation:**

Example showing wrong schema appearing faster:

```
Variant A: 115s actual, 19,500 queries
  Wrong: 19,500 / 120 = 162.5 QPS
  Correct: 19,500 / 115 = 169.6 QPS

Variant B: 122s actual, 20,200 queries
  Wrong: 20,200 / 120 = 168.3 QPS (appears 3.6% faster)
  Correct: 20,200 / 122 = 165.6 QPS

Using config duration: B appears faster
Using actual time: A is actually faster

Wrong calculation reverses the conclusion.
```

**Implementation:**

```python
# Measure actual execution time
start = time.time()
# ... run workload
end = time.time()
elapsed = end - start

# Calculate QPS
qps = successful_queries / elapsed
```

## Logging

Use Python `logging` module:

- Default level: INFO
- With `--verbose`: DEBUG

**Required Log Entries:**

- Selected project and variant
- Resolved paths for schema, data, workloads
- ClickHouse connection success/failure
- Schema file execution and outcomes
- Per-table data load summary
- Workload start/end times
- Query execution counts (successful/failed)
- Query log mismatches
- Generated output file paths

## Error Handling

**Validation Phase:**

- Failures stop execution before any changes
- Clear error messages
- Non-zero exit codes

**Schema/Data Loading:**

- Failures abort the phase with clear reason
- Non-zero exit code

**Workload Execution:**

- Errors counted and surfaced
- If above `max_errors` threshold, abort and mark run as aborted
- Individual query failures recorded but don't stop workload

**Metrics Collection:**

- Issues must be reported, not silently ignored
- Mismatches logged with warnings

**No silent degradation is allowed.**

## Dependencies

```toml
[project]
name = "ch-harness"
version = "0.1.0"
dependencies = [
    "httpx>=0.27.0",      # HTTP client with connection pooling and timeout support
    "pyyaml>=6.0",        # Config parsing
    "pydantic>=2.0.0",    # Config validation
    "pandas>=2.0.0",      # Percentile calculations for reporter
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "black>=24.0.0",
    "ruff>=0.1.0",
]
```

**Note:** `pyarrow` is not required for Phase 1. The harness streams Parquet files as raw bytes to ClickHouse via HTTP; ClickHouse handles all Parquet parsing. `pyarrow` would only be needed if implementing `max_rows` for Parquet in Phase 3.

## Implementation Phases

### Phase 1: Core End-to-End

**Deliver:**

- Config loading with Pydantic validation
- ClickHouse client with connection pooling
- Schema loader with project + variant resolution
- Data loader with HTTP streaming
- Workload runner with:
  - Single-threaded warmup before measurement
  - Concurrent workers with ThreadPoolExecutor
  - Query timeout handling
  - `query_id` tracking
- Metrics collector using `query_id` matching
- Reporter generating CSV with timing metadata
- CLI: `validate`, `init-db`, `load-data`, `run-workload`, `full-run`

**Acceptance:**

- `full-run` produces valid CSV with correct QPS
- Failures produce clear messages and non-zero exit codes
- Warmup runs before concurrent measurement

### Phase 2: Usability

**Add:**

- Markdown output
- `compare` command
- Query parameterization
- Weighted query selection
- `--dry-run` flag
- Enhanced logging

**Acceptance:**

- Both CSV and Markdown produced
- Two variants comparable with single command

### Phase 3: Refinements

**Possible Additions:**

- Database naming isolation
- Improved query log mismatch handling
- Progress reporting
- Graceful shutdown handling
- Results metadata (git commit, ClickHouse version)
