"""Comparison of benchmark results from different runs."""

import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def _load_results(path: str) -> pd.DataFrame:
    """Load benchmark results from JSON (preferred) or CSV (fallback).

    Args:
        path: Path to results file (can be JSON, CSV, or directory containing them)

    Returns:
        DataFrame with query results

    Raises:
        FileNotFoundError: If no valid results file is found
        ValueError: If file format is invalid
    """
    path_obj = Path(path)

    # If path is a directory, look for results.json or results.csv
    if path_obj.is_dir():
        json_file = path_obj / "results.json"
        csv_file = path_obj / "results.csv"

        if json_file.exists():
            path_obj = json_file
        elif csv_file.exists():
            path_obj = csv_file
        else:
            raise FileNotFoundError(f"No results.json or results.csv found in {path}")

    # Try JSON first
    if path_obj.suffix == '.json' or (path_obj.suffix != '.csv' and path_obj.with_suffix('.json').exists()):
        json_path = path_obj if path_obj.suffix == '.json' else path_obj.with_suffix('.json')
        if json_path.exists():
            logger.debug(f"Loading results from JSON: {json_path}")
            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)

                # Extract query stats from JSON structure
                if 'queries' in data:
                    df = pd.DataFrame(data['queries'])
                    logger.debug(f"Loaded {len(df)} queries from JSON")
                    return df
                else:
                    raise ValueError(f"Invalid JSON format: missing 'queries' field in {json_path}")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON {json_path}: {e}. Trying CSV fallback.")
            except Exception as e:
                logger.warning(f"Failed to load JSON {json_path}: {e}. Trying CSV fallback.")

    # Fall back to CSV
    csv_path = path_obj if path_obj.suffix == '.csv' else path_obj.with_suffix('.csv')
    if csv_path.exists():
        logger.debug(f"Loading results from CSV: {csv_path}")
        try:
            df = pd.read_csv(csv_path, comment='#')
            logger.debug(f"Loaded {len(df)} queries from CSV")
            return df
        except Exception as e:
            raise ValueError(f"Failed to load CSV {csv_path}: {e}")

    # Neither JSON nor CSV found
    raise FileNotFoundError(f"No results file found at {path} (tried .json and .csv)")


