query_timeout_seconds
Purpose:

This enforces a hard execution timeout per query.

Meaning:

If ClickHouse takes longer than this threshold,

The client should abort the request

The workload should mark that execution as failed

And continue to the next iteration

This exists because:

Sometimes queries stall due to locks, memory pressure, merges, disk latency etc

In benchmarking, you never want a single query to block a worker indefinitely

You want bounded stalls, not cascading jams

What it protects against:
Without timeout:

Worker thread could end up stuck permanently during slow queries
Example:

execute takes 120 seconds and hangs → throughput collapses → results meaningless.

With timeout:

Query that exceeds, say, 10 seconds will:

be cancelled

recorded as failure

not distort overall QPS

not block worker execution flow

Analogy:

This is like per-unit SLA enforcement.

If query exceeds target SLO, you count it as failure.

think_time_ms
Purpose:

Model real user-side or service-side pacing.

Where QPS = concurrency / (RTT + think_time)

It simulates:

user think time

service queueing time

app-level backoffs

Why this matters in benchmarking

Without think time:

Each worker executes as fast as physically possible

You measure theoretical peak performance

This is "burn the engine at max RPM" mode

With think time:

You shape the workload into representative traffic patterns.

Real examples
Example 1 — Web workload simulation

User reads a page, thinks a bit, clicks next:

duration_seconds = 120
think_time_ms = 500
concurrency = 50


→ roughly 100 ops/sec sustained.

Example 2 — Microservice workload

Service computed → waits on downstream → reissues query:

think_time_ms = 20–50 ms


→ throttles throughput to traffic-realistic conditions.

Here’s where both matter together
You said:
For QPS (queries per second) calculation: The workload runs for approximately duration_seconds (e.g., 120s), but might run a bit longer or shorter. Should QPS be calculated using the configured 120s or the actual measured elapsed time?

❯ 1. Actual measured time
     More accurate - accounts for actual runtime variations. QPS = count / (end_time - start_time).
  2. Config duration
     Simpler - just use configured duration_seconds value. QPS = count / 120.
  3. Type something.
ChatGPT said:

Use actual measured elapsed time. Every time.

Anything else is fake precision.

Let’s walk through this properly.

Why actual elapsed time must be used

Your workload runner is not a synchronous loop that magically starts and stops at an exact timestamp. Real variation happens:

warmup phase duration won’t be exact

startup ramp and worker thread scheduling take time

thread shutdown delays vary

Python scheduling jitter

OS scheduler delays

GC pauses

network latency variation

Even if you intend exactly 120 seconds:

You will actually run something like:

119.3s
121.8s
118.9s


because:

workers begin staggered

some threads finish early because timeout aborted a request

others complete late

If your calculation assumes 120s, you distort throughput.

Real example
Actual behaviour:

Query count: 20,500

Actual elapsed time: 118.9s

True QPS:

20500 / 118.9 = 172.45 QPS

Fake formula using config:
20500 / 120 = 170.83 QPS


Looks harmless?
That’s a 0.95% distortion.

Now imagine workloads where timing discrepancies compound.

Also imagine comparing two variants with small differences.

That one percent matters.

Worse case scenario comparison

Variant A:

configured: 120s

actual: 115s

executed: 19,500 queries

Variant B:

configured: 120s

actual: 122s

executed: 20,200 queries

If you incorrectly use configured value 120s:

A: 19,500 / 120 = 162.5 QPS
B: 20,200 / 120 = 168.3 QPS
Difference: ~3.6%


But correct real QPS:

A: 19,500 / 115 = 169.6 QPS
B: 20,200 / 122 = 165.6 QPS
Difference: –2.41%  (reversed sign)


You literally conclude the wrong schema is faster.

That’s unacceptable.

The rule

QPS must always be calculated as total_successful_queries / actual_elapsed_measurement_time.

Where measurement time starts:

Immediately after warmup completes.

Where it ends:

After the last worker stops issuing queries.

Record these timestamps explicitly.

Additional requirement to embed into spec:

The harness must emit these numbers explicitly:

workload_start_epoch_ms
workload_end_epoch_ms
workload_elapsed_secs


And QPS must be:

count_successful_queries / workload_elapsed_secs

Final answer

Always actual measured elapsed time.
Never use the configured duration.

That maintains fidelity, avoids statistical distortion, and prevents variants from comparing incorrectly due to thread scheduling jitter.

This should be written into the benchmark output contract.

You said:
In the latest plan,. the config has both workload.path and workload.queries[].file. For example: path="baseline" and file="q01_latency.sql". Should the harness look for the file at workloads/baseline/q01_latency.sql (filename relative to path), or does queries[].file contain the full path from workloads/ directory?

❯ 1. Relative to path
     queries[].file is just the filename. Full path = workloads/<path>/<file>. Cleaner, matches directory structure in plan4.
  2. Full path from workloads/
     queries[].file contains full path like "baseline/q01.sql". Makes path field less useful.
  3. Type something.

Enter to select · Tab/Arrow keys to navigate · Esc to cancel
ChatGPT said:

1. Relative to path.

That is the clean, unambiguous, and intention-aligned answer.

Let me justify it clearly and decisively.

