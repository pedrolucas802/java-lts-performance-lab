#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import tomllib
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from shutil import which
from typing import Iterable, TextIO

try:
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskID,
        TextColumn,
        TimeElapsedColumn,
    )
    HAS_RICH = True
except ImportError:
    Console = None
    Progress = None
    SpinnerColumn = None
    BarColumn = None
    TextColumn = None
    TimeElapsedColumn = None
    TaskID = int
    HAS_RICH = False


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNERS_DIR = PROJECT_ROOT / "scripts" / "runners"
AGGREGATORS_DIR = PROJECT_ROOT / "scripts" / "aggregators"
CHARTS_DIR = PROJECT_ROOT / "scripts" / "charts"
LOGS_DIR = PROJECT_ROOT / "results" / "logs"
LANE_CONFIGS_DIR = PROJECT_ROOT / "config" / "benchmark-lanes"
PROFILE_NAME = "stock"

RICH_CONSOLE = Console() if HAS_RICH else None

RUN_LOGGER: "RunLogger | None" = None
RUN_TIMESTAMP: str | None = None
LIVE_PROGRESS_ACTIVE = False


@dataclass(frozen=True)
class BenchmarkLane:
    name: str
    description: str
    container_runtime: str
    cpu_limit: str
    memory_limit_mb: str
    loadgen_location: str
    app_location: str


@dataclass(frozen=True)
class BenchmarkPreset:
    name: str
    description: str
    startup_repetitions: int
    http_duration: str
    http_vus: int
    memory_duration: str
    memory_vus: int
    concurrency_duration: str
    concurrency_vus_list: str
    gc_duration: str
    gc_vus: int
    include_gc_suite: bool
    include_mixed_workload: bool
    product_count: int
    transform_item_count: int
    transform_metadata_count: int
    think_time_seconds: str
    aggregate_think_time_seconds: str


PRESETS: dict[str, BenchmarkPreset] = {
    "smoke": BenchmarkPreset(
        name="smoke",
        description="Fast validation pass for local correctness checks.",
        startup_repetitions=2,
        http_duration="15s",
        http_vus=10,
        memory_duration="15s",
        memory_vus=10,
        concurrency_duration="15s",
        concurrency_vus_list="2,10,25",
        gc_duration="15s",
        gc_vus=8,
        include_gc_suite=False,
        include_mixed_workload=False,
        product_count=150,
        transform_item_count=10,
        transform_metadata_count=6,
        think_time_seconds="0.08",
        aggregate_think_time_seconds="0.05",
    ),
    "full-lab": BenchmarkPreset(
        name="full-lab",
        description="Publication-grade stock run with heavier request shapes and longer durations.",
        startup_repetitions=5,
        http_duration="60s",
        http_vus=40,
        memory_duration="45s",
        memory_vus=30,
        concurrency_duration="30s",
        concurrency_vus_list="5,25,50,100",
        gc_duration="30s",
        gc_vus=20,
        include_gc_suite=True,
        include_mixed_workload=False,
        product_count=500,
        transform_item_count=24,
        transform_metadata_count=12,
        think_time_seconds="0.03",
        aggregate_think_time_seconds="0.02",
    ),
}


class RunLogger:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.handle: TextIO = self.log_path.open("w", encoding="utf-8")

    def close(self) -> None:
        try:
            self.handle.flush()
        finally:
            self.handle.close()

    def write_line(self, line: str = "") -> None:
        self.handle.write(line + "\n")
        self.handle.flush()

    def section(self, title: str) -> None:
        separator = "=" * 100
        self.write_line(separator)
        self.write_line(title)
        self.write_line(separator)


def timestamp_now() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def log_line(message: str) -> None:
    if RUN_LOGGER is not None:
        RUN_LOGGER.write_line(message)


def console(message: str, *, force: bool = False) -> None:
    if force or not LIVE_PROGRESS_ACTIVE:
        if HAS_RICH and RICH_CONSOLE is not None:
            RICH_CONSOLE.print(message)
        else:
            print(message)


