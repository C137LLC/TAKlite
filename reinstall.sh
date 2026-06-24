#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

SCRIPT_NAME="taklite-reinstall"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR=""
YES=false

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
  ./reinstall.sh --yes
  ./reinstall.sh --yes --app-dir /root/TAKlite

This performs a destructive reinstall:
  1. Stages the current TAKlite source in /tmp
  2. Runs uninstall.sh --yes
  3. Recreates the selected app directory
  4. Copies the staged source back
  5. Runs install.sh for a fresh install

WARNING:
  This stops WireGuard and will drop SSH sessions connected through the VPN.
  Make sure public SSH/22 is open or otherwise reachable on the VPS before
  proceeding, or you can lock yourself out.

Use update.sh for normal upgrades that preserve users, certs, ports, and data.
EOF
}

need_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    die "run as root: sudo ./reinstall.sh --yes"
  fi
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

detect_existing_app_dir() {
  local candidate
  for candidate in "/root/taklite" "/root/TAKlite" "/root/taklite-vps-bundle"; do
    if [[ -f "${candidate}/docker-compose.yml" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  return 1
}

default_app_dir() {
  if [[ -n "${APP_DIR}" ]]; then
    printf '%s\n' "${APP_DIR}"
    return 0
  fi

  case "${SCRIPT_DIR}" in
    /root/taklite|/root/TAKlite|/root/taklite-vps-bundle)
      printf '%s\n' "${SCRIPT_DIR}"
      return 0
      ;;
  esac

  detect_existing_app_dir && return 0
  printf '%s\n' "/root/taklite"
}

stage_source() {
  local stage="$1"
  log "Staging TAKlite source to ${stage}"
  rm -rf "${stage}"
  install -d -m 700 "${stage}"
  rsync -a --delete \
    --exclude '.git/' \
    --exclude '.env' \
    --exclude 'taklite/' \
    --exclude 'frontend/node_modules/' \
    --exclude 'frontend/dist/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '*.zip' \
    "${SCRIPT_DIR}/" "${stage}/"
}

copy_source_to_app_dir() {
  local stage="$1"
  local app_dir="$2"

  case "${app_dir}" in
    /|/root|/opt|/etc|/tmp|/private/tmp)
      die "refusing unsafe app dir: ${app_dir}"
      ;;
  esac

  log "Recreating app directory ${app_dir}"
  rm -rf "${app_dir}"
  install -d -m 700 "${app_dir}"
  rsync -a "${stage}/" "${app_dir}/"
  chmod +x "${app_dir}/install.sh" "${app_dir}/update.sh" "${app_dir}/uninstall.sh" "${app_dir}/reinstall.sh" "${app_dir}/smoke-test.sh"
}

main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --yes|-y)
        YES=true
        shift
        ;;
      --app-dir)
        APP_DIR="${2:-}"
        [[ -n "${APP_DIR}" ]] || die "--app-dir requires a path"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "unknown argument: $1"
        ;;
    esac
  done

  if [[ "${YES}" != "true" ]]; then
    usage
    die "refusing destructive reinstall without --yes"
  fi

  need_root
  require_command rsync

  local app_dir stage
  app_dir="$(default_app_dir)"
  stage="/tmp/taklite-reinstall-source-$(date -u +%Y%m%dT%H%M%SZ)"

  cat <<EOF

TAKlite reinstall target:
  ${app_dir}

This will wipe the current TAKlite/WireGuard/WGDashboard identity and create
a fresh install with new VPN keys, TAKlite CA, certs, tokens, and admin state.

EOF

  stage_source "${stage}"
  bash "${stage}/uninstall.sh" --yes --app-dir "${app_dir}"
  copy_source_to_app_dir "${stage}" "${app_dir}"

  log "Starting fresh install from ${app_dir}"
  (
    cd "${app_dir}"
    ./install.sh
  )

  rm -rf "${stage}"
  log "Reinstall complete"
}

main "$@"
