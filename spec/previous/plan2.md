# ClickHouse Benchmarking Harness Specification (Revised)

## High-Level Goal

Build a small Python harness that can:

- Spin up one or more ClickHouse schemas from `.sql` files
- Load test data from CSV or Parquet into those schemas
- Run configurable workloads (sets of queries) with varying concurrency and duration
- Collect timings and key metrics from `system.query_log`
- Emit results as CSV/Markdown for easy comparison between schema variants

## Project Layout

```
ch-harness/
  pyproject.toml
  README.md

  harness/
    __init__.py
    config.py           # parse YAML config
    clickhouse_client.py
    schema_loader.py
    data_loader.py
    workload_runner.py
    metrics_collector.py
    reporter.py
    comparator.py         # NEW: compare results between variants
    parameter_generator.py # NEW: generate query parameters
    utils.py              # NEW: shared utilities
    exceptions.py         # NEW: custom exceptions
    cli.py

  configs/
    example_basic.yml
    example_weighted.yml  # NEW: shows query weights
    example_params.yml    # NEW: shows parameterization

  schemas/
    variant_a/
      001_create_tables.sql
      002_indexes.sql
    variant_b/
      001_create_tables.sql

  data/
    variant_a/
      trades.csv
      prices.parquet
    variant_b/
      trades.csv

  workloads/
    baseline/
      q01_latency.sql
      q02_throughput.sql
    heavy/
      q01_full_scan.sql

  results/  # NEW: default output directory
    .gitkeep
```

## Config Model

Enhanced YAML config with additional features:

```yaml
clickhouse:
  host: "localhost"
  port: 8123
  user: "default"
  password: ""
  database: "bench"
  connection_pool_size: 20  # NEW: for high concurrency
  timeout_seconds: 300      # NEW: query timeout

schema:
  variant: "variant_a"
  fail_on_error: true       # NEW: stop on schema errors

data:
  path: "variant_a"
  load_method: "auto"       # NEW: "auto", "http", or "file"
  truncate_before_load: true # NEW: explicit truncate control
  load:
    - table: "trades"
      file: "trades.csv"
      format: "CSV"
      skip_rows: 1          # NEW: skip header rows
      max_rows: null        # NEW: limit for testing

workload:
  name: "baseline"
  path: "baseline"

  # NEW: explicit query list with weights
  queries:
    - file: q01_latency.sql
      weight: 10  # runs 10x more often than weight=1
    - file: q02_throughput.sql
      weight: 1

  concurrency: 8
  duration_seconds: 120
  ramp_up_seconds: 10
  warmup_queries: 20        # NEW: warm caches before measurement
  think_time_ms: 50
  max_errors: 100           # NEW: abort if too many errors
  query_timeout_seconds: 60 # NEW: per-query timeout

  # NEW: query parameterization
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
  query_log_wait_seconds: 10  # NEW: wait for async query_log writes
  output_csv: "results/baseline_variant_a.csv"
  output_md: "results/baseline_variant_a.md"
```

Implement `harness/config.py` to parse this and provide a typed object.

## Core Components

### clickhouse_client.py

Wrapper around HTTP interface using `httpx` with connection pooling.

**Functions:**

```python
execute(sql: str, params: dict | None = None) -> list[dict]
execute_no_result(sql: str) -> None
insert_stream(table: str, file_handle, format: str) -> None  # NEW
```

**Key features:**
- Use `httpx.Client()` with `limits=httpx.Limits(max_connections=20)`
- Support setting `query_id` parameter for tracking
- Enable `log_queries=1` if not already set in server config
- Proper timeout handling

### schema_loader.py

**Responsibilities:**

- Drop/recreate database if `--fresh` flag is passed
- Load all `.sql` files in `schemas/<variant>/` sorted by filename
- Execute each file as a single batch (ClickHouse HTTP supports multi-statement)
- Log what ran
- Fail fast on errors by default (unless `fail_on_error: false`)

```python
def apply_schema(variant: str, client: ClickHouseClient, database: str, fresh: bool):
    # if fresh: DROP DATABASE IF EXISTS; CREATE DATABASE
    # then run each *.sql in schemas/variant
```

### data_loader.py

**Responsibilities:**

Implements **dual loading strategy** with auto-detection:

