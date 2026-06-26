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

set_env_value() {
  local env_file="$1"
  local key="$2"
  local value="$3"

  if grep -q "^${key}=" "${env_file}"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "${env_file}"
  else
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
  append_env_default "${env_file}" "TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT" "true"
  append_env_default "${env_file}" "TAKLITE_ALLOW_LEGACY_CLIENT_CERT" "false"
  append_env_default "${env_file}" "TAKLITE_ACCESS_CONTROL_ENFORCE" "true"
  append_env_default "${env_file}" "TAKLITE_SOCKET_SEND_TIMEOUT_SECONDS" "2.5"
  append_env_default "${env_file}" "TAKLITE_GUI_UPDATE_ENABLED" "true"
  append_env_default "${env_file}" "TAKLITE_GUI_UPDATE_COMMAND" ""
  append_env_default "${env_file}" "TAKLITE_GUI_UPDATE_WORKDIR" ""
  append_env_default "${env_file}" "TAKLITE_GUI_UPDATE_TIMEOUT_SECONDS" "900"
  append_env_default "${env_file}" "TAKLITE_GUI_UPDATE_REQUEST_DIR" "/data/gui-update"
  append_env_default "${env_file}" "TAKLITE_SETTINGS_REQUEST_DIR" "/data/settings"
  append_env_default "${env_file}" "TAKLITE_FIREWALL_REQUEST_DIR" "/data/firewall"
  append_env_default "${env_file}" "TAKLITE_WG_INTERFACE" "wg0"
  append_env_default "${env_file}" "TAKLITE_PUBLIC_INTERFACE" ""
  append_env_default "${env_file}" "TAKLITE_WIREGUARD_PORT" "51820"
  append_env_default "${env_file}" "TAKLITE_WGDASHBOARD_PORT" "10086"
  if grep -q '^TAKLITE_GUI_UPDATE_ENABLED=false$' "${env_file}" \
      && grep -q '^TAKLITE_GUI_UPDATE_COMMAND=$' "${env_file}" \
      && grep -q '^TAKLITE_GUI_UPDATE_REQUEST_DIR=/data/gui-update$' "${env_file}"; then
    set_env_value "${env_file}" "TAKLITE_GUI_UPDATE_ENABLED" "true"
  fi
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

install_gui_update_runner() {
  local app_dir="$1"
  local request_dir="${app_dir}/taklite/data/gui-update"

  log "Installing TAKlite GUI update runner"
  install -d -m 770 "${request_dir}"
  chown 10001:10001 "${request_dir}" 2>/dev/null || true

  cat >/usr/local/sbin/taklite-gui-update-runner <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${app_dir}"
REQUEST_DIR="\${APP_DIR}/taklite/data/gui-update"
REQUEST_FILE="\${REQUEST_DIR}/request.json"
PROCESSING_FILE="\${REQUEST_DIR}/processing.json"
STATUS_FILE="\${REQUEST_DIR}/status.json"
LOCK_FILE="/run/taklite-gui-update.lock"
STAGE_DIR="/root/TAKlite-update-gui"
LOG_FILE="/root/taklite-admin/gui-update-last.log"

write_status() {
  local state="\$1"
  local message="\${2:-}"
  UPDATE_STATE="\${state}" UPDATE_MESSAGE="\${message}" UPDATE_REQUEST_ID="\${REQUEST_ID:-}" UPDATE_LOG="\${LOG_FILE}" python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
status = {
    "state": os.environ.get("UPDATE_STATE", ""),
    "message": os.environ.get("UPDATE_MESSAGE", ""),
    "request_id": os.environ.get("UPDATE_REQUEST_ID", ""),
    "log": os.environ.get("UPDATE_LOG", ""),
    "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
}
with open(os.environ.get("STATUS_FILE", "/dev/null"), "w", encoding="utf-8") as fh:
    json.dump(status, fh, indent=2)
PY
  chown 10001:10001 "\${STATUS_FILE}" 2>/dev/null || true
  chmod 660 "\${STATUS_FILE}" 2>/dev/null || true
}

export STATUS_FILE
install -d -m 770 "\${REQUEST_DIR}"
chown 10001:10001 "\${REQUEST_DIR}" 2>/dev/null || true
exec 9>"\${LOCK_FILE}"
flock -n 9 || exit 0
[[ -f "\${REQUEST_FILE}" ]] || exit 0
mv "\${REQUEST_FILE}" "\${PROCESSING_FILE}"
chown root:root "\${PROCESSING_FILE}" 2>/dev/null || true
chmod 600 "\${PROCESSING_FILE}" 2>/dev/null || true

REQUEST_ID="\$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("id",""))' "\${PROCESSING_FILE}" 2>/dev/null || true)"
TARGET_TAG="\$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("target_tag",""))' "\${PROCESSING_FILE}" 2>/dev/null || true)"

write_status "running" "Updating TAKlite"
mkdir -p /root/taklite-admin
if [[ "\${TARGET_TAG}" =~ ^v[0-9]+\\.[0-9]+\\.[0-9]+$ ]]; then
  CLONE_ARGS=(--depth 1 --branch "\${TARGET_TAG}" https://github.com/C137LLC/TAKlite.git "\${STAGE_DIR}")
else
  CLONE_ARGS=(--depth 1 https://github.com/C137LLC/TAKlite.git "\${STAGE_DIR}")
fi

set +e
{
  date -u
  rm -rf "\${STAGE_DIR}"
  git clone "\${CLONE_ARGS[@]}"
  cd "\${APP_DIR}"
  ./update.sh --from-dir "\${STAGE_DIR}" --app-dir "\${APP_DIR}"
} >"\${LOG_FILE}" 2>&1
rc=\$?
set -e

if [[ "\${rc}" -eq 0 ]]; then
  write_status "ok" "TAKlite update complete"
else
  write_status "failed" "TAKlite update failed; see \${LOG_FILE}"
fi
rm -f "\${PROCESSING_FILE}"
exit "\${rc}"
EOF
  chmod 700 /usr/local/sbin/taklite-gui-update-runner

  cat >/etc/systemd/system/taklite-gui-update.service <<EOF
[Unit]
Description=TAKlite GUI Update Runner
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/taklite-gui-update-runner
EOF

  cat >/etc/systemd/system/taklite-gui-update.path <<EOF
[Unit]
Description=Watch for TAKlite GUI update requests

[Path]
PathExists=${request_dir}/request.json
Unit=taklite-gui-update.service

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable --now taklite-gui-update.path
}

install_settings_runner() {
  local app_dir="$1"
  local request_dir="${app_dir}/taklite/data/settings"

  log "Installing TAKlite settings runner"
  install -d -m 770 "${request_dir}"
  chown 10001:10001 "${request_dir}" 2>/dev/null || true

  cat >/usr/local/sbin/taklite-settings-runner <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${app_dir}"
REQUEST_DIR="\${APP_DIR}/taklite/data/settings"
REQUEST_FILE="\${REQUEST_DIR}/request.json"
PROCESSING_FILE="\${REQUEST_DIR}/processing.json"
STATUS_FILE="\${REQUEST_DIR}/status.json"
LOCK_FILE="/run/taklite-settings.lock"
LOG_FILE="/root/taklite-admin/settings-last.log"

write_status() {
  local state="\$1"
  local message="\${2:-}"
  SETTINGS_STATE="\${state}" SETTINGS_MESSAGE="\${message}" SETTINGS_REQUEST_ID="\${REQUEST_ID:-}" SETTINGS_LOG="\${LOG_FILE}" STATUS_FILE="\${STATUS_FILE}" python3 - <<'PY'
import json, os
from datetime import datetime, timezone
status = {
    "state": os.environ.get("SETTINGS_STATE", ""),
    "message": os.environ.get("SETTINGS_MESSAGE", ""),
    "request_id": os.environ.get("SETTINGS_REQUEST_ID", ""),
    "log": os.environ.get("SETTINGS_LOG", ""),
    "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
}
with open(os.environ["STATUS_FILE"], "w", encoding="utf-8") as fh:
    json.dump(status, fh, indent=2)
PY
  chown 10001:10001 "\${STATUS_FILE}" 2>/dev/null || true
  chmod 660 "\${STATUS_FILE}" 2>/dev/null || true
}

install -d -m 770 "\${REQUEST_DIR}"
chown 10001:10001 "\${REQUEST_DIR}" 2>/dev/null || true
exec 9>"\${LOCK_FILE}"
flock -n 9 || exit 0
[[ -f "\${REQUEST_FILE}" ]] || exit 0
mv "\${REQUEST_FILE}" "\${PROCESSING_FILE}"
chown root:root "\${PROCESSING_FILE}" 2>/dev/null || true
chmod 600 "\${PROCESSING_FILE}" 2>/dev/null || true
REQUEST_ID="\$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("id",""))' "\${PROCESSING_FILE}" 2>/dev/null || true)"
write_status "running" "Applying TAKlite settings"
mkdir -p /root/taklite-admin
set +e
{
  date -u
  REQUEST_FILE="\${PROCESSING_FILE}" ENV_FILE="\${APP_DIR}/.env" python3 - <<'PY'
import json, os, pathlib, shutil
allowed = {
    "TAKLITE_PUBLIC_HOST", "TAKLITE_SERVER_HOST", "TAKLITE_WGDASHBOARD_URL",
    "TAKLITE_MAX_UPLOAD_BYTES", "TAKLITE_COT_HOST_PORT", "TAKLITE_COT_TLS_HOST_PORT",
    "TAKLITE_HTTP_HOST_PORT", "TAKLITE_HTTPS_HOST_PORT", "TAKLITE_ACCESS_CONTROL_ENFORCE",
    "TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT", "TAKLITE_ALLOW_LEGACY_CLIENT_CERT",
}
request = json.load(open(os.environ["REQUEST_FILE"], encoding="utf-8"))
updates = request.get("env") or {}
bad = sorted(set(updates) - allowed)
if bad:
    raise SystemExit(f"unsupported settings key: {bad[0]}")
env_path = pathlib.Path(os.environ["ENV_FILE"])
backup = env_path.with_suffix(env_path.suffix + ".settings.bak")
shutil.copy2(env_path, backup)
lines = env_path.read_text(encoding="utf-8").splitlines()
seen = set()
out = []
for line in lines:
    if "=" in line and not line.lstrip().startswith("#"):
        key = line.split("=", 1)[0]
        if key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
            continue
    out.append(line)
for key in sorted(set(updates) - seen):
    out.append(f"{key}={updates[key]}")
env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"updated {len(updates)} setting(s); backup {backup}")
PY
  cd "\${APP_DIR}"
  docker compose up -d
} >"\${LOG_FILE}" 2>&1
rc=\$?
set -e
if [[ "\${rc}" -eq 0 ]]; then
  write_status "ok" "TAKlite settings applied"
else
  write_status "failed" "TAKlite settings failed; see \${LOG_FILE}"
fi
rm -f "\${PROCESSING_FILE}"
exit "\${rc}"
EOF
  chmod 700 /usr/local/sbin/taklite-settings-runner

  cat >/etc/systemd/system/taklite-settings.service <<EOF
[Unit]
Description=TAKlite Settings Runner
After=docker.service
Wants=docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/taklite-settings-runner
EOF

  cat >/etc/systemd/system/taklite-settings.path <<EOF
[Unit]
Description=Watch for TAKlite settings requests

[Path]
PathExists=${request_dir}/request.json
Unit=taklite-settings.service

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now taklite-settings.path
}

install_firewall_runner() {
  local app_dir="$1"
  local request_dir="${app_dir}/taklite/data/firewall"

  log "Installing TAKlite firewall runner"
  install -d -m 770 "${request_dir}"
  chown 10001:10001 "${request_dir}" 2>/dev/null || true

  cat >/usr/local/sbin/taklite-firewall-runner <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail

REQUEST_DIR="${request_dir}"
REQUEST_FILE="\${REQUEST_DIR}/request.json"
PROCESSING_FILE="\${REQUEST_DIR}/processing.json"
STATUS_FILE="\${REQUEST_DIR}/status.json"
LOCK_FILE="/run/taklite-firewall.lock"
LOG_FILE="/root/taklite-admin/firewall-last.log"

write_status() {
  local state="\$1"
  local message="\${2:-}"
  FIREWALL_STATE="\${state}" FIREWALL_MESSAGE="\${message}" FIREWALL_REQUEST_ID="\${REQUEST_ID:-}" FIREWALL_LOG="\${LOG_FILE}" STATUS_FILE="\${STATUS_FILE}" PROCESSING_FILE="\${PROCESSING_FILE}" SERVICE_STATES="\${SERVICE_STATES:-{}}" python3 - <<'PY'
import json, os
from datetime import datetime, timezone
try:
    service_states = json.loads(os.environ.get("SERVICE_STATES", "{}"))
except Exception:
    service_states = {}
if not service_states:
    try:
        with open(os.environ.get("PROCESSING_FILE", ""), encoding="utf-8") as fh:
            service_states = json.load(fh).get("services", {})
    except Exception:
        service_states = {}
status = {
    "state": os.environ.get("FIREWALL_STATE", ""),
    "message": os.environ.get("FIREWALL_MESSAGE", ""),
    "request_id": os.environ.get("FIREWALL_REQUEST_ID", ""),
    "log": os.environ.get("FIREWALL_LOG", ""),
    "service_states": service_states,
    "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
}
with open(os.environ["STATUS_FILE"], "w", encoding="utf-8") as fh:
    json.dump(status, fh, indent=2)
PY
  chown 10001:10001 "\${STATUS_FILE}" 2>/dev/null || true
  chmod 660 "\${STATUS_FILE}" 2>/dev/null || true
}

delete_rule() {
  local iface="\$1" proto="\$2" port="\$3"
  if [[ -n "\${iface}" ]]; then
    while iptables -C INPUT -i "\${iface}" -p "\${proto}" --dport "\${port}" -j ACCEPT 2>/dev/null; do iptables -D INPUT -i "\${iface}" -p "\${proto}" --dport "\${port}" -j ACCEPT 2>/dev/null || break; done
  else
    while iptables -C INPUT -p "\${proto}" --dport "\${port}" -j ACCEPT 2>/dev/null; do iptables -D INPUT -p "\${proto}" --dport "\${port}" -j ACCEPT 2>/dev/null || break; done
  fi
}

add_rule() {
  local iface="\$1" proto="\$2" port="\$3"
  if [[ -n "\${iface}" ]]; then
    iptables -C INPUT -i "\${iface}" -p "\${proto}" --dport "\${port}" -j ACCEPT 2>/dev/null || iptables -I INPUT -i "\${iface}" -p "\${proto}" --dport "\${port}" -j ACCEPT
  else
    iptables -C INPUT -p "\${proto}" --dport "\${port}" -j ACCEPT 2>/dev/null || iptables -I INPUT -p "\${proto}" --dport "\${port}" -j ACCEPT
  fi
}

apply_service() {
  local key="\$1" proto="\$2" port="\$3" state="\$4" wg_if="\$5"
  if [[ "\${key}" == "wireguard" && "\${state}" == "closed" ]]; then echo "refusing to close WireGuard"; return 1; fi
  delete_rule "" "\${proto}" "\${port}"
  delete_rule "\${wg_if}" "\${proto}" "\${port}"
  case "\${state}" in
    public) add_rule "" "\${proto}" "\${port}" ;;
    vpn) add_rule "\${wg_if}" "\${proto}" "\${port}" ;;
    closed) ;;
    *) echo "bad state for \${key}: \${state}"; return 1 ;;
  esac
}

