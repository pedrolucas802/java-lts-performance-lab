#!/usr/bin/env python3

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib.pyplot as plt


INPUT_CSV = Path("results/processed/gc-summary.csv")
OUTPUT_DIR = Path("results/charts")


def usage() -> None:
    print("Usage: python generate_gc_charts.py")
    print("Generates GC pause charts from results/processed/gc-summary.csv")
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


def ordered_labels(profile_rows: list[dict[str, str]]) -> list[tuple[str, str]]:
    preferred = [
        ("17", "products-db"),
        ("17", "aggregate-platform"),
        ("21", "products-db"),
        ("21", "aggregate-platform"),
        ("21", "aggregate-virtual"),
        ("25", "products-db"),
        ("25", "aggregate-platform"),
        ("25", "aggregate-virtual"),
    ]
    available = {(row["java_version"], row["scenario"]) for row in profile_rows}
    ordered = [item for item in preferred if item in available]
    extras = sorted(available.difference(preferred), key=lambda item: (int(item[0]), item[1]))
    return ordered + extras


def generate_metric_chart(
    profile_rows: list[dict[str, str]],
    metric_key: str,
    metric_label: str,
    title: str,
    output_file: Path,
) -> None:
    labels = ordered_labels(profile_rows)
    values_map = {
        (row["java_version"], row["scenario"]): float(row[metric_key]) if row.get(metric_key) else 0.0
        for row in profile_rows
    }

    x_labels = [f"J{java}\n{scenario.replace('aggregate-', '')}" for java, scenario in labels]
    values = [values_map.get(label, 0.0) for label in labels]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(range(len(labels)), values, color="#38761d")
    ax.set_xlabel("Java version and scenario")
    ax.set_ylabel(metric_label)
    ax.set_title(title)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(x_labels)
    ax.grid(True, axis="y", alpha=0.3)
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
        print("FAILURE: No rows found in GC summary CSV")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    profiles = sorted({row.get("profile", "stock") or "stock" for row in rows}, key=lambda name: (name != "stock", name))
    default_profile = default_profile_name(profiles)
    outputs: list[Path] = []

    for profile in profiles:
        suffix = "" if profile == default_profile else f"-{profile}"
        profile_rows = [row for row in rows if (row.get("profile", "stock") or "stock") == profile]

        total_pause_png = OUTPUT_DIR / f"gc-total-pause-comparison{suffix}.png"
        generate_metric_chart(
            profile_rows,
            "total_pause_ms",
            "Total GC pause (ms)",
            f"Total GC Pause by Java Version and Scenario ({profile})",
            total_pause_png,
        )
        outputs.append(total_pause_png)

        max_pause_png = OUTPUT_DIR / f"gc-max-pause-comparison{suffix}.png"
        generate_metric_chart(
            profile_rows,
            "max_pause_ms",
            "Max GC pause (ms)",
            f"Max GC Pause by Java Version and Scenario ({profile})",
            max_pause_png,
        )
        outputs.append(max_pause_png)

    print("SUCCESS: Generated GC charts")
    print(f"  Input CSV: {INPUT_CSV}")
    for output in outputs:
        print(f"  Chart: {output}")


if __name__ == "__main__":
    main()