1. **file() method**: Faster, requires ClickHouse server can access file paths
2. **HTTP streaming**: Portable, works for remote/Docker ClickHouse

**Implementation:**

```python
def load_data_to_table(client, table, file_path, format, method="auto"):
    """
    method: "auto", "http", or "file"
    - auto: try file() first, fall back to HTTP if fails
    - http: stream via HTTP POST
    - file: use file() function (requires server access)
    """
    if method == "auto" or method == "file":
        try:
            # Try file() function first (faster if available)
            abs_path = os.path.abspath(file_path)
            sql = f"INSERT INTO {table} SELECT * FROM file('{abs_path}', '{format}')"
            client.execute_no_result(sql)
            return
        except Exception as e:
            if method == "file":
                raise
            logger.info(f"file() method failed, falling back to HTTP streaming: {e}")

    # HTTP streaming method
    with open(file_path, 'rb') as f:
        client.insert_stream(table, f, format)
```

**Features:**
- Support CSV and Parquet formats
- Honor `skip_rows` and `max_rows` config
- Show progress for large files (>1GB)
- Option to truncate tables before load

## Workload Runner

### Behavior

Simulate concurrent users hitting a set of queries repeatedly for N seconds.

**Spec:**

1. Read all `.sql` files in `workloads/<path>/` into memory
2. Build weighted query pool based on `weight` parameter (default=1)
3. **Warmup phase**: Each worker runs N queries to warm caches (results discarded)
4. **Measurement phase**: Each worker thread:
   - Randomly picks a query from weighted pool
   - Substitutes parameters if defined
   - Generates unique `query_id = f"{query_name}_{uuid.uuid4()}"`
   - Executes query with query_id
   - Records:
     - Query ID (for joining with query_log)
     - Start time
     - End time
     - Duration
     - Query name (filename)
     - Success/failure
     - Error message if failed
5. Run for `duration_seconds`
6. Wait `query_log_wait_seconds` for async query_log writes
7. Return execution records

**Implementation detail:** Use `concurrent.futures.ThreadPoolExecutor`. Threading is fine since ClickHouse is remote and IO bound.

### workload_runner.py

```python
run_workload(config, client) -> list[ExecutionRecord]
```

Where `ExecutionRecord` is:

```python
@dataclass
class ExecutionRecord:
    query_id: str          # NEW: for joining with query_log
    query_name: str
    started_at: datetime
    finished_at: datetime
    duration_ms: float
    success: bool
    error_message: str | None
```

**Query weight implementation:**

```python
# Build weighted pool
query_pool = []
for query in queries:
    weight = query.get('weight', 1)
    query_pool.extend([query] * weight)

# Each worker picks from weighted pool
selected = random.choice(query_pool)
```

### parameter_generator.py (NEW)

**Responsibilities:**

Generate random parameters for queries based on config.

**Supported types:**
- `random_int`: Random integer in range [min, max]
- `random_choice`: Random selection from list of values
- `random_float`: Random float in range (future)
- `uuid`: Generate UUID (future)

**Example:**

```python
def generate_params(param_config: dict) -> dict:
    params = {}
    for name, spec in param_config.items():
        if spec['type'] == 'random_int':
            params[name] = random.randint(spec['min'], spec['max'])
        elif spec['type'] == 'random_choice':
            params[name] = random.choice(spec['values'])
    return params
```

**Query file with parameters** (`q01_user_trades.sql`):
```sql
-- Parameters: {user_id}
SELECT * FROM trades WHERE user_id = {user_id} LIMIT 100
```

**Substitution** (simple string formatting with validation):
```python
query_sql = query_template.format(**params)
```

## Metrics Collection via system.query_log

### metrics_collector.py

**Responsibilities:**

Query `system.query_log` using **query_id matching** (not query text matching).

**Critical implementation details:**
- Wait `query_log_wait_seconds` after workload completes (default 10s)
- Or poll until expected query count reached (with 60s timeout)
- Match on `query_id` field (exact, reliable)
- Filter by `event_time` between workload start/end
- Optionally filter by `query_kind = 'Select'`

**Extract fields:**

- `query_id` (for joining)
- `query`
- `query_duration_ms`
- `read_rows`
- `read_bytes`
- `result_rows`
- `result_bytes`
- `memory_usage`
- `ProfileEvents` summary (optional, future)

