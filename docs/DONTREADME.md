**Goal:**

Benchmark Java 17 vs Java 21 vs Java 25 using:
•	JMH for low-level JVM benchmarks
•	Quarkus for realistic backend benchmarks
•	wrk or k6 for load testing
•	JFR + GC logs for JVM analysis
•	Python for result aggregation and charting

**Core question:**

How much do modern Java LTS releases improve:
•	startup time
•	memory footprint
•	throughput
•	tail latency
•	garbage collection behavior
•	concurrency behavior
•	Quarkus runtime efficiency


---
```
java-lts-performance-lab/
│
├── README.md
├── .gitignore
├── docker-compose.yml
├── Makefile
├── runbook.md
│
├── docs/
│   ├── methodology.md
│   ├── benchmark-matrix.md
│   ├── threats-to-validity.md
│   ├── analysis-notes.md
│   └── charts/
│
├── scripts/
│   ├── setup-jdks.sh
│   ├── run_jmh_all.sh
│   ├── run_quarkus_all.sh
│   ├── run_gc_suite.sh
│   ├── collect_metrics.sh
│   ├── parse_gc_logs.py
│   ├── parse_jfr.py
│   ├── aggregate_results.py
│   └── generate_charts.py
│
├── infra/
│   ├── postgres/
│   │   └── init.sql
│   └── k6/
│       ├── products.js
│       ├── transform.js
│       ├── aggregate.js
│       └── mixed-workload.js
│
├── results/
│   ├── raw/
│   │   ├── java17/
│   │   ├── java21/
│   │   └── java25/
│   ├── processed/
│   └── charts/
│
├── jmh-benchmarks/
│   ├── pom.xml
│   └── src/main/java/com/pedrolucas/benchmarks/
│       ├── JsonBenchmarks.java
│       ├── AllocationBenchmarks.java
│       ├── CollectionBenchmarks.java
│       ├── StringBenchmarks.java
│       └── ConcurrencyBenchmarks.java
│
└── quarkus-app/
├── pom.xml
├── src/main/resources/
│   ├── application.properties
│   └── import.sql
└── src/main/java/com/pedrolucas/lab/
├── api/
│   ├── HealthResource.java
│   ├── ProductResource.java
│   ├── TransformResource.java
│   ├── AggregateResource.java
│   └── OrderResource.java
├── service/
│   ├── ProductService.java
│   ├── TransformService.java
│   ├── AggregateService.java
│   └── OrderService.java
├── domain/
│   ├── Product.java
│   ├── Order.java
│   └── Customer.java
├── dto/
│   ├── ProductDTO.java
│   ├── TransformRequest.java
│   ├── TransformResponse.java
│   └── AggregateResponse.java
└── repository/
└── OrderRepository.java
```

---

Best next move

I suggest we do this in this order:
1.	root repo structure
2.	root pom.xml
3.	jmh-benchmarks/pom.xml
4.	quarkus-app/pom.xml
5.	first endpoints and first JMH classes
6.	benchmark scripts
7.	README skeleton



--- 

**Conclusion**

In this first steady-state Quarkus benchmark on Apple Silicon, Java 25 did not produce a large throughput advantage over Java 21 or Java 17. The three LTS versions performed very similarly under moderate HTTP load, suggesting that the practical gains of upgrading may be more visible in startup, warmup, GC behavior, memory footprint, and newer runtime capabilities than in simple steady-state request throughput alone.

Initial Quarkus HTTP benchmarks on an Apple Silicon M4 Pro showed near-identical steady-state throughput across Java 17, 21, and 25 for lightweight REST workloads. In this setup, Java 25 did not significantly outperform earlier LTS releases in requests/sec, indicating that upgrade benefits may be more visible in startup behavior, memory efficiency, observability, and newer runtime features rather than raw steady-state HTTP throughput alone.