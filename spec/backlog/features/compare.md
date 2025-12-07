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