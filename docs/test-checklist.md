# TAKlite VPS Test Checklist

## VPS Install

- VPS is a supported Linux host with systemd, TUN, Docker Compose v2, WireGuard tools, iptables, and fail2ban

- Upload `taklite-vps-bundle`
- Run `sudo ./install.sh`
- Save the printed WGDashboard password
- Save the printed TAKlite bootstrap token
- Pull `/root/taklite-admin/admin-wg0.conf`
- Import and connect WireGuard
- Confirm `/root/taklite-admin/README.txt` contains recovery install notes

## VPN Checks

- `http://10.66.66.1:10086` opens WGDashboard
- `http://10.66.66.1:8080/` opens TAKlite
- `ssh root@10.66.66.1` works over VPN

## TAKlite Checks

- TAKlite UI accepts bootstrap token for first admin setup
- TAKlite UI login works with new admin username/password
- Health endpoint reports OK
- WinTAK/ATAK connects to `10.66.66.1:58087` TCP
- ATAK/WinTAK SSL connection package can be created and downloaded
- VPN-only connection package URL downloads the correct `.dp.zip`
- Revoked connection package URL stops downloading
- ATAK/WinTAK connects to `10.66.66.1:8089` SSL/TLS after importing `.dp.zip`
- At least one client shows as connected in TAKlite
- PLI/location dots appear between two clients
- Pins/markers relay between clients
- Drawings/polygons relay between clients

## Datapackage Checks

- Send a `.dp.zip` from ATAK/WinTAK
- Package appears in TAKlite UI
- Package can be downloaded
- Package can be deleted from TAKlite UI
- Deleted package disappears from UI
- Phone can receive a datapackage from server
- Phone can send a datapackage to server

## Cloud Firewall Checks

- Public `51820/udp` is open
- Public `22/tcp` is closed or restricted after setup
- Public `8080/tcp` is closed
- Public `8443/tcp`, or the custom TAKlite HTTPS/Marti port selected during install, is closed
- Public `58087/tcp` is closed
- Public `8089/tcp` is closed
- Public `10086/tcp` is closed
