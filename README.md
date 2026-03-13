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

**[`docs/methodology.md`](docs/methodology.md)**

---

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

# Current Implemented Benchmarks

### JMH

Raw JVM microbenchmarks currently include:

- JSON serialization
- allocation behavior
- collections and string operations

### Quarkus Application Benchmarks

Endpoints used for testing:

| Endpoint | Purpose |
|------|------|
| `/health` | readiness checks |
| `/products` | JSON serialization workload |
| `/transform` | allocation-heavy request/response |
| `/aggregate` | concurrency and fan-out workload |

### Load Testing

HTTP workloads generated using:

- **k6**

Scenarios include:

- products workload
- transform workload
- concurrency aggregation workload

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

# Hardware Used

Initial tests are running on:

- **MacBook Pro**
- **Apple Silicon M4 Pro**
- **48GB RAM**
- macOS ARM64

Future runs may include containerized environments to evaluate JVM container awareness.

---

# Project Status

Current progress:

- repository structure implemented
- JMH microbenchmarks implemented
- Quarkus benchmark application implemented
- startup benchmark pipeline working
- HTTP load tests working
- result aggregation scripts implemented
- startup charts generated

Next work focuses on:

- virtual thread concurrency analysis
- GC log analysis
- JFR runtime profiling
- containerized benchmarks

---

# Philosophy

This project aims to provide **measured JVM behavior** rather than assuming improvements between Java releases.

Some experiments may show **minimal differences between versions**, which is itself a valuable engineering insight.

---

# License

MIT