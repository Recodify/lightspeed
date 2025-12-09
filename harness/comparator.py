"""Comparison of benchmark results from different runs."""

import json
import logging
from pathlib import Path

import pandas as pd

from harness.utils import format_bytes

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


def _load_metadata(path: str) -> dict:
    """Load metadata from results.json if available."""
    path_obj = Path(path)

    if path_obj.is_dir():
        json_file = path_obj / "results.json"
        if json_file.exists():
            path_obj = json_file
        else:
            return {}

    if path_obj.suffix != ".json":
        candidate_json = path_obj.with_suffix(".json")
        if candidate_json.exists():
            path_obj = candidate_json

    if not path_obj.exists() or path_obj.suffix != ".json":
        return {}

    try:
        with open(path_obj, "r") as f:
            data = json.load(f)
        return data.get("metadata", {})
    except Exception as e:
        logger.warning(f"Failed to load metadata from {path_obj}: {e}")
        return {}


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


def compare_all_variants(variant_results: list[tuple[str, str]], output_path: str) -> None:
    """Compare N benchmark variants and generate comprehensive comparison report.

    Args:
        variant_results: List of (variant_name, results_path) tuples
        output_path: Path for output Markdown comparison report

    Raises:
        FileNotFoundError: If any results file doesn't exist
        ValueError: If results files have invalid format or less than 2 variants
    """
    logger.info(f"Comparing {len(variant_results)} variants")

    # Validation
    if len(variant_results) < 2:
        raise ValueError("N-way comparison requires at least 2 variants")

    # Load all results and metadata
    all_data = {}
    metadata_by_variant = {}
    for variant_name, result_path in variant_results:
        df = _load_results(result_path)
        all_data[variant_name] = df
        metadata_by_variant[variant_name] = _load_metadata(result_path)
        logger.debug(f"Loaded {len(df)} queries for variant '{variant_name}'")

    # Build unified query list (union of all queries)
    all_queries = set()
    for df in all_data.values():
        all_queries.update(df['query_name'].tolist())
    all_queries = sorted(all_queries)

    logger.debug(f"Found {len(all_queries)} unique queries across all variants")

    # For each query, aggregate metrics from all variants
    comparison_data = []
    for query_name in all_queries:
        query_comparison = _compare_query_across_variants(query_name, all_data)
        comparison_data.append(query_comparison)

    # Calculate rankings
    rankings = _calculate_rankings(comparison_data, [v[0] for v in variant_results])

    # Determine overall winner
    winner_summary = _determine_overall_winner(comparison_data, [v[0] for v in variant_results])

    # Generate Markdown report
    _generate_nway_report(
        output_path,
        variant_results,
        comparison_data,
        rankings,
        winner_summary,
        metadata_by_variant,
    )

    logger.info(f"N-way comparison report written to {output_path}")


def _compare_query_across_variants(
    query_name: str,
    all_data: dict[str, pd.DataFrame]
) -> dict:
    """Compare single query across all variants.

    Args:
        query_name: Name of the query to compare
        all_data: Dictionary mapping variant_name to DataFrame with results

    Returns:
        Dictionary with query metrics across all variants plus best variant per metric
    """
    metrics = {
        'p50_ms': {},
        'p95_ms': {},
        'p99_ms': {},
        'avg_query_duration_ms': {},
        'qps': {},
        'avg_read_rows': {},
        'avg_read_bytes': {},
        'avg_memory_usage': {},
        'error_rate': {},
    }

    variants_with_query = []

    # Collect metrics from each variant
    for variant_name, df in all_data.items():
        query_rows = df[df['query_name'] == query_name]
        if len(query_rows) == 0:
            continue  # Query doesn't exist in this variant

        variants_with_query.append(variant_name)
        row = query_rows.iloc[0]

        for metric_name in metrics.keys():
            if metric_name in row and not pd.isna(row[metric_name]):
                metrics[metric_name][variant_name] = row[metric_name]

    # Determine best variant for each metric
    best_variant = {}
    for metric_name, variant_values in metrics.items():
        if not variant_values:
            continue

        if metric_name == 'qps':  # Higher is better
            best_value = max(variant_values.values())
            # Handle ties - list all winners
            best_variant[metric_name] = [k for k, v in variant_values.items() if v == best_value]
        else:  # Lower is better
            best_value = min(variant_values.values())
            # Handle ties - list all winners
            best_variant[metric_name] = [k for k, v in variant_values.items() if v == best_value]

    return {
        'query_name': query_name,
        'variants_with_query': variants_with_query,
        'metrics': metrics,
        'best_variant': best_variant
    }


