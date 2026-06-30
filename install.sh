#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

SCRIPT_NAME="taklite-vps-install"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WG_DIR="/etc/wireguard"
ADMIN_OUT_DIR="/root/taklite-admin"
WGD_DIR="/opt/WGDashboard"
WGD_SRC="${WGD_DIR}/src"
OS_ID=""
OS_VERSION_ID=""
OS_CODENAME=""
OS_PRETTY_NAME=""
OS_ID_LIKE=""
OS_ARCH=""

log() {
  printf '[%s] %s\n' "${SCRIPT_NAME}" "$*"
}

die() {
  printf '[%s] ERROR: %s\n' "${SCRIPT_NAME}" "$*" >&2
  exit 1
}

need_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    die "run as root: sudo ./install.sh"
  fi
}

prompt_default() {
  local prompt="$1"
  local default="$2"
  local value
  read -r -p "${prompt} [${default}]: " value
  printf '%s' "${value:-$default}"
}

random_token() {
  python3 -c 'import secrets, string; alphabet=string.ascii_letters+string.digits+"._=-"; print("".join(secrets.choice(alphabet) for _ in range(32)))'
}

detect_os() {
  [[ -r /etc/os-release ]] || die "cannot read /etc/os-release"
  # shellcheck disable=SC1091
  source /etc/os-release
  OS_ID="${ID:-unknown}"
  OS_VERSION_ID="${VERSION_ID:-}"
  OS_CODENAME="${VERSION_CODENAME:-${UBUNTU_CODENAME:-}}"
  OS_PRETTY_NAME="${PRETTY_NAME:-${OS_ID} ${OS_VERSION_ID}}"
  OS_ID_LIKE="${ID_LIKE:-}"
  OS_ARCH="$(dpkg --print-architecture 2>/dev/null || uname -m)"

  case "${OS_ARCH}" in
    amd64|arm64|aarch64)
      ;;
    *)
      die "unsupported CPU architecture ${OS_ARCH}; supported: amd64/x86_64 and arm64/aarch64"
      ;;
  esac

  case "${OS_ID}" in
    ubuntu)
      case "${OS_VERSION_ID%%.*}" in
        22|24|26|27|28) ;;
        *) die "unsupported Ubuntu version ${OS_VERSION_ID}; use Ubuntu 22.04 LTS or newer" ;;
      esac
      ;;
    debian)
      case "${OS_VERSION_ID%%.*}" in
        12|13|14) ;;
        *) die "unsupported Debian version ${OS_VERSION_ID}; use Debian 12 Bookworm or newer" ;;
      esac
      ;;
    raspbian)
      case "${OS_VERSION_ID%%.*}" in
        12|13|14) ;;
        *) die "unsupported Raspberry Pi OS version ${OS_VERSION_ID}; use 64-bit Bookworm or newer" ;;
      esac
      ;;
    *)
      if [[ " ${OS_ID_LIKE} " == *" debian "* ]]; then
        log "Detected Debian-like host ${OS_PRETTY_NAME}; continuing in best-effort mode"
      else
        die "this installer targets Ubuntu 22.04+, Debian 12+, and Raspberry Pi OS 64-bit Bookworm+; detected ${OS_PRETTY_NAME}"
      fi
      ;;
  esac

  log "Detected ${OS_PRETTY_NAME} (${OS_ARCH})"
}

preflight_host() {
  command -v apt-get >/dev/null 2>&1 || die "apt-get is required for the full VPS installer"
  command -v systemctl >/dev/null 2>&1 || die "systemd is required for WireGuard, WGDashboard, and TAKlite host runners"
  [[ -e /dev/net/tun ]] || die "/dev/net/tun is missing; enable TUN/TAP support on this VPS/container host"
  if [[ "${OS_ARCH}" == "arm64" || "${OS_ARCH}" == "aarch64" ]]; then
    log "ARM64 host detected; TAKlite supports this for Docker/TAKlite, but Raspberry Pi class hardware may build more slowly"
  fi
}

ensure_docker_compose() {
  if docker compose version >/dev/null 2>&1; then
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    die "docker-compose v1 was found, but TAKlite needs Docker Compose v2. Install docker-compose-plugin or docker-compose-v2."
  fi
  die "Docker Compose v2 was not found after package install. Install docker-compose-plugin/docker-compose-v2 for this distro and rerun install.sh."
}

detect_public_endpoint() {
  local endpoint=""
  endpoint="$(curl -fsS4 --max-time 5 https://api.ipify.org 2>/dev/null || true)"
  if [[ -z "${endpoint}" ]]; then
    endpoint="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i=="src") print $(i+1)}' | head -n1)"
  fi
  printf '%s' "${endpoint}"
}

detect_public_interface() {
  ip -4 route ls default | awk '/dev/ {for (i=1; i<=NF; i++) if ($i=="dev") print $(i+1)}' | head -n1
}

ipv4_prefix24() {
  awk -F. '{print $1"."$2"."$3}' <<<"$1"
}

