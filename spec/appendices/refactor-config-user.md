# Updated Plan: Unified Multi-Variant Config Support

## Problem Statement

Previously, configurations could be split between legacy and variant-based approaches. To simplify and future-proof, we will migrate to a single, unified config structure that handles all variants within one file.

## Proposed Solution

The config structure will:

- Always define variants in the same way within the `variants` section of the config
- Eliminate legacy support for `variant` as a field in the top-level config
- Remove backward compatibility for previous config formats
- Use additive variant configuration, where each variant defines a complete config, and variants replace the top-level config sections

## Design Overview

The plan is to:

1. Define project-wide defaults at the top level (for fields that are consistent across all variants)
2. Variants will be listed under `variants`, with each having a complete, independent config
3. When a variant is selected (via CLI), the system will replace the relevant top-level config sections with the corresponding section from the selected variant

## Implementation Steps

### Step 1: Update Config Schema

In `harness/config.py`, we'll create a clean and unified model for the config:

- **VariantConfig**: This will be the model for individual variants, each containing full config sections (e.g., `schema`, `data`, `workload`, `clickhouse`, `metrics`)
- **BenchmarkConfig**: The top-level config, which will define project-wide defaults and a `variants` section

```python
from pydantic import BaseModel
from typing import Optional, Dict

# Define the variant configuration
class VariantConfig(BaseModel):
    description: Optional[str] = None
    data: Optional[DataConfig] = None
    workload: Optional[WorkloadConfig] = None
    schema: Optional[SchemaConfig] = None
    clickhouse: Optional[ClickHouseConfig] = None
    metrics: Optional[MetricsConfig] = None

# Main config
class BenchmarkConfig(BaseModel):
    clickhouse: ClickHouseConfig
    schema: SchemaConfig
    data: DataConfig
    workload: WorkloadConfig
    metrics: MetricsConfig
    variants: Dict[str, VariantConfig]  # This now holds the variants
    variant: str = "default"  # Default to 'default' variant for backward compatibility for non-variant usage
```

### Step 2: Implement Variant Resolution

In `harness/config.py`, we'll add a function to resolve the selected variant. This function will replace the top-level config with the selected variant's config.

```python
def resolve_variant_config(base_config: BenchmarkConfig, variant_name: str) -> BenchmarkConfig:
    # Ensure the variant exists in the config
    if variant_name not in base_config.variants:
        raise ValueError(f"Variant '{variant_name}' not found. Available variants: {', '.join(base_config.variants.keys())}")

    variant = base_config.variants[variant_name]

    # For each section, use the variant's value if defined, otherwise fallback to the top-level config
    resolved_data = variant.data if variant.data is not None else base_config.data
    resolved_workload = variant.workload if variant.workload is not None else base_config.workload
    resolved_schema = variant.schema if variant.schema is not None else base_config.schema
    resolved_clickhouse = variant.clickhouse if variant.clickhouse is not None else base_config.clickhouse
    resolved_metrics = variant.metrics if variant.metrics is not None else base_config.metrics

    return BenchmarkConfig(
        clickhouse=resolved_clickhouse,
        schema=resolved_schema,
        data=resolved_data,
        workload=resolved_workload,
        metrics=resolved_metrics,
        variants=base_config.variants,
        variant=variant_name
    )
```

### Step 3: Update CLI

In `harness/cli.py`, we will update the command-line interface to select a variant using the `--variant <name>` flag and validate the selected variant.

```python
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Run ClickHouse benchmark")
    parser.add_argument('--config', type=str, required=True, help="Path to config file")
    parser.add_argument('--variant', type=str, default="default", help="Select which variant to run")
    args = parser.parse_args()

    return args

def main():
    args = parse_args()
    config = load_config(args.config)

    # Resolve the variant
    config = resolve_variant_config(config, args.variant)

    # Run the full benchmark using the resolved config
    run_benchmark(config)
```

### Step 4: Validation

We will validate the integrity of the config and ensure that all required fields are present:

- If `variants` is defined, ensure at least one variant exists
- If the user specifies a `--variant` that doesn't exist, raise an error
- Ensure that the resolved variant config contains all required sections (`data`, `workload`, etc.)

## Usage Example

### Config Example (config.yml):

```yaml
project: energy_trading

# Project-level defaults
clickhouse:
  host: localhost
  port: 8123
  database: benchmark

schema:
  tables:
    - name: trades
      columns:
        - name: id
          type: Int32
        - name: price
          type: Float64

workload:
  name: baseline
  path: baseline
  concurrency: 4
  duration_seconds: 60

# Define multiple variants
variants:
  default:
    description: "Default baseline configuration"
    data:
      load:
        - table: trades
          file: default_data.csv

  optimized:
    description: "Optimized configuration for larger datasets"
    data:
      load:
        - table: trades
          file: optimized_data.csv
    workload:
      concurrency: 8
      duration_seconds: 120
```

### CLI Commands:

**Running the default variant:**

```bash
python -m harness.cli full-run --config config.yml --variant default
```

**Running the optimized variant:**

```bash
python -m harness.cli full-run --config config.yml --variant optimized
```

**Comparing results between variants:**

```bash
python -m harness.cli compare \
  results/results_default.csv \
  results/results_optimized.csv \
  --output results/comparison.md
```

## Benefits

1. **Cleaner Configs**: No more separate files for each variant. The entire project config is contained in one file, with variants cleanly separated.

2. **Flexibility**: Variants are independent, can define their own settings, and can replace specific sections of the config.

3. **Simplified Validation**: The `--variant` flag provides clear variant selection, and any invalid configuration is caught early.

4. **Easy Comparison**: Clear visual comparison between variants, making it easy to track performance impacts and configurations.

5. **Future-Proof**: The config is future-proof, allowing for easy addition of new variants without disrupting the base config.

## Edge Cases

1. **Variant Not Found**: If the user specifies a variant that doesn't exist, raise a clear error message.

2. **Variant Defines Only Some Sections**: If a variant defines only specific sections (e.g., just `data` but no `workload`), the missing sections should fall back to the base config.

3. **Incomplete Configs**: If a variant config is missing any required section (like `data`, `workload`, etc.), validation should fail with a clear message.

4. **Legacy Config Support**: Ensure that configurations without the `variants` section are still valid, but clearly indicate that users should migrate to the new structure.

## Conclusion

By removing backward compatibility and transitioning to a single, clean config model, this structure streamlines the process, provides clarity, and makes future configuration management more scalable. The implementation ensures:

- Clear separation of baseline configurations and experiment variants
- Easy-to-compare variant configurations for testing and benchmarking
- A clean, maintainable config structure without legacy baggage

This is the way forward for both flexibility and clarity, ensuring your benchmark tool evolves cleanly and efficiently.