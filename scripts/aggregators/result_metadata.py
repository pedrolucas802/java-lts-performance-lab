from __future__ import annotations

from pathlib import Path
from typing import Iterator


PROFILE_NAMES = ("stock",)
DEFAULT_LANE = "host"


def iter_track_dirs(results_root: Path, track: str) -> Iterator[tuple[str, str, str, Path]]:
    explicit_targets: set[tuple[str, str, str]] = set()

    for profile in PROFILE_NAMES:
        base_dir = results_root / profile
        if not base_dir.exists():
            continue

        for track_dir in sorted(base_dir.glob(f"*/java*/{track}")):
            lane = track_dir.parent.parent.name
            java_version = track_dir.parent.name.replace("java", "")
            explicit_targets.add((profile, lane, java_version))
            yield profile, lane, java_version, track_dir

        for track_dir in sorted(base_dir.glob(f"java*/{track}")):
            java_version = track_dir.parent.name.replace("java", "")
            if (profile, DEFAULT_LANE, java_version) in explicit_targets:
                continue
            explicit_targets.add((profile, DEFAULT_LANE, java_version))
            yield profile, DEFAULT_LANE, java_version, track_dir

    for track_dir in sorted(results_root.glob(f"java*/{track}")):
        java_version = track_dir.parent.name.replace("java", "")
        if ("stock", DEFAULT_LANE, java_version) in explicit_targets:
            continue
        yield "stock", DEFAULT_LANE, java_version, track_dir


def common_run_metadata(parsed: dict[str, str], profile: str, lane: str) -> dict[str, str]:
    resolved_lane = parsed.get("lane", lane or DEFAULT_LANE)
    container_default = "docker" if resolved_lane.endswith("container") else "none"
    app_location_default = "container" if resolved_lane.endswith("container") else "host"

    return {
        "profile": parsed.get("profile", profile),
        "lane": resolved_lane,
        "host_os": parsed.get("host_os", "unknown"),
        "container_runtime": parsed.get("container_runtime", container_default),
        "cpu_limit": parsed.get("cpu_limit", "unlimited"),
        "memory_limit_mb": parsed.get("memory_limit_mb", "0"),
        "loadgen_location": parsed.get("loadgen_location", "host"),
        "app_location": parsed.get("app_location", app_location_default),
    }


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
      if "stock" not in source_parts:
          db_mode = "synthetic"

    return {
        "scenario": scenario,
        "thread_mode": thread_mode,
        "db_mode": db_mode,
        "run_class": run_class,
    }
