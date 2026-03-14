#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path


# Constants
RESULTS_ROOT = Path("results/raw")
OUTPUT_DIR = Path("results/processed")
CSV_OUTPUT = OUTPUT_DIR / "quarkus-summary.csv"
JSON_OUTPUT = OUTPUT_DIR / "quarkus-summary.json"


def usage() -> None:
    """Print usage information."""
    print("Usage: python aggregate_quarkus_results.py")
    print("Aggregates Quarkus HTTP benchmark results from results/raw/*/quarkus/*-summary.txt")
    print("Outputs to results/processed/quarkus-summary.csv and .json")


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
        import csv, json, re
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


def extract_float(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        return None
    return float(match.group(1))


def extract_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        return None
    return int(match.group(1))


def parse_summary_file(file_path: Path, java_version: str, scenario: str) -> dict:
    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"WARNING: Failed to read {file_path}: {e}")
        return {}

    http_reqs = extract_int(r"http_reqs\.*:\s+(\d+)", text)
    reqs_per_sec = extract_float(r"http_reqs\.*:\s+\d+\s+([0-9.]+)\/s", text)

    avg_ms = extract_float(r"http_req_duration\.*:\s+avg=([0-9.]+)ms", text)
    p90_ms = extract_float(r"p\(90\)=([0-9.]+)ms", text)
    p95_ms = extract_float(r"p\(95\)=([0-9.]+)ms", text)
    max_ms = extract_float(r"max=([0-9.]+)ms", text)

    failed_rate = extract_float(r"http_req_failed\.*:\s+([0-9.]+)%", text)

    return {
        "java_version": java_version,
        "scenario": scenario,
        "http_reqs": http_reqs,
        "reqs_per_sec": reqs_per_sec,
        "avg_ms": avg_ms,
        "p90_ms": p90_ms,
        "p95_ms": p95_ms,
        "max_ms": max_ms,
        "failed_rate": failed_rate,
        "source_file": str(file_path),
    }


def collect_rows() -> list[dict]:
    rows: list[dict] = []

    for java_dir in sorted(RESULTS_ROOT.glob("java*/quarkus")):
        java_version = java_dir.parent.name.replace("java", "")

        for summary_file in sorted(java_dir.glob("*-summary.txt")):
            scenario = summary_file.name.replace("-summary.txt", "")
            row = parse_summary_file(summary_file, java_version, scenario)
            if row:  # only add if parsing succeeded
                rows.append(row)

    return rows


def merge_repeated_runs(rows: list[dict]) -> list[dict]:
    """Optionally merge repeated runs by averaging metrics."""
    from collections import defaultdict
    import statistics

    merged = defaultdict(list)
    for row in rows:
        key = (row['java_version'], row['scenario'])
        merged[key].append(row)

    result = []
    for (java_version, scenario), runs in merged.items():
        if len(runs) == 1:
            result.append(runs[0])
        else:
            # Average numeric metrics
            avg_row = {
                'java_version': java_version,
                'scenario': scenario,
                'http_reqs': sum(r.get('http_reqs') or 0 for r in runs) // len(runs),
                'reqs_per_sec': statistics.mean(r['reqs_per_sec'] for r in runs if r.get('reqs_per_sec')),
                'avg_ms': statistics.mean(r['avg_ms'] for r in runs if r.get('avg_ms')),
                'p90_ms': statistics.mean(r['p90_ms'] for r in runs if r.get('p90_ms')),
                'p95_ms': statistics.mean(r['p95_ms'] for r in runs if r.get('p95_ms')),
                'max_ms': statistics.mean(r['max_ms'] for r in runs if r.get('max_ms')),
                'failed_rate': statistics.mean(r['failed_rate'] for r in runs if r.get('failed_rate') is not None),
                'source_file': f"merged_{len(runs)}_runs",
            }
            result.append(avg_row)

    return result


def write_csv(rows: list[dict], output_file: Path) -> None:
    fieldnames = [
        "java_version",
        "scenario",
        "http_reqs",
        "reqs_per_sec",
        "avg_ms",
        "p90_ms",
        "p95_ms",
        "max_ms",
        "failed_rate",
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
        print("FAILURE: No Quarkus summary files found under results/raw/*/quarkus/*-summary.txt")
        sys.exit(1)

    # Merge repeated runs
    merged_rows = merge_repeated_runs(rows)

    write_csv(merged_rows, CSV_OUTPUT)
    write_json(merged_rows, JSON_OUTPUT)

    print("SUCCESS: Aggregated Quarkus results")
    print(f"  Rows processed: {len(merged_rows)}")
    print(f"  CSV output: {CSV_OUTPUT}")
    print(f"  JSON output: {JSON_OUTPUT}")


if __name__ == "__main__":
    main()