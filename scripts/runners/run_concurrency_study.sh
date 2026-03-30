#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMMON_SH="${PROJECT_ROOT}/scripts/common.sh"

# shellcheck source=/dev/null
source "${COMMON_SH}"

usage() {
  cat <<EOF
Usage: $0 [JAVA_VERSION] [DURATION] [VUS_LIST]

Run aggregate concurrency ramps for the specified Java version.

Arguments:
  JAVA_VERSION   Java version to test (17, 21, 25) [default: 21]
  DURATION       k6 duration per ramp (e.g. 20s, 1m) [default: 20s]
  VUS_LIST       Comma-separated VU ramp list [default: 2,10,25,50]

Environment:
  BENCHMARK_PROFILE   Output profile name [default: stock]
  APP_JVM_OPTS        Extra JVM flags for the Quarkus app
  PORT                Port for the Quarkus app [default: 8080]
  BENCHMARK_DATASOURCE_URL
  BENCHMARK_DATASOURCE_USERNAME
  BENCHMARK_DATASOURCE_PASSWORD

Examples:
  $0 21 20s 2,10,25,50
  BENCHMARK_PROFILE=tuned $0 25 30s 5,20,50
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

JAVA_VERSION="${1:-21}"
DURATION="${2:-20s}"
VUS_LIST="${3:-2,10,25,50}"
BENCHMARK_PROFILE="${BENCHMARK_PROFILE:-stock}"
BENCHMARK_LANE="${BENCHMARK_LANE:-host}"
BENCHMARK_RESULTS_ROOT="${BENCHMARK_RESULTS_ROOT:-${PROJECT_ROOT}/results/raw/${BENCHMARK_PROFILE}/${BENCHMARK_LANE}}"
APP_JVM_OPTS="${APP_JVM_OPTS:-}"

APP_DIR="quarkus-app"
RESULTS_ROOT="${BENCHMARK_RESULTS_ROOT}"
RESULTS_DIR="${RESULTS_ROOT}/java${JAVA_VERSION}/concurrency"
K6_SCRIPT="${PROJECT_ROOT}/infra/k6/aggregate.js"
PORT="${PORT:-8080}"

validate_java_version "${JAVA_VERSION}"
require_command mvn
require_command java
require_command curl
require_command k6
export BENCHMARK_JAVA_VERSION="${JAVA_VERSION}"

if [[ -z "${BENCHMARK_DATASOURCE_URL:-}" ]]; then
  error "BENCHMARK_DATASOURCE_URL must be set for the DB-backed aggregate workload."
  exit 1
fi

IFS=',' read -r -a VUS_VALUES <<< "${VUS_LIST}"
if [[ "${#VUS_VALUES[@]}" -eq 0 ]]; then
  error "VUS_LIST must contain at least one integer value."
  exit 1
fi

for vus in "${VUS_VALUES[@]}"; do
  if ! [[ "${vus}" =~ ^[0-9]+$ ]] || [[ "${vus}" -lt 1 ]]; then
    error "Invalid VU value '${vus}' in VUS_LIST."
    exit 1
  fi
done

cd "${PROJECT_ROOT}"
ensure_port_free "${PORT}"
mkdir -p "${RESULTS_DIR}"

info "Starting concurrency study"
info "Java version: ${JAVA_VERSION}"
info "Profile: ${BENCHMARK_PROFILE}"
info "Lane: ${BENCHMARK_LANE}"
info "Duration: ${DURATION}"
info "VU ramp: ${VUS_LIST}"
info "Results directory: ${RESULTS_DIR}"

build_app "${JAVA_VERSION}" "${APP_DIR}"
JAR_PATH=$(find_jar "${APP_DIR}")

APP_LOG_FILE="${RESULTS_DIR}/app-concurrency-java${JAVA_VERSION}.log"
APP_ID=$(start_app "${JAR_PATH}" "${APP_LOG_FILE}" "${APP_JVM_OPTS}" "${PORT}")
trap "cleanup_app ${APP_ID}" EXIT

wait_for_health "${PORT}" 60

modes=("platform")
if [[ "${JAVA_VERSION}" == "21" || "${JAVA_VERSION}" == "25" ]]; then
  modes+=("virtual")
fi

for vus in "${VUS_VALUES[@]}"; do
  for mode in "${modes[@]}"; do
    scenario="aggregate-${mode}"
    result_base="${scenario}-vus${vus}"
    summary_file="${RESULTS_DIR}/${result_base}-summary.txt"
    k6_json_file="${RESULTS_DIR}/${result_base}-k6.json"
    metrics_file="${RESULTS_DIR}/${result_base}-metrics.txt"

    info "Running ${scenario} concurrency ramp at ${vus} VUs"

    k6 run \
      --out "json=${k6_json_file}" \
      -e "BASE_URL=http://localhost:${PORT}" \
      -e "DURATION=${DURATION}" \
      -e "VUS=${vus}" \
      -e "AGG_MODE=${mode}" \
      "${K6_SCRIPT}" \
      | tee "${summary_file}"

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
      echo "scenario=${scenario}"
      echo "thread_mode=${mode}"
      echo "db_mode=jdbc"
      echo "run_class=concurrency"
      echo "vus=${vus}"
      echo "duration=${DURATION}"
      echo "summary_file=${summary_file}"
      echo "k6_json_file=${k6_json_file}"
      echo "log_file=${APP_LOG_FILE}"
    } > "${metrics_file}"
  done
done

success "Concurrency study completed for Java ${JAVA_VERSION}"
info "Results written to ${RESULTS_DIR}"