def compare_results(csv_a_path: str, csv_b_path: str, output_path: str) -> None:
    """Compare two benchmark result files and generate comparison report.

    Args:
        csv_a_path: Path to first (baseline) results file (JSON, CSV, or directory)
        csv_b_path: Path to second (comparison) results file (JSON, CSV, or directory)
        output_path: Path for output Markdown comparison report

    Raises:
        FileNotFoundError: If either results file doesn't exist
        ValueError: If results files have invalid format
    """
    logger.info(f"Comparing results: {csv_a_path} vs {csv_b_path}")

    # Load results from JSON (preferred) or CSV (fallback)
    try:
        df_a = _load_results(csv_a_path)
        df_b = _load_results(csv_b_path)
    except FileNotFoundError as e:
        logger.error(f"Results file not found: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to load results files: {e}")
        raise ValueError(f"Invalid results format: {e}")

    # Validate required columns
    required_cols = ['query_name', 'count', 'qps', 'p50_ms', 'p95_ms', 'p99_ms', 'avg_query_duration_ms']
    for col in required_cols:
        if col not in df_a.columns:
            raise ValueError(f"Column '{col}' missing from {csv_a_path}")
        if col not in df_b.columns:
            raise ValueError(f"Column '{col}' missing from {csv_b_path}")

    # Join on query_name
    df_merged = pd.merge(
        df_a,
        df_b,
        on='query_name',
        how='outer',
        suffixes=('_a', '_b')
    )

    # Calculate deltas for each query
    comparisons = []
    for _, row in df_merged.iterrows():
        query_name = row['query_name']

        # Check if query exists in both datasets
        missing_in_a = pd.isna(row.get('count_a'))
        missing_in_b = pd.isna(row.get('count_b'))

        if missing_in_a:
            # Query only in B
            comparisons.append({
                'query_name': query_name,
                'a_p50': 'N/A',
                'b_p50': f"{row['p50_ms_b']:.2f}",
                'delta_p50': 'new',
                'a_p95': 'N/A',
                'b_p95': f"{row['p95_ms_b']:.2f}",
                'delta_p95': 'new',
                'a_avg_dur': 'N/A',
                'b_avg_dur': f"{row['avg_query_duration_ms_b']:.2f}",
                'delta_avg_dur': 'new',
                'a_qps': 'N/A',
                'b_qps': f"{row['qps_b']:.2f}",
                'delta_qps': 'new',
            })
        elif missing_in_b:
            # Query only in A
            comparisons.append({
                'query_name': query_name,
                'a_p50': f"{row['p50_ms_a']:.2f}",
                'b_p50': 'N/A',
                'delta_p50': 'removed',
                'a_p95': f"{row['p95_ms_a']:.2f}",
                'b_p95': 'N/A',
                'delta_p95': 'removed',
                'a_avg_dur': f"{row['avg_query_duration_ms_a']:.2f}",
                'b_avg_dur': 'N/A',
                'delta_avg_dur': 'removed',
                'a_qps': f"{row['qps_a']:.2f}",
                'b_qps': 'N/A',
                'delta_qps': 'removed',
            })
        else:
            # Query in both - calculate deltas
            p50_a = row['p50_ms_a']
            p50_b = row['p50_ms_b']
            p95_a = row['p95_ms_a']
            p95_b = row['p95_ms_b']
            avg_dur_a = row['avg_query_duration_ms_a']
            avg_dur_b = row['avg_query_duration_ms_b']
            qps_a = row['qps_a']
            qps_b = row['qps_b']

            # Calculate percentage changes, handling division by zero
            if p50_a == 0:
                delta_p50 = '+∞' if p50_b > 0 else '0%'
            else:
                delta_p50 = f"{((p50_b - p50_a) / p50_a) * 100:+.2f}%"

            if p95_a == 0:
                delta_p95 = '+∞' if p95_b > 0 else '0%'
            else:
                delta_p95 = f"{((p95_b - p95_a) / p95_a) * 100:+.2f}%"

            if avg_dur_a == 0:
                delta_avg_dur = '+∞' if avg_dur_b > 0 else '0%'
            else:
                delta_avg_dur = f"{((avg_dur_b - avg_dur_a) / avg_dur_a) * 100:+.2f}%"

            if qps_a == 0:
                delta_qps = '+∞' if qps_b > 0 else '0%'
            else:
                delta_qps = f"{((qps_b - qps_a) / qps_a) * 100:+.2f}%"

            comparisons.append({
                'query_name': query_name,
                'a_p50': f"{p50_a:.2f}",
                'b_p50': f"{p50_b:.2f}",
                'delta_p50': delta_p50,
                'a_p95': f"{p95_a:.2f}",
                'b_p95': f"{p95_b:.2f}",
                'delta_p95': delta_p95,
                'a_avg_dur': f"{avg_dur_a:.2f}",
                'b_avg_dur': f"{avg_dur_b:.2f}",
                'delta_avg_dur': delta_avg_dur,
                'a_qps': f"{qps_a:.2f}",
                'b_qps': f"{qps_b:.2f}",
                'delta_qps': delta_qps,
            })

    # Generate Markdown report
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        f.write("# Benchmark Comparison\n\n")
        f.write(f"**Baseline (A):** `{csv_a_path}`\n\n")
        f.write(f"**Comparison (B):** `{csv_b_path}`\n\n")
        f.write("## Performance Comparison\n\n")

        # Write table header
        f.write("| Query | A p50 (ms) | B p50 (ms) | Δ p50 | A p95 (ms) | B p95 (ms) | Δ p95 | A Avg (ms) | B Avg (ms) | Δ Avg | A QPS | B QPS | Δ QPS |\n")
        f.write("|-------|------------|------------|-------|------------|------------|-------|------------|------------|-------|-------|-------|-------|\n")

        # Write table rows
        for comp in comparisons:
            f.write(
                f"| {comp['query_name']} "
                f"| {comp['a_p50']} "
                f"| {comp['b_p50']} "
                f"| {comp['delta_p50']} "
                f"| {comp['a_p95']} "
                f"| {comp['b_p95']} "
                f"| {comp['delta_p95']} "
                f"| {comp['a_avg_dur']} "
                f"| {comp['b_avg_dur']} "
                f"| {comp['delta_avg_dur']} "
                f"| {comp['a_qps']} "
                f"| {comp['b_qps']} "
                f"| {comp['delta_qps']} |\n"
            )

        # Add interpretation guide
        f.write("\n## Interpretation\n\n")
        f.write("- **Positive Δ p50/p95/Avg**: Latency increased (slower)\n")
        f.write("- **Negative Δ p50/p95/Avg**: Latency decreased (faster)\n")
        f.write("- **Positive Δ QPS**: Throughput increased (better)\n")
        f.write("- **Negative Δ QPS**: Throughput decreased (worse)\n")
        f.write("- **new**: Query only in comparison (B)\n")
        f.write("- **removed**: Query only in baseline (A)\n")
        f.write("- **+∞**: Baseline value was zero\n")

    logger.info(f"Comparison report written to {output_path}")
