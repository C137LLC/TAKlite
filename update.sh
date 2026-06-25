#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

SCRIPT_NAME="taklite-update"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_ROOT="/root/taklite-backups"

log() {
  printf '[%s] %s\n' "${SCRIPT_NAME}" "$*"
}

die() {
  printf '[%s] ERROR: %s\n' "${SCRIPT_NAME}" "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage:
  ./update.sh /root/TAKlite-vX.Y.Z.zip
  ./update.sh --release-zip /root/TAKlite-vX.Y.Z.zip
  ./update.sh --from-dir /root/staged/TAKlite --app-dir /root/taklite

This upgrades TAKlite application files while preserving:
  - /etc/wireguard
  - /root/taklite-admin
  - /opt/WGDashboard/src/wg-dashboard.ini
  - .env
  - taklite/data
  - taklite/certs
  - taklite/packages

Do not use this to make a snapshotted VPS into a new independent deployment.
Use a fresh install/rekey workflow for that.
EOF
}

need_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    die "run as root: sudo ./update.sh ..."
  fi
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

has_taklite_state() {
  local dir="$1"
  [[ -f "${dir}/docker-compose.yml" && -f "${dir}/.env" && -d "${dir}/taklite" ]]
}

detect_app_dir() {
  local candidates=()
  [[ -n "${APP_DIR:-}" ]] && candidates+=("${APP_DIR}")
  candidates+=("/root/taklite" "/root/TAKlite" "/root/taklite-vps-bundle" "${SCRIPT_DIR}")

  local candidate
  for candidate in "${candidates[@]}"; do
    if has_taklite_state "${candidate}"; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  return 1
}

stage_zip() {
  local zip_path="$1"
  local stage_dir="$2"

  [[ -f "${zip_path}" ]] || die "release zip not found: ${zip_path}"
  install -d -m 700 "${stage_dir}"

  ZIP_PATH="${zip_path}" STAGE_DIR="${stage_dir}" python3 - <<'PY'
import os
import pathlib
import zipfile

zip_path = pathlib.Path(os.environ["ZIP_PATH"])
stage_dir = pathlib.Path(os.environ["STAGE_DIR"])
with zipfile.ZipFile(zip_path) as zf:
    for member in zf.infolist():
        name = pathlib.PurePosixPath(member.filename)
        if name.is_absolute() or ".." in name.parts:
            raise SystemExit(f"unsafe zip entry: {member.filename}")
    zf.extractall(stage_dir)
PY
}

find_source_dir() {
  local root="$1"
  local compose dir

  while IFS= read -r compose; do
    dir="$(dirname "${compose}")"
    if [[ -f "${dir}/install.sh" && -d "${dir}/docker/taklite" ]]; then
      printf '%s\n' "${dir}"
      return 0
    fi
  done < <(find "${root}" -maxdepth 4 -name docker-compose.yml -type f | sort)

  return 1
}

backup_install() {
  local app_dir="$1"
  local backup_dir="$2"

  log "Backing up current TAKlite install to ${backup_dir}"
  install -d -m 700 "${BACKUP_ROOT}" "${backup_dir}" "${backup_dir}/app"
  rsync -a "${app_dir}/" "${backup_dir}/app/"

  local tar_items=()
  [[ -d /etc/wireguard ]] && tar_items+=("/etc/wireguard")
  [[ -d /root/taklite-admin ]] && tar_items+=("/root/taklite-admin")
  [[ -f /opt/WGDashboard/src/wg-dashboard.ini ]] && tar_items+=("/opt/WGDashboard/src/wg-dashboard.ini")

  if (( ${#tar_items[@]} )); then
    tar -czf "${backup_dir}/wireguard-admin-wgdashboard.tgz" "${tar_items[@]}" 2>/dev/null || true
  fi
}

append_env_default() {
  local env_file="$1"
  local key="$2"
  local value="$3"

  if ! grep -q "^${key}=" "${env_file}"; then
    printf '%s=%s\n' "${key}" "${value}" >>"${env_file}"
  fi
}

merge_env_defaults() {
  local env_file="$1"

  [[ -f "${env_file}" ]] || die "missing preserved .env at ${env_file}"

  append_env_default "${env_file}" "TAKLITE_CERT_PASSWORD" "atakatak"
  append_env_default "${env_file}" "TAKLITE_COT_HOST_PORT" "58087"
  append_env_default "${env_file}" "TAKLITE_COT_TLS_HOST_PORT" "8089"
  append_env_default "${env_file}" "TAKLITE_HTTP_HOST_PORT" "8080"
  append_env_default "${env_file}" "TAKLITE_HTTPS_HOST_PORT" "8443"
  append_env_default "${env_file}" "TAKLITE_WGDASHBOARD_URL" "http://10.66.66.1:10086"
  append_env_default "${env_file}" "TAKLITE_MAX_UPLOAD_BYTES" "268435456"
  append_env_default "${env_file}" "TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT" "false"
  append_env_default "${env_file}" "TAKLITE_ALLOW_LEGACY_CLIENT_CERT" "true"
  append_env_default "${env_file}" "TAKLITE_ACCESS_CONTROL_ENFORCE" "false"
  append_env_default "${env_file}" "TAKLITE_SOCKET_SEND_TIMEOUT_SECONDS" "2.5"
}

health_check() {
  local app_dir="$1"
  local host="10.66.66.1"
  local port="8080"

  if grep -q '^WG_BIND_IP=' "${app_dir}/.env"; then
    host="$(grep '^WG_BIND_IP=' "${app_dir}/.env" | tail -n1 | cut -d= -f2-)"
  fi
  if grep -q '^TAKLITE_HTTP_HOST_PORT=' "${app_dir}/.env"; then
    port="$(grep '^TAKLITE_HTTP_HOST_PORT=' "${app_dir}/.env" | tail -n1 | cut -d= -f2-)"
  fi

  log "Checking TAKlite health at http://${host}:${port}/api/health"
  curl -fsS "http://${host}:${port}/api/health" >/dev/null
}

APP_DIR="${APP_DIR:-}"
RELEASE_ZIP=""
SOURCE_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --app-dir)
      APP_DIR="${2:-}"
      [[ -n "${APP_DIR}" ]] || die "--app-dir requires a path"
      shift 2
      ;;
    --release-zip)
      RELEASE_ZIP="${2:-}"
      [[ -n "${RELEASE_ZIP}" ]] || die "--release-zip requires a path"
      shift 2
      ;;
    --from-dir)
      SOURCE_DIR="${2:-}"
      [[ -n "${SOURCE_DIR}" ]] || die "--from-dir requires a path"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    -*)
      die "unknown option: $1"
      ;;
    *)
      if [[ -z "${RELEASE_ZIP}" && -z "${SOURCE_DIR}" ]]; then
        RELEASE_ZIP="$1"
      else
        die "unexpected argument: $1"
      fi
      shift
      ;;
  esac
