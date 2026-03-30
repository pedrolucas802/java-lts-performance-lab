#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

from observability_common import (
    RESULTS_ROOT,
    find_project_root,
    load_json_file,
    parse_key_value_file,
    validate_results_root,
)
from result_metadata import common_run_metadata, iter_track_dirs, scenario_metadata


OUTPUT_DIR = Path("results/processed")
CSV_OUTPUT = OUTPUT_DIR / "jfr-summary.csv"
JSON_OUTPUT = OUTPUT_DIR / "jfr-summary.json"

EVENT_SUMMARY_PATTERN = re.compile(r"^\s*(jdk\.[A-Za-z0-9]+)\s+(\d+)\s+(\d+)\s*$")


def usage() -> None:
    print("Usage: python aggregate_jfr_results.py")
    print("Aggregates JFR observability results from results/raw/*/gc/*-metrics.txt")
    print("Outputs to results/processed/jfr-summary.csv and .json")


def normalize_class_name(value: str) -> str:
    return value.replace("/", ".")


def parse_jfr_summary(file_path: Path) -> dict[str, object]:
    summary: dict[str, object] = {
        "start": "",
        "duration": "",
        "event_counts": {},
    }

    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        print(f"WARNING: Failed to read JFR summary {file_path}: {exc}")
        return summary

    event_counts: dict[str, int] = {}

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Start:"):
            summary["start"] = stripped.replace("Start:", "", 1).strip()
            continue
        if stripped.startswith("Duration:"):
            summary["duration"] = stripped.replace("Duration:", "", 1).strip()
            continue

        match = EVENT_SUMMARY_PATTERN.match(line)
        if match:
            event_name, count_text, _size_text = match.groups()
            event_counts[event_name] = int(count_text)

    summary["event_counts"] = event_counts
    return summary


def pick_method_label(frames: list[dict]) -> str:
    fallback = ""
    for frame in frames:
        method = frame.get("method", {})
        owner = normalize_class_name(method.get("type", {}).get("name", ""))
        name = method.get("name", "")
        if not owner or not name:
            continue

        label = f"{owner}.{name}"
        if not fallback:
            fallback = label

        if not owner.startswith(("java.", "jdk.", "sun.", "com.sun.")):
            return label

    return fallback


def top_execution_method(file_path: Path) -> tuple[str, int]:
    data = load_json_file(file_path)
    events = data.get("recording", {}).get("events", [])
    counter: Counter[str] = Counter()

    for event in events:
        frames = event.get("values", {}).get("stackTrace", {}).get("frames", [])
        label = pick_method_label(frames)
        if label:
            counter[label] += 1

    if not counter:
        return "", 0

    label, count = counter.most_common(1)[0]
    return label, count


def top_allocation_class(file_path: Path) -> tuple[str, int]:
    data = load_json_file(file_path)
    events = data.get("recording", {}).get("events", [])
    counter: Counter[str] = Counter()

    for event in events:
        class_name = event.get("values", {}).get("objectClass", {}).get("name", "")
        if class_name:
            counter[normalize_class_name(class_name)] += 1

    if not counter:
        return "", 0

    label, count = counter.most_common(1)[0]
    return label, count


def collect_rows() -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []

    for profile, lane, java_version, gc_dir in iter_track_dirs(RESULTS_ROOT, "gc"):
        for metrics_file in sorted(gc_dir.glob("*-metrics.txt")):
            parsed = parse_key_value_file(metrics_file)
            scenario = parsed.get("scenario", "")
            metadata = scenario_metadata(scenario, "jfr", metrics_file)
            run_metadata = common_run_metadata(parsed, profile, lane)

            jfr_file = Path(parsed.get("jfr_file", ""))
            if not jfr_file.is_absolute():
                jfr_file = gc_dir / jfr_file.name

            jfr_summary_file = Path(parsed.get("jfr_summary_file", ""))
            if not jfr_summary_file.is_absolute():
                jfr_summary_file = gc_dir / jfr_summary_file.name

            jfr_execution_file = Path(parsed.get("jfr_execution_file", ""))
            if not jfr_execution_file.is_absolute():
                jfr_execution_file = gc_dir / jfr_execution_file.name

            jfr_allocation_file = Path(parsed.get("jfr_allocation_file", ""))
            if not jfr_allocation_file.is_absolute():
                jfr_allocation_file = gc_dir / jfr_allocation_file.name

            jfr_thread_file = Path(parsed.get("jfr_thread_file", ""))
            if not jfr_thread_file.is_absolute():
                jfr_thread_file = gc_dir / jfr_thread_file.name

            summary = parse_jfr_summary(jfr_summary_file)
            event_counts = summary.get("event_counts", {})
            assert isinstance(event_counts, dict)

            top_method, top_method_samples = top_execution_method(jfr_execution_file)
            top_allocation, top_allocation_samples = top_allocation_class(jfr_allocation_file)

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
                    "jfr_start": str(summary.get("start", "")),
                    "jfr_duration": str(summary.get("duration", "")),
                    "event_count_total": sum(int(count) for count in event_counts.values()),
                    "execution_sample_count": int(event_counts.get("jdk.ExecutionSample", 0)),
                    "allocation_sample_count": int(event_counts.get("jdk.ObjectAllocationSample", 0)),
                    "garbage_collection_events": int(event_counts.get("jdk.GarbageCollection", 0)),
                    "thread_park_events": int(event_counts.get("jdk.ThreadPark", 0)),
                    "virtual_thread_pinned_events": int(event_counts.get("jdk.VirtualThreadPinned", 0)),
                    "java_monitor_enter_events": int(event_counts.get("jdk.JavaMonitorEnter", 0)),
                    "java_thread_statistics_events": int(event_counts.get("jdk.JavaThreadStatistics", 0)),
                    "thread_cpu_load_events": int(event_counts.get("jdk.ThreadCPULoad", 0)),
                    "top_method": top_method,
                    "top_method_samples": top_method_samples,
                    "top_allocation_class": top_allocation,
                    "top_allocation_samples": top_allocation_samples,
                    "jfr_file": str(jfr_file),
                    "jfr_summary_file": str(jfr_summary_file),
                    "jfr_execution_file": str(jfr_execution_file),
                    "jfr_allocation_file": str(jfr_allocation_file),
                    "jfr_thread_file": str(jfr_thread_file),
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


def write_csv(rows: list[dict[str, str | int]]) -> None:
    if not rows:
        print("FAILURE: No JFR suite rows found in raw GC data")
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
        "jfr_start",
        "jfr_duration",
        "event_count_total",
        "execution_sample_count",
        "allocation_sample_count",
        "garbage_collection_events",
        "thread_park_events",
        "virtual_thread_pinned_events",
        "java_monitor_enter_events",
        "java_thread_statistics_events",
        "thread_cpu_load_events",
        "top_method",
        "top_method_samples",
        "top_allocation_class",
        "top_allocation_samples",
        "jfr_file",
        "jfr_summary_file",
        "jfr_execution_file",
        "jfr_allocation_file",
        "jfr_thread_file",
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


def write_json(rows: list[dict[str, str | int]]) -> None:
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

    print("SUCCESS: Aggregated JFR results")
    print(f"  Rows processed: {len(rows)}")
    print(f"  CSV output: {CSV_OUTPUT}")
    print(f"  JSON output: {JSON_OUTPUT}")


if __name__ == "__main__":
    main()
