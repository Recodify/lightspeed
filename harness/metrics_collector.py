"""Metrics collection from ClickHouse query_log."""

import logging
import time
from datetime import datetime

from harness.clickhouse_client import ClickHouseClient
from harness.config import BenchmarkConfig
from harness.exceptions import MetricsCollectionError
from harness.workload_runner import ExecutionRecord

logger = logging.getLogger(__name__)


def collect_query_log_metrics(
    config: BenchmarkConfig,
    client: ClickHouseClient,
    execution_records: list[ExecutionRecord],
    start_time: datetime,
    end_time: datetime
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

    logger.debug(f"Collecting metrics for {len(query_ids)} queries from system.query_log")

    # Build SQL query to fetch metrics
    # Convert datetime to string format ClickHouse expects
    start_time_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    end_time_str = end_time.strftime("%Y-%m-%d %H:%M:%S")

    # Create IN clause with quoted query_ids
    query_ids_clause = ", ".join(f"'{qid}'" for qid in query_ids)

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
            AND query_id IN ({query_ids_clause})
            AND event_time >= toDateTime('{start_time_str}')
            AND event_time <= toDateTime('{end_time_str}')
        ORDER BY event_time DESC
    """

    try:
        results = client.execute(sql)
    except Exception as e:
        raise MetricsCollectionError(f"Failed to query system.query_log: {e}")

    # Build mapping of query_id to metrics
    metrics_map = {}
    for row in results:
        query_id = row["query_id"]

        # If we see duplicate query_ids (shouldn't happen normally), take the latest
        if query_id in metrics_map:
            logger.warning(f"Duplicate query_id in query_log: {query_id} - using latest entry")

        metrics_map[query_id] = {
            "query_duration_ms": row["query_duration_ms"],
            "read_rows": row["read_rows"],
            "read_bytes": row["read_bytes"],
            "result_rows": row["result_rows"],
            "result_bytes": row["result_bytes"],
            "memory_usage": row["memory_usage"],
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
