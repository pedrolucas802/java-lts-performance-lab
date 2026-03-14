#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from shutil import which
from typing import Iterable, TextIO

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNERS_DIR = PROJECT_ROOT / "scripts" / "runners"
AGGREGATORS_DIR = PROJECT_ROOT / "scripts" / "aggregators"
CHARTS_DIR = PROJECT_ROOT / "scripts" / "charts"
LOGS_DIR = PROJECT_ROOT / "results" / "logs"

RICH_CONSOLE = Console()

RUN_LOGGER: "RunLogger | None" = None
RUN_TIMESTAMP: str | None = None
LIVE_PROGRESS_ACTIVE = False


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
        RICH_CONSOLE.print(message)


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
    java_home = macos_java_home(java_version)
    env["JAVA_HOME"] = java_home
    env["PATH"] = f"{java_home}/bin:{env.get('PATH', '')}"
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
        port: int,
        *,
        progress: Progress | None = None,
        task_id: TaskID | None = None,
        completed_tasks: int = 0,
        total_tasks: int = 0,
) -> tuple[subprocess.Popen[str], TextIO, Path]:
    env = build_env(java_version)

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
        label=f"Building Quarkus app for Java {java_version}",
        progress=progress,
        task_id=task_id,
        completed_tasks=completed_tasks,
        total_tasks=total_tasks,
    )

    log_dir = PROJECT_ROOT / "results" / "raw" / f"java{java_version}" / "quarkus"
    log_dir.mkdir(parents=True, exist_ok=True)
    run_suffix = RUN_TIMESTAMP or timestamp_now()
    log_file = log_dir / f"app-run-java{java_version}-{run_suffix}.log"

    jar = find_quarkus_jar()

    set_progress_message(
        progress,
        task_id,
        completed_tasks,
        total_tasks,
        f"Starting Quarkus app for Java {java_version} on port {port}",
    )

    info(f"Starting Quarkus app for Java {java_version} on port {port}")

    log_handle = log_file.open("w", encoding="utf-8")
    process = subprocess.Popen(
        ["java", f"-Dquarkus.http.port={port}", "-jar", str(jar)],
        cwd=str(PROJECT_ROOT),
        env={**env, "PORT": str(port)},
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

    success(f"Quarkus app is healthy for Java {java_version}")
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


def validate_tools() -> None:
    required = ["bash", "python3", "mvn", "k6"]
    missing = [tool for tool in required if which(tool) is None]
    if missing:
        raise RuntimeError(f"Missing required tools: {', '.join(missing)}")

    if sys.platform != "darwin":
        raise RuntimeError(
            "This script currently assumes macOS because it uses /usr/libexec/java_home."
        )


def scenarios_for_version(java_version: str) -> tuple[list[str], list[str]]:
    http = ["products", "transform", "aggregate-platform"]
    memory = ["products", "transform", "aggregate-platform"]

    if java_version in {"21", "25"}:
        http.append("aggregate-virtual")
        memory.append("aggregate-virtual")

    return http, memory


def task_plan(versions: Iterable[str], include_gc: bool) -> list[str]:
    tasks: list[str] = []
    for version in versions:
        tasks.append(f"JMH Java {version}")
        tasks.append(f"Startup Java {version}")
        tasks.append(f"HTTP suite Java {version}")
        tasks.append(f"Memory suite Java {version}")
        if include_gc:
            tasks.append(f"GC suite Java {version}")

    tasks.extend(
        [
            "Aggregate startup results",
            "Aggregate HTTP results",
            "Aggregate memory results",
            "Generate startup chart",
            "Generate Quarkus charts",
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
        action="store_true",
        help="Also run the GC suite for each Java version.",
    )
    args = parser.parse_args()

    logger, run_timestamp, log_path = create_run_logger()
    RUN_LOGGER = logger
    RUN_TIMESTAMP = run_timestamp

    try:
        info(f"Run log file: {log_path}", force_console=True)
        validate_tools()

        versions = [str(v) for v in args.versions]
        for version in versions:
            if version not in {"17", "21", "25"}:
                raise RuntimeError(f"Unsupported Java version: {version}")

        all_tasks = task_plan(versions, args.with_gc_suite)
        total_tasks = len(all_tasks)
        completed_tasks = 0

        logger.section("RUN CONFIGURATION")
        logger.write_line(f"Versions: {', '.join(versions)}")
        logger.write_line(f"Startup repetitions: {args.startup_repetitions}")
        logger.write_line(f"HTTP duration: {args.http_duration}")
        logger.write_line(f"HTTP VUs: {args.http_vus}")
        logger.write_line(f"Port: {args.port}")
        logger.write_line(f"Memory port: {args.memory-port if False else args.memory_port}")
        logger.write_line(f"Heap info: {args.heap_info}")
        logger.write_line(f"With GC suite: {args.with_gc_suite}")
        logger.write_line()

        note(f"Planned tasks: {total_tasks}", force_console=True)

        with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=32),
                TextColumn("{task.completed}/{task.total}"),
                TextColumn("({task.percentage:>5.1f}%)"),
                TimeElapsedColumn(),
                console=RICH_CONSOLE,
                transient=False,
        ) as progress:
            LIVE_PROGRESS_ACTIVE = True

            task_id = progress.add_task(
                description="Initializing benchmark lab",
                total=total_tasks,
                completed=0,
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
                env = build_env(version)
                http_scenarios, memory_scenarios = scenarios_for_version(version)

                prep_message = f"Preparing Java {version} benchmark flow"
                set_progress_message(progress, task_id, completed_tasks, total_tasks, prep_message)
                note(prep_message)

                run_command(
                    ["bash", str(RUNNERS_DIR / "run_jmh_suite.sh"), version],
                    env=env,
                    label=f"JMH microbenchmarks for Java {version}",
                    progress=progress,
                    task_id=task_id,
                    completed_tasks=completed_tasks,
                    total_tasks=total_tasks,
                )
                step(f"JMH Java {version}")

                startup_env = {**env, "PORT": str(args.port)}
                run_command(
                    [
                        "bash",
                        str(RUNNERS_DIR / "run_quarkus_startup_benchmark.sh"),
                        version,
                        str(args.startup_repetitions),
                    ],
                    env=startup_env,
                    label=f"Startup benchmark for Java {version}",
                    progress=progress,
                    task_id=task_id,
                    completed_tasks=completed_tasks,
                    total_tasks=total_tasks,
                )
                step(f"Startup Java {version}")

                process: subprocess.Popen[str] | None = None
                app_log_handle: TextIO | None = None
                try:
                    process, app_log_handle, _ = start_quarkus_app(
                        version,
                        args.port,
                        progress=progress,
                        task_id=task_id,
                        completed_tasks=completed_tasks,
                        total_tasks=total_tasks,
                    )

                    for scenario in http_scenarios:
                        run_command(
                            [
                                "bash",
                                str(RUNNERS_DIR / "run_quarkus_http_benchmark.sh"),
                                version,
                                scenario,
                                args.http_duration,
                                str(args.http_vus),
                            ],
                            env={**env, "PORT": str(args.port)},
                            label=f"HTTP {scenario} on Java {version}",
                            progress=progress,
                            task_id=task_id,
                            completed_tasks=completed_tasks,
                            total_tasks=total_tasks,
                        )
                finally:
                    if process is not None:
                        stop_process(process, app_log_handle)

                step(f"HTTP suite Java {version}")

                for scenario in memory_scenarios:
                    mem_env = {**env, "PORT": str(args.memory_port)}
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
                        label=f"Memory {scenario} on Java {version}",
                        progress=progress,
                        task_id=task_id,
                        completed_tasks=completed_tasks,
                        total_tasks=total_tasks,
                    )

                step(f"Memory suite Java {version}")

                if args.with_gc_suite:
                    run_command(
                        ["bash", str(RUNNERS_DIR / "run_gc_suite.sh"), version],
                        env=env,
                        label=f"GC suite for Java {version}",
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
                ["python3", str(AGGREGATORS_DIR / "aggregate_memory_results.py")],
                label="Aggregating memory results",
                progress=progress,
                task_id=task_id,
                completed_tasks=completed_tasks,
                total_tasks=total_tasks,
            )
            step("Aggregate memory results")

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