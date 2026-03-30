# Benchmark Matrix

This document describes the **benchmark architecture used in the Java LTS Performance Lab**.

The lab evaluates **Java 17, Java 21, and Java 25** across multiple runtime characteristics using controlled experiments.

The benchmark suite combines:

- **JMH microbenchmarks** for isolated JVM behavior
- **Quarkus application benchmarks** for realistic workloads
- **k6 load testing** for HTTP throughput and latency analysis
- **JFR and GC logs** for runtime observability
- automated aggregation scripts for result processing

---

# Implemented Benchmark Components

## JVM Microbenchmarks (JMH)

JMH benchmarks isolate JVM behavior without framework overhead.

Current benchmarks include:

- JSON serialization
- allocation, collections, and string workloads are still planned

These benchmarks are used to evaluate **core JVM runtime performance** across Java versions.

---

## Quarkus Application Benchmarks

The Quarkus benchmark application provides **realistic backend workloads**.

Endpoints used in experiments:

| Endpoint | Purpose |
|------|------|
| `/health` | readiness checks and startup validation |
| `/products` | JSON serialization workload |
| `/products-db` | pooled JDBC read workload |
| `/transform` | allocation-heavy request/response workload |
| `/aggregate` | concurrency and fan-out workload |

These endpoints simulate common backend patterns:

- serialization workloads
- allocation-heavy processing
- concurrent aggregation workloads

---

## Load Testing

HTTP load testing is performed using **k6**.

Current scenarios include:

- `products` workload
- `products-db` workload
- `transform` workload
- `aggregate-platform` and `aggregate-virtual` concurrency workloads
- `mixed-workload` as an optional weighted traffic blend

These scenarios allow measurement of:

- throughput
- tail latency
- warmup behavior
- concurrency scaling

---

# Benchmark Tracks

The benchmark suite is organized into **five experiment tracks**, each targeting specific JVM improvements.

---

# Track A — Startup and Warmup

### Target Features

- startup time improvements
- reduced warmup time
- Quarkus runtime efficiency
- early JVM execution performance

### Measurements

- cold startup time (ms)
- time to first successful `/health`
- time to first successful `/products`
- warmup curve during the first requests
- throughput progression during the first 30 seconds

### Artifacts

- `startup-summary.csv`
- warmup charts

### Current Progress

Implemented:

- Quarkus startup benchmark script
- startup aggregation pipeline
- startup comparison chart

Startup measurement infrastructure is operational, though the methodology will continue to be refined to improve cold-start accuracy.

---

# Track B — Memory and Garbage Collection

### Target Features

- garbage collector performance
- memory usage
- reduced heap footprint
- allocation pressure
- indirect CPU cache locality effects

### Measurements

- RSS at idle
- RSS under load
- heap used / committed
- GC count
- GC pause time
- allocation-heavy endpoint behavior

### Artifacts

- `memory-summary.csv`
- `gc-summary.csv`
- per-version GC logs

### Current Progress

Implemented:

- memory benchmark script
- memory aggregation pipeline

Planned improvements:

- deeper GC log parsing
- GC pause distribution analysis

---

# Track C — Concurrency and IO Workloads

### Target Features

- virtual threads
- blocking IO workloads
- concurrency scaling
- thread model impact

### Measurements

- platform threads vs virtual threads
- latency under higher concurrency
- throughput under simulated fan-out workloads
- blocking IO behavior

### Artifacts

- concurrency comparison CSV
- virtual-thread vs platform-thread charts

### Current Progress

Implemented:

- `/aggregate` endpoint for concurrency testing
- platform-thread execution mode over JDBC fan-out
- virtual-thread execution mode over the same JDBC fan-out workload
- dedicated `concurrency-summary.csv` aggregation
- platform-vs-virtual concurrency charts

Upcoming experiments will compare:

- Java 17 platform threads (baseline)
- Java 21 virtual threads
- Java 25 virtual threads

---

# Track D — JFR Observability

### Target Features

- JFR observability
- runtime hotspot identification
- CPU and allocation profiling

### Measurements

- hottest methods
- allocation hotspots
- thread scheduling behavior
- GC event frequency

### Artifacts

- `.jfr` recordings
- summarized analysis in `/docs`

### Current Progress

Infrastructure prepared for capturing JFR recordings.

Detailed runtime analysis will be incorporated in later experiments.

---

# Track E — Container Awareness

### Target Features

- container-aware JVM behavior
- performance under constrained resources

### Measurements

- startup under CPU and memory limits
- RSS inside Docker containers
- throughput under cgroup constraints

### Artifacts

- container benchmark notes
- constrained vs unconstrained comparisons

### Current Progress

Container-based benchmarking is planned for future iterations of the lab.

---

# Methodology

The benchmark methodology is designed to ensure **reproducible and comparable experiments**.

It defines:

- hardware and operating system
- JDK distributions
- JVM flags
- benchmark duration
- warmup strategy
- repetition strategy
- analysis approach

Detailed methodology documentation can be found in:

`docs/methodology.md`

---

# Test Environment

## Hardware

Device used for current benchmark runs:

- **CPU:** Apple M4 Pro
- **RAM:** 48 GB
- **Storage:** 512 GB SSD
- **Operating System:** macOS 26.3.1
- **Architecture:** ARM64 / Apple Silicon

The environment is kept **constant across all experiments** to avoid introducing external variables.

---

# JDK Distributions

The benchmark compares the following Java LTS versions:

| Version | Role in Benchmark |
|-------|----------------|
| Java 17 | Stability baseline |
| Java 21 | Virtual threads introduction |
| Java 25 | Memory, startup and runtime optimizations |

All tests currently use **Eclipse Temurin builds** for consistency.

---

# Benchmark Execution Strategy

## Warmup

Benchmarks include warmup phases to allow:

- JIT compilation
- runtime optimization
- stable throughput measurement

Warmup analysis is especially important when evaluating:

- JVM startup efficiency
- JIT behavior
- early throughput progression

---

## Duration

Experiments measure:

- first request latency
- warmup progression
- steady-state throughput

Runs typically include:

- short startup experiments
- longer steady-state load tests

---

## Repetitions

Benchmarks are executed multiple times when possible.

Aggregation scripts combine raw measurements into:

- CSV summaries
- charts
- comparative tables

---

# Results Processing

Raw benchmark data is stored in:

`results/raw/`

Processed summaries and charts are generated under:

`results/processed/`  
`results/charts/`

This separation ensures:

- raw measurements remain reproducible
- analysis steps remain transparent
- charts can be regenerated from source data
