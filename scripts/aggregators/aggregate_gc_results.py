#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

from observability_common import (
    RESULTS_ROOT,
    find_project_root,
    parse_k6_summary_file,
    parse_key_value_file,
    validate_results_root,
)
from result_metadata import iter_track_dirs, scenario_metadata


OUTPUT_DIR = Path("results/processed")
CSV_OUTPUT = OUTPUT_DIR / "gc-summary.csv"
JSON_OUTPUT = OUTPUT_DIR / "gc-summary.json"

PAUSE_PATTERN = re.compile(r"GC\(\d+\).*?Pause.*?(\d+(?:\.\d+)?)ms$")
HEAP_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)([KMG])->(\d+(?:\.\d+)?)([KMG])\((\d+(?:\.\d+)?)([KMG])\)"
)
SAFEPOINT_PATTERN = re.compile(r"Total:\s+(\d+)\s+ns")


def usage() -> None:
    print("Usage: python aggregate_gc_results.py")
    print("Aggregates structured GC suite results from results/raw/*/gc/*-metrics.txt")
    print("Outputs to results/processed/gc-summary.csv and .json")


def to_mb(value_text: str, unit: str) -> float:
    value = float(value_text)
    unit_scale = {"K": 1 / 1024, "M": 1.0, "G": 1024.0}
    return value * unit_scale[unit]


def parse_gc_log(file_path: Path) -> dict[str, float | int]:
    summary = {
        "gc_pause_count": 0,
        "young_gc_count": 0,
        "full_gc_count": 0,
        "total_pause_ms": 0.0,
        "max_pause_ms": 0.0,
        "avg_pause_ms": 0.0,
        "safepoint_count": 0,
        "total_safepoint_ms": 0.0,
        "max_heap_before_mb": 0.0,
        "max_heap_after_mb": 0.0,
        "max_heap_capacity_mb": 0.0,
    }

    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        print(f"WARNING: Failed to read GC log {file_path}: {exc}")
        return summary

    for line in lines:
        pause_match = PAUSE_PATTERN.search(line)
        if pause_match:
            pause_ms = float(pause_match.group(1))
            summary["gc_pause_count"] += 1
            summary["total_pause_ms"] += pause_ms
            summary["max_pause_ms"] = max(summary["max_pause_ms"], pause_ms)

            if "Pause Young" in line:
                summary["young_gc_count"] += 1
            if "Pause Full" in line:
                summary["full_gc_count"] += 1

            heap_match = HEAP_PATTERN.search(line)
            if heap_match:
                before_value, before_unit, after_value, after_unit, capacity_value, capacity_unit = heap_match.groups()
                summary["max_heap_before_mb"] = max(
                    summary["max_heap_before_mb"],
                    to_mb(before_value, before_unit),
                )
                summary["max_heap_after_mb"] = max(
                    summary["max_heap_after_mb"],
                    to_mb(after_value, after_unit),
                )
                summary["max_heap_capacity_mb"] = max(
                    summary["max_heap_capacity_mb"],
                    to_mb(capacity_value, capacity_unit),
                )
            continue

        if "[safepoint" in line and "Total:" in line:
            safepoint_match = SAFEPOINT_PATTERN.search(line)
            if safepoint_match:
                total_ns = int(safepoint_match.group(1))
                summary["safepoint_count"] += 1
                summary["total_safepoint_ms"] += total_ns / 1_000_000

    if summary["gc_pause_count"]:
        summary["avg_pause_ms"] = summary["total_pause_ms"] / summary["gc_pause_count"]

    return summary


def collect_rows() -> list[dict[str, str | int | float | None]]:
    rows: list[dict[str, str | int | float | None]] = []

    for profile, java_version, gc_dir in iter_track_dirs(RESULTS_ROOT, "gc"):
        for metrics_file in sorted(gc_dir.glob("*-metrics.txt")):
            parsed = parse_key_value_file(metrics_file)
            scenario = parsed.get("scenario", "")
            metadata = scenario_metadata(scenario, "gc", metrics_file)

            gc_log_file = Path(parsed.get("gc_log_file", ""))
            if not gc_log_file.is_absolute():
                gc_log_file = gc_dir / gc_log_file.name

            summary_file = Path(parsed.get("summary_file", ""))
            if not summary_file.is_absolute():
                summary_file = gc_dir / summary_file.name

            gc_metrics = parse_gc_log(gc_log_file)
            http_metrics = parse_k6_summary_file(summary_file) if summary_file.exists() else {}

            rows.append(
                {
                    "java_version": java_version,
                    "scenario": metadata["scenario"],
                    "profile": parsed.get("profile", profile),
                    "thread_mode": metadata["thread_mode"],
                    "db_mode": metadata["db_mode"],
                    "run_class": metadata["run_class"],
                    "duration": parsed.get("duration", ""),
                    "vus": int(parsed.get("vus", "0")),
                    "http_reqs": http_metrics.get("http_reqs"),
                    "reqs_per_sec": http_metrics.get("reqs_per_sec"),
                    "failed_rate": http_metrics.get("failed_rate"),
                    "gc_pause_count": gc_metrics["gc_pause_count"],
                    "young_gc_count": gc_metrics["young_gc_count"],
                    "full_gc_count": gc_metrics["full_gc_count"],
                    "total_pause_ms": round(float(gc_metrics["total_pause_ms"]), 3),
                    "avg_pause_ms": round(float(gc_metrics["avg_pause_ms"]), 3),
                    "max_pause_ms": round(float(gc_metrics["max_pause_ms"]), 3),
                    "safepoint_count": gc_metrics["safepoint_count"],
                    "total_safepoint_ms": round(float(gc_metrics["total_safepoint_ms"]), 3),
                    "max_heap_before_mb": round(float(gc_metrics["max_heap_before_mb"]), 3),
                    "max_heap_after_mb": round(float(gc_metrics["max_heap_after_mb"]), 3),
                    "max_heap_capacity_mb": round(float(gc_metrics["max_heap_capacity_mb"]), 3),
                    "gc_log_file": str(gc_log_file),
                    "summary_file": str(summary_file),
                    "source_file": str(metrics_file),
                }
            )

    rows.sort(
        key=lambda row: (
            str(row["profile"]),
            int(str(row["java_version"])),
            str(row["scenario"]),
        )
    )
    return rows


def write_csv(rows: list[dict[str, str | int | float | None]]) -> None:
    if not rows:
        print("FAILURE: No GC suite rows found in raw GC data")
        sys.exit(1)

    fieldnames = [
        "java_version",
        "scenario",
        "profile",
        "thread_mode",
        "db_mode",
        "run_class",
        "duration",
        "vus",
        "http_reqs",
        "reqs_per_sec",
        "failed_rate",
        "gc_pause_count",
        "young_gc_count",
        "full_gc_count",
        "total_pause_ms",
        "avg_pause_ms",
        "max_pause_ms",
        "safepoint_count",
        "total_safepoint_ms",
        "max_heap_before_mb",
        "max_heap_after_mb",
        "max_heap_capacity_mb",
        "gc_log_file",
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

    if not validate_results_root():
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = collect_rows()
    write_csv(rows)
    write_json(rows)

    print("SUCCESS: Aggregated GC results")
    print(f"  Rows processed: {len(rows)}")
    print(f"  CSV output: {CSV_OUTPUT}")
    print(f"  JSON output: {JSON_OUTPUT}")


if __name__ == "__main__":
    main()
