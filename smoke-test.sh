#!/usr/bin/env bash
set -Eeuo pipefail

HOST="${1:-10.66.66.1}"
TOKEN="${2:-}"
TOKEN_TYPE="${3:-admin-token}"
HTTP_PORT="${TAKLITE_HTTP_HOST_PORT:-8080}"
COT_PORT="${TAKLITE_COT_HOST_PORT:-58087}"

if [[ -z "${TOKEN}" ]]; then
  echo "usage: ./smoke-test.sh <host> <bootstrap-token-or-session-token> [admin-token|session-token]" >&2
  exit 2
fi

case "${TOKEN_TYPE}" in
  admin-token)
    AUTH_HEADER="X-Admin-Token: ${TOKEN}"
    ;;
  session-token)
    AUTH_HEADER="X-Session-Token: ${TOKEN}"
    ;;
  *)
    echo "token type must be admin-token or session-token" >&2
    exit 2
    ;;
esac

echo "Checking TAKlite health..."
curl -fsS "http://${HOST}:${HTTP_PORT}/api/health"
echo

tmp_pkg="$(mktemp -t taklite-smoke.XXXXXX.dp.zip)"
pkg_dir="$(mktemp -d)"
trap 'rm -f "${tmp_pkg}"; rm -rf "${pkg_dir}"' EXIT
printf 'TAKlite smoke package %s\n' "$(date -u +%FT%TZ)" >"${pkg_dir}/README.txt"
(
  cd "${pkg_dir}"
  zip -q "${tmp_pkg}" README.txt
)

echo "Uploading datapackage..."
upload_url="$(
  curl -fsS \
    -F "assetfile=@${tmp_pkg};filename=taklite-smoke.dp.zip" \
    "http://${HOST}:${HTTP_PORT}/Marti/sync/missionupload?creatorUid=smoke-test"
)"
echo "${upload_url}"

echo "Listing datapackages..."
curl -fsS -H "${AUTH_HEADER}" "http://${HOST}:${HTTP_PORT}/api/datapackages"
echo

echo "CoT relay port check..."
python3 - "${HOST}" "${COT_PORT}" <<'PY'
import socket
import sys
host = sys.argv[1]
port = int(sys.argv[2])
with socket.create_connection((host, port), timeout=5) as s:
    event = b'<event version="2.0" uid="taklite-smoke" type="a-f-G-U-C" how="m-g" time="2026-01-01T00:00:00Z" start="2026-01-01T00:00:00Z" stale="2026-01-01T00:10:00Z"><point lat="38.8895" lon="-77.0353" hae="0" ce="10" le="10"/><detail><contact callsign="TAKlite Smoke"/></detail></event>'
    s.sendall(event)
print("CoT TCP accepted a test event")
PY

echo "Smoke test complete."
