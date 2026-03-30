from __future__ import annotations

from pathlib import Path
from typing import Iterator


PROFILE_NAMES = ("stock", "tuned")


def iter_track_dirs(results_root: Path, track: str) -> Iterator[tuple[str, str, Path]]:
    profile_roots = [
        (profile, results_root / profile)
        for profile in PROFILE_NAMES
        if (results_root / profile).exists()
    ]

    if profile_roots:
        for profile, base_dir in profile_roots:
            for track_dir in sorted(base_dir.glob(f"java*/{track}")):
                java_version = track_dir.parent.name.replace("java", "")
                yield profile, java_version, track_dir
        return

    for track_dir in sorted(results_root.glob(f"java*/{track}")):
        java_version = track_dir.parent.name.replace("java", "")
        yield "stock", java_version, track_dir


def scenario_metadata(scenario: str, run_class: str) -> dict[str, str]:
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
        "aggregate": ("platform", "synthetic"),
        "aggregate-platform": ("platform", "synthetic"),
        "aggregate-virtual": ("virtual", "synthetic"),
    }

    thread_mode, db_mode = mapping.get(scenario, ("unknown", "unknown"))
    return {
        "scenario": scenario,
        "thread_mode": thread_mode,
        "db_mode": db_mode,
        "run_class": run_class,
    }
