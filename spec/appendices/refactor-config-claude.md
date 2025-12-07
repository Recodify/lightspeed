Plan: Multi-Variant Config Support

 Problem Statement

 Currently, users must either:
 1. Create separate config files for each variant, OR
 2. Edit the variant field in the config file each time

 The user wants a single config file that defines multiple variants with their overrides, similar to the example in
 spec/config_example.yml:

 project: default

 # Project-level defaults
 clickhouse: {...}
 schema: {...}
 data: {...}
 workload: {...}

 # Define multiple variants in one config
 variants:
   - default:
       description: "Baseline configuration"
   - variant1:
       description: "Some optimization"
       data:
         load:
           - table: events
             file: variant1_data.csv  # Override data file

 Proposed Solution

 Design Overview - ADDITIVE VARIANTS

 Key insight from user: Variants are additive, not merge/replace. Each variant definition includes its complete configuration, not
 overrides to apply on top of base config.

 Structure:
 1. Top-level config sections (clickhouse, schema, workload, metrics) define project-level defaults
 2. variants section defines multiple named variants, each with complete config for sections it cares about
 3. When selecting a variant, its config sections replace the top-level defaults (not merge)
 4. CLI changes: Add --variant <name> flag to specify which variant to run

 Implementation Steps

 Step 1: Update Config Schema

 File: harness/config.py

 Add new Pydantic model:
 - VariantConfig(BaseModel): Contains complete config sections for a variant
   - description: str | None = None
   - data: DataConfig | None = None
   - workload: WorkloadConfig | None = None
   - schema: SchemaConfig | None = None
   - clickhouse: ClickHouseConfig | None = None
   - metrics: MetricsConfig | None = None

 Update BenchmarkConfig:
 - Change top-level fields to be optional with defaults (to support variants-only configs)
 - Add variants: dict[str, VariantConfig] | None = None
 - Keep existing variant: str = "default" field for backward compatibility

 Step 2: Implement Variant Resolution

 File: harness/config.py

 Add function: resolve_variant_config(base_config: BenchmarkConfig, variant_name: str) -> BenchmarkConfig
 - Takes base config and variant name
 - Looks up variant in base_config.variants[variant_name]
 - For each section in VariantConfig:
   - If variant defines the section, use variant's value (replacement, not merge)
   - Otherwise, use top-level config section
 - Returns new BenchmarkConfig with resolved values
 - Sets config.variant = variant_name

 Example logic:
 variant = base_config.variants[variant_name]
 resolved_data = variant.data if variant.data is not None else base_config.data
 resolved_workload = variant.workload if variant.workload is not None else base_config.workload
 # ... etc for all sections

 Step 3: Update CLI

 File: harness/cli.py

 - Add --variant <name> argument to all subcommands
 - Default to "default" if not specified
 - After loading config with load_config(), call resolve_variant_config(config, args.variant)
 - Validate that the specified variant exists in the config

 Step 4: Validation

 File: harness/config.py

 Validation requirements:
 - If variants is defined, ensure at least one variant exists
 - If user specifies --variant that doesn't exist in config.variants, raise error with available variants
 - Each variant's resolved config should be valid (e.g., required fields present)
 - Note: Don't validate variant directories exist - variants may share data/workload paths

 Backward Compatibility

 To maintain backward compatibility with existing configs that don't have a variants section:
 - If variants is None or not defined, use the config as-is
 - The existing variant field determines the output filename suffix
 - No breaking changes to existing configs

 Example old-style config (still works):
 project: default
 variant: variant1  # Used for output naming only
 clickhouse: {...}
 data: {...}
 workload: {...}

 Example new-style config (preferred):
 project: default
 clickhouse: {...}  # Project-level defaults

 variants:
   default:
     description: "Baseline"
     data: {...}

   variant1:
     description: "Optimization"
     data: {...}  # Completely replaces top-level data config

 Usage Examples

 Example 1: Data variants with shared workload
 # config.yml
 project: default

 # Project-level defaults
 clickhouse:
   host: localhost
   port: 8123
   database: benchmark

 workload:  # Shared by all variants
   name: baseline
   path: baseline
   concurrency: 4
   duration_seconds: 10

 variants:
   default:
     description: "Baseline with 1k rows"
     data:
       load:
         - table: events
           file: data_1k.csv

   large:
     description: "Large dataset with 1M rows"
     data:
       load:
         - table: events
           file: data_1m.csv

 Run variants:
 python -m harness.cli full-run --config config.yml --variant default
 python -m harness.cli full-run --config config.yml --variant large

 Example 2: Workload variants with shared data
 project: default

 clickhouse: {...}

 data:  # Shared by all variants
   load:
     - table: events
       file: sample.csv

 variants:
   low_concurrency:
     description: "4 concurrent workers"
     workload:
       concurrency: 4
       duration_seconds: 60

   high_concurrency:
     description: "16 concurrent workers"
     workload:
       concurrency: 16
       duration_seconds: 60

 Example 3: Compare all variants
 # Run all variants
 python -m harness.cli full-run --config config.yml --variant default
 python -m harness.cli full-run --config config.yml --variant large

 # Compare results
 python -m harness.cli compare \
   results/results_default.csv \
   results/results_large.csv \
   --output results/comparison.md

 Implementation Summary

 Files to Modify:

 1. harness/config.py
   - Add VariantConfig(BaseModel) with optional fields for all config sections
   - Add variants: dict[str, VariantConfig] | None = None to BenchmarkConfig
   - Implement resolve_variant_config(base_config, variant_name) -> BenchmarkConfig
   - Add validation for variant existence and completeness
 2. harness/cli.py
   - Add --variant argument to all subcommands (default="default")
   - After load_config(), call resolve_variant_config() if config has variants
   - Handle errors for missing variants
 3. projects/default/configs/example_basic.yml
   - Convert to new multi-variant format
   - Define default and variant1 variants
   - Move data config into variant definitions
   - Keep clickhouse, workload, metrics at top level as defaults

 Benefits

 1. DRY: Define common config once, override only what differs
 2. Clarity: All variants visible in one file
 3. Easy comparison: Clear what differs between variants
 4. Backward compatible: Existing configs continue to work
 5. Flexible: Can override any config section per variant

 Edge Cases to Handle

 1. User specifies --variant but config has no variants section
   - Use the config as-is with the specified variant name for output naming
   - This maintains backward compatibility
 2. User specifies a variant that doesn't exist in variants
   - Raise error: "Variant 'foo' not found. Available variants: default, large"
 3. Variant defines only some sections (e.g., only data)
   - Use variant's sections where defined
   - Fall back to top-level sections for undefined parts
   - Example: variant defines data but not workload → use variant's data + top-level workload
 4. Required sections missing after resolution
   - After resolving variant, validate that all required sections are present
   - Error if missing: "Variant 'foo' missing required section: workload"
 5. Config with variants but no top-level defaults
   - Valid if each variant defines all required sections
   - Error if any variant is incomplete
 6. Variant config completely replaces section, not merges
   - If variant defines data.load, it replaces entire data.load list
   - No merging of individual table entries