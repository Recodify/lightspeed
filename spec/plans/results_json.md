# Plan: Canonical JSON Results Output

## Context
- Each variant run currently emits CSV and Markdown reports. We want JSON to be the canonical machine-readable output (workload + data_load), with CSV/MD kept for humans/legacy.
- Comparators and downstream tooling will consume JSON first, falling back to CSV only temporarily.

## Goals
1) Emit `results.json` (workload) and `data_load.json` (ingest) per variant run with a stable schema.  
2) Keep CSV/MD emission unchanged for now.  
3) Update comparator/CLI to prefer JSON inputs.  
4) Add minimal tests/fixtures for JSON emission and parsing.

## Non-Goals
- No changes to query execution logic or metrics collected.
- No HTML/PDF generation.
- No LLM commentary.

## Data Shapes
- `results.json`:
  - metadata: `{ project, variant, workload: { name, concurrency, duration_seconds }, run_name, config_name, workload_start_epoch_ms, workload_end_epoch_ms, workload_elapsed_secs }`
  - queries: array of `{ query_name, count, errors, error_rate, qps, p50_ms, p95_ms, p99_ms, avg_read_rows, avg_read_bytes, avg_memory_usage }`
  - summary: `{ total_queries, total_errors, overall_error_rate, overall_qps }`
- `data_load.json`:
  - totals: `{ files_loaded, bytes_transferred, duration_ms, duration_secs, throughput_mb_s }`
  - files: array of `{ table, file, source, bytes, duration_ms, throughput_mb_s }`
  - metadata: `{ project, variant, run_name, config_name, load_method, truncate_before_load }`

## Implementation Steps
1) Reporter:
   - Add writers for `results.json` and `data_load.json` alongside existing CSV/MD.
   - Ensure run directory paths match current layout.
2) Comparator:
   - Update to load JSON first; if missing, fall back to CSV (temporary).
   - No change to output format yet (that’s in the comparison plan).
3) CLI:
   - Accept JSON inputs in `compare` command; prefer JSON when present.
   - Full-run auto-comparison to point at JSON paths once emitted.
4) Tests:
   - Unit test JSON serialization shape from reporter given fixture ExecutionRecords.
   - Comparator load/parsing test from sample `results.json`.
5) Docs:
   - README note: JSON is canonical; CSV/MD remain for humans.
   - Mention file paths: `projects/<project>/results/<config>/<run>/<variant>/results.json` and `data_load.json`.

## Open Questions
- Do we want a version field in JSON to allow future schema evolution? (Recommendation: add `schema_version: 1`.)  
- How long to keep CSV fallback in comparator before removal?***
