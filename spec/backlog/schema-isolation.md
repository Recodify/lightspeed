## multi-variant schemas

### As-is

If running a config with multple variants, the last variant to run is the one that is present in the db at the end of the full run. This is because we have a hardcoded database name and table name.

### To-be

It would be good to isolate them in someway so that state can be inspected post run. This ties in with the result output isolation described in ./spec/backlog/runner.md. We also have to consider multiple runs of multiple variant configs.

 Options for multplie runs:

- A: Create a new database for each run e.g. benchmark becomes benchmark-[runId]
- B: suffix the table name e.g. benchmark.events becomes benchmark.events-[variantName]-[runId]

A feels like the preferable option.

 Options for multplie variants:

- A: suffix the table name with variant name and run id e.g. benchmark.events becomes benchmark.events-[variantName]-[runId]
- B: suffix table name with variant name only and suffix datbase with runId e.g. benchmark.events becomes benchmark-[runId].events-[variantName]

B feels like the preferable option.