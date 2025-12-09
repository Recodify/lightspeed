"""Metrics collection from ClickHouse query_log."""

import logging
import time
from datetime import datetime

from harness.clickhouse_client import ClickHouseClient
from harness.config import BenchmarkConfig
from harness.exceptions import MetricsCollectionError
from harness.utils import compute_isolated_database_name
from harness.workload_runner import ExecutionRecord

logger = logging.getLogger(__name__)


def collect_query_log_metrics(
    config: BenchmarkConfig,
    client: ClickHouseClient,
    execution_records: list[ExecutionRecord],
    start_time: datetime,
    end_time: datetime,
    query_id_prefix: str,
) -> dict[str, dict]:
    """Collect metrics from system.query_log for executed queries.

    Args:
        config: Benchmark configuration
        client: ClickHouse client instance
        execution_records: List of query execution records from workload
        start_time: Workload start time
        end_time: Workload end time

    Returns:
        Dictionary mapping query_id to metrics dict with keys:
        - query_duration_ms: Query execution time in milliseconds
        - read_rows: Number of rows read
        - read_bytes: Number of bytes read
        - result_rows: Number of rows in result
        - result_bytes: Number of bytes in result
        - memory_usage: Peak memory usage in bytes

    Raises:
        MetricsCollectionError: If metrics collection fails
    """
    if not config.metrics.use_query_log:
        logger.debug("Query log collection disabled in config")
        return {}

    # Wait for query_log to flush
    wait_seconds = config.metrics.query_log_wait_seconds
    if wait_seconds > 0:
        logger.debug(f"Waiting {wait_seconds}s for query_log to flush...")
        time.sleep(wait_seconds)

    # Extract all query_ids from execution records
    query_ids = [record.query_id for record in execution_records]
    if not query_ids:
        logger.warning("No execution records to collect metrics for")
        return {}

    if not query_id_prefix:
        raise MetricsCollectionError("query_id_prefix is required for metrics collection")

    logger.debug(f"Collecting metrics for {len(query_ids)} queries from system.query_log")

    # Build SQL query to fetch metrics
    # Convert datetime to string format ClickHouse expects
    start_time_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    end_time_str = end_time.strftime("%Y-%m-%d %H:%M:%S")

    sql = f"""
        SELECT
            query_id,
            query_duration_ms,
            read_rows,
            read_bytes,
            result_rows,
            result_bytes,
            memory_usage
        FROM system.query_log
        WHERE type = 'QueryFinish'
            AND query_id LIKE '{query_id_prefix}%'
            AND event_time >= toDateTime('{start_time_str}')
            AND event_time <= toDateTime('{end_time_str}')
        ORDER BY event_time DESC
    """

    logger.debug(f"collecting query logs. query: {sql}")

    try:
        results = client.execute(sql)
    except Exception as e:
        raise MetricsCollectionError(f"Failed to query system.query_log: {e}")

    def _as_int(row: dict, key: str) -> int:
        """Coerce a query_log field to int, logging and defaulting to 0 on bad data."""
        try:
            return int(row[key])
        except Exception:
            logger.warning(
                "Non-numeric query_log value for %s on query_id=%s: %r (defaulting to 0)",
                key,
                row.get("query_id"),
                row.get(key),
            )
            return 0

    # Build mapping of query_id to metrics
    metrics_map = {}
    executed_ids = set(query_ids)
    for row in results:
        query_id = row["query_id"]

        # Skip metrics not in our executed set (if using prefix filter)
        if executed_ids and query_id not in executed_ids:
            continue

        # If we see duplicate query_ids (shouldn't happen normally), take the latest
        if query_id in metrics_map:
            logger.warning(f"Duplicate query_id in query_log: {query_id} - using latest entry")

        metrics_map[query_id] = {
            "query_duration_ms": _as_int(row, "query_duration_ms"),
            "read_rows": _as_int(row, "read_rows"),
            "read_bytes": _as_int(row, "read_bytes"),
            "result_rows": _as_int(row, "result_rows"),
            "result_bytes": _as_int(row, "result_bytes"),
            "memory_usage": _as_int(row, "memory_usage"),
        }

    # Check for mismatches
    expected_count = len(query_ids)
    actual_count = len(metrics_map)

    if actual_count < expected_count:
        missing_count = expected_count - actual_count
        logger.warning(
            f"Query log returned {actual_count} entries but expected {expected_count} "
            f"({missing_count} queries missing from query_log). "
            f"This may occur if queries failed before reaching QueryFinish state."
        )
    elif actual_count > expected_count:
        extra_count = actual_count - expected_count
        logger.warning(
            f"Query log returned {actual_count} entries but expected {expected_count} "
            f"({extra_count} extra entries). This may indicate duplicate query_ids."
        )
    else:
        logger.debug(f"Successfully collected metrics for all {actual_count} queries")

    return metrics_map


def collect_variant_resource_usage(
    config: BenchmarkConfig,
    client: ClickHouseClient,
    run_name: str,
    config_name: str,
) -> dict:
    """Collect size on disk and server memory usage for a variant.

    Args:
        config: Benchmark configuration
        client: ClickHouse client instance
        run_name: Run name for isolation (e.g., "brave-penguin")
        config_name: Config file name (e.g., "example_basic")

    Returns:
        Dictionary with `size_on_disk_bytes` and `server_memory_usage_bytes`.
    """
    database = compute_isolated_database_name(
        config.project, config_name, run_name, config.variant
    )

    size_on_disk_bytes = _get_database_size_on_disk(client, database)
    server_memory_usage_bytes = _get_server_memory_usage(client)

    return {
        "database": database,
        "size_on_disk_bytes": size_on_disk_bytes,
        "server_memory_usage_bytes": server_memory_usage_bytes,
    }


def _get_database_size_on_disk(client: ClickHouseClient, database: str) -> int | None:
    """Return total bytes on disk for all tables in the given database."""
    sql = f"""
        SELECT COALESCE(sum(bytes_on_disk), 0) AS bytes_on_disk
        FROM system.parts
        WHERE database = '{database}'
    """

    try:
        result = client.execute(sql)
        if result:
            return int(result[0].get("bytes_on_disk", 0))
    except Exception as e:
        logger.warning(
            "Failed to collect size_on_disk for database %s: %s", database, e
        )

    return None


def _get_server_memory_usage(client: ClickHouseClient) -> int | None:
    """Return server memory usage from ClickHouse metrics tables."""
    queries = [
        "SELECT toUInt64(value) AS memory_usage FROM system.asynchronous_metrics WHERE metric = 'MemoryTracking'",
        "SELECT toUInt64(value) AS memory_usage FROM system.metrics WHERE metric = 'MemoryTracking'",
    ]

    for sql in queries:
        try:
            result = client.execute(sql)
            if result:
                return int(result[0].get("memory_usage", 0))
        except Exception as e:
            logger.warning(
                "Failed to collect server memory usage with query %s: %s", sql, e
            )

    return None