def info(message: str, *, force_console: bool = False) -> None:
    line = f"[INFO] {message}"
    console(line, force=force_console)
    log_line(line)


def success(message: str, *, force_console: bool = False) -> None:
    line = f"[OK]   {message}"
    console(line, force=force_console)
    log_line(line)


def error(message: str, *, force_console: bool = False) -> None:
    line = f"[ERR]  {message}"
    console(line, force=force_console)
    log_line(line)


def note(message: str, *, force_console: bool = False) -> None:
    line = f"[NOTE] {message}"
    console(line, force=force_console)
    log_line(line)


def sanitize_message(message: str, limit: int = 72) -> str:
    clean = " ".join(message.split())
    if len(clean) > limit:
        return clean[: limit - 3] + "..."
    return clean


def resolve_java_home(version: str) -> str:
    explicit_home = os.environ.get(f"JAVA{version}_HOME")
    if explicit_home:
        return explicit_home

    if os.environ.get("JAVA_HOME"):
        current_java_home = os.environ["JAVA_HOME"]
        current_java = Path(current_java_home) / "bin" / "java"
        if current_java.exists():
            result = subprocess.run(
                [str(current_java), "-version"],
                capture_output=True,
                text=True,
                check=False,
            )
            version_text = (result.stdout or "") + "\n" + (result.stderr or "")
            if f"version \"{version}." in version_text or f" {version}" in version_text:
                return current_java_home

    if sys.platform == "darwin":
        return macos_java_home(version)

    raise RuntimeError(
        f"Could not resolve JAVA_HOME for Java {version}. "
        f"Set JAVA{version}_HOME or JAVA_HOME before running."
    )


