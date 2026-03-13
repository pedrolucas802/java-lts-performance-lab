# Methodology

This document will describe:
- hardware and OS
- JDK distributions
- JVM flags
- benchmark duration
- warmup strategy
- repetitions
- analysis approach


Device used:

- CPU: Apple M4 Pro
- RAM: 48 GB
- Storage: 512 GB SSD
- MacOS: 26.3.1
- architecture: ARM64 / Apple Silicon


---
# Benchmark Matrix Tracks


# Track A — Startup and Warmup

**Target features**

- startup time improvements
- reduced warmup time
- Quarkus runtime efficiency
- early JVM execution performance

**Measurements**

- cold startup time (ms)
- time to first successful `/health`
- time to first successful `/products`
- warmup curve during the first requests
- throughput progression during the first 30 seconds

**Artifacts**

- `startup-summary.csv`
- warmup charts

**Current progress**

Implemented:

- Quarkus startup benchmark script
- startup aggregation pipeline
- startup comparison chart

Startup measurement infrastructure is operational, though the methodology will be refined to improve cold-start accuracy.

---

# Track B — Memory and Garbage Collection

**Target features**

- garbage collector performance
- memory usage
- reduced heap footprint
- allocation pressure
- indirect CPU cache locality effects

**Measurements**

- RSS at idle
- RSS under load
- heap used / committed
- GC count
- GC pause time
- allocation-heavy endpoint behavior

**Artifacts**

- `memory-summary.csv`
- `gc-summary.csv`
- per-version GC logs

**Current progress**

Implemented:

- memory benchmark script
- memory aggregation pipeline

Planned improvements:

- deeper GC log parsing
- GC pause distribution analysis

---

# Track C — Concurrency and IO Workloads

**Target features**

- virtual threads
- blocking IO workloads
- concurrency scaling
- thread model impact

**Measurements**

- platform threads vs virtual threads
- latency under higher concurrency
- throughput under simulated fan-out workloads
- blocking IO behavior

**Artifacts**

- concurrency comparison CSV
- virtual-thread vs platform-thread charts

**Current progress**

Implemented:

- `/aggregate` endpoint for concurrency testing
- platform-thread execution mode
- virtual-thread execution mode

Upcoming experiments will compare Java 17 platform threads against Java 21 and Java 25 virtual threads.

---

# Track D — JFR Observability

**Target features**

- JFR observability
- runtime hotspot identification
- CPU and allocation profiling

**Measurements**

- hottest methods
- allocation hotspots
- thread scheduling behavior
- GC event frequency

**Artifacts**

- `.jfr` recordings
- summarized analysis in `/docs`

**Current progress**

Infrastructure prepared. Detailed recordings and analysis will be added in later experiments.

---

# Track E — Container Awareness

**Target features**

- container-aware JVM behavior
- performance under constrained resources

**Measurements**

- startup under CPU/memory limits
- RSS inside Docker containers
- throughput under cgroup constraints

**Artifacts**

- container benchmark notes
- constrained vs unconstrained comparisons

**Current progress**

Planned for future iterations of the benchmark lab.

# Methodology

This document describes the experimental design used in the **Java LTS Performance Lab**.  
Its goal is to ensure that all benchmarks are **reproducible, comparable, and transparent**.

The methodology defines:

- hardware and operating system
- JDK distributions used
- JVM flags
- benchmark duration
- warmup strategy
- repetition strategy
- analysis approach

---

# Test Environment

## Hardware

Device used for the current benchmark runs:

- **CPU:** Apple M4 Pro
- **RAM:** 48 GB
- **Storage:** 512 GB SSD
- **Operating System:** macOS 26.3.1
- **Architecture:** ARM64 / Apple Silicon

This environment is kept **constant across all benchmark runs** to avoid introducing external variables.

---

# JDK Distributions

The following Java LTS versions are compared:

| Version | Role in Benchmark |
|-------|----------------|
| Java 17 | Stability baseline |
| Java 21 | Virtual thread introduction |
| Java 25 | Runtime, memory and startup improvements |

All versions use **Eclipse Temurin builds** to ensure a consistent vendor distribution.

