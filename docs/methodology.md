# Methodology

This document describes the **experimental methodology** used in the Java LTS Performance Lab.

Its goal is to ensure that all benchmarks are:

- reproducible
- comparable across Java versions
- transparent in their analysis

The methodology defines:

- hardware and operating system
- JDK distributions
- JVM configuration
- benchmark duration
- warmup strategy
- repetition strategy
- result analysis pipeline

---

# Test Environment

## Hardware

Device used for current benchmark runs:

- **CPU:** Apple M4 Pro
- **RAM:** 48 GB
- **Storage:** 512 GB SSD
- **Architecture:** ARM64 / Apple Silicon

## Operating System

- **OS:** macOS 26.3.1

This environment remains **constant across all benchmark runs** to prevent external variability from influencing results.

---

# JDK Distributions

The benchmark suite compares the following Java LTS releases:

| Version | Role in Benchmark |
|-------|----------------|
| Java 17 | Stability baseline |
| Java 21 | Virtual threads introduction |
| Java 25 | Runtime, memory, and startup optimizations |

All tests currently use **Eclipse Temurin builds** to ensure a consistent vendor distribution.

---

# JVM Configuration

Where possible, experiments use **consistent JVM configuration** across all Java versions.

Typical configuration includes:

- default garbage collector for the JDK
- consistent heap settings when applicable
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

Warmup behavior is especially important when evaluating:

- JVM startup efficiency
- JIT compilation behavior
- early throughput progression

---

## Benchmark Duration

Experiments typically include:

- **short runs** for startup measurement
- **longer load tests** for steady-state throughput

Metrics captured may include:

- first request latency
- warmup progression
- steady-state throughput

---

## Repetition Strategy

Benchmarks are executed multiple times when possible to reduce measurement variance.

Aggregation scripts combine repeated runs into:

- CSV summaries
- charts
- comparative tables

---

# Analysis Pipeline

## Raw Data Storage

Raw benchmark data is stored under:

results/raw/

Each benchmark run records:

- raw performance metrics
- logs (when applicable)
- JVM runtime data

---

## Processed Results

Aggregation scripts convert raw benchmark data into:

- processed CSV summaries
- charts
- comparative tables

Processed artifacts are stored under:

results/processed/
results/charts/

---

# Reproducibility Principles

The benchmark suite is designed so that:

- raw benchmark data remains preserved
- analysis scripts can regenerate all charts
- experiments can be repeated using the same environment

This ensures that results remain **transparent and reproducible** across future benchmark runs.