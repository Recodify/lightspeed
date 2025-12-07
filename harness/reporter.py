"""Report generation for benchmark results."""

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from harness.config import BenchmarkConfig
from harness.workload_runner import ExecutionRecord
from harness.utils import sanitize_name, format_bytes

logger = logging.getLogger(__name__)


def generate_reports(
    config: BenchmarkConfig,
    execution_records: list[ExecutionRecord],
    query_log_metrics: dict[str, dict],
    workload_metadata: dict,
    project_root: Path,
    run_name: str,
    config_name: str,
    data_load_metrics: dict | None = None,
) -> None:
    """Generate JSON, CSV, and Markdown reports from benchmark results.

    Args:
        config: Benchmark configuration
        execution_records: List of query execution records
        query_log_metrics: Dictionary mapping query_id to metrics from query_log
        workload_metadata: Dictionary containing:
            - workload_start_epoch_ms: Workload start time in milliseconds
            - workload_end_epoch_ms: Workload end time in milliseconds
            - workload_elapsed_secs: Actual workload duration in seconds
        project_root: Project root directory for output files
        run_name: Run name for result isolation (e.g., 'brave-penguin')
        config_name: Config file name (e.g., 'example_basic')
        data_load_metrics: Optional data load metrics to include in reports
    """
    logger.debug("Generating benchmark reports...")

    # Group execution records by query_name
    queries_data = defaultdict(list)
    for record in execution_records:
        queries_data[record.query_name].append(record)

    # Calculate aggregated metrics for each query
    query_stats = []
    for query_name, records in sorted(queries_data.items()):
        count = len(records)
        errors = sum(1 for r in records if not r.success)
        error_rate = errors / count if count > 0 else 0.0

        # Calculate QPS using actual elapsed time
        workload_elapsed_secs = workload_metadata["workload_elapsed_secs"]
        qps = count / workload_elapsed_secs if workload_elapsed_secs > 0 else 0.0

        # Calculate percentiles from duration_ms
        durations = [r.duration_ms for r in records]
        df_durations = pd.Series(durations)
        p50_ms = df_durations.quantile(0.50)
        p95_ms = df_durations.quantile(0.95)
        p99_ms = df_durations.quantile(0.99)

        # Calculate averages from query_log metrics where available
        query_ids = [r.query_id for r in records]
        metrics_available = [query_log_metrics.get(qid) for qid in query_ids if qid in query_log_metrics]

        if metrics_available:
            avg_read_rows = sum(m["read_rows"] for m in metrics_available) / len(metrics_available)
            avg_read_bytes = sum(m["read_bytes"] for m in metrics_available) / len(metrics_available)
            avg_memory_usage = sum(m["memory_usage"] for m in metrics_available) / len(metrics_available)
            avg_query_duration_ms = (sum(m["query_duration_ms"] for m in metrics_available) / len(metrics_available))
        else:
            avg_read_rows = 0
            avg_read_bytes = 0
            avg_memory_usage = 0
            avg_query_duration_ms = 0

        query_stats.append({
            "query_name": query_name,
            "count": count,
            "errors": errors,
            "error_rate": error_rate,
            "qps": qps,
            "p50_ms": p50_ms,
            "p95_ms": p95_ms,
            "p99_ms": p99_ms,
            "avg_query_duration_ms": avg_query_duration_ms,
            "avg_read_rows": avg_read_rows,
            "avg_read_bytes": avg_read_bytes,
            "avg_memory_usage": avg_memory_usage,
        })

    # Generate output paths: results/{config_name}/{run_name}/{variant}/results.*
    run_dir = _build_run_dir(config, project_root, config_name, run_name)
    csv_path = run_dir / Path(config.metrics.output_csv).name
    md_path = run_dir / Path(config.metrics.output_md).name
    json_path = run_dir / "results.json"

    # Generate JSON report (canonical)
    _generate_json_report(
        json_path,
        query_stats,
        workload_metadata,
        config,
        run_name,
        config_name
    )

    # Generate CSV report
    _generate_csv_report(
        csv_path,
        query_stats,
        workload_metadata,
        config
    )

    # Generate Markdown report
    _generate_markdown_report(
        md_path,
        query_stats,
        workload_metadata,
        config
    )

    # Generate data load outputs if provided
    if data_load_metrics is not None:
        data_csv_path = run_dir / Path(config.metrics.data_output_csv).name
        data_json_path = run_dir / "data_load.json"

        _generate_data_load_json(
            data_json_path,
            data_load_metrics,
            config,
            run_name,
            config_name
        )
        _generate_data_load_csv(
            data_csv_path,
            data_load_metrics,
            config
        )
        _write_data_load_markdown(
            md_path,
            data_load_metrics,
            config,
            append=True
        )
        logger.info(f"Data load results saved: {data_json_path.relative_to(project_root.parent.parent)}")

    logger.info(f"Results saved: {json_path.relative_to(project_root.parent.parent)}")


