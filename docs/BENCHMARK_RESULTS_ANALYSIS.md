# Java LTS Performance Lab - Benchmark Results Analysis
**Heavy Load Test: March 16, 2026**

---

## Executive Summary

This report analyzes the heavy load benchmark comparing **Java 17 (baseline), Java 21 (virtual threads), and Java 25 (optimizations)** across startup time, HTTP throughput, latency, and memory usage.

**Test Configuration:**
- **Virtual Users (VUs)**: 50 concurrent users
- **Duration**: 60 seconds per scenario
- **Startup Repetitions**: 5 runs each
- **Scenarios**: Products, Transform, Aggregate-Platform, Aggregate-Virtual (21/25 only)

---

## 1. STARTUP TIME ANALYSIS

### Overview
Quarkus startup time under different Java versions.

| Java Version | Avg External (ms) | Avg Quarkus (ms) | Runs | Variance |
|---|---|---|---|---|
| **Java 17** | 456 | 249 | 5 | Low (±2ms) |
| **Java 21** | 457 | 263 | 5 | Medium (±18ms) |
| **Java 25** | 455 | 256 | 5 | Low (±15ms) |

### Key Findings

✅ **Startup Performance is Consistent Across Versions**
- All three versions start in ~450-460ms (external measure)
- Difference: ~7ms total across versions (1.5% variance)
- Java 21 shows slightly higher Quarkus internal startup time (263ms vs 249-256ms)

🔍 **Interpretation**
- **No startup regression** from Java 17 → 25
- Java 21's additional internal startup overhead is minimal and likely attributable to virtual thread initialization
- Java 25 brings it closer to Java 17 levels, suggesting optimization

---

## 2. HTTP LOAD TEST ANALYSIS (Heavy: 50 VUs, 60s)

### Throughput Comparison

| Scenario | Java 17 | Java 21 | Java 25 | Winner |
|---|---|---|---|---|
| **Products** | 192.4 req/s | 191.8 req/s | 192.4 req/s | **Tie (17/25)** |
| **Transform** | 193.0 req/s | 192.4 req/s | 193.1 req/s | **Tie (17/25)** |
| **Aggregate-Platform** | 529.7 req/s | 527.6 req/s | 528.5 req/s | **Tie (17/25)** |
| **Aggregate-Virtual** | N/A | 507.5 req/s | 524.1 req/s | **Java 25 +3.3%** |

### Latency Analysis (95th Percentile)

| Scenario | Java 17 | Java 21 | Java 25 |
|---|---|---|---|
| **Products** | 5.96 ms | 5.98 ms | 6.39 ms |
| **Transform** | 4.03 ms | 4.53 ms | 4.17 ms |
| **Aggregate-Platform** | 47.73 ms | 47.63 ms | 47.53 ms | 
| **Aggregate-Virtual** | N/A | 50.27 ms | 47.45 ms |

### Key Findings

✅ **Throughput is Essentially Equivalent**
- All versions handle 192-193 req/s on simple endpoints (Products/Transform)
- Aggregate workloads reach 507-529 req/s
- Differences: <1% variance (within statistical noise)

⚠️ **Virtual Threads Show Benefit**
- **Java 25 aggregate-virtual**: 524.1 req/s (vs Java 21: 507.5 req/s)
- **Improvement: +3.3%** under virtual thread workload
- This suggests Java 25's virtual thread optimizations are kicking in

🔍 **Latency is Stable**
- P95 latencies consistent across versions
- Simple workloads: 2-6ms
- Complex workloads: 44-50ms
- Java 25 slightly better on aggregate-virtual (47.45ms vs 50.27ms)

---

## 3. MEMORY USAGE ANALYSIS

### Idle Memory (RSS in KB)

| Scenario | Java 17 | Java 21 | Java 25 |
|---|---|---|---|
| **Products** | 127.6 MB | 144.8 MB | 140.9 MB |
| **Transform** | 137.2 MB | 142.9 MB | 140.4 MB |
| **Aggregate-Platform** | 137.7 MB | 142.5 MB | 141.9 MB |
| **Aggregate-Virtual** | N/A | 145.3 MB | 141.1 MB |

### Peak Memory Under Load (RSS in KB)

| Scenario | Java 17 | Java 21 | Java 25 | Winner |
|---|---|---|---|---|
| **Products** | 234.0 MB | 234.7 MB | 192.3 MB | **Java 25 -18%** ✅ |
| **Transform** | 195.1 MB | 210.3 MB | 177.1 MB | **Java 25 -9%** ✅ |
| **Aggregate-Platform** | 264.8 MB | 226.8 MB | 439.0 MB | **Java 21 -14%** ⚠️ |
| **Aggregate-Virtual** | N/A | 237.3 MB | 431.4 MB | **Java 21 -45%** ⚠️ |

