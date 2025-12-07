# ClickHouse Benchmark Harness – Plan6 (Final Specification)

**Based on**: Plan4 + Plan5 review + Appendix1 clarifications

**Status**: ✅ **READY FOR IMPLEMENTATION**

**Review Score**: 9.5/10

---

## Critical Additions from Appendix1

### 1. Query Timeout Behavior (query_timeout_seconds)

**Purpose**: Enforce hard per-query execution timeout to prevent worker thread blocking.

**Implementation requirement**:
- If ClickHouse query exceeds `query_timeout_seconds`, the client **must abort the request**
- The execution **must be marked as failed** in ExecutionRecord
- Worker **must continue to next iteration** (not block indefinitely)

**Protects against**:
- Lock contention stalling queries
- Memory pressure causing slowdowns
- Merge operations blocking reads
- Disk latency spikes
- Unbounded query execution collapsing throughput

**Example**:
```yaml
workload:
  query_timeout_seconds: 60  # Any query >60s is aborted and marked failed
```

**Implementation in workload_runner.py**:
```python
import httpx

# Configure timeout in httpx client
timeout = httpx.Timeout(
    connect=10.0,
    read=config.query_timeout_seconds,
    write=10.0,
    pool=10.0
)

client = httpx.Client(timeout=timeout, limits=...)

try:
    result = client.post(...)
except httpx.ReadTimeout:
    # Mark execution as failed
    record.success = False
    record.error_message = f"Query timeout after {query_timeout_seconds}s"
    # Continue to next query
```

**Why this matters**:
- Without timeout: A single stuck query can block a worker thread permanently, collapsing QPS to near zero
- With timeout: Query is cancelled, counted as failure, and doesn't distort overall QPS or block execution flow

### 2. Think Time Behavior (think_time_ms)

**Purpose**: Model real-world pacing between queries to simulate realistic traffic patterns.

**Formula**: `QPS = concurrency / (average_query_RTT + think_time)`

**Simulates**:
- User think time (reading results before next action)
- Service queueing time
- Application-level backoffs
- Downstream dependencies

**Without think_time** (think_time_ms = 0):
- Workers execute at maximum possible rate
- Measures theoretical peak performance
- "Burn the engine at max RPM" mode

**With think_time** (think_time_ms > 0):
- Shapes workload into representative traffic patterns
- More realistic benchmarking

**Examples**:

**Web workload simulation**:
```yaml
workload:
  concurrency: 50
  duration_seconds: 120
  think_time_ms: 500  # User reads page, thinks, clicks next
  # Result: ~100 ops/sec sustained
```

**Microservice workload**:
```yaml
workload:
  concurrency: 20
  think_time_ms: 30  # Service waits on downstream, reissues query
  # Result: Throttles to traffic-realistic conditions
```

**Implementation**:
```python
def worker_func():
    while should_continue():
        query = select_query()
        execute_query(query)

        if config.think_time_ms > 0:
            time.sleep(config.think_time_ms / 1000.0)
```

### 3. QPS Calculation - MANDATORY APPROACH

**Rule**: QPS **MUST ALWAYS** use actual measured elapsed time, **NEVER** config duration.

**Why this is critical**:

Real workload runners have timing variations:
- Warmup phase duration varies
- Worker thread scheduling jitter
- Thread shutdown delays
- Python GC pauses
- Network latency variation

**Even if configured for 120s, actual runtime might be**:
- 119.3s
- 121.8s
- 118.9s

**Impact of using wrong calculation**:

**Example - Wrong schema appears faster**:

```
Variant A:
  configured: 120s, actual: 115s, queries: 19,500
  Wrong QPS (using config): 19,500 / 120 = 162.5 QPS
  Correct QPS: 19,500 / 115 = 169.6 QPS

Variant B:
  configured: 120s, actual: 122s, queries: 20,200
  Wrong QPS (using config): 20,200 / 120 = 168.3 QPS (seems 3.6% faster!)
  Correct QPS: 20,200 / 122 = 165.6 QPS

Result: Using config duration shows B as 3.6% faster
Reality: Using actual time shows A is 2.4% faster

YOU LITERALLY CONCLUDE THE WRONG SCHEMA IS FASTER.
```

