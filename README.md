# ClickHouse Benchmarking Harness

ClickHouse workload harness for running repeatable benchmarks with per-project variants, automatic schema/data setup, and rich reporting. The repo ships with a sample project under `projects/default` that you can clone for your own datasets and workloads.

## Highlights
- YAML-driven configuration with per-variant overrides (different schemas, data files, workloads, and ClickHouse settings).
- Schema/application lifecycle: optional fresh database creation, project + variant SQL schema layers.
- Data loading with CSV/Parquet/etc. via HTTP insert streams, including optional truncation.
- Workload runner with concurrency, ramp-up, warmup, parameterized queries, and weighted query selection.
- Metrics from `system.query_log` plus CSV and Markdown reports; built-in CSV comparison for regressions.

## Repository layout
- `harness/`: CLI, config validation, schema/data loaders, workload runner, metrics collector, reporter, comparator.
- `projects/<project>/configs/`: Benchmark configs (YAML).
- `projects/<project>/schemas/`: Project-wide schema SQL (optional).
- `projects/<project>/data/`: Project-wide data files (optional).
- `projects/<project>/workloads/<workload>/`: Project-wide queries.
- `projects/<project>/variants/<variant>/`: Variant-specific `schemas/`, `data/`, `workloads/`.
- `projects/<project>/results/`: Output CSV/Markdown reports per run.

## Prerequisites
- Python 3.10+
- Access to a ClickHouse server over HTTP (default `localhost:8123`); ensure the configured user can create databases/tables and read `system.query_log`.

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Running the sample project
1. Start/point a ClickHouse server and update credentials in `projects/default/configs/example_basic.yml` if needed.
2. Run a full benchmark (validate → schema → data → workload) for all configured variants:
   ```bash
   python -m harness.cli full-run --config projects/default/configs/example_basic.yml
   ```
   - Pass `--variant variant1` to run only that variant.
   - Add `--verbose` for debug logs.
3. Reports will land in `projects/default/results/` with variant suffixes (for example, `results_default.csv`, `results_variant1.md`).

Common commands (all accept `--verbose` and `--variant`):
- Validate connectivity and files:  
  `python -m harness.cli validate --config projects/default/configs/example_basic.yml`
- Apply schema only:  
  `python -m harness.cli init-db --config projects/default/configs/example_basic.yml`
- Load data only:  
  `python -m harness.cli load-data --config projects/default/configs/example_basic.yml`
- Run workload only (no schema/data steps):  
  `python -m harness.cli run-workload --config projects/default/configs/example_basic.yml`

## Configuration essentials
Each config (`projects/<project>/configs/*.yml`) defines:
- `project`: Project directory name under `projects/`.
- `variants`: Optional map of variant overrides. When present, `full-run` without `--variant` executes all variants in the map.
- `clickhouse`: `host`, `port`, `user`, `password`, `database`, `connection_pool_size`, `timeout_seconds`.
- `schema`: `fresh` (drop/recreate database), `fail_on_error`.
- `data`: `load_method` (e.g., `insert`), `truncate_before_load`, `load` entries (`table`, `file`, `format`). Project files load first, variants supplement/override.
- `workload`: `name`, `path`, optional explicit `queries` (with `file` and `weight`) or auto-discovery of `*.sql`; `concurrency`, `duration_seconds`, `ramp_up_seconds`, `warmup_queries`, `think_time_ms`, `max_errors`, `query_timeout_seconds`, optional `parameters` for `.format` substitution.
- `metrics`: `use_query_log`, `query_log_wait_seconds`, `output_csv`, `output_md` (variant suffix auto-added).

## Comparing results
Generate a Markdown diff between two CSV outputs:
```bash
python -m harness.cli compare \
  projects/default/results/results_default.csv \
  projects/default/results/results_variant1.csv \
  --output projects/default/results/comparison.md
```

## Creating a new project
- Copy `projects/default` to `projects/<your_project>`; keep the directory layout from the "Repository layout" section.
- Add schemas/data/workloads per project and per variant as needed.
- Create a config in `projects/<your_project>/configs/` and run `full-run` against it.
