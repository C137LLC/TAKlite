<img width="3364" height="1582" alt="admin-dashboard" src="https://github.com/user-attachments/assets/a4434098-c714-41e3-9581-daccbeaaa513" />

# TAKlite

TAKlite is a lightweight WireGuard-hosted TAK relay and datapackage service for small ATAK/WinTAK teams.

It installs a VPN-first stack on a fresh Ubuntu VPS: WireGuard, WGDashboard, a TAKlite admin dashboard, TLS CoT, plain TCP CoT, datapackage handling, and a simple user portal for ATAK/WinTAK `.dp.zip` connection bundles.

## What It Does

- Installs WireGuard with an initial admin peer
- Runs WGDashboard over the VPN for peer management
- Runs TAKlite over the VPN for TAK users, clients, and datapackages
- Creates ATAK/WinTAK TLS connection packages
- Provides user/password portal downloads with QR/link support
- Relays PLI, chat, markers, drawings, polygons, and CoT traffic
- Supports datapackage upload, search, download, receive, and delete
- Generates fresh keys, tokens, passwords, CA, and certs on every install

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

The installer prompts for environment-specific values and prints the admin WireGuard profile, WGDashboard login, TAKlite bootstrap token, and certificate password at completion.

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
7. Use TAKlite Connection Users to create ATAK/WinTAK `.dp.zip` bundles.
8. Give users WireGuard QR plus TAKlite portal QR/link and password.
9. Test PLI, chat, marker drops, and datapackages.

Admin config retrieval examples:

```bash
scp root@YOUR_VPS_PUBLIC_IP:/root/taklite-admin/admin-wg0.conf .
rsync -av root@YOUR_VPS_PUBLIC_IP:/root/taklite-admin/admin-wg0.conf .
```

## Security Notes

Every clean install generates new:

- WireGuard server and admin peer keys
- WGDashboard password
- TAKlite bootstrap token
- TAKlite certificate password
- Local CA and server certificate
- ATAK/WinTAK client certificates

Do not reuse `/root/taklite-admin`, `/etc/wireguard`, `.env`, `taklite/certs`, or `taklite/data` between VPS deployments.

## Documentation

- [User Guide](docs/user-guide.md)
- [User Guide PDF](docs/TAKlite-User-Guide.pdf)
- [Admin Install Guide](docs/admin-install-guide.md)
- [Test Checklist](docs/test-checklist.md)
