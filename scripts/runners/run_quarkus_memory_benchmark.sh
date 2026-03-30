#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

JAVA_VERSION="${1:-21}"
SCENARIO="${2:-products}"
HEAP_INFO="${HEAP_INFO:-false}"
VUS="${VUS:-20}"
BENCHMARK_PROFILE="${BENCHMARK_PROFILE:-stock}"
BENCHMARK_LANE="${BENCHMARK_LANE:-host}"
BENCHMARK_RESULTS_ROOT="${BENCHMARK_RESULTS_ROOT:-${PROJECT_ROOT}/results/raw/${BENCHMARK_PROFILE}/${BENCHMARK_LANE}}"
APP_JVM_OPTS="${APP_JVM_OPTS:-}"

APP_DIR="quarkus-app"
RESULTS_ROOT="${BENCHMARK_RESULTS_ROOT}"
K6_DIR="${PROJECT_ROOT}/infra/k6"

PORT="${PORT:-8081}"
DURATION="${DURATION:-20s}"

cd "${PROJECT_ROOT}"

source "${PROJECT_ROOT}/scripts/common.sh"
export BENCHMARK_JAVA_VERSION="${JAVA_VERSION}"

validate_java_version "${JAVA_VERSION}"
require_command mvn
require_command java
require_command curl
require_command k6

ensure_port_free "${PORT}"

RESULTS_DIR="${RESULTS_ROOT}/java${JAVA_VERSION}/memory"
mkdir -p "${RESULTS_DIR}"

if [[ "$SCENARIO" =~ ^aggregate ]]; then
    K6_SCRIPT="${K6_DIR}/aggregate.js"
else
    K6_SCRIPT="${K6_DIR}/${SCENARIO}.js"
fi

if ! [[ "$SCENARIO" =~ ^(products|products-db|transform|mixed-workload|aggregate|aggregate-platform|aggregate-virtual)$ ]]; then
    error "Invalid SCENARIO '$SCENARIO'. Must be products, products-db, transform, mixed-workload, aggregate, aggregate-platform, or aggregate-virtual."
    exit 1
fi

if [[ ! -f "${K6_SCRIPT}" ]]; then
    error "K6 script not found: ${K6_SCRIPT}"
    exit 1
fi

info "Starting memory benchmark"
info "Java version: ${JAVA_VERSION}"
info "Scenario: ${SCENARIO}"
info "Profile: ${BENCHMARK_PROFILE}"
info "Lane: ${BENCHMARK_LANE}"
info "Results directory: ${RESULTS_DIR}"

build_app "${JAVA_VERSION}" "${APP_DIR}"

JAR_PATH=$(find_jar "${APP_DIR}")

LOG_FILE="${RESULTS_DIR}/${SCENARIO}-memory-java${JAVA_VERSION}.log"
METRICS_FILE="${RESULTS_DIR}/${SCENARIO}-memory-java${JAVA_VERSION}.txt"

JVM_OPTS="${APP_JVM_OPTS}"

if [[ "${HEAP_INFO}" == "true" ]]; then
    JVM_OPTS="${JVM_OPTS} -XX:+PrintGC"
fi

info "Starting Quarkus app..."

APP_ID=$(start_app "${JAR_PATH}" "${LOG_FILE}" "${JVM_OPTS}" "${PORT}")

trap "cleanup_app ${APP_ID}" EXIT

wait_for_health "${PORT}" 60

IDLE_RSS_KB=$(get_rss_kb "${APP_ID}")
info "Idle RSS: ${IDLE_RSS_KB} KB"

SUMMARY_FILE="${RESULTS_DIR}/${SCENARIO}-summary.txt"
K6_JSON_FILE="${RESULTS_DIR}/${SCENARIO}-k6.json"

info "Running load test..."

EXTRA_ENV=()
if [[ "$SCENARIO" == "aggregate-platform" ]]; then
    EXTRA_ENV+=(-e "AGG_MODE=platform")
elif [[ "$SCENARIO" == "aggregate-virtual" ]]; then
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

sleep 1

POST_LOAD_RSS_KB=$(get_rss_kb "${APP_ID}")

info "Post-load RSS: ${POST_LOAD_RSS_KB} KB"

RSS_DELTA_KB=$((POST_LOAD_RSS_KB - IDLE_RSS_KB))

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
echo "idle_rss_kb=${IDLE_RSS_KB}"
echo "post_load_rss_kb=${POST_LOAD_RSS_KB}"
echo "rss_delta_kb=${RSS_DELTA_KB}"
echo "pid=${APP_ID}"
echo "log_file=${LOG_FILE}"
echo "summary_file=${SUMMARY_FILE}"
echo "k6_json_file=${K6_JSON_FILE}"
} > "${METRICS_FILE}"

success "Memory benchmark completed"
info "Results written to ${METRICS_FILE}"
