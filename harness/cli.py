"""Command-line interface for the ClickHouse benchmarking harness."""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from harness.clickhouse_client import ClickHouseClient
from harness.comparator import compare_results
from harness.config import (
    compute_project_root,
    compute_variant_root,
    load_config,
    validate_config,
)
from harness.data_loader import load_data
from harness.exceptions import HarnessError
from harness.metrics_collector import collect_query_log_metrics
from harness.reporter import generate_reports
from harness.schema_loader import apply_schema
from harness.utils import setup_logging
from harness.workload_runner import run_workload

logger = logging.getLogger(__name__)


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate configuration and test connectivity.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        logger.info(f"Loading configuration from {args.config}")
        config = load_config(args.config)

        logger.info("Validating configuration...")
        validate_config(config)
        logger.info("Configuration validation passed")

        logger.info("Testing ClickHouse connectivity...")
        with ClickHouseClient(config.clickhouse) as client:
            if client.test_connection():
                logger.info("ClickHouse connection successful")
            else:
                logger.error("ClickHouse connection failed")
                return 1

        logger.info("All validation checks passed")
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
        logger.info(f"Loading configuration from {args.config}")
        config = load_config(args.config)

        project_root = compute_project_root(config)
        variant_root = compute_variant_root(config)

        logger.info("Applying database schema...")
        with ClickHouseClient(config.clickhouse) as client:
            apply_schema(config, client, project_root, variant_root)

        logger.info("Schema application completed successfully")
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
        logger.info(f"Loading configuration from {args.config}")
        config = load_config(args.config)

        project_root = compute_project_root(config)
        variant_root = compute_variant_root(config)

        logger.info("Loading data into tables...")
        with ClickHouseClient(config.clickhouse) as client:
            load_data(config, client, project_root, variant_root)

        logger.info("Data loading completed successfully")
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
        logger.info(f"Loading configuration from {args.config}")
        config = load_config(args.config)

        project_root = compute_project_root(config)
        variant_root = compute_variant_root(config)

        logger.info("Running workload...")
        workload_result = run_workload(config, project_root, variant_root)

        execution_records = workload_result["records"]
        workload_metadata = {
            "workload_start_epoch_ms": workload_result["workload_start_epoch_ms"],
            "workload_end_epoch_ms": workload_result["workload_end_epoch_ms"],
            "workload_elapsed_secs": workload_result["workload_elapsed_secs"],
        }

        logger.info(f"Workload completed: {len(execution_records)} queries executed")

        # Convert epoch milliseconds to datetime for metrics collection
        start_time = datetime.fromtimestamp(workload_result["workload_start_epoch_ms"] / 1000)
        end_time = datetime.fromtimestamp(workload_result["workload_end_epoch_ms"] / 1000)

        # Collect metrics from query_log
        logger.info("Collecting metrics from query_log...")
        with ClickHouseClient(config.clickhouse) as client:
            query_log_metrics = collect_query_log_metrics(
                config,
                client,
                execution_records,
                start_time,
                end_time,
            )

        # Generate reports
        logger.info("Generating reports...")
        generate_reports(
            config,
            execution_records,
            query_log_metrics,
            workload_metadata,
            project_root,
        )

        logger.info("Workload execution and reporting completed successfully")
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
        logger.info(f"Loading configuration from {args.config}")
        config = load_config(args.config)

        # If dry-run, only validate
        if args.dry_run:
            logger.info("Dry-run mode: validating only")
            return cmd_validate(args)

        # Step 1: Validate
        logger.info("Step 1: Validating configuration...")
        if cmd_validate(args) != 0:
            logger.error("Validation failed, aborting full-run")
            return 1

        # Step 2: Initialize database if fresh schema requested
        if config.schema.fresh:
            logger.info("Step 2: Initializing database (fresh schema)...")
            if cmd_init_db(args) != 0:
                logger.error("Schema initialization failed, aborting full-run")
                return 1
        else:
            logger.info("Step 2: Skipping schema initialization (fresh=False)")

        # Step 3: Load data
        logger.info("Step 3: Loading data...")
        if cmd_load_data(args) != 0:
            logger.error("Data loading failed, aborting full-run")
            return 1

        # Step 4: Run workload
        logger.info("Step 4: Running workload...")
        if cmd_run_workload(args) != 0:
            logger.error("Workload execution failed, aborting full-run")
            return 1

        logger.info("Full benchmark run completed successfully")
        return 0

    except HarnessError as e:
        logger.error(f"Full-run failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error during full-run: {e}", exc_info=True)
        return 1


def cmd_compare(args: argparse.Namespace) -> int:
    """Compare two benchmark result CSV files.

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
        logger.error(f"Invalid CSV file: {e}")
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
    parser_validate.add_argument("--verbose", action="store_true", help="Enable verbose logging (DEBUG level)")

    # init-db command
    parser_init_db = subparsers.add_parser(
        "init-db",
        help="Initialize database schema",
    )
    parser_init_db.add_argument("--config", type=str, required=True, help="Path to configuration YAML file")
    parser_init_db.add_argument("--verbose", action="store_true", help="Enable verbose logging (DEBUG level)")

    # load-data command
    parser_load_data = subparsers.add_parser(
        "load-data",
        help="Load data into ClickHouse tables",
    )
    parser_load_data.add_argument("--config", type=str, required=True, help="Path to configuration YAML file")
    parser_load_data.add_argument("--verbose", action="store_true", help="Enable verbose logging (DEBUG level)")

    # run-workload command
    parser_run_workload = subparsers.add_parser(
        "run-workload",
        help="Run workload and collect metrics",
    )
    parser_run_workload.add_argument("--config", type=str, required=True, help="Path to configuration YAML file")
    parser_run_workload.add_argument("--verbose", action="store_true", help="Enable verbose logging (DEBUG level)")

    # full-run command
    parser_full_run = subparsers.add_parser(
        "full-run",
        help="Run complete benchmark (validate, init-db if fresh, load-data, run-workload)",
    )
    parser_full_run.add_argument("--config", type=str, required=True, help="Path to configuration YAML file")
    parser_full_run.add_argument("--verbose", action="store_true", help="Enable verbose logging (DEBUG level)")
    parser_full_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry-run mode: validate only, don't execute",
    )

    # compare command
    parser_compare = subparsers.add_parser(
        "compare",
        help="Compare two benchmark result CSV files",
    )
    parser_compare.add_argument(
        "csv_a",
        type=str,
        help="Path to first (baseline) CSV results file",
    )
    parser_compare.add_argument(
        "csv_b",
        type=str,
        help="Path to second (comparison) CSV results file",
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
