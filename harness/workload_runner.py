"""Workload execution for benchmarking ClickHouse queries."""

import logging
import random
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx

from harness.clickhouse_client import ClickHouseClient
from harness.config import BenchmarkConfig, ParameterSpec, WorkloadConfig
from harness.exceptions import WorkloadAbortedError
from harness.parameter_generator import generate_params

logger = logging.getLogger(__name__)


@dataclass
class ExecutionRecord:
    """Record of a single query execution."""

    query_id: str
    query_name: str
    executed_sql: str
    started_at: datetime
    finished_at: datetime
    duration_ms: float
    success: bool
    error_message: str | None


class SharedCounter:
    """Thread-safe counter for tracking errors across workers."""

    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()

    def increment(self) -> int:
        """Increment counter and return new value."""
        with self._lock:
            self._value += 1
            return self._value

    @property
    def value(self) -> int:
        """Get current value."""
        with self._lock:
            return self._value


def load_queries(
    config: WorkloadConfig,
    project_root: Path,
    variant_root: Path
) -> list[dict]:
    """Load query files for workload execution.

    Supports two modes:
    1. Explicit: Query files and weights specified in config
    2. Auto-discovery: All *.sql files in workload directory

    Args:
        config: Workload configuration
        project_root: Project root directory
        variant_root: Variant root directory

    Returns:
        List of dicts: [{"file": name, "weight": N, "sql": content}, ...]

    Raises:
        FileNotFoundError: If required query file not found
    """
    queries = []

    if config.queries:
        # Explicit mode
        logger.debug(f"Loading {len(config.queries)} explicit queries")

        for query_spec in config.queries:
            # Try variant first, then project
            variant_path = variant_root / "workloads" / config.path / query_spec.file
            project_path = project_root / "workloads" / config.path / query_spec.file

            if variant_path.exists():
                query_path = variant_path
                logger.debug(f"Query file (variant): {query_spec.file}")
            elif project_path.exists():
                query_path = project_path
                logger.debug(f"Query file (project): {query_spec.file}")
            else:
                raise FileNotFoundError(
                    f"Query file not found: {query_spec.file} "
                    f"(checked {variant_path} and {project_path})"
                )

            sql = query_path.read_text()
            queries.append({
                "file": query_spec.file,
                "weight": query_spec.weight,
                "sql": sql
            })

    else:
        # Auto-discovery mode
        logger.debug("Auto-discovering queries from workload directory")

        variant_dir = variant_root / "workloads" / config.path
        project_dir = project_root / "workloads" / config.path

        # Collect all query files
        query_files = {}

        # Project files first (lower priority)
        if project_dir.exists():
            for query_path in project_dir.glob("*.sql"):
                sql = query_path.read_text()
                query_files[query_path.name] = {
                    "file": query_path.name,
                    "weight": 1,
                    "sql": sql
                }

        # Variant files override project files
        if variant_dir.exists():
            for query_path in variant_dir.glob("*.sql"):
                sql = query_path.read_text()
                query_files[query_path.name] = {
                    "file": query_path.name,
                    "weight": 1,
                    "sql": sql
                }

        if not query_files:
            raise FileNotFoundError(
                f"No query files found in workload path: {config.path} "
                f"(checked {variant_dir} and {project_dir})"
            )

        queries = list(query_files.values())
        logger.debug(f"Auto-discovered {len(queries)} queries")

    return queries


def build_weighted_pool(queries: list[dict]) -> list[dict]:
    """Build weighted pool for random query selection.

    Args:
        queries: List of query dicts with 'weight' field

    Returns:
        Flattened list with queries duplicated by weight
    """
    pool = []

    for query in queries:
        # Duplicate query 'weight' times
        for _ in range(query["weight"]):
            pool.append(query)

    logger.debug(f"Built weighted pool: {len(pool)} total queries from {len(queries)} unique")
    return pool


