# Plan for Multi-Variant Schema Isolation and Results Isolation

## Overview

We want to isolate schema and results per variant and run to avoid data overlaps and make it easier to track performance across multiple test configurations. This will ensure that each variant and run has its own set of data tables and corresponding results files. The config will remain the same as before, but we'll enhance how we handle schema and results storage.

## Key Concepts

- **Schema Isolation**: Each variant and run should have its own schema and tables, ensuring no data overlap or overwriting across runs or variants
- **Results Isolation**: Results will be written to isolated directories per run, with clear directory names for easy comparison

## 1. Schema Isolation

We will ensure complete isolation through two complementary layers that work together:

1. **Run-level isolation**: Each run gets its own database
2. **Variant-level isolation**: Within each run's database, each variant gets its own tables

**Final naming convention**: `benchmark_[runName].[tableName]_[variantName]`

For example:
- `benchmark_brave_penguin.events_default`
- `benchmark_brave_penguin.events_optimized`
- `benchmark_clever_falcon.events_default`

This ensures:
- No data contamination between runs (different databases)
- No data contamination between variants within a run (table name suffixes)
- Clear identification of what data belongs to which run and variant
- Easy post-run inspection and comparison

### Implementation

**Step 1: Create a database for the run**

```python
def create_run_database(run_name: str) -> str:
    """Create a unique database for this benchmark run."""
    # Replace hyphens with underscores for ClickHouse database name compatibility
    safe_name = run_name.replace('-', '_')
    database_name = f"benchmark_{safe_name}"

    # SQL to create the database
    create_database_sql = f"CREATE DATABASE IF NOT EXISTS {database_name}"
    execute_sql(create_database_sql)

    logger.info(f"Created run database: {database_name}")
    return database_name
```

**Step 2: Create variant-specific tables within the run database**

```python
def create_variant_table(database_name: str, table_name: str, variant_name: str, schema_sql: str) -> str:
    """Create a variant-specific table within the run's database."""
    # Sanitize variant name for ClickHouse compatibility
    safe_variant = variant_name.replace('-', '_')
    full_table_name = f"{database_name}.{table_name}_{safe_variant}"

    # Replace placeholder table name in schema SQL with the variant-specific name
    create_table_sql = schema_sql.replace(f"CREATE TABLE {table_name}",
                                          f"CREATE TABLE IF NOT EXISTS {full_table_name}")

    execute_sql(create_table_sql)
    logger.info(f"Created variant table: {full_table_name}")
    return full_table_name
```

**Complete workflow:**

```python
def setup_isolated_schema(run_name: str, variant_name: str, schema_files: list) -> dict:
    """Set up complete schema isolation for a run and variant."""
    # Step 1: Create run-level database
    database_name = create_run_database(run_name)

    # Step 2: Create all variant-specific tables
    created_tables = {}
    for schema_file in schema_files:
        with open(schema_file, 'r') as f:
            schema_sql = f.read()

        # Extract base table name from schema SQL
        base_table_name = extract_table_name(schema_sql)

        # Create variant-specific table
        full_table_name = create_variant_table(
            database_name,
            base_table_name,
            variant_name,
            schema_sql
        )
        created_tables[base_table_name] = full_table_name

    return {
        'database': database_name,
        'tables': created_tables
    }
```

## 2. Results Isolation

We will create unique subdirectories for each run inside `./projects/[project name]/results/`, so that results from different runs do not overwrite each other.

### Naming Strategy for Results Directories

The results for each run will be placed in a unique directory under `./projects/[project name]/results/`.

**Approach**: Docker-style memorable names using the `coolname` package

- If the user specifies a run name via `--run-name`, use that
- If not specified, generate a memorable name using `coolname` (e.g., `brave-penguin`, `clever-falcon`)
- This provides:
  - Human-readable identification
  - No date/time parsing complexity
  - Multiple runs per day without collision
  - Memorable references for discussion ("let's compare against the brave-penguin run")
  - Large namespace (~100k combinations with 2-part names, ~10M with 3-part names)

**Implementation:**

```python
from coolname import generate_slug
import os

def create_run_folder(base_path: str, run_name: str = None) -> tuple[str, str]:
    """Create a unique run folder with either a specified or generated name.

    Args:
        base_path: Base directory for results
        run_name: Optional user-specified run name

    Returns:
        Tuple of (run_folder_path, run_name)
    """
    if run_name is None:
        # Generate a 2-part memorable name (adjective-noun)
        run_name = generate_slug(2)

        # Handle the rare collision by generating a new name
        attempt = 1
        while os.path.exists(os.path.join(base_path, run_name)):
            run_name = generate_slug(2)
            attempt += 1
            if attempt > 5:  # After 5 attempts, append a number
                run_name = f"{run_name}-{attempt}"
                break

    run_folder = os.path.join(base_path, run_name)
    os.makedirs(run_folder, exist_ok=True)
    return run_folder, run_name
```

