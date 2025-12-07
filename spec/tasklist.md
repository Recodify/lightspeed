# Phase 1 Implementation Tasklist

## Overview

Phase 1 delivers a complete end-to-end benchmarking harness with core functionality:
- Config loading and validation
- Schema and data loading
- Workload execution with proper warmup
- Metrics collection from query_log
- CSV report generation
- CLI interface

## Task Breakdown

### 1. Project Setup

**File:** `pyproject.toml`

- [ ] Create pyproject.toml with dependencies:
  - httpx>=0.27.0
  - pyyaml>=6.0
  - pydantic>=2.0.0
  - pandas>=2.0.0
- [ ] Add dev dependencies (pytest, black, ruff)
- [ ] Configure project metadata (name, version)

**Files:** Repository structure

- [ ] Create `harness/` package directory
- [ ] Create `projects/default/` example project
- [ ] Create subdirectories: `configs/`, `schemas/`, `data/`, `workloads/`, `variants/`, `results/`
- [ ] Add `__init__.py` files to Python packages

---

### 2. Exception Definitions

**File:** `harness/exceptions.py`

- [ ] Define `HarnessError` base exception
- [ ] Define `ValidationError` for config/file validation failures
- [ ] Define `SchemaLoadError` for schema execution failures
- [ ] Define `DataLoadError` for data loading failures
- [ ] Define `WorkloadAbortedError` for max_errors threshold exceeded
- [ ] Define `MetricsCollectionError` for query_log issues

---

### 3. Configuration Module

**File:** `harness/config.py`

- [ ] Define Pydantic models for config structure:
  - `ClickHouseConfig` (host, port, user, password, database, connection_pool_size, timeout_seconds)
  - `SchemaConfig` (fail_on_error, fresh)
  - `DataLoadEntry` (table, file, format)
  - `DataConfig` (load_method, truncate_before_load, load list)
  - `QuerySpec` (file, weight with default=1)
  - `ParameterSpec` (type, min/max for random_int, values for random_choice)
  - `WorkloadConfig` (name, path, queries, concurrency, duration_seconds, etc.)
  - `MetricsConfig` (use_query_log, query_log_wait_seconds, output_csv, output_md)
  - `BenchmarkConfig` (project, variant, clickhouse, schema, data, workload, metrics)

- [ ] Implement `load_config(path: str) -> BenchmarkConfig`
  - Read YAML file
  - Parse with Pydantic
  - Return validated config object

- [ ] Implement path computation:
  - `compute_project_root(config) -> Path`
  - `compute_variant_root(config) -> Path`

- [ ] Implement validation functions:
  - `validate_project_structure(config)` - check directories exist
  - `validate_schema_files(config, project_root, variant_root)` - check .sql files exist
  - `validate_data_files(config, project_root, variant_root)` - check data files exist
  - `validate_workload_files(config, project_root, variant_root)` - check query files exist (explicit or auto-discover)

- [ ] Implement `validate_config(config)` - orchestrates all validation

---

### 4. ClickHouse Client

**File:** `harness/clickhouse_client.py`

- [ ] Create `ClickHouseClient` class
  - Constructor: `__init__(config: ClickHouseConfig, timeout_seconds: int)`
  - Build base URL from host and port
  - Create httpx.Client with:
    - `httpx.Timeout` (read=timeout_seconds)
    - `httpx.Limits` (max_connections=connection_pool_size)

- [ ] Implement `execute(sql: str, params: dict | None = None, settings: dict | None = None) -> list[dict]`
  - POST to ClickHouse HTTP interface
  - Include user, password, database in query params
  - Add settings to query params if provided
  - Parse JSON response
  - Return list of row dicts

- [ ] Implement `execute_no_result(sql: str, params: dict | None = None, settings: dict | None = None) -> None`
  - Same as execute but don't parse response
  - Used for DDL, INSERT

- [ ] Implement `insert_stream(table: str, file_handle, fmt: str, settings: dict | None = None) -> None`
  - Build query: `INSERT INTO {table} FORMAT {fmt}`
  - POST with file_handle as body
  - Stream file bytes directly

- [ ] Implement `test_connection() -> bool`
  - Execute `SELECT 1`
  - Return True if successful, False otherwise

- [ ] Add context manager support (`__enter__`, `__exit__`) for client cleanup

---

### 5. Schema Loader

**File:** `harness/schema_loader.py`

- [ ] Implement `apply_schema(config: BenchmarkConfig, client: ClickHouseClient, project_root: Path, variant_root: Path)`

