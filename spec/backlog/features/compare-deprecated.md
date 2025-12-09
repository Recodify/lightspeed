# Comparison

We currently write out a basic markdown report comparing the results of a multi-variant run.


## As-Is


# Benchmark Comparison

**Baseline (A):** `/home/sam/code/lightspeed/projects/keyselectionlocal/results/basic/opalescentbasilisk/variant0/results.csv`

**Comparison (B):** `/home/sam/code/lightspeed/projects/keyselectionlocal/results/basic/opalescentbasilisk/variant1/results.csv`

## Performance Comparison

| Query | A p50 (ms) | B p50 (ms) | Δ p50 | A p95 (ms) | B p95 (ms) | Δ p95 | A QPS | B QPS | Δ QPS |
|-------|------------|------------|-------|------------|------------|-------|-------|-------|-------|
| q01_agg_max.sql | 10.06 | 8.84 | -12.13% | 19.19 | 15.96 | -16.83% | 354.99 | 410.49 | +15.63% |

## Interpretation

- **Positive Δ p50/p95**: Latency increased (slower)
- **Negative Δ p50/p95**: Latency decreased (faster)
- **Positive Δ QPS**: Throughput increased (better)
- **Negative Δ QPS**: Throughput decreased (worse)
- **new**: Query only in comparison (B)
- **removed**: Query only in baseline (A)
- **+∞**: Baseline value was zero


## To Be


I don't find the above intuitive to read. Some thoughts on how this can be improved:

- instead of A and B in table headers, use the variant name
- colorise the output red = slower/loser green = faster/winner
- Add qualative analysis in plain text.
  - Perhaps we can generate this algorithmically.
  - Perhaps we need an LLM
    - User supplies api_key?
    - Use a local llm and supply scripts to get oolama stood up in docker?
- Some graphs would be nice.
- Generate an html report?
- Generate a pdf report?

## Goal

I want an easy to read report that clearly states the difference between the variants and which one is better and why. This is to help inform team memebers on the impacts of schema design decisions in clickhouse.

### Context from a chatgpt chat

🔍 QUESTIONS
1. What is the grain of comparison?

The spec uses language like:

single run vs single run

single run vs multiple runs

multiple sets

But it is ambiguous whether comparison is:

A. Comparing full dataset aggregates (across all metrics per run)
B. Comparing individual metrics one-by-one
C. Comparing derived summary statistics only (e.g. best-of, average, deltas)

This matters a lot for data structures and output shape.

Which applies?

2. What is the canonical identity of a “run”?

Candidate keys visible in the repo:

run timestamp

run directory index

run metadata file

explicit run ID

If this becomes a persistent tool, it needs determinism.

Preferred:

A named run_id persisted somewhere canonical

Is that the intention?

3. Do you expect cross-metric alignment by timestamp?

Metrics often differ in cardinality. Examples:

metric_A: 1000 samples
metric_B: 83 samples
metric_C: 1 sample

You could align by:

A. Index-based alignment (lazy but brittle)
B. Nearest-timestamp interpolation
C. Aggregation to sampling windows
D. No alignment (only aggregated comparison)

Which is correct?

4. What output medium will be treated as primary truth?

Spec mentions a table of differences, a “scorecard,” and possible visualisation.

Which of these is the primary deliverable?

Machine-readable JSON/dict

Human-readable tabular console output

CSV/markdown files

HTML report

What is THE canonical output you expect another harness component to consume?

5. Is comparison directional or symmetric?

Example:
RunA median latency = 400ms
RunB median latency = 250ms

Which is truth?

A. RunB is better
B. RunA has regression
C. Statistical difference but no semantic judgement

Given you're not backwards compatible and you're iterating fast, I suspect:

directional regression detection is desired

Confirm or deny.

6. What is the nature of metrics?

Your code hints at values like:

durations

counts

ratios

throughput

arbitrary numeric values

Some comparisons make no sense without knowing what higher/lower means.

Do you want comparison logic:

A. Global and generic (max is worse?)
B. Explicit per-metric semantics defined somewhere?

Opinionated recommendation upfront

You are in the dangerous early phase where over-generalisation will screw you later.

The pragmatic architecture is:

Treat comparison as:

comparing aggregated statistics of runs

not raw streams

Require:

runs emit stats.json files describing:

{
  "metric_id": {
    "count": ...,
    "mean": ...,
    "median": ...,
    "p95": ...,
    "min": ...,
    "max": ...
  }
}

Then comparison becomes trivial:

dict-to-dict diff

optional significance highlighting

easy score weighting

Anything fancier must be deliberately implemented later, once the ergonomics of usage are real.

That choice would keep the comparator maintainable and deterministic.

Before I write the plan I require answers to:

2, 3, 4, 5

The others I can infer.

So answer these precisely:

Q2: What uniquely identifies a run?

Choose one number:

integer index

timestamp folder name

explicit run_id persisted into metadata.json

hierarchical location alone (path is identity)

Q3: Should raw time-series be aligned?

Choose one:

A. No alignment
B. Align by timestamp resolution (e.g. nearest 10ms)
C. Only compare aggregated summaries

Q4: Primary output format?

Choose one:

A. JSON (for downstream automation)
B. Markdown table
C. Console rich formatting
D. HTML artefact

Q5: Should comparison indicate improvement/regression automatically?

Choose one:

A. Yes, determine better/worse
B. No, just highlight difference magnitude
C. Only annotate differences above threshold

Reply with those five choices and I will proceed into the formal plan.

You said:
results.md
File

Data Load

Unable to display visualization

Results

Unable to display visualization
1. This should be obvious from the repo, but I'll explain anyway. A comparison is a post processing step from a test run that contains multiple variants. A variant is different scheam/table design that may or may not be faster for the given workload. When a test run is perform, each variant is deployed and the workload run against it, this is done sequentially, variant0 then variant 1 etc. When each variant completes it's test workload, it generates some result files: results.csv, results.md and data_load.csv. A comparison is a post processing step that takes the name of two variants, looks in their results.csv and generates a comparison.
2. run_id is auto generated at run time usign coolname. This is capture in the dir structure in which th results are stored (see vscode screenshot)
3. no, this will be addressed by test suite design
4. it's currently csv and md, this is likely to change in the future and should perhaps be moved to json as the primary canonical result. In fact, I am going to do that before we make this change. So assume that results.csv becomes results.json and will also include data_load metrics.
5. I'm not sure I'm clear on the question but i feel like it is an important one
6. you can now see this in the attached, however we may need to supplement