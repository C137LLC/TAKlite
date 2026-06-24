# TAKlite Deployment And Update Lifecycle

This guide separates two admin tasks that must not be mixed:

- New deployment or cloned snapshot rekey: create fresh WireGuard, WGDashboard, TAKlite admin, CA, server cert, and ATAK/WinTAK user certs.
- Existing deployment update: replace TAKlite application files while preserving VPN peers, TAKlite certs, datapackages, SQLite data, and generated connection packages.

## Recommended Snapshot Strategy

Best option: snapshot the VPS before running `install.sh`.

That gives you a clean base image with Ubuntu, Docker, Zello, firewall preferences, and any common tools, but without reused TAKlite/WireGuard identity.

For every new VPS created from that base snapshot:

1. Upload or clone TAKlite.
2. Run `./install.sh`.
3. Answer prompts for that environment.
4. Pull the generated admin WireGuard `.conf`.
5. Connect VPN.
6. Create the first TAKlite admin account with the one-time bootstrap token.
7. Create new WireGuard peers and TAKlite connection users.

This produces new VPN keys, admin credentials, TAKlite CA, server certs, and ATAK/WinTAK client certs for every VPS.

## Snapshot Already Contains TAKlite

If the snapshot already has TAKlite and WireGuard installed, do not reuse it as-is for a new deployment. It would reuse VPN keys, WGDashboard credentials, TAKlite CA, server certs, client certs, admin data, and possibly datapackages.

## Option A: Rebuild From A Cleaner Snapshot

Create a new base snapshot from a VPS that has only:

- Ubuntu
- Docker
- Zello On-Prem, if desired
- Firewall baseline
- no `/etc/wireguard/wg0.conf`
- no `/root/taklite-admin`
- no TAKlite `.env`, certs, data, or packages

Then run `install.sh` fresh on each new VPS.

This is the safest and cleanest repeatable deployment path.

## Option B: Destructive Rekey Existing Snapshot

Use this only when you intentionally want the cloned VPS to become a new independent deployment.

This removes TAKlite and WireGuard identity, but does not touch a sibling Zello install in `/root/docker`.

```bash
systemctl stop wg-dashboard 2>/dev/null || true
systemctl stop wg-quick@wg0 2>/dev/null || true
docker stop taklite 2>/dev/null || true
docker rm taklite 2>/dev/null || true

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "/root/taklite-rekey-backups/$STAMP"
chmod 700 /root/taklite-rekey-backups "/root/taklite-rekey-backups/$STAMP"

tar -czf "/root/taklite-rekey-backups/$STAMP/old-identity.tgz" \
  /etc/wireguard \
  /root/taklite-admin \
  /opt/WGDashboard \
  /root/taklite/.env \
  /root/taklite/taklite/data \
  /root/taklite/taklite/certs \
  /root/taklite/taklite/packages \
  2>/dev/null || true

rm -rf /etc/wireguard/wg0.conf /root/taklite-admin /opt/WGDashboard
rm -rf /root/taklite/.env /root/taklite/taklite/data /root/taklite/taklite/certs /root/taklite/taklite/packages

cd /root/taklite
./install.sh
```

If your app directory is `/root/TAKlite` or `/root/taklite-vps-bundle`, replace `/root/taklite` in the commands above.

## Zello Co-Hosted VPS

Zello On-Prem commonly needs `8443/tcp`. TAKlite can run next to it cleanly.

During TAKlite install, use:

```text
TAKlite HTTP/admin host port: 8080
TAKlite HTTPS/Marti host port: 18443
TAKlite plain CoT TCP host port: 58087
TAKlite TLS CoT TCP host port: 8089
```

After this, ATAK/WinTAK should use:

```text
TLS CoT: 10.66.66.1:8089:ssl
Secure server / datapackage port: 18443
```

Only WireGuard UDP should be public. Keep TAKlite, WGDashboard, SSH-over-VPN, and Zello admin access behind the tunnel unless you intentionally expose something.

## Existing Server Update

For normal TAKlite releases, do not run `install.sh`.

Use `update.sh`. It preserves:

- `/etc/wireguard`
- `/root/taklite-admin`
- WGDashboard config
- TAKlite `.env`
- TAKlite SQLite database
- TAKlite CA/server/client cert material
- generated connection package records
- uploaded datapackages

Updates do not overwrite the existing `TAKLITE_CERT_PASSWORD` in `.env`. If an older server used a long certificate password and you want to switch to `atakatak`, edit `/root/taklite/.env`, restart TAKlite, then reissue affected connection users or create new connection packages. Existing already-downloaded `.dp.zip` files keep the password they were created with.

From your admin computer:

```bash
scp TAKlite-vX.Y.Z.zip root@YOUR_VPS_PUBLIC_IP:/root/
```

Or over VPN:

```bash
scp TAKlite-vX.Y.Z.zip root@10.66.66.1:/root/
```

On the VPS:

```bash
cd /root/taklite
./update.sh /root/TAKlite-vX.Y.Z.zip
```

If the currently installed release does not have `update.sh`, extract the new release and run the updater from the staged copy:

```bash
cd /root
python3 - <<'PY'
import pathlib, zipfile
zip_path = pathlib.Path("/root/TAKlite-vX.Y.Z.zip")
stage = pathlib.Path("/root/taklite-update-stage")
stage.mkdir(exist_ok=True)
with zipfile.ZipFile(zip_path) as z:
    z.extractall(stage)
print(next(stage.rglob("update.sh")))
PY

bash "$(find /root/taklite-update-stage -name update.sh | head -n1)" --release-zip /root/TAKlite-vX.Y.Z.zip --app-dir /root/taklite
```

## Update Rollback

`update.sh` creates a backup under:

```text
/root/taklite-backups/YYYYMMDDTHHMMSSZ
```

To roll back:

```bash
BACKUP_DIR=/root/taklite-backups/YYYYMMDDTHHMMSSZ
APP_DIR=/root/taklite

cd "$APP_DIR"
docker compose down || true
rsync -a --delete "$BACKUP_DIR/app/" "$APP_DIR/"
docker compose up -d --build
docker compose ps
```

Replace `YYYYMMDDTHHMMSSZ` with the actual backup directory.