Why file must be relative to workload.path

Given:

workload:
  path: "baseline"
  queries:
    - file: "q01_latency.sql"
    - file: "q02_throughput.sql"


The harness must look here:

PROJECT_ROOT/workloads/baseline/q01_latency.sql
PROJECT_ROOT/workloads/baseline/q02_throughput.sql


and then apply override semantics:

Correct resolution order:
1. Variant-specific workload path:
VARIANT_ROOT/workloads/baseline/q01_latency.sql


if missing, fallback to:

2. Project-wide workload path:
PROJECT_ROOT/workloads/baseline/q01_latency.sql

Why this is the right choice
✔ Cleaner cognitive model

workload.path defines the workload grouping
file defines the unit under that grouping

That is intuitive and maps to every standard benchmarking harness approach.

✔ Matches directory-driven semantics in our structure

We already have:

workloads/
  baseline/
  heavy/


where each folder semantically represents test class or scenario.

To force the user to write:

file: baseline/q01_latency.sql


is redundant and pollutes configs.

✔ Enables swapping workload sets with a single line change

Change:

workload.path: "baseline"


to

workload.path: "heavy"


Everything still resolves.

If filenames were full paths, you’d have to rewrite every entry.

That’s brittle.

✔ Enables workload-wide parameterisation

This is the big one.

Because grouping is explicit, we can later add:

metadata per workload directory

default parameters per workload

weights per workload group

workload-level tags

global warmup scripts

Everything becomes “scoped to a workload directory” logically.

✔ Keeps config readable

Compare:

Bad (full explicit pathing):

queries:
  - file: "baseline/q01_latency.sql"
  - file: "baseline/q02_throughput.sql"
  - file: "baseline/q03_full_scan.sql"


vs.

Good:

path: "baseline"
queries:
  - file: "q01_latency.sql"
  - file: "q02_throughput.sql"
  - file: "q03_full_scan.sql"


The second example is immediately comprehensible.

Final rule to put in the spec

workload.queries[file] must always be resolved relative to workload.path.

Lookups follow:

projects/<project>/variants/<variant>/workloads/<path>/<file>

projects/<project>/workloads/<path>/<file>

If neither exists, validation must fail and execution must stop.

That is unambiguous, scalable, and fully consistent with the rest of the design model.

You said:
do we need to register queries in the config if we don't want an explict weight? Can we just resolve from disk
ChatGPT said:
Thought for 7s

Short answer:

No, you shouldn’t have to list queries in the config if you don’t care about weights or subsets. We can absolutely support “just resolve everything from disk”.

Let’s make this precise.

Two modes for workloads

I’d design it like this:

1. Explicit mode (when workload.queries is present)

Use this when you want control.

workload:
  path: "baseline"
  queries:
    - file: "q01_latency.sql"      # weight defaults to 1 if omitted
      weight: 10
    - file: "q02_throughput.sql"
      weight: 1


Behaviour:

For each entry:

resolve file relative to workload.path, with variant-then-project logic:

VARIANT_ROOT/workloads/baseline/q01_latency.sql

else PROJECT_ROOT/workloads/baseline/q01_latency.sql

If weight is missing, treat it as 1.

You get:

explicit subset selection

per query weighting

stable query set independent of whatever is lying around on disk

This is the “I know exactly what I want to benchmark” mode.

2. Auto-discovery mode (when workload.queries is absent)

Use this when you just want “run all the queries in this folder evenly”.

Config:

workload:
  path: "baseline"
  # no queries: block at all


Behaviour:

List all .sql files under the effective workload path:

variant first: VARIANT_ROOT/workloads/baseline/*.sql

then project: PROJECT_ROOT/workloads/baseline/*.sql

if a filename exists in both, variant wins

Build queries list internally where:

queries = [
  {"file": "q01_latency.sql", "weight": 1},
  {"file": "q02_throughput.sql", "weight": 1},
  ...
]


Proceed exactly as if it had been specified explicitly.

So the rule becomes:

If workload.queries is defined, use it.
If it’s missing or empty, auto-discover *.sql under workload.path and treat all with weight 1.

Why keep both modes

You want both because:

Early on, it’s nice to just drop queries in a folder and run them with zero config ceremony.

Later, you’ll absolutely want to:

exclude a nasty O(N²) debug query

give 10x weight to “hot path” queries

keep a stable benchmark set even if someone dumps extra SQL files into that directory

Explicit list mode gives you precision.
Auto mode gives you ergonomics.

Spec tweak to bake this in

We just update the workload spec like this:

workload:
  name: "baseline"
  path: "baseline"

  # Optional. If omitted, all *.sql in workloads/<path>/ are used with weight=1
  queries:
    - file: "q01_latency.sql"
      weight: 10
    - file: "q02_throughput.sql"
      weight: 1


And in the implementation:

if config.workload.queries:
    queries = normalise_explicit_queries(...)
else:
    queries = discover_queries_from_disk(...)


So to answer your question very directly:

No, you don’t need to register queries in the config if you’re happy with “all queries, equal weight”.

Yes, you can absolutely just resolve from disk, and only drop into explicit queries[] when you want fine-grained control.