---

# JVM Configuration

Where possible, the same JVM configuration is used across versions.

Typical configuration parameters include:

- default GC for the JDK version
- identical heap settings where applicable
- identical Quarkus application configuration

Future experiments may introduce controlled variations such as:

- explicit GC selection
- container memory limits
- additional JFR profiling flags

---

# Benchmark Execution Strategy

## Warmup Strategy

Benchmarks include warmup phases to allow:

- JIT compilation
- runtime optimization
- stable throughput measurements

Warmup behavior is especially important when analyzing:

- JVM startup efficiency
- JIT compilation behavior
- early throughput progression

## Benchmark Duration

Load tests measure:

- first request latency
- warmup curve
- steady‑state throughput

Typical runs include:

- short startup experiments
- longer load tests for steady‑state behavior

## Repetition Strategy

Benchmarks are executed multiple times when possible to reduce variance.

Aggregation scripts combine raw results into:

- CSV summaries
- charts
- comparative tables

---

# Benchmark Matrix Tracks

The lab is organized into **five benchmark tracks**, each targeting different JVM features.

---

# Track A — Startup and Warmup

## Target Features

- startup time improvements
- reduced warmup time
- Quarkus runtime efficiency
- early JVM execution performance

## Measurements

- cold startup time (ms)
- time to first successful `/health`
- time to first successful `/products`
- warmup curve during the first requests
- throughput progression during the first 30 seconds

## Artifacts

- `startup-summary.csv`
- warmup charts

## Current Progress

Implemented:

- Quarkus startup benchmark script
- startup aggregation pipeline
- startup comparison chart

Startup measurement infrastructure is operational, though the methodology will continue to be refined to improve cold‑start accuracy.

---

# Track B — Memory and Garbage Collection

## Target Features

- garbage collector performance
- memory usage
- reduced heap footprint
- allocation pressure
- indirect CPU cache locality effects

## Measurements

- RSS at idle
- RSS under load
- heap used / committed
- GC count
- GC pause time
- allocation-heavy endpoint behavior

## Artifacts

- `memory-summary.csv`
- `gc-summary.csv`
- per-version GC logs

## Current Progress

Implemented:

- memory benchmark script
- memory aggregation pipeline

Planned improvements:

- deeper GC log parsing
- GC pause distribution analysis

---

# Track C — Concurrency and IO Workloads

## Target Features

- virtual threads
- blocking IO workloads
- concurrency scaling
- thread model impact

## Measurements

- platform threads vs virtual threads
- latency under higher concurrency
- throughput under simulated fan‑out workloads
- blocking IO behavior

## Artifacts

- concurrency comparison CSV
- virtual-thread vs platform-thread charts

## Current Progress

Implemented:

- `/aggregate` endpoint for concurrency testing
- platform-thread execution mode
- virtual-thread execution mode

Upcoming experiments will compare Java 17 platform threads against Java 21 and Java 25 virtual threads.

---

# Track D — JFR Observability

## Target Features

- JFR observability
- runtime hotspot identification
- CPU and allocation profiling

## Measurements

- hottest methods
- allocation hotspots
- thread scheduling behavior
- GC event frequency

## Artifacts

- `.jfr` recordings
- summarized analysis in `/docs`

## Current Progress

Infrastructure is prepared for capturing JFR recordings.  
Detailed recordings and analysis will be added in later experiments.

---

# Track E — Container Awareness

## Target Features

- container-aware JVM behavior
- performance under constrained resources

## Measurements

- startup under CPU/memory limits
- RSS inside Docker containers
- throughput under cgroup constraints

## Artifacts

- container benchmark notes
- constrained vs unconstrained comparisons

## Current Progress

Container-based benchmarking is planned for future iterations of the lab.

---

# Analysis Approach

Raw benchmark data is stored under:

```
results/raw/
```

Aggregation scripts convert raw results into:

- processed CSV summaries
- charts
- comparative tables

Processed artifacts are stored under:

```
results/processed/
results/charts/
```

This separation ensures that:

- raw benchmark data remains reproducible
- analysis steps remain transparent
- charts can be regenerated from source measurements