# Implementation Roadmap

This roadmap turns the benchmark matrix into an execution plan that is easier to implement, verify, and discuss.

The structure is inspired by:

- Quarkus benchmark reporting style from the March 2, 2026 article at `https://quarkus.io/blog/new-benchmarks/`
- the benchmark harness split between easy local runs and stricter isolated runs in `https://github.com/quarkusio/spring-quarkus-perf-comparison`

This lab adapts those ideas to a different goal:

- compare Java 17, 21, and 25 on the same application
- compare platform threads and virtual threads where applicable
- keep the official comparison stock-only through M5
- keep any tuning work as a future note so the main question stays centered on Java-version performance

## Comparison Matrix

Every milestone should preserve the same comparison matrix unless a row is intentionally out of scope:

| Label | Java | Thread Mode | Purpose |
|---|---|---|---|
| `17-platform` | 17 | platform | long-term baseline |
| `21-platform` | 21 | platform | isolate JVM changes from Loom |
| `21-virtual` | 21 | virtual | first Loom comparison |
| `25-platform` | 25 | platform | current LTS JVM comparison |
| `25-virtual` | 25 | virtual | current Loom comparison |

The official publication path through M5 uses `stock` only.

## Milestones

### M1 - Harness and Result Integrity

Primary goal:

- make current numbers trustworthy before expanding coverage

Work:

- fix scenario-labeling bugs in runners
- make chart generation include all scenarios across versions
- align runbook and Make targets with real commands
- define a stable processed-result schema for startup, HTTP, memory, GC, concurrency, and JFR
- document confidence levels for local runs vs isolated runs

Feature comparison focus:

| Area | M1 comparison goal |
|---|---|
| Garbage collector and memory | trustworthy RSS baselines, post-load RSS, heap metadata placeholders |
| CPU usage | define output schema for CPU metrics even if collection is added in M4 |
| I/O | keep current synthetic workloads, but mark them as non-final |
| Threads / concurrency / Loom | only compare modes that are already implemented, with clear labels |
| JVM | startup, first-request, warmup, and steady-state throughput baselines |

Deliverables:

- fixed benchmark runners
- updated charts
- updated runbook
- milestone roadmap in docs

Exit criteria:

- no mislabeled aggregate scenarios
- generated charts include `aggregate-virtual` when data exists
- a new contributor can run the working commands from docs without guessing

### M2 - Real I/O Groundwork

Primary goal:

- move at least one benchmark path from synthetic in-memory work to real blocking I/O

Work:

- add a Postgres-backed read path
- seed benchmark data in Dockerized Postgres
- add at least one k6 scenario for the DB-backed path
- define how mixed workload runs should combine JSON, transform, DB, and aggregation endpoints

Feature comparison focus:

| Area | M2 comparison goal |
|---|---|
| Garbage collector and memory | compare synthetic JSON vs DB-backed reads under the same result schema |
| CPU usage | compare CPU cost per request between in-memory and DB-backed paths |
| I/O | establish a real database path as the new baseline I/O workload |
| Threads / concurrency / Loom | keep platform mode first so I/O shape is isolated from Loom changes |
| JVM | compare how each JDK behaves once request latency includes real blocking work |

Deliverables:

- DB-backed Quarkus endpoint
- Postgres seed data
- DB-backed k6 scenario

Exit criteria:

- benchmark app can serve one repeatable DB-backed scenario
- Dockerized Postgres contains deterministic seed data
- the new scenario is documented as optional groundwork for later milestones

### M3 - Loom and Concurrency Study

Primary goal:

- compare platform threads and virtual threads with the same blocking workload

Work:

- replace purely synthetic aggregate behavior with real downstream blocking work
- run concurrency ramps at multiple VU levels
- publish a dedicated `concurrency-summary.csv`
- generate platform-vs-virtual charts

Feature comparison focus:

| Area | M3 comparison goal |
|---|---|
| Garbage collector and memory | compare thread-related footprint and allocation growth under load |
| CPU usage | observe scheduler overhead and CPU cost at rising concurrency |
| I/O | compare blocking behavior with JDBC or downstream HTTP fan-out |
| Threads / concurrency / Loom | main focus of the milestone |
| JVM | compare `21-platform` vs `21-virtual` and `25-platform` vs `25-virtual` before cross-version claims |

### M4 - GC, JFR, and CPU Deep Dive

Primary goal:

- move from top-line performance to runtime-behavior analysis

Work:

- add structured GC logging
- add GC parsing and `gc-summary.csv`
- capture JFR files for representative scenarios
- add CPU and memory timeline collection
- document hottest methods, allocation hotspots, and pause distribution

Feature comparison focus:

| Area | M4 comparison goal |
|---|---|
| Garbage collector and memory | GC count, pause time, live-set growth, allocation pressure |
| CPU usage | CPU-seconds per scenario, hot methods, safepoints, scheduler effects |
| I/O | separate blocked time from CPU time |
| Threads / concurrency / Loom | inspect parking, pinning, scheduler events |
| JVM | main focus of the milestone through JFR, GC logs, and warmup behavior |

### M5 - Containerized and Isolated Java-Version Comparison

Primary goal:

- move from convenient local runs to cleaner stock Java-version comparisons under containerized and isolated conditions

Work:

- keep the official run matrix stock-only
- introduce dual execution lanes:
  - `macos-container` for local comparative runs
  - `linux-container` for higher-confidence container-aware conclusions
- write raw results under `results/raw/stock/{lane}/javaXX/{track}/`
- add lane and container metadata to every processed output
- generate lane-specific charts instead of creating a separate reporting format

Feature comparison focus:

| Area | M5 comparison goal |
|---|---|
| Garbage collector and memory | constrained-memory behavior and RSS under explicit limits |
| CPU usage | throttling, quotas, and per-core efficiency under stock settings |
| I/O | cleaner observations without same-host interference between app and load generation |
| Threads / concurrency / Loom | platform and virtual behavior under explicit CPU and memory limits |
| JVM | higher-confidence stock Java-version comparisons in containerized lanes |

## Future Note

Possible later work:

- evaluate whether light tuning changes Java-version rankings
- revisit whether light-tuning changes platform-vs-virtual comparisons in meaningful ways

This is intentionally outside the current milestone plan.

## Immediate Backlog

### Next changes to land

1. Expand JMH coverage so the benchmark matrix matches the documented JVM microbenchmark scope.
2. Run the full comparison matrix under `stock` on `macos-container`, then repeat on `linux-container`.
3. Strengthen the observability suite with longer representative runs and publication-quality interpretation notes.

### Open questions for later milestones

- Should the main realistic I/O workload use JDBC, downstream HTTP fan-out, or both?
- Should mixed-workload runs be weighted by request mix or time-sliced by scenario?
- If tuning is revisited later, should it standardize on one heap policy across all JDKs or preserve each JDK default first?
- Which final claims require Linux-only validation before publication?