install_packages() {
  log "Installing VPS packages"
  apt-get update
  local compose_package=""
  for candidate in docker-compose-plugin docker-compose-v2; do
    if apt-cache show "${candidate}" >/dev/null 2>&1; then
      compose_package="${candidate}"
      break
    fi
  done
  [[ -n "${compose_package}" ]] || die "could not find a Docker Compose v2 package in apt; expected docker-compose-plugin or docker-compose-v2"

  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ca-certificates curl fail2ban git iproute2 iptables net-tools python3 python3-pip \
    python3-venv qrencode rsync util-linux wireguard-tools docker.io openssl zip "${compose_package}"
  systemctl enable --now docker
  systemctl enable --now fail2ban
  ensure_docker_compose
}

collect_settings() {
  local detected_endpoint detected_nic base token_default
  detected_endpoint="$(detect_public_endpoint)"
  detected_nic="$(detect_public_interface)"

  [[ -n "${detected_endpoint}" ]] || detected_endpoint="YOUR_VPS_PUBLIC_IP"
  [[ -n "${detected_nic}" ]] || detected_nic="eth0"

  SERVER_ENDPOINT="$(prompt_default "Public IP or DNS name clients use for WireGuard" "${detected_endpoint}")"
  SERVER_NIC="$(prompt_default "Public network interface" "${detected_nic}")"
  WG_NIC="$(prompt_default "WireGuard interface name" "wg0")"
  WG_SERVER_IP="$(prompt_default "WireGuard server IPv4" "10.66.66.1")"
  WG_CIDR="$(prompt_default "WireGuard IPv4 CIDR" "24")"
  WG_PORT="$(prompt_default "WireGuard UDP port" "51820")"
  ADMIN_NAME="$(prompt_default "Initial admin peer name" "admin")"

  base="$(ipv4_prefix24 "${WG_SERVER_IP}")"
  ADMIN_IP="$(prompt_default "Initial admin WireGuard IPv4" "${base}.2")"
  ADMIN_ALLOWED_IPS="$(prompt_default "AllowedIPs for admin client" "0.0.0.0/0")"
  CLIENT_DNS="$(prompt_default "DNS resolver for generated peers" "1.1.1.1")"
  WGD_BIND_IP="$(prompt_default "WGDashboard bind IP" "${WG_SERVER_IP}")"
  WGD_PORT="$(prompt_default "WGDashboard port" "10086")"
  WGD_USER="$(prompt_default "WGDashboard username" "admin")"
  WGD_PASSWORD="$(random_token)"
  TAKLITE_BIND_IP="$(prompt_default "TAKlite bind IP" "${WG_SERVER_IP}")"
  TAKLITE_PUBLIC_HOST="$(prompt_default "TAKlite API host used in package URLs" "${TAKLITE_BIND_IP}")"
  TAKLITE_ADMIN_TOKEN="$(prompt_default "TAKlite admin token" "$(random_token)")"
  TAKLITE_CERT_PASSWORD="$(prompt_default "ATAK/WinTAK certificate password" "atakatak")"
  TAKLITE_SECURE_MODE="$(prompt_default "Enable secure mode: require TLS cert identity and enforce groups" "yes")"
  if [[ "${TAKLITE_SECURE_MODE,,}" =~ ^(y|yes|true|1)$ ]]; then
    TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT="true"
    TAKLITE_ALLOW_LEGACY_CLIENT_CERT="false"
    TAKLITE_ACCESS_CONTROL_ENFORCE="true"
  else
    TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT="false"
    TAKLITE_ALLOW_LEGACY_CLIENT_CERT="true"
    TAKLITE_ACCESS_CONTROL_ENFORCE="false"
  fi
  TAKLITE_COT_HOST_PORT="$(prompt_default "TAKlite plain CoT TCP host port" "58087")"
  TAKLITE_COT_TLS_HOST_PORT="$(prompt_default "TAKlite TLS CoT TCP host port" "8089")"
  TAKLITE_HTTP_HOST_PORT="$(prompt_default "TAKlite HTTP/admin host port" "8080")"
  TAKLITE_HTTPS_HOST_PORT="$(prompt_default "TAKlite HTTPS/Marti host port" "8443")"
}