def _calculate_rankings(
    comparison_data: list[dict],
    all_variants: list[str]
) -> dict:
    """Calculate rankings for each key metric.

    Returns ranking of variants by average p50, p95, and qps across all queries.
    """
    # Aggregate metrics per variant
    variant_metrics = {v: {'p50': [], 'p95': [], 'qps': []} for v in all_variants}

    for query_comp in comparison_data:
        for metric_key, result_key in [
            ('p50_ms', 'p50'),
            ('p95_ms', 'p95'),
            ('qps', 'qps')
        ]:
            for variant, value in query_comp['metrics'][metric_key].items():
                variant_metrics[variant][result_key].append(value)

    # Calculate averages and rank
    rankings = {}
    for metric in ['p50', 'p95', 'qps']:
        ranked = []
        for variant in all_variants:
            values = variant_metrics[variant][metric]
            if values:
                avg_value = sum(values) / len(values)
                ranked.append((variant, avg_value))

        # Sort: ascending for latency, descending for throughput
        reverse = (metric == 'qps')
        ranked.sort(key=lambda x: x[1], reverse=reverse)
        rankings[f'by_{metric}'] = ranked

    return rankings


def _determine_overall_winner(
    comparison_data: list[dict],
    all_variants: list[str]
) -> dict:
    """Determine overall winner based on per-query wins.

    Returns summary with overall winner and win counts per variant.
    """
    wins_per_variant = {v: 0 for v in all_variants}

    # Count wins per variant (using p50 as primary metric)
    for query_comp in comparison_data:
        best_variants = query_comp['best_variant'].get('p50_ms', [])
        if best_variants:
            # If tie, award win to all tied variants
            for variant in best_variants:
                if variant in wins_per_variant:
                    wins_per_variant[variant] += 1

    # Find overall winner (variant with most wins)
    if wins_per_variant:
        overall_winner = max(wins_per_variant.items(), key=lambda x: x[1])[0]
    else:
        overall_winner = "N/A"

    return {
        'overall_winner': overall_winner,
        'wins_per_variant': wins_per_variant,
    }


