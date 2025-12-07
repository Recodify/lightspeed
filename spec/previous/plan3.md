# ClickHouse Benchmark Harness – Complete Specification

This document defines a benchmarking harness designed to evaluate ClickHouse performance under different schema and data layouts, using realistic workloads. The harness must provide repeatable testing, structured output, and comparability of results across schema variants.

## 1. Purpose

The harness will allow users to:

1. Apply a schema definition and load data into ClickHouse
2. Execute controlled concurrency workloads using SQL files
3. Parameterise queries dynamically
4. Capture execution timings and query log metrics
5. Produce structured summary results
6. Compare multiple benchmark runs across schema variants

This enables reliable performance evaluation without manual experimentation.

## 2. Technology

- **Language:** Python
- **ClickHouse communication:** HTTP via `httpx.Client`
- **Storage format for workload input:** SQL files
- **Configuration:** YAML
- **Outputs:** CSV and Markdown

ClickHouse native binary protocol must not be used.

## 3. Repository Structure

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

  configs/
    example_basic.yml
    example_weighted.yml
    example_params.yml

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

  results/
    .gitkeep
```

This structure is fixed and must be followed.

## 4. Configuration Specification (YAML)

Configuration must support the following fields:

```yaml
clickhouse:
  host: "localhost"
  port: 8123
  user: "default"
  password: ""
  database: "bench"
  connection_pool_size: 20
  timeout_seconds: 300

schema:
  variant: "variant_a"
  fail_on_error: true
  fresh: true

data:
  path: "variant_a"
  load_method: "auto"
  truncate_before_load: true
  load:
    - table: "trades"
      file: "trades.csv"
      format: "CSV"
      skip_rows: 1
      max_rows: null

workload:
  name: "baseline"
  path: "baseline"
  queries:
    - file: "q01_latency.sql"
      weight: 10
    - file: "q02_throughput.sql"
      weight: 2

  concurrency: 8
  duration_seconds: 120
  ramp_up_seconds: 10
  warmup_queries: 20
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
  output_md: "results/baseline_variant_a.md"
