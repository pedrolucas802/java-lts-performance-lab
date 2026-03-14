#!/usr/bin/env python3

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib.pyplot as plt


# Constants
INPUT_CSV = Path("results/processed/quarkus-summary.csv")
OUTPUT_DIR = Path("results/charts")


def usage() -> None:
    """Print usage information."""
    print("Usage: python generate_quarkus_charts.py")
    print("Generates various charts from Quarkus benchmark results in results/processed/quarkus-summary.csv")
    print("Outputs charts to results/charts/")


def find_project_root() -> Path:
    """Find the project root directory by looking for pom.xml."""
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / "pom.xml").exists():
            return parent
    return current  # fallback to cwd


def check_dependencies() -> bool:
    """Check if required modules are available."""
    try:
        import matplotlib.pyplot
        import csv
        return True
    except ImportError as e:
        print(f"ERROR: Missing required module: {e}")
        print("Install with: pip install matplotlib")
        return False


def validate_inputs() -> bool:
    """Validate input files exist."""
    if not INPUT_CSV.exists():
        print(f"ERROR: Input file not found: {INPUT_CSV}")
        return False
    return True


def generate_throughput_chart(data: dict, output_file: Path) -> None:
    """Generate throughput comparison chart."""
    java_versions = list(data.keys())
    scenarios = list(data[java_versions[0]].keys())

    fig, ax = plt.subplots(figsize=(10, 6))
    bar_width = 0.2
    x = range(len(scenarios))

    for i, java in enumerate(java_versions):
        throughputs = [data[java][scenario]['reqs_per_sec'] or 0 for scenario in scenarios]
        ax.bar([pos + i * bar_width for pos in x], throughputs, bar_width, label=f'Java {java}')

    ax.set_xlabel('Scenario')
    ax.set_ylabel('Requests/sec')
    ax.set_title('Quarkus Throughput by Java Version and Scenario')
    ax.set_xticks([pos + bar_width for pos in x])
    ax.set_xticklabels(scenarios)
    ax.legend()
    plt.tight_layout()
    plt.savefig(output_file, dpi=150)
    plt.close()


def generate_latency_chart(data: dict, output_file: Path) -> None:
    """Generate latency comparison chart."""
    java_versions = list(data.keys())
    scenarios = list(data[java_versions[0]].keys())

    fig, ax = plt.subplots(figsize=(10, 6))
    bar_width = 0.15
    x = range(len(scenarios))

    for i, java in enumerate(java_versions):
        avg_latencies = [data[java][scenario]['avg_ms'] or 0 for scenario in scenarios]
        p95_latencies = [data[java][scenario]['p95_ms'] or 0 for scenario in scenarios]

        ax.bar([pos + i * bar_width for pos in x], avg_latencies, bar_width, label=f'Java {java} Avg', alpha=0.7)
        ax.bar([pos + i * bar_width + bar_width/2 for pos in x], p95_latencies, bar_width, label=f'Java {java} P95', alpha=0.7)

    ax.set_xlabel('Scenario')
    ax.set_ylabel('Latency (ms)')
    ax.set_title('Quarkus Latency by Java Version and Scenario')
    ax.set_xticks([pos + bar_width for pos in x])
    ax.set_xticklabels(scenarios)
    ax.legend()
    plt.tight_layout()
    plt.savefig(output_file, dpi=150)
    plt.close()


def generate_failure_rate_chart(data: dict, output_file: Path) -> None:
    """Generate failure rate comparison chart."""
    java_versions = list(data.keys())
    scenarios = list(data[java_versions[0]].keys())

    fig, ax = plt.subplots(figsize=(10, 6))
    bar_width = 0.2
    x = range(len(scenarios))

    for i, java in enumerate(java_versions):
        failure_rates = [data[java][scenario]['failed_rate'] or 0 for scenario in scenarios]
        ax.bar([pos + i * bar_width for pos in x], failure_rates, bar_width, label=f'Java {java}')

    ax.set_xlabel('Scenario')
    ax.set_ylabel('Failure Rate (%)')
    ax.set_title('Quarkus Failure Rate by Java Version and Scenario')
    ax.set_xticks([pos + bar_width for pos in x])
    ax.set_xticklabels(scenarios)
    ax.legend()
    plt.tight_layout()
    plt.savefig(output_file, dpi=150)
    plt.close()


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h"):
        usage()
        sys.exit(0)

    # Change to project root
    project_root = find_project_root()
    import os
    os.chdir(project_root)

    if not check_dependencies():
        sys.exit(1)

    if not validate_inputs():
        sys.exit(1)

    # Load data
    data = {}
    try:
        with INPUT_CSV.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                java = row["java_version"]
                scenario = row["scenario"]
                if java not in data:
                    data[java] = {}
                data[java][scenario] = {
                    'reqs_per_sec': float(row["reqs_per_sec"]) if row["reqs_per_sec"] else None,
                    'avg_ms': float(row["avg_ms"]) if row["avg_ms"] else None,
                    'p95_ms': float(row["p95_ms"]) if row["p95_ms"] else None,
                    'failed_rate': float(row["failed_rate"]) if row["failed_rate"] else None,
                }
    except Exception as e:
        print(f"ERROR: Failed to read input CSV {INPUT_CSV}: {e}")
        sys.exit(1)

    if not data:
        print("FAILURE: No data found in Quarkus summary CSV")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate charts
    throughput_png = OUTPUT_DIR / "quarkus-throughput-comparison.png"
    try:
        generate_throughput_chart(data, throughput_png)
    except Exception as e:
        print(f"ERROR: Failed to generate throughput chart {throughput_png}: {e}")
        sys.exit(1)

    latency_png = OUTPUT_DIR / "quarkus-latency-comparison.png"
    try:
        generate_latency_chart(data, latency_png)
    except Exception as e:
        print(f"ERROR: Failed to generate latency chart {latency_png}: {e}")
        sys.exit(1)

    failure_rate_png = OUTPUT_DIR / "quarkus-failure-rate-comparison.png"
    try:
        generate_failure_rate_chart(data, failure_rate_png)
    except Exception as e:
        print(f"ERROR: Failed to generate failure rate chart {failure_rate_png}: {e}")
        sys.exit(1)

    print("SUCCESS: Generated Quarkus charts")
    print(f"  Input CSV: {INPUT_CSV}")
    print(f"  Throughput chart: {throughput_png}")
    print(f"  Latency chart: {latency_png}")
    print(f"  Failure rate chart: {failure_rate_png}")


if __name__ == "__main__":
    main()
