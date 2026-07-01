# TAKlite Start-To-Finish Setup Guide

Version: TAKlite v0.2.20

Audience: new TAKlite administrators standing up a fresh VPS.

Starting point: you already have a working Ubuntu VPS and a root shell over SSH using the VPS public IP.

Example:

```bash
ssh root@YOUR_VPS_PUBLIC_IP
```

Replace `YOUR_VPS_PUBLIC_IP` everywhere in this guide with the real VPS public IP address.

## Command Conventions Used In This Guide

Commands are labeled by where they should be run:

- `On your local machine`: run from Windows PowerShell, macOS Terminal, or Linux Terminal.
- `On the VPS`: run inside the SSH shell after connecting to the server.

In copy commands, the last argument is usually the destination path.

For example:

```bash
scp root@YOUR_VPS_PUBLIC_IP:/root/taklite-admin/admin-wg0.conf /path/to/local/folder/admin-wg0.conf
```

This means:

```text
source:      root@YOUR_VPS_PUBLIC_IP:/root/taklite-admin/admin-wg0.conf
destination: /path/to/local/folder/admin-wg0.conf
```

The source is on the VPS. The destination is on your local machine.

Windows local path example:

```text
C:\Users\YOURNAME\Downloads\admin-wg0.conf
```

macOS local path example:

```text
/Users/YOURNAME/Downloads/admin-wg0.conf
```

Linux local path example:

```text
/home/YOURNAME/Downloads/admin-wg0.conf
```

Tip: `.` means "the current folder." This guide uses explicit paths because they are clearer for new admins.

## 0. Create An SSH Key On Your Local Machine

Most VPS providers let you paste an SSH public key during VPS creation. This is better than password-only SSH.

If you already have an SSH key you want to use, you can skip key creation and use your existing public key.

### Windows 10/11 PowerShell

Open PowerShell.

Check whether OpenSSH is available:

```powershell
ssh -V
```

Create a new key:

```powershell
ssh-keygen -t ed25519 -a 100 -f "$env:USERPROFILE\.ssh\taklite_ed25519" -C "taklite-admin"
```

When prompted, enter a passphrase or press Enter for no passphrase. A passphrase is more secure but must be typed when using the key.

Show the public key:

```powershell
type "$env:USERPROFILE\.ssh\taklite_ed25519.pub"
```

Copy the full line that starts with:

```text
ssh-ed25519
```

Paste that public key into the VPS provider when creating the server.

SSH to the VPS:

```powershell
ssh -i "$env:USERPROFILE\.ssh\taklite_ed25519" root@YOUR_VPS_PUBLIC_IP
```

Copy files from the VPS to Windows:

```powershell
scp -i "$env:USERPROFILE\.ssh\taklite_ed25519" root@YOUR_VPS_PUBLIC_IP:/root/taklite-admin/admin-wg0.conf "$env:USERPROFILE\Downloads\admin-wg0.conf"
```

Tip: the final part, `"$env:USERPROFILE\Downloads\admin-wg0.conf"`, is where the file will land on your Windows computer. Change it if you want the file somewhere else.

If Windows asks whether to trust the host fingerprint, type:

```text
yes
```

### macOS Or Linux Terminal

Create a new key:

```bash
ssh-keygen -t ed25519 -a 100 -f ~/.ssh/taklite_ed25519 -C "taklite-admin"
```

Show the public key:

```bash
cat ~/.ssh/taklite_ed25519.pub
```

Copy the full `ssh-ed25519 ...` line and paste it into the VPS provider when creating the server.

SSH to the VPS:

```bash
ssh -i ~/.ssh/taklite_ed25519 root@YOUR_VPS_PUBLIC_IP
```

Copy files from the VPS:

```bash
scp -i ~/.ssh/taklite_ed25519 root@YOUR_VPS_PUBLIC_IP:/root/taklite-admin/admin-wg0.conf ~/Downloads/admin-wg0.conf
```

Tip: the final part, `~/Downloads/admin-wg0.conf`, is where the file will land on your Mac or Linux computer. Change it if you want a different destination.

### If The VPS Was Created Before Adding The Key

If the VPS provider gave you password SSH access first, log in with the password and add your public key manually.

