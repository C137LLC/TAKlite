#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

SCRIPT_NAME="taklite-portable"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() {
  printf '[%s] %s\n' "${SCRIPT_NAME}" "$*"
}

die() {
  printf '[%s] ERROR: %s\n' "${SCRIPT_NAME}" "$*" >&2
  exit 1
}

prompt_default() {
  local prompt="$1"
  local default="$2"
  local value
  read -r -p "${prompt} [${default}]: " value
  printf '%s' "${value:-$default}"
}

random_token() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import secrets, string; alphabet=string.ascii_letters+string.digits+"._=-"; print("".join(secrets.choice(alphabet) for _ in range(32)))'
  elif command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 32 | tr -d '/+'
  else
    date +taklite-%s
  fi
}

detect_lan_ip() {
  if command -v ip >/dev/null 2>&1; then
    ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i=="src") print $(i+1)}' | head -n1
  elif command -v route >/dev/null 2>&1 && command -v ipconfig >/dev/null 2>&1; then
    local iface
    iface="$(route get default 2>/dev/null | awk '/interface:/ {print $2; exit}')"
    [[ -n "${iface}" ]] && ipconfig getifaddr "${iface}" 2>/dev/null || true
  fi
}

docker_compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    die "Docker Compose was not found. Install Docker Desktop or Docker Engine with the Compose plugin."
  fi
}

command -v docker >/dev/null 2>&1 || die "Docker was not found. Install Docker Desktop or Docker Engine first."
docker info >/dev/null 2>&1 || die "Docker is not running or this user cannot access Docker."

cd "${BASE_DIR}"
install -d -m 700 taklite/data taklite/packages taklite/certs

if [[ -f .env ]]; then
  log "Using existing .env"
else
  local_ip="$(detect_lan_ip || true)"
  [[ -n "${local_ip:-}" ]] || local_ip="127.0.0.1"
  bind_ip="$(prompt_default "Bind address: 127.0.0.1 for this computer only, 0.0.0.0 for LAN testing" "127.0.0.1")"
  server_host_default="127.0.0.1"
  if [[ "${bind_ip}" == "0.0.0.0" ]]; then
    server_host_default="${local_ip}"
  fi
  server_host="$(prompt_default "TAKlite host/IP ATAK clients will use" "${server_host_default}")"
  admin_token="$(prompt_default "TAKlite bootstrap token" "$(random_token)")"
  container_user="10001:10001"
  if [[ "$(uname -s 2>/dev/null || true)" != "Linux" ]]; then
    container_user="$(id -u):$(id -g)"
  fi

  cat >.env <<EOF
WG_BIND_IP=${bind_ip}
TAKLITE_PUBLIC_HOST=${server_host}
TAKLITE_SERVER_HOST=${server_host}
TAKLITE_CONTAINER_USER=${container_user}
TAKLITE_AUTO_INIT_CERTS=true
TAKLITE_ADMIN_TOKEN=${admin_token}
TAKLITE_CERT_PASSWORD=atakatak
TAKLITE_COT_HOST_PORT=58087
TAKLITE_COT_TLS_HOST_PORT=8089
TAKLITE_HTTP_HOST_PORT=8080
TAKLITE_HTTPS_HOST_PORT=8443
TAKLITE_WGDASHBOARD_URL=
TAKLITE_MAX_UPLOAD_BYTES=268435456
TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT=true
TAKLITE_ALLOW_LEGACY_CLIENT_CERT=false
TAKLITE_ACCESS_CONTROL_ENFORCE=true
TAKLITE_SOCKET_SEND_TIMEOUT_SECONDS=2.5
TAKLITE_GUI_UPDATE_ENABLED=false
TAKLITE_GUI_UPDATE_COMMAND=
TAKLITE_GUI_UPDATE_WORKDIR=
TAKLITE_GUI_UPDATE_TIMEOUT_SECONDS=900
TAKLITE_GUI_UPDATE_REQUEST_DIR=
TAKLITE_SETTINGS_REQUEST_DIR=
TAKLITE_FIREWALL_REQUEST_DIR=
TAKLITE_WG_INTERFACE=
TAKLITE_PUBLIC_INTERFACE=
TAKLITE_WIREGUARD_PORT=
TAKLITE_WGDASHBOARD_PORT=
EOF
  chmod 600 .env
fi

log "Starting TAKlite portable container"
docker_compose up -d --build

http_port="$(awk -F= '/^TAKLITE_HTTP_HOST_PORT=/ {print $2}' .env | tail -n1)"
https_port="$(awk -F= '/^TAKLITE_HTTPS_HOST_PORT=/ {print $2}' .env | tail -n1)"
host="$(awk -F= '/^TAKLITE_PUBLIC_HOST=/ {print $2}' .env | tail -n1)"
token="$(awk -F= '/^TAKLITE_ADMIN_TOKEN=/ {print $2}' .env | tail -n1)"

cat <<EOF

TAKlite portable mode is running.

Dashboard:
  http://${host}:${http_port}/

HTTPS/Marti:
  https://${host}:${https_port}/Marti

Bootstrap token:
  ${token}

Portable mode does not install WireGuard, WGDashboard, systemd services, or firewall rules.

EOF
