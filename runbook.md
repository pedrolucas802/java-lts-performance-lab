# Validation Runbook

This runbook is the step-by-step path to validate the benchmark lab across Java 17, 21, and 25.

It covers:

1. environment setup
2. milestone-by-milestone validation
3. the canonical full-lab commands
4. the output files you should inspect after each phase

The canonical automation entrypoint is:

```bash
python3 scripts/runners/run_full_benchmark_lab.py --preset full-lab --versions 17 21 25 --lane macos-container
```

## 1. Prerequisites

Required tools:

- Java 17, 21, and 25 installed locally
- `mvn`
- `python3`
- `k6`
- `docker`
- `jfr`

Recommended local verification:

```bash
java -version
mvn -version
python3 --version
k6 version
docker --version
jfr version
```

## 2. One-Time Environment Setup

### 2.1 Export all Java homes

```bash
export JAVA17_HOME=$(/usr/libexec/java_home -v 17)
export JAVA21_HOME=$(/usr/libexec/java_home -v 21)
export JAVA25_HOME=$(/usr/libexec/java_home -v 25)

export JAVA_HOME="$JAVA21_HOME"
export PATH="$JAVA_HOME/bin:$PATH"
```

### 2.2 Start Postgres and export datasource settings

```bash
docker compose up -d postgres

export BENCHMARK_DATASOURCE_URL=jdbc:postgresql://localhost:5432/benchmarkdb
export BENCHMARK_DATASOURCE_USERNAME=benchmark
export BENCHMARK_DATASOURCE_PASSWORD=benchmark
```

### 2.3 Validate the seeded dataset

The current full-lab path assumes a larger deterministic dataset.

```bash
docker compose exec postgres \
  psql -U benchmark -d benchmarkdb \
  -c "select count(*) from benchmark_products;"
```

Expected result:

- `50000` rows

## 3. Baseline Smoke Before Any Long Run

Run a fast end-to-end validation before starting heavier runs:

```bash
python3 scripts/runners/run_full_benchmark_lab.py \
  --preset smoke \
  --versions 17 21 25 \
  --lane macos-container
```

Smoke preset characteristics:

- startup repetitions: `2`
- HTTP duration: `15s`
- memory duration: `15s`
- concurrency duration: `15s`
- observability suite: disabled
- mixed workload: disabled

Inspect:

- `results/processed/startup-summary.csv`
- `results/processed/quarkus-summary.csv`
- `results/processed/memory-summary.csv`
- `results/processed/concurrency-summary.csv`
- `results/logs/full-benchmark-run-*.log`

## 4. Milestone 1 Validation: Harness and Result Integrity

Goal:

- validate the full benchmark harness
- validate startup, HTTP, memory, and processed outputs across all three Java versions
- validate JMH and chart generation

### 4.1 Run JMH for all three Java versions

```bash
for v in 17 21 25; do
  bash scripts/runners/run_jmh_suite.sh "$v"
done
```

### 4.2 Run startup, HTTP, memory, and concurrency through the canonical runner

```bash
python3 scripts/runners/run_full_benchmark_lab.py \
  --preset smoke \
  --versions 17 21 25 \
  --lane macos-container
```

### 4.3 Validate outputs

Check:

- `results/processed/startup-summary.csv`
- `results/processed/quarkus-summary.csv`
- `results/processed/memory-summary.csv`
- `results/processed/concurrency-summary.csv`
- `results/charts/`

Expected validation points:

- all summaries contain rows for Java 17, 21, and 25
- `aggregate-virtual` appears only for Java 21 and 25
- no mislabeled aggregate scenarios
- charts generate without dropping lane or scenario data

## 5. Milestone 2 Validation: Real I/O Groundwork

Goal:

- validate the DB-backed read path and the mixed-workload groundwork

### 5.1 Manual API smoke on Java 21

```bash
mvn -pl quarkus-app clean package -DskipTests -Djava.release=21

BENCHMARK_DATASOURCE_URL=jdbc:postgresql://localhost:5432/benchmarkdb \
BENCHMARK_DATASOURCE_USERNAME=benchmark \
BENCHMARK_DATASOURCE_PASSWORD=benchmark \
java -jar quarkus-app/target/quarkus-app/quarkus-run.jar
```

In a second terminal:

```bash
curl -i 'http://localhost:8080/health'
curl -i 'http://localhost:8080/products?count=500'
curl -i 'http://localhost:8080/products-db?count=500'
```

Expected result:

- `/products-db` returns `200 OK`

### 5.2 Targeted DB-backed benchmark

```bash
BENCHMARK_LANE=macos-container \
bash scripts/runners/run_quarkus_suite.sh 21 30s 20 "products-db"
```

### 5.3 Optional mixed-workload validation

```bash
BENCHMARK_LANE=macos-container \
bash scripts/runners/run_quarkus_suite.sh 21 30s 20 "mixed-workload"
```

Validate:

- `results/raw/stock/macos-container/java21/quarkus/products-db-summary.txt`
- `results/raw/stock/macos-container/java21/quarkus/products-db-k6.json`
- `results/raw/stock/macos-container/java21/quarkus/mixed-workload-summary.txt`

## 6. Milestone 3 Validation: Loom and Concurrency Study

Goal:

- validate platform-thread and virtual-thread comparisons under the DB-backed aggregate workload

