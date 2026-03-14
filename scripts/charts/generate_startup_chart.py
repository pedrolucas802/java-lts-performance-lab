#!/usr/bin/env python3

from pathlib import Path
import sys
import pandas as pd
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_CSV = PROJECT_ROOT / "results" / "processed" / "startup-summary.csv"
OUTPUT_PNG = PROJECT_ROOT / "results" / "charts" / "startup-comparison.png"


def main() -> int:
    if not INPUT_CSV.exists():
        print(f"ERROR: Missing input CSV: {INPUT_CSV}")
        return 1

    try:
        df = pd.read_csv(INPUT_CSV)
    except Exception as exc:
        print(f"ERROR: Failed to read input CSV {INPUT_CSV}: {exc}")
        return 1

    if df.empty:
        print("ERROR: Startup summary CSV is empty.")
        return 1

    if "external_startup_ms" not in df.columns:
        print(
            "ERROR: Expected column 'external_startup_ms' not found. "
            f"Available columns: {list(df.columns)}"
        )
        return 1

    if "java_version" not in df.columns:
        print(
            "ERROR: Expected column 'java_version' not found. "
            f"Available columns: {list(df.columns)}"
        )
        return 1

    # average repeated runs by Java version
    grouped = (
        df.groupby("java_version", as_index=False)["external_startup_ms"]
        .mean()
        .sort_values("java_version")
    )

    OUTPUT_PNG.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(8, 5))
    plt.bar(grouped["java_version"].astype(str), grouped["external_startup_ms"])
    plt.xlabel("Java Version")
    plt.ylabel("External Startup Time (ms)")
    plt.title("Quarkus Startup Comparison")
    plt.tight_layout()
    plt.savefig(OUTPUT_PNG, dpi=200)
    plt.close()

    print(f"SUCCESS: Startup chart written to {OUTPUT_PNG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())