install -d -m 770 "\${REQUEST_DIR}"
chown 10001:10001 "\${REQUEST_DIR}" 2>/dev/null || true
exec 9>"\${LOCK_FILE}"
flock -n 9 || exit 0
[[ -f "\${REQUEST_FILE}" ]] || exit 0
mv "\${REQUEST_FILE}" "\${PROCESSING_FILE}"
chown root:root "\${PROCESSING_FILE}" 2>/dev/null || true
chmod 600 "\${PROCESSING_FILE}" 2>/dev/null || true
REQUEST_ID="\$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("id",""))' "\${PROCESSING_FILE}" 2>/dev/null || true)"
SERVICE_STATES="\$(python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1])).get("services",{}), separators=(",", ":")))' "\${PROCESSING_FILE}")"
write_status "running" "Applying firewall policy"
mkdir -p /root/taklite-admin
set +e
{
  date -u
  iptables-save >"/root/taklite-admin/iptables-before-taklite-firewall.rules" || true
  python3 - "\${PROCESSING_FILE}" <<'PY' >/tmp/taklite-firewall-apply.sh
import json, shlex, sys
request = json.load(open(sys.argv[1], encoding="utf-8"))
defs = request.get("service_definitions") or {}
services = request.get("services") or {}
wg_if = (request.get("interfaces") or {}).get("wireguard") or "wg0"
for key, state in services.items():
    definition = defs.get(key) or {}
    proto = definition.get("protocol")
    port = int(definition.get("port") or 0)
    if key not in defs or proto not in ("tcp", "udp") or not 1 <= port <= 65535:
        raise SystemExit(f"bad firewall service: {key}")
    print("apply_service", shlex.quote(key), shlex.quote(proto), shlex.quote(str(port)), shlex.quote(state), shlex.quote(wg_if))
PY
  source /tmp/taklite-firewall-apply.sh
  rm -f /tmp/taklite-firewall-apply.sh
  iptables-save >"/root/taklite-admin/iptables-after-taklite-firewall.rules" || true
} >"\${LOG_FILE}" 2>&1
rc=\$?
set -e
if [[ "\${rc}" -eq 0 ]]; then
  write_status "ok" "Firewall policy applied"