```

All fields must be parsed and validated.

## 5. Module Requirements

### 5.1 config.py

Must:

- Load YAML into structured config objects
- Validate required paths exist
- Verify ClickHouse connectivity using `SELECT 1`
- Provide errors with actionable messages

### 5.2 clickhouse_client.py

Requirements:

- Use `httpx.Client` with connection pooling
- Provide:

```python
execute(sql: str, params: dict|None, settings: dict|None) -> rows
execute_no_result(sql: str, params: dict|None, settings: dict|None)
insert_stream(table: str, file_handle, format: str)
```

- Must support passing `query_id` via `settings`

### 5.3 schema_loader.py

Must:

- If `fresh=true`, drop & recreate database
- Apply each file in ordered lexical order
- Execute each SQL file as a single statement (no splitting)
- Stop immediately if failure and `fail_on_error=true`

### 5.4 data_loader.py

Requirements:

- Must ingest using HTTP INSERT into ClickHouse
- Must support:
  - `skip_rows` for CSV
  - Truncate before load if configured
  - `max_rows` limitation by truncating input before send

Implementation detail:

- For CSV, use streaming POST
- For Parquet, stream binary payload

`load_method` is present but may initially behave identically to HTTP-based ingestion.

### 5.5 parameter_generator.py

Must support:

- `{field}` → `random_int(min,max)`
- `{field}` → `random_choice(values)`

Returned result should be a dict suitable for `.format(**params)` replacement.

### 5.6 workload_runner.py

Requirements:

- Load SQL files from workload folder
- Expand weighted query selection
- Worker behaviour:
  - Run warmup queries (ignored for reporting)
  - Then run measurement queries until duration expires
- Each query execution must:
  - Assign a globally unique `query_id`
  - Record timing
  - Collect error state
- Store:

```
query_name, query_id, started_at, finished_at, duration_ms, success, error_message
```

Abort workload early if `max_errors` is exceeded.

### 5.7 metrics_collector.py

Functionality:

- After workload ends, wait configured seconds
- Query `system.query_log` using `query_id IN (...)`
- Collect:
  - `query_duration_ms`
  - `read_rows`
  - `read_bytes`
  - `result_rows`
  - `result_bytes`
  - `memory_usage`
- Return mapping by `query_id`

Client-side records must be joined using this mapping.

### 5.8 reporter.py

Must compute per query name:

- count
- errors
- error rate
- QPS
- p50 latency
- p95 latency
- p99 latency
- avg read_rows
- avg read_bytes
- avg memory_usage

Must output both:

1. CSV (canonical artifact)
2. Markdown (human-readable table)

### 5.9 comparator.py

Comparison must:

- Load two CSVs
- Join on `query_name`
- Produce deltas for:
  - QPS
  - p50
  - p95

Write a Markdown table showing before/after values and percentage change.

### 5.10 cli.py

Commands:

```
validate          # Validate config, environment, paths, connectivity
init-db           # Apply schema rules
load-data         # Load dataset
run-workload      # Execute workload; produce artifacts
full-run          # init-db + load-data + run-workload
compare <A> <B>   # Compare two result sets
```

Global flags:

```
--config path
--verbose
--dry-run
```

Dry-run performs validation only.

## 6. Logging Requirements

- Use Python `logging` module
- INFO is default
- DEBUG when `--verbose` enabled
- At minimum log:
  - DB creation
  - Schema file execution
  - Rows inserted per table
  - Workload start/stop times
  - Number of failures
  - Output file paths

## 7. Output Deliverables

The harness must generate:

### Mandatory outputs

- One CSV per run containing metrics
- One Markdown summary table
- Comparison Markdown output when comparing runs

### Implicit outputs

- Progress and logs in stdout

## 8. Correctness Guarantees

The harness must:

- Never rely on fuzzy matching of queries
- Identify executions strictly by `query_id`
- Ensure that query_log data is flushed before collection
- Correctly align workload timing with measurements
- Produce deterministic outputs when run twice on the same system

## 9. Phased Implementation Plan

The design above is the full system. Implementation may proceed in phases.

### Phase 1 — Fully Correct, Repeatable Core Harness

This phase must deliver a working harness that executes end-to-end without silent failures, missed states, or ambiguous outputs.

#### Mandatory Delivery Items

**1. Configuration & Validation**

- ✔ Validates required folders exist
- ✔ Validates ClickHouse connection via `SELECT 1`
- ✔ Aborts early on:
  - Missing schema files
  - Missing workload files
  - Missing data files

No partial execution allowed if validation fails.

**2. Schema Loading (with guarantees)**

- ✔ Ordered execution
- ✔ Errors must be reported per file
- ✔ If `fail_on_error=true`:
  - Execution stops immediately
  - Harness exits with non-zero status
- ✔ If `fail_on_error=false`:
  - Errors logged
  - Progress continues
  - End summary lists failed files

**3. Data Loading**

- ✔ HTTP ingestion only
- ✔ Relies on correct row count confirmation
- ✔ Log must include:
  - `table_name`
  - `rows_sent`
  - `bytes_sent` (if detectable)
  - `duration`
  - Execution success/failure
- ✔ Must warn if zero rows inserted
- ✔ Must validate table exists before insertion

**4. Workload Execution**

- ✔ Every query execution tracked
- ✔ Every failure recorded
- ✔ Harness aborts early if error threshold breached

Example: `max_errors=10` and worker hits 11 failures → workload terminates

- ✔ All errors must contain:
  - `query_id`
  - `query_name`
  - `error_message`
  - `elapsed_ms`

No swallowed errors are allowed.

**5. Query Log Matching**

- ✔ Must guarantee one-to-one matching
- ✔ If missing query logs:
  - Harness should warn explicitly
  - Log number expected vs number found
  - Produce partial results only with a warning header

Example warning:

```
WARNING: 124 executions recorded client-side, but only 120 found in query_log.
4 missing records have been marked with metrics=null.
```

**6. CSV Reporting Guarantees**

Output must:

- Never be empty
- Always contain headers
- Include error rate
- Include QPS (not optional)

Errors must never appear as blanks, they must be explicit:
`error_message="<string>"` or `error_message=null`

**7. CLI Exit Codes**

This part matters a lot for reliability:

| Exit code | Meaning |
|-----------|---------|
| 0 | All stages executed successfully |
| 1 | Validation failed before execution |
| 2 | Schema build failure |
| 3 | Data ingestion failure |
| 4 | Workload aborted due to thresholds |
| 5 | Metrics collection incomplete |
| >5 | Unexpected runtime failure |

This allows usage in CI/CD and integration pipelines.

#### Phase 1 Acceptance Criteria

This is non-negotiable.

A harness user must be able to run:

```bash
python -m harness.cli full-run --config configs/example_basic.yml
```

…and guaranteed:

- Schema created or explicitly aborted
- Data loaded or explicitly aborted
- Workload executed or aborted with error cause
- CSV produced
- Report includes correctness notes

And critically: **No silent degraded mode may exist.**

### Phase 2 — Usability & Comparative Interpretation

Once correctness is done, usability enhancements become natural.

Deliver:

- Markdown summary output
- Comparison command (side-by-side deltas)
- Weighted workload selection
- Basic parameter substitution

Focus here is convenience, not correctness.

### Phase 3 — Advanced Testing Fidelity Features

This phase adds analytical sophistication:

- Database run isolation (timestamp-based DB names)
- Highlighting queries with regressions
- Grouping workloads by class (latency vs full scans)
- Annotating outputs with timestamp, git commit tag, host identification

Example extended output row:

```
device_hostname, git_commit_hash, timestamp, query_name, p50_latency_ms, p95_latency_ms
```

These enable long-term benchmarking history.

### Why This Ordering Makes Sense

**Phase 1 = correctness**

It must not be possible to:

- Think performance improved when metrics were missing
- Ingest partial data
- Execute against wrong schema
- Silently produce mismatched execution vs query logs

Without correctness, benchmark data is worthless.

**Phase 2 = insight**

Quality-of-life features make consumption easier.

**Phase 3 = institutional value**

This is where the harness becomes a long-term asset.

---

This document represents the complete design and delivery plan. It is authoritative and final.