def generate_data_load_reports(
    config: BenchmarkConfig,
    data_load_metrics: dict,
    project_root: Path,
    run_name: str,
    config_name: str,
) -> None:
    """Generate JSON, CSV, and Markdown outputs for data loading only."""
    logger.debug("Generating data load reports...")

    run_dir = _build_run_dir(config, project_root, config_name, run_name)
    data_csv_path = run_dir / Path(config.metrics.data_output_csv).name
    data_json_path = run_dir / "data_load.json"
    md_path = run_dir / Path(config.metrics.output_md).name

    _generate_data_load_json(
        data_json_path,
        data_load_metrics,
        config,
        run_name,
        config_name
    )
    _generate_data_load_csv(
        data_csv_path,
        data_load_metrics,
        config
    )
    _write_data_load_markdown(
        md_path,
        data_load_metrics,
        config,
        append=False
    )

    logger.info(f"Data load results saved: {data_json_path.relative_to(project_root.parent.parent)}")


def _generate_csv_report(
    output_path: Path,
    query_stats: list[dict],
    workload_metadata: dict,
    config: BenchmarkConfig
) -> None:
    """Generate CSV report with metadata as comments."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        # Write metadata as comments
        f.write(f"# workload_start_epoch_ms: {workload_metadata['workload_start_epoch_ms']}\n")
        f.write(f"# workload_end_epoch_ms: {workload_metadata['workload_end_epoch_ms']}\n")
        f.write(f"# workload_elapsed_secs: {workload_metadata['workload_elapsed_secs']}\n")
        f.write(f"# project: {config.project}\n")
        f.write(f"# variant: {config.variant}\n")

        # Write header
        f.write("query_name,count,errors,error_rate,qps,p50_ms,p95_ms,p99_ms,avg_query_duration_ms,avg_read_rows,avg_read_bytes,avg_memory_usage\n")

        # Write data rows
        for stat in query_stats:
            f.write(
                f"{stat['query_name']},"
                f"{stat['count']},"
                f"{stat['errors']},"
                f"{stat['error_rate']:.4f},"
                f"{stat['qps']:.2f},"
                f"{stat['p50_ms']:.2f},"
                f"{stat['p95_ms']:.2f},"
                f"{stat['p99_ms']:.2f},"
                f"{stat['avg_query_duration_ms']:.2f},"
                f"{stat['avg_read_rows']:.0f},"
                f"{stat['avg_read_bytes']:.0f},"
                f"{stat['avg_memory_usage']:.0f}\n"
            )

    logger.debug(f"CSV report written to {output_path}")


def _generate_markdown_report(
    output_path: Path,
    query_stats: list[dict],
    workload_metadata: dict,
    config: BenchmarkConfig
) -> None:
    """Generate Markdown report with formatted tables and summary."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert epoch milliseconds to readable timestamps
    start_dt = datetime.fromtimestamp(workload_metadata['workload_start_epoch_ms'] / 1000)
    end_dt = datetime.fromtimestamp(workload_metadata['workload_end_epoch_ms'] / 1000)

    with open(output_path, "w") as f:
        # Metadata section
        f.write("# Benchmark Results\n\n")
        f.write("## Metadata\n\n")
        f.write(f"- **Project**: {config.project}\n")
        f.write(f"- **Variant**: {config.variant}\n")
        f.write(f"- **Workload**: {config.workload.name}\n")
        f.write(f"- **Concurrency**: {config.workload.concurrency}\n")
        f.write(f"- **Start Time**: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **End Time**: {end_dt.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **Duration**: {workload_metadata['workload_elapsed_secs']:.2f} seconds\n\n")

        # Performance table
        f.write("## Query Performance\n\n")
        f.write("| Query Name | Count | Errors | Error Rate | QPS | p50 (ms) | p95 (ms) | p99 (ms) | Avg Duration (ms) | Avg Rows Read | Avg Bytes Read | Avg Memory (bytes) |\n")
        f.write("|------------|-------|--------|------------|-----|----------|----------|----------|-------------------|---------------|----------------|--------------------|\n")

        for stat in query_stats:
            f.write(
                f"| {stat['query_name']} "
                f"| {stat['count']} "
                f"| {stat['errors']} "
                f"| {stat['error_rate']:.2%} "
                f"| {stat['qps']:.2f} "
                f"| {stat['p50_ms']:.2f} "
                f"| {stat['p95_ms']:.2f} "
                f"| {stat['p99_ms']:.2f} "
                f"| {stat['avg_query_duration_ms']:.2f} "
                f"| {stat['avg_read_rows']:.0f} "
                f"| {stat['avg_read_bytes']:.0f} "
                f"| {stat['avg_memory_usage']:.0f} |\n"
            )

        # Summary section
        f.write("\n## Summary\n\n")
        total_queries = sum(s['count'] for s in query_stats)
        total_errors = sum(s['errors'] for s in query_stats)
        overall_error_rate = total_errors / total_queries if total_queries > 0 else 0.0
        overall_qps = total_queries / workload_metadata['workload_elapsed_secs'] if workload_metadata['workload_elapsed_secs'] > 0 else 0.0

        f.write(f"- **Total Queries Executed**: {total_queries}\n")
        f.write(f"- **Total Errors**: {total_errors}\n")
        f.write(f"- **Overall Error Rate**: {overall_error_rate:.2%}\n")
        f.write(f"- **Overall QPS**: {overall_qps:.2f}\n")

    logger.debug(f"Markdown report written to {output_path}")