done

if [[ -z "${RELEASE_ZIP}" && -z "${SOURCE_DIR}" ]]; then
  usage
  die "provide a release zip, or pass --from-dir with a staged TAKlite source directory"
fi

need_root
require_command docker
require_command rsync
require_command python3
require_command curl

APP_DIR="$(detect_app_dir)" || die "could not find existing TAKlite app dir; pass --app-dir /root/taklite"
[[ -f "${APP_DIR}/docker-compose.yml" ]] || die "not a TAKlite app dir: ${APP_DIR}"
[[ -f "${APP_DIR}/.env" ]] || die "refusing update without preserved .env in ${APP_DIR}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="${BACKUP_ROOT}/${STAMP}"
STAGE_DIR="/root/taklite-update-${STAMP}"

if [[ -n "${RELEASE_ZIP}" ]]; then
  log "Staging release zip ${RELEASE_ZIP}"
  stage_zip "${RELEASE_ZIP}" "${STAGE_DIR}"
  SOURCE_DIR="$(find_source_dir "${STAGE_DIR}")" || die "could not find TAKlite source in ${RELEASE_ZIP}"
elif [[ -n "${SOURCE_DIR}" ]]; then
  [[ -f "${SOURCE_DIR}/docker-compose.yml" ]] || die "--from-dir is missing docker-compose.yml: ${SOURCE_DIR}"
fi

SOURCE_DIR="$(cd "${SOURCE_DIR}" && pwd)"
APP_DIR="$(cd "${APP_DIR}" && pwd)"

[[ "${SOURCE_DIR}" != "${APP_DIR}" ]] || die "source and app dir are the same; stage a new release zip or use --from-dir"

backup_install "${APP_DIR}" "${BACKUP_DIR}"

log "Stopping TAKlite container"
(
  cd "${APP_DIR}"
  docker compose down || true
)

log "Applying release files from ${SOURCE_DIR}"
rsync -a --delete \
  --exclude '.git/' \
  --exclude '.env' \
  --exclude 'taklite/' \
  "${SOURCE_DIR}/" "${APP_DIR}/"

chmod +x "${APP_DIR}/install.sh" "${APP_DIR}/smoke-test.sh" "${APP_DIR}/update.sh"
install -d -m 700 "${APP_DIR}/taklite/data" "${APP_DIR}/taklite/certs" "${APP_DIR}/taklite/packages"
chown -R 10001:10001 "${APP_DIR}/taklite/data" "${APP_DIR}/taklite/certs" "${APP_DIR}/taklite/packages"
merge_env_defaults "${APP_DIR}/.env"

log "Rebuilding and starting TAKlite"
(
  cd "${APP_DIR}"
  docker compose up -d --build
  docker compose ps
)

health_check "${APP_DIR}"

cat <<EOF

TAKlite update complete.

Backup:
  ${BACKUP_DIR}

Preserved:
  ${APP_DIR}/.env
  ${APP_DIR}/taklite/data
  ${APP_DIR}/taklite/certs
  ${APP_DIR}/taklite/packages
  /etc/wireguard
  /root/taklite-admin
  WGDashboard config, if present

EOF
