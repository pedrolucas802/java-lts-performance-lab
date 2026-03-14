# Runbook

This document will contain the exact steps to reproduce benchmark runs for:

- Java 17
- Java 21
- Java 25

Planned:

# 1. Select Java version
export JAVA_HOME=$(/usr/libexec/java_home -v 21)
export PATH="$JAVA_HOME/bin:$PATH"

# 2. Run JMH
bash scripts/runners/run_jmh_all.sh 21

# 3. Run startup benchmark
bash scripts/runners/run_quarkus_startup_benchmark.sh 21 3

# 4. Start Quarkus app
mvn -pl quarkus-app clean package -DskipTests -Djava.release=21
java -jar quarkus-app/target/quarkus-app/quarkus-run.jar

# 5. Run HTTP benchmarks
bash scripts/runners/run_quarkus_http_benchmark.sh 21 products 10s 10
bash scripts/runners/run_quarkus_http_benchmark.sh 21 transform 10s 10
bash scripts/runners/run_quarkus_http_benchmark.sh 21 aggregate-platform 10s 10
bash scripts/runners/run_quarkus_http_benchmark.sh 21 aggregate-virtual 10s 10

# 6. Run memory benchmarks
bash scripts/runners/run_quarkus_memory_benchmark.sh 21 products
bash scripts/runners/run_quarkus_memory_benchmark.sh 21 transform
bash scripts/runners/run_quarkus_memory_benchmark.sh 21 aggregate-platform
bash scripts/runners/run_quarkus_memory_benchmark.sh 21 aggregate-virtual

# 7. Aggregate results
python3 scripts/aggregators/aggregate_quarkus_results.py
python3 scripts/aggregators/aggregate_startup_results.py
python3 scripts/aggregators/aggregate_memory_results.py

# 8. Generate charts
python3 scripts/charts/generate_startup_chart.py
python3 scripts/charts/generate_charts.py