On the VPS:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
nano ~/.ssh/authorized_keys
```

Paste your local public key into the file, save it, then run:

```bash
chmod 600 ~/.ssh/authorized_keys
```

From your local machine, test key login:

```bash
ssh -i PATH_TO_PRIVATE_KEY root@YOUR_VPS_PUBLIC_IP
```

On Windows, `PATH_TO_PRIVATE_KEY` may look like:

```text
C:\Users\YOURNAME\.ssh\taklite_ed25519
```

On macOS/Linux, it may look like:

```text
~/.ssh/taklite_ed25519
```

### When A VPS Is Rebuilt And SSH Warns About Host Keys

If you rebuild or replace a VPS at the same IP, SSH may warn:

```text
WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED
```

Only do this if you intentionally rebuilt the VPS or trust that the server changed.

Windows PowerShell:

```powershell
ssh-keygen -R YOUR_VPS_PUBLIC_IP
```

macOS/Linux:

```bash
ssh-keygen -R YOUR_VPS_PUBLIC_IP
```

Then connect again and accept the new fingerprint.

## 1. What TAKlite Installs

TAKlite installs a VPN-first TAK relay stack:

- WireGuard VPN on UDP `51820`
- WGDashboard for WireGuard peer management
- TAKlite admin dashboard on `http://10.66.66.1:8080/`
- User download portal on `http://10.66.66.1:8080/connect/`
- TLS CoT server for ATAK/WinTAK on `10.66.66.1:8089`
- Plain TCP CoT server on `10.66.66.1:58087`
- HTTPS/Marti datapackage service on `10.66.66.1:8443`
- Datapackage upload, download, receive, and delete
- ATAK/WinTAK `.dp.zip` connection package generation
- Admin GUI for users, packages, access control, firewall, settings, and updates

Security model:

- Public internet should normally expose only WireGuard UDP `51820`.
- SSH `22/tcp` is needed during install and can later be restricted to VPN only.
- WGDashboard, TAKlite Admin, TAK ports, and datapackage services should stay VPN only.

## 2. VPS Firewall Before Install

In your VPS provider firewall/security group, allow:

```text
22/tcp from your admin IP temporarily
51820/udp from anywhere
```

Do not publicly expose these TAKlite service ports:

```text
8080/tcp
8443/tcp
58087/tcp
8089/tcp
10086/tcp
```

Those are intended to be reachable over WireGuard after the VPN is connected.

## 3. Install TAKlite From GitHub On The VPS

Run these commands in the root SSH shell on the VPS:

```bash
cd /root

apt-get update
apt-get install -y git

rm -rf /root/taklite
git clone https://github.com/C137LLC/TAKlite.git /root/taklite

cd /root/taklite
chmod +x install.sh update.sh uninstall.sh reinstall.sh smoke-test.sh
./install.sh
```

Tips:

- Run this block on the VPS, not on your local machine.
- `cd /root` moves into the root user's home folder on the VPS.
- `rm -rf /root/taklite` removes any old staged TAKlite folder before cloning fresh. Do not run this if you have a live TAKlite install you are trying to preserve.
- `git clone ... /root/taklite` downloads TAKlite into `/root/taklite`.
- `chmod +x ...` makes the scripts executable.
- `./install.sh` starts the first-time installer.
- For normal updates later, use `update.sh`, not `install.sh`.

The installer will ask several questions. For most deployments, press Enter to accept the defaults.

Important prompts:

```text
Public IP or DNS name clients use for WireGuard
Public network interface
WireGuard interface name
WireGuard server IPv4
WireGuard UDP port
Initial admin peer name
Initial admin WireGuard IPv4
AllowedIPs for admin client
DNS resolver for generated peers
WGDashboard bind IP
WGDashboard port
WGDashboard username
TAKlite bind IP
TAKlite API host used in package URLs
TAKlite admin token
ATAK/WinTAK certificate password
Enable secure mode
TAKlite plain CoT TCP host port
TAKlite TLS CoT TCP host port
TAKlite HTTP/admin host port
TAKlite HTTPS/Marti host port
```

Recommended defaults:

```text
WireGuard interface: wg0
WireGuard server IP: 10.66.66.1
WireGuard UDP port: 51820
Initial admin VPN IP: 10.66.66.2
WGDashboard bind: 10.66.66.1
WGDashboard port: 10086
TAKlite bind: 10.66.66.1
TAKlite HTTP/admin: 8080
TAKlite HTTPS/Marti: 8443
Plain CoT TCP: 58087
TLS CoT TCP: 8089
Certificate password: atakatak
Secure mode: yes
```

