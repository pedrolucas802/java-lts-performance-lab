#!/usr/bin/env bash
set -euo pipefail

# Java LTS Performance Lab - Startup Benchmark Runner
# Measures Quarkus application startup time with repetitions

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMMON_SH="${PROJECT_ROOT}/scripts/common.sh"

# Default values
JAVA_VERSION="${1:-21}"
REPETITIONS="${2:-1}"

# Constants
APP_DIR="quarkus-app"
RESULTS_ROOT="${PROJECT_ROOT}/results/raw"
PORT="${PORT:-8080}"
MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-60}"

usage() {
    cat << EOF
Usage: $0 [JAVA_VERSION] [REPETITIONS]

Run Quarkus startup benchmark for specified Java version.

Arguments:
    JAVA_VERSION     Java version to test (17, 21, 25) [default: 21]
    REPETITIONS      Number of startup runs to perform [default: 1]

Environment:
    PORT             Port for Quarkus app [default: 8080]
    MAX_WAIT_SECONDS Maximum seconds to wait for startup [default: 60]

Examples:
    $0 21 3
    $0 17 5

Outputs results to: results/raw/java{JAVA_VERSION}/quarkus/startup-java{JAVA_VERSION}-run*.txt
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

# Validate arguments
if ! [[ "${REPETITIONS}" =~ ^[0-9]+$ ]] || [[ "${REPETITIONS}" -lt 1 ]]; then
    echo "ERROR: REPETITIONS must be a positive integer." >&2
    exit 1
fi

# Change to project root
cd "${PROJECT_ROOT}"

RESULTS_DIR="${RESULTS_ROOT}/java${JAVA_VERSION}/quarkus"
mkdir -p "${RESULTS_DIR}"

echo "INFO: Starting Quarkus startup benchmark"
echo "INFO: Java version: ${JAVA_VERSION}"
echo "INFO: Repetitions: ${REPETITIONS}"
echo "INFO: Results directory: ${RESULTS_DIR}"

# Source common functions
# shellcheck source=/dev/null
source "${COMMON_SH}"

validate_java_version "${JAVA_VERSION}"
require_command mvn
require_command java
require_command curl
require_command python3
ensure_port_free "${PORT}"

build_app "${JAVA_VERSION}" "${APP_DIR}"
JAR_PATH=$(find_jar "${APP_DIR}")

now_ns() {
    python3 - <<'PY'
import time
print(time.monotonic_ns())
PY
}

extract_quarkus_startup_ms() {
    local log_file=$1

    python3 - "${log_file}" <<'PY'
import pathlib
import re
import sys

log_path = pathlib.Path(sys.argv[1])
if not log_path.exists():
    print("")
    raise SystemExit(0)

text = log_path.read_text(errors="ignore")

patterns = [
    r"started in\s+([0-9]+(?:\.[0-9]+)?)s",
    r"started in\s+([0-9]+(?:\.[0-9]+)?)s\. Listening",
]

for pattern in patterns:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if match:
        seconds = float(match.group(1))
        print(int(seconds * 1000))
        raise SystemExit(0)

print("")
PY
}

run_startup_benchmark() {
    local run_num=$1
    local log_file="${RESULTS_DIR}/startup-java${JAVA_VERSION}-run${run_num}.log"
    local metrics_file="${RESULTS_DIR}/startup-java${JAVA_VERSION}-run${run_num}.txt"

    info "Starting run ${run_num}/${REPETITIONS}..."

    ensure_port_free "${PORT}"

    local start_ns
    start_ns=$(now_ns)

    local app_pid
    app_pid=$(start_app "${JAR_PATH}" "${log_file}" "" "${PORT}")

    if ! wait_for_health "${PORT}" "${MAX_WAIT_SECONDS}"; then
        error "Application failed to start within ${MAX_WAIT_SECONDS} seconds"
        error "Application log:"
        cat "${log_file}" >&2
        cleanup_app "${app_pid}"
        exit 1
    fi

    local end_ns
    end_ns=$(now_ns)

    local external_startup_ms=$(( (end_ns - start_ns) / 1000000 ))

    local quarkus_startup_ms
    quarkus_startup_ms=$(extract_quarkus_startup_ms "${log_file}")

    {
        echo "java_version=${JAVA_VERSION}"
        echo "run_number=${run_num}"
        echo "external_startup_ms=${external_startup_ms}"
        echo "quarkus_startup_ms=${quarkus_startup_ms}"
        echo "port=${PORT}"
        echo "log_file=${log_file}"
    } > "${metrics_file}"

    cleanup_app "${app_pid}"
    sleep 1

    info "Run ${run_num} completed - External: ${external_startup_ms}ms, Quarkus: ${quarkus_startup_ms:-N/A}ms"
}

for ((run=1; run<=REPETITIONS; run++)); do
    run_startup_benchmark "${run}"
done

success "Completed ${REPETITIONS} startup benchmark runs for Java ${JAVA_VERSION}"
info "Results written to ${RESULTS_DIR}/startup-java${JAVA_VERSION}-run*.txt"