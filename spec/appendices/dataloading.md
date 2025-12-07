# Data Loading Semantics

## Resolution and Load Order

For each `data.load` entry in the configuration:

```yaml
data:
  load:
    - table: "dim_product"
      file: "dim_product.csv"
      format: "CSVWithNames"
    - table: "trades"
      file: "trades.csv"
      format: "CSVWithNames"
```

The harness resolves and loads data files according to the following rules:

### Resolution Algorithm

For each entry:

1. Compute file paths:
   - `project_path = PROJECT_ROOT/data/<file>`
   - `variant_path = VARIANT_ROOT/data/<file>`

2. Load order (into the table specified by `table` field):
   - If `project_path` exists, load it first
   - If `variant_path` exists, load it second (appends to same table)

3. Validation:
   - At least one of `project_path` or `variant_path` must exist
   - If neither exists, validation fails with error: "No data file found for `<file>` in project or variant directories"

### Key Principles

- **Target table** is always determined by the `table` field in the config entry, never inferred from filenames
- **Project-level data** is optional per entry
- **Variant-level data** is optional per entry
- **At least one must exist** per entry to pass validation
- **Load order is deterministic**: project file always loads before variant file when both exist

## Usage Patterns

### Pattern 1: Shared Dimension Data

**Use case:** Reference tables, lookups, dictionaries that are identical across all variants.

**Layout:**

```
projects/default/
  data/
    dim_product.csv
    dim_counterparty.csv

  variants/
    variant_a/
      data/
        trades.csv
    variant_b/
      data/
        trades.csv
```

**Config:**

```yaml
data:
  load:
    - table: "dim_product"
      file: "dim_product.csv"
      format: "CSVWithNames"
    - table: "dim_counterparty"
      file: "dim_counterparty.csv"
      format: "CSVWithNames"
    - table: "trades"
      file: "trades.csv"
      format: "CSVWithNames"
```

**Behavior:**

- `dim_product`: Loaded from project-level file for all variants
- `dim_counterparty`: Loaded from project-level file for all variants
- `trades`: Loaded from variant-specific file only (different per variant)

### Pattern 2: Baseline + Overlay

**Use case:** Common baseline dataset with variant-specific additions for stress testing or extended scenarios.

**Layout:**

```
projects/default/
  data/
    trades.csv          # Baseline: 1M rows, Jan-Jun 2024

  variants/
    variant_a/
      data/
        trades.csv      # Extension: 500K rows, Jul-Sep 2024
```

**Config:**

```yaml
data:
  load:
    - table: "trades"
      file: "trades.csv"
      format: "CSVWithNames"
```

**Behavior:**

For `variant_a`:
1. Load `projects/default/data/trades.csv` → 1M rows in `trades`
2. Load `projects/default/variants/variant_a/data/trades.csv` → +500K rows in `trades`
3. Final table contains 1.5M rows (baseline + overlay)

**Note:** This pattern assumes appending rows is the desired behavior. If replacement semantics are needed, use different filenames or separate config entries.

### Pattern 3: Variant-Specific Tables

**Use case:** Fact tables or scenario data that differs completely across variants.

**Layout:**

```
projects/default/
  data/
    dim_product.csv

  variants/
    variant_a/
      data/
        trades.csv
        positions.csv
    variant_b/
      data/
        trades.csv
        # positions.csv absent
```

**Config:**

```yaml
data:
  load:
    - table: "dim_product"
      file: "dim_product.csv"
      format: "CSVWithNames"
    - table: "trades"
      file: "trades.csv"
      format: "CSVWithNames"
    - table: "positions"
      file: "positions.csv"
      format: "CSVWithNames"
```

**Behavior:**

For `variant_a`:
- `dim_product`: Loaded from project-level file
- `trades`: Loaded from variant-level file only
- `positions`: Loaded from variant-level file only

For `variant_b`:
- `dim_product`: Loaded from project-level file
- `trades`: Loaded from variant-level file only
- `positions`: **Validation fails** (file not found)

**Rationale:** Prevents accidentally running a variant with incomplete data. Each variant must provide all required files or remove unnecessary entries from its config.

## Implementation Notes

### data_loader.py Behavior

For each `data.load` entry:

1. Resolve file paths using the algorithm above
2. If `truncate_before_load` is true: Execute `TRUNCATE TABLE <table>` once
3. Load sequence:
   - If project file exists:
     - Open file handle
     - Stream via `INSERT INTO <table> FORMAT <format>` with file as HTTP body
     - Log: table name, bytes sent, duration, success/failure
   - If variant file exists:
     - Open file handle
     - Stream via `INSERT INTO <table> FORMAT <format>` with file as HTTP body
     - Log: table name, bytes sent, duration, success/failure
4. Any failure aborts the entire data loading phase with non-zero exit code

### CSV Header Handling

For CSV files, the harness assumes files contain headers and uses `CSVWithNames` format. ClickHouse handles header skipping natively; no client-side row skipping is required.

### File Format Support

The harness streams all file formats as raw bytes to ClickHouse via HTTP. ClickHouse performs all parsing:

- **CSV**: Use `CSVWithNames` for files with headers
- **Parquet**: ClickHouse parses directly from HTTP stream
- **Other formats**: Specify any ClickHouse-supported format string

The harness does not require `pyarrow` or other parsing libraries; it is purely a streaming transport layer.

## Error Messages

**File not found:**
```
Error: No data file found for 'trades.csv'
  - Checked: projects/default/data/trades.csv (not found)
  - Checked: projects/default/variants/variant_a/data/trades.csv (not found)
  - At least one must exist for table 'trades'
```

**Load failure:**
```
Error: Failed to load data into table 'trades'
  - File: projects/default/data/trades.csv
  - HTTP status: 400
  - ClickHouse error: Code: 27. DB::Exception: Cannot parse input: expected ',' before: ...
```

## Rationale

This design supports three distinct use cases with a single, predictable mechanism:

1. **Shared reference data**: Project-level files provide invariant dimensions/lookups for all variants
2. **Variant-specific scenarios**: Variant-level files provide facts, time periods, or stress datasets unique to each test
3. **Baseline + extension**: Both files present allows testing "normal + spike" or "historical + recent" patterns

No special configuration flags are needed. The presence or absence of files in each location determines the behavior, making the system's operation immediately obvious from directory structure.

The "at least one must exist" validation prevents silent failures from typos or missing files while allowing maximum flexibility in how projects and variants partition their data.