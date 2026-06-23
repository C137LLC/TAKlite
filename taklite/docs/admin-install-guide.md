# TAKlite Admin Install Guide

This guide walks an admin through installing TAKlite on a brand new Ubuntu 26.04 LTS x64 VPS, joining the WireGuard VPN, opening the dashboards, and creating ATAK/WinTAK connection packages.

## What The Admin Needs

- Fresh Ubuntu 26.04 LTS x64 VPS
- Root SSH access during initial setup
- Public cloud firewall access
- WireGuard app on the admin computer or phone
- TAKlite bundle folder or zip

Recommended cloud firewall before install:

- Allow `22/tcp` temporarily from the admin IP
- Allow `51820/udp` publicly
- Do not expose `8080/tcp`, `8443/tcp`, `58087/tcp`, `8089/tcp`, or `10086/tcp`

After VPN is confirmed, close or tightly restrict public SSH.

## Per-Install Security

Treat every VPS as a fresh security boundary. The installer generates new secrets and certificates every time it runs on a clean host.

Generated per install:

- WireGuard server key
- Initial admin WireGuard peer key and preshared key
- WGDashboard password
- TAKlite bootstrap token
- TAKlite certificate password
- TAKlite local certificate authority
- TAKlite server certificate
- ATAK/WinTAK client certificates created in the dashboard

Do not reuse `/root/taklite-admin`, `/etc/wireguard`, `taklite/certs`, `taklite/data`, or an old `.env` between VPS deployments.

## Upload TAKlite