### Memory Delta (Load Increase)

| Scenario | Java 17 | Java 21 | Java 25 |
|---|---|---|---|
| **Products** | 106.4 MB | 89.9 MB | 51.4 MB |
| **Transform** | 58.0 MB | 67.4 MB | 36.7 MB |
| **Aggregate-Platform** | 127.1 MB | 84.3 MB | 297.1 MB |
| **Aggregate-Virtual** | N/A | 92.1 MB | 290.3 MB |

### Key Findings

✅ **Java 25 Reduces Memory Under Light Loads**
- Products: -18% peak memory (234MB → 192MB)
- Transform: -9% peak memory (195MB → 177MB)
- **Memory optimization is real for simple workloads**

⚠️ **Aggregate Workloads Show Anomaly**
- Java 25 uses significantly MORE memory under aggregate load (297MB vs 127MB for Java 17)
- This is a **2.3x increase** compared to Java 17
- Java 21 performs better here (84MB delta)

🔍 **Interpretation**
- Java 25 memory optimizations work well for **simple, allocation-light workloads**
- But aggregate workloads (which do fan-out requests) consume more memory
- Possible cause: Java 25 may be buffering more requests/responses in memory
- **Requires investigation** into garbage collection behavior (see GC Suite logs)

---

## 4. PERFORMANCE STABILITY

### Consistency Metrics (Lower is Better)

**Startup Variance (ms):**
- Java 17: ±2.0 ms (Excellent)
- Java 21: ±18.0 ms (Good, but higher)
- Java 25: ±15.0 ms (Good)

**Throughput Variance (<1%):**
- All three versions show excellent consistency across 60-second heavy load

---

## 5. CONCLUSIONS & RECOMMENDATIONS

### ✅ What's Working Well

1. **All Versions Are Performant**
   - No version shows startup regression
   - Throughput equivalent across the board
   - Latency is stable and low

2. **Java 25 Virtual Thread Optimization**
   - Aggregate-virtual workload: +3.3% throughput
   - Better latency on virtual thread scenarios (47.45ms)
   - Shows promise for I/O-bound concurrent workloads

3. **Java 25 Memory Efficiency (Simple Workloads)**
   - 18% peak memory reduction on products scenario
   - 9% reduction on transform scenario
   - Suggests better memory management for allocation-heavy code

### ⚠️ Areas Requiring Investigation

1. **Java 21 Higher Startup Variance**
   - Why does run #1 show 305ms Quarkus startup vs ~256ms average?
   - Could be JIT compilation variance or virtual thread warmup

2. **Java 25 Aggregate Memory Spike**
   - Peak memory increases to 439MB under aggregate-platform load (vs 264MB Java 17)
   - Need to analyze GC logs in `results/raw/java25/gc/`
   - Possible causes:
     - Different GC tuning
     - Memory buffering strategy changed
     - Virtual thread overhead not yet optimized

3. **Aggregate-Virtual Inconsistency**
   - Java 25 shows both best throughput (+3.3%) AND worst memory usage
   - Trade-off between throughput and memory efficiency

### 🎯 Recommendations

**For Production:**
1. **Use Java 25 for simple REST workloads** - 18% memory savings is significant
2. **Monitor Java 25 aggregate workloads** - throughput gain not worth the memory cost yet
3. **Java 21 remains solid baseline** - consistent performance across all scenarios

**For Further Analysis:**
1. Run with `--heap-info` flag to capture GC logs and analyze:
   - Full GC frequency
   - Pause times
   - Heap fragmentation
2. Profile aggregate workload with Java Flight Recorder (JFR) to understand memory allocation patterns
3. Test with different heap sizes (-Xmx) to see if Java 25 memory issue is heap pressure or allocation pattern

**Benchmark Improvement:**
1. The 60-second duration tests show good stability - consider this the standard
2. Generate box plots for latency percentiles (not just p95)
3. Add memory timeline graphs (not just idle/peak delta)

---

## Generated Charts

📊 Available in `results/charts/`:
- `startup-comparison.png` - Startup time across versions
- `quarkus-throughput-comparison.png` - Requests/sec by scenario
- `quarkus-latency-comparison.png` - P95 latency comparison
- `quarkus-failure-rate-comparison.png` - Error rate (all 0%)

---

## Data Files

Raw results available in `results/processed/`:
- `startup-summary.csv` - All 15 startup runs (5 per version)
- `quarkus-summary.csv` - HTTP benchmark metrics
- `memory-summary.csv` - Memory profiling data

GC logs (if collected):
- `results/raw/java{17,21,25}/gc/` - GC analysis files

