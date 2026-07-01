# TAKlite Platform Support

TAKlite has two install modes.

## Full VPS Appliance

Use this mode for a real TAKlite deployment. It installs and manages:

- WireGuard
- WGDashboard
- TAKlite Docker container
- TAKlite host runners for updates, settings, and firewall changes
- fail2ban SSH jail
- WireGuard and TAKlite firewall exposure rules

Run:

```bash
sudo ./install.sh
```

Recommended targets:

```text
Ubuntu 22.x or newer, including LTS and interim releases, amd64/x86_64 or arm64/aarch64
Debian 12 Bookworm or newer, amd64 or arm64
Debian 13 Trixie, amd64 or arm64
Raspberry Pi OS 64-bit Bookworm or newer
```

The installer is intentionally capability-based instead of locked to one distro list. Other Linux distributions can work when the required host features and commands are already installed. On apt-based systems TAKlite installs dependencies automatically. On non-apt systems, install the required host dependencies first, then rerun `install.sh`.

Required host features:

- `systemd`
- `/dev/net/tun`
- Docker Engine
- Docker Compose v2
- `wireguard-tools`
- `iptables`
- `fail2ban`
- outbound internet access during install

Unsupported for full appliance mode:

- Windows host OS
- macOS host OS
- Docker Desktop alone
- WSL without systemd/TUN/WireGuard support
- 32-bit Raspberry Pi OS or `armhf`
- Containers that cannot create WireGuard interfaces

## Portable Docker Mode

Use this mode for local testing, demos, development, or a TAKlite relay where VPN/firewall are handled elsewhere.

It runs:

- TAKlite admin UI
- HTTP/Marti API
- HTTPS/Marti API
- plain CoT TCP
- TLS CoT TCP
- datapackage storage
- connection package generation

It does not install:

- WireGuard
- WGDashboard
- fail2ban
- systemd services
- host firewall rules
- GUI update/settings/firewall runners

### macOS/Linux/WSL/Git Bash

Run from the repo folder:

```bash
./portable-start.sh
```

Defaults bind TAKlite to `127.0.0.1`, which is safest for local testing.

For ATAK phones on the same LAN, choose:

```text
Bind address: 0.0.0.0
TAKlite host/IP ATAK clients will use: your computer LAN IP
```

### Windows PowerShell

Start Docker Desktop, then run from the repo folder:

```powershell
.\portable-start.ps1
```

For LAN testing from ATAK phones:

```powershell
.\portable-start.ps1 -BindIp 0.0.0.0 -ServerHost YOUR_WINDOWS_LAN_IP
```

Windows Defender Firewall may prompt for Docker Desktop network access. Allow it for private networks if phones need to reach TAKlite from the same LAN.

### Docker Desktop GUI

1. Copy `.env.desktop.example` to `.env`.
2. For local-only testing, leave:

```env
WG_BIND_IP=127.0.0.1
TAKLITE_PUBLIC_HOST=127.0.0.1
TAKLITE_SERVER_HOST=127.0.0.1
```

3. For phone/LAN testing, set:

```env
WG_BIND_IP=0.0.0.0
TAKLITE_PUBLIC_HOST=YOUR_COMPUTER_LAN_IP
TAKLITE_SERVER_HOST=YOUR_COMPUTER_LAN_IP
```

4. Change `TAKLITE_ADMIN_TOKEN`.
5. In Docker Desktop, run the Compose project.

The container generates its local CA, HTTPS server cert, ATAK truststore, and server truststore automatically when:

```env
TAKLITE_AUTO_INIT_CERTS=true
```

## Choosing A Mode

Use full VPS appliance mode when users need managed VPN onboarding and a production-like deployment.

Use portable Docker mode when:

- testing TAKlite locally
- running behind an existing VPN
- running in Docker Desktop
- developing the admin UI or protocol behavior
- proving ATAK/WinTAK connectivity before moving to a VPS

Portable mode can still create ATAK/WinTAK `.dp.zip` connection packages. The generated connection packages point to the `TAKLITE_SERVER_HOST` and ports in `.env`.

## Notes For Raspberry Pi

Use 64-bit Raspberry Pi OS. The 32-bit `armhf` OS is intentionally blocked by the installer.

Builds are slower on small Pi hardware because the frontend and container image build locally. A Pi 4 or Pi 5 with enough storage is recommended.

If the Pi is behind a router, forward WireGuard UDP only. Keep TAKlite, WGDashboard, and CoT ports VPN-only unless you intentionally expose them.
