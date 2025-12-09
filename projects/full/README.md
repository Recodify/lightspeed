# Full Example Project

This project demonstrates a more complete setup for the benchmarking harness, including multiple variants, weighted queries, and parameterized workloads. It uses the sample schemas and data under `projects/full/variants` and the baseline workload queries in `projects/full/workloads/baseline/`.

## Files of Interest

- **Configs**: `projects/full/configs/`
  - `example_bare.yml` — minimal config showing how to point a project at a workload and variant data.
  - `example_basic.yml` — multi-variant config with simple and aggregate queries.
  - `example_load_methods.yml` — compares `insert` vs `script` data loading using shared data.
  - `example_weighted.yml` — demonstrates weighted query selection.
  - `example_params.yml` — shows how to add parameters for dynamic queries.
  - `example_full_run.yml` — new end-to-end example combining weighted and parameterized queries across variants.
- **Variants**: `projects/full/variants/`
  - `default` — orders data by time to optimize range scans.
  - `variant1` — orders data by user to optimize per-user lookups and includes the scripted data load example.
- **Workloads**: `projects/full/workloads/baseline/` — contains three sample queries, including a parameterized filter.

## Running the full example

Ensure your ClickHouse instance is reachable with credentials from the config, then run:

```bash
python -m harness.cli full-run --config projects/full/configs/example_full_run.yml --run-name demo
```

Results will be written under `projects/full/results/<config>/<run>/` for each variant (e.g., `default` and `variant1`).
