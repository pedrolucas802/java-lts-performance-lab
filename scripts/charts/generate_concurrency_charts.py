#!/usr/bin/env python3

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib.pyplot as plt


INPUT_CSV = Path("results/processed/concurrency-summary.csv")
OUTPUT_DIR = Path("results/charts")
THREAD_ORDER = ["aggregate-platform", "aggregate-virtual", "aggregate"]


def usage() -> None:
    print("Usage: python generate_concurrency_charts.py")
    print("Generates aggregate platform/virtual comparison charts from results/processed/concurrency-summary.csv")
    print("Outputs charts to results/charts/")


def find_project_root() -> Path:
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / "pom.xml").exists():
            return parent
    return current


def validate_inputs() -> bool:
    if not INPUT_CSV.exists():
        print(f"ERROR: Input file not found: {INPUT_CSV}")
        return False
    return True


def default_profile_name(profiles: list[str]) -> str:
    return "stock" if "stock" in profiles else profiles[0]


def ordered_scenarios(profile_rows: list[dict[str, str]]) -> list[str]:
    available = {row["scenario"] for row in profile_rows}
    ordered = [scenario for scenario in THREAD_ORDER if scenario in available]
    extras = sorted(available.difference(THREAD_ORDER))
    return ordered + extras


def generate_metric_chart(
    profile_rows: list[dict[str, str]],
    metric_key: str,
    metric_label: str,
    title: str,
    output_file: Path,
) -> None:
    java_versions = sorted({row["java_version"] for row in profile_rows}, key=int)
    scenarios = ordered_scenarios(profile_rows)
    series = {
        (row["java_version"], row["scenario"]): float(row[metric_key]) if row.get(metric_key) else 0.0
        for row in profile_rows
    }

    fig, ax = plt.subplots(figsize=(9, 5))
    bar_width = 0.22
    x = range(len(java_versions))

    for index, scenario in enumerate(scenarios):
        values = [
            series.get((java_version, scenario), 0.0)
            for java_version in java_versions
        ]
        positions = [value + index * bar_width for value in x]
        ax.bar(positions, values, bar_width, label=scenario)

    ax.set_xlabel("Java version")
    ax.set_ylabel(metric_label)
    ax.set_title(title)
    center_offset = bar_width * max(len(scenarios) - 1, 0) / 2
    ax.set_xticks([value + center_offset for value in x])
    ax.set_xticklabels([f"Java {java_version}" for java_version in java_versions])
    ax.legend()
    plt.tight_layout()
    plt.savefig(output_file, dpi=150)
    plt.close()


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h"):
        usage()
        sys.exit(0)

    project_root = find_project_root()
    import os
    os.chdir(project_root)

    if not validate_inputs():
        sys.exit(1)

    try:
        with INPUT_CSV.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except Exception as exc:
        print(f"ERROR: Failed to read input CSV {INPUT_CSV}: {exc}")
        sys.exit(1)

    if not rows:
        print("FAILURE: No rows found in concurrency summary CSV")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    profiles = sorted({row.get("profile", "stock") or "stock" for row in rows}, key=lambda name: (name != "stock", name))
    default_profile = default_profile_name(profiles)
    outputs: list[Path] = []

    for profile in profiles:
        suffix = "" if profile == default_profile else f"-{profile}"
        profile_rows = [row for row in rows if (row.get("profile", "stock") or "stock") == profile]

        throughput_png = OUTPUT_DIR / f"concurrency-throughput-comparison{suffix}.png"
        generate_metric_chart(
            profile_rows,
            "reqs_per_sec",
            "Requests/sec",
            f"Aggregate Throughput by Thread Mode ({profile})",
            throughput_png,
        )
        outputs.append(throughput_png)

        latency_png = OUTPUT_DIR / f"concurrency-latency-comparison{suffix}.png"
        generate_metric_chart(
            profile_rows,
            "p95_ms",
            "P95 latency (ms)",
            f"Aggregate P95 Latency by Thread Mode ({profile})",
            latency_png,
        )
        outputs.append(latency_png)

    print("SUCCESS: Generated concurrency charts")
    print(f"  Input CSV: {INPUT_CSV}")
    for output in outputs:
        print(f"  Chart: {output}")


if __name__ == "__main__":
    main()
