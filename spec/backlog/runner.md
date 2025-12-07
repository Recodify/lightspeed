## Runtime output

### As is

Currently when you run a test scenario via via, the output you see whilst it's runing are the http requests and responses.

### To be

It would be nice to have more meaningful output whilst running. Option of options for this:

- A: simple terminal progress with stats
- B: as above but with some sort of ascii plotting to show states, think ascii art line chart
- C: do something with jypter
- D: do something with matlibplot
- E: introduce a web runner and have plotting, progress and stats on there.


## Results


### As is
Currently the results that are written to disk are not scoped to a given run. This means you can't compare easily across runs as the resutls from the previous run are overwritten.

### To be
Create a sub dir under ./projects/[project name]/results for each run. Few options for naming:

- a simple monotonically incrementing int
- date + time
- both of the above