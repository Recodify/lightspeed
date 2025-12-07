"""Data loading into ClickHouse tables."""

import logging
import time
from pathlib import Path

from harness.clickhouse_client import ClickHouseClient
from harness.config import BenchmarkConfig
from harness.exceptions import DataLoadError

logger = logging.getLogger(__name__)


def resolve_data_file(
    filename: str,
    project_root: Path,
    variant_root: Path
) -> Path:
    """Resolve data file path using variant-first resolution.

    Args:
        filename: Data file name
        project_root: Project root directory
        variant_root: Variant root directory

    Returns:
        Resolved file path

    Raises:
        DataLoadError: If file not found in either location
    """
    # Try variant first
    variant_path = variant_root / "data" / filename
    if variant_path.exists():
        logger.debug(f"Resolved data file (variant): {variant_path}")
        return variant_path

    # Fallback to project
    project_path = project_root / "data" / filename
    if project_path.exists():
        logger.debug(f"Resolved data file (project): {project_path}")
        return project_path

    # Not found
    raise DataLoadError(
        f"Data file not found: {filename} "
        f"(checked {variant_path} and {project_path})"
    )


def load_data(
    config: BenchmarkConfig,
    client: ClickHouseClient,
    project_root: Path,
    variant_root: Path
) -> dict[str, int]:
    """Load data into ClickHouse tables from files.

    Args:
        config: Benchmark configuration
        client: ClickHouse client
        project_root: Project root directory
        variant_root: Variant root directory

    Returns:
        Summary dict with: {"tables_loaded": N, "bytes_transferred": N}

    Raises:
        DataLoadError: If data loading fails for any file
    """
    tables_loaded = 0
    bytes_transferred = 0

    for entry in config.data.load:
        # Resolve file path
        data_file = resolve_data_file(entry.file, project_root, variant_root)
        file_size = data_file.stat().st_size

        logger.info(
            f"Loading {entry.file} ({_format_bytes(file_size)}) "
            f"into table {entry.table} as {entry.format}"
        )

        # Truncate if requested
        if config.data.truncate_before_load:
            try:
                client.execute_no_result(f"TRUNCATE TABLE {entry.table}")
                logger.debug(f"Truncated table: {entry.table}")
            except Exception as e:
                raise DataLoadError(f"Failed to truncate table {entry.table}: {e}")

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
                client.insert_stream(entry.table, f, actual_format)

            duration = time.time() - start_time
            throughput_mbps = (file_size / (1024 * 1024)) / duration if duration > 0 else 0

            logger.info(
                f"Loaded {entry.table}: {_format_bytes(file_size)} "
                f"in {duration:.2f}s ({throughput_mbps:.2f} MB/s)"
            )

            tables_loaded += 1
            bytes_transferred += file_size

        except Exception as e:
            raise DataLoadError(
                f"Failed to load {entry.file} into {entry.table}: {e}"
            )

    logger.info(
        f"Data loading complete: {tables_loaded} tables, "
        f"{_format_bytes(bytes_transferred)} total"
    )

    return {
        "tables_loaded": tables_loaded,
        "bytes_transferred": bytes_transferred
    }


def _format_bytes(bytes_count: int) -> str:
    """Format bytes as human-readable string.

    Args:
        bytes_count: Number of bytes

    Returns:
        Formatted string (e.g., "1.2 MB", "45 KB")
    """
    if bytes_count < 1024:
        return f"{bytes_count} B"
    elif bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.2f} KB"
    elif bytes_count < 1024 * 1024 * 1024:
        return f"{bytes_count / (1024 * 1024):.2f} MB"
    else:
        return f"{bytes_count / (1024 * 1024 * 1024):.2f} GB"
