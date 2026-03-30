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
    lane_column = "lane" if "lane" in df.columns else None
    profiles = (
        sorted(df[profile_column].dropna().unique(), key=lambda name: (name != "stock", name))
        if profile_column else ["stock"]
    )
    lanes = (
        sorted(df[lane_column].dropna().unique(), key=lambda name: (name != "host", name))
        if lane_column else ["host"]
    )
    default_profile = "stock" if "stock" in profiles else profiles[0]
    default_lane = "host" if "host" in lanes else lanes[0]

    generated_outputs = []
    for lane in lanes:
        lane_df = df if lane_column is None else df[df[lane_column] == lane]
        for profile in profiles:
            profile_df = lane_df if profile_column is None else lane_df[lane_df[profile_column] == profile]
            if profile_df.empty:
                continue

            grouped = (
                profile_df.groupby("java_version", as_index=False)["external_startup_ms"]
                .mean()
                .sort_values("java_version")
            )

            suffix_parts = []
            if lane != "host":
                suffix_parts.append(lane)
            if profile != default_profile:
                suffix_parts.append(profile)
            suffix = f"-{'-'.join(suffix_parts)}" if suffix_parts else ""
            output_png = OUTPUT_PNG.with_name(f"{OUTPUT_PNG.stem}{suffix}{OUTPUT_PNG.suffix}")

            plt.figure(figsize=(8, 5))
            plt.bar(grouped["java_version"].astype(str), grouped["external_startup_ms"])
            plt.xlabel("Java Version")
            plt.ylabel("External Startup Time (ms)")
            plt.title(f"Quarkus Startup Comparison ({lane}, {profile})")
            plt.tight_layout()
            plt.savefig(output_png, dpi=200)
            plt.close()
            generated_outputs.append(output_png)

    for output in generated_outputs:
        print(f"SUCCESS: Startup chart written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
