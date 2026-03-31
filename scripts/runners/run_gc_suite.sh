#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

JAVA_VERSION="${1:-21}"
DURATION="${2:-20s}"
VUS="${3:-10}"
BENCHMARK_LANE="${BENCHMARK_LANE:-host}"
BENCHMARK_PROFILE="stock"
BENCHMARK_RESULTS_ROOT="${BENCHMARK_RESULTS_ROOT:-${PROJECT_ROOT}/results/raw/${BENCHMARK_PROFILE}/${BENCHMARK_LANE}}"
APP_JVM_OPTS="${APP_JVM_OPTS:-}"
PORT="${PORT:-8082}"
CPU_SAMPLE_INTERVAL_SECONDS="${CPU_SAMPLE_INTERVAL_SECONDS:-1}"
GC_SCENARIOS="${GC_SCENARIOS:-}"

APP_DIR="quarkus-app"
RESULTS_ROOT="${BENCHMARK_RESULTS_ROOT}"
K6_DIR="${PROJECT_ROOT}/infra/k6"
RESULTS_DIR="${RESULTS_ROOT}/java${JAVA_VERSION}/gc"

SCRIPT_APP_PID=""
SCRIPT_SAMPLER_PID=""

usage() {
    cat <<EOF
Usage: $0 [JAVA_VERSION] [DURATION] [VUS]

Run the observability suite with structured GC logs, JFR recordings, and CPU timeline sampling.

Arguments:
    JAVA_VERSION    Java version to test (17, 21, 25) [default: 21]
    DURATION        Load-test duration per scenario [default: 20s]
    VUS             Virtual users per scenario [default: 10]

Environment:
    APP_JVM_OPTS                  Extra JVM opts for the Quarkus app
    PORT                          Quarkus app port [default: 8082]
    CPU_SAMPLE_INTERVAL_SECONDS   CPU sampling interval [default: 1]
    GC_SCENARIOS                  Comma-separated scenario override

Representative default scenarios:
    Java 17: products-db, aggregate-platform
    Java 21/25: products-db, aggregate-platform, aggregate-virtual
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

cd "${PROJECT_ROOT}"

source "${PROJECT_ROOT}/scripts/common.sh"
export BENCHMARK_JAVA_VERSION="${JAVA_VERSION}"

cleanup_suite() {
    if [[ -n "${SCRIPT_SAMPLER_PID}" ]] && kill -0 "${SCRIPT_SAMPLER_PID}" >/dev/null 2>&1; then
        kill "${SCRIPT_SAMPLER_PID}" >/dev/null 2>&1 || true
        wait "${SCRIPT_SAMPLER_PID}" 2>/dev/null || true
    fi
    SCRIPT_SAMPLER_PID=""

    if [[ -n "${SCRIPT_APP_PID}" ]]; then
        cleanup_app "${SCRIPT_APP_PID}"
    fi
    SCRIPT_APP_PID=""
}

trap cleanup_suite EXIT

start_cpu_sampler() {
    local app_id=$1
    local timeline_file=$2
    local interval=$3

    echo "timestamp_epoch,elapsed_seconds,cpu_percent,rss_kb,cpu_time" > "${timeline_file}"

    (
        local start_epoch current_epoch elapsed snapshot cpu_percent rss_kb cpu_time
        start_epoch=$(date +%s)

        while true; do
            if ! snapshot=$(get_app_snapshot "${app_id}"); then
                break
            fi

            IFS=',' read -r cpu_percent rss_kb cpu_time <<< "${snapshot}"
            current_epoch=$(date +%s)
            elapsed=$((current_epoch - start_epoch))

            echo "${current_epoch},${elapsed},${cpu_percent:-},${rss_kb:-},${cpu_time:-}" >> "${timeline_file}"
            sleep "${interval}"
        done
    ) >/dev/null 2>&1 &

    echo $!
}

stop_cpu_sampler() {
    local sampler_pid=$1

    if [[ -n "${sampler_pid}" ]] && kill -0 "${sampler_pid}" >/dev/null 2>&1; then
        kill "${sampler_pid}" >/dev/null 2>&1 || true
        wait "${sampler_pid}" 2>/dev/null || true
    fi
}

wait_for_artifact() {
    local path=$1
    local max_wait=${2:-50}

    for ((i=1; i<=max_wait; i++)); do
        if [[ -s "${path}" ]]; then
            return 0
        fi
        sleep 0.2
    done

    error "Expected artifact was not created: ${path}"
    return 1
}

validate_java_version "${JAVA_VERSION}"
require_command mvn
require_command java
require_command curl
require_command k6
require_command jfr
require_command ps
require_command awk

if ! [[ "${VUS}" =~ ^[0-9]+$ ]] || [[ "${VUS}" -lt 1 ]]; then
    error "VUS must be a positive integer."
    exit 1
fi

mkdir -p "${RESULTS_DIR}"
ensure_port_free "${PORT}"

declare -a SCENARIOS
if [[ -n "${GC_SCENARIOS}" ]]; then
    IFS=',' read -r -a SCENARIOS <<< "${GC_SCENARIOS}"
else
    SCENARIOS=("products-db" "aggregate-platform")
    if [[ "${JAVA_VERSION}" =~ ^(21|25)$ ]]; then
        SCENARIOS+=("aggregate-virtual")
    fi
fi

for scenario in "${SCENARIOS[@]}"; do
    if ! [[ "${scenario}" =~ ^(products|products-db|transform|aggregate|aggregate-platform|aggregate-virtual|mixed-workload)$ ]]; then
        error "Invalid GC scenario '${scenario}'."
        exit 1
    fi
done

info "Starting GC / JFR / CPU observability suite"
info "Java version: ${JAVA_VERSION}"
info "Lane: ${BENCHMARK_LANE}"
info "Duration: ${DURATION}"
info "Virtual users: ${VUS}"
info "Port: ${PORT}"
info "Results directory: ${RESULTS_DIR}"
info "Scenarios: ${SCENARIOS[*]}"

build_app "${JAVA_VERSION}" "${APP_DIR}"
JAR_PATH=$(find_jar "${APP_DIR}")

for SCENARIO in "${SCENARIOS[@]}"; do
    cleanup_suite
    ensure_port_free "${PORT}"

    if [[ "${SCENARIO}" =~ ^aggregate ]]; then
        K6_SCRIPT="${K6_DIR}/aggregate.js"
    else
        K6_SCRIPT="${K6_DIR}/${SCENARIO}.js"
    fi

    if [[ ! -f "${K6_SCRIPT}" ]]; then
        error "K6 script not found: ${K6_SCRIPT}"
        exit 1
    fi

    APP_LOG_FILE="${RESULTS_DIR}/${SCENARIO}-app.log"
    GC_LOG_FILE="${RESULTS_DIR}/${SCENARIO}-gc.log"
    JFR_FILE="${RESULTS_DIR}/${SCENARIO}.jfr"
    JFR_SUMMARY_FILE="${RESULTS_DIR}/${SCENARIO}-jfr-summary.txt"
    JFR_EXECUTION_FILE="${RESULTS_DIR}/${SCENARIO}-execution-samples.json"
    JFR_ALLOCATION_FILE="${RESULTS_DIR}/${SCENARIO}-allocation-samples.json"
    JFR_THREAD_FILE="${RESULTS_DIR}/${SCENARIO}-thread-events.json"
    CPU_TIMELINE_FILE="${RESULTS_DIR}/${SCENARIO}-cpu-timeline.csv"
    SUMMARY_FILE="${RESULTS_DIR}/${SCENARIO}-summary.txt"
    K6_JSON_FILE="${RESULTS_DIR}/${SCENARIO}-k6.json"
    METRICS_FILE="${RESULTS_DIR}/${SCENARIO}-metrics.txt"

    rm -f \
        "${APP_LOG_FILE}" \
        "${GC_LOG_FILE}" \
        "${JFR_FILE}" \
        "${JFR_SUMMARY_FILE}" \
        "${JFR_EXECUTION_FILE}" \
        "${JFR_ALLOCATION_FILE}" \
        "${JFR_THREAD_FILE}" \
        "${CPU_TIMELINE_FILE}" \
        "${SUMMARY_FILE}" \
        "${K6_JSON_FILE}" \
        "${METRICS_FILE}"

    JVM_OPTS="${APP_JVM_OPTS} -Xlog:gc*,safepoint:file=${GC_LOG_FILE}:time,uptimemillis,level,tags:filecount=1 -XX:StartFlightRecording=filename=${JFR_FILE},settings=profile,disk=true,dumponexit=true,maxsize=250M"

    info "Starting observability scenario: ${SCENARIO}"
    SCRIPT_APP_PID=$(start_app "${JAR_PATH}" "${APP_LOG_FILE}" "${JVM_OPTS}" "${PORT}")
    APP_ID_FOR_RUN="${SCRIPT_APP_PID}"
    wait_for_health "${PORT}" 60

    START_SNAPSHOT="$(get_app_snapshot "${SCRIPT_APP_PID}" || true)"
    START_CPU_PERCENT=""
    START_RSS_KB=""
    START_CPU_TIME=""
    if [[ -n "${START_SNAPSHOT}" ]]; then
        IFS=',' read -r START_CPU_PERCENT START_RSS_KB START_CPU_TIME <<< "${START_SNAPSHOT}"
    fi

    SCRIPT_SAMPLER_PID=$(start_cpu_sampler "${SCRIPT_APP_PID}" "${CPU_TIMELINE_FILE}" "${CPU_SAMPLE_INTERVAL_SECONDS}")

    EXTRA_ENV=()
    if [[ "${SCENARIO}" == "aggregate-platform" ]]; then
        EXTRA_ENV+=(-e "AGG_MODE=platform")
    elif [[ "${SCENARIO}" == "aggregate-virtual" ]]; then
        EXTRA_ENV+=(-e "AGG_MODE=virtual")
    fi

    k6_cmd=(
        k6 run
        --out "json=${K6_JSON_FILE}"
        -e "BASE_URL=http://localhost:${PORT}"
        -e "DURATION=${DURATION}"
        -e "VUS=${VUS}"
    )

    if [[ ${#EXTRA_ENV[@]} -gt 0 ]]; then
        k6_cmd+=("${EXTRA_ENV[@]}")
    fi

    k6_cmd+=("${K6_SCRIPT}")

    "${k6_cmd[@]}" | tee "${SUMMARY_FILE}"

    stop_cpu_sampler "${SCRIPT_SAMPLER_PID}"
    SCRIPT_SAMPLER_PID=""

    END_SNAPSHOT="$(get_app_snapshot "${SCRIPT_APP_PID}" || true)"
    END_CPU_PERCENT=""
    END_RSS_KB=""
    END_CPU_TIME=""
    if [[ -n "${END_SNAPSHOT}" ]]; then
        IFS=',' read -r END_CPU_PERCENT END_RSS_KB END_CPU_TIME <<< "${END_SNAPSHOT}"
    fi

    cleanup_app "${SCRIPT_APP_PID}"
    SCRIPT_APP_PID=""

    wait_for_artifact "${JFR_FILE}"
    wait_for_artifact "${GC_LOG_FILE}"

    jfr summary "${JFR_FILE}" > "${JFR_SUMMARY_FILE}"
    jfr print --json --events jdk.ExecutionSample --stack-depth 8 "${JFR_FILE}" > "${JFR_EXECUTION_FILE}"
    jfr print --json --events jdk.ObjectAllocationSample "${JFR_FILE}" > "${JFR_ALLOCATION_FILE}"
    jfr print --json --events jdk.ThreadPark,jdk.VirtualThreadPinned,jdk.JavaMonitorEnter,jdk.JavaThreadStatistics,jdk.GarbageCollection,jdk.ThreadCPULoad "${JFR_FILE}" > "${JFR_THREAD_FILE}"

    {
        echo "java_version=${JAVA_VERSION}"
        echo "profile=${BENCHMARK_PROFILE}"
        echo "lane=${BENCHMARK_LANE}"
        echo "host_os=$(benchmark_host_os)"
        echo "container_runtime=$(benchmark_container_runtime)"
        echo "cpu_limit=$(benchmark_cpu_limit)"
        echo "memory_limit_mb=$(benchmark_memory_limit_mb)"
        echo "loadgen_location=$(benchmark_loadgen_location)"
        echo "app_location=$(benchmark_app_location)"
        echo "scenario=${SCENARIO}"
        echo "duration=${DURATION}"
        echo "vus=${VUS}"
        echo "port=${PORT}"
        echo "pid=${APP_ID_FOR_RUN}"
        echo "start_cpu_percent=${START_CPU_PERCENT}"
        echo "start_rss_kb=${START_RSS_KB}"
        echo "start_cpu_time=${START_CPU_TIME}"
        echo "end_cpu_percent=${END_CPU_PERCENT}"
        echo "end_rss_kb=${END_RSS_KB}"
        echo "end_cpu_time=${END_CPU_TIME}"
        echo "gc_log_file=${GC_LOG_FILE}"
        echo "jfr_file=${JFR_FILE}"
        echo "jfr_summary_file=${JFR_SUMMARY_FILE}"
        echo "jfr_execution_file=${JFR_EXECUTION_FILE}"
        echo "jfr_allocation_file=${JFR_ALLOCATION_FILE}"
        echo "jfr_thread_file=${JFR_THREAD_FILE}"
        echo "cpu_timeline_file=${CPU_TIMELINE_FILE}"
        echo "summary_file=${SUMMARY_FILE}"
        echo "k6_json_file=${K6_JSON_FILE}"
        echo "app_log_file=${APP_LOG_FILE}"
    } > "${METRICS_FILE}"

    success "Observability scenario completed for ${SCENARIO}"
    info "Metrics written to ${METRICS_FILE}"
done

success "GC / JFR / CPU observability suite completed"
