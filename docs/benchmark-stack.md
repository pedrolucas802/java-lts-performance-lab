# Benchmark Stack

The project uses multiple complementary benchmarking approaches:

### JVM microbenchmarks

- **JMH**
- isolates JVM behavior from framework overhead

### Application benchmarks

- **Quarkus REST application**
- realistic backend request workloads

### Load testing

- **k6**
- controlled HTTP load scenarios

### JVM analysis

- **JFR recordings**
- **GC logs**
- allocation and memory profiling

### Result processing

- **Python scripts**
- automatic aggregation and chart generation