#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

SCRIPT_NAME="taklite-uninstall"
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
  ./uninstall.sh --yes
  ./uninstall.sh --yes --app-dir /root/TAKlite

This removes TAKlite, WGDashboard, WireGuard config, generated admin files,
certs, datapackages, database, install backups, and TAKlite runtime state.

WARNING:
  This stops WireGuard and will drop SSH sessions connected through the VPN.
  Make sure public SSH/22 is open or otherwise reachable on the VPS before
  proceeding, or you can lock yourself out.

It intentionally does not remove system packages such as docker, git, rsync,
wireguard-tools, fail2ban, or qrencode because other services may use them.

This is destructive. Use update.sh for normal upgrades.
EOF
}

need_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    die "run as root: sudo ./uninstall.sh --yes"
  fi
}

warn_disconnect() {
  cat <<'EOF'

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
TAKlite destructive uninstall warning

This will stop WireGuard, remove /etc/wireguard, remove WGDashboard,
delete TAKlite certs, users, datapackages, database, generated packages,
admin recovery files, and backups.

If you are SSH'd into this VPS over the WireGuard tunnel, this command can
drop the current shell before it finishes.

Before continuing, make sure the VPS firewall allows SSH on port 22 from a
network you can reach, or have console/VPS provider access ready.

Press Ctrl-C now to abort.
Continuing in 10 seconds...
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

EOF
  sleep 10
}

detect_app_dirs() {
  local dirs=()
  [[ -n "${APP_DIR}" ]] && dirs+=("${APP_DIR}")
  dirs+=("/root/taklite" "/root/TAKlite" "/root/taklite-vps-bundle")

  local seen="" dir
  for dir in "${dirs[@]}"; do
    [[ -n "${dir}" ]] || continue
    [[ -d "${dir}" ]] || continue
    case " ${seen} " in
      *" ${dir} "*) continue ;;
    esac
    seen="${seen} ${dir}"
    printf '%s\n' "${dir}"
  done
}

run_compose_down() {
  local dir="$1"
  if [[ -f "${dir}/docker-compose.yml" ]]; then
    log "Stopping TAKlite compose stack in ${dir}"
    (cd "${dir}" && docker compose down --remove-orphans) || true
  fi
}

stop_taklite_container() {
  if command -v docker >/dev/null 2>&1; then
    log "Removing TAKlite container if present"
    docker rm -f taklite >/dev/null 2>&1 || true
  fi
}

stop_wgdashboard() {
  log "Stopping WGDashboard service if present"
  systemctl disable --now wg-dashboard.service >/dev/null 2>&1 || true
  if [[ -x /opt/WGDashboard/src/wgd.sh ]]; then
    (cd /opt/WGDashboard/src && ./wgd.sh stop) >/dev/null 2>&1 || true
  fi
  rm -f /etc/systemd/system/wg-dashboard.service
  systemctl daemon-reload >/dev/null 2>&1 || true
}

stop_wireguard() {
  local conf name
  shopt -s nullglob
  for conf in /etc/wireguard/*.conf; do
    name="$(basename "${conf}" .conf)"
    log "Stopping WireGuard interface ${name}"
    systemctl disable --now "wg-quick@${name}" >/dev/null 2>&1 || true
    wg-quick down "${name}" >/dev/null 2>&1 || true
  done
  shopt -u nullglob
}

remove_fail2ban_config() {
  log "Removing TAKlite fail2ban jail"
  rm -f /etc/fail2ban/jail.d/taklite-vps.local
  systemctl restart fail2ban >/dev/null 2>&1 || true
}

remove_files() {
  log "Removing TAKlite and VPN state"
  rm -rf \
    /etc/wireguard \
    /etc/sysctl.d/99-taklite-wireguard.conf \
    /root/taklite-admin \
    /root/taklite-backups \
    /root/taklite-rekey-backups \
    /root/TAKlite-update \
    /root/taklite-update-stage \
    /opt/WGDashboard

  local dir
  while IFS= read -r dir; do
    case "${dir}" in
      /|/root|/opt|/etc|/tmp|/private/tmp)
        die "refusing unsafe app dir removal: ${dir}"
        ;;
    esac
    log "Removing app directory ${dir}"
    rm -rf "${dir}"
  done < <(detect_app_dirs)
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
    die "refusing destructive uninstall without --yes"
  fi

  need_root
  warn_disconnect

  local dir
  while IFS= read -r dir; do
    run_compose_down "${dir}"
  done < <(detect_app_dirs)

  stop_taklite_container
  stop_wgdashboard
  stop_wireguard
  remove_fail2ban_config
  remove_files

  log "Uninstall complete. TAKlite, WGDashboard, WireGuard config, and TAKlite state were removed."
}

main "$@"
