# TAKlite User Guide

## Purpose

TAKlite is a lightweight TAK relay and datapackage service for small ATAK/WinTAK teams over WireGuard VPN.

It provides:

- WireGuard VPN access for admins and TAK clients
- WGDashboard for VPN peer management
- TAKlite admin dashboard for TAK users, clients, and datapackages
- TLS CoT TCP for ATAK/WinTAK on `10.66.66.1:8089`
- Plain CoT TCP test port on `10.66.66.1:58087`
- Marti-style datapackage upload, search, download, and delete
- Connection User portal for downloading ATAK/WinTAK `.dp.zip` certificate bundles

## Network Model

TAKlite is designed to be VPN-first.

Public internet:

- `51820/udp` WireGuard only
- Temporary `22/tcp` SSH only during setup, then close or restrict it

VPN-only:

- `22/tcp` SSH
- `10086/tcp` WGDashboard
- `8080/tcp` TAKlite admin UI, client portal, and HTTP datapackage API
- `8443/tcp` TAKlite HTTPS datapackage API
- `58087/tcp` plain CoT TCP
- `8089/tcp` TLS CoT TCP

Portable Docker mode is different. It runs TAKlite only and does not install WireGuard, WGDashboard, fail2ban, systemd services, or firewall rules. Use portable mode for local testing or when VPN/firewall are handled outside TAKlite.

## Per-Install Security

Every fresh VPS installation generates new security material.

Do not copy `/root/taklite-admin`, `/etc/wireguard`, `taklite/certs`, `taklite/data`, or an old `.env` from one VPS to another.

Generated per install:

- WireGuard server private key
- Initial admin WireGuard peer key and preshared key
- WGDashboard password
- TAKlite bootstrap token
- TAKlite local certificate authority
- TAKlite server certificate
- Generated ATAK/WinTAK user certificates

The TAKlite certificate password defaults to `atakatak` for easier ATAK/WinTAK imports unless changed during install.

The installer saves root-only recovery notes here:

```text
/root/taklite-admin/README.txt
```

## Fresh VPS Install

Create a fresh supported Linux VPS. Supported full-appliance targets include Ubuntu 22.04 LTS or newer, Debian 12 Bookworm or newer, and Raspberry Pi OS 64-bit Bookworm or newer. See [Platform Support](platform-support.md).

Option A, deploy directly from a GitHub clone while logged into the VPS shell as `root`:

```bash
cd /root
apt-get update
apt-get install -y git
rm -rf /root/taklite
git clone https://github.com/C137LLC/TAKlite.git /root/taklite
cd /root/taklite
chmod +x install.sh smoke-test.sh
./install.sh
```

Option B, deploy from a release zip:

```bash
scp taklite-vps-bundle.zip root@YOUR_VPS_PUBLIC_IP:/root/
```

On the VPS:

```bash
cd /root
unzip taklite-vps-bundle.zip
cd /root/taklite-vps-bundle
chmod +x install.sh smoke-test.sh
./install.sh
```

Use the defaults unless the VPS environment requires different values.

For local Docker Desktop testing instead of a VPS:

```bash
./portable-start.sh
```

On Windows PowerShell:

```powershell
.\portable-start.ps1
```

Important defaults:

```text
WireGuard server: 10.66.66.1
Admin VPN peer: 10.66.66.2
WGDashboard: http://10.66.66.1:10086
TAKlite admin: http://10.66.66.1:8080/
Client portal: http://10.66.66.1:8080/connect/
TLS CoT: 10.66.66.1:8089
Plain CoT: 10.66.66.1:58087
Certificate password: atakatak unless changed during install; saved in `/root/taklite-admin/README.txt`
```

If TAKlite HTTPS/Marti was installed on a custom port, ATAK/WinTAK secure server or datapackage settings should use that custom port.

## Save Install Output

At the end of installation, save:

- Admin WireGuard `.conf`
- Admin WireGuard QR path
- WGDashboard username/password
- TAKlite bootstrap token
- TAKlite admin URL

Recovery files are saved on the VPS:

```text
/root/taklite-admin/README.txt
/root/taklite-admin/bootstrap-token.txt
/root/taklite-admin/admin-wg0.conf
/root/taklite-admin/admin-wg0.png
```

