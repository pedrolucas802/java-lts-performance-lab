#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMMON_SH="${PROJECT_ROOT}/scripts/common.sh"

# shellcheck source=/dev/null
source "${COMMON_SH}"

usage() {
  cat <<EOF
Usage: $0 [JAVA_VERSION]

Run the JMH benchmark suite for the specified Java version.

Arguments:
  JAVA_VERSION   Java version to test (17, 21, 25) [default: 21]

Examples:
  $0 21
  $0 17
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

JAVA_VERSION="${1:-21}"
BENCHMARK_PROFILE="${BENCHMARK_PROFILE:-stock}"
BENCHMARK_LANE="${BENCHMARK_LANE:-host}"
BENCHMARK_RESULTS_ROOT="${BENCHMARK_RESULTS_ROOT:-results/raw/${BENCHMARK_PROFILE}/${BENCHMARK_LANE}}"
validate_java_version "${JAVA_VERSION}"
require_command mvn
require_command java

cd "${PROJECT_ROOT}"

RESULTS_DIR="${BENCHMARK_RESULTS_ROOT}/java${JAVA_VERSION}/jmh"
mkdir -p "${RESULTS_DIR}"

info "Running JMH suite for Java ${JAVA_VERSION}"

mvn -pl jmh-benchmarks clean package -Djava.release="${JAVA_VERSION}"

java -jar jmh-benchmarks/target/jmh-benchmarks.jar \
  -rf json \
  -rff "${RESULTS_DIR}/json-serialization-baseline.json"

success "JMH suite completed for Java ${JAVA_VERSION}"