def _generate_json_report(
    output_path: Path,
    query_stats: list[dict],
    workload_metadata: dict,
    config: BenchmarkConfig,
    run_name: str,
    config_name: str
) -> None:
    """Generate JSON report with structured data."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Calculate summary statistics
    total_queries = sum(s['count'] for s in query_stats)
    total_errors = sum(s['errors'] for s in query_stats)
    overall_error_rate = total_errors / total_queries if total_queries > 0 else 0.0
    overall_qps = total_queries / workload_metadata['workload_elapsed_secs'] if workload_metadata['workload_elapsed_secs'] > 0 else 0.0

    # Build structured JSON output
    report_data = {
        "schema_version": 1,
        "metadata": {
            "project": config.project,
            "variant": config.variant,
            "run_name": run_name,
            "config_name": config_name,
            "workload": {
                "name": config.workload.name,
                "concurrency": config.workload.concurrency,
                "duration_seconds": config.workload.duration_seconds
            },
            "workload_start_epoch_ms": workload_metadata['workload_start_epoch_ms'],
            "workload_end_epoch_ms": workload_metadata['workload_end_epoch_ms'],
            "workload_elapsed_secs": workload_metadata['workload_elapsed_secs']
        },
        "queries": query_stats,
        "summary": {
            "total_queries": total_queries,
            "total_errors": total_errors,
            "overall_error_rate": overall_error_rate,
            "overall_qps": overall_qps
        }
    }

    with open(output_path, "w") as f:
        json.dump(report_data, f, indent=2)

    logger.debug(f"JSON report written to {output_path}")


def _generate_data_load_csv(
    output_path: Path,
    data_load_metrics: dict,
    config: BenchmarkConfig
) -> None:
    """Generate CSV with per-file data load metrics."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    files = data_load_metrics.get("files", [])

    with open(output_path, "w") as f:
        f.write(f"# project: {config.project}\n")
        f.write(f"# variant: {config.variant}\n")
        f.write(f"# total_files: {data_load_metrics.get('files_loaded', len(files))}\n")
        f.write(f"# total_bytes: {data_load_metrics.get('bytes_transferred', 0)}\n")
        f.write(f"# duration_secs: {data_load_metrics.get('duration_secs', 0):.4f}\n")
        f.write(f"# duration_ms: {data_load_metrics.get('duration_ms', data_load_metrics.get('duration_secs', 0) * 1000):.2f}\n")
        f.write(f"# throughput_mb_s: {data_load_metrics.get('throughput_mb_s', 0):.4f}\n")
        f.write("table,file,source,bytes,duration_ms,throughput_mb_s\n")

        for entry in files:
            f.write(
                f"{entry.get('table','')},"
                f"{entry.get('file','')},"
                f"{entry.get('source','')},"
                f"{entry.get('bytes',0)},"
                f"{entry.get('duration_ms', entry.get('duration_secs',0) * 1000):.2f},"
                f"{entry.get('throughput_mb_s',0):.4f}\n"
            )

    logger.debug(f"Data load CSV written to {output_path}")


