#!/usr/bin/env python3

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt


INPUT_CSV = Path("results/processed/startup-summary.csv")
OUTPUT_PNG = Path("results/charts/startup-comparison.png")


def main() -> None:
    if not INPUT_CSV.exists():
        print(f"Missing input file: {INPUT_CSV}")
        return

    java_versions: list[str] = []
    startup_values: list[int] = []

    with INPUT_CSV.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            java_versions.append(row["java_version"])
            startup_values.append(int(row["startup_ms"]))

    if not java_versions:
        print("No rows found in startup summary.")
        return

    OUTPUT_PNG.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(8, 5))
    plt.bar(java_versions, startup_values)
    plt.title("Quarkus Startup Time by Java Version")
    plt.xlabel("Java Version")
    plt.ylabel("Startup Time (ms)")
    plt.tight_layout()
    plt.savefig(OUTPUT_PNG, dpi=150)

    print(f"Chart written to {OUTPUT_PNG}")


if __name__ == "__main__":
    main()