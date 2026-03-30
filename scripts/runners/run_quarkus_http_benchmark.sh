#!/usr/bin/env bash
set -euo pipefail

# Java LTS Performance Lab - HTTP Load Test Runner
# Runs K6 load tests against Quarkus application

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Default values
JAVA_VERSION="${1:-21}"
SCENARIO="${2:-products}"
DURATION="${3:-20s}"
VUS="${4:-10}"
BENCHMARK_PROFILE="${BENCHMARK_PROFILE:-stock}"

# Constants
RESULTS_ROOT="${PROJECT_ROOT}/results/raw/${BENCHMARK_PROFILE}"
K6_DIR="${PROJECT_ROOT}/infra/k6"
PORT="${PORT:-8080}"

if [[ "$SCENARIO" =~ ^aggregate ]]; then
    K6_SCRIPT="${K6_DIR}/aggregate.js"
else
    K6_SCRIPT="${K6_DIR}/${SCENARIO}.js"
fi

RESULTS_DIR="${RESULTS_ROOT}/java${JAVA_VERSION}/quarkus"

usage() {
    cat << EOF
Usage: $0 [JAVA_VERSION] [SCENARIO] [DURATION] [VUS]

Run HTTP load test against Quarkus application using K6.

Arguments:
    JAVA_VERSION    Java version to test (17, 21, 25) [default: 21]
    SCENARIO        Test scenario (products, products-db, transform, mixed-workload, aggregate, aggregate-platform, aggregate-virtual) [default: products]
    DURATION        Test duration (e.g., 30s, 5m) [default: 20s]
    VUS             Number of virtual users [default: 10]

Environment:
    PORT            Port for Quarkus app [default: 8080]

Examples:
    $0 21 products 30s 20     # 20 VUs for 30s on products scenario
    $0 17 aggregate 1m 50     # 50 VUs for 1m on aggregate scenario

Requires Quarkus app to be running. Outputs to results/raw/java{JAVA_VERSION}/quarkus/
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

# Validate arguments
if ! [[ "$JAVA_VERSION" =~ ^(17|21|25)$ ]]; then
    echo "ERROR: Invalid JAVA_VERSION '$JAVA_VERSION'. Must be 17, 21, or 25." >&2
    exit 1
fi

if ! [[ "$SCENARIO" =~ ^(products|products-db|transform|mixed-workload|aggregate|aggregate-platform|aggregate-virtual)$ ]]; then
    echo "ERROR: Invalid SCENARIO '$SCENARIO'. Must be products, products-db, transform, mixed-workload, aggregate, aggregate-platform, or aggregate-virtual." >&2
    exit 1
fi

if ! [[ "$VUS" =~ ^[0-9]+$ ]] || [[ "$VUS" -lt 1 ]]; then
    echo "ERROR: VUS must be a positive integer." >&2
    exit 1
fi

# Change to project root
cd "${PROJECT_ROOT}"

RESULTS_DIR="${RESULTS_ROOT}/java${JAVA_VERSION}/quarkus"

if [[ ! -f "${K6_SCRIPT}" ]]; then
    echo "ERROR: K6 script not found: ${K6_SCRIPT}" >&2
    exit 1
fi

if ! command -v k6 >/dev/null 2>&1; then
    echo "ERROR: k6 is not installed or not available on PATH." >&2
    echo "Install it on macOS with: brew install k6" >&2
    exit 1
fi

mkdir -p "${RESULTS_DIR}"

echo "INFO: Starting HTTP load test"
echo "INFO: Java version: ${JAVA_VERSION}"
echo "INFO: Scenario: ${SCENARIO}"
echo "INFO: Profile: ${BENCHMARK_PROFILE}"
echo "INFO: Duration: ${DURATION}"
echo "INFO: Virtual users: ${VUS}"
echo "INFO: Results directory: ${RESULTS_DIR}"

# Validate app is reachable
echo "INFO: Validating Quarkus app is reachable..."
if ! curl -s "http://localhost:${PORT}/health" >/dev/null; then
    echo "ERROR: Quarkus app not reachable at http://localhost:${PORT}/health" >&2
    echo "Start the app first with: ./scripts/runners/run_quarkus_startup_benchmark.sh ${JAVA_VERSION}" >&2
    exit 1
fi

echo "INFO: Running K6 load test..."

EXTRA_ENV=""
if [[ "$SCENARIO" == "aggregate-platform" ]]; then
    EXTRA_ENV="-e AGG_MODE=platform"
elif [[ "$SCENARIO" == "aggregate-virtual" ]]; then
    EXTRA_ENV="-e AGG_MODE=virtual"
fi

k6 run \
    --out json="${RESULTS_DIR}/${SCENARIO}-k6.json" \
    -e BASE_URL="http://localhost:${PORT}" \
    -e DURATION="${DURATION}" \
    -e VUS="${VUS}" \
    ${EXTRA_ENV} \
    "${K6_SCRIPT}" | tee "${RESULTS_DIR}/${SCENARIO}-summary.txt"

echo "SUCCESS: HTTP load test completed for Java ${JAVA_VERSION}, scenario ${SCENARIO}"
echo "INFO: Results written to ${RESULTS_DIR}/${SCENARIO}-summary.txt and ${SCENARIO}-k6.json"
