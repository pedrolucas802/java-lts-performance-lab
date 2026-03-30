from __future__ import annotations

import json
import re
from pathlib import Path


RESULTS_ROOT = Path("results/raw")


def find_project_root() -> Path:
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / "pom.xml").exists():
            return parent
    return current


def validate_results_root() -> bool:
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


def parse_k6_summary_file(file_path: Path) -> dict[str, float | int | None]:
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


def parse_process_time_to_seconds(value: str) -> float | None:
    raw = value.strip()
    if not raw:
        return None

    days = 0
    time_part = raw
    if "-" in raw:
        day_text, time_part = raw.split("-", 1)
        try:
            days = int(day_text)
        except ValueError:
            return None

    parts = time_part.split(":")
    try:
        numeric_parts = [float(part) for part in parts]
    except ValueError:
        return None

    if len(numeric_parts) == 2:
        hours = 0.0
        minutes, seconds = numeric_parts
    elif len(numeric_parts) == 3:
        hours, minutes, seconds = numeric_parts
    else:
        return None

    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def load_json_file(file_path: Path) -> dict:
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"WARNING: Failed to parse JSON {file_path}: {exc}")
        return {}
