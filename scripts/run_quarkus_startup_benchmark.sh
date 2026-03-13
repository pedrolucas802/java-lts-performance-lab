#!/usr/bin/env bash
set -euo pipefail

APP_DIR="quarkus-app"
RESULTS_DIR="results/raw"
JAVA_VERSION="${1:-21}"
PORT="${PORT:-8080}"
MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-60}"

mkdir -p "${RESULTS_DIR}/java${JAVA_VERSION}/quarkus"

echo "Building Quarkus app for Java ${JAVA_VERSION}..."
mvn -q -pl "${APP_DIR}" clean package -DskipTests

JAR_PATH=$(find "${APP_DIR}/target/quarkus-app" -name "quarkus-run.jar" | head -n 1)

if [[ -z "${JAR_PATH}" ]]; then
  echo "Could not find quarkus-run.jar"
  exit 1
fi

LOG_FILE="${RESULTS_DIR}/java${JAVA_VERSION}/quarkus/startup-java${JAVA_VERSION}.log"
METRICS_FILE="${RESULTS_DIR}/java${JAVA_VERSION}/quarkus/startup-java${JAVA_VERSION}.txt"

echo "Starting app from ${JAR_PATH}..."
START_NS=$(date +%s%N)

java -jar "${JAR_PATH}" > "${LOG_FILE}" 2>&1 &
APP_PID=$!

cleanup() {
  if ps -p "${APP_PID}" > /dev/null 2>&1; then
    kill "${APP_PID}" || true
    wait "${APP_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

SUCCESS=0
for ((i=1; i<=MAX_WAIT_SECONDS*10; i++)); do
  if curl -s "http://localhost:${PORT}/health" > /dev/null; then
    END_NS=$(date +%s%N)
    SUCCESS=1
    break
  fi
  sleep 0.1
done

if [[ "${SUCCESS}" -ne 1 ]]; then
  echo "Application did not become healthy within ${MAX_WAIT_SECONDS} seconds."
  exit 1
fi

STARTUP_MS=$(( (END_NS - START_NS) / 1000000 ))

echo "java_version=${JAVA_VERSION}" > "${METRICS_FILE}"
echo "startup_ms=${STARTUP_MS}" >> "${METRICS_FILE}"
echo "port=${PORT}" >> "${METRICS_FILE}"
echo "log_file=${LOG_FILE}" >> "${METRICS_FILE}"

echo "Startup benchmark complete:"
cat "${METRICS_FILE}"