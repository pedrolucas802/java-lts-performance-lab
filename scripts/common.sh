#!/usr/bin/env bash
set -euo pipefail

# Common functions for Quarkus benchmark scripts

PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

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

benchmark_host_os() {
  local uname_value
  uname_value=$(uname -s | tr '[:upper:]' '[:lower:]')
  case "${uname_value}" in
    darwin*) echo "darwin" ;;
    linux*) echo "linux" ;;
    *) echo "${uname_value}" ;;
  esac
}

benchmark_lane() {
  echo "${BENCHMARK_LANE:-host}"
}

benchmark_container_runtime() {
  if [[ -n "${BENCHMARK_CONTAINER_RUNTIME:-}" ]]; then
    echo "${BENCHMARK_CONTAINER_RUNTIME}"
  elif [[ "$(benchmark_lane)" =~ container$ ]]; then
    echo "docker"
  else
    echo "none"
  fi
}

benchmark_cpu_limit() {
  echo "${BENCHMARK_CPU_LIMIT:-unlimited}"
}

benchmark_memory_limit_mb() {
  echo "${BENCHMARK_MEMORY_LIMIT_MB:-0}"
}

benchmark_loadgen_location() {
  echo "${BENCHMARK_LOADGEN_LOCATION:-host}"
}

benchmark_app_location() {
  echo "${BENCHMARK_APP_LOCATION:-host}"
}

app_is_container() {
  local app_id=$1
  [[ "${app_id}" == container:* ]]
}

container_name_from_app_id() {
  local app_id=$1
  echo "${app_id#container:}"
}

container_memory_to_kb() {
  local raw_value=$1
  local number unit

  number=$(echo "${raw_value}" | sed -E 's/^([0-9.]+).*/\1/')
  unit=$(echo "${raw_value}" | sed -E 's/^[0-9.]+([A-Za-z]+).*/\1/')

  case "${unit}" in
    B)
      awk "BEGIN {printf \"%d\", ${number} / 1024}"
      ;;
    KB|kB|KiB)
      awk "BEGIN {printf \"%d\", ${number}}"
      ;;
    MB|MiB)
      awk "BEGIN {printf \"%d\", ${number} * 1024}"
      ;;
    GB|GiB)
      awk "BEGIN {printf \"%d\", ${number} * 1024 * 1024}"
      ;;
    *)
      echo 0
      ;;
  esac
}