Option A, deploy from a GitHub clone:

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/taklite.git
cd taklite
scp -r . root@YOUR_VPS_PUBLIC_IP:/root/taklite
```

Option B, deploy from a release zip:

```bash
scp taklite-vps-bundle.zip root@YOUR_VPS_PUBLIC_IP:/root/
```

Then on the VPS:

```bash
cd /root
unzip taklite-vps-bundle.zip
```

## Run Installer

If you deployed from a GitHub clone:

```bash
cd /root/taklite
chmod +x install.sh smoke-test.sh
./install.sh
```

If you deployed from a release zip:

```bash
cd /root/taklite-vps-bundle
chmod +x install.sh smoke-test.sh
./install.sh
```

Use defaults unless your VPS environment requires different values.

Important defaults:

```text
WireGuard interface: wg0
WireGuard server IP: 10.66.66.1
WireGuard UDP port: 51820
Initial admin VPN IP: 10.66.66.2
WGDashboard: http://10.66.66.1:10086
TAKlite UI: http://10.66.66.1:8080/
Plain CoT TCP: 10.66.66.1:58087
TLS CoT TCP: 10.66.66.1:8089
Datapackage HTTP: http://10.66.66.1:8080/Marti
Datapackage HTTPS: https://10.66.66.1:8443/Marti
Certificate password: generated per install and printed in `/root/taklite-admin/README.txt`
```

## Save The Bootstrap Output

At the end of installation, the terminal prints the critical setup information.

Save:

- Admin WireGuard `.conf` path
- Admin WireGuard QR path
- WGDashboard URL, username, and password
- TAKlite URL
- TAKlite bootstrap token
- Certificate password

The bootstrap token is used to create the first TAKlite admin username/password.

A root-only copy is saved on the VPS:

```text
/root/taklite-admin/README.txt
/root/taklite-admin/bootstrap-token.txt
/root/taklite-admin/admin-wg0.conf
/root/taklite-admin/admin-wg0.png
```

If the terminal is closed, SSH back into the VPS and read:

```bash
cat /root/taklite-admin/README.txt
```

## Pull The Admin WireGuard Profile

From the admin computer:

```bash
scp root@YOUR_VPS_PUBLIC_IP:/root/taklite-admin/admin-wg0.conf .
```

Import `admin-wg0.conf` into WireGuard and connect.

Alternatively, display the QR code on the VPS:

```bash
qrencode -t ansiutf8 < /root/taklite-admin/admin-wg0.conf
```

Then scan it from a phone with the WireGuard app.

## Open Admin Dashboards

After WireGuard connects:

```text
WGDashboard: http://10.66.66.1:10086
TAKlite UI:  http://10.66.66.1:8080/
```

Use WGDashboard for WireGuard peers and tunnel management.

Use TAKlite UI for:

- Creating the first TAKlite admin account
- Viewing connected TAK clients
- Viewing, downloading, and deleting datapackages
- Creating ATAK/WinTAK connection `.dp.zip` packages
- Revoking or deleting TAKlite connection packages

## Create First TAKlite Admin User

Open:

```text
http://10.66.66.1:8080/
```

Enter the bootstrap token printed by the installer, then create a username and password.

After this, log in with the username/password.

Keep the root-only install notes in case recovery is needed:

```text
/root/taklite-admin/README.txt
```

## Create ATAK/WinTAK Connection User

Preferred user flow:

1. Admin creates or shows the user's WireGuard peer QR in WGDashboard.
2. User scans the WireGuard QR and connects VPN.
3. Admin creates a TAKlite Connection User.
4. Admin shows or copies that user's portal QR/link.
5. User opens the portal over VPN, signs in, and downloads their `.dp.zip`.
6. User imports the `.dp.zip` in ATAK/WinTAK.

In the TAKlite UI:

1. Open Connection Users.
2. Enter a username, such as `alpha-phone`.
3. Enter a temporary user download password.
4. Optionally enter a note.
5. Leave Allow re-download off for one-time downloads, or turn it on for repeated testing.
6. Click Create User.
7. Use QR or Copy URL for that user.

The portal URL is VPN-only:

```text
http://10.66.66.1:8080/connect/
```

Per-user QR codes point to the portal with the username prefilled. The password is still required.

Admin actions:

- Reset Password: changes the user's portal password and logs out active portal sessions
- Allow/Disable Re-download: controls whether the same user can download the same package more than once
- Reissue: revokes the old certificate package and creates a new `.dp.zip` for the same portal user
- Revoke: disables the portal user and revokes the certificate package

## Create Standalone ATAK/WinTAK Connection Package

In the TAKlite UI:

1. Open Connection Packages.
2. Enter a package name, such as `alpha-phone`.
3. Optionally enter a note.
4. Click Create DP.zip.
5. Click Download DP.zip.

TAKlite also shows a VPN-only download URL for each connection package, for example:

```text
http://10.66.66.1:8080/connect/RANDOMTOKEN.dp.zip
```

Give that URL only to the intended VPN-connected user. Revoking the connection package disables the URL.

This direct URL path is useful for quick testing, but Connection Users are preferred for normal distribution because they require a username/password and track first/last download time.

The generated package contains:

- `server.pref`
- TAKlite truststore `.p12`
- client certificate `.p12`

The certificate password is generated fresh for every VPS install. It is printed at install completion and saved in:

```text
/root/taklite-admin/README.txt
```

The connection package configures ATAK/WinTAK for:

```text
Host: 10.66.66.1
Port: 8089
Protocol: SSL/TLS
```

Plain TCP remains available for manual testing:

```text
Host: 10.66.66.1
Port: 58087
Protocol: TCP
SSL/TLS: off
```

## Import On ATAK

On the Android device:

1. Connect WireGuard VPN.
2. Copy or download the generated `.dp.zip` to the phone.
3. Open ATAK.
4. Import the datapackage.
5. If prompted for certificate password, use the generated password from `/root/taklite-admin/README.txt`.
6. Confirm the TAKlite server connection turns green.

Then test:

- PLI/team location dots
- Marker drops
- Drawing/polygon relay
- Datapackage receive
- Datapackage send

## Import On WinTAK

On the Windows computer:

1. Connect WireGuard VPN.
2. Import the generated `.dp.zip` into WinTAK.
3. If prompted for certificate password, use the generated password from `/root/taklite-admin/README.txt`.
4. Confirm the TAKlite server connection turns green.

WinTAK can also be manually pointed at:

```text
10.66.66.1:58087 TCP
```

for plain TCP testing.

## Datapackage Admin

In the TAKlite UI, the Datapackages table shows uploaded packages.

Available actions:

- Download package to the admin computer
- Delete package database record and stored file

The backend implements these Marti-style endpoints:

```text
POST /Marti/sync/missionupload
GET  /Marti/sync/search?keywords=missionpackage
GET  /Marti/sync/content?hash=...
PUT  /Marti/api/sync/metadata/{hash}/tool
```

## Connected Clients

The TAKlite UI shows connected clients with:

- Callsign/name
- UID
- IP address
- Transport mode
- Connection uptime
- Connected time
- Last seen time

Clients appear after they connect and send CoT traffic.

## Smoke Test

After connecting to the VPN, run from the VPS:

```bash
cd /root/taklite-vps-bundle
./smoke-test.sh 10.66.66.1 TAKLITE_BOOTSTRAP_TOKEN_OR_ADMIN_TOKEN
```

Also check:

```bash
docker compose ps
curl -fsS http://10.66.66.1:8080/api/health
wg show
```

## Firewall After Setup

At the cloud firewall/security-group:

- Keep public `51820/udp` open
- Close public SSH or restrict it to trusted admin IPs
- Do not expose TAKlite or WGDashboard publicly

Expected VPN-only services:

```text
22/tcp      SSH over VPN
10086/tcp   WGDashboard
8080/tcp    TAKlite UI and HTTP datapackage API
8443/tcp    TAKlite HTTPS datapackage API
58087/tcp   plain CoT TCP
8089/tcp   TLS CoT TCP
```

## Routine Admin Workflow

1. Connect WireGuard as admin.
2. Open WGDashboard for VPN peer work.
3. Open TAKlite UI for TAK users and packages.
4. Create a WireGuard peer for a device.
5. Create a TAKlite Connection User for that device.
6. Give the user the WireGuard QR.
7. After VPN connects, give the user the TAKlite portal QR/link and password.
8. User downloads and imports their `.dp.zip`.
9. Confirm the device appears in Connected Clients.
10. Test PLI and datapackage send/receive.
