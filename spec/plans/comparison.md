# Plan: Comparison Report Improvements

## Warning

This is a loose plan as the design/endgoal isn't yet nailed down. See ./spec/appendices/comparison_results.md for more background.


## Context
- Comparison is a post-processing step after a multi-variant run. Each variant produces `results.*` (workload metrics) and `data_load.*`, stored under `projects/<project>/results/<config>/<run>/<variant>/`.
- Run identity: directory hierarchy captures the auto-generated run name (coolname).
- No raw time-series alignment is needed; we compare aggregated results.
- Primary canonical output for per-variant results will move to JSON (superset of current CSV, including data_load metrics). Markdown remains for humans.

## Goals
1) Make comparisons easy to read: variant names in headers, clear better/worse indication, human-readable summary.
2) Support an arbitrary number of variants in a single run (N-way).
3) Use JSON results as canonical inputs for comparison to simplify future evolution.
4) Produce comparison outputs for human consumption (Markdown/HTML) and machine consumption (JSON diff), with optional color cues in Markdown.

## Non-Goals
- No raw time-series alignment or statistical significance testing in this phase.
- No LLM-generated qualitative commentary in this iteration (can be added later).
- No PDF generation in this iteration (HTML/MD is sufficient).

## Inputs
- Two per-variant result JSON files (canonical): `results.json` per variant, containing per-query stats (`p50_ms`, `p95_ms`, `p99_ms`, `qps`, `count`, `errors`, `error_rate`, etc.) plus metadata (project, variant, workload, run_name) and data_load summary.
- Optional: Markdown/CSV from each variant (legacy) — used only if JSON is missing (best-effort).

## Outputs
- Pairwise comparisons (baseline vs each other variant):
  - `comparison_<baseline>_vs_<variant>.json`
  - `comparison_<baseline>_vs_<variant>.md`
- Aggregate N-way summary (optional but recommended):
  - `comparison_summary.json` with rankings per metric (e.g., best latency, best QPS) and per-query leader/laggard.
  - `comparison_summary.md` highlighting winners/losers per query and overall counts.

## Data Shapes
- Per-variant results JSON (expected shape):
  - metadata: project, variant, workload_name, concurrency, run_name, timings.
  - queries: array of { query_name, count, errors, error_rate, qps, p50_ms, p95_ms, p99_ms, avg_read_rows, avg_read_bytes, avg_memory_usage }.
  - data_load: { files_loaded, bytes_transferred, duration_ms, throughput_mb_s, files: [...] } (optional).
- Comparison JSON:
  - baseline_variant, comparison_variant, baseline_path, comparison_path
  - overall: { total_queries_delta, total_errors_delta, overall_qps_delta, winner (optional scoring) }
  - per_query: for each query: { query_name, baseline: {metrics}, comparison: {metrics}, deltas: {p50_pct, p95_pct, p99_pct, qps_pct}, status: "better" | "worse" | "mixed" | "missing_baseline" | "missing_comparison" }
  - data_load (optional): compare duration_ms, throughput_mb_s, bytes_transferred if present.
- N-way summary JSON (optional):
  - variants: list of variants included
  - per_query: { query_name, rankings: [{variant, p50_ms, rank}, ...], best_variant_by_latency, best_variant_by_qps }
  - overall: counts of per-query wins/losses per variant, tie handling rules.

## Rules for “better/worse” (directional judgement)
- Latency metrics (p50/p95/p99): lower is better.
- Throughput (qps), bytes_read, rows_read: higher is better.
- Errors/error_rate: lower is better.
- Status per query:
  - If all present metrics point same way, label better/worse accordingly.
  - If mixed signals, label mixed.
  - If missing on one side, mark missing_baseline/missing_comparison.
- Overall winner (optional): count queries where comparison is better minus worse; ties -> "mixed". (Open to adjustment/weighting.)

## UX for Markdown
- Table headers use variant names (no A/B).
- Show absolute values and percent deltas: e.g., `12.3 ms (−8.5%)`.
- Colorization (if allowed): green for better, red for worse, gray for missing/mixed.
- Summary bullets: #queries improved/regressed, biggest regression, biggest win, data load delta if available.

## Flow
1) Ensure reporter emits canonical `results.json` alongside existing CSV/MD.
2) Extend comparator to read JSON first; if absent, fall back to CSV parsing (temporary).
3) For N variants: pick baseline (first in run order or user-specified) and generate pairwise comparisons against it. Optionally generate full pairwise matrix if requested.
4) Generate an aggregate summary (N-way) that ranks variants per query and per metric.
5) Store outputs under `projects/<project>/results/<config>/<run>/`:
   - Pairwise: `comparison_<baseline>_vs_<variant>.{json,md}`
   - Summary: `comparison_summary.{json,md}`
6) `full-run` auto-comparison triggers generation of pairwise outputs and the summary when more than one variant is present.

## Implementation Steps
1) (Pre-req) Complete `results_json.md` plan: reporter emits canonical `results.json` / `data_load.json`; comparator can read JSON.
2) Comparator:
   - Input: list of variant result JSON paths; select baseline (default first).
   - Compute per-query deltas and status using the rules above.
   - Emit pairwise `comparison_<baseline>_vs_<variant>.{json,md}`.
   - Emit N-way `comparison_summary.{json,md}` with rankings and win/loss counts.
   - Fallback to CSV only if JSON missing (temporary).
3) CLI:
   - Update `compare` command to accept JSON or CSV; prefer JSON.
   - `full-run` auto-comparison: generate pairwise and summary when more than one variant is run; allow optional `--baseline` override and a flag to generate full matrix.
4) Tests:
   - Unit tests for delta logic/status classification and ranking.
   - Fixture-based comparison tests reading sample `results.json` files for multiple variants.
5) Docs:
   - README note: results now emitted as JSON (canonical) and Markdown/CSV legacy; comparisons consume JSON.
   - Mention auto-comparison outputs per run when multiple variants are executed, including summary file paths.

## Open Questions
- Do we want a weighted overall score (e.g., prioritize p95 over p50, or weight by query count)?
- Should data_load deltas be surfaced in the main summary by default or behind a flag?
- Should we keep CSV fallback indefinitely or schedule removal once JSON is ubiquitous?
