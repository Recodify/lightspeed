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

  projects
    default
        configs/
            example_basic.yml
            example_weighted.yml
            example_params.yml
        schemas/ #project wide invariant schemas go here
        data/ #project wide invariant schema go here
        workloads/ #project wide invariant queries go here
        variants
            default
                schemas/
                    001_create_tables.sql
                    002_indexes.sql
                data/
                    trades.csv
            variant_a/
                data/
                    trades.csv
                    prices.parquet
                schemas/
                    001_create_tables.sql
        workloads/
            baseline/
                q01_latency.sql
                q02_throughput.sql
            heavy/
                q01_full_scan.sql

        results/
            .gitkeep
    project A
        configs/
            ...
        schemas/
            ...
        variants/
    etc
