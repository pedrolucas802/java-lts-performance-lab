#!/usr/bin/env bash
set -euo pipefail

JAVA_VERSION="${1:-21}"
SCENARIO="${2:-products}"
PORT="${PORT:-8080}"
DURATION="${DURATION:-20s}"

APP_DIR="quarkus-app"
RESULTS_DIR="results/raw/java${JAVA_VERSION}/memory"
mkdir -p "${RESULTS_DIR}"

echo "Building Quarkus app for Java ${JAVA_VERSION}..."
mvn -q -pl "${APP_DIR}" clean package -DskipTests -Djava.release="${JAVA_VERSION}"

JAR_PATH=$(find "${APP_DIR}/target/quarkus-app" -name "quarkus-run.jar" | head -n 1)

if [[ -z "${JAR_PATH}" ]]; then
  echo "Could not find quarkus-run.jar"
  exit 1
fi

LOG_FILE="${RESULTS_DIR}/${SCENARIO}-memory-java${JAVA_VERSION}.log"
METRICS_FILE="${RESULTS_DIR}/${SCENARIO}-memory-java${JAVA_VERSION}.txt"

echo "Starting app..."
java -jar "${JAR_PATH}" > "${LOG_FILE}" 2>&1 &
APP_PID=$!

cleanup() {
  if ps -p "${APP_PID}" >/dev/null 2>&1; then
    kill "${APP_PID}" || true
    wait "${APP_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

for _ in {1..300}; do
  if curl -s "http://localhost:${PORT}/health" >/dev/null; then
    break
  fi
  sleep 0.1
done

if ! ps -p "${APP_PID}" >/dev/null 2>&1; then
  echo "App process exited unexpectedly."
  exit 1
fi

IDLE_RSS_KB=$(ps -o rss= -p "${APP_PID}" | xargs)
echo "Idle RSS: ${IDLE_RSS_KB} KB"

case "${SCENARIO}" in
  products)
    k6 run \
      --out json="${RESULTS_DIR}/${SCENARIO}-k6.json" \
      -e BASE_URL="http://localhost:${PORT}" \
      -e DURATION="${DURATION}" \
      infra/k6/products.js \
      > "${RESULTS_DIR}/${SCENARIO}-summary.txt"
    ;;
  transform)
    k6 run \
      --out json="${RESULTS_DIR}/${SCENARIO}-k6.json" \
      -e BASE_URL="http://localhost:${PORT}" \
      -e DURATION="${DURATION}" \
      infra/k6/transform.js \
      > "${RESULTS_DIR}/${SCENARIO}-summary.txt"
    ;;
  aggregate-platform)
    k6 run \
      --out json="${RESULTS_DIR}/${SCENARIO}-k6.json" \
      -e BASE_URL="http://localhost:${PORT}" \
      -e DURATION="${DURATION}" \
      -e AGG_MODE="platform" \
      infra/k6/aggregate.js \
      > "${RESULTS_DIR}/${SCENARIO}-summary.txt"
    ;;
  aggregate-virtual)
    k6 run \
      --out json="${RESULTS_DIR}/${SCENARIO}-k6.json" \
      -e BASE_URL="http://localhost:${PORT}" \
      -e DURATION="${DURATION}" \
      -e AGG_MODE="virtual" \
      infra/k6/aggregate.js \
      > "${RESULTS_DIR}/${SCENARIO}-summary.txt"
    ;;
  *)
    echo "Unsupported scenario: ${SCENARIO}"
    exit 1
    ;;
esac

POST_LOAD_RSS_KB=$(ps -o rss= -p "${APP_PID}" | xargs)
echo "Post-load RSS: ${POST_LOAD_RSS_KB} KB"

{
  echo "java_version=${JAVA_VERSION}"
  echo "scenario=${SCENARIO}"
  echo "idle_rss_kb=${IDLE_RSS_KB}"
  echo "post_load_rss_kb=${POST_LOAD_RSS_KB}"
  echo "rss_delta_kb=$((POST_LOAD_RSS_KB - IDLE_RSS_KB))"
  echo "pid=${APP_PID}"
  echo "log_file=${LOG_FILE}"
} > "${METRICS_FILE}"

echo "Memory benchmark complete:"
cat "${METRICS_FILE}"


#	•	builds the app
#	•	starts it
#	•	measures idle RSS
#	•	runs one load scenario
#	•	measures RSS again
#	•	stores everything under results/raw/javaXX/memory/