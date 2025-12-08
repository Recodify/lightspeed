# ClickHouse Benchmarking Harness

A Python-based benchmarking harness for ClickHouse that enables systematic performance testing across different schema designs. Run repeatable benchmarks, compare variants, and make data-driven schema decisions with comprehensive performance metrics.

## Why This Tool Exists

ClickHouse offers unprecedented flexibility in schema design compared to traditional databases. For any given use case, you might choose between:

- **Table engines**: MergeTree, ReplacingMergeTree, SummingMergeTree, AggregatingMergeTree, and more
- **Indexing strategies**: Primary keys, secondary indexes, bloom filters, set indexes
- **Partitioning schemes**: By time, by key, by hash, or no partitioning
- **Compression codecs**: LZ4, ZSTD, Delta, DoubleDelta, Gorilla, and combinations
- **Materialized views**: Pre-aggregations vs query-time aggregation
- **Data types**: Specialized types like LowCardinality, Array, Map, Nested
- **Settings**: Hundreds of tunables affecting merge behavior, memory usage, and parallelism

This flexibility is powerful but creates a problem: **How do you know which design performs best for your workload?**

This harness solves that problem by making it trivial to:
1. Define multiple schema variants
2. Run identical workloads against each
3. Compare performance with statistical rigor
4. Make informed decisions based on real data

## Features

- **Multi-variant benchmarking**: Test multiple schema designs with identical workloads
- **YAML-driven configuration**: Define everything in code-reviewed, version-controlled configs
- **Comprehensive metrics**: Latency percentiles (p50/p95/p99), throughput (QPS), resource usage (memory, rows/bytes read)
- **Multiple output formats**: JSON (canonical), CSV, and Markdown reports
- **N-way comparison**: Compare all variants side-by-side with rankings and deltas
- **Flexible data loading**: CSV, Parquet, and other formats via HTTP streaming
- **Realistic workloads**: Concurrency, ramp-up, warmup, weighted queries, parameterized queries
- **Schema lifecycle management**: Fresh databases, migrations, layered project + variant schemas
- **Repeatable runs**: Named runs with consistent output organization

## Quick Start

### Prerequisites

- Python 3.10+
- ClickHouse server accessible over HTTP (default: localhost:8123)
- User permissions to create databases/tables and read from system.query_log

### Installation

```bash
git clone <repository-url>
cd lightspeed
# With make (recommended)
make install

# Or manually
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .

# Helper: run commands inside the venv without activating your shell
./activate.sh python -m harness.cli --help
```

### Minimal Example

Create a minimal config file at `projects/myproject/configs/simple.yml`:

```yaml
project: "myproject"
variant: "baseline"

clickhouse:
  host: "localhost"
  port: 8123
  user: "default"
  password: ""
  database: "benchmark"

schema:
  fresh: true  # Drop and recreate database

data:
  load_method: "http"
  load: []  # No data for this minimal example

workload:
  name: "simple"
  path: "simple"
  queries:
    - file: "query.sql"
  concurrency: 1
  duration_seconds: 10

metrics:
  use_query_log: true
```

Create a schema at `projects/myproject/variants/baseline/schemas/001_create_table.sql`:

```sql
CREATE TABLE events (
    timestamp DateTime,
    user_id UInt64,
    event_type String
) ENGINE = MergeTree()
ORDER BY (timestamp, user_id);
```

Create a query at `projects/myproject/workloads/simple/query.sql`:

```sql
SELECT count() FROM events WHERE timestamp > now() - INTERVAL 1 DAY;
```

Run the benchmark:

```bash
python -m harness.cli full-run --config projects/myproject/configs/simple.yml
```

Results will be saved to `projects/myproject/results/<config>/<run>/baseline/`.

## Project Structure

