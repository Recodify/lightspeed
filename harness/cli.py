"""Command-line interface for the ClickHouse benchmarking harness."""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from coolname import generate_slug

from harness.clickhouse_client import ClickHouseClient
from harness.comparator import compare_results, compare_all_variants
from harness.config import (
    compute_project_root,
    compute_variant_root,
    load_config,
    resolve_variant_config,
    validate_config,
)
from harness.data_loader import load_data
from harness.exceptions import HarnessError
from harness.metrics_collector import collect_query_log_metrics
from harness.reporter import generate_reports, generate_data_load_reports
from harness.schema_loader import apply_schema
from harness.utils import setup_logging, sanitize_name
from harness.workload_runner import run_workload

logger = logging.getLogger(__name__)


def generate_run_name(base_path: Path, user_run_name: str | None = None) -> str:
    """Generate or validate a unique run name.

    Args:
        base_path: Base directory for results (e.g., projects/default/results/)
        user_run_name: Optional user-specified run name

    Returns:
        Run name (either user-specified or auto-generated)
    """
    if user_run_name is not None:
        # Use user-specified name as-is
        return user_run_name

    # Generate a 2-part memorable name (adjective-noun)
    run_name = generate_slug(2)

    # Handle the rare collision by generating a new name
    attempt = 1
    while (base_path / run_name).exists():
        run_name = generate_slug(2)
        attempt += 1
        if attempt > 5:  # After 5 attempts, append a number
            run_name = f"{run_name}-{attempt}"
            break

    return run_name


def compute_run_dir(config, project_root: Path, config_name: str, run_name: str) -> Path:
    """Compute the run directory path used by reporter for a variant."""
    csv_output = Path(config.metrics.output_csv)
    results_base = project_root / csv_output.parent

    safe_config_name = sanitize_name(config_name)
    safe_run_name = sanitize_name(run_name)
    safe_variant = sanitize_name(config.variant)

    return results_base / safe_config_name / safe_run_name / safe_variant


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate configuration and test connectivity.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        logger.debug(f"Loading configuration from {args.config}")
        config = load_config(args.config)

        # Resolve variant
        config = resolve_variant_config(config, args.variant)

        logger.debug("Validating configuration...")
        validate_config(config)
        logger.debug("Configuration validation passed")

        logger.debug("Testing ClickHouse connectivity...")
        with ClickHouseClient(config.clickhouse) as client:
            if client.test_connection():
                logger.debug("ClickHouse connection successful")
            else:
                logger.error("ClickHouse connection failed")
                return 1

        logger.debug("Validation complete")
        return 0

    except HarnessError as e:
        logger.error(f"Validation failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error during validation: {e}", exc_info=True)
        return 1


def cmd_init_db(args: argparse.Namespace) -> int:
    """Initialize database schema.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        logger.debug(f"Loading configuration from {args.config}")
        config = load_config(args.config)

        # Resolve variant
        config = resolve_variant_config(config, args.variant)

        # Extract config name and generate/use run name
        config_path = Path(args.config)
        config_name = config_path.stem
        project_root = compute_project_root(config)
        results_base = project_root / "results"
        run_name = generate_run_name(results_base, args.run_name if hasattr(args, 'run_name') else None)
        logger.info(f"Run: {run_name}")

        variant_root = compute_variant_root(config)

        logger.debug("Applying database schema...")
        with ClickHouseClient(config.clickhouse) as client:
            apply_schema(config, client, project_root, variant_root, run_name, config_name)

        logger.debug("Schema applied")
        return 0

    except HarnessError as e:
        logger.error(f"Schema initialization failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error during schema initialization: {e}", exc_info=True)
        return 1


def cmd_load_data(args: argparse.Namespace) -> int:
    """Load data into ClickHouse tables.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        logger.debug(f"Loading configuration from {args.config}")
        config = load_config(args.config)

        # Resolve variant
        config = resolve_variant_config(config, args.variant)

        # Extract config name and generate/use run name
        config_path = Path(args.config)
        config_name = config_path.stem
        project_root = compute_project_root(config)
        results_base = project_root / "results"
        run_name = generate_run_name(results_base, args.run_name if hasattr(args, 'run_name') else None)
        logger.info(f"Run: {run_name}")

        variant_root = compute_variant_root(config)

        logger.debug("Loading data into tables...")
        with ClickHouseClient(config.clickhouse) as client:
            data_load_metrics = load_data(config, client, project_root, variant_root, run_name, config_name)

        generate_data_load_reports(
            config,
            data_load_metrics,
            project_root,
            run_name,
            config_name,
        )

        logger.info(f"Results: projects/{config.project}/results/{config_name}/{run_name}/{config.variant}/")
        logger.debug("Data loaded")
        return 0

    except HarnessError as e:
        logger.error(f"Data loading failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error during data loading: {e}", exc_info=True)
        return 1