def run_warmup(
    warmup_queries: int,
    query_pool: list[dict],
    client: ClickHouseClient,
    param_config: dict[str, ParameterSpec] | None
) -> None:
    """Run warmup queries single-threaded before measurement.

    Args:
        warmup_queries: Number of warmup queries to execute
        query_pool: Weighted pool of queries
        client: ClickHouse client
        param_config: Parameter configuration for query substitution
    """
    if warmup_queries == 0:
        logger.debug("Skipping warmup (warmup_queries=0)")
        return

    logger.debug(f"Running {warmup_queries} warmup queries (single-threaded)")

    for i in range(warmup_queries):
        # Select random query
        query = random.choice(query_pool)

        # Generate parameters
        params = generate_params(param_config)

        # Format SQL
        try:
            sql = query["sql"].format(**params)
        except KeyError as e:
            logger.warning(f"Warmup query {i+1}: parameter substitution failed: {e}")
            continue

        # Execute (ignore results and errors)
        try:
            client.execute(sql)
        except Exception:
            pass  # Ignore warmup errors

        # Log progress periodically
        if (i + 1) % 100 == 0:
            logger.debug(f"Warmup progress: {i+1}/{warmup_queries}")

    logger.debug("Warmup complete")


def worker_func(
    config: WorkloadConfig,
    query_pool: list[dict],
    client: ClickHouseClient,
    param_config: dict[str, ParameterSpec] | None,
    stop_event: threading.Event,
    error_counter: SharedCounter,
    worker_id: int,
    start_time: float,
    duration_seconds: int
) -> list[ExecutionRecord]:
    """Worker function for concurrent query execution.

    Args:
        config: Workload configuration
        query_pool: Weighted pool of queries
        client: ClickHouse client (shared across workers)
        param_config: Parameter configuration
        stop_event: Event to signal early termination
        error_counter: Shared error counter
        worker_id: Worker identifier for logging
        start_time: Workload start time (for duration check)
        duration_seconds: Total workload duration

    Returns:
        List of ExecutionRecords for this worker
    """
    records = []
    logger.debug(f"Worker {worker_id} started")

    while not stop_event.is_set():
        # Check duration
        elapsed = time.time() - start_time
        if elapsed >= duration_seconds:
            logger.debug(f"Worker {worker_id} duration exceeded")
            break

        # Check error threshold
        if error_counter.value >= config.max_errors:
            logger.warning(
                f"Worker {worker_id} stopping due to error threshold "
                f"({error_counter.value} >= {config.max_errors})"
            )
            stop_event.set()
            break

        # Select random query
        query = random.choice(query_pool)
        query_name = query["file"]

        # Generate parameters
        params = generate_params(param_config)

        # Format SQL
        try:
            executed_sql = query["sql"].format(**params)
        except KeyError as e:
            error_counter.increment()
            logger.warning(f"Worker {worker_id}: parameter substitution failed: {e}")
            continue

        # Generate unique query_id
        query_id = f"{query_name}_{uuid.uuid4()}"

        # Execute query
        started_at = datetime.now()
        start_ms = time.time() * 1000

        try:
            client.execute(executed_sql, settings={"query_id": query_id})

            finished_at = datetime.now()
            end_ms = time.time() * 1000
            duration_ms = end_ms - start_ms

            records.append(ExecutionRecord(
                query_id=query_id,
                query_name=query_name,
                executed_sql=executed_sql,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                success=True,
                error_message=None
            ))

        except httpx.ReadTimeout:
            finished_at = datetime.now()
            end_ms = time.time() * 1000
            duration_ms = end_ms - start_ms

            error_counter.increment()

            records.append(ExecutionRecord(
                query_id=query_id,
                query_name=query_name,
                executed_sql=executed_sql,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                success=False,
                error_message="Query timeout"
            ))

        except Exception as e:
            finished_at = datetime.now()
            end_ms = time.time() * 1000
            duration_ms = end_ms - start_ms

            error_counter.increment()

            records.append(ExecutionRecord(
                query_id=query_id,
                query_name=query_name,
                executed_sql=executed_sql,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                success=False,
                error_message=str(e)
            ))

        # Think time
        if config.think_time_ms > 0:
            time.sleep(config.think_time_ms / 1000.0)

    logger.debug(f"Worker {worker_id} completed: {len(records)} queries executed")
    return records


