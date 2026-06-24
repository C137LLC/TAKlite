<p align="center">
  <img src="assets/taklite-logo.png" alt="TAKlite - VPN TAK RELAY" width="760">
</p>

# TAKlite

TAKlite is a lightweight WireGuard-hosted TAK relay and datapackage service for small ATAK/WinTAK teams.

It installs a VPN-first stack on a fresh Ubuntu VPS: WireGuard, WGDashboard, a TAKlite admin dashboard, TLS CoT, plain TCP CoT, datapackage handling, and a simple user portal for ATAK/WinTAK `.dp.zip` connection bundles.

## What It Does

- Installs WireGuard with an initial admin peer
- Runs WGDashboard over the VPN for peer management
- Runs TAKlite over the VPN for TAK users, clients, and datapackages
- Creates ATAK/WinTAK TLS connection packages
- Provides user/password portal downloads with QR/link support
- Supports bulk Connection User creation for faster onboarding
- Relays PLI, chat, markers, drawings, polygons, and CoT traffic
- Supports datapackage upload, search, download, receive, and delete
- Generates fresh keys, tokens, passwords, CA, and certs on every install

## Dashboard Preview

![TAKlite admin dashboard](docs/images/admin-dashboard.png)

## Requirements

- Fresh Ubuntu 26.04 LTS x64 VPS
- Root SSH access for initial setup
- Cloud firewall/security group control
- WireGuard app on the admin computer or phone
- ATAK or WinTAK clients for testing
- Public `51820/udp` open for WireGuard
- Temporary `22/tcp` SSH access during install

Do not expose TAKlite, WGDashboard, CoT, or datapackage ports publicly. They are intended to be VPN-only.

## Install

From your admin computer:

```bash
git clone https://github.com/C137LLC/TAKlite.git
cd taklite
scp -r . root@YOUR_VPS_PUBLIC_IP:/root/taklite
```

On the VPS:

```bash
cd /root/taklite
chmod +x install.sh smoke-test.sh
./install.sh
```

The installer prompts for environment-specific values and prints the admin WireGuard profile, WGDashboard login, TAKlite bootstrap token, and certificate password at completion. The ATAK/WinTAK certificate password defaults to `atakatak` unless you change it during install.

Root-only recovery notes are saved on the VPS:

```text
/root/taklite-admin/README.txt
```

## Default VPN Services

After connecting the admin WireGuard profile:

```text
WGDashboard: http://10.66.66.1:10086
TAKlite:     http://10.66.66.1:8080/
Portal:      http://10.66.66.1:8080/connect/
TLS CoT:     10.66.66.1:8089
Plain CoT:   10.66.66.1:58087
```

## Basic Workflow

1. Run `./install.sh` on the VPS.
2. Copy the generated admin WireGuard config back to your local machine.
3. Import the admin WireGuard config and connect VPN.
4. Open WGDashboard and TAKlite over the VPN.
5. Create the first TAKlite admin account with the bootstrap token.
6. Use WGDashboard to create device VPN peers.
7. Use TAKlite Connection Users to create ATAK/WinTAK `.dp.zip` bundles, either one at a time or with Create Bulk Users.
8. Give users WireGuard QR plus TAKlite portal QR/link and password.
9. Test PLI, chat, marker drops, and datapackages.

Admin config retrieval examples:

```bash
scp root@YOUR_VPS_PUBLIC_IP:/root/taklite-admin/admin-wg0.conf .
rsync -av root@YOUR_VPS_PUBLIC_IP:/root/taklite-admin/admin-wg0.conf .
```

## Updating An Existing Server

Do not rerun `install.sh` for normal updates. Use `update.sh` so the server keeps its existing WireGuard peers, TAKlite users, certs, datapackages, and `.env`.

The `.env` file is preserved during updates. That means custom network settings and ports remain in place, including any changed TAKlite HTTP/HTTPS/CoT ports, WireGuard bind IP, and WGDashboard URL.

Copy/paste update command for the VPS:

```bash
set -Eeuo pipefail

if ! command -v git >/dev/null 2>&1; then
  apt-get update
  apt-get install -y git
fi

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

STAGE=/root/TAKlite-update
rm -rf "$STAGE"
git clone --depth 1 https://github.com/C137LLC/TAKlite.git "$STAGE"

bash "$STAGE/update.sh" --from-dir "$STAGE" --app-dir "$APP_DIR"
```

That command stages the latest GitHub version, updates the live TAKlite app, and preserves the live `.env`, certs, database, datapackages, generated packages, WireGuard config, and custom port settings.

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

For a specific version tag:

```bash
cd /root
rm -rf /root/TAKlite-update
git clone --branch vX.Y.Z --depth 1 \
  https://github.com/C137LLC/TAKlite.git \
  /root/TAKlite-update

bash /root/TAKlite-update/update.sh --from-dir /root/TAKlite-update
```

Never clone directly over the live TAKlite app directory. Clone into a staging directory such as `/root/TAKlite-update`, then run the staged `update.sh --from-dir`.

## Uninstall Or Reinstall

Use these only when you intentionally want to wipe the TAKlite deployment. Normal upgrades should use `update.sh`.

Warning: uninstall and reinstall stop WireGuard. If you are SSH'd into the VPS through the WireGuard tunnel, your shell can disconnect before the command finishes. Make sure public SSH/22 is open from a network you can reach, or have VPS console access ready before running these.

Uninstall wipes TAKlite, WGDashboard, WireGuard config, admin recovery files, certs, users, datapackages, generated packages, and TAKlite backups:

```bash
cd /root
rm -rf /root/TAKlite-update
git clone --depth 1 https://github.com/C137LLC/TAKlite.git /root/TAKlite-update

bash /root/TAKlite-update/uninstall.sh --yes
```

Reinstall wipes the current deployment, recreates the app directory, and runs a fresh install with new WireGuard and TAKlite identity:

```bash
cd /root
rm -rf /root/TAKlite-update
git clone --depth 1 https://github.com/C137LLC/TAKlite.git /root/TAKlite-update

bash /root/TAKlite-update/reinstall.sh --yes
```

## Security Notes

Every clean install generates new:

- WireGuard server and admin peer keys
- WGDashboard password
- TAKlite bootstrap token
- Local CA and server certificate
- ATAK/WinTAK client certificates

The TAKlite certificate password defaults to `atakatak` for easier ATAK/WinTAK imports unless changed during install.

Do not reuse `/root/taklite-admin`, `/etc/wireguard`, `.env`, `taklite/certs`, or `taklite/data` between VPS deployments.

## Documentation

- [User Guide](docs/user-guide.md)
- [User Guide PDF](docs/TAKlite-User-Guide.pdf)
- [Admin Install Guide](docs/admin-install-guide.md)
- [Deployment And Update Lifecycle](docs/deployment-lifecycle.md)
- [Upgrade Guide](docs/upgrade-guide.md)
- [Test Checklist](docs/test-checklist.md)
- [Audit Notes](docs/audit-notes.md)