def cmd_run_workload(args: argparse.Namespace) -> int:
    """Run workload and collect metrics.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        logger.debug(f"Loading configuration from {args.config}")
        config = load_config(args.config)

        # Resolve variant
        config = resolve_variant_config(config, args.variant)

        # Extract config name from file path
        config_path = Path(args.config)
        config_name = config_path.stem

        project_root = compute_project_root(config)
        variant_root = compute_variant_root(config)

        # Generate or use specified run name
        results_base = project_root / "results"
        run_name = generate_run_name(results_base, args.run_name if hasattr(args, 'run_name') else None)

        logger.info(f"Run: {run_name}")

        logger.debug("Running workload...")
        workload_result = run_workload(config, project_root, variant_root, run_name, config_name)

        execution_records = workload_result["records"]
        workload_metadata = {
            "workload_start_epoch_ms": workload_result["workload_start_epoch_ms"],
            "workload_end_epoch_ms": workload_result["workload_end_epoch_ms"],
            "workload_elapsed_secs": workload_result["workload_elapsed_secs"],
        }

        logger.debug(f"Workload completed: {len(execution_records)} queries executed")

        # Convert epoch milliseconds to datetime for metrics collection
        start_time = datetime.fromtimestamp(workload_result["workload_start_epoch_ms"] / 1000)
        end_time = datetime.fromtimestamp(workload_result["workload_end_epoch_ms"] / 1000)

        # Collect metrics from query_log
        logger.debug("Collecting metrics from query_log...")
        with ClickHouseClient(config.clickhouse) as client:
            query_log_metrics = collect_query_log_metrics(
                config,
                client,
                execution_records,
                start_time,
                end_time,
                workload_result.get("query_id_prefix"),
            )

        # Generate reports with run_name and config_name
        logger.debug("Generating reports...")
        generate_reports(
            config,
            execution_records,
            query_log_metrics,
            workload_metadata,
            project_root,
            run_name,
            config_name,
        )

        logger.info(f"Results: projects/{config.project}/results/{config_name}/{run_name}/{config.variant}/")
        logger.debug("Workload execution and reporting complete")
        return 0

    except HarnessError as e:
        logger.error(f"Workload execution failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error during workload execution: {e}", exc_info=True)
        return 1


def cmd_full_run(args: argparse.Namespace) -> int:
    """Run complete benchmark: validate, init-db (if fresh), load-data, run-workload.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        logger.debug(f"Loading configuration from {args.config}")
        base_config = load_config(args.config)

        # Extract config name from file path (e.g., "example_basic" from "example_basic.yml")
        config_path = Path(args.config)
        config_name = config_path.stem

        # Generate or use specified run name
        project_root = compute_project_root(base_config)
        results_base = project_root / "results"
        run_name = generate_run_name(results_base, args.run_name if hasattr(args, 'run_name') else None)

        logger.info(f"Run: {run_name}")

        # Determine which variants to run
        # If --variant is explicitly provided, run only that variant
        # If --variant is not provided and config has variants, run ALL variants
        # If --variant is not provided and config has no variants, use "default"

        if hasattr(args, 'variant') and args.variant != "default":
            # User explicitly specified a variant
            variants_to_run = [args.variant]
        elif base_config.variants is not None:
            # Config has variants, run all of them
            variants_to_run = list(base_config.variants.keys())
            logger.info(f"Running all variants: {', '.join(variants_to_run)}")
        else:
            # No variants in config, use default
            variants_to_run = ["default"]

        run_results: list[tuple[str, Path]] = []

        # Run each variant
        for variant_name in variants_to_run:
            # Resolve variant
            config = resolve_variant_config(base_config, variant_name)
            data_load_metrics = None

            # High-level banner
            logger.info("=" * 60)
            logger.info(f"Starting benchmark: {config.project} / {config.variant}")
            logger.info(f"Workload: {config.workload.name} ({config.workload.concurrency} workers, {config.workload.duration_seconds}s)")
            logger.info("=" * 60)

            # If dry-run, only validate
            if args.dry_run:
                logger.info("Dry-run mode: validating only")
                return cmd_validate(args)

            # Step 1: Validate
            logger.info("[1/4] Validating configuration...")
            validate_config(config)

            # Step 2: Initialize database if fresh schema requested
            if config.schema.fresh:
                logger.info("[2/4] Initializing database (fresh schema)...")
                variant_root = compute_variant_root(config)
                with ClickHouseClient(config.clickhouse) as client:
                    apply_schema(config, client, project_root, variant_root, run_name, config_name)
            else:
                logger.info("[2/4] Skipping schema initialization (fresh=False)")

            # Step 3: Load data
            logger.info("[3/4] Loading data...")
            variant_root = compute_variant_root(config)
            with ClickHouseClient(config.clickhouse) as client:
                data_load_metrics = load_data(config, client, project_root, variant_root, run_name, config_name)

            # Step 4: Run workload
            logger.info("[4/4] Running workload...")

            # Run workload inline to pass run_name to reporter
            variant_root = compute_variant_root(config)

            logger.debug("Running workload...")
            workload_result = run_workload(config, project_root, variant_root, run_name, config_name)

            execution_records = workload_result["records"]
            workload_metadata = {
                "workload_start_epoch_ms": workload_result["workload_start_epoch_ms"],
                "workload_end_epoch_ms": workload_result["workload_end_epoch_ms"],
                "workload_elapsed_secs": workload_result["workload_elapsed_secs"],
            }

            logger.debug(f"Workload completed: {len(execution_records)} queries executed")

            # Convert epoch milliseconds to datetime for metrics collection
            start_time = datetime.fromtimestamp(workload_result["workload_start_epoch_ms"] / 1000)
            end_time = datetime.fromtimestamp(workload_result["workload_end_epoch_ms"] / 1000)

            # Collect metrics from query_log
            logger.debug("Collecting metrics from query_log...")
            with ClickHouseClient(config.clickhouse) as client:
                query_log_metrics = collect_query_log_metrics(
                    config,
                    client,
                    execution_records,
                    start_time,
                    end_time,
                    workload_result.get("query_id_prefix"),
                )

            # Generate reports with run_name and config_name
            logger.debug("Generating reports...")
            generate_reports(
                config,
                execution_records,
                query_log_metrics,
                workload_metadata,
                project_root,
                run_name,
                config_name,
                data_load_metrics=data_load_metrics,
            )

            # Track result path for later comparisons (prefer JSON)
            run_dir = compute_run_dir(config, project_root, config_name, run_name)
            result_json = run_dir / "results.json"
            run_results.append((variant_name, result_json))

            logger.info("=" * 60)
            logger.info(f"Benchmark completed: {config.variant}")
            logger.info(f"Results: projects/{config.project}/results/{config_name}/{run_name}/{config.variant}/")
            logger.info("=" * 60)

        # Perform N-way comparison when multiple variants are run
        if len(run_results) > 1:
            comparison_root = run_results[0][1].parent.parent  # .../<config>/<run>/
            output_path = comparison_root / "comparison_all_variants.md"
            try:
                compare_all_variants(run_results, str(output_path))
                rel_out = output_path.relative_to(project_root.parent.parent)
                logger.info(f"N-way comparison complete: {rel_out}")
            except Exception as e:
                logger.error(f"N-way comparison failed: {e}")

        # All variants completed successfully
        return 0

    except HarnessError as e:
        logger.error(f"Full-run failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error during full-run: {e}", exc_info=True)
        return 1


