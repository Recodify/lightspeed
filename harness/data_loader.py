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


def resolve_script_path(script: str, project_root: Path, variant_root: Path) -> Path:
    """Resolve a load script path, preferring variant over project scope.

    Args:
        script: Script filename relative to data directories
        project_root: Project root directory
        variant_root: Variant root directory

    Returns:
        Path to the script file

    Raises:
        DataLoadError: If script file cannot be found
    """
    candidate_variant = variant_root / "data" / script
    candidate_project = project_root / "data" / script

    if candidate_variant.exists():
        logger.debug(f"Using variant data load script: {candidate_variant}")
        return candidate_variant

    if candidate_project.exists():
        logger.debug(f"Using project data load script: {candidate_project}")
        return candidate_project

    raise DataLoadError(
        f"Data load script not found: {script} (checked {candidate_variant} and {candidate_project})"
    )


def get_clickhouse_file_path(data_file: Path, repo_root: Path) -> str:
    """
    Convert a data file path to a ClickHouse-accessible path.

    We prefer a path relative to the repo root so it can be resolved inside
    ClickHouse when the repo is mounted into /var/lib/clickhouse/user_files
    (container scenario). If the file is unexpectedly outside the repo, fall
    back to the absolute path to preserve existing behavior.
    """
    try:
        return str(data_file.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        logger.debug(
            "Data file is outside repo root; falling back to absolute path: %s", data_file
        )
        return str(data_file.resolve())


def load_data(
    config: BenchmarkConfig,
    client: ClickHouseClient,
    project_root: Path,
    variant_root: Path,
    run_name: str,
    config_name: str
) -> dict:
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
        Dict with overall and per-file metrics.

    Raises:
        DataLoadError: If data loading fails for any file
    """
    files_loaded = 0
    bytes_transferred = 0
    file_stats: list[dict] = []
    overall_start = time.time()
    load_method = config.data.load_method.lower()
    repo_root = project_root.parents[1] if len(project_root.parents) > 1 else project_root.parent

    # Compute isolated database name
    isolated_database = compute_isolated_database_name(
        config.project, config_name, run_name, config.variant
    )

    for entry in config.data.load:
        # Use database.table format
        full_table_name = f"{isolated_database}.{entry.table}"

        if load_method == "script" and not entry.script:
            raise DataLoadError(
                f"Data load entry for table {entry.table} requires a script when load_method is 'script'"
            )

        # Collect all data files for this entry (project + variant)
        data_files = collect_data_files(entry.file, project_root, variant_root)

        script_path = None
        if load_method == "script":
            script_path = resolve_script_path(entry.script, project_root, variant_root)

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

            # Allow ISO8601 datetimes with T/Z when loading CSV data
            load_settings = None
            if actual_format.upper().startswith("CSV"):
                load_settings = {"date_time_input_format": "best_effort"}

            # Load data
            start_time = time.time()

            try:
                if load_method == "http":
                    with open(data_file, "rb") as f:
                        client.insert_stream(full_table_name, f, actual_format, settings=load_settings)
                elif load_method == "insert":
                    file_path = get_clickhouse_file_path(data_file, repo_root)
                    escaped_path = file_path.replace("'", "\\'")
                    query = (
                        f"INSERT INTO {full_table_name} "
                        f"SELECT * FROM file('{escaped_path}', '{actual_format}')"
                    )
                    logger.info(query)
                    client.execute_no_result(query, settings=load_settings)
                elif load_method == "script":
                    file_path = get_clickhouse_file_path(data_file, repo_root)
                    escaped_path = file_path.replace("'", "\\'")
                    script_template = script_path.read_text()
                    try:
                        query = script_template.format(
                            table=full_table_name,
                            file_path=escaped_path,
                            format=actual_format,
                        )
                        logger.info(query)
                    except Exception as e:
                        raise DataLoadError(
                            f"Failed to format load script {script_path}: {e}"
                        )
                    client.execute_no_result(query, settings=load_settings)
                else:
                    raise DataLoadError(
                        f"Unsupported load method: {config.data.load_method}"
                    )

                duration = time.time() - start_time
                throughput_mbps = (file_size / (1024 * 1024)) / duration if duration > 0 else 0

                logger.debug(
                    f"Loaded {full_table_name} ({source}): {format_bytes(file_size)} "
                    f"in {duration:.2f}s ({throughput_mbps:.2f} MB/s)"
                )

                files_loaded += 1
                bytes_transferred += file_size
                file_stats.append({
                    "table": entry.table,
                    "file": entry.file,
                    "source": source,
                    "bytes": file_size,
                    "duration_secs": duration,
                    "duration_ms": duration * 1000,
                    "throughput_mb_s": throughput_mbps,
                })

            except Exception as e:
                raise DataLoadError(
                    f"Failed to load {entry.file} ({source}) into {full_table_name}: {e}"
                )

    total_duration = time.time() - overall_start
    total_throughput = (
        (bytes_transferred / (1024 * 1024)) / total_duration if total_duration > 0 else 0
    )
    total_duration_ms = total_duration * 1000

    logger.debug(
        f"Data loading complete: {files_loaded} files loaded, "
        f"{format_bytes(bytes_transferred)} total "
        f"in {total_duration:.2f}s ({total_throughput:.2f} MB/s)"
    )

    return {
        "files_loaded": files_loaded,
        "bytes_transferred": bytes_transferred,
        "duration_secs": total_duration,
        "duration_ms": total_duration_ms,
        "throughput_mb_s": total_throughput,
        "files": file_stats,
    }