rewrite_datasource_url_for_container() {
  local datasource_url=$1
  echo "${datasource_url}" | sed -E 's/(jdbc:postgresql:\/\/)(localhost|127\.0\.0\.1)(:.*)$/\1host.docker.internal\3/'
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

start_container_app() {
  local jar_path=$1
  local log_file=$2
  local jvm_opts=${3:-}
  local port=${4:-8080}

  require_command docker

  local java_version="${BENCHMARK_JAVA_VERSION:-21}"
  local container_name
  container_name="java-lts-lab-${java_version}-${port}-$(date +%s)"

  local docker_args=(
    run
    -d
    --name "${container_name}"
    -p "${port}:8080"
    -v "${PROJECT_ROOT}:${PROJECT_ROOT}"
    -w "${PROJECT_ROOT}"
    -e "JAVA_TOOL_OPTIONS=${jvm_opts}"
    -e "BENCHMARK_DATASOURCE_USERNAME=${BENCHMARK_DATASOURCE_USERNAME:-benchmark}"
    -e "BENCHMARK_DATASOURCE_PASSWORD=${BENCHMARK_DATASOURCE_PASSWORD:-benchmark}"
    -e "BENCHMARK_DATASOURCE_INITIAL_SIZE=${BENCHMARK_DATASOURCE_INITIAL_SIZE:-2}"
    -e "BENCHMARK_DATASOURCE_MIN_SIZE=${BENCHMARK_DATASOURCE_MIN_SIZE:-2}"
    -e "BENCHMARK_DATASOURCE_MAX_SIZE=${BENCHMARK_DATASOURCE_MAX_SIZE:-16}"
    -e "BENCHMARK_DATASOURCE_ACQUISITION_TIMEOUT_SECONDS=${BENCHMARK_DATASOURCE_ACQUISITION_TIMEOUT_SECONDS:-2}"
  )

  if [[ -n "${BENCHMARK_DATASOURCE_URL:-}" ]]; then
    docker_args+=(
      -e
      "BENCHMARK_DATASOURCE_URL=$(rewrite_datasource_url_for_container "${BENCHMARK_DATASOURCE_URL}")"
    )
  fi

  if [[ "$(benchmark_host_os)" == "linux" ]]; then
    docker_args+=(--add-host "host.docker.internal:host-gateway")
  fi

  if [[ "$(benchmark_cpu_limit)" != "unlimited" ]]; then
    docker_args+=(--cpus "$(benchmark_cpu_limit)")
  fi

  if [[ "$(benchmark_memory_limit_mb)" != "0" ]]; then
    docker_args+=(--memory "$(benchmark_memory_limit_mb)m")
  fi

  local start_cmd
  start_cmd="java \${JAVA_TOOL_OPTIONS:-} -Dquarkus.http.port=8080 -jar '${jar_path}' > '${log_file}' 2>&1"

  docker_args+=(
    "eclipse-temurin:${java_version}-jre"
    /bin/sh
    -lc
    "${start_cmd}"
  )

  info "Starting containerized app from ${jar_path} on port ${port}..."
  docker "${docker_args[@]}" >/dev/null

  echo "container:${container_name}"
}

start_app() {
  local jar_path=$1
  local log_file=$2
  local jvm_opts=${3:-}
  local port=${4:-8080}

  if [[ "$(benchmark_app_location)" == "container" ]]; then
    start_container_app "${jar_path}" "${log_file}" "${jvm_opts}" "${port}"
    return 0
  fi

  info "Starting app from ${jar_path} on port ${port}..."

  java ${jvm_opts} \
    -Dquarkus.http.port="${port}" \
    -jar "${jar_path}" \
    > "${log_file}" 2>&1 &

  echo $!
}

get_app_snapshot() {
  local app_id=$1

  if app_is_container "${app_id}"; then
    local container_name snapshot cpu_percent mem_usage raw_memory_kb
    container_name=$(container_name_from_app_id "${app_id}")

    snapshot=$(docker stats --no-stream --format '{{.CPUPerc}},{{.MemUsage}}' "${container_name}" 2>/dev/null | head -n 1)
    if [[ -z "${snapshot}" ]]; then
      return 1
    fi

    cpu_percent=$(echo "${snapshot}" | cut -d',' -f1 | tr -d '%' | xargs)
    mem_usage=$(echo "${snapshot}" | cut -d',' -f2 | cut -d'/' -f1 | xargs)
    raw_memory_kb=$(container_memory_to_kb "${mem_usage}")

    echo "${cpu_percent:-0},${raw_memory_kb:-0},"
    return 0
  fi

  if ! ps -p "${app_id}" >/dev/null 2>&1; then
    return 1
  fi

  ps -p "${app_id}" -o %cpu= -o rss= -o time= | awk 'NF {print $1","$2","$3; exit}'
}

get_rss_kb() {
  local app_id=$1
  local snapshot

  if ! snapshot=$(get_app_snapshot "${app_id}"); then
    error "Application identity ${app_id} is not running."
    return 1
  fi

  echo "${snapshot}" | cut -d',' -f2 | xargs
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
  local app_id=$1

  if app_is_container "${app_id}"; then
    local container_name
    container_name=$(container_name_from_app_id "${app_id}")
    docker rm -f "${container_name}" >/dev/null 2>&1 || true
    return 0
  fi

  if ps -p "${app_id}" >/dev/null 2>&1; then
    kill "${app_id}" || true
    wait "${app_id}" 2>/dev/null || true
  fi
}
