#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMMON_SH="${PROJECT_ROOT}/scripts/common.sh"

# shellcheck source=/dev/null
source "${COMMON_SH}"

usage() {
  cat <<EOF
Usage: $0 [JAVA_VERSION] [DURATION] [VUS] [SCENARIOS_CSV]

Run the Quarkus HTTP scenario suite against a single started application.

Arguments:
  JAVA_VERSION   Java version to test (17, 21, 25) [default: 21]
  DURATION       k6 duration per scenario [default: 20s]
  VUS            k6 virtual users per scenario [default: 10]
  SCENARIOS_CSV  Comma-separated scenarios to run
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

JAVA_VERSION="${1:-21}"
DURATION="${2:-20s}"
VUS="${3:-10}"
SCENARIOS_CSV="${4:-}"
BENCHMARK_PROFILE="${BENCHMARK_PROFILE:-stock}"
BENCHMARK_LANE="${BENCHMARK_LANE:-host}"
APP_JVM_OPTS="${APP_JVM_OPTS:-}"
PORT="${PORT:-8080}"
BENCHMARK_RESULTS_ROOT="${BENCHMARK_RESULTS_ROOT:-${PROJECT_ROOT}/results/raw/${BENCHMARK_PROFILE}/${BENCHMARK_LANE}}"

validate_java_version "${JAVA_VERSION}"
require_command mvn
require_command java
require_command curl

export BENCHMARK_JAVA_VERSION="${JAVA_VERSION}"
export BENCHMARK_RESULTS_ROOT

cd "${PROJECT_ROOT}"
ensure_port_free "${PORT}"

APP_DIR="quarkus-app"
RESULTS_DIR="${BENCHMARK_RESULTS_ROOT}/java${JAVA_VERSION}/quarkus"
mkdir -p "${RESULTS_DIR}"

if [[ -z "${SCENARIOS_CSV}" ]]; then
  scenarios=("products" "products-db" "transform" "aggregate-platform")
  if [[ "${JAVA_VERSION}" == "21" || "${JAVA_VERSION}" == "25" ]]; then
    scenarios+=("aggregate-virtual")
  fi
else
  IFS=',' read -r -a scenarios <<< "${SCENARIOS_CSV}"
fi

info "Starting Quarkus HTTP suite"
info "Java version: ${JAVA_VERSION}"
info "Profile: ${BENCHMARK_PROFILE}"
info "Lane: ${BENCHMARK_LANE}"
info "Duration: ${DURATION}"
info "VUs: ${VUS}"
info "Scenarios: ${scenarios[*]}"

build_app "${JAVA_VERSION}" "${APP_DIR}"
JAR_PATH=$(find_jar "${APP_DIR}")

APP_LOG_FILE="${RESULTS_DIR}/app-suite-java${JAVA_VERSION}.log"
APP_ID=$(start_app "${JAR_PATH}" "${APP_LOG_FILE}" "${APP_JVM_OPTS}" "${PORT}")
trap "cleanup_app ${APP_ID}" EXIT

wait_for_health "${PORT}" 60

for scenario in "${scenarios[@]}"; do
  bash "${SCRIPT_DIR}/run_quarkus_http_benchmark.sh" "${JAVA_VERSION}" "${scenario}" "${DURATION}" "${VUS}"
done

success "Quarkus HTTP suite completed for Java ${JAVA_VERSION}"