def run_workload(
    config: BenchmarkConfig,
    project_root: Path,
    variant_root: Path
) -> dict:
    """Execute workload and collect execution records.

    Args:
        config: Benchmark configuration
        project_root: Project root directory
        variant_root: Variant root directory

    Returns:
        Dict with keys:
        - records: List of ExecutionRecords
        - workload_start_epoch_ms: Workload start timestamp
        - workload_end_epoch_ms: Workload end timestamp
        - workload_elapsed_secs: Actual elapsed time

    Raises:
        WorkloadAbortedError: If max_errors threshold exceeded
    """
    # Load queries
    queries = load_queries(config.workload, project_root, variant_root)

    # Build weighted pool
    query_pool = build_weighted_pool(queries)

    logger.debug(
        f"Workload: {config.workload.name}, "
        f"concurrency: {config.workload.concurrency}, "
        f"duration: {config.workload.duration_seconds}s"
    )

    # Create workload-specific client with query timeout
    workload_httpx_client = httpx.Client(
        timeout=httpx.Timeout(config.workload.query_timeout_seconds, connect=10.0),
        limits=httpx.Limits(
            max_connections=config.clickhouse.connection_pool_size,
            max_keepalive_connections=config.clickhouse.connection_pool_size
        )
    )

    # Create ClickHouse client for workload
    client = ClickHouseClient(
        config.clickhouse,
        timeout_seconds=config.workload.query_timeout_seconds
    )

    # Replace httpx client with workload-specific one
    client.client = workload_httpx_client

    # Run warmup
    run_warmup(
        config.workload.warmup_queries,
        query_pool,
        client,
        config.workload.parameters
    )

    # Run concurrent workload
    logger.info(f"Running workload: {config.workload.concurrency} workers × {config.workload.duration_seconds}s")

    workload_start_epoch_ms = int(time.time() * 1000)
    start_time = time.time()

    stop_event = threading.Event()
    error_counter = SharedCounter()

    all_records = []

    with ThreadPoolExecutor(max_workers=config.workload.concurrency) as executor:
        # Submit worker tasks
        futures = []
        for i in range(config.workload.concurrency):
            future = executor.submit(
                worker_func,
                config.workload,
                query_pool,
                client,
                config.workload.parameters,
                stop_event,
                error_counter,
                i,
                start_time,
                config.workload.duration_seconds
            )
            futures.append(future)

        # Wait for ramp-up period before starting measurement
        if config.workload.ramp_up_seconds > 0:
            logger.debug(f"Ramp-up period: {config.workload.ramp_up_seconds}s")
            time.sleep(config.workload.ramp_up_seconds)
            # Reset start time after ramp-up
            workload_start_epoch_ms = int(time.time() * 1000)

        # Collect results
        for future in as_completed(futures):
            worker_records = future.result()
            all_records.extend(worker_records)

    workload_end_epoch_ms = int(time.time() * 1000)
    workload_elapsed_secs = (workload_end_epoch_ms - workload_start_epoch_ms) / 1000.0

    # Close client
    client.client.close()

    logger.info(
        f"Completed: {len(all_records)} queries in {workload_elapsed_secs:.2f}s "
        f"({error_counter.value} errors)"
    )

    # Check if error threshold exceeded
    if error_counter.value >= config.workload.max_errors:
        raise WorkloadAbortedError(
            f"Workload aborted: error count {error_counter.value} "
            f"exceeded threshold {config.workload.max_errors}"
        )

    return {
        "records": all_records,
        "workload_start_epoch_ms": workload_start_epoch_ms,
        "workload_end_epoch_ms": workload_end_epoch_ms,
        "workload_elapsed_secs": workload_elapsed_secs
    }