Secure mode should normally be `yes`. It requires TLS client identity and enables role/group access enforcement.

## 4. Save The Install Output

At the end of install, TAKlite prints the important one-time setup values:

- Admin WireGuard config path
- Admin WireGuard QR path
- WGDashboard URL
- WGDashboard username/password
- TAKlite admin URL
- TAKlite bootstrap token
- ATAK/WinTAK certificate password

The same recovery information is stored on the VPS here:

```bash
cat /root/taklite-admin/README.txt
```

Important files:

```text
/root/taklite-admin/README.txt
/root/taklite-admin/bootstrap-token.txt
/root/taklite-admin/admin-wg0.conf
/root/taklite-admin/admin-wg0.png
```

Keep `/root/taklite-admin/README.txt` private. It contains admin recovery information.

## 5. Pull The Admin WireGuard Config To Your Computer

Run this from your admin computer, not inside the VPS.

Windows PowerShell example:

```powershell
scp root@YOUR_VPS_PUBLIC_IP:/root/taklite-admin/admin-wg0.conf "$env:USERPROFILE\Downloads\admin-wg0.conf"
```

macOS/Linux Terminal example:

```bash
scp root@YOUR_VPS_PUBLIC_IP:/root/taklite-admin/admin-wg0.conf ~/Downloads/admin-wg0.conf
```

Alternative with `rsync`:

Windows PowerShell with an explicit local destination:

```powershell
rsync -av root@YOUR_VPS_PUBLIC_IP:/root/taklite-admin/admin-wg0.conf "$env:USERPROFILE\Downloads\admin-wg0.conf"
```

Note: plain Windows PowerShell may not include `rsync`. If `rsync` is not installed, use the `scp` command above. `rsync` is commonly available in WSL, Git Bash, macOS, and Linux.

macOS/Linux Terminal with an explicit local destination:

```bash
rsync -av root@YOUR_VPS_PUBLIC_IP:/root/taklite-admin/admin-wg0.conf ~/Downloads/admin-wg0.conf
```

Tips:

- The command runs on your local computer because it pulls a file down from the VPS.
- `root@YOUR_VPS_PUBLIC_IP:/root/taklite-admin/admin-wg0.conf` is the remote VPS file.
- `~/Downloads/admin-wg0.conf` or `"$env:USERPROFILE\Downloads\admin-wg0.conf"` is the local destination.
- If you used a custom SSH key, add `-i PATH_TO_PRIVATE_KEY` to `scp`.
- If your public SSH is already closed, use `root@10.66.66.1` while connected to WireGuard.

Import `admin-wg0.conf` into the WireGuard app on your computer and connect it.

If you are setting up from a phone, you can show the QR code from the VPS:

```bash
qrencode -t ansiutf8 < /root/taklite-admin/admin-wg0.conf
```

Scan it with the WireGuard mobile app.

## 6. Confirm The Admin VPN Works

After connecting WireGuard, test from your admin computer:

```bash
ping 10.66.66.1
```

Then test SSH over the VPN:

```bash
ssh root@10.66.66.1
```

If this works, you can administer the VPS through the VPN.

## 7. Open WGDashboard And TAKlite

Open these URLs from the admin computer while WireGuard is connected:

```text
WGDashboard: http://10.66.66.1:10086
TAKlite:     http://10.66.66.1:8080/
Portal:      http://10.66.66.1:8080/connect/
```

WGDashboard manages WireGuard peers.

TAKlite manages TAK users, connection packages, datapackages, access policy, settings, and firewall exposure.

## 8. Create The First TAKlite Admin Account

Open:

```text
http://10.66.66.1:8080/
```

TAKlite will ask for the bootstrap token. Get it from the install output or from the VPS:

```bash
cat /root/taklite-admin/bootstrap-token.txt
```

Enter the token, then create the first TAKlite admin username and password.

After this, log in with that username and password. The bootstrap token is only for initial admin setup.

## 9. Create VPN Peers In WGDashboard

Open:

```text
http://10.66.66.1:10086
```

Log in with the WGDashboard username and password from:

```bash
cat /root/taklite-admin/README.txt
```

Use WGDashboard to create one WireGuard peer per device.

