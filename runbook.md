# Runbook

This document records the current repeatable workflow for benchmark runs on:

- Java 17
- Java 21
- Java 25

# Canonical Path
Use the full runner as the primary command path. Through M5, the official publication path is `stock` only. The smaller bash runners remain useful for smoke tests and targeted reruns.

# 1. Select Java version
export JAVA_HOME=$(/usr/libexec/java_home -v 21)
export PATH="$JAVA_HOME/bin:$PATH"

# 2. Start Postgres for DB-backed scenarios
docker compose up -d postgres

export BENCHMARK_DATASOURCE_URL=jdbc:postgresql://localhost:5432/benchmarkdb
export BENCHMARK_DATASOURCE_USERNAME=benchmark
export BENCHMARK_DATASOURCE_PASSWORD=benchmark

# 3. Run the full benchmark lab on the local container lane (primary path)
python3 scripts/runners/run_full_benchmark_lab.py --versions 17 21 25 --profile stock --lane macos-container

# 4. Optional higher-confidence Linux lane
python3 scripts/runners/run_full_benchmark_lab.py --versions 17 21 25 --profile stock --lane linux-container

# 5. Optional observability run
python3 scripts/runners/run_full_benchmark_lab.py --versions 21 --profile stock --lane macos-container --with-observability-suite

# 6. Optional mixed-workload run
python3 scripts/runners/run_full_benchmark_lab.py --versions 21 --profile stock --lane macos-container --include-mixed-workload

# 7. Deferred M6 tuning study
python3 scripts/runners/run_full_benchmark_lab.py --versions 17 21 25 --profile tuned --lane macos-container

# Confidence Levels
Use these labels when interpreting results:

- local smoke: verifies commands, endpoint behavior, and artifact generation
- local comparative: useful for preliminary stock JDK comparisons on one machine with background noise minimized
- isolated/publishable: requires a stricter environment, ideally the `linux-container` lane and separate load generation for final container-aware claims

# Targeted Smoke and Rerun Commands

# 1. Run JMH only
bash scripts/runners/run_jmh_suite.sh 21

# 2. Run startup benchmark only
BENCHMARK_PROFILE=stock BENCHMARK_LANE=macos-container bash scripts/runners/run_quarkus_startup_benchmark.sh 21 3

# 3. Start Quarkus app for manual HTTP smoke tests
mvn -pl quarkus-app clean package -DskipTests -Djava.release=21
java -jar quarkus-app/target/quarkus-app/quarkus-run.jar

# 4. Run HTTP scenarios directly
BENCHMARK_PROFILE=stock BENCHMARK_LANE=macos-container bash scripts/runners/run_quarkus_http_benchmark.sh 21 products 10s 10
BENCHMARK_PROFILE=stock BENCHMARK_LANE=macos-container bash scripts/runners/run_quarkus_http_benchmark.sh 21 products-db 10s 10
BENCHMARK_PROFILE=stock BENCHMARK_LANE=macos-container bash scripts/runners/run_quarkus_http_benchmark.sh 21 transform 10s 10
BENCHMARK_PROFILE=stock BENCHMARK_LANE=macos-container bash scripts/runners/run_quarkus_http_benchmark.sh 21 aggregate-platform 10s 10
BENCHMARK_PROFILE=stock BENCHMARK_LANE=macos-container bash scripts/runners/run_quarkus_http_benchmark.sh 21 aggregate-virtual 10s 10
BENCHMARK_PROFILE=stock BENCHMARK_LANE=macos-container bash scripts/runners/run_quarkus_http_benchmark.sh 21 mixed-workload 10s 10

# 5. Run memory scenarios directly
BENCHMARK_PROFILE=stock BENCHMARK_LANE=macos-container bash scripts/runners/run_quarkus_memory_benchmark.sh 21 products
BENCHMARK_PROFILE=stock BENCHMARK_LANE=macos-container bash scripts/runners/run_quarkus_memory_benchmark.sh 21 products-db
BENCHMARK_PROFILE=stock BENCHMARK_LANE=macos-container bash scripts/runners/run_quarkus_memory_benchmark.sh 21 transform
BENCHMARK_PROFILE=stock BENCHMARK_LANE=macos-container bash scripts/runners/run_quarkus_memory_benchmark.sh 21 aggregate-platform
BENCHMARK_PROFILE=stock BENCHMARK_LANE=macos-container bash scripts/runners/run_quarkus_memory_benchmark.sh 21 aggregate-virtual

# 6. Run the dedicated concurrency ramp study
BENCHMARK_PROFILE=stock BENCHMARK_LANE=macos-container bash scripts/runners/run_concurrency_study.sh 21 20s 2,10,25,50

# 7. Run the observability suite directly
BENCHMARK_PROFILE=stock BENCHMARK_LANE=macos-container bash scripts/runners/run_gc_suite.sh 21 20s 10

# 8. Aggregate results
python3 scripts/aggregators/aggregate_quarkus_results.py
python3 scripts/aggregators/aggregate_startup_results.py
python3 scripts/aggregators/aggregate_concurrency_results.py
python3 scripts/aggregators/aggregate_memory_results.py
python3 scripts/aggregators/aggregate_gc_results.py
python3 scripts/aggregators/aggregate_cpu_results.py
python3 scripts/aggregators/aggregate_jfr_results.py

# 9. Generate charts
python3 scripts/charts/generate_startup_chart.py
python3 scripts/charts/generate_quarkus_charts.py
python3 scripts/charts/generate_concurrency_charts.py
python3 scripts/charts/generate_gc_charts.py
python3 scripts/charts/generate_cpu_charts.py