**Dependencies:**

Add to `pyproject.toml` or `requirements.txt`:

```
coolname>=2.2.0
```

### Subdirectory Structure for Each Variant and Run

For every variant and run, create a dedicated folder under the results directory:

```
./projects/[project name]/results/
    brave-penguin/
        default/
            results.csv
            results.md
        optimized/
            results.csv
            results.md
    clever-falcon/
        default/
            results.csv
            results.md
        high-concurrency/
            results.csv
            results.md
```

**Implementation:**

```python
def write_variant_results(run_folder: str, variant_name: str, results_data: dict):
    variant_folder = os.path.join(run_folder, variant_name)
    os.makedirs(variant_folder, exist_ok=True)
    variant_result_file = os.path.join(variant_folder, "results.json")
    with open(variant_result_file, "w") as result_file:
        json.dump(results_data, result_file)
```

## 3. Integration with CLI

The command-line interface will handle the variant selection and the result writing. The main update will involve selecting the variant, creating the appropriate subdirectory, and then writing results there.

### Step 1: Parsing Command Line Arguments

Add the `--run-name` argument to allow users to specify a memorable name for the run.

```python
def parse_args():
    parser = argparse.ArgumentParser(description="Run ClickHouse benchmark")
    parser.add_argument('--config', type=str, required=True, help="Path to config file")
    parser.add_argument('--variant', type=str, default="default", help="Select which variant to run")
    parser.add_argument('--run-name', type=str, default=None, help="Specify a name for this run (e.g., 'baseline-test'). If not provided, generates a memorable name like 'thirsty-badger'")
    args = parser.parse_args()
    return args
```

### Step 2: Resolve Config for Variant

After loading the config, resolve the selected variant using the `resolve_variant_config()` function:

```python
def main():
    args = parse_args()
    config = load_config(args.config)

    # Resolve the selected variant's config
    config = resolve_variant_config(config, args.variant)

    # Create the folder for the current run with specified or generated name
    run_folder, run_name = create_run_folder("./projects/[project_name]/results/", args.run_name)

    # Log the run name for reference
    logger.info(f"Starting benchmark run: {run_name}")

    # Write results for each variant to its respective folder
    write_variant_results(run_folder, args.variant, results_data)
```

**Example CLI usage:**

```bash
# With explicit run name
python -m harness.cli full-run --config config.yml --variant optimized --run-name baseline-v1

# Auto-generated name (e.g., "brave-penguin")
python -m harness.cli full-run --config config.yml --variant optimized

# Compare two runs by their memorable names
python -m harness.cli compare \
  projects/default/results/brave-penguin/optimized/results.csv \
  projects/default/results/clever-falcon/optimized/results.csv \
  --output projects/default/results/comparison-penguin-vs-falcon.md
```

## 4. Benefits of This Approach

1. **Clear Isolation**: Ensures no overwriting of results between runs or variants

2. **Traceability**: Each run and variant is easily identifiable by memorable names that are easy to reference in discussion

3. **Easier Comparison**: Allows for straightforward comparison of different variants and runs by storing results in well-organized directories with human-readable names

4. **Post-Run Inspection**: After each run, data from that specific benchmark run is preserved in its own folder, making inspection and auditability easier

5. **Human-Friendly**: Names like "brave-penguin" are much easier to remember and discuss than timestamps or sequential numbers, with a large namespace (~100k combinations) that virtually eliminates collisions

6. **Flexibility**: Users can specify meaningful names for important baseline runs while getting auto-generated names for exploratory runs

7. **Well-Maintained**: Uses the `coolname` package which is actively maintained and battle-tested

## 5. Edge Cases and Considerations

1. **Run Overlaps**: Ensure that no data is accidentally overwritten by concurrent runs. This can be prevented with unique folder names.

2. **Error Handling**: Ensure that the system handles errors gracefully—particularly in cases where a run fails midway. Only partial data should be written if the benchmark doesn't complete.

3. **Storage Management**: Monitor disk space usage. As the number of runs grows, it might be necessary to implement a cleanup or archiving process to prevent excessive disk consumption.

## 6. Conclusion

This plan creates a clean, isolated structure for managing schema and results across multiple runs and variants. By ensuring that:

- Each run is fully isolated in its own database or folder
- Results for each variant are written to unique directories per run

We can effectively track the performance of different configurations, ensure easy comparison, and avoid the pitfalls of data overlap and overwriting. This setup is future-proof, scalable, and clear for benchmarking purposes.