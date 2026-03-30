#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import tomllib
import urllib.request
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
PROFILE_CONFIGS_DIR = PROJECT_ROOT / "config" / "benchmark-profiles"
LANE_CONFIGS_DIR = PROJECT_ROOT / "config" / "benchmark-lanes"

RICH_CONSOLE = Console() if HAS_RICH else None

RUN_LOGGER: "RunLogger | None" = None
RUN_TIMESTAMP: str | None = None
LIVE_PROGRESS_ACTIVE = False


@dataclass(frozen=True)
class BenchmarkProfile:
    name: str
    description: str
    app_jvm_opts: tuple[str, ...]
    app_env: dict[str, str]

    @property
    def app_jvm_opts_string(self) -> str:
        return " ".join(self.app_jvm_opts)


@dataclass(frozen=True)
class BenchmarkLane:
    name: str
    description: str
    container_runtime: str
    cpu_limit: str
    memory_limit_mb: str
    loadgen_location: str
    app_location: str


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


def load_profile_config(java_version: str, profile_name: str) -> BenchmarkProfile:
    profile_path = PROFILE_CONFIGS_DIR / profile_name / f"java{java_version}.toml"
    if not profile_path.exists():
        raise FileNotFoundError(f"Missing profile config: {profile_path}")

    data = tomllib.loads(profile_path.read_text(encoding="utf-8"))
    app_jvm_opts = tuple(str(item) for item in data.get("app_jvm_opts", []))
    app_env = {
        str(key): str(value)
        for key, value in data.get("app_env", {}).items()
    }

    return BenchmarkProfile(
        name=str(data.get("profile", profile_name)),
        description=str(data.get("description", "")),
        app_jvm_opts=app_jvm_opts,
        app_env=app_env,
    )


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
        profile: BenchmarkProfile,
        lane: BenchmarkLane,
        extra_env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = build_env(java_version)
    env.update(profile.app_env)
    env["BENCHMARK_PROFILE"] = profile.name
    env["BENCHMARK_LANE"] = lane.name
    env["BENCHMARK_RESULTS_ROOT"] = str(PROJECT_ROOT / "results" / "raw" / profile.name / lane.name)
    env["BENCHMARK_CONTAINER_RUNTIME"] = lane.container_runtime
    env["BENCHMARK_CPU_LIMIT"] = lane.cpu_limit
    env["BENCHMARK_MEMORY_LIMIT_MB"] = lane.memory_limit_mb
    env["BENCHMARK_LOADGEN_LOCATION"] = lane.loadgen_location
    env["BENCHMARK_APP_LOCATION"] = lane.app_location
    env["BENCHMARK_HOST_OS"] = sys.platform
    env["BENCHMARK_JAVA_VERSION"] = java_version
    env["APP_JVM_OPTS"] = profile.app_jvm_opts_string
    if extra_env:
        env.update(extra_env)
    return env


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


def wait_for_health(port: int, timeout_seconds: int = 90) -> None:
    deadline = time.time() + timeout_seconds
    url = f"http://localhost:{port}/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError(f"Application did not become healthy on {url} within {timeout_seconds}s")


def find_quarkus_jar() -> Path:
    jar = PROJECT_ROOT / "quarkus-app" / "target" / "quarkus-app" / "quarkus-run.jar"
    if not jar.exists():
        raise FileNotFoundError(f"Could not find Quarkus runner jar at {jar}")
    return jar


