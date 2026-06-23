# TAKlite Upgrade Guide

Use this guide to update an existing TAKlite VPS without rebuilding the server, replacing WireGuard, or reissuing every user connection package.

The upgrade process preserves:

- WireGuard server config and peers in `/etc/wireguard`
- WGDashboard install and login config
- Admin recovery files in `/root/taklite-admin`
- TAKlite `.env`
- TAKlite SQLite database
- TAKlite local CA, server certs, and generated client cert packages
- Uploaded datapackages

Do not run `install.sh` for an upgrade. The installer is for fresh VPS setup.

## Before You Start

Connect to the VPS by SSH. This can be public SSH if still open, or SSH over the WireGuard tunnel:

```bash
ssh root@YOUR_VPS_PUBLIC_IP
```

Or, over VPN:

```bash
ssh root@10.66.66.1
```

Find the current TAKlite app directory:

```bash
if [ -f /root/taklite/docker-compose.yml ]; then
  APP_DIR=/root/taklite
elif [ -f /root/taklite-vps-bundle/docker-compose.yml ]; then
  APP_DIR=/root/taklite-vps-bundle
else
  echo "Could not find TAKlite app directory" >&2
  exit 1
fi

cd "$APP_DIR"
docker compose ps
curl -sS http://10.66.66.1:8080/api/health
```

## Back Up The Existing Install

Create a root-only backup before replacing anything:

```bash
if [ -f /root/taklite/docker-compose.yml ]; then
  APP_DIR=/root/taklite
elif [ -f /root/taklite-vps-bundle/docker-compose.yml ]; then
  APP_DIR=/root/taklite-vps-bundle
else
  echo "Could not find TAKlite app directory" >&2
  exit 1
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="/root/taklite-backups/$STAMP"

mkdir -p "$BACKUP_DIR"
chmod 700 /root/taklite-backups "$BACKUP_DIR"

rsync -a "$APP_DIR"/ "$BACKUP_DIR/app"/

tar -czf "$BACKUP_DIR/wireguard-admin.tgz" \
  /etc/wireguard \
  /root/taklite-admin \
  /opt/WGDashboard/src/wg-dashboard.ini \
  2>/dev/null || true

echo "Backup saved at: $BACKUP_DIR"
```

This backup includes `.env`, the SQLite DB, certs, generated connection packages, and uploaded datapackages.

## Upload The New Release

From your admin computer, upload the new release zip:

```bash
scp TAKlite-vX.Y.Z.zip root@YOUR_VPS_PUBLIC_IP:/root/
```

Or, if SSH is only available over VPN:

```bash
scp TAKlite-vX.Y.Z.zip root@10.66.66.1:/root/
```

## Stage The New Files

On the VPS:

```bash
if [ -f /root/taklite/docker-compose.yml ]; then
  APP_DIR=/root/taklite
elif [ -f /root/taklite-vps-bundle/docker-compose.yml ]; then
  APP_DIR=/root/taklite-vps-bundle
else
  echo "Could not find TAKlite app directory" >&2
  exit 1
fi

RELEASE_ZIP="/root/TAKlite-vX.Y.Z.zip"
STAGE_DIR="/root/taklite-update-$(date -u +%Y%m%dT%H%M%SZ)"

if ! command -v unzip >/dev/null 2>&1; then
  apt-get update
  apt-get install -y unzip
fi

mkdir -p "$STAGE_DIR"
unzip -q "$RELEASE_ZIP" -d "$STAGE_DIR"

SRC_DIR="$(find "$STAGE_DIR" -maxdepth 3 -name docker-compose.yml -exec dirname {} \; | head -n1)"
if [ -z "$SRC_DIR" ]; then
  echo "Could not find docker-compose.yml in release zip" >&2
  exit 1
fi

echo "Staged release source: $SRC_DIR"
```

## Apply The Upgrade

Stop TAKlite, copy the new app files, preserve runtime state, rebuild, and restart:

```bash
cd "$APP_DIR"
docker compose down

rsync -a --delete \
  --exclude '.env' \
  --exclude 'taklite/data/' \
  --exclude 'taklite/certs/' \
  --exclude 'taklite/packages/' \
  "$SRC_DIR"/ "$APP_DIR"/

chmod +x "$APP_DIR/install.sh" "$APP_DIR/smoke-test.sh"

grep -q '^TAKLITE_MAX_UPLOAD_BYTES=' "$APP_DIR/.env" || printf '\nTAKLITE_MAX_UPLOAD_BYTES=268435456\n' >> "$APP_DIR/.env"
grep -q '^TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT=' "$APP_DIR/.env" || printf 'TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT=false\n' >> "$APP_DIR/.env"
grep -q '^TAKLITE_ALLOW_LEGACY_CLIENT_CERT=' "$APP_DIR/.env" || printf 'TAKLITE_ALLOW_LEGACY_CLIENT_CERT=true\n' >> "$APP_DIR/.env"

docker compose up -d --build
```

The `rsync` command intentionally excludes `.env`, `taklite/data`, `taklite/certs`, and `taklite/packages`. Those directories contain the server identity and runtime data.

## Verify The Upgrade

On the VPS:

```bash
cd "$APP_DIR"
docker compose ps
docker logs --tail 80 taklite
curl -sS http://10.66.66.1:8080/api/health
```

From an admin browser over VPN:

```text
http://10.66.66.1:8080/
```

Check:

- Admin login still works.
- Existing Connection Users still appear.
- Existing Connection Packages still appear.
- Existing datapackages still appear.
- ATAK/WinTAK clients reconnect.
- PLI, chat, markers, and datapackages still work.

## Roll Back

If the upgrade fails, restore the backup created earlier:

```bash
if [ -f /root/taklite/docker-compose.yml ]; then
  APP_DIR=/root/taklite
elif [ -f /root/taklite-vps-bundle/docker-compose.yml ]; then
  APP_DIR=/root/taklite-vps-bundle
else
  echo "Could not find TAKlite app directory" >&2
  exit 1
fi

BACKUP_DIR="/root/taklite-backups/YYYYMMDDTHHMMSSZ"

cd "$APP_DIR"
docker compose down || true

rsync -a --delete "$BACKUP_DIR/app"/ "$APP_DIR"/

cd "$APP_DIR"
docker compose up -d --build
docker compose ps
docker logs --tail 80 taklite
```

Replace `YYYYMMDDTHHMMSSZ` with the actual backup folder name.

## What Not To Do

- Do not rerun `install.sh` on an existing server for a normal update.
- Do not delete `.env`.
- Do not delete `taklite/certs`.
- Do not delete `taklite/data`.
- Do not delete `taklite/packages`.
- Do not copy certs or `.env` from one VPS to another.
- Do not overwrite `/etc/wireguard` unless intentionally restoring a full server backup.

## Version Notes

Patch releases should normally be upgradeable with this guide.

If a future release requires a special migration, the release notes should say so clearly and include any extra commands before the `docker compose up -d --build` step.