def _generate_nway_report(
    output_path: str,
    variant_results: list[tuple[str, str]],
    comparison_data: list[dict],
    rankings: dict,
    winner_summary: dict,
    metadata_by_variant: dict,
) -> None:
    """Generate comprehensive N-way comparison Markdown report."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        # Header
        f.write("# N-Way Benchmark Comparison\n\n")

        # Metadata table
        _write_metadata_table(f, variant_results, metadata_by_variant)

        # Executive summary
        _write_executive_summary(f, winner_summary)

        # Section 1: Side-by-side comparison
        f.write("## Section 1: Side-by-Side Performance Comparison\n\n")
        for query_comp in comparison_data:
            _write_query_comparison_table(f, query_comp, variant_results)

        # Section 2: Rankings
        f.write("## Section 2: Rankings\n\n")
        _write_rankings(f, rankings)

        # Interpretation guide
        _write_interpretation_guide(f)


def _write_metadata_table(f, variant_results, metadata_by_variant):
    """Write variants metadata table."""
    f.write(f"**Variants Compared**: {len(variant_results)} variants\n\n")
    f.write("| Variant | Results Path | Size on Disk | Server Memory Usage |\n")
    f.write("|---------|--------------|-------------|---------------------|\n")
    for variant_name, result_path in variant_results:
        metadata = metadata_by_variant.get(variant_name, {}) if metadata_by_variant else {}
        resources = metadata.get("variant_resources", {})
        size_on_disk = resources.get("size_on_disk_bytes")
        server_memory = resources.get("server_memory_usage_bytes")
        size_display = format_bytes(size_on_disk) if size_on_disk is not None else "N/A"
        memory_display = format_bytes(server_memory) if server_memory is not None else "N/A"
        f.write(
            f"| {variant_name} | `{result_path}` | {size_display} | {memory_display} |\n"
        )
    f.write("\n---\n\n")


def _write_executive_summary(f, winner_summary):
    """Write executive summary section."""
    f.write("## Executive Summary\n\n")
    f.write(f"**Overall Winner**: {winner_summary['overall_winner']}\n\n")
    f.write("**Win Distribution** (based on p50 latency):\n")
    total_wins = sum(winner_summary['wins_per_variant'].values())
    for variant, wins in sorted(
        winner_summary['wins_per_variant'].items(),
        key=lambda x: x[1],
        reverse=True
    ):
        pct = (wins / total_wins * 100) if total_wins > 0 else 0
        f.write(f"- {variant}: {wins} queries ({pct:.1f}%)\n")
    f.write("\n---\n\n")


def _write_query_comparison_table(f, query_comp, variant_results):
    """Write side-by-side comparison table for single query."""
    query_name = query_comp['query_name']
    variants_with_query = query_comp['variants_with_query']
    all_variants = [v[0] for v in variant_results]

    f.write(f"### Query: {query_name}\n")
    f.write(f"*(Available in: {', '.join(variants_with_query)})*\n\n")

    # Table header
    header = "| Metric |"
    for variant in all_variants:
        header += f" {variant} |"
    header += " Best |"
    for variant in all_variants:
        header += f" Δ ({variant}) |"
    f.write(header + "\n")

    # Table separator
    sep = "|--------|"
    for _ in all_variants:
        sep += "----------|"
    sep += "------|"
    for _ in all_variants:
        sep += "------------------|"
    f.write(sep + "\n")

    # Metrics rows
    metric_display = [
        ('p50_ms', 'p50 (ms)', 'lower'),
        ('p95_ms', 'p95 (ms)', 'lower'),
        ('avg_query_duration_ms', 'Avg (ms)', 'lower'),
        ('qps', 'QPS', 'higher'),
    ]

    for metric_key, metric_label, direction in metric_display:
        row = f"| {metric_label} |"

        # Variant values
        variant_vals = {}
        for variant in all_variants:
            val = query_comp['metrics'][metric_key].get(variant)
            if val is None:
                row += " N/A |"
                variant_vals[variant] = None
            else:
                row += f" {val:.2f} |"
                variant_vals[variant] = val

        # Best performer(s)
        best_variants = query_comp['best_variant'].get(metric_key, [])
        if not best_variants:
            row += " N/A |"
            best_val = None
        else:
            row += f" {', '.join(best_variants)} |"
            # Get best value from first best variant
            best_val = variant_vals.get(best_variants[0])

        # Delta from best for each variant
        for variant in all_variants:
            val = variant_vals[variant]
            if val is None:
                row += " N/A |"
            elif best_val is None or variant in best_variants:
                row += " - |"
            else:
                delta_pct = ((val - best_val) / best_val) * 100
                row += f" {delta_pct:+.1f}% |"

        f.write(row + "\n")

    # Winner line
    best_for_query = query_comp['best_variant'].get('p50_ms', [])
    winner_text = ', '.join(best_for_query) if best_for_query else 'N/A'
    f.write(f"\n**Winner for this query**: {winner_text}\n\n")
    f.write("---\n\n")


def _write_rankings(f, rankings):
    """Write rankings section."""
    ranking_configs = [
        ('by_p50', 'p50 Latency', 'ms', 'lower'),
        ('by_p95', 'p95 Latency', 'ms', 'lower'),
        ('by_qps', 'QPS', 'qps', 'higher'),
    ]

    for ranking_key, title, unit, direction in ranking_configs:
        f.write(f"### Ranking by {title} (Average Across All Queries)\n\n")
        f.write(f"| Rank | Variant | Avg {title}")
        if unit != 'qps':
            f.write(f" ({unit})")
        f.write(" | Relative to Best |\n")
        f.write("|------|---------|--------------|------------------|\n")

        ranked = rankings[ranking_key]
        if not ranked:
            f.write("| - | No data | - | - |\n")
            f.write("\n")
            continue

        best_val = ranked[0][1]
        for rank, (variant, avg_val) in enumerate(ranked, 1):
            if rank == 1:
                delta = "-"
            else:
                delta_pct = ((avg_val - best_val) / best_val) * 100
                delta = f"{delta_pct:+.1f}%"

            f.write(f"| {rank} | {variant} | {avg_val:.2f} | {delta} |\n")

        f.write("\n")


def _write_interpretation_guide(f):
    """Write interpretation guide section."""
    f.write("---\n\n")
    f.write("## Interpretation Guide\n\n")
    f.write("### Metrics\n")
    f.write("- **p50 (ms)**: Median query latency - 50% of queries complete faster\n")
    f.write("- **p95 (ms)**: 95th percentile latency - only 5% of queries are slower\n")
    f.write("- **Avg (ms)**: Average query duration across all executions\n")
    f.write("- **QPS**: Queries per second (throughput)\n\n")

    f.write("### Performance Direction\n")
    f.write("- **Latency** (p50, p95, Avg): Lower is better\n")
    f.write("- **Throughput** (QPS): Higher is better\n\n")

    f.write("### Symbols\n")
    f.write("- **N/A**: Query not available in this variant\n")
    f.write("- **-**: This variant is the best performer\n")
    f.write("- **Δ (delta)**: Percentage difference from best performer\n")
    f.write("  - Positive Δ in latency = slower (worse)\n")
    f.write("  - Negative Δ in latency = faster (better)\n")
    f.write("  - Positive Δ in QPS = higher throughput (better)\n")
    f.write("  - Negative Δ in QPS = lower throughput (worse)\n")