Typical workflow:

1. Create a new peer.
2. Give it a recognizable name, such as `alpha-phone-01`.
3. Download the `.conf` or show the QR code.
4. User imports/scans it in WireGuard.
5. User turns WireGuard on.
6. Confirm the peer handshake appears in WGDashboard.

WireGuard only gets the device onto the VPN. TAKlite connection packages are still required for ATAK/WinTAK.

## 10. Create A Single TAKlite Connection User

In TAKlite, open:

```text
Users
```

Use this for normal user onboarding.

Fields:

- `Username`: login name for the user's TAKlite portal, for example `alpha-phone-01`
- `Password`: temporary portal password for downloading the `.dp.zip`
- `Description`: optional admin note
- `Role`: optional access role
- `Groups`: optional access groups
- `Allow re-download`: allow the same portal user to download the package more than once

Click:

```text
Create User
```

TAKlite creates:

- a portal user/password
- a per-user TLS client certificate
- a `.dp.zip` ATAK/WinTAK connection bundle
- a VPN-only portal link and QR code

User actions:

- `Download DP.zip`: admin downloads the user connection package
- `Copy URL`: copy the user's portal URL
- `QR`: show a QR code for the user's portal page
- `Edit`: edit display name/description
- `Reset password`: change the portal password
- `Allow/Disable re-download`: control repeated package downloads
- `Reissue`: revoke old cert/package and create a new one
- `Revoke`: disable the user and certificate package
- `Delete`: remove the user record, optionally deleting generated package files

## 11. Create Bulk TAKlite Users

In TAKlite, open:

```text
Users
```

Click:

```text
Create Bulk Users
```

Example:

```text
Name prefix: user
Number: 20
```

TAKlite creates:

```text
user1
user2
user3
...
user20
```

Bulk users use the shared portal password:

```text
atakatak
```

After creation, copy or download the CSV. It contains usernames, passwords, portal links, and connection strings. Save it before leaving the page.

## 12. Give A User Their Connection Info

Each end user needs two things:

1. WireGuard VPN config or QR from WGDashboard
2. TAKlite portal link or QR plus their portal password

Recommended user instructions:

1. Import or scan the WireGuard config.
2. Turn WireGuard on.
3. Open the TAKlite portal QR or URL:

```text
http://10.66.66.1:8080/connect/
```

4. Log in with the assigned username/password.
5. Download the `.dp.zip`.
6. Import the `.dp.zip` into ATAK or WinTAK.
7. If asked for a certificate password, use:

```text
atakatak
```

Unless the installer was configured with a different certificate password.

## 13. ATAK Import And Test

On Android:

1. Confirm WireGuard is connected.
2. Open ATAK.
3. Import the downloaded `.dp.zip`.
4. If prompted for the `.p12` password, enter `atakatak` unless changed during install.
5. Confirm the server connection turns green.
6. Drop a point.
7. Send a chat message.
8. Send a datapackage.
9. Confirm another client receives the point, chat, and datapackage.

The generated connection package configures:

```text
Server: 10.66.66.1
TLS CoT: 8089
HTTPS/Marti datapackages: 8443
Protocol: SSL/TLS
```

## 14. WinTAK Import And Test

On Windows:

1. Confirm WireGuard is connected.
2. Open WinTAK.
3. Import the downloaded `.dp.zip`.
4. If prompted for certificate password, enter `atakatak` unless changed during install.
5. Confirm the server connection turns green.
6. Drop a point.
7. Send chat.
8. Send a datapackage.
9. Confirm another client receives it.

## 15. Datapackages In TAKlite

Open:

```text
Datapackages
```

This page shows datapackages uploaded through ATAK/WinTAK.

Actions:

- `Download`: download the datapackage to the admin computer
- `Delete`: remove it from the TAKlite server

Use this to confirm phone-to-server, WinTAK-to-server, and server-to-client datapackage transfer.

## 16. Connection Packages

Open:

```text
Connection Packages
```

This creates standalone `.dp.zip` packages without a portal username/password.

Use this for testing or special cases. For normal users, prefer `Users`, because portal users are easier to revoke, reissue, and track.

Actions:

- `Create DP.zip`: create a standalone ATAK/WinTAK connection package
- `Download`: download the package
- `Copy URL`: copy the VPN-only direct package URL
- `Revoke`: disable the package
- `Delete`: remove the package record and generated files