- [ ] If `config.schema.fresh` is True:
  - Execute `DROP DATABASE IF EXISTS {database}`
  - Execute `CREATE DATABASE {database}`
  - Log actions

- [ ] Load project-wide schemas:
  - Find all `*.sql` in `project_root/schemas/` (sorted)
  - For each file:
    - Read entire file
    - Execute as single statement via `client.execute_no_result()`
    - Log file name and outcome
    - If fails and `fail_on_error=True`, raise `SchemaLoadError`
    - If fails and `fail_on_error=False`, log warning and continue

- [ ] Load variant-specific schemas:
  - Find all `*.sql` in `variant_root/schemas/` (sorted)
  - Same execution logic as project-wide

- [ ] Return summary (files executed, failures)

---

### 6. Data Loader

**File:** `harness/data_loader.py`

- [ ] Implement `resolve_data_file(filename: str, project_root: Path, variant_root: Path) -> Path`
  - Try `variant_root/data/{filename}` first
  - Fallback to `project_root/data/{filename}`
  - Raise `DataLoadError` if neither exists

- [ ] Implement `load_data(config: BenchmarkConfig, client: ClickHouseClient, project_root: Path, variant_root: Path)`

- [ ] For each entry in `config.data.load`:
  - Resolve file path
  - If `truncate_before_load=True`: `TRUNCATE TABLE {table}`
  - Open file in binary mode
  - Determine actual format:
    - If format is "CSV" and headers expected, use "CSVWithNames"
    - Otherwise use format as-is
  - Call `client.insert_stream(table, file_handle, format)`
  - Log: table name, file size, duration, success/failure
  - If fails, raise `DataLoadError`

- [ ] Return summary (tables loaded, bytes transferred)

---

### 7. Parameter Generator

**File:** `harness/parameter_generator.py`

- [ ] Implement `generate_params(param_config: dict | None) -> dict`
  - If param_config is None or empty, return empty dict
  - For each parameter:
    - If `type == "random_int"`: `random.randint(min, max)`
    - If `type == "random_choice"`: `random.choice(values)`
  - Return dict of parameter name → value

---

### 8. Workload Runner

**File:** `harness/workload_runner.py`

- [ ] Implement `load_queries(config: WorkloadConfig, project_root: Path, variant_root: Path) -> list[dict]`
  - If `config.queries` is specified (explicit mode):
    - For each query entry:
      - Resolve file: try `variant_root/workloads/{path}/{file}` then `project_root/workloads/{path}/{file}`
      - Read SQL content
      - Return list: `[{"file": filename, "weight": weight, "sql": content}, ...]`
  - Else (auto-discovery mode):
    - Glob `variant_root/workloads/{path}/*.sql` and `project_root/workloads/{path}/*.sql`
    - If same filename in both, variant wins
    - Return list with weight=1 for all

- [ ] Implement `build_weighted_pool(queries: list[dict]) -> list[dict]`
  - For each query, duplicate it `weight` times in pool
  - Return flattened list for random selection

- [ ] Define `ExecutionRecord` dataclass:
  - `query_id: str`
  - `query_name: str`
  - `executed_sql: str`
  - `started_at: datetime`
  - `finished_at: datetime`
  - `duration_ms: float`
  - `success: bool`
  - `error_message: str | None`

- [ ] Implement `run_warmup(warmup_queries: int, query_pool: list, client: ClickHouseClient, param_config: dict | None)`
  - For i in range(warmup_queries):
    - Select random query from pool
    - Generate parameters
    - Format SQL with parameters
    - Execute (ignore results, ignore errors)
    - Log progress every N queries

- [ ] Implement `worker_func(config: WorkloadConfig, query_pool: list, client: ClickHouseClient, param_config: dict | None, stop_event: threading.Event, error_counter: SharedCounter) -> list[ExecutionRecord]`
  - Loop while not stopped and duration not exceeded:
    - Check if `error_counter > max_errors`, set stop_event if so
    - Select random query
    - Generate parameters
    - Format SQL with `sql.format(**params)` → `executed_sql`
    - Generate unique `query_id = f"{query_name}_{uuid.uuid4()}"`
    - Record `started_at`
    - Try executing with `client.execute(executed_sql, settings={"query_id": query_id})`
    - Handle `httpx.ReadTimeout` → mark as timeout error
    - Handle other exceptions → mark as error
    - Record `finished_at`, calculate `duration_ms`
    - Create `ExecutionRecord`
    - Sleep `think_time_ms` if configured
  - Return list of ExecutionRecords