def cmd_compare(args: argparse.Namespace) -> int:
    """Compare two benchmark result files (JSON or CSV).

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        logger.info(f"Comparing {args.csv_a} vs {args.csv_b}")

        compare_results(args.csv_a, args.csv_b, args.output)

        logger.info(f"Comparison complete: {args.output}")
        return 0

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except ValueError as e:
        logger.error(f"Invalid results file: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error during comparison: {e}", exc_info=True)
        return 1


def main() -> int:
    """Main entry point for CLI.

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="ClickHouse Benchmarking Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # validate command
    parser_validate = subparsers.add_parser(
        "validate",
        help="Validate configuration and test ClickHouse connectivity",
    )
    parser_validate.add_argument("--config", type=str, required=True, help="Path to configuration YAML file")
    parser_validate.add_argument("--variant", type=str, default="default", help="Variant to run (default: default)")
    parser_validate.add_argument("--verbose", action="store_true", help="Enable verbose logging (DEBUG level)")

    # init-db command
    parser_init_db = subparsers.add_parser(
        "init-db",
        help="Initialize database schema",
    )
    parser_init_db.add_argument("--config", type=str, required=True, help="Path to configuration YAML file")
    parser_init_db.add_argument("--variant", type=str, default="default", help="Variant to run (default: default)")
    parser_init_db.add_argument("--verbose", action="store_true", help="Enable verbose logging (DEBUG level)")
    parser_init_db.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Specify a name for this run (e.g., 'baseline-v1'). If not provided, generates a memorable name like 'brave-penguin'",
    )

    # load-data command
    parser_load_data = subparsers.add_parser(
        "load-data",
        help="Load data into ClickHouse tables",
    )
    parser_load_data.add_argument("--config", type=str, required=True, help="Path to configuration YAML file")
    parser_load_data.add_argument("--variant", type=str, default="default", help="Variant to run (default: default)")
    parser_load_data.add_argument("--verbose", action="store_true", help="Enable verbose logging (DEBUG level)")
    parser_load_data.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Specify a name for this run (e.g., 'baseline-v1'). If not provided, generates a memorable name like 'brave-penguin'",
    )

    # run-workload command
    parser_run_workload = subparsers.add_parser(
        "run-workload",
        help="Run workload and collect metrics",
    )
    parser_run_workload.add_argument("--config", type=str, required=True, help="Path to configuration YAML file")
    parser_run_workload.add_argument("--variant", type=str, default="default", help="Variant to run (default: default)")
    parser_run_workload.add_argument("--verbose", action="store_true", help="Enable verbose logging (DEBUG level)")
    parser_run_workload.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Specify a name for this run (e.g., 'baseline-v1'). If not provided, generates a memorable name like 'brave-penguin'",
    )

    # full-run command
    parser_full_run = subparsers.add_parser(
        "full-run",
        help="Run complete benchmark (validate, init-db if fresh, load-data, run-workload)",
    )
    parser_full_run.add_argument("--config", type=str, required=True, help="Path to configuration YAML file")
    parser_full_run.add_argument("--variant", type=str, default="default", help="Variant to run (default: default)")
    parser_full_run.add_argument("--verbose", action="store_true", help="Enable verbose logging (DEBUG level)")
    parser_full_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry-run mode: validate only, don't execute",
    )
    parser_full_run.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Specify a name for this run (e.g., 'baseline-v1'). If not provided, generates a memorable name like 'brave-penguin'",
    )

    # compare command
    parser_compare = subparsers.add_parser(
        "compare",
        help="Compare two benchmark result files (JSON or CSV)",
    )
    parser_compare.add_argument(
        "csv_a",
        type=str,
        help="Path to first (baseline) results file (JSON, CSV, or directory)",
    )
    parser_compare.add_argument(
        "csv_b",
        type=str,
        help="Path to second (comparison) results file (JSON, CSV, or directory)",
    )
    parser_compare.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path for output Markdown comparison report",
    )
    parser_compare.add_argument("--verbose", action="store_true", help="Enable verbose logging (DEBUG level)")

    # Parse arguments
    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose if hasattr(args, 'verbose') else False)

    # Check if command was provided
    if not args.command:
        parser.print_help()
        return 1

    # Dispatch to command handlers
    if args.command == "validate":
        return cmd_validate(args)
    elif args.command == "init-db":
        return cmd_init_db(args)
    elif args.command == "load-data":
        return cmd_load_data(args)
    elif args.command == "run-workload":
        return cmd_run_workload(args)
    elif args.command == "full-run":
        return cmd_full_run(args)
    elif args.command == "compare":
        return cmd_compare(args)
    else:
        logger.error(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