write_wireguard_config() {
  local server_priv server_pub admin_priv admin_pub admin_psk wg_network

  [[ ! -e "${WG_DIR}/${WG_NIC}.conf" ]] || die "${WG_DIR}/${WG_NIC}.conf already exists; refusing to overwrite"

  log "Creating WireGuard server and initial admin peer"
  install -d -m 700 "${WG_DIR}"

  server_priv="$(wg genkey)"
  server_pub="$(printf '%s' "${server_priv}" | wg pubkey)"
  admin_priv="$(wg genkey)"
  admin_pub="$(printf '%s' "${admin_priv}" | wg pubkey)"
  admin_psk="$(wg genpsk)"
  wg_network="$(ipv4_prefix24 "${WG_SERVER_IP}").0/${WG_CIDR}"

  cat >"${WG_DIR}/${WG_NIC}.conf" <<EOF
[Interface]
Address = ${WG_SERVER_IP}/${WG_CIDR}
ListenPort = ${WG_PORT}
PrivateKey = ${server_priv}
SaveConfig = false
PostUp = iptables -C INPUT -p udp --dport ${WG_PORT} -j ACCEPT 2>/dev/null || iptables -I INPUT -p udp --dport ${WG_PORT} -j ACCEPT
PostUp = iptables -C INPUT -i ${WG_NIC} -p tcp --dport 22 -j ACCEPT 2>/dev/null || iptables -I INPUT -i ${WG_NIC} -p tcp --dport 22 -j ACCEPT
PostUp = iptables -C INPUT -i ${WG_NIC} -p tcp --dport ${WGD_PORT} -j ACCEPT 2>/dev/null || iptables -I INPUT -i ${WG_NIC} -p tcp --dport ${WGD_PORT} -j ACCEPT
PostUp = iptables -C INPUT -i ${WG_NIC} -p tcp --dport ${TAKLITE_HTTP_HOST_PORT} -j ACCEPT 2>/dev/null || iptables -I INPUT -i ${WG_NIC} -p tcp --dport ${TAKLITE_HTTP_HOST_PORT} -j ACCEPT
PostUp = iptables -C INPUT -i ${WG_NIC} -p tcp --dport ${TAKLITE_HTTPS_HOST_PORT} -j ACCEPT 2>/dev/null || iptables -I INPUT -i ${WG_NIC} -p tcp --dport ${TAKLITE_HTTPS_HOST_PORT} -j ACCEPT
PostUp = iptables -C INPUT -i ${WG_NIC} -p tcp --dport ${TAKLITE_COT_HOST_PORT} -j ACCEPT 2>/dev/null || iptables -I INPUT -i ${WG_NIC} -p tcp --dport ${TAKLITE_COT_HOST_PORT} -j ACCEPT
PostUp = iptables -C INPUT -i ${WG_NIC} -p tcp --dport ${TAKLITE_COT_TLS_HOST_PORT} -j ACCEPT 2>/dev/null || iptables -I INPUT -i ${WG_NIC} -p tcp --dport ${TAKLITE_COT_TLS_HOST_PORT} -j ACCEPT
PostUp = iptables -C FORWARD -i ${WG_NIC} -j ACCEPT 2>/dev/null || iptables -I FORWARD -i ${WG_NIC} -j ACCEPT
PostUp = iptables -C FORWARD -o ${WG_NIC} -j ACCEPT 2>/dev/null || iptables -I FORWARD -o ${WG_NIC} -j ACCEPT
PostUp = iptables -t nat -C POSTROUTING -s ${wg_network} -o ${SERVER_NIC} -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s ${wg_network} -o ${SERVER_NIC} -j MASQUERADE
PostDown = iptables -D INPUT -p udp --dport ${WG_PORT} -j ACCEPT 2>/dev/null || true
PostDown = iptables -D INPUT -i ${WG_NIC} -p tcp --dport 22 -j ACCEPT 2>/dev/null || true
PostDown = iptables -D INPUT -i ${WG_NIC} -p tcp --dport ${WGD_PORT} -j ACCEPT 2>/dev/null || true
PostDown = iptables -D INPUT -i ${WG_NIC} -p tcp --dport ${TAKLITE_HTTP_HOST_PORT} -j ACCEPT 2>/dev/null || true
PostDown = iptables -D INPUT -i ${WG_NIC} -p tcp --dport ${TAKLITE_HTTPS_HOST_PORT} -j ACCEPT 2>/dev/null || true
PostDown = iptables -D INPUT -i ${WG_NIC} -p tcp --dport ${TAKLITE_COT_HOST_PORT} -j ACCEPT 2>/dev/null || true
PostDown = iptables -D INPUT -i ${WG_NIC} -p tcp --dport ${TAKLITE_COT_TLS_HOST_PORT} -j ACCEPT 2>/dev/null || true
PostDown = iptables -D FORWARD -i ${WG_NIC} -j ACCEPT 2>/dev/null || true
PostDown = iptables -D FORWARD -o ${WG_NIC} -j ACCEPT 2>/dev/null || true
PostDown = iptables -t nat -D POSTROUTING -s ${wg_network} -o ${SERVER_NIC} -j MASQUERADE 2>/dev/null || true

### Client ${ADMIN_NAME}
[Peer]
PublicKey = ${admin_pub}
PresharedKey = ${admin_psk}
AllowedIPs = ${ADMIN_IP}/32
EOF

  chmod 600 "${WG_DIR}/${WG_NIC}.conf"

  install -d -m 700 "${ADMIN_OUT_DIR}"
  cat >"${ADMIN_OUT_DIR}/${ADMIN_NAME}-${WG_NIC}.conf" <<EOF
[Interface]
PrivateKey = ${admin_priv}
Address = ${ADMIN_IP}/32
DNS = ${CLIENT_DNS}

[Peer]
PublicKey = ${server_pub}
PresharedKey = ${admin_psk}
Endpoint = ${SERVER_ENDPOINT}:${WG_PORT}
AllowedIPs = ${ADMIN_ALLOWED_IPS}
PersistentKeepalive = 21
EOF

  chmod 600 "${ADMIN_OUT_DIR}/${ADMIN_NAME}-${WG_NIC}.conf"
  qrencode -t png -o "${ADMIN_OUT_DIR}/${ADMIN_NAME}-${WG_NIC}.png" <"${ADMIN_OUT_DIR}/${ADMIN_NAME}-${WG_NIC}.conf"
}