- [ ] Implement `run_workload(config: BenchmarkConfig, project_root: Path, variant_root: Path) -> dict`
  - Load queries (explicit or auto-discover)
  - Build weighted pool
  - Create workload-specific httpx client with `query_timeout_seconds`
  - Create ClickHouseClient with workload client
  - Run warmup phase (single-threaded)
  - Record `workload_start_epoch_ms = time.time() * 1000`
  - Create ThreadPoolExecutor with `concurrency` workers
  - Launch worker threads
  - Collect results from all workers
  - Record `workload_end_epoch_ms = time.time() * 1000`
  - Calculate `workload_elapsed_secs`
  - Return dict with `records`, timing metadata

---

### 9. Metrics Collector

**File:** `harness/metrics_collector.py`

- [ ] Implement `collect_query_log_metrics(config: BenchmarkConfig, client: ClickHouseClient, execution_records: list[ExecutionRecord], start_time: datetime, end_time: datetime) -> dict`

- [ ] Sleep for `query_log_wait_seconds`

- [ ] Extract all query_ids from execution_records

- [ ] Query `system.query_log`:
  - Filter: `type = 'QueryFinish'`
  - Filter: `query_id IN (...)`
  - Filter: `event_time >= start_time AND event_time <= end_time`
  - Select: `query_id`, `query_duration_ms`, `read_rows`, `read_bytes`, `result_rows`, `result_bytes`, `memory_usage`

- [ ] Build mapping: `query_id -> metrics dict`

- [ ] Check for mismatches:
  - If fewer entries than executions: log warning
  - If more entries than executions: log warning about duplicates, deduplicate by taking latest

- [ ] Return metrics mapping

---

### 10. Reporter

**File:** `harness/reporter.py`

- [ ] Implement `generate_reports(config: BenchmarkConfig, execution_records: list[ExecutionRecord], query_log_metrics: dict, workload_metadata: dict, project_root: Path)`

- [ ] Group execution_records by `query_name`

- [ ] For each query, calculate:
  - `count` = total executions
  - `errors` = count where `success=False`
  - `error_rate = errors / count`
  - `qps = count / workload_elapsed_secs`
  - `p50_ms`, `p95_ms`, `p99_ms` from `duration_ms` (use pandas.quantile or numpy.percentile)
  - `avg_read_rows`, `avg_read_bytes`, `avg_memory_usage` from query_log_metrics where available

- [ ] Generate CSV:
  - Prepend metadata as comments:
    - `# workload_start_epoch_ms: ...`
    - `# workload_end_epoch_ms: ...`
    - `# workload_elapsed_secs: ...`
    - `# project: ...`
    - `# variant: ...`
  - Write header: `query_name,count,errors,error_rate,qps,p50_ms,p95_ms,p99_ms,avg_read_rows,avg_read_bytes,avg_memory_usage`
  - Write data rows

- [ ] Generate Markdown:
  - Metadata section with formatted timestamps, project, variant, concurrency
  - Table with query performance metrics
  - Summary section with totals

- [ ] Write files to `project_root/{output_csv}` and `project_root/{output_md}`

- [ ] Log output file paths

---

### 11. Comparator

**File:** `harness/comparator.py`

- [ ] Implement `compare_results(csv_a_path: str, csv_b_path: str, output_path: str)`

- [ ] Read both CSV files with pandas (skip comment rows)

- [ ] Join on `query_name`

- [ ] For each query, calculate:
  - `delta_p50 = ((b_p50 - a_p50) / a_p50) * 100` (handle division by zero)
  - `delta_p95 = ((b_p95 - a_p95) / a_p95) * 100`
  - `delta_qps = ((b_qps - a_qps) / a_qps) * 100`

- [ ] Handle edge cases:
  - If baseline is 0: mark as "N/A" or "+∞"
  - If query exists in only one variant: mark as "missing"

- [ ] Generate Markdown table:
  - Columns: Query, A p50, B p50, Δ p50, A QPS, B QPS, Δ QPS

- [ ] Write to output_path

---

### 12. Utils Module

**File:** `harness/utils.py`

- [ ] Implement `setup_logging(verbose: bool)`
  - Configure logging level (DEBUG if verbose, INFO otherwise)
  - Set format with timestamps
  - Configure handler to stdout

- [ ] Implement `format_duration(ms: float) -> str`
  - Convert milliseconds to human-readable (e.g., "1.2s", "45ms")

- [ ] Implement `format_bytes(bytes: int) -> str`
  - Convert to KB/MB/GB as appropriate

