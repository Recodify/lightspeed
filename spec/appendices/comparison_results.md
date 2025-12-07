Plan for LLM
1. Context and goals

You have a multi variant ClickHouse benchmark harness.

Each variant run produces results per variant, currently written as CSV plus Markdown, with a simple comparison Markdown report that uses A and B instead of variant names and is not very intuitive.

You want to:

Make the comparison report clearly show which variant is better and why.

Use variant names instead of A and B.

Add qualitative analysis in plain language.

Add visual cues, including colors and possibly graphs.

Optionally support HTML and PDF outputs later.

Backwards compatibility is not required.

Scope is focused on:

harness/metrics_collector.py

harness/reporter.py

harness/comparator.py

but it is acceptable to touch nearby files such as harness/cli.py where needed.

Inputs this plan assumes

Spec file

https://raw.githubusercontent.com/Recodify/lightspeed/refs/heads/implement/spec/backlog/features/compare.md

Repo root

https://github.com/Recodify/lightspeed

The spec for results isolation and JSON output has either already landed, or can be implemented together with this work.

High level outcome

A comparison command that takes two result files for two variants and produces:

A structured in memory comparison model.

A human friendly Markdown comparison report, variant oriented, with clear winners and losers.

Optional HTML output that uses color and simple charts, designed so PDF export can be added later if desired.

A clear seam for future LLM based qualitative summaries but with a fully algorithmic implementation by default.

2. Decide and document the canonical results format

Before touching comparator logic, stabilise what it is comparing.

Inspect the current metrics outputs

Open harness/metrics_collector.py and harness/reporter.py.

Identify the current CSV schema for workload results and any existing JSON output.

Identify where run level and variant level metadata lives, such as:

project name

variant name

run identifier for the benchmark

workload name or path

Define a canonical JSON structure for a single variant run

The goal is to preserve all the information the comparator and reporter need, in a format that is stable over time and does not depend on a particular CSV layout.

Introduce a Python model in a new small module, for example harness/results_model.py, with simple dataclasses such as:

QueryMetric with fields like name, p50_ms, p95_ms, qps, and any other existing metrics.

VariantRunInfo with project, variant, run_id, workload_name, run_timestamp.

DataLoadMetric for data load timing and counts if those already exist in metrics.

VariantResults that wraps VariantRunInfo, a mapping of query_name to QueryMetric, and an optional data_load section.

Define the JSON schema as a direct serialisation of VariantResults.

Document this schema in a short section in the spec or README so future changes are deliberate.

Update metrics collection to emit JSON as the primary canonical output

In metrics_collector.py and reporter.py:

Build a VariantResults instance from the current collection logic.

Serialise it to results.json alongside any existing CSV or Markdown, for example in the same directory that currently gets results.csv.

Update any existing places that read results.csv to move toward the JSON, or at least keep them compatible during migration.

For this feature set, allow the comparator to assume JSON input

The compare command will treat its positional arguments as paths to results.json files for two separate variants.

If CSV input is currently supported, do not preserve it unless you explicitly want to keep that, since you stated backwards compatibility is not a concern.

3. Design a comparison domain model, separate from presentation

Keep the comparison logic independent of Markdown or HTML so you can add new renderers later.

Create comparison models, again preferably in harness/results_model.py or in a new module such as harness/comparison_model.py.

MetricDelta for a single numeric metric between two variants, including:

baseline_value

comparison_value

absolute_delta

percent_delta

direction enumeration such as FASTER, SLOWER, TIED, NEW_ONLY_IN_B, REMOVED_ONLY_IN_A.

QueryComparison for a single query name containing:

name

the raw QueryMetric values for each variant

MetricDelta instances for p50, p95, qps

a derived winner field per query, for example whichever variant is faster on p95 or by some deterministic rule.

VariantComparisonSummary with aggregated statistics such as:

how many queries favour each variant on p50

how many queries favour each on p95

how many queries favour each on qps

worst regression and best improvement.

ComparisonResult wrapping:

baseline VariantResults

comparison VariantResults

all QueryComparison instances keyed by query name

lists of queries_only_in_baseline and queries_only_in_comparison

the overall VariantComparisonSummary.

Implement a pure function in harness/comparator.py that takes VariantResults for A and B and returns ComparisonResult.

Queries present in both variants are compared metric by metric.

Queries only in baseline are marked as removed.

Queries only in comparison are marked as new.

Decide on a consistent rule for the query level winner. For example:

Prefer the variant with lower p95.

Use p50 as a tie breaker.

Optionally consider qps if latencies are tied.

Build simple direction logic with clear semantics

For latency metrics, lower is better.

For throughput metrics, higher is better.

Treat divide by zero cases explicitly and surface them as +inf or a clear label for the report.

4. Redesign comparator CLI and file level behaviour

This is the front door that users will hit.

Decide the CLI surface

In harness/cli.py keep a simple entry point, for example:

python -m harness.cli compare path_to_results_a path_to_results_b

Extend it with flags such as:

--markdown-output path for Markdown output, default in the same directory as the first input.

--html-output path for HTML report, optional.

--title "Custom title" optional.

Implement the CLI flow in cli.py

Parse args.

Load both JSON files into VariantResults using a helper function.

Feed them into the pure comparison engine to get a ComparisonResult.

Call the reporter functions described in the next section to render Markdown, and optionally HTML.

Return a non zero exit code for obvious failures, such as:

cannot parse JSON

metrics are missing the columns expected by the comparison logic

input files do not exist.

Remove or refactor any CSV based compare logic

If comparator.py currently reads CSV directly, keep a thin adapter that converts the CSV representation into VariantResults for any internal reuse, but make JSON the primary path.

5. Implement a new Markdown comparison reporter

This is the path of least resistance that will give you a big improvement with modest effort.

In harness/reporter.py add a new function such as render_comparison_markdown(comparison_result, output_path) that:

Renders a heading section with:

Project, workload name, run IDs, and variant names for A and B.

A one line summary of which variant appears to be better overall.

Renders a brief qualitative summary based on the statistics in VariantComparisonSummary.

For example, “Variant wide_index is faster on most queries for p95 latency, with a median improvement of around X percent.”

Renders a table of per query metrics with the following columns:

Query name

Variant A p50 and p95

Variant B p50 and p95

Percent delta for p95

A simple winner column that shows “A”, “B”, “tie”, “new in B” or “removed from A”.

Optionally qps values and deltas.

Uses variant names rather than just A and B in the column labels, for example “baseline_variant” and “wide_index_variant”.

Adds clear key or legend for any symbols used, for example if you add ticks or warning icons for regressions.

Add basic visual cues within the constraints of Markdown

You cannot rely on color in plain Markdown so use symbols such as:

A tick for rows where comparison is better.

A warning icon for regressions.

Keep the layout compatible with GitHub and terminal views.

Add a section for queries that exist only in one variant

List queries that are new in B.

List queries that have been removed relative to baseline.

6. Add an HTML comparison reporter, with color and graph hooks

This is where you can make the output visually compelling and where color finally makes sense.

Decide simple HTML template strategy

Use either a tiny local template engine such as Jinja, or build a string based template in reporter.py.

Keep dependencies minimal so the harness remains lightweight.

Implement render_comparison_html(comparison_result, output_path)

Include a top level summary section mirroring the Markdown content.

Use color for performance differences with a simple CSS block, for example:

Green for improvements.

Red for regressions.

Neutral color for minor changes.

Render the per query table with colored cells for latency and throughput deltas.

Add tooltips or small footnotes to explain directionality for latency versus throughput.

Add hooks for charts without overcomplicating the first version

Start with one or two simple charts such as:

A bar chart of p95 per query for both variants.

A bar chart of qps per query for both variants.

Implement charts using a simple client side library loaded from a CDN, or generate inline SVG with Python.

Keep the chart preparation code isolated so you can turn it off if it adds friction.

Prepare for optional PDF export later

Structure the HTML so it prints cleanly to PDF from a browser.

If you want a programmatic PDF export later, you can add a tiny integration with something like WeasyPrint, in a separate optional module, without baking it into the core comparator.

7. Implement algorithmic qualitative analysis with an LLM seam

You want better narrative explanation, but you do not want to couple this harness too tightly to any particular LLM provider.

Implement a pure Python description generator

Add a function such as generate_text_summary(comparison_result) that returns:

A short overall summary paragraph.

A list of notable improvements.

A list of notable regressions.

Drive it entirely from VariantComparisonSummary plus a few spotlight queries such as:

The queries with the largest improvements in p95.

The queries with the worst regressions.

Design an interface for optional LLM summarisation

Introduce an abstract ComparisonSummariser interface with a single method that returns structured summary text.

Provide a default implementation that uses the algorithmic summary function above.

Add a clearly separated extension point where a user can plug in an LLM based summariser if they configure an API key and endpoint in their own environment.

Do not implement the actual online LLM integration as part of this task, just define the seam and keep configuration in the existing YAML if and when you decide to use it.

Wire the summariser into Markdown and HTML renderers

Reporter functions call the summariser to get their textual narrative, then embed that into the top section of each report.

8. Tests and validation

Given you will hand this to an LLM for implementation, spell out concrete tests so it can self check.

Unit tests for core comparison logic

Add tests for MetricDelta calculation with:

Normal cases.

Zero baseline values.

Missing metrics.

Add tests for QueryComparison winner resolution.

Add tests for detection of new and removed queries.

Unit tests for Markdown rendering

Use a tiny synthetic ComparisonResult and assert that:

Variant names appear in headings and table headers.

Query names are present.

Direction labels such as new and removed appear where expected.

Unit tests for JSON round trip

Construct a VariantResults instance, write it to JSON, read it back, and assert equality.

Smoke test for the CLI compare command

Use a very small project in projects/ with two variants and short workloads.

Run full-run for both variants to generate two results.json files.

Run the new compare command.

Confirm that it produces Markdown and HTML reports without error.

9. Implementation order for the LLM

To keep the work tractable for a coding model, suggest this sequence.

Introduce the VariantResults and comparison model dataclasses in a new module.

Add JSON output of VariantResults in metrics_collector and reporter, preserving existing behaviour for now.

Implement the pure comparison engine that takes two VariantResults and returns ComparisonResult.

Wire harness/cli.py to load two JSON files, call the comparison engine, and call a temporary stub renderer, for example printing a minimal table.

Replace the stub renderer with the full Markdown reporter.

Add the HTML reporter and hook it into the CLI flag.

Implement the algorithmic summary function, feed it into both reporters.

Add unit tests and a basic smoke test as described.

Drop this entire section into your spec/backlog/features/compare.md as the Plan for LLM and let your code model loose on it.