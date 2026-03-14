#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


# Constants
RESULTS_ROOT = Path("results/raw")
OUTPUT_DIR = Path("results/processed")
CSV_OUTPUT = OUTPUT_DIR / "memory-summary.csv"
JSON_OUTPUT = OUTPUT_DIR / "memory-summary.json"


def usage() -> None:
    """Print usage information."""
    print("Usage: python aggregate_memory_results.py")
    print("Aggregates memory benchmark results from results/raw/*/memory/*-memory-java*.txt")
    print("Outputs to results/processed/memory-summary.csv and .json")


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
        import csv, json
        return True
    except ImportError as e:
        print(f"ERROR: Missing required module: {e}")
        return False


def validate_inputs() -> bool:
    """Validate input directories and files exist."""
    if not RESULTS_ROOT.exists():
        print(f"ERROR: Results directory not found: {RESULTS_ROOT}")
        return False
    return True


def parse_key_value_file(file_path: Path) -> dict[str, str]:
    """Parse a key=value file into a dictionary."""
    data: dict[str, str] = {}
    try:
        for line in file_path.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    except Exception as e:
        print(f"WARNING: Failed to parse {file_path}: {e}")
    return data


def collect_rows() -> list[dict]:
    rows: list[dict] = []

    for memory_dir in sorted(RESULTS_ROOT.glob("java*/memory")):
        java_version = memory_dir.parent.name.replace("java", "")

        for metrics_file in sorted(memory_dir.glob("*-memory-java*.txt")):
            parsed = parse_key_value_file(metrics_file)

            rows.append({
                "java_version": java_version,
                "scenario": parsed.get("scenario", ""),
                "idle_rss_kb": int(parsed.get("idle_rss_kb", "0")),
                "post_load_rss_kb": int(parsed.get("post_load_rss_kb", "0")),
                "rss_delta_kb": int(parsed.get("rss_delta_kb", "0")),
                "pid": int(parsed.get("pid", "0")),
                "log_file": parsed.get("log_file", ""),
                "source_file": str(metrics_file),
            })

    return rows


def write_csv(rows: list[dict], output_file: Path) -> None:
    fieldnames = [
        "java_version",
        "scenario",
        "idle_rss_kb",
        "post_load_rss_kb",
        "rss_delta_kb",
        "pid",
        "log_file",
        "source_file",
    ]
    try:
        with output_file.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    except Exception as e:
        print(f"ERROR: Failed to write CSV {output_file}: {e}")
        sys.exit(1)


def write_json(rows: list[dict], output_file: Path) -> None:
    try:
        output_file.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"ERROR: Failed to write JSON {output_file}: {e}")
        sys.exit(1)


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

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = collect_rows()

    if not rows:
        print("FAILURE: No memory benchmark results found in results/raw/*/memory/*-memory-java*.txt")
        sys.exit(1)

    write_csv(rows, CSV_OUTPUT)
    write_json(rows, JSON_OUTPUT)

    print("SUCCESS: Aggregated memory results")
    print(f"  Rows processed: {len(rows)}")
    print(f"  CSV output: {CSV_OUTPUT}")
    print(f"  JSON output: {JSON_OUTPUT}")


if __name__ == "__main__":
    main()