### 6.1 Run concurrency ramps for every Java version

```bash
for v in 17 21 25; do
  BENCHMARK_LANE=macos-container \
  bash scripts/runners/run_concurrency_study.sh "$v" 30s 5,25,50,100
done
```

### 6.2 Regenerate concurrency outputs

```bash
python3 scripts/aggregators/aggregate_concurrency_results.py
python3 scripts/charts/generate_concurrency_charts.py
```

Validate:

- `results/processed/concurrency-summary.csv`
- lane-specific concurrency charts under `results/charts/`

Expected validation points:

- Java 17 includes only `aggregate-platform`
- Java 21 and 25 include both `aggregate-platform` and `aggregate-virtual`
- rows include VU ramp metadata and lane metadata

## 7. Milestone 4 Validation: GC, CPU, and JFR Observability

Goal:

- validate structured GC logs, CPU sampling, and JFR capture for representative scenarios

### 7.1 Run the observability suite for every Java version

```bash
for v in 17 21 25; do
  BENCHMARK_LANE=macos-container \
  bash scripts/runners/run_gc_suite.sh "$v" 30s 20
done
```

### 7.2 Aggregate and chart observability outputs

```bash
python3 scripts/aggregators/aggregate_gc_results.py
python3 scripts/aggregators/aggregate_cpu_results.py
python3 scripts/aggregators/aggregate_jfr_results.py
python3 scripts/charts/generate_gc_charts.py
python3 scripts/charts/generate_cpu_charts.py
```

Validate:

- `results/processed/gc-summary.csv`
- `results/processed/cpu-summary.csv`
- `results/processed/jfr-summary.csv`
- lane-specific GC and CPU charts under `results/charts/`
- raw `.jfr` files under `results/raw/stock/{lane}/javaXX/gc/`

## 8. Milestone 5 Validation: Containerized and Isolated Java-Version Comparison

Goal:

- validate the stock-only, lane-aware benchmark flow
- keep raw outputs separated by lane
- run the whole implemented lab for all three Java versions

### 8.1 Local comparative lane

This is the main full-lab command for macOS development and preliminary comparison:

```bash
python3 scripts/runners/run_full_benchmark_lab.py \
  --preset full-lab \
  --versions 17 21 25 \
  --lane macos-container
```

The `full-lab` preset currently uses:

- startup repetitions: `5`
- HTTP: `60s` at `40` VUs
- memory: `45s` at `30` VUs
- concurrency: `30s` at `5,25,50,100`
- observability suite: enabled
- product count: `500`
- transform items: `24`
- transform metadata keys: `12`

### 8.2 Higher-confidence Linux lane

Use this lane for cleaner container-aware comparison and final publication runs:

```bash
python3 scripts/runners/run_full_benchmark_lab.py \
  --preset full-lab \
  --versions 17 21 25 \
  --lane linux-container
```

### 8.3 Optional full mixed-workload pass

Mixed workload remains non-primary but is useful once the single-scenario baselines are green.

```bash
python3 scripts/runners/run_full_benchmark_lab.py \
  --preset full-lab \
  --versions 17 21 25 \
  --lane macos-container \
  --include-mixed-workload
```

Validate:

- raw results written to `results/raw/stock/macos-container/` and `results/raw/stock/linux-container/`
- processed summaries include lane/container metadata
- charts distinguish lanes cleanly

## 9. Milestone 6 Note: Future Work Only

There is no implemented Milestone 6 command path right now.

Future work may revisit:

- light JVM tuning studies
- tuning-sensitive Java-version ranking changes
- tuning-sensitive Loom comparisons

This is intentionally outside the current official benchmark path.

## 10. Canonical Commands

### 10.1 Full implemented lab on macOS lane

```bash
python3 scripts/runners/run_full_benchmark_lab.py \
  --preset full-lab \
  --versions 17 21 25 \
  --lane macos-container
```

### 10.2 Full implemented lab on Linux lane

```bash
python3 scripts/runners/run_full_benchmark_lab.py \
  --preset full-lab \
  --versions 17 21 25 \
  --lane linux-container
```

### 10.3 Fast validation pass

```bash
python3 scripts/runners/run_full_benchmark_lab.py \
  --preset smoke \
  --versions 17 21 25 \
  --lane macos-container
```

## 11. Output Checklist

After a successful full-lab run, verify:

- `results/processed/startup-summary.csv`
- `results/processed/quarkus-summary.csv`
- `results/processed/memory-summary.csv`
- `results/processed/concurrency-summary.csv`
- `results/processed/gc-summary.csv`
- `results/processed/cpu-summary.csv`
- `results/processed/jfr-summary.csv`
- `results/charts/`
- `results/logs/full-benchmark-run-*.log`

## 12. Troubleshooting

### Postgres is up but `/products-db` returns `503`

The app process does not see:

- `BENCHMARK_DATASOURCE_URL`
- `BENCHMARK_DATASOURCE_USERNAME`
- `BENCHMARK_DATASOURCE_PASSWORD`

Restart the app or rerun the runner from the same shell where those variables are exported.

### Port already in use

Free these ports before rerunning:

- `8080` for startup and HTTP suites
- `8081` for memory suite
- `8082` for observability suite

### `aggregate-virtual` does not exist for Java 17

That is expected. Java 17 is the platform-thread baseline only.
