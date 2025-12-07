"""Report generation for benchmark results."""

import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from harness.config import BenchmarkConfig
from harness.workload_runner import ExecutionRecord

logger = logging.getLogger(__name__)


def generate_reports(
    config: BenchmarkConfig,
    execution_records: list[ExecutionRecord],
    query_log_metrics: dict[str, dict],
    workload_metadata: dict,
    project_root: Path
) -> None:
    """Generate CSV and Markdown reports from benchmark results.

    Args:
        config: Benchmark configuration
        execution_records: List of query execution records
        query_log_metrics: Dictionary mapping query_id to metrics from query_log
        workload_metadata: Dictionary containing:
            - workload_start_epoch_ms: Workload start time in milliseconds
            - workload_end_epoch_ms: Workload end time in milliseconds
            - workload_elapsed_secs: Actual workload duration in seconds
        project_root: Project root directory for output files
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
        else:
            avg_read_rows = 0
            avg_read_bytes = 0
            avg_memory_usage = 0

        query_stats.append({
            "query_name": query_name,
            "count": count,
            "errors": errors,
            "error_rate": error_rate,
            "qps": qps,
            "p50_ms": p50_ms,
            "p95_ms": p95_ms,
            "p99_ms": p99_ms,
            "avg_read_rows": avg_read_rows,
            "avg_read_bytes": avg_read_bytes,
            "avg_memory_usage": avg_memory_usage,
        })

    # Generate output paths with variant name inserted
    # Replace the filename to include variant: results/foo.csv -> results/foo_variant.csv
    csv_output = Path(config.metrics.output_csv)
    csv_filename = f"{csv_output.stem}_{config.variant}{csv_output.suffix}"
    csv_path = project_root / csv_output.parent / csv_filename

    md_output = Path(config.metrics.output_md)
    md_filename = f"{md_output.stem}_{config.variant}{md_output.suffix}"
    md_path = project_root / md_output.parent / md_filename

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

    logger.info(f"Results saved: {csv_path.relative_to(project_root.parent.parent)}")


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
        f.write("query_name,count,errors,error_rate,qps,p50_ms,p95_ms,p99_ms,avg_read_rows,avg_read_bytes,avg_memory_usage\n")

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
        f.write("| Query Name | Count | Errors | Error Rate | QPS | p50 (ms) | p95 (ms) | p99 (ms) | Avg Rows Read | Avg Bytes Read | Avg Memory (bytes) |\n")
        f.write("|------------|-------|--------|------------|-----|----------|----------|----------|---------------|----------------|--------------------|\n")

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