```python
def fetch_query_log_metrics(client, query_ids: list[str], since: datetime, until: datetime) -> list[dict]:
    # SELECT ... FROM system.query_log
    # WHERE query_id IN (...) AND event_time >= since AND event_time <= until
```

Join with `ExecutionRecords` on `query_id` for complete metrics.

## Reporter

### reporter.py

**Requirements:**

Take:

- List of `ExecutionRecord`
- List of `query_log` rows (joined on query_id)

**Compute per-query stats:**

- p50/p95/p99 latency
- min/max
- count
- error count
- **QPS (queries per second)** - NEW
- **Error rate** - NEW
- avg `read_rows`, `read_bytes`, `memory_usage` if available

**Emit:**

- CSV file with per-query metrics
- Markdown table for quick drop into Confluence/Notion

**Updated CSV columns:**

```
query_name,count,errors,qps,error_rate,p50_ms,p95_ms,p99_ms,min_ms,max_ms,avg_read_rows,avg_read_bytes,avg_memory_usage
```

**Example Markdown:**

```markdown
| Query       | Count | QPS  | p50 (ms) | p95 (ms) | p99 (ms) | Errors | Avg rows read | Avg bytes read |
|-------------|-------|------|----------|----------|----------|--------|---------------|----------------|
| q01_latency | 1000  | 83.3 | 12       | 25       | 40       | 0      | 1.2M          | 45MB           |
| q02_tput    | 100   | 8.3  | 120      | 250      | 400      | 2      | 15M           | 500MB          |
```

**Implementation:**
```python
qps = total_queries / duration_seconds
error_rate = error_count / total_queries
```

### comparator.py (NEW)

**Responsibilities:**

Compare results from multiple benchmark runs (different schema variants).

**Command:**
```bash
python -m harness.cli compare \
  results/baseline_variant_a.csv \
  results/baseline_variant_b.csv \
  --output comparison.md
```

**Output example:**
```markdown
| Query       | Variant A p50 | Variant B p50 | Δ (%) | Variant A QPS | Variant B QPS | Δ (%) |
|-------------|---------------|---------------|-------|---------------|---------------|-------|
| q01_latency | 12ms          | 8ms           | -33%  | 83.3          | 125.0         | +50%  |
| q02_tput    | 120ms         | 150ms         | +25%  | 8.3           | 6.7           | -19%  |
```

**Features:**
- Side-by-side comparison
- Calculate percentage difference
- Highlight regressions (color in terminal, bold in markdown)
- Support comparing 2+ variants

## CLI Entrypoint

### cli.py

Implement CLI using `argparse`.

**Commands:**

**`validate`** - NEW
- Validate config without execution
- Check files exist, ClickHouse connectivity
- Useful for CI/CD

**`init-db`**
- `--config configs/example_basic.yml`
- Applies schema and optionally drops database
- `--fresh` flag to drop/recreate

**`load-data`**
- Uses `data_loader` and config
- Shows progress for large files

**`run-workload`**
- Runs the workload
- Captures start/end timestamps
- Runs `metrics_collector`
- Writes CSV and Markdown via `reporter`

**`full-run`**
- `init-db` (optional `--fresh`)
- `load-data`
- `run-workload`
- Most common workflow

**`compare`** - NEW
- Compare results from multiple runs
- Generate side-by-side comparison

**Global flags:**
- `--config`: Path to YAML config
- `--fresh`: Drop database before init
- `--dry-run`: Validate without executing
- `--verbose`: Detailed logging
- `--quiet`: Minimal output

**Usage:**

```bash
# Validate config
python -m harness.cli validate --config configs/example.yml

# Full run with fresh database
python -m harness.cli full-run --config configs/example_basic.yml --fresh

# Dry run
python -m harness.cli full-run --config configs/example.yml --dry-run

# Compare variants
python -m harness.cli compare \
  results/variant_a.csv \
  results/variant_b.csv \
  --output comparison.md

# Individual commands
python -m harness.cli init-db --config configs/example.yml --fresh
python -m harness.cli load-data --config configs/example.yml
python -m harness.cli run-workload --config configs/example.yml
```

## Non-Negotiable Design Constraints

### Statelessness
No hidden global state. Everything parameterized by config and CLI flags.

### Repeatability
Running the same config twice should produce comparable results.

