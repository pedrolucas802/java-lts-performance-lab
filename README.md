# java-lts-performance-lab

Benchmarking Java 17 vs Java 21 vs Java 25 with:
- JMH microbenchmarks
- Quarkus application benchmarks
- GC and JFR analysis
- reproducible scripts and charts

## Planned benchmark areas
- startup time
- memory footprint
- throughput
- tail latency
- garbage collection behavior
- virtual threads and concurrency

## Modules
- `jmh-benchmarks`: raw JVM microbenchmarks
- `quarkus-app`: realistic backend benchmark app

## Status
Repository structure initialized. Benchmark implementation in progress.