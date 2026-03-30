from __future__ import annotations

from pathlib import Path
from typing import Iterator


PROFILE_NAMES = ("stock", "tuned")


def iter_track_dirs(results_root: Path, track: str) -> Iterator[tuple[str, str, Path]]:
    explicit_versions: set[tuple[str, str]] = set()

    for profile in PROFILE_NAMES:
        base_dir = results_root / profile
        if not base_dir.exists():
            continue

        for track_dir in sorted(base_dir.glob(f"java*/{track}")):
            java_version = track_dir.parent.name.replace("java", "")
            explicit_versions.add((profile, java_version))
            yield profile, java_version, track_dir

    for track_dir in sorted(results_root.glob(f"java*/{track}")):
        java_version = track_dir.parent.name.replace("java", "")
        if ("stock", java_version) in explicit_versions:
            continue
        yield "stock", java_version, track_dir


def scenario_metadata(scenario: str, run_class: str, source_file: Path | None = None) -> dict[str, str]:
    if run_class == "startup":
        return {
            "scenario": "startup",
            "thread_mode": "none",
            "db_mode": "none",
            "run_class": "startup",
        }

    mapping = {
        "products": ("request", "none"),
        "products-db": ("request", "jdbc"),
        "transform": ("request", "none"),
        "mixed-workload": ("mixed", "mixed"),
        "aggregate": ("platform", "jdbc"),
        "aggregate-platform": ("platform", "jdbc"),
        "aggregate-virtual": ("virtual", "jdbc"),
    }

    thread_mode, db_mode = mapping.get(scenario, ("unknown", "unknown"))

    if source_file is not None and scenario.startswith("aggregate"):
        source_parts = set(source_file.parts)
        if "stock" not in source_parts and "tuned" not in source_parts:
            db_mode = "synthetic"

    return {
        "scenario": scenario,
        "thread_mode": thread_mode,
        "db_mode": db_mode,
        "run_class": run_class,
    }
