#!/usr/bin/env bash
set -euo pipefail

# Common functions for Quarkus benchmark scripts

info() {
  echo "INFO: $*" >&2
}

success() {
  echo "SUCCESS: $*" >&2
}

error() {
  echo "ERROR: $*" >&2
}

validate_java_version() {
  local java_version=$1
  case "${java_version}" in
    17|21|25) ;;
    *)
      error "JAVA_VERSION must be one of: 17, 21, 25"
      exit 1
      ;;
  esac
}

require_command() {
  local cmd=$1
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    error "Required command not found on PATH: ${cmd}"
    exit 1
  fi
}

ensure_port_free() {
  local port=$1
  if command -v lsof >/dev/null 2>&1; then
    if lsof -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
      error "Port ${port} is already in use."
      exit 1
    fi
  fi
}

get_rss_kb() {
  local app_pid=$1

  if ! ps -p "${app_pid}" >/dev/null 2>&1; then
    error "Process ${app_pid} is not running."
    return 1
  fi

  ps -o rss= -p "${app_pid}" | xargs
}

build_app() {
  local java_version=$1
  local app_dir=$2

  info "Building Quarkus app for Java ${java_version}..."

  mvn -q -pl "${app_dir}" clean package \
    -DskipTests \
    -Djava.release="${java_version}"
}

find_jar() {
  local app_dir=$1

  local jar_path
  jar_path=$(find "${app_dir}/target/quarkus-app" -name "quarkus-run.jar" | head -n 1)

  if [[ -z "${jar_path}" ]]; then
    error "Could not find quarkus-run.jar"
    exit 1
  fi

  echo "${jar_path}"
}

start_app() {
  local jar_path=$1
  local log_file=$2
  local jvm_opts=${3:-}
  local port=${4:-8080}

  info "Starting app from ${jar_path} on port ${port}..."

  java ${jvm_opts} \
    -Dquarkus.http.port="${port}" \
    -jar "${jar_path}" \
    > "${log_file}" 2>&1 &

  echo $!
}

wait_for_health() {
  local port=$1
  local max_wait_seconds=$2

  local success=0

  for ((i=1; i<=max_wait_seconds*10; i++)); do
    if curl -s "http://localhost:${port}/health" >/dev/null; then
      success=1
      break
    fi
    sleep 0.1
  done

  if [[ "${success}" -ne 1 ]]; then
    error "Application did not become healthy within ${max_wait_seconds} seconds."
    return 1
  fi

  return 0
}

cleanup_app() {
  local app_pid=$1

  if ps -p "${app_pid}" >/dev/null 2>&1; then
    kill "${app_pid}" || true
    wait "${app_pid}" 2>/dev/null || true
  fi
}