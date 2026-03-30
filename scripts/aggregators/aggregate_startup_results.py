#!/usr/bin/env python3
import csv
import json
import sys
from pathlib import Path

from result_metadata import iter_track_dirs, scenario_metadata


# Constants
RESULTS_ROOT = Path("results/raw")
OUTPUT_DIR = Path("results/processed")
CSV_OUTPUT = OUTPUT_DIR / "startup-summary.csv"
JSON_OUTPUT = OUTPUT_DIR / "startup-summary.json"


def usage() -> None:
    """Print usage information."""
    print("Usage: python aggregate_startup_results.py")
    print("Aggregates startup benchmark results from results/raw/*/quarkus/startup-java*.txt")
    print("Outputs to results/processed/startup-summary.csv and .json")


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
    """Collect all startup result rows."""
    rows: list[dict] = []

    for profile, java_version, java_dir in iter_track_dirs(RESULTS_ROOT, "quarkus"):
        for file_path in sorted(java_dir.glob("startup-java*.txt")):
            parsed = parse_key_value_file(file_path)
            metadata = scenario_metadata(parsed.get("scenario", "startup"), "startup", file_path)

            rows.append({
                "java_version": java_version,
                "scenario": metadata["scenario"],
                "profile": parsed.get("profile", profile),
                "thread_mode": metadata["thread_mode"],
                "db_mode": metadata["db_mode"],
                "run_class": metadata["run_class"],
                "run_number": int(parsed.get("run_number", "1")),
                "external_startup_ms": int(parsed.get("external_startup_ms", parsed.get("startup_ms", "0"))),
                "quarkus_startup_ms": int(parsed.get("quarkus_startup_ms", "0")) if parsed.get("quarkus_startup_ms") else None,
                "port": int(parsed.get("port", "8080")),
                "log_file": parsed.get("log_file", ""),
                "source_file": str(file_path),
            })

    return rows


def write_csv(rows: list[dict], output_file: Path) -> None:
    """Write rows to CSV file."""
    fieldnames = [
        "java_version",
        "scenario",
        "profile",
        "thread_mode",
        "db_mode",
        "run_class",
        "run_number",
        "external_startup_ms",
        "quarkus_startup_ms",
        "port",
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
    """Write rows to JSON file."""
    try:
        output_file.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"ERROR: Failed to write JSON {output_file}: {e}")
        sys.exit(1)


def main() -> None:
    """Main entry point."""
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
        print("FAILURE: No startup result files found in results/raw/*/quarkus/startup-java*.txt")
        sys.exit(1)

    write_csv(rows, CSV_OUTPUT)
    write_json(rows, JSON_OUTPUT)

    print("SUCCESS: Aggregated startup results")
    print(f"  Rows processed: {len(rows)}")
    print(f"  CSV output: {CSV_OUTPUT}")
    print(f"  JSON output: {JSON_OUTPUT}")


if __name__ == "__main__":
    main()