```
lightspeed/
├── harness/                    # Core benchmarking engine
│   ├── cli.py                  # Command-line interface
│   ├── config.py               # Configuration parsing and validation
│   ├── clickhouse_client.py   # ClickHouse HTTP client
│   ├── schema_loader.py        # Schema application (SQL files)
│   ├── data_loader.py          # Data loading (CSV, Parquet, etc.)
│   ├── workload_runner.py      # Concurrent query execution
│   ├── metrics_collector.py   # Performance metrics from query_log
│   ├── reporter.py             # JSON/CSV/Markdown report generation
│   ├── comparator.py           # Multi-variant comparison reports
│   └── parameter_generator.py # Query parameterization
│
└── projects/                   # Your benchmarking projects
    └── <project_name>/
        ├── configs/            # Benchmark configurations (YAML)
        │   └── example.yml
        │
        ├── schemas/            # Project-wide schemas (shared across variants)
        │   └── 001_dimensions.sql
        │
        ├── data/               # Project-wide data files (shared across variants)
        │   └── dimensions.csv
        │
        ├── workloads/          # Query workloads
        │   ├── baseline/
        │   │   ├── q01_point_lookup.sql
        │   │   └── q02_aggregation.sql
        │   └── heavy/
        │       └── q01_full_scan.sql
        │
        ├── variants/           # Schema variants to benchmark
        │   ├── baseline/       # Example: standard MergeTree
        │   │   ├── schemas/
        │   │   │   ├── 001_create_events.sql
        │   │   │   └── 002_indexes.sql
        │   │   └── data/
        │   │       └── events.csv
        │   │
        │   ├── optimized/      # Example: with secondary indexes
        │   │   └── schemas/
        │   │       ├── 001_create_events.sql
        │   │       └── 002_indexes.sql
        │   │
        │   └── partitioned/    # Example: with partitioning
        │       └── schemas/
        │           └── 001_create_events.sql
        │
        └── results/            # Benchmark outputs
            └── <config>/
                └── <run>/
                    ├── baseline/
                    │   ├── results.json
                    │   ├── results.csv
                    │   ├── results.md
                    │   └── data_load.json
                    ├── optimized/
                    │   └── results.json
                    └── comparison_all_variants.md
```

### File Organization Principles

**Project-level files** (`schemas/`, `data/`, `workloads/`):
- Shared across all variants
- Use for dimension tables, lookup data, common queries
- Applied first, before variant-specific files

**Variant-level files** (`variants/<name>/schemas/`, `variants/<name>/data/`):
- Specific to each variant
- Contains the schema/data that differs between variants
- Applied after project-level files

**Result organization**: `projects/<project>/results/<config>/<run>/<variant>/`
- `<config>`: Configuration file name (without .yml)
- `<run>`: Named run or auto-generated name (e.g., "bold-penguin")
- `<variant>`: Variant name

## Configuration Reference

### Complete Example

```yaml
project: "default"
variant: "baseline"

clickhouse:
  host: "localhost"
  port: 8123
  user: "default"
  password: ""
  database: "benchmark"
  connection_pool_size: 20
  timeout_seconds: 300

schema:
  fresh: true
  fail_on_error: true

data:
  load_method: "http"
  truncate_before_load: true
  load:
    - table: "events"
      file: "events.csv"
      format: "CSVWithNames"
    - table: "metrics"
      file: "metrics.parquet"
      format: "Parquet"

workload:
  name: "baseline"
  path: "baseline"
  queries:
    - file: "q01_point_lookup.sql"
      weight: 10
    - file: "q02_aggregation.sql"
      weight: 5
    - file: "q03_range_scan.sql"
      weight: 1
  concurrency: 8
  duration_seconds: 120
  ramp_up_seconds: 10
  warmup_queries: 100
  think_time_ms: 50
  max_errors: 100
  query_timeout_seconds: 60

metrics:
  use_query_log: true
  query_log_wait_seconds: 10
```

### Section: `clickhouse`

Connection and client configuration.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `host` | string | Yes | - | ClickHouse server hostname or IP |
| `port` | integer | Yes | - | HTTP port (usually 8123) |
| `user` | string | Yes | - | Database user |
| `password` | string | No | `""` | User password |
| `database` | string | Yes | - | Target database name |
| `connection_pool_size` | integer | No | 10 | HTTP connection pool size |
| `timeout_seconds` | integer | No | 300 | Timeout for schema/data/metrics operations |

