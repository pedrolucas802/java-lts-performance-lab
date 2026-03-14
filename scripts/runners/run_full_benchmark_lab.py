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


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNERS_DIR = PROJECT_ROOT / "scripts" / "runners"
AGGREGATORS_DIR = PROJECT_ROOT / "scripts" / "aggregators"
CHARTS_DIR = PROJECT_ROOT / "scripts" / "charts"
LOGS_DIR = PROJECT_ROOT / "results" / "logs"


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


RUN_LOGGER: RunLogger | None = None
RUN_TIMESTAMP: str | None = None


def timestamp_now() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def console(message: str) -> None:
    print(message, flush=True)


def log_line(message: str) -> None:
    if RUN_LOGGER is not None:
        RUN_LOGGER.write_line(message)


def info(message: str) -> None:
    line = f"[INFO] {message}"
    console(line)
    log_line(line)


def success(message: str) -> None:
    line = f"[OK]   {message}"
    console(line)
    log_line(line)


def error(message: str) -> None:
    line = f"[ERR]  {message}"
    console(line)
    log_line(line)


def note(message: str) -> None:
    line = f"[NOTE] {message}"
    console(line)
    log_line(line)


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


def print_progress(current: int, total: int, label: str) -> None:
    width = 30
    filled = int(width * current / total) if total else width
    bar = "#" * filled + "-" * (width - filled)
    percent = (current / total * 100.0) if total else 100.0
    console(f"[{bar}] {current}/{total} ({percent:5.1f}%)  {label}")


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


def run_command(
        cmd: list[str],
        *,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
        check: bool = True,
        label: str | None = None,
) -> subprocess.CompletedProcess[str]:
    command_str = " ".join(cmd)
    info(f"Running: {command_str}")
    if label:
        note(label)

    started = time.time()
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


def start_quarkus_app(java_version: str, port: int) -> tuple[subprocess.Popen[str], TextIO, Path]:
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
    )

    log_dir = PROJECT_ROOT / "results" / "raw" / f"java{java_version}" / "quarkus"
    log_dir.mkdir(parents=True, exist_ok=True)
    run_suffix = RUN_TIMESTAMP or timestamp_now()
    log_file = log_dir / f"app-run-java{java_version}-{run_suffix}.log"

    jar = find_quarkus_jar()
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
        error("This master script currently assumes macOS because it uses /usr/libexec/java_home.")
        raise RuntimeError("Unsupported platform for this script")


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
    global RUN_LOGGER, RUN_TIMESTAMP

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
        help="Port to use for startup and HTTP benchmark app. Default: 8080",
    )
    parser.add_argument(
        "--memory-port",
        type=int,
        default=8081,
        help="Port to use for memory benchmark app. Default: 8081",
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
        info(f"Run log file: {log_path}")
        validate_tools()

        versions = [str(v) for v in args.versions]
        for version in versions:
            if version not in {"17", "21", "25"}:
                raise RuntimeError(f"Unsupported Java version: {version}")

        all_tasks = task_plan(versions, args.with_gc_suite)
        completed = 0

        def step(label: str) -> None:
            nonlocal completed
            completed += 1
            print_progress(completed, len(all_tasks), label)

        logger.section("RUN CONFIGURATION")
        logger.write_line(f"Versions: {', '.join(versions)}")
        logger.write_line(f"Startup repetitions: {args.startup_repetitions}")
        logger.write_line(f"HTTP duration: {args.http_duration}")
        logger.write_line(f"HTTP VUs: {args.http_vus}")
        logger.write_line(f"Startup/HTTP port: {args.port}")
        logger.write_line(f"Memory port: {args.memory_port}")
        logger.write_line(f"Heap info: {args.heap_info}")
        logger.write_line(f"With GC suite: {args.with_gc_suite}")
        logger.write_line()

        note(f"Planned tasks: {len(all_tasks)}")

        for version in versions:
            env = build_env(version)
            http_scenarios, memory_scenarios = scenarios_for_version(version)
            note(f"Preparing benchmark flow for Java {version}")

            run_command(
                ["bash", str(RUNNERS_DIR / "run_jmh_suite.sh"), version],
                env=env,
                label=f"JMH microbenchmarks for Java {version}",
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
                label=f"Startup benchmark for Java {version} on port {args.port}",
            )
            step(f"Startup Java {version}")

            process: subprocess.Popen[str] | None = None
            app_log_handle: TextIO | None = None
            try:
                process, app_log_handle, _ = start_quarkus_app(version, args.port)

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
                        label=f"HTTP scenario '{scenario}' for Java {version}",
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
                    label=f"Memory scenario '{scenario}' for Java {version} on port {args.memory_port}",
                )
            step(f"Memory suite Java {version}")

            if args.with_gc_suite:
                run_command(
                    ["bash", str(RUNNERS_DIR / "run_gc_suite.sh"), version],
                    env=env,
                    label=f"GC suite for Java {version}",
                )
                step(f"GC suite Java {version}")

        run_command(
            ["python3", str(AGGREGATORS_DIR / "aggregate_startup_results.py")],
            label="Aggregating startup benchmark results",
        )
        step("Aggregate startup results")

        run_command(
            ["python3", str(AGGREGATORS_DIR / "aggregate_quarkus_results.py")],
            label="Aggregating HTTP benchmark results",
        )
        step("Aggregate HTTP results")

        run_command(
            ["python3", str(AGGREGATORS_DIR / "aggregate_memory_results.py")],
            label="Aggregating memory benchmark results",
        )
        step("Aggregate memory results")

        run_command(
            ["python3", str(CHARTS_DIR / "generate_startup_chart.py")],
            label="Generating startup comparison chart",
        )
        step("Generate startup chart")

        run_command(
            ["python3", str(CHARTS_DIR / "generate_quarkus_charts.py")],
            label="Generating Quarkus comparison charts",
        )
        step("Generate Quarkus charts")

        success("Full benchmark lab completed successfully.")
        success(f"Processed results: {PROJECT_ROOT / 'results' / 'processed'}")
        success(f"Charts: {PROJECT_ROOT / 'results' / 'charts'}")
        success(f"Run log: {log_path}")
        return 0

    except KeyboardInterrupt:
        error("Interrupted by user.")
        return 130
    except Exception as exc:
        error(str(exc))
        return 1
    finally:
        if RUN_LOGGER is not None:
            RUN_LOGGER.close()


if __name__ == "__main__":
    raise SystemExit(main())