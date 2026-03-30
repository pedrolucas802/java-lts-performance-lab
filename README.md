# java-lts-performance-lab

A performance engineering lab comparing **Java 17, Java 21, and Java 25** using realistic backend workloads and controlled benchmarks.

The goal is to understand how modern Java LTS releases affect **startup time, memory usage, throughput, GC behavior, and concurrency performance** in real-world applications.

---

# Objectives

This repository investigates how newer Java releases impact backend systems by measuring:

- application **startup time**
- **memory footprint** and allocation behavior
- **HTTP throughput** and **tail latency**
- **garbage collection** performance
- **concurrency behavior** (platform threads vs virtual threads)
- **Quarkus runtime efficiency**

The project focuses on **measured results rather than assumptions about JVM improvements.**

---

# Java LTS Focus

| Version | Key Focus |
|------|------|
| **Java 17** | Stability baseline |
| **Java 21** | Virtual threads and new concurrency model |
| **Java 25** | Memory improvements, startup optimization, runtime tuning |

Java 17 acts as the **baseline**, while Java 21 and Java 25 introduce runtime capabilities that may affect performance in different ways.

---

# Java Runtime Features Evaluated

The lab evaluates improvements related to:

- JVM runtime performance
- Garbage collector behavior
- Virtual threads and concurrency
- Memory usage and allocation pressure
- CPU cache locality (indirect effects)
- Reduced heap footprint
- Faster startup and warmup
- Ahead-of-Time profiling optimizations
- JFR observability improvements
- Container-aware runtime behavior
- IO-heavy workloads

---

# Benchmark Matrix

The experiments are organized into **five benchmark tracks**, each targeting specific JVM improvements.

For the full experimental design and measurement methodology, see:

**[`docs/benchmark-matrix.md`](docs/benchmark-matrix.md)**
**[`docs/benchmark-stack.md`](docs/benchmark-stack.md)**
**[`docs/methodology.md`](docs/methodology.md)**

---

# Repository Structure

```
java-lts-performance-lab
│
├── jmh-benchmarks
│   └── raw JVM microbenchmarks
│
├── quarkus-app
│   └── realistic backend benchmark application
│
├── scripts
│   └── benchmark automation scripts
│
├── infra
│   └── k6 load testing scenarios
│
├── results
│   ├── raw
│   ├── processed
│   └── charts
│
└── docs
    ├── methodology
    ├── analysis notes
    └── benchmark documentation
```

---

# Primary Workflow

The primary benchmark entrypoint is:

`python3 scripts/runners/run_full_benchmark_lab.py`

It now supports:

- Java-specific `stock` and `tuned` profile configs under `config/benchmark-profiles/`
- lane configs under `config/benchmark-lanes/` with `macos-container` and `linux-container`
- official HTTP scenarios for `products`, `products-db`, `transform`, `aggregate-platform`, and `aggregate-virtual`
- optional `mixed-workload` execution when explicitly enabled
- profile-and-lane-aware raw result storage under `results/raw/{profile}/{lane}/`
- dedicated concurrency summary and aggregate thread-mode charts
- optional GC/JFR/CPU observability runs with processed `gc-summary.csv`, `cpu-summary.csv`, and `jfr-summary.csv`

The smaller bash runners remain useful for targeted smoke tests and single-scenario reruns.

Through M5, the official publication path is `stock` only. The existing `tuned` profile support remains in the repo for a deferred M6 study.

---

# Initial Observations

Early steady-state Quarkus HTTP benchmarks on **Apple Silicon (M4 Pro)** show **very similar throughput across Java 17, Java 21, and Java 25** for lightweight REST workloads.

Java 25 did **not significantly outperform earlier LTS releases** in raw requests/sec under moderate HTTP load.

This suggests that the practical gains of newer Java versions may be more visible in:

- startup behavior
- warmup performance
- memory efficiency
- garbage collection improvements
- virtual thread concurrency
- runtime observability

rather than simple steady-state HTTP throughput alone.

---

# Project Status

Current progress:

- repository structure implemented
- JMH microbenchmarks implemented
- Quarkus benchmark application implemented
- DB-backed `products-db` scenario implemented as the primary real-I/O baseline
- DB-backed aggregate fan-out implemented as the primary concurrency workload
- profile-aware benchmark configs added for `stock` and `tuned` runs
- lane-aware benchmark configs added for `macos-container` and `linux-container`
- full benchmark runner promoted as the canonical orchestrator
- startup benchmark pipeline working
- HTTP load tests working
- GC/JFR/CPU observability suite working
- result aggregation scripts implemented
- startup, HTTP, concurrency, GC, and CPU chart generation implemented with lane-specific outputs

Next work focuses on:

- stock result publication across container lanes
- JMH scope expansion
- deferred M6 tuning study
