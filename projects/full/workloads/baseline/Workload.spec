Good, now we are asking the right question:
“Given 10M rows now and 16B later, what queries actually stress the key type?”

Principles first, then I will give you concrete SQL.

You want workloads where the key is:

in the filter

in the GROUP BY

in JOINs

in ORDER BY / TOP-K


That is where String vs UUID vs UInt32 actually matters. Simple count() barely touches it.

Below I will write queries using a generic key_col and ts so you can template them per variant.


---

Q1. Hot key point lookup within a time window

Tests: index lookup on key, then a moderately narrow scan.

-- q01_hot_key_timeslice.sql
SELECT count() AS cnt
FROM timeseriesdata
WHERE key_col = {hot_key}      -- substitute variant specific key
  AND ts >= {from_ts}
  AND ts <  {to_ts};

Run with:

{hot_key} picked from the top 1 percent most frequent keys

Multiple different hot keys over many runs


This shows you:

Cost of primary index lookup on different key encodings

Effects of repeated hot keys on cache



---

Q2. Cold key lookup (rare key)

Same as Q1 but for a rare key.

-- q02_cold_key_single.sql
SELECT count() AS cnt
FROM timeseriesdata
WHERE key_col = {rare_key};

Pick {rare_key} from the bottom 10 percent by frequency.

This separates:

“hot key in cache” vs “cold key, probably needs extra IO”

Whether LC vs int vs string changes behavior when nothing is cached



---

Q3. Group by key over a large window

Now we care about grouping and hash tables, not just index lookup.

-- q03_group_by_key.sql
SELECT
    key_col,
    count() AS cnt,
    sum(metric) AS total_metric
FROM timeseriesdata
WHERE ts >= {from_ts}
  AND ts <  {to_ts}
GROUP BY key_col;

This will:

Build a hash table keyed on your type

Touch a big slice of the data (make the window big enough to hit most rows)


This is where I expect:

String to start falling behind

UUID to lag ints

UInt16 vs UInt32 still very close but maybe separable at 16B rows



---

Q4. Top-K by key

Same as Q3 but sorted and limited.

-- q04_topk_keys.sql
SELECT
    key_col,
    count() AS cnt
FROM timeseriesdata
GROUP BY key_col
ORDER BY cnt DESC
LIMIT 100;

Tests:

GROUP BY on key

Sort on aggregate

The engine is juggling key representation in both aggregation and final sort


Again, this is where narrow ints should consistently beat long strings.


---

Q5. Join fact to dimension by key

Make a small dimension table with some attributes per key, e.g.:

-- dim_key(key_col, group_id UInt32, category String, ...)

Query:

-- q05_fact_dim_join.sql
SELECT
    d.group_id,
    count() AS cnt,
    sum(f.metric) AS total_metric
FROM timeseriesdata AS f
INNER JOIN dim_key AS d
    ON f.key_col = d.key_col
WHERE f.ts >= {from_ts}
  AND f.ts <  {to_ts}
GROUP BY d.group_id;

This tests:

Join hash table keyed by your type

Fact side probing into that hash

GROUP BY on a different attribute


Joins are where LC and big strings can really hurt if anything will.


---

Q6. Distinct keys over a big slice

Cardinality + hashing cost.

-- q06_distinct_keys.sql
SELECT
    countDistinct(key_col) AS distinct_keys
FROM timeseriesdata
WHERE ts >= {from_ts}
  AND ts <  {to_ts};

Also run a version with uniqCombined(key_col) to see if approximate methods react differently.

This tests:

hashing cost of key types

size and behavior of intermediate aggregation states



---

Q7. Mixed predicate query

More realistic composite filter, not just key equals.

-- q07_mixed_filter.sql
SELECT
    count() AS cnt,
    avg(metric) AS avg_metric
FROM timeseriesdata
WHERE key_col IN ({k1}, {k2}, {k3}, {k4}, {k5})
  AND ts >= {from_ts}
  AND ts <  {to_ts}
  AND metric BETWEEN {m_low} AND {m_high};

This stresses:

key in a small IN set

filter pushdown

combining predicates



---

How to run this in a way that is not garbage

Given you have 10M now but design for 16B:

1. Use the same query shapes now. They will scale.


2. For each query:

pick multiple parameter sets (different keys and time windows)

run 30–100 iterations per variant

randomise order of variants per iteration, do not always hit string first



3. Capture p50, p95 and QPS like you already do, but interpret differences:

< 3 percent: noise unless consistent across many queries

3–10 percent: real but small

> 10 percent: meaningful






With these query types you will actually be testing the impact of key representation:

point lookups

hot vs cold keys

grouping

top-k

joins

distincts


That is enough to decide:

“String LC is fine” vs “we really prefer UInt32”

and to stop worrying about whether UInt16 buys you anything over UInt32 in the real world.
