# java-lts-performance-lab

Benchmarking **Java 17 vs Java 21 vs Java 25** using:
- **JMH** microbenchmarks
- **Quarkus** application benchmarks
- **k6** load testing
- structured result aggregation scripts
- startup and chart generation utilities

## Project goal

This repository investigates how modern Java LTS versions behave in realistic backend scenarios, with emphasis on:
- JVM performance
- startup and warmup behavior
- memory usage
- garbage collector behavior
- virtual threads and concurrency
- IO-heavy workloads
- Quarkus runtime performance
- observability foundations with JFR/GC logs

## Current status

Implemented so far:
- multi-module Maven structure
- `jmh-benchmarks` module with initial Jackson JSON serialization benchmark
- `quarkus-app` module with benchmark endpoints:
    - `/health`
    - `/products`
    - `/transform`
    - `/aggregate`
- benchmark automation scripts for:
    - Quarkus startup timing
    - Quarkus HTTP benchmarking with k6
    - Quarkus memory benchmarking
- aggregation scripts for:
    - Quarkus HTTP benchmark summaries
    - startup summaries
    - memory summaries
- startup comparison chart generation

## Current benchmark coverage

### JMH
- JSON serialization benchmark

### Quarkus HTTP
- `/products` for JSON serialization / response payload behavior
- `/transform` for allocation-heavy request/response handling
- `/aggregate` for concurrency experiments with platform threads vs virtual threads

### Aggregation and reporting
- `results/processed/quarkus-summary.csv`
- `results/processed/startup-summary.csv`
- `results/processed/memory-summary.csv`
- `results/charts/startup-comparison.png`

## Initial findings

### Quarkus steady-state HTTP results
On the current Apple Silicon test machine, initial Quarkus HTTP benchmarks showed **very similar steady-state performance** across Java 17, 21, and 25 for the current lightweight REST scenarios.

This is a useful result: the project is already showing measured behavior rather than assumed version advantages.

### Startup measurements
Startup aggregation is working, but the current startup numbers are likely **too optimistic to be treated as true cold-start data**. The measurement pipeline exists and is producing data, but the startup methodology still needs refinement before final conclusions are documented.

## Machine used so far

Primary local benchmark machine:
- **MacBook Pro 16-inch (2025)**
- **Apple M4 Pro**
- **48 GB RAM**
- **512 GB SSD**
- **macOS arm64 / Apple Silicon**

## Repository structure

```text
java-lts-performance-lab/
├── docs/
├── infra/
├── jmh-benchmarks/
├── quarkus-app/
├── results/
└── scripts/
```

## How to run the lab

### JMH baseline
```bash
make jmh JAVA_VERSION=21
```

### Quarkus startup benchmark
```bash
./scripts/run_quarkus_startup_benchmark.sh 21
```

### Quarkus HTTP benchmark
Start the packaged app first, then run:

```bash
./scripts/run_quarkus_http_benchmark.sh 21 products
./scripts/run_quarkus_http_benchmark.sh 21 transform
```

### Aggregate Quarkus HTTP results
```bash
python3 scripts/aggregate_quarkus_results.py
```

### Aggregate startup results
```bash
python3 scripts/aggregate_startup_results.py
python3 scripts/generate_startup_chart.py
```

### Memory benchmark
```bash
./scripts/run_quarkus_memory_benchmark.sh 21 products
python3 scripts/aggregate_memory_results.py
```

## Next planned steps

High-value next steps:
1. tighten startup methodology to capture more trustworthy cold-start data
2. benchmark `/aggregate` with platform threads vs virtual threads
3. expand memory and GC analysis
4. record JFR and GC logs for selected runs
5. evaluate constrained/container-style runs

## Notes on interpretation

This repository is designed as a performance lab, not a marketing demo. Some comparisons may show negligible differences between Java versions, and those results are still valuable when they are measured carefully and reported honestly.

# Runbook

This document records the current repeatable workflow for the benchmark lab.

## 1. Select a Java version

Examples:

```bash
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
export PATH="$JAVA_HOME/bin:$PATH"
```

```bash
export JAVA_HOME=$(/usr/libexec/java_home -v 21)
export PATH="$JAVA_HOME/bin:$PATH"
```

```bash
export JAVA_HOME=$(/usr/libexec/java_home -v 25)
export PATH="$JAVA_HOME/bin:$PATH"
```

Verify:

```bash
java -version
mvn -version
```

## 2. Run JMH baseline

```bash
make jmh JAVA_VERSION=21
```

This produces JSON baseline output under `results/raw/{profile}/{lane}/javaXX/jmh/`.

## 3. Run Quarkus startup benchmark

```bash
BENCHMARK_PROFILE=stock BENCHMARK_LANE=macos-container bash scripts/runners/run_quarkus_startup_benchmark.sh 21 3
```

This writes startup logs and metrics under `results/raw/{profile}/{lane}/javaXX/quarkus/`.

## 4. Build and run Quarkus app for HTTP benchmarking

```bash
mvn -pl quarkus-app clean package -DskipTests -Djava.release=21
java -jar quarkus-app/target/quarkus-app/quarkus-run.jar
```

## 5. Run Quarkus HTTP benchmark scenarios

```bash
BENCHMARK_PROFILE=stock BENCHMARK_LANE=macos-container bash scripts/runners/run_quarkus_http_benchmark.sh 21 products 10s 10
BENCHMARK_PROFILE=stock BENCHMARK_LANE=macos-container bash scripts/runners/run_quarkus_http_benchmark.sh 21 transform 10s 10
```

Optional aggregate concurrency scenario:

```bash
k6 run -e BASE_URL=http://localhost:8080 -e AGG_MODE=platform infra/k6/aggregate.js
k6 run -e BASE_URL=http://localhost:8080 -e AGG_MODE=virtual infra/k6/aggregate.js
```

