#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


INPUT_CSV = Path("results/processed/quarkus-summary.csv")
OUTPUT_DIR = Path("results/processed")
CSV_OUTPUT = OUTPUT_DIR / "concurrency-summary.csv"
JSON_OUTPUT = OUTPUT_DIR / "concurrency-summary.json"
CONCURRENCY_SCENARIOS = {"aggregate", "aggregate-platform", "aggregate-virtual"}


def usage() -> None:
    print("Usage: python aggregate_concurrency_results.py")
    print("Filters aggregate platform/virtual rows from results/processed/quarkus-summary.csv")
    print("Outputs to results/processed/concurrency-summary.csv and .json")


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


def load_rows() -> list[dict[str, str]]:
    try:
        with INPUT_CSV.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except Exception as exc:
        print(f"ERROR: Failed to read input CSV {INPUT_CSV}: {exc}")
        sys.exit(1)


def collect_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    concurrency_rows = [
        row for row in rows
        if row.get("scenario") in CONCURRENCY_SCENARIOS
    ]
    concurrency_rows.sort(
        key=lambda row: (
            row.get("profile", "stock"),
            int(row.get("java_version", "0")),
            row.get("scenario", ""),
        )
    )
    return concurrency_rows


def write_csv(rows: list[dict[str, str]]) -> None:
    if not rows:
        print("FAILURE: No aggregate concurrency rows found in Quarkus summary data")
        sys.exit(1)

    fieldnames = [
        "java_version",
        "scenario",
        "profile",
        "thread_mode",
        "db_mode",
        "run_class",
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
        with CSV_OUTPUT.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    except Exception as exc:
        print(f"ERROR: Failed to write CSV {CSV_OUTPUT}: {exc}")
        sys.exit(1)


def write_json(rows: list[dict[str, str]]) -> None:
    try:
        JSON_OUTPUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"ERROR: Failed to write JSON {JSON_OUTPUT}: {exc}")
        sys.exit(1)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h"):
        usage()
        sys.exit(0)

    project_root = find_project_root()
    import os
    os.chdir(project_root)

    if not validate_inputs():
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = collect_rows(load_rows())
    write_csv(rows)
    write_json(rows)

    print("SUCCESS: Aggregated concurrency results")
    print(f"  Rows processed: {len(rows)}")
    print(f"  CSV output: {CSV_OUTPUT}")
    print(f"  JSON output: {JSON_OUTPUT}")


if __name__ == "__main__":
    main()
