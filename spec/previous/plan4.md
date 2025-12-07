# ClickHouse Benchmark Harness – Full Specification

This document defines a ClickHouse benchmarking harness that can support multiple projects and schema variants under a single tool.

The harness must:

- Run repeatable benchmarks against ClickHouse
- Support multiple logical projects under `projects/`
- Support shared project assets plus per-variant overrides
- Produce trustworthy metrics with clear error behaviour
- Compare results across schema variants and runs

## 1. Repository Structure

The repository layout is fixed and must look like this:

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

Key ideas:

- `projects/<project>` defines a logical benchmarking project
- Each project can have:
  - Shared schemas, data, workloads
  - Multiple variants with their own overrides
- Results are written under `projects/<project>/results`

## 2. Configuration Format

Config files live under `projects/<project>/configs/`.

Each config must follow this structure:

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
  load_method: "auto"           # initially treated as HTTP
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
  output_md:  "results/baseline_variant_a.md"
```

### 2.1 Project and variant selection

- `project`: name of directory under `projects/`
- `variant`: name of directory under `projects/<project>/variants/`

The harness must treat these as the primary selectors for resolving schema, data, workloads and result paths.

## 3. Path Resolution Rules

All resolution is based on project and variant.

Let:

- `PROJECT_ROOT = projects/<project>`
- `VARIANT_ROOT = projects/<project>/variants/<variant>`

### 3.1 Schemas

Schema files are applied in two layers:

1. **Project-wide schemas first:**
   - `PROJECT_ROOT/schemas/*.sql` sorted by filename
   - Optional, may be empty

2. **Variant-specific schemas next:**
   - `VARIANT_ROOT/schemas/*.sql` sorted by filename
   - Optional, may be empty

Execution order is always: project level, then variant level.

Semantics are controlled by the SQL. If a variant wants to override project tables it must do so explicitly with DROP or CREATE statements.

### 3.2 Data

For each configured `data.load` entry with `file: "<name>"`:

1. First try variant-specific:
   - `VARIANT_ROOT/data/<file>`

2. If not found, fallback to project-wide:
   - `PROJECT_ROOT/data/<file>`

If neither exists, the harness must treat this as a validation error and abort before loading.

### 3.3 Workloads

Workloads are stored under:

- **Project-wide:**
  - `PROJECT_ROOT/workloads/<workload.path>/...`

- **Optionally variant-specific:**
  - `VARIANT_ROOT/workloads/<workload.path>/...`

Resolution rule for each configured query file name in `workload.queries`:

1. Try `VARIANT_ROOT/workloads/<path>/<file>`
2. If not found, try `PROJECT_ROOT/workloads/<path>/<file>`
3. If not found, validation must fail

All queries must be resolvable before running the workload.

### 3.4 Results

`metrics.output_csv` and `metrics.output_md` are treated as paths relative to `PROJECT_ROOT`, unless they are absolute.

Example config:

```yaml
metrics:
  output_csv: "results/baseline_variant_a.csv"
  output_md:  "results/baseline_variant_a.md"
```

The harness must write to:

- `PROJECT_ROOT/results/baseline_variant_a.csv`
- `PROJECT_ROOT/results/baseline_variant_a.md`

## 4. Modules and Responsibilities

All modules live under `harness/`.

### 4.1 config.py

**Tasks:**

- Load YAML config into typed structures
- Read `project` and `variant`, compute `PROJECT_ROOT` and `VARIANT_ROOT`
- Validate:
  - Project directory exists
  - ClickHouse connectivity with `SELECT 1`
  - Presence and readability of schema, data, workloads as per resolution rules
- Provide clear error messages and non-zero exit codes when validation fails

### 4.2 clickhouse_client.py

**Implementation:**

- Use `httpx.Client` with connection pooling
- Construct base URL from `clickhouse.host` and `clickhouse.port`
- Provide functions:

```python
execute(sql: str, params: dict | None = None, settings: dict | None = None) -> list[dict]
execute_no_result(sql: str, params: dict | None = None, settings: dict | None = None) -> None
insert_stream(table: str, file_handle, fmt: str, settings: dict | None = None) -> None
```

- Must support passing ClickHouse settings, including `query_id`
- Must respect `timeout_seconds` and connection pool size from config

### 4.3 schema_loader.py

**Behaviour:**

If `schema.fresh` is true:

1. `DROP DATABASE IF EXISTS <database>`
2. `CREATE DATABASE <database>`

Then:

1. Apply all `PROJECT_ROOT/schemas/*.sql` sorted lexically
2. Apply all `VARIANT_ROOT/schemas/*.sql` sorted lexically

**Execution is:**

- Each file read entirely and sent as a single statement over HTTP
- No splitting by semicolon

**Error handling:**

- If a statement fails and `fail_on_error` is true:
  - Log the failing file and error
  - Abort schema loading and return a specific exit code
- If `fail_on_error` is false:
  - Log the error but continue
  - At the end, summarise failed files

### 4.4 data_loader.py

**Implementation constraints:**

- Data must be loaded using HTTP INSERT
- `load_method` may be present but must be handled as HTTP only for now

For each `data.load` entry:

1. Resolve file path using project or variant rule
2. If `truncate_before_load` is true:
   - Issue `TRUNCATE TABLE <table>`
3. Open the file and, for CSV, skip `skip_rows` lines in the client before streaming
4. If `max_rows` is set, stop after that many rows when reading
5. Use:
   ```sql
   INSERT INTO <table> FORMAT <format>
   ```
   with the file streamed as the request body
6. Log for each table:
   - Table name
   - Rows sent (if counted)
   - Approximate bytes sent
   - Duration
   - Success or failure

Any failure must abort the process with a clear error.

### 4.5 parameter_generator.py

Must support dynamic parameters for workload queries.

For a configuration:

```yaml
workload:
  parameters:
    user_id:
      type: random_int
      min: 1
      max: 1000
    date:
      type: random_choice
      values: ["2024-01-01", "2024-06-01", "2024-12-01"]
```

It must expose:

```python
def generate_params(param_config: dict) -> dict:
    # returns something like {"user_id": 123, "date": "2024-06-01"}
```

**Types:**

- `random_int` with `min`, `max`
- `random_choice` with explicit values list

Queries use Python `.format` placeholders, for example:

```sql
SELECT *
FROM trades
WHERE user_id = {user_id}
  AND trade_date = toDate('{date}')
LIMIT 100;
```

The workload runner must call:

```python
sql_to_run = raw_sql.format(**params)
```

### 4.6 workload_runner.py

**Responsibilities:**

- Load queries as text from resolved workload files
- Build a weighted selection pool from config:

```yaml
queries:
  - file: "q01_latency.sql"
    weight: 10
  - file: "q02_throughput.sql"
    weight: 2
```

A worker must:

- Run a warmup phase that issues `warmup_queries` executions, ignored for metrics
- Then run a measurement phase for `duration_seconds`

For each execution, the runner must:

- Pick a query according to weight
- Generate parameters
- Create a unique `query_id` (for example `f"{query_name}_{uuid4()}"`)
- Record start time
- Execute via `clickhouse_client.execute(...)` with `query_id` passed as a setting
- Record end time
- Calculate `duration_ms`
- Record success or failure and any error message
- Sleep `think_time_ms` between executions

Define an `ExecutionRecord` structure with at least:

- `query_name`
- `query_id`
- `started_at`
- `finished_at`
- `duration_ms`
- `success`
- `error_message`

**Workload abort policy:**

- Maintain a shared error counter
- If total number of failures exceeds `max_errors`, abort all workers and mark run as aborted due to error threshold

### 4.7 metrics_collector.py

**Tasks:**

- After workload completes, sleep `metrics.query_log_wait_seconds` to allow ClickHouse to flush `system.query_log`
- Query `system.query_log` with:
  - `type = 'QueryFinish'`
  - `query_id IN (...)` for all recorded query_ids
- Extract for each row:
  - `query_id`
  - `query_duration_ms`
  - `read_rows`
  - `read_bytes`
  - `result_rows`
  - `result_bytes`
  - `memory_usage`
- Return a mapping `query_id -> metrics dict`

If fewer query_ids are found than executions:

- Log a clear warning showing expected and actual counts
- Keep records with missing log metrics, but mark their query_log derived fields as null or missing

### 4.8 reporter.py

Combine:

- `ExecutionRecord` list
- Query log metrics mapping

For each `query_name` compute:

- Count of executions
- Errors count
- `error_rate = errors / count`
- QPS over the measurement period:
  ```
  qps = count / duration_seconds
  ```
- Latency percentiles p50, p95, p99 based on `duration_ms` from `ExecutionRecord`
- Average `read_rows`, `read_bytes`, `memory_usage` from query log metrics where present

**Produce:**

1. CSV with header:
   ```
   query_name,count,errors,error_rate,qps,p50_ms,p95_ms,p99_ms,avg_read_rows,avg_read_bytes,avg_memory_usage
   ```

2. Markdown table with the same information in human-readable form

The harness must always emit headers and must never produce an empty file silently.

### 4.9 comparator.py

Given two result CSV files, for example:

```bash
python -m harness.cli compare \
  projects/default/results/baseline_variant_a.csv \
  projects/default/results/baseline_variant_b.csv \
  --output projects/default/results/baseline_compare.md
```

The comparator must:

- Load both CSVs
- Join on `query_name`
- Compute for each query:
  - p50 delta percentage
  - p95 delta percentage
  - QPS delta percentage

Generate a Markdown table like:

```markdown
| Query       | A p50 (ms) | B p50 (ms) | Δ p50 (%) | A QPS | B QPS | Δ QPS (%) |
|------------|------------|------------|-----------|-------|-------|-----------|
| q01_latency| 12         | 8          | -33.3     | 80    | 120   | +50.0     |
```

### 4.10 cli.py

Provide a CLI with these commands:

- `validate`
- `init-db`
- `load-data`
- `run-workload`
- `full-run`
- `compare`

**Global flags:**

- `--config <path>` target config file
- `--verbose` to enable debug logging
- `--dry-run` for `full-run` that performs validation only

**Behaviour:**

**`validate`:**
- Load config
- Resolve project and variant
- Check ClickHouse connectivity
- Confirm all schema, data and workload files exist
- Log any errors and exit with non-zero code on failure

**`init-db`:**
- Run schema loader with configured behaviour

**`load-data`:**
- Run data loader

**`run-workload`:**
- Run workload_runner
- Collect metrics
- Invoke reporter

**`full-run`:**
- Internally does `validate`
- Then `init-db` if `schema.fresh` is true
- Then `load-data`
- Then `run-workload`

**`compare`:**
- Takes two CSV paths and an optional `--output` path
- Writes Markdown comparison to the given output path or to stdout if none provided

Exit codes should be consistent and nonzero on any failure so this can be used in CI or automation.

## 5. Logging and Error Behaviour

Logging must use Python `logging` module.

- **Default level:** INFO
- **With `--verbose`:** DEBUG

At minimum log:

- Selected project and variant
- Resolved paths for schema, data, workloads
- ClickHouse connection success or failure
- Schema file execution start and outcome
- Per table data load summary
- Workload start and end times
- Number of successful and failed query executions
- Any mismatch between query executions and query log entries
- Paths of generated CSV and Markdown output

**Error handling rules:**

- Validation failures must stop execution before any schema or data changes are made
- Schema or data load failures must abort the corresponding phase and exit with a clear reason
- Workload errors must be counted and surfaced. If above threshold, the run is aborted and marked as such
- Metrics collection issues must be reported, not silently ignored

**No silent degradation is allowed.**

## 6. Phased Implementation Plan

The design above is the full target. Implementation can be split into phases, but each phase must preserve correctness and explicit error behaviour.

### Phase 1: Core End-to-End Harness

**Deliver:**

- Repository layout
- Config loading and validation
- ClickHouse client
- Schema loader with project plus variant resolution
- Data loader with HTTP ingestion
- Workload runner with:
  - Concurrency
  - Warmup
  - `query_id` tracking
- Metrics collector using `system.query_log` and `query_id`
- Reporter that writes CSV with:
  - count, errors, error_rate, qps, p50, p95, p99
- CLI with:
  - `validate`
  - `init-db`
  - `load-data`
  - `run-workload`
  - `full-run`

**Acceptance:**

- Running `full-run` with an example config in `projects/default/configs/` yields a valid CSV under `projects/default/results/` and logs all key steps
- Failures in any stage produce clear messages and non-zero exit codes

### Phase 2: Usability and Interpretation

**Add:**

- Markdown summary output in reporter
- `comparator` command and `comparator.py`
- Parameterisation of queries via `parameter_generator.py`
- Weighted query selection in the workload runner
- `--dry-run` flag
- Better human-readable logs

**Acceptance:**

- CSV and Markdown are both produced
- Two variants can be benchmarked and compared with a single command

### Phase 3: Refinements and Extensions

**Possible additions:**

- Database naming isolation for runs
- Improved warnings around query log mismatches
- Richer metrics in reports
- Optional per-variant workloads with the same override semantics as data

These are enhancements on top of a stable core.

---

This is the full, unified specification for the ClickHouse benchmark harness with multi-project and multi-variant support.