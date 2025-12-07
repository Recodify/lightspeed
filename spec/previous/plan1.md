# ClickHouse Benchmarking Harness Specification

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
  pyproject.toml or requirements.txt
  README.md

  harness/
    __init__.py
    config.py           # parse YAML/JSON config
    clickhouse_client.py
    schema_loader.py
    data_loader.py
    workload_runner.py
    metrics_collector.py
    reporter.py
    cli.py

  configs/
    example_basic.yml

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
```

## Config Model

Define a single YAML config that describes:

```yaml
clickhouse:
  host: "localhost"
  port: 8123
  user: "default"
  password: ""
  database: "bench"

schema:
  # folder under schemas/
  variant: "variant_a"

data:
  # folder under data/variant/
  path: "variant_a"
  load:
    - table: "trades"
      file: "trades.csv"
      format: "CSV"
    - table: "prices"
      file: "prices.parquet"
      format: "Parquet"

workload:
  name: "baseline"
  # folder under workloads/
  path: "baseline"
  concurrency: 8
  duration_seconds: 120
  ramp_up_seconds: 10
  think_time_ms: 50  # optional sleep between queries per worker

metrics:
  # whether to query system.query_log
  use_query_log: true
  query_log_window_seconds: 300
  output_csv: "results/baseline_variant_a.csv"
  output_md:  "results/baseline_variant_a.md"
```

Implement `harness/config.py` to parse this and provide a typed object.

## Core Components

### clickhouse_client.py

Simple wrapper around HTTP interface using `requests` or `httpx`.

**Functions:**

```python
execute(sql: str, params: dict | None = None) -> list[dict]
execute_no_result(sql: str) -> None
```

Option to enable `log_queries=1` if not already set in server config.

### schema_loader.py

**Responsibilities:**

- Drop/recreate database if `--fresh` flag is passed
- Load all `.sql` files in `schemas/<variant>/` sorted by filename
- Execute each statement sequentially
- Log what ran

```python
def apply_schema(variant: str, client: ClickHouseClient, database: str, fresh: bool):
    # if fresh: DROP DATABASE IF EXISTS; CREATE DATABASE
    # then run each *.sql in schemas/variant
```

### data_loader.py

**Responsibilities:**

For each `data.load` entry in config:

- Build an `INSERT INTO table SELECT * FROM file(...)` style query or `INSERT INTO table FORMAT CSV` + stream file via HTTP
- Support at least CSV and Parquet
- Option to truncate tables before load when `--fresh` is set

Simplest approach:

```sql
INSERT INTO {table}
SELECT *
FROM file('{abs_path}', '{FORMAT}');
```

Handle large files by streaming where possible.

## Workload Runner

### Behavior

Simulate concurrent users hitting a set of queries repeatedly for N seconds.

**Spec:**

1. Read all `.sql` files in `workloads/<path>/` into memory
2. Each worker goroutine/thread:
   - Waits for optional ramp-up
   - Randomly picks a query from the list
   - Executes it
   - Records:
     - Start time
     - End time
     - Duration
     - Query name (filename)
     - Success/failure
3. Run for `duration_seconds`
4. Store raw per-execution metrics in memory, then dump to CSV

**Implementation detail:** Use `concurrent.futures.ThreadPoolExecutor` or `asyncio`. Threading is fine since ClickHouse is remote and IO bound.

### workload_runner.py

```python
run_workload(config, client) -> list[ExecutionRecord]
```

Where `ExecutionRecord` is:

```python
@dataclass
class ExecutionRecord:
    query_name: str
    started_at: datetime
    finished_at: datetime
    duration_ms: float
    success: bool
    error_message: str | None
```

## Metrics Collection via system.query_log

### metrics_collector.py

**Responsibilities:**

Query `system.query_log` for rows matching:

- `event_time` between start and end of workload ± guard band
- `query_kind = 'Select'`
- Optional `initial_user` or `client_name` tag to isolate harness traffic

**Extract fields:**

- `query`
- `query_duration_ms`
- `read_rows`
- `read_bytes`
- `result_rows`
- `result_bytes`
- `memory_usage`
- `ProfileEvents` summary if needed (maybe later)

```python
def fetch_query_log_metrics(client, since: datetime, until: datetime) -> list[dict]:
    # SELECT ... FROM system.query_log WHERE event_time >= since AND ...
```

Join this data with local `ExecutionRecords`, probably on normalized query text or an injected comment marker like:

```sql
-- harness_query: q01_latency
SELECT ...
```

So you can match query to `query_name`.

## Reporter

### reporter.py

**Requirements:**

Take:

- List of `ExecutionRecord`
- List of `query_log` rows

**Compute per-query stats:**

- p50/p95/p99 latency
- min/max
- count
- error count
- avg `read_rows`, `read_bytes`, `memory_usage` if available

**Emit:**

- CSV file with per-query metrics
- Markdown table for quick drop into Confluence/Notion

**Example CSV columns:**

```
query_name,p50_ms,p95_ms,p99_ms,count,errors,avg_read_rows,avg_read_bytes,avg_memory_usage
```

**Example Markdown:**

```markdown
| Query       | p50 (ms) | p95 (ms) | p99 (ms) | Count | Errors | Avg rows read | Avg bytes read |
|-------------|----------|----------|----------|-------|--------|---------------|----------------|
| q01_latency | 12       | 25       | 40       | 1000  | 0      | 1.2M          | 45MB           |
```

## CLI Entrypoint

### cli.py

Implement a simple CLI using `argparse`.

**Commands:**

**`init-db`**
- `--config configs/example_basic.yml`
- Applies schema and optionally drops database

**`load-data`**
- Uses `data_loader` and config

**`run-workload`**
- Runs the workload
- Captures start/end timestamps
- Runs `metrics_collector`
- Writes CSV and Markdown via `reporter`

**`full-run`**
- `init-db` (optional `--fresh`)
- `load-data`
- `run-workload`

**Usage:**

```bash
python -m harness.cli full-run --config configs/example_basic.yml --fresh
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