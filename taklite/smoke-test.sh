#!/usr/bin/env bash
set -Eeuo pipefail

HOST="${1:-10.66.66.1}"
TOKEN="${2:-}"

if [[ -z "${TOKEN}" ]]; then
  echo "usage: ./smoke-test.sh <host> <taklite-admin-token>" >&2
  exit 2
fi

echo "Checking TAKlite health..."
curl -fsS -H "X-Admin-Token: ${TOKEN}" "http://${HOST}:8080/api/health"
echo

tmp_pkg="$(mktemp -t taklite-smoke.XXXXXX.dp.zip)"
printf 'TAKlite smoke package %s\n' "$(date -u +%FT%TZ)" >"${tmp_pkg}"

echo "Uploading datapackage..."
upload_url="$(
  curl -fsS \
    -F "assetfile=@${tmp_pkg};filename=taklite-smoke.dp.zip" \
    "http://${HOST}:8080/Marti/sync/missionupload?creatorUid=smoke-test"
)"
echo "${upload_url}"

echo "Listing datapackages..."
curl -fsS -H "X-Admin-Token: ${TOKEN}" "http://${HOST}:8080/api/datapackages"
echo

echo "CoT relay port check..."
python3 - "${HOST}" <<'PY'
import socket
import sys
host = sys.argv[1]
with socket.create_connection((host, 58087), timeout=5) as s:
    event = b'<event version="2.0" uid="taklite-smoke" type="a-f-G-U-C" how="m-g" time="2026-01-01T00:00:00Z" start="2026-01-01T00:00:00Z" stale="2026-01-01T00:10:00Z"><point lat="38.8895" lon="-77.0353" hae="0" ce="10" le="10"/><detail><contact callsign="TAKlite Smoke"/></detail></event>'
    s.sendall(event)
print("CoT TCP accepted a test event")
PY

echo "Smoke test complete."