---

### 13. CLI

**File:** `harness/cli.py`

- [ ] Use `argparse` to define CLI

- [ ] Global arguments:
  - `--config <path>` (required for most commands)
  - `--verbose` (flag)
  - `--dry-run` (flag, for full-run only)

- [ ] Implement `validate` command:
  - Load config
  - Run all validation checks
  - Test ClickHouse connectivity
  - Exit 0 if all pass, exit 1 if any fail

- [ ] Implement `init-db` command:
  - Load config
  - Create default ClickHouse client (with `timeout_seconds`)
  - Run schema_loader.apply_schema()
  - Exit with appropriate code

- [ ] Implement `load-data` command:
  - Load config
  - Create default ClickHouse client
  - Run data_loader.load_data()
  - Exit with appropriate code

- [ ] Implement `run-workload` command:
  - Load config
  - Create default ClickHouse client (for metrics collection)
  - Run workload_runner.run_workload() (creates its own workload client)
  - Collect metrics with metrics_collector
  - Generate reports with reporter
  - Exit with appropriate code

- [ ] Implement `full-run` command:
  - If `--dry-run`: run validate only
  - Else:
    - Run validate
    - If `schema.fresh=True`: run init-db
    - Run load-data
    - Run run-workload
  - Exit with appropriate code

- [ ] Implement `compare` command:
  - Arguments: `csv_a`, `csv_b`, `--output <path>`
  - Run comparator.compare_results()
  - Exit with appropriate code

- [ ] Add main entrypoint for `python -m harness.cli`

---

### 14. Example Project Setup

**Directory:** `projects/default/`

- [ ] Create `configs/example_basic.yml` with minimal valid config
- [ ] Create `configs/example_weighted.yml` showing query weights
- [ ] Create `configs/example_params.yml` showing parameterization
- [ ] Create `variants/default/schemas/001_create_tables.sql` with example schema
- [ ] Create `variants/default/data/sample.csv` with small test dataset
- [ ] Create `workloads/baseline/q01_simple.sql` with example query
- [ ] Create empty `results/.gitkeep`

---

### 15. Testing

**File:** `tests/test_config.py`

- [ ] Test config loading with valid YAML
- [ ] Test config validation failures (missing files, invalid values)
- [ ] Test path resolution

**File:** `tests/test_workload_runner.py`

- [ ] Test query discovery (explicit and auto modes)
- [ ] Test weighted pool building
- [ ] Test ExecutionRecord creation

**File:** `tests/test_reporter.py`

- [ ] Test percentile calculation
- [ ] Test CSV generation
- [ ] Test Markdown generation

**File:** `tests/integration_test.py` (optional)

- [ ] Spin up ClickHouse in Docker
- [ ] Run full-run with test data
- [ ] Verify CSV output contains expected metrics

---

### 16. Documentation

**File:** `README.md`

- [ ] Overview and features
- [ ] Installation instructions
- [ ] Quick start guide
- [ ] Configuration reference
- [ ] CLI command examples
- [ ] Project structure explanation

---

## Acceptance Criteria

Phase 1 is complete when:

- [ ] `python -m harness.cli validate --config projects/default/configs/example_basic.yml` succeeds
- [ ] `python -m harness.cli full-run --config projects/default/configs/example_basic.yml` produces valid CSV and Markdown in `results/`
- [ ] CSV contains correct columns with timing metadata
- [ ] QPS is calculated using actual measured time (not config duration)
- [ ] Warmup runs single-threaded before concurrent measurement
- [ ] Query timeouts work (queries exceeding `query_timeout_seconds` are aborted and marked failed)
- [ ] All error conditions produce clear messages and non-zero exit codes
- [ ] Auto-discovery mode works (can run workload without listing queries in config)
- [ ] Unit tests pass
- [ ] README provides clear usage instructions

---

## Implementation Order Recommendation

1. **Setup & Config** (Tasks 1-3): Foundation
2. **ClickHouse Client** (Task 4): Core connectivity
3. **Schema & Data** (Tasks 5-6): Basic loading
4. **Workload Runner** (Tasks 7-8): Core benchmarking
5. **Metrics & Reporting** (Tasks 9-10): Results generation
6. **CLI** (Task 13): User interface
7. **Examples & Docs** (Tasks 14, 16): Usability
8. **Comparator & Utils** (Tasks 11-12): Nice-to-haves
9. **Testing** (Task 15): Validation

This order ensures you can test each component as it's built, with early integration testing possible after task 8.
