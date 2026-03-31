# AI Agent Guidelines for java-lts-performance-lab

## Project Overview
Performance benchmarking lab comparing Java 17, 21, 25 LTS releases using Quarkus applications, JMH microbenchmarks, and k6 load testing. Evaluates startup time, memory usage, throughput, GC behavior, and concurrency across realistic backend workloads.

## Architecture
- **quarkus-app**: REST API with endpoints like `/products` (JSON serialization), `/transform` (allocation-heavy), `/aggregate` (concurrency/fan-out)
- **jmh-benchmarks**: Isolated JVM microbenchmarks for allocation, collections, JSON, concurrency
- **infra/k6/**: Load testing scenarios (products.js, mixed-workload.js) with warmup phases
- **scripts/runners/**: Bash automation for benchmarks (startup, HTTP, memory, JMH, GC)
- **scripts/aggregators/**: Python scripts processing raw logs into CSVs (e.g., aggregate_startup_results.py merges repetitions)
- **scripts/charts/**: Python generating PNG charts from processed data
- **Data flow**: Raw results in `results/raw/java{17,21,25}/` → processed CSVs in `results/processed/` → charts in `results/charts/`

## Critical Workflows
- Build Quarkus app: `mvn -pl quarkus-app clean package -DskipTests -Djava.release=21`
- Run startup benchmark: `./scripts/runners/run_quarkus_startup_benchmark.sh 21 3` (repetitions, measures external + internal startup)
- Run HTTP load tests: `./scripts/runners/run_quarkus_http_benchmark.sh 21 aggregate-platform 30s 20` (scenario, duration, VUs; validates reachability)
- Run memory benchmarks: `./scripts/runners/run_quarkus_memory_benchmark.sh 21 aggregate-platform` (captures RSS; HEAP_INFO=true for heap data)
- Aggregate results: Python scripts in `scripts/aggregators/` (e.g., aggregate_quarkus_results.py supports aggregate-platform/virtual)
- Generate charts: `scripts/charts/generate_startup_chart.py`, `generate_quarkus_charts.py` (multiple PNGs per output file)

## Project Conventions
- Java versions: 17 (baseline), 21 (virtual threads), 25 (optimizations); use `-Djava.release=XX` for Maven
- Scenarios: products, transform, aggregate-platform (all versions); aggregate-virtual (21/25 only)
- Output paths: Raw logs in `results/raw/javaXX/quarkus/`, processed CSVs in `results/processed/`, charts in `results/charts/`
- Benchmark tracks: A (startup/warmup), B (memory/GC), C (concurrency/IO), D (JFR), E (containers) - see `docs/benchmark-matrix.md`
- Quarkus config: JVM-only (no native), consistent CDI injection (e.g., ProductService for data)

## Key Files
- `docs/benchmark-matrix.md`: Experiment design and methodology
- `docs/methodology.md`: Hardware, JDKs, JVM flags, reproducibility
- `runbook.md`: Step-by-step execution guide
- `scripts/common.sh`: Shared Bash functions (info/success/error, validate_java_version, require_command)
- `infra/k6/transform.js`: Request/response processing example
- `results/processed/quarkus-summary.csv`: Aggregated HTTP metrics

## Common Patterns
- **Bash scripts**: Start with `#!/usr/bin/env bash; set -euo pipefail`; include usage(), input validation, dependency checks (require_command), root detection (`SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`), clear output paths, success/failure messages
- **Python scripts**: main() entrypoint, constants at top (RESULTS_ROOT, OUTPUT_DIR), robust missing-file handling (check if dirs/files exist), consistent output names (e.g., startup-summary.csv), predictable CSV columns (java_version, scenario, metric), no duplicated parsing logic
- **Naming**: Runners like run_quarkus_suite.sh, aggregators like aggregate_quarkus_results.py, charts like generate_quarkus_charts.py
- **Integration**: Maven for builds, k6 for HTTP tests, Python for data processing; scripts share common.sh for utilities
