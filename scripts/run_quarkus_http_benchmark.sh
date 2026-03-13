#!/usr/bin/env bash
set -euo pipefail

JAVA_VERSION="${1:-21}"
SCENARIO="${2:-products}"
RESULTS_DIR="results/raw/java${JAVA_VERSION}/quarkus"
K6_SCRIPT="infra/k6/${SCENARIO}.js"
PORT="${PORT:-8080}"
DURATION="${DURATION:-20s}"

mkdir -p "${RESULTS_DIR}"

if [[ ! -f "${K6_SCRIPT}" ]]; then
  echo "K6 script not found: ${K6_SCRIPT}"
  exit 1
fi

if ! command -v k6 >/dev/null 2>&1; then
  echo "k6 is not installed or not available on PATH."
  echo "Install it on macOS with: brew install k6"
  exit 1
fi

echo "Running HTTP benchmark for scenario: ${SCENARIO}"
echo "Results dir: ${RESULTS_DIR}"

k6 run \
  --out json="${RESULTS_DIR}/${SCENARIO}-k6.json" \
  -e BASE_URL="http://localhost:${PORT}" \
  -e DURATION="${DURATION}" \
  "${K6_SCRIPT}" | tee "${RESULTS_DIR}/${SCENARIO}-summary.txt"