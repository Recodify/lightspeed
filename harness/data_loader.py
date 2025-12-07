"""Data loading into ClickHouse tables."""

import logging
import time
from pathlib import Path

from harness.clickhouse_client import ClickHouseClient
from harness.config import BenchmarkConfig
from harness.exceptions import DataLoadError
from harness.utils import format_bytes, compute_isolated_database_name

logger = logging.getLogger(__name__)


def collect_data_files(
    filename: str,
    project_root: Path,
    variant_root: Path
) -> list[tuple[Path, str]]:
    """Collect data files to load (project first, then variant supplement).

    Args:
        filename: Data file name
        project_root: Project root directory
        variant_root: Variant root directory

    Returns:
        List of (path, source) tuples where source is "project" or "variant"

    Raises:
        DataLoadError: If file not found in either location
    """
    files_to_load = []

    project_path = project_root / "data" / filename
    variant_path = variant_root / "data" / filename

    # Project data always loaded first if it exists
    if project_path.exists():
        files_to_load.append((project_path, "project"))
        logger.debug(f"Will load data file (project): {filename}")

    # Variant data loaded as supplement if it exists
    if variant_path.exists():
        files_to_load.append((variant_path, "variant"))
        logger.debug(f"Will load data file (variant): {filename}")

    # At least one must exist
    if not files_to_load:
        raise DataLoadError(
            f"Data file not found: {filename} "
            f"(checked {project_path} and {variant_path})"
        )

    return files_to_load


def load_data(
    config: BenchmarkConfig,
    client: ClickHouseClient,
    project_root: Path,
    variant_root: Path,
    run_name: str,
    config_name: str
) -> dict[str, int]:
    """Load data into ClickHouse tables from files with isolation.

    Uses isolated database (one per variant).
    Table names remain unchanged from config.
    Loads project data first, then variant data as supplement.

    Args:
        config: Benchmark configuration
        client: ClickHouse client
        project_root: Project root directory
        variant_root: Variant root directory
        run_name: Run name for isolation (e.g., 'brave-penguin')
        config_name: Config file name (e.g., 'example_basic')

    Returns:
        Summary dict with: {"files_loaded": N, "bytes_transferred": N}

    Raises:
        DataLoadError: If data loading fails for any file
    """
    files_loaded = 0
    bytes_transferred = 0

    # Compute isolated database name
    isolated_database = compute_isolated_database_name(
        config.project, config_name, run_name, config.variant
    )

    for entry in config.data.load:
        # Use database.table format
        full_table_name = f"{isolated_database}.{entry.table}"

        # Collect all data files for this entry (project + variant)
        data_files = collect_data_files(entry.file, project_root, variant_root)

        # Truncate once before loading all files for this table
        if config.data.truncate_before_load:
            try:
                client.execute_no_result(f"TRUNCATE TABLE {full_table_name}")
                logger.debug(f"Truncated table: {full_table_name}")
            except Exception as e:
                raise DataLoadError(f"Failed to truncate table {full_table_name}: {e}")

        # Load each file (project first, then variant)
        for data_file, source in data_files:
            file_size = data_file.stat().st_size

            logger.debug(
                f"Loading {entry.file} ({source}) ({format_bytes(file_size)}) "
                f"into table {full_table_name} as {entry.format}"
            )

            # Determine actual format
            # If CSV format, use CSVWithNames to leverage header row
            actual_format = entry.format
            if entry.format.upper() == "CSV":
                actual_format = "CSVWithNames"
                logger.debug(f"Using {actual_format} for CSV with headers")

            # Load data
            start_time = time.time()

            try:
                with open(data_file, "rb") as f:
                    client.insert_stream(full_table_name, f, actual_format)

                duration = time.time() - start_time
                throughput_mbps = (file_size / (1024 * 1024)) / duration if duration > 0 else 0

                logger.debug(
                    f"Loaded {full_table_name} ({source}): {format_bytes(file_size)} "
                    f"in {duration:.2f}s ({throughput_mbps:.2f} MB/s)"
                )

                files_loaded += 1
                bytes_transferred += file_size

            except Exception as e:
                raise DataLoadError(
                    f"Failed to load {entry.file} ({source}) into {full_table_name}: {e}"
                )

    logger.debug(
        f"Data loading complete: {files_loaded} files loaded, "
        f"{format_bytes(bytes_transferred)} total"
    )

    return {
        "files_loaded": files_loaded,
        "bytes_transferred": bytes_transferred
    }
