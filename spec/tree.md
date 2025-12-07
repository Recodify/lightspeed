.
├── activate.sh
├── ch_harness.egg-info
│   ├── dependency_links.txt
│   ├── PKG-INFO
│   ├── requires.txt
│   ├── SOURCES.txt
│   └── top_level.txt
├── CLAUDE.md
├── coverage
├── harness
│   ├── clickhouse_client.py
│   ├── cli.py
│   ├── comparator.py
│   ├── config.py
│   ├── data_loader.py
│   ├── exceptions.py
│   ├── __init__.py
│   ├── __main__.py
│   ├── metrics_collector.py
│   ├── parameter_generator.py
│   ├── __pycache__
│   │   ├── clickhouse_client.cpython-312.pyc
│   │   ├── cli.cpython-312.pyc
│   │   ├── comparator.cpython-312.pyc
│   │   ├── config.cpython-312.pyc
│   │   ├── data_loader.cpython-312.pyc
│   │   ├── exceptions.cpython-312.pyc
│   │   ├── __init__.cpython-312.pyc
│   │   ├── __main__.cpython-312.pyc
│   │   ├── metrics_collector.cpython-312.pyc
│   │   ├── parameter_generator.cpython-312.pyc
│   │   ├── reporter.cpython-312.pyc
│   │   ├── schema_loader.cpython-312.pyc
│   │   ├── utils.cpython-312.pyc
│   │   └── workload_runner.cpython-312.pyc
│   ├── reporter.py
│   ├── schema_loader.py
│   ├── tools
│   │   ├── data.csv
│   │   └── data-generator.py
│   ├── utils.py
│   └── workload_runner.py
├── Makefile
├── projects
│   ├── barebones
│   │   ├── configs
│   │   │   └── bare_config.yml
│   │   ├── data
│   │   ├── results
│   │   │   ├── bareconfig
│   │   │   │   ├── industriouskudu
│   │   │   │   │   └── default
│   │   │   │   │       ├── data_load.csv
│   │   │   │   │       ├── results.csv
│   │   │   │   │       └── results.md
│   │   │   │   ├── keenlemming
│   │   │   │   │   └── default
│   │   │   │   │       ├── data_load.csv
│   │   │   │   │       ├── results.csv
│   │   │   │   │       └── results.md
│   │   │   │   └── tuscancaracal
│   │   │   │       └── default
│   │   │   │           ├── data_load.csv
│   │   │   │           ├── results.csv
│   │   │   │           └── results.md
│   │   │   ├── examplebare
│   │   │   │   └── elegantoctopus
│   │   │   │       ├── default
│   │   │   │       │   ├── results.csv
│   │   │   │       │   └── results.md
│   │   │   │       └── variant1
│   │   │   │           ├── results.csv
│   │   │   │           └── results.md
│   │   │   ├── examplebasic
│   │   │   │   ├── benignjunglefowl
│   │   │   │   │   ├── default
│   │   │   │   │   │   ├── results.csv
│   │   │   │   │   │   └── results.md
│   │   │   │   │   └── variant1
│   │   │   │   │       ├── results.csv
│   │   │   │   │       └── results.md
│   │   │   │   └── defiantcricket
│   │   │   │       ├── default
│   │   │   │       │   ├── results.csv
│   │   │   │       │   └── results.md
│   │   │   │       └── variant1
│   │   │   │           ├── results.csv
│   │   │   │           └── results.md
│   │   │   ├── results_default.csv
│   │   │   ├── results_default.md
│   │   │   ├── results_variant1.csv
│   │   │   └── results_variant1.md
│   │   ├── schemas
│   │   ├── variants
│   │   │   ├── default
│   │   │   │   ├── data
│   │   │   │   │   └── sample.csv
│   │   │   │   └── schemas
│   │   │   │       └── 001_create_tables.sql
│   │   │   └── variant1
│   │   │       ├── data
│   │   │       │   └── sample.csv
│   │   │       └── schemas
│   │   │           └── 001_create_tables.sql
│   │   └── workloads
│   │       └── baseline
│   │           ├── q01_simple.sql
│   │           └── q02_aggregate.sql
│   ├── engineselectionlocal
│   ├── full
│   │   ├── configs
│   │   │   ├── example_bare.yml
│   │   │   ├── example_basic.yml
│   │   │   ├── example_params.yml
│   │   │   └── example_weighted.yml
│   │   ├── data
│   │   ├── results
│   │   │   ├── examplebare
│   │   │   │   └── elegantoctopus
│   │   │   │       ├── default
│   │   │   │       │   ├── results.csv
│   │   │   │       │   └── results.md
│   │   │   │       └── variant1
│   │   │   │           ├── results.csv
│   │   │   │           └── results.md
│   │   │   ├── examplebasic
│   │   │   │   ├── benignjunglefowl
│   │   │   │   │   ├── default
│   │   │   │   │   │   ├── results.csv
│   │   │   │   │   │   └── results.md
│   │   │   │   │   └── variant1
│   │   │   │   │       ├── results.csv
│   │   │   │   │       └── results.md
│   │   │   │   └── defiantcricket
│   │   │   │       ├── default
│   │   │   │       │   ├── results.csv
│   │   │   │       │   └── results.md
│   │   │   │       └── variant1
│   │   │   │           ├── results.csv
│   │   │   │           └── results.md
│   │   │   ├── results_default.csv
│   │   │   ├── results_default.md
│   │   │   ├── results_variant1.csv
│   │   │   └── results_variant1.md
│   │   ├── schemas
│   │   ├── variants
│   │   │   ├── default
│   │   │   │   ├── data
│   │   │   │   │   └── sample.csv
│   │   │   │   └── schemas
│   │   │   │       └── 001_create_tables.sql
│   │   │   └── variant1
│   │   │       ├── data
│   │   │       │   └── sample.csv
│   │   │       └── schemas
│   │   │           └── 001_create_tables.sql
│   │   └── workloads
│   │       └── baseline
│   │           ├── q01_simple.sql
│   │           ├── q02_aggregate.sql
│   │           └── q03_parameterized.sql
│   ├── keyselectionlocal
│   │   ├── configs
│   │   │   └── basic.yml
│   │   ├── data
│   │   │   └── data.csv
│   │   ├── results
│   │   │   └── basic
│   │   │       ├── jadejacamar
│   │   │       │   ├── variant0
│   │   │       │   │   ├── data_load.csv
│   │   │       │   │   ├── results.csv
│   │   │       │   │   └── results.md
│   │   │       │   └── variant1
│   │   │       │       ├── data_load.csv
│   │   │       │       ├── results.csv
│   │   │       │       └── results.md
│   │   │       ├── opalescentbasilisk
│   │   │       │   ├── comparison_variant0_vs_variant1.md
│   │   │       │   ├── variant0
│   │   │       │   │   ├── data_load.csv
│   │   │       │   │   ├── results.csv
│   │   │       │   │   └── results.md
│   │   │       │   └── variant1
│   │   │       │       ├── data_load.csv
│   │   │       │       ├── results.csv
│   │   │       │       └── results.md
│   │   │       ├── papermink
│   │   │       │   ├── comparison_variant0_vs_variant1.md
│   │   │       │   ├── variant0
│   │   │       │   │   ├── data_load.csv
│   │   │       │   │   ├── results.csv
│   │   │       │   │   └── results.md
│   │   │       │   └── variant1
│   │   │       │       ├── data_load.csv
│   │   │       │       ├── results.csv
│   │   │       │       └── results.md
│   │   │       ├── perfectearthworm
│   │   │       │   └── variant0
│   │   │       │       ├── data_load.csv
│   │   │       │       ├── results.csv
│   │   │       │       └── results.md
│   │   │       └── toughnyala
│   │   │           └── variant1
│   │   │               ├── data_load.csv
│   │   │               ├── results.csv
│   │   │               └── results.md
│   │   ├── schemas
│   │   ├── variants
│   │   │   ├── variant0
│   │   │   │   ├── data
│   │   │   │   └── schemas
│   │   │   │       └── 001_create_tables.sql
│   │   │   └── variant1
│   │   │       ├── data
│   │   │       └── schemas
│   │   │           └── 001_create_tables.sql
│   │   └── workloads
│   │       └── baseline
│   │           └── q01_agg_max.sql
│   └── orderbylocal
├── pyproject.toml
├── readme.local.md
├── README.md
└── spec
    ├── appendices
    │   ├── appendix1.md
    │   ├── config_example.yml
    │   ├── dataloading.md
    │   ├── refactor-config-claude.md
    │   └── refactor-config-user.md
    ├── backlog
    │   ├── bugs
    │   │   ├── config_database_name.md
    │   │   └── metrics_collector_long_run.md
    │   └── features
    │       ├── cli.md
    │       ├── compare.md
    │       ├── data.md
    │       ├── detached-project-root.md
    │       ├── misc.md
    │       ├── operational-metrics.md
    │       ├── results.md
    │       └── runner.md
    ├── done
    │   └── features
    │       ├── schema-isolation.md
    │       └── test-isolation.md
    ├── plan.md
    ├── plans
    │   ├── comparison.md
    │   └── results_json.md
    ├── previous
    │   ├── plan1.md
    │   ├── plan2.md
    │   ├── plan3.md
    │   ├── plan4.md
    │   ├── plan5.md
    │   └── plan6.md
    ├── prompts
    │   ├── cgptplan.md
    │   ├── data-generator.md
    │   ├── implement-phase1.md
    │   └── workflow.md
    ├── tasklist.md
    └── tree.md

103 directories, 163 files
