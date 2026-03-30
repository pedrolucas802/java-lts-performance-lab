#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from observability_common import (
    RESULTS_ROOT,
    find_project_root,
    parse_k6_summary_file,
    parse_key_value_file,
    parse_process_time_to_seconds,
    validate_results_root,
)
from result_metadata import common_run_metadata, iter_track_dirs, scenario_metadata


OUTPUT_DIR = Path("results/processed")
CSV_OUTPUT = OUTPUT_DIR / "cpu-summary.csv"
JSON_OUTPUT = OUTPUT_DIR / "cpu-summary.json"


def usage() -> None:
    print("Usage: python aggregate_cpu_results.py")
    print("Aggregates CPU timeline results from results/raw/*/gc/*-metrics.txt")
    print("Outputs to results/processed/cpu-summary.csv and .json")


def summarize_cpu_timeline(file_path: Path) -> dict[str, float | int | None]:
    summary = {
        "samples": 0,
        "elapsed_seconds": 0.0,
        "avg_cpu_percent": 0.0,
        "peak_cpu_percent": 0.0,
        "avg_rss_kb": 0.0,
        "peak_rss_kb": 0,
        "rss_delta_kb": 0,
    }

    try:
        with file_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except Exception as exc:
        print(f"WARNING: Failed to read CPU timeline {file_path}: {exc}")
        return summary

    if not rows:
        return summary

    cpu_values: list[float] = []
    rss_values: list[int] = []
    last_elapsed = 0.0

    for row in rows:
        cpu_raw = (row.get("cpu_percent") or "").strip()
        rss_raw = (row.get("rss_kb") or "").strip()
        elapsed_raw = (row.get("elapsed_seconds") or "").strip()

        if cpu_raw:
            cpu_values.append(float(cpu_raw))
        if rss_raw:
            rss_values.append(int(float(rss_raw)))
        if elapsed_raw:
            last_elapsed = float(elapsed_raw)

    summary["samples"] = len(rows)
    summary["elapsed_seconds"] = last_elapsed
    if cpu_values:
        summary["avg_cpu_percent"] = round(sum(cpu_values) / len(cpu_values), 3)
        summary["peak_cpu_percent"] = round(max(cpu_values), 3)
    if rss_values:
        summary["avg_rss_kb"] = round(sum(rss_values) / len(rss_values), 3)
        summary["peak_rss_kb"] = max(rss_values)
        summary["rss_delta_kb"] = rss_values[-1] - rss_values[0]

    return summary


def collect_rows() -> list[dict[str, str | int | float | None]]:
    rows: list[dict[str, str | int | float | None]] = []

    for profile, lane, java_version, gc_dir in iter_track_dirs(RESULTS_ROOT, "gc"):
        for metrics_file in sorted(gc_dir.glob("*-metrics.txt")):
            parsed = parse_key_value_file(metrics_file)
            scenario = parsed.get("scenario", "")
            metadata = scenario_metadata(scenario, "cpu", metrics_file)
            run_metadata = common_run_metadata(parsed, profile, lane)

            cpu_timeline_file = Path(parsed.get("cpu_timeline_file", ""))
            if not cpu_timeline_file.is_absolute():
                cpu_timeline_file = gc_dir / cpu_timeline_file.name

            summary_file = Path(parsed.get("summary_file", ""))
            if not summary_file.is_absolute():
                summary_file = gc_dir / summary_file.name

            cpu_metrics = summarize_cpu_timeline(cpu_timeline_file)
            http_metrics = parse_k6_summary_file(summary_file) if summary_file.exists() else {}

            start_cpu_time = parse_process_time_to_seconds(parsed.get("start_cpu_time", ""))
            end_cpu_time = parse_process_time_to_seconds(parsed.get("end_cpu_time", ""))
            cpu_seconds = None
            if start_cpu_time is not None and end_cpu_time is not None and end_cpu_time >= start_cpu_time:
                cpu_seconds = round(end_cpu_time - start_cpu_time, 3)
            elif cpu_metrics["samples"] and cpu_metrics["elapsed_seconds"]:
                cpu_seconds = round((float(cpu_metrics["avg_cpu_percent"]) / 100.0) * float(cpu_metrics["elapsed_seconds"]), 3)

            http_reqs = http_metrics.get("http_reqs")
            cpu_per_1k = None
            if cpu_seconds is not None and isinstance(http_reqs, int) and http_reqs > 0:
                cpu_per_1k = round((cpu_seconds / http_reqs) * 1000, 6)

            rows.append(
                {
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
                    "thread_mode": metadata["thread_mode"],
                    "db_mode": metadata["db_mode"],
                    "run_class": metadata["run_class"],
                    "duration": parsed.get("duration", ""),
                    "vus": int(parsed.get("vus", "0")),
                    "samples": cpu_metrics["samples"],
                    "elapsed_seconds": cpu_metrics["elapsed_seconds"],
                    "cpu_seconds": cpu_seconds,
                    "cpu_seconds_per_1k_requests": cpu_per_1k,
                    "avg_cpu_percent": cpu_metrics["avg_cpu_percent"],
                    "peak_cpu_percent": cpu_metrics["peak_cpu_percent"],
                    "avg_rss_kb": cpu_metrics["avg_rss_kb"],
                    "peak_rss_kb": cpu_metrics["peak_rss_kb"],
                    "rss_delta_kb": cpu_metrics["rss_delta_kb"],
                    "http_reqs": http_reqs,
                    "reqs_per_sec": http_metrics.get("reqs_per_sec"),
                    "failed_rate": http_metrics.get("failed_rate"),
                    "cpu_timeline_file": str(cpu_timeline_file),
                    "summary_file": str(summary_file),
                    "source_file": str(metrics_file),
                }
            )

    rows.sort(
        key=lambda row: (
            str(row["profile"]),
            str(row["lane"]),
            int(str(row["java_version"])),
            str(row["scenario"]),
        )
    )
    return rows


def write_csv(rows: list[dict[str, str | int | float | None]]) -> None:
    if not rows:
        print("FAILURE: No CPU suite rows found in raw GC data")
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
        "duration",
        "vus",
        "samples",
        "elapsed_seconds",
        "cpu_seconds",
        "cpu_seconds_per_1k_requests",
        "avg_cpu_percent",
        "peak_cpu_percent",
        "avg_rss_kb",
        "peak_rss_kb",
        "rss_delta_kb",
        "http_reqs",
        "reqs_per_sec",
        "failed_rate",
        "cpu_timeline_file",
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

    print("SUCCESS: Aggregated CPU results")
    print(f"  Rows processed: {len(rows)}")
    print(f"  CSV output: {CSV_OUTPUT}")
    print(f"  JSON output: {JSON_OUTPUT}")


if __name__ == "__main__":
    main()
