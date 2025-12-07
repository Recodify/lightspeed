# ClickHouse Benchmarking Harness

This Python-based benchmarking harness for ClickHouse allows users to run repeatable benchmarks across various schema variants. The tool supports automatic schema and data setup, as well as rich, configurable reporting. It includes functionality to handle multiple projects and variants for comprehensive performance analysis.

## Highlights

**YAML-driven configuration**: Easily define variants with per-variant overrides, such as different schemas, data files, workloads, and ClickHouse settings.

**Schema/application lifecycle**: Option to create fresh databases, manage project + variant schema layers, and apply migrations.

**Flexible data loading**: Supports CSV, Parquet, and other formats, using efficient HTTP insert streams.

**Workload execution**: Allows concurrency, ramp-up, warmup, parameterized queries, and weighted query selection for realistic performance testing.

**Rich reporting**: Outputs performance metrics in CSV and Markdown format, with built-in comparison tools for regression testing.

## Repository Layout

```
ch-harness/
  pyproject.toml           # Project dependencies
  README.md                # This document

  harness/
    __init__.py
    config.py              # Configuration handling
    clickhouse_client.py   # Interfacing with ClickHouse
    schema_loader.py       # Schema creation and application
    data_loader.py         # Data loading via HTTP insert
    workload_runner.py     # Executes workload and manages concurrency
    metrics_collector.py   # Collects performance metrics
    reporter.py            # Generates output reports
    comparator.py          # Compares benchmark results
    parameter_generator.py # Handles query parameters
    utils.py               # Utility functions
    exceptions.py          # Custom exceptions for error handling
    cli.py                 # Command-line interface

  projects/
    <project_name>/
      configs/              # Benchmark configuration YAMLs
        example_basic.yml
        example_weighted.yml
        example_params.yml

      schemas/              # Project-wide schema files (optional)
      data/                 # Project-wide data files (optional)
      workloads/            # Project-wide workload queries
        baseline/
          q01_latency.sql
          q02_throughput.sql
        heavy/
          q01_full_scan.sql

      variants/             # Variant-specific overrides (schemas, data, etc.)
        <variant_name>/
          schemas/
            001_create_tables.sql
            002_indexes.sql
          data/
            trades.csv
            prices.parquet
          workloads/
            baseline/
              q01_latency.sql

      results/              # Benchmark result output files
        .gitkeep
```

## Prerequisites

- Python 3.10+
- A ClickHouse server accessible over HTTP (localhost:8123 by default)
- Ensure the configured user has permission to create databases/tables and read from system.query_log

## Setup

To get started, first set up the environment and install the necessary dependencies.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Running the Sample Project

1. **Set up ClickHouse**: Ensure your ClickHouse server is running and update the credentials in `projects/default/configs/example_basic.yml` if needed.

2. **Run a full benchmark** (including schema, data, and workload for all configured variants):

```bash
python -m harness.cli full-run --config projects/default/configs/example_basic.yml
```

To run only a specific variant, add `--variant variant1`.

Use `--verbose` for debug logs.

Reports will be saved in `projects/default/results/` with variant-specific filenames (e.g., `results_default.csv`, `results_variant1.md`).

## Common Commands

**Validate connectivity and files:**

```bash
python -m harness.cli validate --config projects/default/configs/example_basic.yml
```

**Apply schema only:**

```bash
python -m harness.cli init-db --config projects/default/configs/example_basic.yml
```

**Load data only:**

```bash
python -m harness.cli load-data --config projects/default/configs/example_basic.yml
```

**Run workload only:**

```bash
python -m harness.cli run-workload --config projects/default/configs/example_basic.yml
```

## Configuration Essentials

Each config (`projects/<project>/configs/*.yml`) defines:

- **project**: The project directory name under `projects/`
- **variant**: Defines which variant to run, overriding default configurations for specific tests
- **clickhouse**: Connection details (host, port, user, password, database, etc.)
- **schema**: Schema settings (e.g., `fresh` to drop and recreate the database)
- **data**: Data load settings (e.g., `load_method` for inserting data via HTTP)
- **workload**: Defines the workload with concurrency, duration, query parameters, and query selection
- **metrics**: Defines which metrics to collect, and where to output them (workload CSV/MD plus a data-load CSV)

### Example configuration file:

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
  timeout_seconds: 300  # Timeout for schema, data, and metrics operations

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
  query_timeout_seconds: 60

metrics:
  use_query_log: true
  query_log_wait_seconds: 10
  output_csv: "results/baseline_variant_a.csv"
  output_md:  "results/baseline_variant_a.md"
  data_output_csv: "results/baseline_data_load.csv"
```

## Comparing Results

To compare two sets of results (CSV), run the following command:

```bash
python -m harness.cli compare \
  projects/default/results/results_default.csv \
  projects/default/results/results_variant1.csv \
  --output projects/default/results/comparison.md
```

## Creating a New Project

To create a new project:

1. Copy the `projects/default` directory to a new project directory: `projects/<your_project>`
2. Add your schemas, data, and workloads to the corresponding directories
3. Create a config for your project under `projects/<your_project>/configs/`
4. Run the full benchmark using:

```bash
python -m harness.cli full-run --config projects/<your_project>/configs/<your_config>.yml
```

## Multi-Variant Support

Variants are the core concept of this benchmarking harness. A variant represents a different schema design (or data configuration) that you want to benchmark. The harness allows you to compare performance across multiple schema variants by running the same workload against each one.

For example, you might have variants for:
- Different indexing strategies
- Alternative table engines (MergeTree vs ReplacingMergeTree)
- Varied partitioning schemes
- Different compression codecs

### Project vs Variant Files

The harness uses a layered approach to compose the final configuration:

- **Project-level files** (`projects/<project>/schemas/`, `projects/<project>/data/`): Shared across all variants. Use these for dimensions, dictionaries, lookup tables, existing production seeders, and any variant-invariant data or schema elements.

- **Variant-level files** (`projects/<project>/variants/<variant>/schemas/`, `projects/<project>/variants/<variant>/data/`): Specific to each variant. Use these for the schema and data that differ between variants.

The final configuration for a variant = project files + variant files.

By default, running a full benchmark executes all defined variants sequentially. When running a full benchmark (`full-run`), you can specify a `--variant` flag to run only that variant.

### Example variant configuration:

```yaml
variants:
  default:
    description: "Baseline configuration"
    data:
      load:
        - table: events
          file: events_1k.csv

  large:
    description: "Large dataset"
    data:
      load:
        - table: events
          file: events_1m.csv
```

To run a specific variant:

```bash
python -m harness.cli full-run --config projects/default/configs/example_basic.yml --variant large
```

## Conclusion

This ClickHouse Benchmarking Harness provides a flexible and scalable approach for performance testing across multiple variants and configurations. With clear isolation between variants and results, and automated reporting, this tool allows for streamlined benchmarking and comparative analysis.