### Section: `schema`

Schema loading behavior.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `fresh` | boolean | No | false | Drop and recreate database before applying schemas |
| `fail_on_error` | boolean | No | true | Abort if any schema file fails to execute |

**Schema file order**: Files are executed in lexicographic order. Use numeric prefixes (e.g., `001_`, `002_`) to control execution order.

**Schema layering**: Project-level schemas are applied first, then variant-level schemas.

### Section: `data`

Data loading configuration.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `load_method` | string | Yes | - | Loading method (currently only `"http"` supported) |
| `truncate_before_load` | boolean | No | false | TRUNCATE tables before loading data |
| `load` | array | Yes | - | List of table/file mappings |
| `load[].table` | string | Yes | - | Target table name |
| `load[].file` | string | Yes | - | Data file name (relative to `data/` or `variants/<variant>/data/`) |
| `load[].format` | string | Yes | - | ClickHouse format (e.g., `CSVWithNames`, `Parquet`, `JSONEachRow`) |

**Data file resolution**: Files are searched in variant-level `data/` first, then project-level `data/`.

**Data loading metrics**: Load performance (throughput, duration) is captured in `data_load.json` and `data_load.csv`.

### Section: `workload`

Query workload configuration.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | Workload name (for reporting) |
| `path` | string | Yes | - | Workload directory name under `workloads/` |
| `queries` | array | Yes | - | List of query definitions |
| `queries[].file` | string | Yes | - | Query filename (relative to `workloads/<path>/`) |
| `queries[].weight` | integer | No | 1 | Query selection weight (higher = more frequent) |
| `queries[].params` | object | No | {} | Query parameters (see Parameterized Queries) |
| `concurrency` | integer | Yes | - | Number of concurrent clients |
| `duration_seconds` | integer | Yes | - | Benchmark duration (excludes warmup and ramp-up) |
| `ramp_up_seconds` | integer | No | 0 | Gradual concurrency ramp-up period |
| `warmup_queries` | integer | No | 0 | Number of warmup queries to execute (excluded from metrics) |
| `think_time_ms` | integer | No | 0 | Delay between queries per client (milliseconds) |
| `max_errors` | integer | No | 100 | Abort benchmark after this many errors |
| `query_timeout_seconds` | integer | No | 60 | Per-query timeout |

**Query selection**: Queries are randomly selected based on weights. Weight of 10 means 10x more likely to be selected than weight of 1.

**Query file resolution**: Files are searched in variant-level `workloads/<path>/` first, then project-level `workloads/<path>/`.

**Parameterized queries**: Use `{param_name}` in SQL. Provide `params` with generator config:

```yaml
queries:
  - file: "lookup.sql"
    params:
      user_id:
        type: "random_int"
        min: 1
        max: 1000000
```

See `parameter_generator.py` for supported parameter types.

### Section: `metrics`

Metrics collection configuration.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `use_query_log` | boolean | Yes | - | Collect metrics from system.query_log |
| `query_log_wait_seconds` | integer | No | 10 | Wait time after workload for query_log flush |

**Note**: Legacy `output_csv`, `output_md`, and `data_output_csv` fields are ignored. Output paths are automatically determined based on the results directory structure.

### Multi-Variant Configuration

To benchmark multiple variants in a single run, define them in your config:

```yaml
variants:
  baseline:
    description: "Standard MergeTree"

  optimized:
    description: "With secondary indexes"
    # Variant-specific overrides can go here

  partitioned:
    description: "Partitioned by day"
```

Run all variants:

```bash
python -m harness.cli full-run --config projects/myproject/configs/example.yml
```

Run a specific variant:

```bash
python -m harness.cli full-run --config projects/myproject/configs/example.yml --variant optimized
```

## CLI Commands

### `full-run`

Run complete benchmark: schema, data, workload, and reporting.

```bash
python -m harness.cli full-run --config <path> [--variant <name>] [--run-name <name>] [--verbose]
```

**Arguments**:
- `--config`: Path to YAML configuration file (required)
- `--variant`: Run specific variant only (default: all variants defined in config)
- `--run-name`: Custom run name (default: auto-generated memorable name like "brave-penguin")
- `--verbose`: Enable DEBUG logging

