# Dependency Update Checklist

Use this before publishing a TAKlite release or after a base OS/Docker dependency change.

## Release Inputs

- Confirm the target release tag and changelog.
- Confirm the release zip was built from the same commit as the tag.
- Confirm the GitHub release asset exposes a SHA-256 digest for the TAKlite release zip so GUI updates can verify it before install.
- Confirm no test VPS data, generated certs, `.env`, WireGuard configs, or admin credentials are included.

## Docker And OS Packages

- Review `docker/taklite/Dockerfile` base images.
- Review `install.sh` package lists for Ubuntu/Debian compatibility.
- Test install on at least one supported Ubuntu VPS and one Debian-based host when practical.
- Run `docker compose build --pull` on a test host when checking for base image updates.

## Frontend Packages

Run from the repo root:

```bash
cd frontend
npm install
npm audit
npm run build
```

If `npm audit` reports issues, update the smallest dependency set that resolves the finding and retest the admin UI.

## Python Service

TAKlite intentionally uses Python standard-library code for the service. After service changes, run:

```bash
python3 -m unittest discover -s tests
python3 -m py_compile docker/taklite/taklite_service.py
```

## Security Regression Checks

Confirm:

- Admin login throttling still works.
- Admin 2FA setup, login, and disable flows work when enabled.
- TAKlite auth failures emit `TAKlite auth failure scope=... remote=...`.
- Fail2ban `sshd` and `taklite-auth` jails load on a VPS install.
- TLS client cert requirement remains enabled by default.
- Legacy client cert CN remains disabled by default.
- Legacy direct P12 downloads remain disabled by default.
- Datapackage uploads reject unsafe ZIP paths and excessive compression.
- Revoking or reissuing a connection package disconnects matching active clients.
- Firewall GUI cannot close WireGuard and requires SSH-over-WireGuard confirmation before closing SSH.

## VPS Smoke Test

On a test VPS:

```bash
cd /root/taklite
docker compose ps
curl -sS http://10.66.66.1:8080/api/health
fail2ban-client status
fail2ban-client status taklite-auth
```

Then verify from ATAK/WinTAK:

- TLS connection stays green.
- PLI and chat work.
- Datapackage upload works.
- Datapackage search/query works.
- Admin panel can send a datapackage to a selected client.