**MANDATORY implementation**:

```python
# In workload_runner.py
def run_workload(config, client):
    # Phase 1: Warmup (not measured)
    run_warmup(...)

    # Phase 2: Measurement
    workload_start_epoch_ms = time.time() * 1000

    # Run concurrent workers
    records = run_concurrent_workers(...)

    workload_end_epoch_ms = time.time() * 1000
    workload_elapsed_secs = (workload_end_epoch_ms - workload_start_epoch_ms) / 1000.0

    return {
        'records': records,
        'workload_start_epoch_ms': workload_start_epoch_ms,
        'workload_end_epoch_ms': workload_end_epoch_ms,
        'workload_elapsed_secs': workload_elapsed_secs
    }

# In reporter.py
def calculate_qps(count_successful_queries, workload_elapsed_secs):
    return count_successful_queries / workload_elapsed_secs
```

**Output contract - MUST emit in CSV/Markdown**:
- `workload_start_epoch_ms`
- `workload_end_epoch_ms`
- `workload_elapsed_secs`
- `qps = count_successful_queries / workload_elapsed_secs`

**Measurement time window**:
- **Starts**: Immediately after warmup completes
- **Ends**: After last worker stops issuing queries

### 4. Workload Query Discovery - Two Modes

**Problem**: Do we need to list every query in config, or can we auto-discover from disk?

**Solution**: Support BOTH modes

#### Mode 1: Explicit Mode (when `workload.queries` is present)

Use when you want control over query selection and weights.

```yaml
workload:
  path: "baseline"
  queries:
    - file: "q01_latency.sql"
      weight: 10
    - file: "q02_throughput.sql"
      weight: 1
    # weight defaults to 1 if omitted
```

**Behavior**:
- Resolve each file relative to `workload.path` with variant→project fallback
- Use specified weights
- Stable query set independent of disk contents

**Benefits**:
- Explicit subset selection
- Per-query weighting
- Exclude problematic queries (e.g., debug queries)
- Maintain stable benchmark even if extra files added to directory

#### Mode 2: Auto-Discovery Mode (when `workload.queries` is absent)

Use when you want "run all queries in this folder with equal weight".

```yaml
workload:
  path: "baseline"
  # No queries block - auto-discover all *.sql
```

**Behavior**:
1. List all `*.sql` files under effective workload path:
   - First: `VARIANT_ROOT/workloads/baseline/*.sql`
   - Then: `PROJECT_ROOT/workloads/baseline/*.sql`
   - If filename exists in both, variant wins (override semantics)

2. Build internal queries list:
   ```python
   queries = [
       {"file": "q01_latency.sql", "weight": 1},
       {"file": "q02_throughput.sql", "weight": 1},
       # ... all discovered .sql files
   ]
   ```

3. Proceed exactly as if explicitly specified

**Benefits**:
- Zero config ceremony for simple cases
- Just drop queries in folder and run
- Natural for exploratory benchmarking

**Implementation**:
```python
def load_queries(config):
    if config.workload.queries:
        # Explicit mode
        return normalize_explicit_queries(config.workload.queries)
    else:
        # Auto-discovery mode
        return discover_queries_from_disk(config.workload.path)

def discover_queries_from_disk(workload_path):
    queries = {}

    # Project-wide queries
    project_queries = glob(f"{PROJECT_ROOT}/workloads/{workload_path}/*.sql")
    for path in project_queries:
        filename = os.path.basename(path)
        queries[filename] = {"file": filename, "weight": 1, "path": path}

    # Variant overrides (overwrite if same filename)
    variant_queries = glob(f"{VARIANT_ROOT}/workloads/{workload_path}/*.sql")
    for path in variant_queries:
        filename = os.path.basename(path)
        queries[filename] = {"file": filename, "weight": 1, "path": path}

    return list(queries.values())
```