If needed:

```bash
cat /root/taklite-admin/README.txt
```

## Admin VPN Login

Pull the admin WireGuard config:

```bash
scp root@YOUR_VPS_PUBLIC_IP:/root/taklite-admin/admin-wg0.conf .
```

Or use `rsync`:

```bash
rsync -av root@YOUR_VPS_PUBLIC_IP:/root/taklite-admin/admin-wg0.conf .
```

Import `admin-wg0.conf` into WireGuard and connect.

Open:

```text
WGDashboard: http://10.66.66.1:10086
TAKlite:     http://10.66.66.1:8080/
```

## First TAKlite Admin Account

Open:

```text
http://10.66.66.1:8080/
```

Use the bootstrap token from install output or:

```bash
cat /root/taklite-admin/bootstrap-token.txt
```

Create the first TAKlite admin username/password.

## Create A TAK Device User

Use this workflow for each ATAK/WinTAK device.

1. In WGDashboard, create a WireGuard peer for the user device.
2. Give the user the WireGuard QR or `.conf`.
3. In TAKlite, open Connection Users.
4. Enter a username, temporary password, and optional note.
5. Click Create User.
6. The user appears in the Connection Users table.
7. Use Download DP.zip, QR, or Copy URL.

For bulk onboarding:

1. Open Connection Users.
2. Click Create Bulk Users.
3. Enter a name prefix such as `user`.
4. Enter the number of users to create.
5. Click Create Batch.
6. TAKlite creates users such as `user1`, `user2`, and `user3`, with matching `.dp.zip` packages.
7. Copy or download the CSV shown after creation. Bulk-created portal users use `atakatak` as the shared portal password.

Connection User actions:

- Download DP.zip: admin downloads the user's ATAK/WinTAK cert bundle
- Copy URL: copies the VPN-only portal URL
- QR: shows a QR for the user's portal page
- Edit: updates display name and note
- Reset Password: changes the user's portal password
- Allow/Disable Re-download: controls repeated downloads
- Reissue: revokes the old cert bundle and creates a fresh one
- Revoke: disables the user and cert package
- Delete: removes the user record, with optional generated file deletion

## User Device Flow

For the end user:

1. Scan/import the WireGuard config.
2. Connect WireGuard.
3. Open the TAKlite portal QR or URL:

```text
http://10.66.66.1:8080/connect/
```

4. Log in with the username/password from the admin.
5. Download the `.dp.zip`.
6. Import the `.dp.zip` into ATAK or WinTAK.
7. If prompted, use `atakatak` unless the admin changed the certificate password during install. The active value is saved in:

```text
/root/taklite-admin/README.txt
```

The imported package configures:

```text
Host: 10.66.66.1
Port: 8089
Protocol: SSL/TLS
```

## ATAK Test

On Android:

1. Confirm WireGuard handshake is active.
2. Import the `.dp.zip` in ATAK.
3. Confirm the server connection turns green.
4. Drop a point.
5. Send chat.
6. Send a datapackage.
7. Confirm other clients receive the point/chat/datapackage.

## WinTAK Test

On Windows:

1. Confirm WireGuard is connected.
2. Import the `.dp.zip` in WinTAK.
3. Confirm the server connection turns green.
4. Drop a point.
5. Send chat.
6. Send a datapackage.
7. Confirm ATAK receives it.

## Datapackage Admin

The TAKlite dashboard shows uploaded datapackages.

Admin actions:

- Download datapackage to local machine
- Delete datapackage record and stored file

Expected API activity in logs:

```text
POST /Marti/sync/missionupload
GET /Marti/sync/search
GET /Marti/sync/content?hash=...
```

## Connected Clients

The dashboard shows:

- Callsign/name
- UID
- IP address
- Transport mode
- Client certificate common name
- Connection uptime
- Connected time
- Last seen time

TLS clients should show a certificate common name matching the created Connection User or package name.

## Updating TAKlite

Use `update.sh` for normal upgrades. Do not rerun `install.sh` on an existing server unless you are intentionally creating a fresh deployment with new WireGuard and TAKlite credentials.