**Behavior**:
1. Validates configuration and connectivity
2. For each variant:
   - Applies schema (project-level + variant-level)
   - Loads data
   - Runs workload
   - Collects metrics
   - Generates reports (JSON, CSV, MD)
3. Generates N-way comparison report if multiple variants ran

**Output**: `projects/<project>/results/<config>/<run>/<variant>/`

### `validate`

Validate configuration and connectivity without running benchmarks.

```bash
python -m harness.cli validate --config <path> [--variant <name>] [--verbose]
```

**Checks**:
- YAML syntax and required fields
- ClickHouse connectivity
- Schema files exist and are readable
- Data files exist and are readable
- Query files exist and are readable

### `init-db`

Apply schemas only (no data loading or workload execution).

```bash
python -m harness.cli init-db --config <path> [--variant <name>] [--verbose]
```

**Use cases**:
- Verify schema syntax
- Set up database for manual testing
- Debug schema application issues

### `load-data`

Load data only (assumes schema already exists).

```bash
python -m harness.cli load-data --config <path> [--variant <name>] [--verbose]
```

**Use cases**:
- Reload data without recreating schema
- Test data loading performance
- Debug data loading issues

### `run-workload`

Run workload only (assumes schema and data already exist).

```bash
python -m harness.cli run-workload --config <path> [--variant <name>] [--run-name <name>] [--verbose]
```

**Use cases**:
- Re-run workload with same schema/data
- Test different workload configurations
- Quick iteration on query performance

### `compare`

Generate comparison report between two result sets.

```bash
python -m harness.cli compare <path_a> <path_b> --output <output_path>
```

**Arguments**:
- `<path_a>`: First results file (JSON or CSV) or directory
- `<path_b>`: Second results file (JSON or CSV) or directory
- `--output`: Output path for comparison report (Markdown)

**Note**: `full-run` automatically generates N-way comparison reports when multiple variants are run.

## Output Formats

All benchmarks generate multiple output formats for different use cases.

### JSON (Canonical Format)

`results.json` - Machine-readable workload metrics:

```json
{
  "schema_version": "1.0",
  "metadata": {
    "project": "myproject",
    "variant": "baseline",
    "workload": "baseline",
    "config_name": "example",
    "run_name": "bold-penguin",
    "timestamp": "2025-12-07T23:08:42.123456",
    "duration_seconds": 120,
    "concurrency": 8
  },
  "queries": [
    {
      "query_name": "q01_point_lookup.sql",
      "count": 15234,
      "errors": 0,
      "error_rate": 0.0,
      "qps": 127.12,
      "p50_ms": 8.52,
      "p95_ms": 14.58,
      "p99_ms": 18.34,
      "avg_query_duration_ms": 9.23,
      "avg_read_rows": 1245,
      "avg_read_bytes": 52341,
      "avg_memory_usage": 1048576
    }
  ],
  "summary": {
    "total_queries": 15234,
    "total_errors": 0,
    "overall_qps": 127.12
  }
}
```

`data_load.json` - Data loading metrics:

```json
{
  "schema_version": "1.0",
  "metadata": {
    "project": "myproject",
    "variant": "baseline",
    "load_method": "http"
  },
  "totals": {
    "files_loaded": 2,
    "total_rows": 1000000,
    "total_bytes": 52428800,
    "total_duration_seconds": 12.34,
    "overall_throughput_mb_per_sec": 4.05
  },
  "ingest": [
    {
      "table": "events",
      "file": "events.csv",
      "format": "CSVWithNames",
      "rows": 900000,
      "bytes": 47185920,
      "duration_seconds": 11.23,
      "throughput_mb_per_sec": 4.01
    }
  ]
}
```

### CSV Format

`results.csv` - Tabular query metrics with metadata as comments:

```csv
# project: myproject
# variant: baseline
# workload: baseline
# timestamp: 2025-12-07T23:08:42
query_name,count,errors,error_rate,qps,p50_ms,p95_ms,p99_ms,avg_query_duration_ms,avg_read_rows,avg_read_bytes,avg_memory_usage
q01_point_lookup.sql,15234,0,0.0,127.12,8.52,14.58,18.34,9.23,1245,52341,1048576
```

`data_load.csv` - Per-file load metrics:

```csv
# project: myproject
# variant: baseline
table,file,format,rows,bytes,duration_seconds,throughput_mb_per_sec
events,events.csv,CSVWithNames,900000,47185920,11.23,4.01
```

### Markdown Format

`results.md` - Human-readable formatted report with tables and summary statistics.

### Comparison Reports

`comparison_all_variants.md` - N-way comparison across all variants (generated automatically by `full-run`):

```markdown
# N-Way Benchmark Comparison

**Variants Compared**: 3 variants

| Variant | Results Path |
|---------|--------------|
| baseline | `/path/to/results/baseline/results.json` |
| optimized | `/path/to/results/optimized/results.json` |
| partitioned | `/path/to/results/partitioned/results.json` |

## Executive Summary

**Overall Winner**: optimized

**Win Distribution** (based on p50 latency):
- optimized: 8 queries (80.0%)
- baseline: 2 queries (20.0%)
- partitioned: 0 queries (0.0%)

## Section 1: Side-by-Side Performance Comparison

### Query: q01_point_lookup.sql

| Metric | baseline | optimized | partitioned | Best | Δ (baseline) | Δ (optimized) | Δ (partitioned) |
|--------|----------|-----------|-------------|------|--------------|---------------|-----------------|
| p50 (ms) | 8.52 | 6.23 | 9.12 | optimized | +36.8% | - | +46.4% |
| p95 (ms) | 14.58 | 11.34 | 15.67 | optimized | +28.6% | - | +38.2% |
| QPS | 429.24 | 587.45 | 401.23 | optimized | -26.9% | - | -31.7% |

## Section 2: Rankings

### Ranking by p50 Latency (Average Across All Queries)

| Rank | Variant | Avg p50 Latency (ms) | Relative to Best |
|------|---------|----------------------|------------------|
| 1 | optimized | 6.23 | - |
| 2 | baseline | 8.52 | +36.8% |
| 3 | partitioned | 9.12 | +46.4% |
```

## Comparing Results

When you run `full-run` with multiple variants, an N-way comparison report is automatically generated at:

```
projects/<project>/results/<config>/<run>/comparison_all_variants.md
```

This report includes:
- Side-by-side tables showing all variants for each query
- Rankings by p50, p95, and QPS
- Percentage deltas relative to best performer
- Executive summary with overall winner

To manually compare specific results:

```bash
python -m harness.cli compare \
  projects/myproject/results/example/run1/baseline/results.json \
  projects/myproject/results/example/run2/baseline/results.json \
  --output comparison.md
```

The comparison accepts:
- JSON files (`results.json`)
- CSV files (`results.csv`)
- Directories (will find `results.json` automatically)

## Creating a New Project

1. **Create project directory structure**:

```bash
mkdir -p projects/myproject/{configs,schemas,data,workloads/baseline,variants/baseline/schemas,results}
```

2. **Create a minimal config** at `projects/myproject/configs/example.yml`:

```yaml
project: "myproject"
variant: "baseline"

clickhouse:
  host: "localhost"
  port: 8123
  user: "default"
  password: ""
  database: "myproject_bench"

schema:
  fresh: true

data:
  load_method: "http"
  load: []

workload:
  name: "baseline"
  path: "baseline"
  queries:
    - file: "query.sql"
  concurrency: 4
  duration_seconds: 60

metrics:
  use_query_log: true
```

3. **Add schema** at `projects/myproject/variants/baseline/schemas/001_create_table.sql`:

```sql
CREATE TABLE events (
    timestamp DateTime,
    user_id UInt64,
    event_type String
) ENGINE = MergeTree()
ORDER BY (timestamp, user_id);
```

4. **Add query** at `projects/myproject/workloads/baseline/query.sql`:

```sql
SELECT count() FROM events WHERE timestamp > now() - INTERVAL 1 HOUR;
```

