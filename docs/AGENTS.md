# AI Agent Guidelines for java-lts-performance-lab

## Project Overview
This is a performance engineering lab comparing Java 17, 21, and 25 LTS releases using controlled benchmarks. The project evaluates JVM improvements in startup time, memory usage, throughput, GC behavior, and concurrency across realistic backend workloads.

## Architecture
- **Multi-module Maven project** with root POM defining `jmh-benchmarks` and `quarkus-app` modules
- **JMH microbenchmarks** isolate JVM behavior (allocation, collections, JSON, concurrency)
- **Quarkus application** provides REST endpoints for realistic workloads:
  - `/health` - readiness checks
  - `/products` - JSON serialization (e.g., `GET /products?count=100`)
  - `/transform` - allocation-heavy processing
  - `/aggregate` - concurrency/fan-out workloads
- **K6 load testing** in `infra/k6/` with scenarios like `products.js`, `mixed-workload.js`
- **Postgres** database setup in `infra/postgres/init.sql` for data-driven benchmarks
- **Results pipeline**: Raw data → Python aggregation scripts → processed CSVs → charts

## Critical Workflows
- **Build for specific Java version**: `mvn -pl quarkus-app clean package -DskipTests -Djava.release=21`
- **Run startup benchmark**: `./scripts/runners/run_quarkus_startup_benchmark.sh 21 3` (supports repetitions, measures external + Quarkus internal startup time)
- **Run HTTP load tests**: `./scripts/runners/run_quarkus_http_benchmark.sh 21 aggregate 30s 20` (scenario, duration, VUs; validates app reachability; supports aggregate-platform/virtual)
- **Run memory benchmarks**: `./scripts/runners/run_quarkus_memory_benchmark.sh 21 aggregate-platform` (shares logic with startup; captures RSS; optional heap info with HEAP_INFO=true)
- **Aggregate results**: Python scripts in `scripts/aggregators/` process raw logs into CSVs (e.g., `aggregate_startup_results.py` merges repeated runs)
- **Generate charts**: `scripts/charts/generate_startup_chart.py` and `generate_quarkus_charts.py` create multiple PNGs (throughput, latency, failure rate) in `results/charts/`

## Project Conventions
- **Java version targeting**: Use `-Djava.release=17/21/25` for Maven builds; overrides default in root POM
- **Result organization**: Raw outputs in `results/raw/{profile}/{lane}/javaXX/` subdirs (quarkus/, jmh/, gc/, jfr/); processed data in `results/processed/`
- **Benchmark tracks**: Five experiment categories (A: startup/warmup, B: memory/GC, C: concurrency/IO, D: JFR observability, E: containers) - see `docs/benchmark-matrix.md`
- **Quarkus config**: Native image disabled; focuses on JVM runtime performance
- **Load testing**: K6 scenarios simulate realistic traffic patterns with warmup phases
- **Metrics collection**: Scripts capture JFR recordings, GC logs, and system metrics during runs

## Key Files
- `docs/benchmark-matrix.md` - Detailed experiment design and measurement methodology
- `docs/methodology.md` - Hardware, JDK versions, JVM flags, and reproducibility guidelines
- `runbook.md` - Step-by-step benchmark execution (currently outlines planned workflow)
- `scripts/runners/` - Bash scripts for automated benchmark execution
- `infra/k6/` - Load testing scenarios with transform.js for request/response processing
- `results/processed/` - Aggregated CSV outputs (e.g., `startup-summary.csv`, `quarkus-summary.json`)

## Dependencies & Environment
- **Quarkus 3.20.2** with REST Jackson and SmallRye Health
- **JMH** for microbenchmarking with custom state objects
- **Python scripts** for data aggregation (no virtual env required)
- **Eclipse Temurin JDKs** for Java 17/21/25 consistency
- **macOS ARM64** (Apple Silicon) for current development runs; lane-aware container support exists through `macos-container` and `linux-container`

## Common Patterns
- **Endpoint injection**: Quarkus resources inject CDI services (e.g., `ProductService` for data generation)
- **DTOs**: Simple Jackson-serializable classes in `dto/` package
- **Service layer**: Business logic separated from REST resources
- **Benchmark parameterization**: JMH benchmarks use `@Param` for configurable workloads
- **Result aggregation**: Python scripts parse log files into structured CSVs with version comparisons