## 17. Access Control Basics

Open:

```text
Access
```

Access control has four pieces:

- `Roles`: broad permission sets
- `Groups`: team or visibility buckets
- `Bulk Membership`: assign roles/groups to many users at once
- `Visibility Links`: allow one group to see/send to another group

Recommended simple setup:

1. Create an admin-style role with `Can see everyone` and `Can send to everyone`.
2. Create a normal role with `Can see assigned groups` and `Can send to assigned groups`.
3. Create groups such as `Alpha`, `Bravo`, and `Admin`.
4. Put admins in the admin-style role.
5. Put team users into their team groups.
6. Use Access Preview to verify policy before field testing.

Important behavior:

- A role with `Can see everyone` can see all users, even users in groups it does not belong to.
- Normal team users only see users in their assigned group unless groups are linked.
- Users do not automatically see admin users just because admins can see them.
- A group with no links remains isolated except to roles that can see everyone.

Visibility Links:

- `No Link`: groups stay isolated.
- `Alpha -> Bravo`: Alpha can see/send to Bravo, but Bravo cannot see/send to Alpha.
- `Bravo -> Alpha`: Bravo can see/send to Alpha, but Alpha cannot see/send to Bravo.
- `Two Way`: both groups can see/send to each other.

Use:

```text
Access Preview
```

to check exactly what one user can see, send to, receive from, and who can see that user.

## 18. Firewall GUI

Open:

```text
Firewall
```

This panel manages TAKlite-known service exposure.

Firewall states:

- `Public`: reachable from the public VPS interface
- `VPN only`: reachable over WireGuard only
- `Closed`: blocked/unavailable

Recommended steady-state:

```text
WireGuard: Public
SSH: VPN only after confirming ssh root@10.66.66.1 works
WG Dashboard: VPN only
TAKlite Admin: VPN only
TAK HTTPS/Marti: VPN only
CoT TCP: VPN only
TLS CoT: VPN only
```

Click:

```text
Apply Firewall
```

The host runner applies the firewall as root and writes backups here:

```text
/root/taklite-admin/iptables-before-taklite-firewall.rules
/root/taklite-admin/iptables-after-taklite-firewall.rules
/root/taklite-admin/firewall-last.log
```

Safety notes:

- Do not close WireGuard.
- Do not switch SSH away from Public until VPN-side SSH works.
- Firewall changes do not change TAKlite port settings.
- If you change ports in Settings, review Firewall afterward.

## 19. Settings GUI

Open:

```text
Settings
```

Settings changes are written to `.env` by a host-side runner. Some changes restart TAKlite.

Editable settings:

- `Public Host`: host used in generated URLs and portal links
- `Server Host`: TAK host written into connection packages
- `WG Dashboard URL`: top-bar WGDashboard link
- `Max Upload Bytes`: datapackage upload limit
- `Admin HTTP Port`: TAKlite admin UI and user portal port
- `HTTPS/Marti Port`: secure datapackage/Marti-compatible port
- `CoT TCP Port`: plain TCP CoT port
- `TLS CoT Port`: certificate-backed TLS CoT port
- `Access Enforcement`: enforce role/group policy
- `Require Client Certs`: require valid per-user TLS client certs
- `Allow Legacy Cert CN`: allow older shared certificate identities

Click:

```text
Apply Settings
```

The settings runner backs up `.env`, writes allowed changes, and restarts TAKlite if required.

Useful files:

```text
/root/taklite/.env
/root/taklite/.env.settings.bak
/root/taklite-admin/settings-last.log
```

## 20. Verify The Server

On the VPS:

```bash
cd /root/taklite
docker compose ps
docker logs --tail 100 taklite
curl -sS http://10.66.66.1:8080/api/health
```

Tips:

- Run these from the VPS shell.
- `docker compose ps` shows whether the TAKlite container is running.
- `docker logs --tail 100 taklite` shows the latest TAKlite logs.
- `curl ... /api/health` checks whether the TAKlite API is responding over the VPN address.

Expected health output includes:

```text
"ok": true
"version": "TAKlite 0.2.20"
"auth_enabled": true
```

Check WireGuard:

```bash
wg show
systemctl status wg-quick@wg0 --no-pager
systemctl status wg-dashboard --no-pager
```