enable_wireguard() {
  log "Enabling IPv4 forwarding and starting WireGuard"
  cat >/etc/sysctl.d/99-taklite-wireguard.conf <<EOF
net.ipv4.ip_forward = 1
EOF
  sysctl --system >/dev/null
  systemctl enable --now "wg-quick@${WG_NIC}"
}

install_wgdashboard() {
  log "Installing WGDashboard"
  if [[ ! -d "${WGD_DIR}/.git" ]]; then
    git clone https://github.com/WGDashboard/WGDashboard.git "${WGD_DIR}"
  else
    git -C "${WGD_DIR}" pull --ff-only
  fi

  chmod +x "${WGD_SRC}/wgd.sh"
  (
    cd "${WGD_SRC}"
    printf '\n' | ./wgd.sh install
  )
  chmod 700 "${WG_DIR}"
  chmod 600 "${WG_DIR}"/*.conf
}

configure_wgdashboard() {
  local password_hash totp_key

  log "Configuring WGDashboard on ${WGD_BIND_IP}:${WGD_PORT}"
  password_hash="$(
    WGD_PASSWORD="${WGD_PASSWORD}" "${WGD_SRC}/venv/bin/python3" -c \
      'import bcrypt, os; print(bcrypt.hashpw(os.environ["WGD_PASSWORD"].encode(), bcrypt.gensalt()).decode())'
  )"
  totp_key="$("${WGD_SRC}/venv/bin/python3" -c 'import pyotp; print(pyotp.random_base32())' 2>/dev/null || random_token)"

  cat >"${WGD_SRC}/wg-dashboard.ini" <<EOF
[Account]
username = ${WGD_USER}
password = ${password_hash}
enable_totp = false
totp_verified = false
totp_key = ${totp_key}

[Server]
wg_conf_path = /etc/wireguard
awg_conf_path = /etc/amnezia/amneziawg
app_prefix =
app_ip = ${WGD_BIND_IP}
app_port = ${WGD_PORT}
auth_req = true
dashboard_refresh_interval = 60000
dashboard_sort = status
dashboard_theme = dark
dashboard_api_key = false
dashboard_language = en-US

[Peers]
peer_global_dns = ${CLIENT_DNS}
peer_endpoint_allowed_ip = ${ADMIN_ALLOWED_IPS}
remote_endpoint = ${SERVER_ENDPOINT}:${WG_PORT}
peer_mtu = 1420
peer_keep_alive = 21
peer_display_mode = grid

[Other]
welcome_session = false
EOF
  chmod 600 "${WGD_SRC}/wg-dashboard.ini"
}

install_wgdashboard_service() {
  log "Installing WGDashboard systemd service"
  cat >/etc/systemd/system/wg-dashboard.service <<EOF
[Unit]
Description=WGDashboard
After=network-online.target wg-quick@${WG_NIC}.service
Wants=network-online.target
Requires=wg-quick@${WG_NIC}.service
ConditionPathIsDirectory=/etc/wireguard

[Service]
Type=forking
PIDFile=${WGD_SRC}/gunicorn.pid
WorkingDirectory=${WGD_SRC}
ExecStart=${WGD_SRC}/wgd.sh start
ExecStop=${WGD_SRC}/wgd.sh stop
ExecReload=${WGD_SRC}/wgd.sh restart
TimeoutSec=120
PrivateTmp=yes
Restart=always

[Install]
WantedBy=multi-user.target
EOF

  chmod 664 /etc/systemd/system/wg-dashboard.service
  systemctl daemon-reload
  systemctl enable --now wg-dashboard.service
}

configure_fail2ban() {
  log "Configuring fail2ban sshd jail"
  cat >/etc/fail2ban/jail.d/taklite-vps.local <<EOF
[sshd]
enabled = true
port = ssh
maxretry = 4
findtime = 10m
bantime = 1h
EOF
  systemctl restart fail2ban
}

install_gui_update_runner() {
  local request_dir="${BASE_DIR}/taklite/data/gui-update"

  log "Installing TAKlite GUI update runner"
  install -d -m 770 "${request_dir}"
  chown 10001:10001 "${request_dir}" 2>/dev/null || true

  cat >/usr/local/sbin/taklite-gui-update-runner <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${BASE_DIR}"
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
  local request_dir="${BASE_DIR}/taklite/data/settings"

  log "Installing TAKlite settings runner"
  install -d -m 770 "${request_dir}"
  chown 10001:10001 "${request_dir}" 2>/dev/null || true

  cat >/usr/local/sbin/taklite-settings-runner <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${BASE_DIR}"
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
    "TAKLITE_PUBLIC_HOST",
    "TAKLITE_SERVER_HOST",
    "TAKLITE_WGDASHBOARD_URL",
    "TAKLITE_MAX_UPLOAD_BYTES",
    "TAKLITE_COT_HOST_PORT",
    "TAKLITE_COT_TLS_HOST_PORT",
    "TAKLITE_HTTP_HOST_PORT",
    "TAKLITE_HTTPS_HOST_PORT",
    "TAKLITE_ACCESS_CONTROL_ENFORCE",
    "TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT",
    "TAKLITE_ALLOW_LEGACY_CLIENT_CERT",
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
  local request_dir="${BASE_DIR}/taklite/data/firewall"

  log "Installing TAKlite firewall runner"
  install -d -m 770 "${request_dir}"
  chown 10001:10001 "${request_dir}" 2>/dev/null || true

  cat >/usr/local/sbin/taklite-firewall-runner <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail

REQUEST_DIR="${BASE_DIR}/taklite/data/firewall"
REQUEST_FILE="\${REQUEST_DIR}/request.json"
PROCESSING_FILE="\${REQUEST_DIR}/processing.json"
STATUS_FILE="\${REQUEST_DIR}/status.json"
LOCK_FILE="/run/taklite-firewall.lock"
LOG_FILE="/root/taklite-admin/firewall-last.log"
WG_IF="${WG_NIC}"

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
    while iptables -C INPUT -i "\${iface}" -p "\${proto}" --dport "\${port}" -j ACCEPT 2>/dev/null; do
      iptables -D INPUT -i "\${iface}" -p "\${proto}" --dport "\${port}" -j ACCEPT 2>/dev/null || break
    done
  else
    while iptables -C INPUT -p "\${proto}" --dport "\${port}" -j ACCEPT 2>/dev/null; do
      iptables -D INPUT -p "\${proto}" --dport "\${port}" -j ACCEPT 2>/dev/null || break
    done
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
  local key="\$1" proto="\$2" port="\$3" state="\$4"
  if [[ "\${key}" == "wireguard" && "\${state}" == "closed" ]]; then
    echo "refusing to close WireGuard"
    return 1
  fi
  delete_rule "" "\${proto}" "\${port}"
  delete_rule "\${WG_IF}" "\${proto}" "\${port}"
  case "\${state}" in
    public) add_rule "" "\${proto}" "\${port}" ;;
    vpn) add_rule "\${WG_IF}" "\${proto}" "\${port}" ;;
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
for key, state in services.items():
    definition = defs.get(key) or {}
    proto = definition.get("protocol")
    port = int(definition.get("port") or 0)
    if key not in defs or proto not in ("tcp", "udp") or not 1 <= port <= 65535:
        raise SystemExit(f"bad firewall service: {key}")
    print("apply_service", shlex.quote(key), shlex.quote(proto), shlex.quote(str(port)), shlex.quote(state))
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

start_taklite() {
  local cert_password="${TAKLITE_CERT_PASSWORD}"

  log "Writing TAKlite environment"
  install -d -m 700 "${BASE_DIR}/taklite/data" "${BASE_DIR}/taklite/packages" "${BASE_DIR}/taklite/certs"
  install -d -m 770 "${BASE_DIR}/taklite/data/gui-update" "${BASE_DIR}/taklite/data/settings" "${BASE_DIR}/taklite/data/firewall"
  if [[ ! -s "${BASE_DIR}/taklite/certs/taklite-ca.crt" || ! -s "${BASE_DIR}/taklite/certs/taklite-ca.key" ]]; then
    log "Generating TAKlite local CA"
    openssl genrsa -out "${BASE_DIR}/taklite/certs/taklite-ca.key" 4096
    openssl req -x509 -new -nodes \
      -key "${BASE_DIR}/taklite/certs/taklite-ca.key" \
      -sha256 -days 3650 \
      -out "${BASE_DIR}/taklite/certs/taklite-ca.crt" \
      -subj "/CN=TAKlite Local CA"
    chmod 600 "${BASE_DIR}/taklite/certs/taklite-ca.key"
    chmod 644 "${BASE_DIR}/taklite/certs/taklite-ca.crt"
  fi
  if [[ ! -s "${BASE_DIR}/taklite/certs/taklite.crt" || ! -s "${BASE_DIR}/taklite/certs/taklite.key" || ! -s "${BASE_DIR}/taklite/certs/taklite-truststore.p12" ]]; then
    log "Generating TAKlite HTTPS server certificate and ATAK truststore for ${TAKLITE_BIND_IP}"
    openssl genrsa -out "${BASE_DIR}/taklite/certs/taklite.key" 3072
    openssl req -new \
      -key "${BASE_DIR}/taklite/certs/taklite.key" \
      -out "${BASE_DIR}/taklite/certs/taklite-server.csr" \
      -subj "/CN=${TAKLITE_BIND_IP}"
    cat >"${BASE_DIR}/taklite/certs/taklite-server.ext" <<EOF_CERT
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = IP:${TAKLITE_BIND_IP},DNS:taklite.local
EOF_CERT
    openssl x509 -req \
      -in "${BASE_DIR}/taklite/certs/taklite-server.csr" \
      -CA "${BASE_DIR}/taklite/certs/taklite-ca.crt" \
      -CAkey "${BASE_DIR}/taklite/certs/taklite-ca.key" \
      -CAcreateserial \
      -out "${BASE_DIR}/taklite/certs/taklite-server.crt" \
      -days 825 -sha256 \
      -extfile "${BASE_DIR}/taklite/certs/taklite-server.ext"
    cat "${BASE_DIR}/taklite/certs/taklite-server.crt" "${BASE_DIR}/taklite/certs/taklite-ca.crt" >"${BASE_DIR}/taklite/certs/taklite.crt"
    openssl genrsa -out "${BASE_DIR}/taklite/certs/taklite-truststore-holder.key" 2048
    openssl req -new \
      -key "${BASE_DIR}/taklite/certs/taklite-truststore-holder.key" \
      -out "${BASE_DIR}/taklite/certs/taklite-truststore-holder.csr" \
      -subj "/CN=taklite-truststore"
    cat >"${BASE_DIR}/taklite/certs/taklite-truststore-holder.ext" <<EOF_CERT
basicConstraints=CA:FALSE
keyUsage = digitalSignature, keyEncipherment
EOF_CERT
    openssl x509 -req \
      -in "${BASE_DIR}/taklite/certs/taklite-truststore-holder.csr" \
      -CA "${BASE_DIR}/taklite/certs/taklite-ca.crt" \
      -CAkey "${BASE_DIR}/taklite/certs/taklite-ca.key" \
      -CAcreateserial \
      -out "${BASE_DIR}/taklite/certs/taklite-truststore-holder.crt" \
      -days 825 -sha256 \
      -extfile "${BASE_DIR}/taklite/certs/taklite-truststore-holder.ext"
    openssl pkcs12 -export \
      -inkey "${BASE_DIR}/taklite/certs/taklite-truststore-holder.key" \
      -in "${BASE_DIR}/taklite/certs/taklite-truststore-holder.crt" \
      -certfile "${BASE_DIR}/taklite/certs/taklite-ca.crt" \
      -out "${BASE_DIR}/taklite/certs/taklite-truststore.p12" \
      -name taklite-ca \
      -certpbe PBE-SHA1-3DES \
      -keypbe PBE-SHA1-3DES \
      -macalg sha1 \
      -passout "pass:${cert_password}"
    cp "${BASE_DIR}/taklite/certs/taklite-truststore.p12" "${BASE_DIR}/taklite/certs/${TAKLITE_BIND_IP}.p12"
    chmod 600 "${BASE_DIR}/taklite/certs/taklite.key" "${BASE_DIR}/taklite/certs/taklite-truststore-holder.key"
    chmod 644 "${BASE_DIR}/taklite/certs/taklite.crt" "${BASE_DIR}/taklite/certs/taklite-server.crt" "${BASE_DIR}/taklite/certs/taklite-truststore-holder.crt" "${BASE_DIR}/taklite/certs/taklite-truststore.p12" "${BASE_DIR}/taklite/certs/${TAKLITE_BIND_IP}.p12"
  fi
  if [[ ! -s "${BASE_DIR}/taklite/certs/${TAKLITE_BIND_IP}.p12" ]]; then
    if [[ ! -s "${BASE_DIR}/taklite/certs/taklite-truststore-holder.crt" || ! -s "${BASE_DIR}/taklite/certs/taklite-truststore-holder.key" ]]; then
      openssl genrsa -out "${BASE_DIR}/taklite/certs/taklite-truststore-holder.key" 2048
      openssl req -new \
        -key "${BASE_DIR}/taklite/certs/taklite-truststore-holder.key" \
        -out "${BASE_DIR}/taklite/certs/taklite-truststore-holder.csr" \
        -subj "/CN=taklite-truststore"
      cat >"${BASE_DIR}/taklite/certs/taklite-truststore-holder.ext" <<EOF_CERT
basicConstraints=CA:FALSE
keyUsage = digitalSignature, keyEncipherment
EOF_CERT
      openssl x509 -req \
        -in "${BASE_DIR}/taklite/certs/taklite-truststore-holder.csr" \
        -CA "${BASE_DIR}/taklite/certs/taklite-ca.crt" \
        -CAkey "${BASE_DIR}/taklite/certs/taklite-ca.key" \
        -CAcreateserial \
        -out "${BASE_DIR}/taklite/certs/taklite-truststore-holder.crt" \
        -days 825 -sha256 \
        -extfile "${BASE_DIR}/taklite/certs/taklite-truststore-holder.ext"
    fi
    openssl pkcs12 -export \
      -inkey "${BASE_DIR}/taklite/certs/taklite-truststore-holder.key" \
      -in "${BASE_DIR}/taklite/certs/taklite-truststore-holder.crt" \
      -certfile "${BASE_DIR}/taklite/certs/taklite-ca.crt" \
      -out "${BASE_DIR}/taklite/certs/${TAKLITE_BIND_IP}.p12" \
      -name taklite-ca \
      -certpbe PBE-SHA1-3DES \
      -keypbe PBE-SHA1-3DES \
      -macalg sha1 \
      -passout "pass:${cert_password}"
    chmod 600 "${BASE_DIR}/taklite/certs/taklite-truststore-holder.key"
    chmod 644 "${BASE_DIR}/taklite/certs/${TAKLITE_BIND_IP}.p12"
  fi
  chown -R 10001:10001 "${BASE_DIR}/taklite/data" "${BASE_DIR}/taklite/packages" "${BASE_DIR}/taklite/certs"
  cat >"${BASE_DIR}/.env" <<EOF
WG_BIND_IP=${TAKLITE_BIND_IP}
TAKLITE_PUBLIC_HOST=${TAKLITE_PUBLIC_HOST}
TAKLITE_SERVER_HOST=${TAKLITE_BIND_IP}
TAKLITE_CONTAINER_USER=10001:10001
TAKLITE_AUTO_INIT_CERTS=false
TAKLITE_ADMIN_TOKEN=${TAKLITE_ADMIN_TOKEN}
TAKLITE_CERT_PASSWORD=${TAKLITE_CERT_PASSWORD}
TAKLITE_COT_HOST_PORT=${TAKLITE_COT_HOST_PORT}
TAKLITE_COT_TLS_HOST_PORT=${TAKLITE_COT_TLS_HOST_PORT}
TAKLITE_HTTP_HOST_PORT=${TAKLITE_HTTP_HOST_PORT}
TAKLITE_HTTPS_HOST_PORT=${TAKLITE_HTTPS_HOST_PORT}
TAKLITE_WGDASHBOARD_URL=http://${WGD_BIND_IP}:${WGD_PORT}
TAKLITE_MAX_UPLOAD_BYTES=268435456
TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT=${TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT}
TAKLITE_ALLOW_LEGACY_CLIENT_CERT=${TAKLITE_ALLOW_LEGACY_CLIENT_CERT}
TAKLITE_ACCESS_CONTROL_ENFORCE=${TAKLITE_ACCESS_CONTROL_ENFORCE}
TAKLITE_SOCKET_SEND_TIMEOUT_SECONDS=2.5
TAKLITE_GUI_UPDATE_ENABLED=true
TAKLITE_GUI_UPDATE_COMMAND=
TAKLITE_GUI_UPDATE_WORKDIR=
TAKLITE_GUI_UPDATE_TIMEOUT_SECONDS=900
TAKLITE_GUI_UPDATE_REQUEST_DIR=/data/gui-update
TAKLITE_SETTINGS_REQUEST_DIR=/data/settings
TAKLITE_FIREWALL_REQUEST_DIR=/data/firewall
TAKLITE_WG_INTERFACE=${WG_NIC}
TAKLITE_PUBLIC_INTERFACE=${SERVER_NIC}
TAKLITE_WIREGUARD_PORT=${WG_PORT}
TAKLITE_WGDASHBOARD_PORT=${WGD_PORT}
EOF
  chmod 600 "${BASE_DIR}/.env"

  log "Building and starting TAKlite"
  (
    cd "${BASE_DIR}"
    docker compose up -d --build
  )
}

write_admin_notes() {
  cat >"${ADMIN_OUT_DIR}/bootstrap-token.txt" <<EOF
TAKlite bootstrap token:
${TAKLITE_ADMIN_TOKEN}

Use this token at http://${TAKLITE_BIND_IP}:${TAKLITE_HTTP_HOST_PORT}/ after connecting WireGuard.
It creates the first TAKlite admin username/password.
Keep this file root-only for recovery.
EOF
  chmod 600 "${ADMIN_OUT_DIR}/bootstrap-token.txt"

  cat >"${ADMIN_OUT_DIR}/README.txt" <<EOF
TAKlite VPS install complete.

Admin WireGuard config:
  ${ADMIN_OUT_DIR}/${ADMIN_NAME}-${WG_NIC}.conf

Admin QR image:
  ${ADMIN_OUT_DIR}/${ADMIN_NAME}-${WG_NIC}.png

From the admin computer:
  scp root@${SERVER_ENDPOINT}:${ADMIN_OUT_DIR}/${ADMIN_NAME}-${WG_NIC}.conf .

After importing and connecting WireGuard:
  WGDashboard: http://${WGD_BIND_IP}:${WGD_PORT}
  TAKlite UI:  http://${TAKLITE_BIND_IP}:${TAKLITE_HTTP_HOST_PORT}/
  TAKlite HTTPS API: https://${TAKLITE_BIND_IP}:${TAKLITE_HTTPS_HOST_PORT}/Marti

WGDashboard login:
  username: ${WGD_USER}
  password: ${WGD_PASSWORD}

TAKlite admin token:
  ${TAKLITE_ADMIN_TOKEN}

Use this token once in the TAKlite UI to create the first username/password.
Root-only bootstrap token file:
  ${ADMIN_OUT_DIR}/bootstrap-token.txt

ATAK/WinTAK TCP connection:
  host: ${TAKLITE_BIND_IP}
  port: ${TAKLITE_COT_HOST_PORT}
  protocol: TCP
  SSL/TLS: off

ATAK/WinTAK SSL connection packages:
  create and download per-user .dp.zip packages in the TAKlite UI
  TAKlite UI: http://${TAKLITE_BIND_IP}:${TAKLITE_HTTP_HOST_PORT}/
  certificate password: ${TAKLITE_CERT_PASSWORD}

TAKlite security mode:
  access enforcement: ${TAKLITE_ACCESS_CONTROL_ENFORCE}
  TLS client cert required: ${TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT}
  legacy shared cert CN allowed: ${TAKLITE_ALLOW_LEGACY_CLIENT_CERT}

Mission/datapackage HTTP base:
  http://${TAKLITE_PUBLIC_HOST}:${TAKLITE_HTTP_HOST_PORT}/Marti

Mission/datapackage HTTPS base:
  https://${TAKLITE_BIND_IP}:${TAKLITE_HTTPS_HOST_PORT}/Marti

ATAK HTTPS truststore:
  URL from a VPN-connected phone: http://${TAKLITE_BIND_IP}:${TAKLITE_HTTP_HOST_PORT}/certs/taklite-truststore.p12
  File on VPS: ${BASE_DIR}/taklite/certs/taklite-truststore.p12
  Password: ${TAKLITE_CERT_PASSWORD}

Cloud firewall target after VPN is confirmed:
  allow ${WG_PORT}/udp publicly
  close or tightly restrict public SSH
  do not expose ${TAKLITE_HTTP_HOST_PORT}/tcp, ${TAKLITE_COT_HOST_PORT}/tcp, or ${WGD_PORT}/tcp publicly
  do not expose ${TAKLITE_HTTPS_HOST_PORT}/tcp publicly unless you intentionally want public TAK HTTPS API

Local service checks on the VPS:
  wg show
  docker compose -f ${BASE_DIR}/docker-compose.yml ps
  curl -sS -H 'X-Admin-Token: ${TAKLITE_ADMIN_TOKEN}' http://${TAKLITE_BIND_IP}:${TAKLITE_HTTP_HOST_PORT}/api/health
EOF
  chmod 600 "${ADMIN_OUT_DIR}/README.txt"
}

print_summary() {
  cat <<EOF

TAKlite VPS install complete.

IMPORTANT: SAVE THIS BOOTSTRAP INFORMATION NOW

Admin WireGuard config:
   ${ADMIN_OUT_DIR}/${ADMIN_NAME}-${WG_NIC}.conf

Admin WireGuard QR:
   ${ADMIN_OUT_DIR}/${ADMIN_NAME}-${WG_NIC}.png

TAKlite URL after VPN connection:
   http://${TAKLITE_BIND_IP}:${TAKLITE_HTTP_HOST_PORT}/

TAKlite one-time bootstrap token:
   ${TAKLITE_ADMIN_TOKEN}

Use this token to create the first TAKlite admin username/password.
A root-only copy was saved at:
   ${ADMIN_OUT_DIR}/bootstrap-token.txt

1. Pull the admin WireGuard profile:
   scp root@${SERVER_ENDPOINT}:${ADMIN_OUT_DIR}/${ADMIN_NAME}-${WG_NIC}.conf .

2. Import that .conf into WireGuard and connect.

3. Open WGDashboard:
   http://${WGD_BIND_IP}:${WGD_PORT}

   username: ${WGD_USER}
   password: ${WGD_PASSWORD}

4. Open TAKlite:
   http://${TAKLITE_BIND_IP}:${TAKLITE_HTTP_HOST_PORT}/

   one-time bootstrap token: ${TAKLITE_ADMIN_TOKEN}
   use it to create the first TAKlite admin username/password

5. ATAK/WinTAK TCP:
   ${TAKLITE_BIND_IP}:${TAKLITE_COT_HOST_PORT}
   protocol TCP, SSL/TLS off

6. ATAK/WinTAK SSL connection packages:
   open TAKlite, log in, create a connection package, then import the downloaded .dp.zip
   certificate password: ${TAKLITE_CERT_PASSWORD}

Security mode:
   access enforcement: ${TAKLITE_ACCESS_CONTROL_ENFORCE}
   TLS client cert required: ${TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT}

Saved notes:
   ${ADMIN_OUT_DIR}/README.txt

EOF

  if [[ -t 1 ]]; then
    printf 'Admin WireGuard QR:\n'
    qrencode -t ansiutf8 <"${ADMIN_OUT_DIR}/${ADMIN_NAME}-${WG_NIC}.conf" || true
  fi
}

main() {
  need_root
  detect_os
  preflight_host
  install_packages
  collect_settings
  write_wireguard_config
  enable_wireguard
  install_wgdashboard
  configure_wgdashboard
  install_wgdashboard_service
  configure_fail2ban
  install_gui_update_runner
  install_settings_runner
  install_firewall_runner
  start_taklite
  write_admin_notes
  print_summary
}

main "$@"
