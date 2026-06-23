# TAKlite

TAKlite is a lightweight WireGuard-hosted TAK relay and datapackage service for small ATAK/WinTAK teams.

It is intended for fresh Ubuntu VPS deployments where the only public service is WireGuard. Admins connect through the VPN, manage WireGuard peers in WGDashboard, then manage TAK connection users and datapackages in the TAKlite dashboard.

## Features

- WireGuard VPN install with an initial admin peer
- WGDashboard bound to the VPN interface
- TAKlite admin dashboard bound to the VPN interface
- Connection User portal for ATAK/WinTAK `.dp.zip` certificate bundle downloads
- Admin QR codes for user portal links
- TLS CoT TCP on `10.66.66.1:8089`
- Plain CoT TCP test port on `10.66.66.1:58087`
- PLI/location, marker, drawing, polygon, and chat relay over CoT
- Marti-style datapackage upload/search/download/delete
- Connected client view with callsign, UID, IP, cert CN, uptime, and last seen
- Per-install generated WireGuard keys, dashboard password, TAKlite bootstrap token, local CA, server cert, client certs, and cert password

## Security Model

TAKlite is VPN-first.

Public internet:

- `51820/udp` WireGuard
- Temporary `22/tcp` SSH during installation only, then close or restrict it

VPN-only:

- `22/tcp` SSH
- `10086/tcp` WGDashboard
- `8080/tcp` TAKlite dashboard, client portal, and HTTP datapackage API
- `8443/tcp` TAKlite HTTPS datapackage API
- `58087/tcp` plain CoT TCP
- `8089/tcp` TLS CoT TCP

Do not reuse generated secrets between VPS deployments. Each fresh install creates new keys, tokens, passwords, and certificates.

Do not copy these directories/files from one VPS to another:

- `/root/taklite-admin`
- `/etc/wireguard`
- `taklite/certs`
- `taklite/data`
- `.env`

## Repository Layout

```text
.
├── README.md
├── install.sh
├── smoke-test.sh
├── docker-compose.yml
├── docker/
│   └── taklite/
│       ├── Dockerfile
│       └── taklite_service.py
└── docs/
    ├── user-guide.md
    ├── TAKlite-User-Guide.pdf
    ├── admin-install-guide.md
    └── test-checklist.md
```

## Fresh VPS Deployment

Target platform:

- Ubuntu 26.04 LTS x64
- Root SSH access for initial install
- Cloud firewall access

Recommended cloud firewall before install:

- Allow `22/tcp` temporarily from the admin IP
- Allow `51820/udp` publicly
- Do not expose TAKlite, WGDashboard, CoT, or datapackage ports publicly

### Option A: Deploy From A Git Clone

From the admin computer:

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/taklite.git
cd taklite
scp -r . root@YOUR_VPS_PUBLIC_IP:/root/taklite
```

On the VPS:

```bash
cd /root/taklite
chmod +x install.sh smoke-test.sh
./install.sh
```

### Option B: Deploy From A Release Zip

From the admin computer:

```bash
scp taklite-vps-bundle.zip root@YOUR_VPS_PUBLIC_IP:/root/
```

On the VPS:

```bash
cd /root
unzip taklite-vps-bundle.zip
cd taklite-vps-bundle
chmod +x install.sh smoke-test.sh
./install.sh
```

## Installer Output

At completion, the installer prints and saves root-only setup notes.

Save:

- Admin WireGuard config path
- Admin WireGuard QR path
- WGDashboard URL, username, and password
- TAKlite URL
- TAKlite bootstrap token
- TAKlite certificate password

Recovery files:

```text
/root/taklite-admin/README.txt
/root/taklite-admin/bootstrap-token.txt
/root/taklite-admin/admin-wg0.conf
/root/taklite-admin/admin-wg0.png
```

## First Admin Login

1. Pull or scan the admin WireGuard profile from `/root/taklite-admin`.
2. Connect WireGuard.
3. Open WGDashboard:

```text
http://10.66.66.1:10086
```

4. Open TAKlite:

```text
http://10.66.66.1:8080/
```

5. Use the TAKlite bootstrap token to create the first admin username/password.

## Creating ATAK/WinTAK Users

Preferred workflow:

1. Admin creates a WireGuard peer in WGDashboard.
2. User scans/imports the WireGuard config and connects VPN.
3. Admin creates a Connection User in TAKlite.
4. Admin gives the user the portal QR/link and password.
5. User opens:

```text
http://10.66.66.1:8080/connect/
```

6. User logs in, downloads their `.dp.zip`, and imports it into ATAK/WinTAK.

The generated package configures:

```text
Host: 10.66.66.1
Port: 8089
Protocol: SSL/TLS
```

The certificate password is generated fresh during install and saved in `/root/taklite-admin/README.txt`.

## Datapackages

TAKlite implements the Marti-style datapackage paths used by ATAK/WinTAK:

```text
POST /Marti/sync/missionupload
GET  /Marti/sync/search
GET  /Marti/sync/content?hash=...
PUT  /Marti/api/sync/metadata/{hash}/tool
```

Uploaded datapackages appear in the TAKlite dashboard with Download and Delete controls.

## Basic Verification

After VPN connection:

```bash
curl -fsS http://10.66.66.1:8080/api/health
```

On the VPS:

```bash
cd /root/taklite-vps-bundle
docker compose ps
docker logs -f taklite
wg show
```

For a git-clone deployment into `/root/taklite`, use:

```bash
cd /root/taklite
docker compose ps
docker logs -f taklite
wg show
```

## Documentation

- [User Guide](docs/user-guide.md)
- [User Guide PDF](docs/TAKlite-User-Guide.pdf)
- [Admin Install Guide](docs/admin-install-guide.md)
- [Test Checklist](docs/test-checklist.md)

## Release Notes

This repository is structured for you to publish under your own GitHub account. No git remote is configured by this bundle.