Check runners:

```bash
systemctl status taklite-gui-update.path --no-pager
systemctl status taklite-settings.path --no-pager
systemctl status taklite-firewall.path --no-pager
```

Check fail2ban:

```bash
fail2ban-client status
fail2ban-client status sshd
```

## 21. Update TAKlite Later

For normal updates, do not rerun `install.sh`.

Use the GUI update button in Settings, or run this on the VPS:

```bash
cd /root
rm -rf /root/TAKlite-update
git clone --depth 1 https://github.com/C137LLC/TAKlite.git /root/TAKlite-update

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

bash /root/TAKlite-update/update.sh --from-dir /root/TAKlite-update --app-dir "$APP_DIR"
```

Tips:

- Run this on the VPS.
- This clones the latest TAKlite into a staging folder, not over the live install.
- `APP_DIR` finds the currently installed TAKlite folder.
- `update.sh` preserves live data, certs, packages, WireGuard, and custom ports.
- Do not run `install.sh` for an update.

Updates preserve:

- `.env`
- custom port choices
- WireGuard config and peers
- WGDashboard config
- TAKlite users
- certificates
- generated connection packages
- uploaded datapackages
- database state

## 22. Uninstall Or Reinstall

Only use these when you intentionally want to wipe the server.

Warning: uninstall and reinstall stop WireGuard. If you are SSH'd in over the VPN, your shell can disconnect. Make sure public SSH `22/tcp` is open or use the VPS web console.

Uninstall:

```bash
cd /root
rm -rf /root/TAKlite-update
git clone --depth 1 https://github.com/C137LLC/TAKlite.git /root/TAKlite-update
bash /root/TAKlite-update/uninstall.sh --yes
```

Reinstall:

```bash
cd /root
rm -rf /root/TAKlite-update
git clone --depth 1 https://github.com/C137LLC/TAKlite.git /root/TAKlite-update
bash /root/TAKlite-update/reinstall.sh --yes
```

Reinstall creates a fresh TAKlite/WireGuard identity. It does not preserve existing VPN peers or TAK connection packages.

## 23. Common Troubleshooting

Cannot open `http://10.66.66.1:8080/`:

```bash
wg show
docker compose ps
curl -sS http://10.66.66.1:8080/api/health
```

WireGuard connected but no TAKlite UI:

- Confirm the admin device is on the VPN.
- Confirm TAKlite container is running.
- Confirm Firewall tab or iptables allows `8080/tcp` on `wg0`.

ATAK/WinTAK connection is red:

- Confirm WireGuard is connected.
- Confirm the `.dp.zip` was imported.
- Confirm TLS CoT is `10.66.66.1:8089`.
- Reissue the user package if old certs were imported.
- Confirm `Require Client Certs` and `Allow Legacy Cert CN` settings match your package type.

Datapackages fail:

- Confirm secure/Marti port is `8443` unless changed.
- Confirm the user is on VPN.
- Confirm max upload size is large enough in Settings.
- Check TAKlite logs:

```bash
docker logs --tail 150 taklite
```

SSH over VPN fails:

```bash
wg show
ss -tulpen | grep ':22'
iptables -S INPUT | grep -E 'wg0|dport 22'
fail2ban-client status sshd
```

If fail2ban banned the admin VPN IP:

```bash
fail2ban-client set sshd unbanip 10.66.66.2
```

## 24. Quick New Deployment Checklist

1. VPS public firewall allows `22/tcp` from admin and `51820/udp` public.
2. SSH to public IP works.
3. Clone TAKlite into `/root/taklite`.
4. Run `./install.sh`.
5. Save `/root/taklite-admin/README.txt`.
6. Pull `admin-wg0.conf` with `scp` or scan QR.
7. Connect admin WireGuard.
8. Open WGDashboard and TAKlite.
9. Create TAKlite admin account with bootstrap token.
10. Create device VPN peers in WGDashboard.
11. Create TAKlite Connection Users or Bulk Users.
12. Give users WireGuard QR plus TAKlite portal QR/link/password.
13. Import `.dp.zip` in ATAK/WinTAK.
14. Test PLI, chat, marker, and datapackage transfer.
15. Set Firewall steady-state: WireGuard Public, admin/TAK services VPN only.
16. Close or restrict public SSH after VPN-side SSH is confirmed.
