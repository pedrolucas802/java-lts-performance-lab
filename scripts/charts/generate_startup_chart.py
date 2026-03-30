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

    OUTPUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    profile_column = "profile" if "profile" in df.columns else None
    profiles = (
        sorted(df[profile_column].dropna().unique(), key=lambda name: (name != "stock", name))
        if profile_column else ["stock"]
    )
    default_profile = "stock" if "stock" in profiles else profiles[0]

    generated_outputs = []
    for profile in profiles:
        profile_df = df if profile_column is None else df[df[profile_column] == profile]
        grouped = (
            profile_df.groupby("java_version", as_index=False)["external_startup_ms"]
            .mean()
            .sort_values("java_version")
        )

        output_png = OUTPUT_PNG if profile == default_profile else OUTPUT_PNG.with_name(
            f"{OUTPUT_PNG.stem}-{profile}{OUTPUT_PNG.suffix}"
        )

        plt.figure(figsize=(8, 5))
        plt.bar(grouped["java_version"].astype(str), grouped["external_startup_ms"])
        plt.xlabel("Java Version")
        plt.ylabel("External Startup Time (ms)")
        plt.title(f"Quarkus Startup Comparison ({profile})")
        plt.tight_layout()
        plt.savefig(output_png, dpi=200)
        plt.close()
        generated_outputs.append(output_png)

    for output in generated_outputs:
        print(f"SUCCESS: Startup chart written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