## 6. Aggregate HTTP benchmark summaries

```bash
python3 scripts/aggregate_quarkus_results.py
cat results/processed/quarkus-summary.csv
```

## 7. Aggregate startup summaries and chart

```bash
python3 scripts/aggregate_startup_results.py
cat results/processed/startup-summary.csv
python3 scripts/generate_startup_chart.py
```

## 8. Run memory benchmark

Examples:

```bash
./scripts/run_quarkus_memory_benchmark.sh 21 products
./scripts/run_quarkus_memory_benchmark.sh 21 transform
./scripts/run_quarkus_memory_benchmark.sh 21 aggregate-platform
./scripts/run_quarkus_memory_benchmark.sh 21 aggregate-virtual
```

Aggregate:

```bash
python3 scripts/aggregate_memory_results.py
cat results/processed/memory-summary.csv
```

## 9. Current caution points

- startup numbers are currently likely too optimistic for true cold-start conclusions
- virtual-thread comparisons should be framed as:
    - Java 17 platform baseline
    - Java 21 platform vs virtual
    - Java 25 platform vs virtual
- all comparisons should keep hardware, load shape, and payload size fixed

# Methodology

## Objective

The goal of this project is to compare Java 17, 21, and 25 in a reproducible backend-oriented benchmark lab using Quarkus, JMH, and scripted analysis.

## Current test environment

Primary test machine:
- MacBook Pro 16-inch (2025)
- Apple M4 Pro
- 48 GB RAM
- 512 GB SSD
- macOS arm64 / Apple Silicon

## Core principles

To keep comparisons useful:
- the same machine is used for all local comparisons
- the application code stays constant across Java versions
- the benchmark scenario, payload shape, and concurrency level remain fixed for a given comparison
- only the Java version or explicitly chosen runtime setting should change between runs

## Current benchmark categories

### 1. JMH microbenchmarks
Used for isolated JVM behavior without framework overhead.

Implemented so far:
- Jackson JSON serialization benchmark

### 2. Quarkus startup benchmark
Used to capture application startup timing.

Status:
- measurement pipeline implemented
- aggregation implemented
- methodology needs refinement before strong conclusions are made

### 3. Quarkus HTTP benchmarks
Used to compare steady-state behavior for simple REST workloads.

Implemented scenarios:
- `/products`
- `/transform`

### 4. Concurrency benchmark
Used to compare platform thread vs virtual thread execution.

Implemented endpoint:
- `/aggregate`

Status:
- endpoint implemented
- dedicated comparison runs still in progress

### 5. Memory benchmark
Used to compare idle and post-load RSS across scenarios.

Implemented scenarios:
- `products`
- `transform`
- `aggregate-platform`
- `aggregate-virtual`

## Current interpretation limits

### Startup
The current startup numbers are likely too small to represent robust cold-start timing. The benchmark path works, but the metric should not yet be treated as final.

### CPU cache locality
This project may only support indirect discussion of cache-locality-related effects through memory footprint and object behavior. It does not directly measure hardware cache performance.

### Container awareness
This benchmark suite is currently running on a local machine rather than under strict container CPU/memory limits. Container-specific conclusions are therefore still pending.

## Current result posture

Early results show that Java 17, 21, and 25 can be very close in steady-state Quarkus HTTP throughput for lightweight scenarios. This is an acceptable and useful result. The project is intended to measure real behavior, including cases where differences are small.

# Analysis Notes

## Current implemented artifacts

### Code
- parent multi-module Maven project
- `jmh-benchmarks` module
- `quarkus-app` module
- Quarkus endpoints:
    - `/health`
    - `/products`
    - `/transform`
    - `/aggregate`

### Scripts
- `run_quarkus_startup_benchmark.sh`
- `run_quarkus_http_benchmark.sh`
- `run_quarkus_memory_benchmark.sh`
- `aggregate_quarkus_results.py`
- `aggregate_startup_results.py`
- `aggregate_memory_results.py`
- `generate_startup_chart.py`

## Current findings

### 1. Quarkus HTTP
Initial Java 17 vs 21 vs 25 steady-state HTTP results are tightly clustered for the current scenarios.

That suggests:
- the current REST scenarios are relatively lightweight
- steady-state throughput alone may not be where Java 25 shows its strongest practical differences
- upgrade benefits may become more visible in startup, memory, concurrency, GC, and observability work

### 2. Startup
The startup pipeline works end-to-end, but the current values are likely too optimistic. The next step should be improving the measurement method before using startup results as headline conclusions.

### 3. Virtual threads
The `/aggregate` endpoint is in place to support platform vs virtual thread comparisons. Java 17 should be treated as a platform-thread baseline only.

### 4. Memory
Memory benchmark infrastructure is in place, but a full 17/21/25 summary still needs to be generated and interpreted.

## Planned comparisons by topic

### JVM performance
- JMH JSON benchmark
- Quarkus HTTP benchmark
- startup and warmup measurements

### Garbage collector
- allocation-heavy request scenarios
- later GC log collection and comparison

### Virtual threads and concurrency
- `/aggregate?mode=platform`
- `/aggregate?mode=virtual`

### Memory usage
- idle RSS
- post-load RSS
- RSS delta

### Lower heap usage / cache-related effects
- inferred indirectly through allocation-heavy and memory footprint experiments

### Startup / warmup
- current pipeline exists
- methodology refinement required

### JFR observability
- JVM flags prepared for future runs
- detailed recordings not yet fully incorporated into processed summaries

### Container awareness / performance
- planned for later constrained runs

### IO workloads
- represented mainly by `/aggregate` and future higher-concurrency scenarios