**Config schema update**:
```yaml
workload:
  name: "baseline"
  path: "baseline"

  # OPTIONAL: If omitted, all *.sql in workloads/<path>/ are used with weight=1
  queries:
    - file: "q01_latency.sql"
      weight: 10
    - file: "q02_throughput.sql"
      weight: 1
```

---

## Updated Config Schema

```yaml
project: "default"
variant: "variant_a"

clickhouse:
  host: "localhost"
  port: 8123
  user: "default"
  password: ""
  database: "bench"
  connection_pool_size: 20
  timeout_seconds: 300

schema:
  fail_on_error: true
  fresh: true

data:
  load_method: "http"
  truncate_before_load: true
  load:
    - table: "trades"
      file: "trades.csv"
      format: "CSVWithNames"
    - table: "prices"
      file: "prices.parquet"
      format: "Parquet"

workload:
  name: "baseline"
  path: "baseline"

  # OPTIONAL: If omitted, auto-discover all *.sql with weight=1
  queries:
    - file: "q01_latency.sql"
      weight: 10
    - file: "q02_throughput.sql"
      weight: 1

  concurrency: 8
  duration_seconds: 120
  ramp_up_seconds: 10
  warmup_queries: 20
  think_time_ms: 50           # Sleep between queries per worker
  max_errors: 100
  query_timeout_seconds: 60   # Abort queries exceeding this duration

  # Optional query parameterization
  parameters:
    user_id:
      type: random_int
      min: 1
      max: 1000
    date:
      type: random_choice
      values: ["2024-01-01", "2024-06-01", "2024-12-31"]

metrics:
  use_query_log: true
  query_log_wait_seconds: 10
  output_csv: "results/baseline_variant_a.csv"
  output_md:  "results/baseline_variant_a.md"
```

---

## Enhanced Reporter Output Contract

### CSV Output

**Required columns**:
```
query_name,count,errors,error_rate,qps,p50_ms,p95_ms,p99_ms,avg_read_rows,avg_read_bytes,avg_memory_usage
```

**Additional metadata rows** (prepend to CSV):
```
# Benchmark Metadata
# workload_start_epoch_ms: 1234567890123
# workload_end_epoch_ms: 1234567890243
# workload_elapsed_secs: 120.123
# project: default
# variant: variant_a
# concurrency: 8
# clickhouse_version: 24.1.1
```

### Markdown Output

Include summary section:

```markdown
# Benchmark Results: baseline (variant_a)

## Run Metadata
- **Workload Duration**: 120.123 seconds (configured: 120s)
- **Start Time**: 2024-01-15 14:30:00.123 UTC
- **End Time**: 2024-01-15 14:32:00.246 UTC
- **Project**: default
- **Variant**: variant_a
- **Concurrency**: 8
- **ClickHouse Version**: 24.1.1

## Query Performance

| Query | Count | QPS | p50 (ms) | p95 (ms) | p99 (ms) | Errors | Avg rows read | Avg bytes read |
|-------|-------|-----|----------|----------|----------|--------|---------------|----------------|
| q01_latency | 1000 | 8.33 | 12 | 25 | 40 | 0 | 1.2M | 45MB |
| q02_tput | 100 | 0.83 | 120 | 250 | 400 | 2 | 15M | 500MB |

## Summary
- **Total Queries**: 1100
- **Successful**: 1098 (99.8%)
- **Failed**: 2 (0.2%)
- **Overall QPS**: 9.15
```

---

## Updated ExecutionRecord Schema

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ExecutionRecord:
    query_id: str              # Unique ID for joining with query_log
    query_name: str            # Filename (e.g., "q01_latency.sql")
    executed_sql: str          # Actual SQL after parameter substitution
    started_at: datetime       # Query start timestamp
    finished_at: datetime      # Query end timestamp
    duration_ms: float         # Client-side measured duration
    success: bool              # True if query succeeded
    error_message: str | None  # Error details if failed (timeout, exception, etc.)