### Schema Variants
The harness must make it easy to run the same workload against different schema variants by just changing `schema.variant` and `data.path` in config.

### No Magic ClickHouse Assumptions
All ClickHouse details, like DB name and user, are taken from config.

### Extensibility
Code should be modular so you can later:

- Plug in synthetic data generators
- Add more workload patterns
- Benchmark different clusters simply by changing config

## Dependencies (pyproject.toml)

```toml
[project]
name = "ch-harness"
version = "0.1.0"
dependencies = [
    "httpx>=0.27.0",      # ClickHouse HTTP client with connection pooling
    "pyyaml>=6.0",        # Config parsing
    "pandas>=2.0.0",      # Percentile calculations, optional advanced metrics
    "pyarrow>=14.0.0",    # Parquet support
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "black>=24.0.0",
    "ruff>=0.1.0",
]
```

## Critical Implementation Notes

1. **Query ID tracking**: Always set `query_id` when executing queries, store in `ExecutionRecord`, use for joining with `system.query_log`

2. **Async query_log handling**:
   - Wait 10s after workload completes
   - Or poll `system.query_log` until expected count reached (max 60s timeout)
   - Warn if query_log count doesn't match execution count

3. **Connection pooling**:
   - Use `httpx.Client()` with `limits=httpx.Limits(max_connections=20)`
   - Reuse client across workers

4. **Error handling**:
   - Schema/data errors: Fail fast by default
   - Workload errors: Log and continue, track in `ExecutionRecord`
   - Abort if `max_errors` threshold exceeded

5. **Logging**:
   - Use Python `logging` module
   - `--verbose` flag for debug level
   - Log to stdout + optional file
   - Log: schema DDL execution, data load progress, workload start/end, per-worker errors

6. **Progress tracking**:
   - Show progress for data loads >1GB using `tqdm` or similar
   - Show workload progress (queries executed / time remaining)

7. **SQL file execution**:
   - Execute each `.sql` file as single batch (ClickHouse supports multi-statement)
   - Don't split on semicolons (complex, error-prone)

## Testing Strategy

1. **Unit tests**: Each module (config parser, parameter generator, reporter, etc.)
2. **Integration test**: Spin up ClickHouse in Docker, run full-run with test data
3. **Sample data**: Include tiny CSV/Parquet files in `data/sample/` for testing
4. **Example configs**: Test all config variations (basic, weighted, parameterized)

## Documentation Requirements

1. **README.md**:
   - Quickstart (install, run example)
   - Architecture overview
   - CLI reference
   - Configuration guide

2. **Example configs**:
   - `example_basic.yml`: Simple case
   - `example_weighted.yml`: Query weights
   - `example_params.yml`: Query parameterization

3. **Troubleshooting guide**:
   - file() vs HTTP loading
   - query_log timing issues
   - Connection pooling
   - Common errors

## Key Improvements Over Original Spec

### Critical Fixes
1. **Data loading**: Dual method (HTTP streaming + file()) with auto-detection for portability
2. **Query matching**: Use explicit `query_id` instead of fragile query text matching
3. **Connection pooling**: Proper `httpx` configuration for high concurrency
4. **Throughput metrics**: Added QPS and error rate to reporter

### Enhanced Features
5. **Query weights**: Simulate realistic traffic patterns
6. **Query parameterization**: Dynamic queries with random parameters
7. **Warmup phase**: Warm caches before measurement for accuracy
8. **Comparison command**: Built-in tool to compare schema variants
9. **Validation**: `--dry-run` and `validate` command
10. **Better error handling**: `max_errors` threshold, explicit error strategies
11. **Logging**: Comprehensive logging with verbosity control
12. **Progress tracking**: Visual feedback for long operations

## Implementation Estimate

**Core features**: ~1-2 days
- Config parser, ClickHouse client, schema loader: 0.5 day
- Data loader (dual method): 0.5 day
- Workload runner (with weights, params, warmup): 1 day
- Metrics collector, reporter: 0.5 day
- CLI: 0.5 day

**Enhanced features**: ~0.5 day
- Comparison command: 0.25 day
- Validation, dry-run: 0.25 day

**Testing & docs**: ~0.5 day
- Unit tests: 0.25 day
- Integration test, README: 0.25 day

**Total**: ~2-3 days for complete implementation