def macos_java_home(version: str) -> str:
    result = subprocess.run(
        ["/usr/libexec/java_home", "-v", version],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Could not resolve JAVA_HOME for Java {version}: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def build_env(java_version: str) -> dict[str, str]:
    env = os.environ.copy()
    java_home = resolve_java_home(java_version)
    env["JAVA_HOME"] = java_home
    env["PATH"] = f"{java_home}/bin:{env.get('PATH', '')}"
    return env


def load_lane_config(lane_name: str) -> BenchmarkLane:
    lane_path = LANE_CONFIGS_DIR / f"{lane_name}.toml"
    if not lane_path.exists():
        raise FileNotFoundError(f"Missing lane config: {lane_path}")

    data = tomllib.loads(lane_path.read_text(encoding="utf-8"))
    return BenchmarkLane(
        name=str(data.get("lane", lane_name)),
        description=str(data.get("description", "")),
        container_runtime=str(data.get("container_runtime", "none")),
        cpu_limit=str(data.get("cpu_limit", "unlimited")),
        memory_limit_mb=str(data.get("memory_limit_mb", "0")),
        loadgen_location=str(data.get("loadgen_location", "host")),
        app_location=str(data.get("app_location", "host")),
    )


def build_runtime_env(
        java_version: str,
        lane: BenchmarkLane,
        extra_env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = build_env(java_version)
    env["BENCHMARK_PROFILE"] = PROFILE_NAME
    env["BENCHMARK_LANE"] = lane.name
    env["BENCHMARK_RESULTS_ROOT"] = str(PROJECT_ROOT / "results" / "raw" / PROFILE_NAME / lane.name)
    env["BENCHMARK_CONTAINER_RUNTIME"] = lane.container_runtime
    env["BENCHMARK_CPU_LIMIT"] = lane.cpu_limit
    env["BENCHMARK_MEMORY_LIMIT_MB"] = lane.memory_limit_mb
    env["BENCHMARK_LOADGEN_LOCATION"] = lane.loadgen_location
    env["BENCHMARK_APP_LOCATION"] = lane.app_location
    env["BENCHMARK_HOST_OS"] = sys.platform
    env["BENCHMARK_JAVA_VERSION"] = java_version
    env["APP_JVM_OPTS"] = env.get("APP_JVM_OPTS", "")
    if extra_env:
        env.update(extra_env)
    return env


def resolve_setting(value, preset_value):
    if value is None:
        return preset_value
    return value


def summarize_output(text: str, *, max_lines: int = 8) -> list[str]:
    interesting_prefixes = (
        "SUCCESS:",
        "ERROR:",
        "INFO:",
        "Benchmark result is saved to",
        "Chart written to",
        "CSV output:",
        "JSON output:",
        "Rows processed:",
        "Processed rows:",
        "Throughput chart:",
        "Latency chart:",
        "Failure rate chart:",
    )

    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    selected: list[str] = []

    for line in lines:
        if line.startswith(interesting_prefixes):
            selected.append(line)

    if not selected:
        selected = lines[-max_lines:]

    if len(selected) > max_lines:
        selected = selected[-max_lines:]

    return selected


def set_progress_message(
        progress: Progress | None,
        task_id: TaskID | None,
        completed: int,
        total: int,
        message: str,
) -> None:
    if progress is None or task_id is None:
        return
    progress.update(
        task_id,
        completed=completed,
        total=total,
        description=sanitize_message(message),
    )


def advance_progress(
        progress: Progress | None,
        task_id: TaskID | None,
        completed: int,
        total: int,
        message: str,
) -> None:
    if progress is None or task_id is None:
        return
    progress.update(
        task_id,
        completed=completed,
        total=total,
        description=sanitize_message(message),
    )


def run_command(
        cmd: list[str],
        *,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
        check: bool = True,
        label: str | None = None,
        progress: Progress | None = None,
        task_id: TaskID | None = None,
        completed_tasks: int = 0,
        total_tasks: int = 0,
) -> subprocess.CompletedProcess[str]:
    command_str = " ".join(cmd)

    if label:
        set_progress_message(progress, task_id, completed_tasks, total_tasks, label)

    info(f"Running: {command_str}")

    if label:
        note(label)

    started = time.time()
    started_at = datetime.now().isoformat()

    result = subprocess.run(
        cmd,
        cwd=str(cwd or PROJECT_ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    duration = time.time() - started

    if RUN_LOGGER is not None:
        RUN_LOGGER.section(f"COMMAND: {command_str}")
        RUN_LOGGER.write_line(f"Started at: {started_at}")
        RUN_LOGGER.write_line(f"Finished at: {datetime.now().isoformat()}")
        RUN_LOGGER.write_line(f"Duration seconds: {duration:.2f}")
        RUN_LOGGER.write_line(f"Return code: {result.returncode}")
        RUN_LOGGER.write_line("--- STDOUT ---")
        if result.stdout:
            RUN_LOGGER.write_line(result.stdout.rstrip())
        RUN_LOGGER.write_line("--- STDERR ---")
        if result.stderr:
            RUN_LOGGER.write_line(result.stderr.rstrip())
        RUN_LOGGER.write_line()

    summary_lines = summarize_output((result.stdout or "") + "\n" + (result.stderr or ""))
    for line in summary_lines:
        note(line)

    info(f"Finished in {duration:.2f}s with exit code {result.returncode}")

    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {command_str}")

    return result


def validate_tools(*, include_gc: bool, lane: str) -> None:
    required = ["bash", "python3", "mvn", "k6"]
    if include_gc:
        required.append("jfr")
    if lane.endswith("container"):
        required.append("docker")
    missing = [tool for tool in required if which(tool) is None]
    if missing:
        raise RuntimeError(f"Missing required tools: {', '.join(missing)}")


def scenarios_for_version(java_version: str, include_mixed_workload: bool) -> tuple[list[str], list[str]]:
    http = ["products", "products-db", "transform", "aggregate-platform"]
    memory = ["products", "products-db", "transform", "aggregate-platform"]

    if java_version in {"21", "25"}:
        http.append("aggregate-virtual")
        memory.append("aggregate-virtual")

    if include_mixed_workload:
        http.append("mixed-workload")

    return http, memory


def task_plan(versions: Iterable[str], *, include_gc: bool, skip_jmh: bool) -> list[str]:
    tasks: list[str] = []
    for version in versions:
        if not skip_jmh:
            tasks.append(f"JMH Java {version}")
        tasks.append(f"Startup Java {version}")
        tasks.append(f"HTTP suite Java {version}")
        tasks.append(f"Concurrency study Java {version}")
        tasks.append(f"Memory suite Java {version}")
        if include_gc:
            tasks.append(f"GC suite Java {version}")

    tasks.extend(
        [
            "Aggregate startup results",
            "Aggregate HTTP results",
            "Aggregate concurrency results",
            "Aggregate memory results",
        ]
    )

    if include_gc:
        tasks.extend(
            [
                "Aggregate GC results",
                "Aggregate CPU results",
                "Aggregate JFR results",
            ]
        )

    tasks.extend(
        [
            "Generate startup chart",
            "Generate Quarkus charts",
            "Generate concurrency charts",
        ]
    )

    if include_gc:
        tasks.extend(
            [
                "Generate GC charts",
                "Generate CPU charts",
            ]
        )
    return tasks


def create_run_logger() -> tuple[RunLogger, str, Path]:
    run_timestamp = timestamp_now()
    log_path = LOGS_DIR / f"full-benchmark-run-{run_timestamp}.log"
    logger = RunLogger(log_path)
    logger.section("JAVA LTS PERFORMANCE LAB RUN")
    logger.write_line(f"Run timestamp: {run_timestamp}")
    logger.write_line(f"Project root: {PROJECT_ROOT}")
    logger.write_line(f"Python: {sys.executable}")
    logger.write_line()
    return logger, run_timestamp, log_path


def default_lane_name() -> str:
    return "macos-container" if sys.platform == "darwin" else "linux-container"


def main() -> int:
    global RUN_LOGGER, RUN_TIMESTAMP, LIVE_PROGRESS_ACTIVE

    parser = argparse.ArgumentParser(
        description="Run the full Java LTS benchmark lab end-to-end."
    )
    parser.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        default="full-lab",
        help="Execution preset. Default: full-lab",
    )
    parser.add_argument(
        "--versions",
        nargs="+",
        default=["17", "21", "25"],
        help="Java versions to benchmark. Default: 17 21 25",
    )
    parser.add_argument(
        "--startup-repetitions",
        type=int,
        default=None,
        help="Number of startup repetitions per Java version. Default: preset-driven",
    )
    parser.add_argument(
        "--http-duration",
        default=None,
        help="HTTP benchmark duration. Default: preset-driven",
    )
    parser.add_argument(
        "--http-vus",
        type=int,
        default=None,
        help="HTTP benchmark virtual users. Default: preset-driven",
    )
    parser.add_argument(
        "--memory-duration",
        default=None,
        help="Memory benchmark duration. Default: preset-driven",
    )
    parser.add_argument(
        "--memory-vus",
        type=int,
        default=None,
        help="Memory benchmark virtual users. Default: preset-driven",
    )
    parser.add_argument(
        "--concurrency-duration",
        default=None,
        help="Concurrency ramp duration per VU level. Default: preset-driven",
    )
    parser.add_argument(
        "--concurrency-vus-list",
        default=None,
        help="Comma-separated VU ramp list for the concurrency study. Default: preset-driven",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for startup and HTTP benchmarks. Default: 8080",
    )
    parser.add_argument(
        "--memory-port",
        type=int,
        default=8081,
        help="Port for memory benchmarks. Default: 8081",
    )
    parser.add_argument(
        "--heap-info",
        action="store_true",
        help="Enable heap monitoring for memory benchmarks.",
    )
    parser.add_argument(
        "--with-gc-suite",
        "--with-observability-suite",
        dest="with_gc_suite",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Also run the GC/JFR/CPU observability suite for each Java version. Default: preset-driven",
    )
    parser.add_argument(
        "--gc-duration",
        default=None,
        help="Observability suite duration per scenario. Default: preset-driven",
    )
    parser.add_argument(
        "--gc-vus",
        type=int,
        default=None,
        help="Observability suite virtual users per scenario. Default: preset-driven",
    )
    parser.add_argument(
        "--gc-port",
        type=int,
        default=8082,
        help="Port for the GC/JFR/CPU observability suite. Default: 8082",
    )
    parser.add_argument(
        "--skip-jmh",
        action="store_true",
        help="Skip the JMH suite and only run Quarkus app benchmarks.",
    )
    parser.add_argument(
        "--lane",
        choices=["macos-container", "linux-container"],
        default=default_lane_name(),
        help="Execution lane for app-based runs. Default is macos-container on macOS and linux-container elsewhere.",
    )
    parser.add_argument(
        "--product-count",
        type=int,
        default=None,
        help="Requested product count for products/products-db scenarios. Default: preset-driven",
    )
    parser.add_argument(
        "--transform-item-count",
        type=int,
        default=None,
        help="Number of items in transform requests. Default: preset-driven",
    )
    parser.add_argument(
        "--transform-metadata-count",
        type=int,
        default=None,
        help="Number of metadata keys in transform requests. Default: preset-driven",
    )
    parser.add_argument(
        "--think-time-seconds",
        default=None,
        help="Client think time for products/products-db/transform/mixed scenarios. Default: preset-driven",
    )
    parser.add_argument(
        "--aggregate-think-time-seconds",
        default=None,
        help="Client think time for aggregate scenarios. Default: preset-driven",
    )
    parser.add_argument(
        "--include-mixed-workload",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Also run the weighted mixed-workload HTTP scenario. Default: preset-driven",
    )
    args = parser.parse_args()

    logger, run_timestamp, log_path = create_run_logger()
    RUN_LOGGER = logger
    RUN_TIMESTAMP = run_timestamp

    preset = PRESETS[args.preset]
    startup_repetitions = resolve_setting(args.startup_repetitions, preset.startup_repetitions)
    http_duration = resolve_setting(args.http_duration, preset.http_duration)
    http_vus = resolve_setting(args.http_vus, preset.http_vus)
    memory_duration = resolve_setting(args.memory_duration, preset.memory_duration)
    memory_vus = resolve_setting(args.memory_vus, preset.memory_vus)
    concurrency_duration = resolve_setting(args.concurrency_duration, preset.concurrency_duration)
    concurrency_vus_list = resolve_setting(args.concurrency_vus_list, preset.concurrency_vus_list)
    with_gc_suite = resolve_setting(args.with_gc_suite, preset.include_gc_suite)
    gc_duration = resolve_setting(args.gc_duration, preset.gc_duration)
    gc_vus = resolve_setting(args.gc_vus, preset.gc_vus)
    include_mixed_workload = resolve_setting(args.include_mixed_workload, preset.include_mixed_workload)
    product_count = resolve_setting(args.product_count, preset.product_count)
    transform_item_count = resolve_setting(args.transform_item_count, preset.transform_item_count)
    transform_metadata_count = resolve_setting(
        args.transform_metadata_count,
        preset.transform_metadata_count,
    )
    think_time_seconds = resolve_setting(args.think_time_seconds, preset.think_time_seconds)
    aggregate_think_time_seconds = resolve_setting(
        args.aggregate_think_time_seconds,
        preset.aggregate_think_time_seconds,
    )

    try:
        info(f"Run log file: {log_path}", force_console=True)
        validate_tools(include_gc=with_gc_suite, lane=args.lane)

        versions = [str(v) for v in args.versions]
        for version in versions:
            if version not in {"17", "21", "25"}:
                raise RuntimeError(f"Unsupported Java version: {version}")
        if product_count < 1:
            raise RuntimeError("Product count must be a positive integer.")
        if transform_item_count < 1:
            raise RuntimeError("Transform item count must be a positive integer.")
        if transform_metadata_count < 1:
            raise RuntimeError("Transform metadata count must be a positive integer.")

        lane = load_lane_config(args.lane)

        all_tasks = task_plan(
            versions,
            include_gc=with_gc_suite,
            skip_jmh=args.skip_jmh,
        )
        total_tasks = len(all_tasks)
        completed_tasks = 0

        logger.section("RUN CONFIGURATION")
        logger.write_line(f"Preset: {preset.name}")
        logger.write_line(f"Preset description: {preset.description}")
        logger.write_line(f"Versions: {', '.join(versions)}")
        logger.write_line(f"Lane: {lane.name}")
        logger.write_line(f"Lane description: {lane.description}")
        logger.write_line(f"Startup repetitions: {startup_repetitions}")
        logger.write_line(f"HTTP duration: {http_duration}")
        logger.write_line(f"HTTP VUs: {http_vus}")
        logger.write_line(f"Concurrency duration: {concurrency_duration}")
        logger.write_line(f"Concurrency VU ramp: {concurrency_vus_list}")
        logger.write_line(f"Memory duration: {memory_duration}")
        logger.write_line(f"Memory VUs: {memory_vus}")
        logger.write_line(f"Port: {args.port}")
        logger.write_line(f"Memory port: {args.memory_port}")
        logger.write_line(f"Heap info: {args.heap_info}")
        logger.write_line(f"With GC suite: {with_gc_suite}")
        logger.write_line(f"GC duration: {gc_duration}")
        logger.write_line(f"GC VUs: {gc_vus}")
        logger.write_line(f"GC port: {args.gc_port}")
        logger.write_line(f"Skip JMH: {args.skip_jmh}")
        logger.write_line(f"Include mixed workload: {include_mixed_workload}")
        logger.write_line(f"Product count: {product_count}")
        logger.write_line(f"Transform item count: {transform_item_count}")
        logger.write_line(f"Transform metadata count: {transform_metadata_count}")
        logger.write_line(f"Think time seconds: {think_time_seconds}")
        logger.write_line(f"Aggregate think time seconds: {aggregate_think_time_seconds}")
        logger.write_line()

        note(f"Planned tasks: {total_tasks}", force_console=True)
        note(f"Preset '{preset.name}': {preset.description}", force_console=True)

        progress_context = (
            Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=32),
                TextColumn("{task.completed}/{task.total}"),
                TextColumn("({task.percentage:>5.1f}%)"),
                TimeElapsedColumn(),
                console=RICH_CONSOLE,
                transient=False,
            )
            if HAS_RICH and Progress is not None
            else nullcontext(None)
        )

        with progress_context as progress:
            LIVE_PROGRESS_ACTIVE = progress is not None

            task_id = (
                progress.add_task(
                    description="Initializing benchmark lab",
                    total=total_tasks,
                    completed=0,
                )
                if progress is not None
                else None
            )

            def step(task_label: str) -> None:
                nonlocal completed_tasks
                completed_tasks += 1
                advance_progress(
                    progress,
                    task_id,
                    completed_tasks,
                    total_tasks,
                    task_label,
                )

            for version_index, version in enumerate(versions, start=1):
                workload_env = {
                    "PRODUCT_COUNT": str(product_count),
                    "TRANSFORM_ITEM_COUNT": str(transform_item_count),
                    "TRANSFORM_METADATA_COUNT": str(transform_metadata_count),
                    "THINK_TIME_SECONDS": think_time_seconds,
                    "AGGREGATE_THINK_TIME_SECONDS": aggregate_think_time_seconds,
                }
                runtime_env = build_runtime_env(version, lane, workload_env)
                http_scenarios, memory_scenarios = scenarios_for_version(version, include_mixed_workload)
                version_label = f"Java {version} ({version_index}/{len(versions)})"

                requires_database = any(
                    scenario in {"products-db", "mixed-workload", "aggregate-platform", "aggregate-virtual"}
                    for scenario in (*http_scenarios, *memory_scenarios)
                )
                if requires_database and not runtime_env.get("BENCHMARK_DATASOURCE_URL"):
                    raise RuntimeError(
                        f"Java {version} requires BENCHMARK_DATASOURCE_URL for DB-backed scenarios."
                    )

                prep_message = f"{version_label}: preparing benchmark flow"
                set_progress_message(progress, task_id, completed_tasks, total_tasks, prep_message)
                note(prep_message)

                if not args.skip_jmh:
                    run_command(
                        ["bash", str(RUNNERS_DIR / "run_jmh_suite.sh"), version],
                        env=runtime_env,
                        label=f"{version_label}: JMH microbenchmarks",
                        progress=progress,
                        task_id=task_id,
                        completed_tasks=completed_tasks,
                        total_tasks=total_tasks,
                    )
                    step(f"{version_label}: JMH")

                startup_env = build_runtime_env(
                    version,
                    lane,
                    workload_env | {"PORT": str(args.port)},
                )
                run_command(
                    [
                        "bash",
                        str(RUNNERS_DIR / "run_quarkus_startup_benchmark.sh"),
                        version,
                        str(startup_repetitions),
                    ],
                    env=startup_env,
                    label=f"{version_label}: startup benchmark",
                    progress=progress,
                    task_id=task_id,
                    completed_tasks=completed_tasks,
                    total_tasks=total_tasks,
                )
                step(f"{version_label}: startup")

                run_command(
                    [
                        "bash",
                        str(RUNNERS_DIR / "run_quarkus_suite.sh"),
                        version,
                        http_duration,
                        str(http_vus),
                        ",".join(http_scenarios),
                    ],
                    env=build_runtime_env(version, lane, workload_env | {"PORT": str(args.port)}),
                    label=f"{version_label}: HTTP suite on {lane.name}",
                    progress=progress,
                    task_id=task_id,
                    completed_tasks=completed_tasks,
                    total_tasks=total_tasks,
                )

                step(f"{version_label}: HTTP suite")

                run_command(
                    [
                        "bash",
                        str(RUNNERS_DIR / "run_concurrency_study.sh"),
                        version,
                        concurrency_duration,
                        concurrency_vus_list,
                    ],
                    env=build_runtime_env(version, lane, workload_env | {"PORT": str(args.port)}),
                    label=f"{version_label}: concurrency study",
                    progress=progress,
                    task_id=task_id,
                    completed_tasks=completed_tasks,
                    total_tasks=total_tasks,
                )
                step(f"{version_label}: concurrency study")

                for scenario in memory_scenarios:
                    mem_env = build_runtime_env(
                        version,
                        lane,
                        workload_env
                        | {
                            "PORT": str(args.memory_port),
                            "DURATION": memory_duration,
                            "VUS": str(memory_vus),
                        },
                    )
                    if args.heap_info:
                        mem_env["HEAP_INFO"] = "true"

                    run_command(
                        [
                            "bash",
                            str(RUNNERS_DIR / "run_quarkus_memory_benchmark.sh"),
                            version,
                            scenario,
                        ],
                        env=mem_env,
                        label=f"{version_label}: memory {scenario}",
                        progress=progress,
                        task_id=task_id,
                        completed_tasks=completed_tasks,
                        total_tasks=total_tasks,
                    )

                step(f"{version_label}: memory suite")

                if with_gc_suite:
                    run_command(
                        [
                            "bash",
                            str(RUNNERS_DIR / "run_gc_suite.sh"),
                            version,
                            gc_duration,
                            str(gc_vus),
                        ],
                        env=build_runtime_env(version, lane, workload_env | {"PORT": str(args.gc_port)}),
                        label=f"{version_label}: GC/JFR/CPU suite",
                        progress=progress,
                        task_id=task_id,
                        completed_tasks=completed_tasks,
                        total_tasks=total_tasks,
                    )
                    step(f"{version_label}: GC suite")

            run_command(
                ["python3", str(AGGREGATORS_DIR / "aggregate_startup_results.py")],
                label="Aggregating startup results",
                progress=progress,
                task_id=task_id,
                completed_tasks=completed_tasks,
                total_tasks=total_tasks,
            )
            step("Aggregate startup results")

            run_command(
                ["python3", str(AGGREGATORS_DIR / "aggregate_quarkus_results.py")],
                label="Aggregating HTTP results",
                progress=progress,
                task_id=task_id,
                completed_tasks=completed_tasks,
                total_tasks=total_tasks,
            )
            step("Aggregate HTTP results")

            run_command(
                ["python3", str(AGGREGATORS_DIR / "aggregate_concurrency_results.py")],
                label="Aggregating concurrency results",
                progress=progress,
                task_id=task_id,
                completed_tasks=completed_tasks,
                total_tasks=total_tasks,
            )
            step("Aggregate concurrency results")

            run_command(
                ["python3", str(AGGREGATORS_DIR / "aggregate_memory_results.py")],
                label="Aggregating memory results",
                progress=progress,
                task_id=task_id,
                completed_tasks=completed_tasks,
                total_tasks=total_tasks,
            )
            step("Aggregate memory results")

            if with_gc_suite:
                run_command(
                    ["python3", str(AGGREGATORS_DIR / "aggregate_gc_results.py")],
                    label="Aggregating GC results",
                    progress=progress,
                    task_id=task_id,
                    completed_tasks=completed_tasks,
                    total_tasks=total_tasks,
                )
                step("Aggregate GC results")

                run_command(
                    ["python3", str(AGGREGATORS_DIR / "aggregate_cpu_results.py")],
                    label="Aggregating CPU results",
                    progress=progress,
                    task_id=task_id,
                    completed_tasks=completed_tasks,
                    total_tasks=total_tasks,
                )
                step("Aggregate CPU results")

                run_command(
                    ["python3", str(AGGREGATORS_DIR / "aggregate_jfr_results.py")],
                    label="Aggregating JFR results",
                    progress=progress,
                    task_id=task_id,
                    completed_tasks=completed_tasks,
                    total_tasks=total_tasks,
                )
                step("Aggregate JFR results")

            run_command(
                ["python3", str(CHARTS_DIR / "generate_startup_chart.py")],
                label="Generating startup chart",
                progress=progress,
                task_id=task_id,
                completed_tasks=completed_tasks,
                total_tasks=total_tasks,
            )
            step("Generate startup chart")

            run_command(
                ["python3", str(CHARTS_DIR / "generate_quarkus_charts.py")],
                label="Generating Quarkus charts",
                progress=progress,
                task_id=task_id,
                completed_tasks=completed_tasks,
                total_tasks=total_tasks,
            )
            step("Generate Quarkus charts")

            run_command(
                ["python3", str(CHARTS_DIR / "generate_concurrency_charts.py")],
                label="Generating concurrency charts",
                progress=progress,
                task_id=task_id,
                completed_tasks=completed_tasks,
                total_tasks=total_tasks,
            )
            step("Generate concurrency charts")

            if with_gc_suite:
                run_command(
                    ["python3", str(CHARTS_DIR / "generate_gc_charts.py")],
                    label="Generating GC charts",
                    progress=progress,
                    task_id=task_id,
                    completed_tasks=completed_tasks,
                    total_tasks=total_tasks,
                )
                step("Generate GC charts")

                run_command(
                    ["python3", str(CHARTS_DIR / "generate_cpu_charts.py")],
                    label="Generating CPU charts",
                    progress=progress,
                    task_id=task_id,
                    completed_tasks=completed_tasks,
                    total_tasks=total_tasks,
                )
                step("Generate CPU charts")

            set_progress_message(
                progress,
                task_id,
                completed_tasks,
                total_tasks,
                "Benchmark lab completed",
            )

        LIVE_PROGRESS_ACTIVE = False

        success("Full benchmark lab completed successfully.", force_console=True)
        success(
            f"Processed results: {PROJECT_ROOT / 'results' / 'processed'}",
            force_console=True,
        )
        success(
            f"Charts: {PROJECT_ROOT / 'results' / 'charts'}",
            force_console=True,
        )
        success(f"Run log: {log_path}", force_console=True)
        return 0

    except KeyboardInterrupt:
        LIVE_PROGRESS_ACTIVE = False
        error("Interrupted by user.", force_console=True)
        return 130
    except Exception as exc:
        LIVE_PROGRESS_ACTIVE = False
        error(str(exc), force_console=True)
        return 1
    finally:
        LIVE_PROGRESS_ACTIVE = False
        if RUN_LOGGER is not None:
            RUN_LOGGER.close()


if __name__ == "__main__":
    raise SystemExit(main())
