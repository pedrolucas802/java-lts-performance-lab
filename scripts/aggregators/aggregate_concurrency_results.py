#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

from result_metadata import common_run_metadata, iter_track_dirs, scenario_metadata

RESULTS_ROOT = Path("results/raw")
OUTPUT_DIR = Path("results/processed")
CSV_OUTPUT = OUTPUT_DIR / "concurrency-summary.csv"
JSON_OUTPUT = OUTPUT_DIR / "concurrency-summary.json"


def usage() -> None:
    print("Usage: python aggregate_concurrency_results.py")
    print("Aggregates raw concurrency ramp results from results/raw/*/concurrency/*-metrics.txt")
    print("Outputs to results/processed/concurrency-summary.csv and .json")


def find_project_root() -> Path:
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / "pom.xml").exists():
            return parent
    return current


def validate_inputs() -> bool:
    if not RESULTS_ROOT.exists():
        print(f"ERROR: Results directory not found: {RESULTS_ROOT}")
        return False
    return True


def parse_key_value_file(file_path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        for line in file_path.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    except Exception as exc:
        print(f"WARNING: Failed to parse {file_path}: {exc}")
    return data


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


def parse_summary_file(file_path: Path) -> dict[str, float | int | None]:
    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"WARNING: Failed to read {file_path}: {exc}")
        return {}

    return {
        "http_reqs": extract_int(r"http_reqs\.*:\s+(\d+)", text),
        "reqs_per_sec": extract_float(r"http_reqs\.*:\s+\d+\s+([0-9.]+)\/s", text),
        "avg_ms": extract_float(r"http_req_duration\.*:\s+avg=([0-9.]+)ms", text),
        "p90_ms": extract_float(r"p\(90\)=([0-9.]+)ms", text),
        "p95_ms": extract_float(r"p\(95\)=([0-9.]+)ms", text),
        "max_ms": extract_float(r"max=([0-9.]+)ms", text),
        "failed_rate": extract_float(r"http_req_failed\.*:\s+([0-9.]+)%", text),
    }


def collect_rows() -> list[dict[str, str | int | float | None]]:
    rows: list[dict[str, str | int | float | None]] = []

    for profile, lane, java_version, concurrency_dir in iter_track_dirs(RESULTS_ROOT, "concurrency"):
        for metrics_file in sorted(concurrency_dir.glob("*-metrics.txt")):
            parsed = parse_key_value_file(metrics_file)
            scenario = parsed.get("scenario", "")
            metadata = scenario_metadata(scenario, parsed.get("run_class", "concurrency"), metrics_file)
            run_metadata = common_run_metadata(parsed, profile, lane)

            summary_file = Path(parsed.get("summary_file", metrics_file.name.replace("-metrics.txt", "-summary.txt")))
            if not summary_file.is_absolute():
                summary_file = metrics_file.parent / summary_file.name

            summary_metrics = parse_summary_file(summary_file)
            if not summary_metrics:
                continue

            rows.append({
                "java_version": java_version,
                "scenario": metadata["scenario"],
                "profile": run_metadata["profile"],
                "lane": run_metadata["lane"],
                "host_os": run_metadata["host_os"],
                "container_runtime": run_metadata["container_runtime"],
                "cpu_limit": run_metadata["cpu_limit"],
                "memory_limit_mb": run_metadata["memory_limit_mb"],
                "loadgen_location": run_metadata["loadgen_location"],
                "app_location": run_metadata["app_location"],
                "thread_mode": parsed.get("thread_mode", metadata["thread_mode"]),
                "db_mode": parsed.get("db_mode", metadata["db_mode"]),
                "run_class": parsed.get("run_class", metadata["run_class"]),
                "vus": int(parsed.get("vus", "0")),
                "duration": parsed.get("duration", ""),
                "http_reqs": summary_metrics["http_reqs"],
                "reqs_per_sec": summary_metrics["reqs_per_sec"],
                "avg_ms": summary_metrics["avg_ms"],
                "p90_ms": summary_metrics["p90_ms"],
                "p95_ms": summary_metrics["p95_ms"],
                "max_ms": summary_metrics["max_ms"],
                "failed_rate": summary_metrics["failed_rate"],
                "summary_file": str(summary_file),
                "source_file": str(metrics_file),
            })

    rows.sort(
        key=lambda row: (
            str(row["profile"]),
            str(row["lane"]),
            int(str(row["java_version"])),
            int(str(row["vus"])),
            str(row["scenario"]),
        )
    )
    return rows


def write_csv(rows: list[dict[str, str | int | float | None]]) -> None:
    if not rows:
        print("FAILURE: No aggregate concurrency rows found in raw concurrency data")
        sys.exit(1)

    fieldnames = [
        "java_version",
        "scenario",
        "profile",
        "lane",
        "host_os",
        "container_runtime",
        "cpu_limit",
        "memory_limit_mb",
        "loadgen_location",
        "app_location",
        "thread_mode",
        "db_mode",
        "run_class",
        "vus",
        "duration",
        "http_reqs",
        "reqs_per_sec",
        "avg_ms",
        "p90_ms",
        "p95_ms",
        "max_ms",
        "failed_rate",
        "summary_file",
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


def write_json(rows: list[dict[str, str | int | float | None]]) -> None:
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
    rows = collect_rows()
    write_csv(rows)
    write_json(rows)

    print("SUCCESS: Aggregated concurrency results")
    print(f"  Rows processed: {len(rows)}")
    print(f"  CSV output: {CSV_OUTPUT}")
    print(f"  JSON output: {JSON_OUTPUT}")


if __name__ == "__main__":
    main()