else
  write_status "failed" "Firewall policy failed; see \${LOG_FILE}"
fi
rm -f "\${PROCESSING_FILE}"
exit "\${rc}"
EOF
  chmod 700 /usr/local/sbin/taklite-firewall-runner

  cat >/etc/systemd/system/taklite-firewall.service <<EOF
[Unit]
Description=TAKlite Firewall Runner
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/taklite-firewall-runner
EOF

  cat >/etc/systemd/system/taklite-firewall.path <<EOF
[Unit]
Description=Watch for TAKlite firewall requests

[Path]
PathExists=${request_dir}/request.json
Unit=taklite-firewall.service

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now taklite-firewall.path
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

if [[ -n "${APP_DIR}" ]]; then
  APP_DIR="$(cd "${APP_DIR}" && pwd)"
else
  APP_DIR="$(detect_app_dir)" || die "could not find existing TAKlite app dir; pass --app-dir /root/taklite"
fi
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
  --exclude '/taklite/' \
  "${SOURCE_DIR}/" "${APP_DIR}/"

chmod +x "${APP_DIR}/install.sh" "${APP_DIR}/smoke-test.sh" "${APP_DIR}/update.sh"
install -d -m 700 "${APP_DIR}/taklite/data" "${APP_DIR}/taklite/certs" "${APP_DIR}/taklite/packages"
install -d -m 770 "${APP_DIR}/taklite/data/gui-update" "${APP_DIR}/taklite/data/settings" "${APP_DIR}/taklite/data/firewall"
chown -R 10001:10001 "${APP_DIR}/taklite/data" "${APP_DIR}/taklite/certs" "${APP_DIR}/taklite/packages"
merge_env_defaults "${APP_DIR}/.env"
install_gui_update_runner "${APP_DIR}"
install_settings_runner "${APP_DIR}"
install_firewall_runner "${APP_DIR}"

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