```

**Why `executed_sql` field is critical**:
- Debug parameter generation issues
- Understand what actually ran when queries fail
- Reproduce failures manually
- Audit benchmark correctness

---

## Workload Runner Implementation (Complete)

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import uuid
from typing import List

def run_workload(config, client) -> dict:
    """
    Run benchmarking workload with proper warmup and measurement phases.

    Returns:
        dict with:
            - records: List[ExecutionRecord]
            - workload_start_epoch_ms: float
            - workload_end_epoch_ms: float
            - workload_elapsed_secs: float
    """
    # Load queries (explicit or auto-discovered)
    queries = load_queries(config)
    query_pool = build_weighted_pool(queries)

    # Phase 1: Single-threaded warmup (NOT measured)
    logger.info(f"Running {config.warmup_queries} warmup queries...")
    for i in range(config.warmup_queries):
        query = random.choice(query_pool)
        params = generate_params(config.parameters) if config.parameters else {}
        sql = query['sql'].format(**params)
        try:
            client.execute(sql)
        except Exception as e:
            logger.debug(f"Warmup query {i} failed: {e}")

    logger.info("Warmup complete. Starting measurement phase...")

    # Phase 2: Concurrent measurement phase
    workload_start_epoch_ms = time.time() * 1000

    records = []
    error_count = 0
    stop_event = threading.Event()

    def worker_func() -> List[ExecutionRecord]:
        """Worker thread that executes queries until duration expires."""
        local_records = []
        worker_start = time.time()

        while not stop_event.is_set():
            # Check if duration exceeded
            if time.time() - worker_start > config.duration_seconds:
                break

            # Check error threshold
            if error_count > config.max_errors:
                logger.error(f"Error threshold exceeded ({error_count} > {config.max_errors})")
                stop_event.set()
                break

            # Select query
            query = random.choice(query_pool)
            query_name = query['file']

            # Generate parameters
            params = generate_params(config.parameters) if config.parameters else {}
            executed_sql = query['sql'].format(**params)

            # Generate unique query_id
            query_id = f"{query_name}_{uuid.uuid4()}"

            # Execute
            started_at = datetime.now()
            success = True
            error_message = None

            try:
                client.execute(
                    executed_sql,
                    settings={'query_id': query_id}
                )
            except httpx.ReadTimeout:
                success = False
                error_message = f"Query timeout after {config.query_timeout_seconds}s"
                error_count += 1
            except Exception as e:
                success = False
                error_message = str(e)
                error_count += 1

            finished_at = datetime.now()
            duration_ms = (finished_at - started_at).total_seconds() * 1000

            # Record execution
            record = ExecutionRecord(
                query_id=query_id,
                query_name=query_name,
                executed_sql=executed_sql,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                success=success,
                error_message=error_message
            )
            local_records.append(record)

            # Think time
            if config.think_time_ms > 0:
                time.sleep(config.think_time_ms / 1000.0)

        return local_records

    # Run workers
    with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
        futures = [executor.submit(worker_func) for _ in range(config.concurrency)]

        for future in as_completed(futures):
            try:
                worker_records = future.result()
                records.extend(worker_records)
            except Exception as e:
                logger.error(f"Worker failed: {e}")

    workload_end_epoch_ms = time.time() * 1000
    workload_elapsed_secs = (workload_end_epoch_ms - workload_start_epoch_ms) / 1000.0

    logger.info(f"Measurement complete. Duration: {workload_elapsed_secs:.3f}s, Queries: {len(records)}")

    return {
        'records': records,
        'workload_start_epoch_ms': workload_start_epoch_ms,
        'workload_end_epoch_ms': workload_end_epoch_ms,
        'workload_elapsed_secs': workload_elapsed_secs
    }
```

---

## Path Resolution Rules (from Plan4)

### Query Resolution

For `workload.path = "baseline"` and `queries[].file = "q01_latency.sql"`:

**Resolution order**:
1. `VARIANT_ROOT/workloads/baseline/q01_latency.sql`
2. `PROJECT_ROOT/workloads/baseline/q01_latency.sql` (fallback)
3. Error if neither exists