Updates preserve the live `.env`, so custom ports and network settings stay in place. This includes TAKlite HTTP/HTTPS/CoT ports, WireGuard settings, and the WGDashboard URL.

Release zip workflow:

```bash
scp TAKlite-vX.Y.Z.zip root@10.66.66.1:/root/

ssh root@10.66.66.1

if [ -f /root/taklite/docker-compose.yml ]; then
  APP_DIR=/root/taklite
elif [ -f /root/TAKlite/docker-compose.yml ]; then
  APP_DIR=/root/TAKlite
elif [ -f /root/taklite-vps-bundle/docker-compose.yml ]; then
  APP_DIR=/root/taklite-vps-bundle
else
  echo "Could not find TAKlite app directory" >&2
  exit 1
fi

bash "$APP_DIR/update.sh" /root/TAKlite-vX.Y.Z.zip
```

Git clone workflow:

```bash
ssh root@10.66.66.1
cd /root
rm -rf /root/TAKlite-update
git clone https://github.com/C137LLC/TAKlite.git /root/TAKlite-update

bash /root/TAKlite-update/update.sh --from-dir /root/TAKlite-update
```

For a specific release tag:

```bash
cd /root
rm -rf /root/TAKlite-update
git clone --branch vX.Y.Z --depth 1 \
  https://github.com/C137LLC/TAKlite.git \
  /root/TAKlite-update

bash /root/TAKlite-update/update.sh --from-dir /root/TAKlite-update
```

Never `git clone` directly over the live TAKlite app directory. Clone into a staging directory and let the staged `update.sh` copy application files while preserving `.env`, certs, database, datapackages, and packages.

## Uninstalling Or Reinstalling

Use uninstall or reinstall only when you intentionally want to wipe the current deployment. Use `update.sh` for normal upgrades.

Warning: both workflows stop WireGuard. If your SSH session is connected through the WireGuard tunnel, the shell can disconnect before the command finishes. Before running either command, make sure public SSH/22 is open from a network you can reach, or have VPS console access ready.

Uninstall wipes TAKlite, WGDashboard, WireGuard config, admin recovery files, certs, users, datapackages, generated packages, and TAKlite backups:

```bash
cd /root
rm -rf /root/TAKlite-update
git clone --depth 1 https://github.com/C137LLC/TAKlite.git /root/TAKlite-update

bash /root/TAKlite-update/uninstall.sh --yes
```

Reinstall wipes the deployment and starts a fresh install:

```bash
cd /root
rm -rf /root/TAKlite-update
git clone --depth 1 https://github.com/C137LLC/TAKlite.git /root/TAKlite-update

bash /root/TAKlite-update/reinstall.sh --yes
```

## Troubleshooting

Watch logs:

```bash
cd /root/taklite-vps-bundle
docker logs -f taklite
```

Check services:

```bash
docker compose ps
curl -fsS http://10.66.66.1:8080/api/health
wg show
```

Check ports:

```bash
ss -tulpn | grep -E '(:8080|:8443|:58087|:8089|:10086|:51820)'
```

Common issues:

- Portal login invalid: confirm the user was created under Connection Users, not Connection Packages.
- Invalid truststore: create a fresh Connection User after deploy and import the newest `.dp.zip`.
- Red TAK connection: confirm VPN is connected, use `10.66.66.1:8089:ssl`, and watch logs for `cert_cn=...`.
- Datapackage send fails: confirm the TAK client has the server connection from the `.dp.zip` and can reach `10.66.66.1:8080` plus the configured HTTPS/Marti port, usually `8443`.

## Smoke Test

From the VPS:

```bash
cd /root/taklite-vps-bundle
./smoke-test.sh 10.66.66.1 TAKLITE_BOOTSTRAP_TOKEN_OR_ADMIN_TOKEN
```

## Routine Admin Checklist

1. Connect admin WireGuard.
2. Open WGDashboard.
3. Open TAKlite admin dashboard.
4. Create WireGuard peer for user.
5. Create TAKlite Connection User.
6. Give user WireGuard QR.
7. Give user portal QR/link and password.
8. User downloads/imports `.dp.zip`.
9. Confirm client appears in Connected Clients.
10. Test PLI, chat, marker drops, and datapackages.
