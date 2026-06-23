# TAKlite Audit Notes

This is the working audit/backlog for hardening TAKlite without turning it into full TAK Server.

## Current Scope

TAKlite is a VPN-first relay and datapackage service. The intended public VPS exposure is WireGuard UDP only. WGDashboard, TAKlite HTTP/HTTPS, CoT TCP, and CoT TLS should remain reachable only over WireGuard.

## Fixed In This Pass

- Bootstrap token is bootstrap-only. After the first admin account exists, `X-Admin-Token` no longer authorizes admin APIs.
- Admin and portal login endpoints have basic in-process throttling.
- Datapackage uploads now have explicit body-size limits and ZIP validation.
- JSON request bodies now have a small explicit size limit.
- Download filenames are sanitized before `Content-Disposition`.
- Generated per-user client cert revocation is enforced for CoT TLS connections.
- CoT buffering has a max incomplete-event size to reduce memory abuse.
- CoT event database retention is capped by row count.
- Admin and portal HTTP responses include baseline browser security headers.
- Generic legacy client certificate download endpoints require admin auth.
- New installs no longer generate a shared legacy client certificate package by default.
- Docker runtime is hardened with read-only root filesystem, dropped capabilities, `no-new-privileges`, and tmpfs `/tmp`.

## Security Backlog

- Add fail2ban filters for TAKlite admin/portal failed logins and CoT TLS unauthorized client cert attempts.
- Add optional mTLS-required mode as the recommended future default once ATAK/WinTAK import behavior is fully documented.
- Add certificate serial tracking and CRL generation if strict TLS revocation is needed beyond app-layer common-name checks.
- Add backup/restore scripts for `/root/taklite-admin`, `.env`, SQLite DB, cert CA material, and package storage.
- Add an upgrade script that preserves `.env`, data, packages, and certs while pulling newer code.
- Add CSRF protection if TAKlite is ever intentionally exposed outside the VPN.
- Consider removing public tokenized `.dp.zip` URLs and keeping only portal-authenticated downloads for higher-security deployments.

## Performance Backlog

- Stream datapackage upload validation to disk instead of reading the whole ZIP into memory.
- Add SQLite indexes for datapackage hash, event UID, event received time, and portal/cert profile joins.
- Add CoT client write queues so one slow client cannot block relay fanout.
- Add configurable package-retention policy by age and disk usage.
- Add a diagnostics endpoint for queue depth, DB size, package directory size, and event counts.

## Ease-Of-Use Backlog

- Add a first-run checklist in the admin dashboard.
- Add dashboard indicators for VPN-only binding and exposed public ports.
- Add server health panel: uptime, service version, disk usage, DB size, package storage size, memory, and container status.
- Add connection health panel: CoT TCP/TLS listener status, current clients, stale clients, last CoT event time, and datapackage upload/download counts.
- Add VPN health panel: WireGuard interface state, peer count, latest handshakes, transfer totals, and endpoint IPs.
- Add a direct WGDashboard button/link from the TAKlite admin dashboard.
- Add inline warnings when TAKlite detects that its admin/API ports are reachable from a non-VPN interface.
- Add bulk portal user creation from CSV.
- Add one-click admin diagnostics bundle.
- Add UI copy buttons for scp/rsync retrieval commands after install.
- Add an upgrade guide and release notes template.
- Add a live map view showing connected clients, latest PLI, recent CoT markers, chat, routes, drawings, and polygons.
- Add CoT event browser/search for troubleshooting received XML without requiring shell access.

## Validation Checklist

- Fresh Ubuntu 26.04 VPS install.
- Admin WireGuard profile connects and reaches WGDashboard.
- First admin account creation works with bootstrap token.
- Bootstrap token no longer authorizes admin APIs after admin account exists.
- Admin can create portal users and download `.dp.zip` bundles.
- ATAK imports `.dp.zip` and connects to TLS CoT.
- WinTAK imports `.dp.zip` and connects to TLS CoT.
- PLI, chat, marker drops, drawings, and polygons relay between clients.
- ATAK and WinTAK can upload and download datapackages.
- Revoked per-user cert profile can no longer connect over CoT TLS.
- Plain TCP CoT still works when intentionally configured.