**Why this design**:
- ✅ Clean cognitive model: `path` defines grouping, `file` defines unit
- ✅ Matches directory structure naturally
- ✅ Enables swapping workload sets with single line change
- ✅ Keeps config readable
- ✅ Enables workload-wide metadata/parameterization in future

### Schema Resolution

1. Project-wide schemas first: `PROJECT_ROOT/schemas/*.sql` (sorted)
2. Variant schemas next: `VARIANT_ROOT/schemas/*.sql` (sorted)

### Data Resolution

For each `data.load[].file`:
1. `VARIANT_ROOT/data/<file>`
2. `PROJECT_ROOT/data/<file>` (fallback)
3. Error if neither exists

---

## Repository Structure

```
ch-harness/
  pyproject.toml
  README.md

  harness/
    __init__.py
    config.py
    clickhouse_client.py
    schema_loader.py
    data_loader.py
    workload_runner.py
    metrics_collector.py
    reporter.py
    comparator.py
    parameter_generator.py
    utils.py
    exceptions.py
    cli.py

  projects/
    default/
      configs/
        example_basic.yml
        example_weighted.yml
        example_params.yml

      schemas/           # Project-wide schemas (optional)
      data/              # Project-wide data (optional)
      workloads/         # Project-wide workloads
        baseline/
          q01_latency.sql
          q02_throughput.sql
        heavy/
          q01_full_scan.sql

      variants/
        default/
          schemas/
            001_create_tables.sql
          data/
            trades.csv

        variant_a/
          schemas/
            001_create_tables.sql
          data/
            trades.csv
            prices.parquet
          workloads/      # Variant-specific workload overrides (optional)
            baseline/
              q01_latency.sql  # Overrides project-wide version

      results/
        .gitkeep
```

---

## Dependencies

```toml
[project]
name = "ch-harness"
version = "0.1.0"
dependencies = [
    "httpx>=0.27.0",      # HTTP client with connection pooling and timeout support
    "pyyaml>=6.0",        # Config parsing
    "pydantic>=2.0.0",    # Config validation
    "pandas>=2.0.0",      # Percentile calculations
    "pyarrow>=14.0.0",    # Parquet support
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "black>=24.0.0",
    "ruff>=0.1.0",
]
```

---

## Summary of All Critical Decisions

| Topic | Decision | Source | Rationale |
|-------|----------|--------|-----------|
| Warmup timing | Single-threaded BEFORE workers | User clarification | Ensures accurate cache warming |
| QPS calculation | Actual measured time | Appendix1 | Prevents statistical distortion, maintains fidelity |
| CSV headers | ClickHouse CSVWithNames | User clarification | Native, efficient |
| Query resolution | Relative to workload.path | Appendix1 | Clean, scalable, readable |
| Query discovery | Auto-discover OR explicit | Appendix1 | Ergonomics + control |
| Query timeout | Per-query hard timeout | Appendix1 | Prevents worker blocking |
| Think time | Configurable sleep between queries | Appendix1 | Realistic traffic simulation |
| max_rows | Defer to Phase 3 | User clarification | Not critical for v1 |
| Output metadata | Include timing metadata | Appendix1 | Traceability and accuracy |

---

## Final Assessment

**Status**: ✅ **READY FOR IMPLEMENTATION**

**Overall Score**: 9.5/10

**All critical requirements defined**:
- ✅ Warmup architecture (single-threaded pre-measurement)
- ✅ QPS calculation (mandatory actual time approach)
- ✅ Query timeout behavior (abort and continue)
- ✅ Think time semantics (realistic pacing)
- ✅ Query discovery modes (auto + explicit)
- ✅ Output metadata contract (timing fields required)
- ✅ Path resolution (variant→project fallback)

**Key improvements from appendix1**:
1. **Query timeout**: Critical for preventing worker thread blocking
2. **QPS mandate**: Prevents benchmarking errors that could reverse conclusions
3. **Query auto-discovery**: Reduces config ceremony for simple cases
4. **Think time clarity**: Enables realistic workload simulation
5. **Output metadata**: Ensures traceability and reproducibility

**This specification is production-ready** with comprehensive error handling, realistic workload modeling, and accurate measurement guarantees.
