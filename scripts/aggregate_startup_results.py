#!/usr/bin/env python3
import csv
import json
from pathlib import Path


RESULTS_ROOT = Path("results/raw")
OUTPUT_DIR = Path("results/processed")


def parse_key_value_file(file_path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in file_path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def collect_rows() -> list[dict]:
    rows: list[dict] = []

    for java_dir in sorted(RESULTS_ROOT.glob("java*/quarkus")):
        java_version = java_dir.parent.name.replace("java", "")

        for file_path in sorted(java_dir.glob("startup-java*.txt")):
            parsed = parse_key_value_file(file_path)

            rows.append({
                "java_version": java_version,
                "startup_ms": int(parsed.get("startup_ms", "0")),
                "port": int(parsed.get("port", "8080")),
                "log_file": parsed.get("log_file", ""),
                "source_file": str(file_path),
            })

    return rows


def write_csv(rows: list[dict], output_file: Path) -> None:
    fieldnames = ["java_version", "startup_ms", "port", "log_file", "source_file"]
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
        print("No startup result files found.")
        return

    csv_file = OUTPUT_DIR / "startup-summary.csv"
    json_file = OUTPUT_DIR / "startup-summary.json"

    write_csv(rows, csv_file)
    write_json(rows, json_file)

    print(f"Wrote {len(rows)} rows to:")
    print(f"  - {csv_file}")
    print(f"  - {json_file}")


if __name__ == "__main__":
    main()