5. **Run the benchmark**:

```bash
python -m harness.cli full-run --config projects/myproject/configs/example.yml
```

6. **View results**:

```bash
cat projects/myproject/results/example/*/baseline/results.md
```

## Best Practices

### Schema Variant Design

When creating schema variants to test:

1. **Change one thing at a time** - Isolate variables to understand impact
2. **Keep queries identical** - Use project-level workloads when possible
3. **Use descriptive variant names** - `baseline`, `with_bloom_filter`, `partitioned_by_day`
4. **Document variants** - Add comments in schema files explaining the design choice

### Workload Design

For realistic benchmarks:

1. **Use production query patterns** - Extract real queries from your application
2. **Weight queries appropriately** - Match production frequency distribution
3. **Include warmup** - Let ClickHouse populate caches naturally
4. **Run long enough** - 2-5 minutes minimum for stable metrics
5. **Use realistic concurrency** - Match expected production load

### Data Loading

1. **Use representative data** - Real or realistic synthetic data
2. **Match production scale** - Or scale proportionally
3. **Consider data distribution** - Cardinality, skew, and patterns matter
4. **Seed data consistently** - For reproducible benchmarks

### Interpreting Results

1. **Look at percentiles, not just averages** - p95 and p99 matter for user experience
2. **Consider throughput** - QPS shows overall capacity
3. **Check resource usage** - Memory and bytes read indicate efficiency
4. **Run multiple times** - Verify consistency before making decisions
5. **Compare like-to-like** - Same data, same workload, same hardware

## Troubleshooting

### ClickHouse Connection Issues

```
Error: Could not connect to ClickHouse at localhost:8123
```

**Solutions**:
- Verify ClickHouse is running: `curl http://localhost:8123`
- Check host/port in config
- Verify user/password credentials
- Check firewall rules

### Schema Application Failures

```
Error: Schema file failed to execute: 001_create_table.sql
```

**Solutions**:
- Check SQL syntax in schema file
- Verify table doesn't already exist (or use `fresh: true`)
- Check user has CREATE permissions
- Review ClickHouse error message in logs (`--verbose`)

### Data Loading Failures

```
Error: Data load failed for table 'events'
```

**Solutions**:
- Verify table exists (run `init-db` first)
- Check data file format matches declared format
- Verify file encoding (UTF-8 expected)
- Check for data type mismatches
- Use `--verbose` to see detailed error messages

### Metrics Collection Issues

```
Warning: No metrics found in query_log
```

**Solutions**:
- Ensure `system.query_log` is enabled in ClickHouse config
- Increase `query_log_wait_seconds` in config
- Check user has SELECT permission on system.query_log
- Verify queries are actually executing (check for errors)

## Advanced Topics

### Custom Parameter Generators

Create custom parameter types by extending `parameter_generator.py`:

```python
@parameter_generator("custom_type")
def generate_custom(config: dict) -> Any:
    # Your generator logic
    return generated_value
```

### Integration with CI/CD

Run regression benchmarks in CI:

```bash
# Run benchmark
python -m harness.cli full-run --config projects/myproject/configs/ci.yml --run-name "commit-${GIT_SHA}"

# Check for regressions
python scripts/check_regression.py \
  projects/myproject/results/ci/commit-${PREV_SHA}/baseline/results.json \
  projects/myproject/results/ci/commit-${GIT_SHA}/baseline/results.json \
  --threshold 5  # Fail if p95 regressed by >5%
```

### Distributed ClickHouse

For distributed tables, adjust your schema and queries accordingly:

```sql
-- Schema variant: distributed
CREATE TABLE events_local ON CLUSTER cluster (
    ...
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/events', '{replica}')
...;

CREATE TABLE events ON CLUSTER cluster AS events_local
ENGINE = Distributed(cluster, currentDatabase(), events_local, rand());
```

Query against the distributed table in your workload.

## Contributing

Contributions welcome. Please:

1. Follow existing code style
2. Add tests for new features
3. Update documentation
4. Submit pull requests with clear descriptions

## License

[Add your license here]