def start_quarkus_app(
        java_version: str,
        profile: BenchmarkProfile,
        lane: BenchmarkLane,
        port: int,
        *,
        progress: Progress | None = None,
        task_id: TaskID | None = None,
        completed_tasks: int = 0,
        total_tasks: int = 0,
) -> tuple[subprocess.Popen[str], TextIO, Path]:
    env = build_runtime_env(java_version, profile, lane, {"PORT": str(port)})

    run_command(
        [
            "mvn",
            "-pl",
            "quarkus-app",
            "clean",
            "package",
            "-DskipTests",
            f"-Djava.release={java_version}",
        ],
        env=env,
        label=f"Building Quarkus app for Java {java_version} ({profile.name})",
        progress=progress,
        task_id=task_id,
        completed_tasks=completed_tasks,
        total_tasks=total_tasks,
    )

    log_dir = PROJECT_ROOT / "results" / "raw" / profile.name / f"java{java_version}" / "quarkus"
    log_dir.mkdir(parents=True, exist_ok=True)
    run_suffix = RUN_TIMESTAMP or timestamp_now()
    log_file = log_dir / f"app-run-java{java_version}-{run_suffix}.log"

    jar = find_quarkus_jar()

    set_progress_message(
        progress,
        task_id,
        completed_tasks,
        total_tasks,
        f"Starting Quarkus app for Java {java_version} ({profile.name}) on port {port}",
    )

    info(f"Starting Quarkus app for Java {java_version} ({profile.name}) on port {port}")

    log_handle = log_file.open("w", encoding="utf-8")
    command = ["java", *profile.app_jvm_opts, f"-Dquarkus.http.port={port}", "-jar", str(jar)]
    process = subprocess.Popen(
        command,
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        wait_for_health(port)
    except Exception:
        process.terminate()
        log_handle.close()
        raise

    success(f"Quarkus app is healthy for Java {java_version} ({profile.name})")
    note(f"Application log: {log_file}")

    return process, log_handle, log_file


def stop_process(process: subprocess.Popen[str], log_handle: TextIO | None = None) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    if log_handle is not None and not log_handle.closed:
        log_handle.flush()
        log_handle.close()


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
        "--versions",
        nargs="+",
        default=["17", "21", "25"],
        help="Java versions to benchmark. Default: 17 21 25",
    )
    parser.add_argument(
        "--startup-repetitions",
        type=int,
        default=3,
        help="Number of startup repetitions per Java version. Default: 3",
    )
    parser.add_argument(
        "--http-duration",
        default="20s",
        help="HTTP benchmark duration. Default: 20s",
    )
    parser.add_argument(
        "--http-vus",
        type=int,
        default=10,
        help="HTTP benchmark virtual users. Default: 10",
    )
    parser.add_argument(
        "--memory-duration",
        default="20s",
        help="Memory benchmark duration. Default: 20s",
    )
    parser.add_argument(
        "--memory-vus",
        type=int,
        default=20,
        help="Memory benchmark virtual users. Default: 20",
    )
    parser.add_argument(
        "--concurrency-duration",
        default="20s",
        help="Concurrency ramp duration per VU level. Default: 20s",
    )
    parser.add_argument(
        "--concurrency-vus-list",
        default="2,10,25,50",
        help="Comma-separated VU ramp list for the concurrency study. Default: 2,10,25,50",
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
        action="store_true",
        help="Also run the GC/JFR/CPU observability suite for each Java version.",
    )
    parser.add_argument(
        "--gc-duration",
        default="20s",
        help="Observability suite duration per scenario. Default: 20s",
    )
    parser.add_argument(
        "--gc-vus",
        type=int,
        default=10,
        help="Observability suite virtual users per scenario. Default: 10",
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
        "--profile",
        choices=["stock", "tuned"],
        default="stock",
        help="Benchmark profile config to use for app-based runs. Default: stock",
    )
    parser.add_argument(
        "--lane",
        choices=["macos-container", "linux-container"],
        default=default_lane_name(),
        help="Execution lane for app-based runs. Default is macos-container on macOS and linux-container elsewhere.",
    )
    parser.add_argument(
        "--include-mixed-workload",
        action="store_true",
        help="Also run the weighted mixed-workload HTTP scenario.",
    )
    args = parser.parse_args()

    logger, run_timestamp, log_path = create_run_logger()
    RUN_LOGGER = logger
    RUN_TIMESTAMP = run_timestamp

    try:
        info(f"Run log file: {log_path}", force_console=True)
        validate_tools(include_gc=args.with_gc_suite, lane=args.lane)

        versions = [str(v) for v in args.versions]
        for version in versions:
            if version not in {"17", "21", "25"}:
                raise RuntimeError(f"Unsupported Java version: {version}")

        lane = load_lane_config(args.lane)

        all_tasks = task_plan(
            versions,
            include_gc=args.with_gc_suite,
            skip_jmh=args.skip_jmh,
        )
        total_tasks = len(all_tasks)
        completed_tasks = 0

        logger.section("RUN CONFIGURATION")
        logger.write_line(f"Versions: {', '.join(versions)}")
        logger.write_line(f"Profile: {args.profile}")
        logger.write_line(f"Lane: {lane.name}")
        logger.write_line(f"Lane description: {lane.description}")
        logger.write_line(f"Startup repetitions: {args.startup_repetitions}")
        logger.write_line(f"HTTP duration: {args.http_duration}")
        logger.write_line(f"HTTP VUs: {args.http_vus}")
        logger.write_line(f"Concurrency duration: {args.concurrency_duration}")
        logger.write_line(f"Concurrency VU ramp: {args.concurrency_vus_list}")
        logger.write_line(f"Memory duration: {args.memory_duration}")
        logger.write_line(f"Memory VUs: {args.memory_vus}")
        logger.write_line(f"Port: {args.port}")
        logger.write_line(f"Memory port: {args.memory_port}")
        logger.write_line(f"Heap info: {args.heap_info}")
        logger.write_line(f"With GC suite: {args.with_gc_suite}")
        logger.write_line(f"GC duration: {args.gc_duration}")
        logger.write_line(f"GC VUs: {args.gc_vus}")
        logger.write_line(f"GC port: {args.gc_port}")
        logger.write_line(f"Skip JMH: {args.skip_jmh}")
        logger.write_line(f"Include mixed workload: {args.include_mixed_workload}")
        logger.write_line()

        note(f"Planned tasks: {total_tasks}", force_console=True)

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

            for version in versions:
                profile = load_profile_config(version, args.profile)
                runtime_env = build_runtime_env(version, profile, lane)
                http_scenarios, memory_scenarios = scenarios_for_version(version, args.include_mixed_workload)

                requires_database = any(
                    scenario in {"products-db", "mixed-workload", "aggregate-platform", "aggregate-virtual"}
                    for scenario in (*http_scenarios, *memory_scenarios)
                )
                if requires_database and not runtime_env.get("BENCHMARK_DATASOURCE_URL"):
                    raise RuntimeError(
                        f"Profile '{profile.name}' for Java {version} requires BENCHMARK_DATASOURCE_URL for DB-backed scenarios."
                    )

                prep_message = f"Preparing Java {version} ({profile.name}) benchmark flow"
                set_progress_message(progress, task_id, completed_tasks, total_tasks, prep_message)
                note(prep_message)

                if not args.skip_jmh:
                    run_command(
                        ["bash", str(RUNNERS_DIR / "run_jmh_suite.sh"), version],
                        env=runtime_env,
                        label=f"JMH microbenchmarks for Java {version}",
                        progress=progress,
                        task_id=task_id,
                        completed_tasks=completed_tasks,
                        total_tasks=total_tasks,
                    )
                    step(f"JMH Java {version}")

                startup_env = build_runtime_env(version, profile, lane, {"PORT": str(args.port)})
                run_command(
                    [
                        "bash",
                        str(RUNNERS_DIR / "run_quarkus_startup_benchmark.sh"),
                        version,
                        str(args.startup_repetitions),
                    ],
                    env=startup_env,
                    label=f"Startup benchmark for Java {version} ({profile.name})",
                    progress=progress,
                    task_id=task_id,
                    completed_tasks=completed_tasks,
                    total_tasks=total_tasks,
                )
                step(f"Startup Java {version}")

                run_command(
                    [
                        "bash",
                        str(RUNNERS_DIR / "run_quarkus_suite.sh"),
                        version,
                        args.http_duration,
                        str(args.http_vus),
                        ",".join(http_scenarios),
                    ],
                    env=build_runtime_env(version, profile, lane, {"PORT": str(args.port)}),
                    label=f"HTTP suite for Java {version} ({profile.name}, {lane.name})",
                    progress=progress,
                    task_id=task_id,
                    completed_tasks=completed_tasks,
                    total_tasks=total_tasks,
                )

                step(f"HTTP suite Java {version}")

                run_command(
                    [
                        "bash",
                        str(RUNNERS_DIR / "run_concurrency_study.sh"),
                        version,
                        args.concurrency_duration,
                        args.concurrency_vus_list,
                    ],
                    env=build_runtime_env(version, profile, lane, {"PORT": str(args.port)}),
                    label=f"Concurrency study for Java {version} ({profile.name})",
                    progress=progress,
                    task_id=task_id,
                    completed_tasks=completed_tasks,
                    total_tasks=total_tasks,
                )
                step(f"Concurrency study Java {version}")

                for scenario in memory_scenarios:
                    mem_env = build_runtime_env(
                        version,
                        profile,
                        lane,
                        {
                            "PORT": str(args.memory_port),
                            "DURATION": args.memory_duration,
                            "VUS": str(args.memory_vus),
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
                        label=f"Memory {scenario} on Java {version} ({profile.name})",
                        progress=progress,
                        task_id=task_id,
                        completed_tasks=completed_tasks,
                        total_tasks=total_tasks,
                    )

                step(f"Memory suite Java {version}")

                if args.with_gc_suite:
                    run_command(
                        [
                            "bash",
                            str(RUNNERS_DIR / "run_gc_suite.sh"),
                            version,
                            args.gc_duration,
                            str(args.gc_vus),
                        ],
                        env=build_runtime_env(version, profile, lane, {"PORT": str(args.gc_port)}),
                        label=f"GC/JFR/CPU suite for Java {version} ({profile.name})",
                        progress=progress,
                        task_id=task_id,
                        completed_tasks=completed_tasks,
                        total_tasks=total_tasks,
                    )
                    step(f"GC suite Java {version}")

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

            if args.with_gc_suite:
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

            if args.with_gc_suite:
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
