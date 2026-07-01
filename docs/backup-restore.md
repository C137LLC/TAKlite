# TAKlite Backup And Restore

Use this when preserving or restoring an existing TAKlite deployment. Do not use a backup restore to create a new independent VPS unless you intentionally want to reuse the same WireGuard keys, TAKlite CA, user certificates, admin state, and datapackages.

## What To Back Up

Back up these paths from the VPS:

```bash
/root/taklite/.env
/root/taklite/taklite/data
/root/taklite/taklite/certs
/root/taklite/taklite/packages
/etc/wireguard
/root/taklite-admin
/opt/WGDashboard/src/wg-dashboard.ini
```

If the install directory is `/root/TAKlite`, use that path instead of `/root/taklite`.

## Create A Manual Backup

Run this on the VPS as root:

```bash
set -Eeuo pipefail
APP_DIR=/root/taklite
[ -f /root/TAKlite/docker-compose.yml ] && APP_DIR=/root/TAKlite
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="/root/taklite-manual-backups/$STAMP"

mkdir -p "$BACKUP_DIR"
chmod 700 /root/taklite-manual-backups "$BACKUP_DIR"

tar -czf "$BACKUP_DIR/taklite-app-state.tgz" \
  -C "$APP_DIR" \
  .env taklite/data taklite/certs taklite/packages

tar -czf "$BACKUP_DIR/wireguard-admin.tgz" \
  /etc/wireguard \
  /root/taklite-admin \
  /opt/WGDashboard/src/wg-dashboard.ini 2>/dev/null || true

echo "Backup written to: $BACKUP_DIR"
```

## Pull A Backup To Your Admin Computer

Run this from your admin computer, not inside the VPS:

```bash
scp -r root@YOUR_VPS_PUBLIC_IP:/root/taklite-manual-backups/YYYYMMDDTHHMMSSZ /path/to/local/backup-folder
```

Example for macOS/Linux:

```bash
scp -r root@203.0.113.10:/root/taklite-manual-backups/20260630T180000Z ~/Documents/TAKlite-backups/
```

## Restore To The Same Server

Run this on the VPS as root:

```bash
set -Eeuo pipefail
APP_DIR=/root/taklite
[ -f /root/TAKlite/docker-compose.yml ] && APP_DIR=/root/TAKlite
BACKUP_DIR=/root/taklite-manual-backups/YYYYMMDDTHHMMSSZ

cd "$APP_DIR"
docker compose down || true

tar -xzf "$BACKUP_DIR/taklite-app-state.tgz" -C "$APP_DIR"
tar -xzf "$BACKUP_DIR/wireguard-admin.tgz" -C / || true

chmod 600 "$APP_DIR/taklite/certs/taklite-ca.key" "$APP_DIR/taklite/certs/taklite.key" 2>/dev/null || true
chmod 700 /root/taklite-admin 2>/dev/null || true
systemctl restart "wg-quick@wg0" 2>/dev/null || true
systemctl restart wg-dashboard 2>/dev/null || true
docker compose up -d --build
```

## Fresh VPS Warning

For a brand-new VPS, prefer a fresh TAKlite install. Fresh installs create new:

- WireGuard keys and peers
- TAKlite CA and server certificates
- Admin bootstrap token
- WGDashboard credentials

Only restore old identity material when you intentionally want the new VPS to be the same deployment.