def _write_data_load_markdown(
    output_path: Path,
    data_load_metrics: dict,
    config: BenchmarkConfig,
    append: bool,
) -> None:
    """Write or append a Data Load section to a Markdown report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    files = data_load_metrics.get("files", [])

    already_exists = output_path.exists()
    mode = "a" if append and already_exists else "w"

    with open(output_path, mode) as f:
        if mode == "a" and already_exists:
            f.write("\n\n")
        else:
            f.write("# Benchmark Results\n\n")

        f.write("## Data Load\n\n")
        f.write(f"- **Project**: {config.project}\n")
        f.write(f"- **Variant**: {config.variant}\n")
        f.write(f"- **Load Method**: {config.data.load_method}\n")
        f.write(f"- **Truncate Before Load**: {config.data.truncate_before_load}\n")
        f.write(f"- **Total Files**: {data_load_metrics.get('files_loaded', len(files))}\n")
        f.write(f"- **Total Bytes**: {format_bytes(data_load_metrics.get('bytes_transferred', 0))}\n")
        duration_secs = data_load_metrics.get('duration_secs', 0)
        duration_ms = data_load_metrics.get('duration_ms', duration_secs * 1000)
        f.write(f"- **Duration**: {duration_secs:.2f} seconds ({duration_ms:.0f} ms)\n")
        f.write(f"- **Throughput**: {data_load_metrics.get('throughput_mb_s', 0):.2f} MB/s\n\n")

        f.write("| Table | File | Source | Bytes | Duration (ms) | Throughput (MB/s) |\n")
        f.write("|-------|------|--------|-------|---------------|-------------------|\n")

        for entry in files:
            f.write(
                f"| {entry.get('table','')} "
                f"| {entry.get('file','')} "
                f"| {entry.get('source','')} "
                f"| {format_bytes(entry.get('bytes', 0))} "
                f"| {entry.get('duration_ms', entry.get('duration_secs', 0) * 1000):.0f} "
                f"| {entry.get('throughput_mb_s', 0):.2f} |\n"
            )

    logger.debug(f"Data load markdown written to {output_path} (append={append})")


def _generate_data_load_json(
    output_path: Path,
    data_load_metrics: dict,
    config: BenchmarkConfig,
    run_name: str,
    config_name: str
) -> None:
    """Generate JSON with data load metrics."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    files = data_load_metrics.get("files", [])

    # Build structured JSON output
    report_data = {
        "schema_version": 1,
        "metadata": {
            "project": config.project,
            "variant": config.variant,
            "run_name": run_name,
            "config_name": config_name,
            "load_method": config.data.load_method,
            "truncate_before_load": config.data.truncate_before_load
        },
        "totals": {
            "files_loaded": data_load_metrics.get('files_loaded', len(files)),
            "bytes_transferred": data_load_metrics.get('bytes_transferred', 0),
            "duration_ms": data_load_metrics.get('duration_ms', data_load_metrics.get('duration_secs', 0) * 1000),
            "duration_secs": data_load_metrics.get('duration_secs', 0),
            "throughput_mb_s": data_load_metrics.get('throughput_mb_s', 0)
        },
        "ingest": files
    }

    with open(output_path, "w") as f:
        json.dump(report_data, f, indent=2)

    logger.debug(f"Data load JSON written to {output_path}")


def _build_run_dir(
    config: BenchmarkConfig,
    project_root: Path,
    config_name: str,
    run_name: str
) -> Path:
    """Build variant run directory based on config, run, and variant names."""
    safe_config_name = sanitize_name(config_name)
    safe_run_name = sanitize_name(run_name)
    safe_variant = sanitize_name(config.variant)

    csv_output = Path(config.metrics.output_csv)
    results_base = project_root / csv_output.parent
    return results_base / safe_config_name / safe_run_name / safe_variant
