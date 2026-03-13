#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import re
from pathlib import Path


RESULTS_ROOT = Path("results/raw")
OUTPUT_DIR = Path("results/processed")


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
    text = file_path.read_text(encoding="utf-8")

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
            rows.append(row)

    return rows


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

    with output_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(rows: list[dict], output_file: Path) -> None:
    output_file.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = collect_rows()

    if not rows:
        print("No Quarkus summary files found under results/raw/*/quarkus/*-summary.txt")
        return

    csv_file = OUTPUT_DIR / "quarkus-summary.csv"
    json_file = OUTPUT_DIR / "quarkus-summary.json"

    write_csv(rows, csv_file)
    write_json(rows, json_file)

    print(f"Wrote {len(rows)} rows to:")
    print(f"  - {csv_file}")
    print(f"  - {json_file}")


if __name__ == "__main__":
    main()