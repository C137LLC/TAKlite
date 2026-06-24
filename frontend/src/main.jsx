import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  Boxes,
  Copy,
  Download,
  ExternalLink,
  FileArchive,
  Gauge,
  KeyRound,
  LayoutDashboard,
  LogOut,
  PackagePlus,
  Pencil,
  QrCode,
  RefreshCw,
  RotateCw,
  Trash2,
  UserPlus,
  Users,
  Wifi,
  XCircle,
} from 'lucide-react';
import './styles.css';

const SESSION_KEY = 'takliteSession';
const navItems = [
  ['overview', LayoutDashboard, 'Overview'],
  ['clients', Wifi, 'Clients'],
  ['datapackages', FileArchive, 'Datapackages'],
  ['users', Users, 'Users'],
  ['packages', Boxes, 'Connection Packages'],
];

function authHeaders(session, extra = {}) {
  return {
    'Content-Type': 'application/json',
    ...(session ? { 'X-Session-Token': session } : {}),
    ...extra,
  };
}

async function api(path, session, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...authHeaders(session),
      ...(options.headers || {}),
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.error || response.statusText);
  }
  return body;
}

function fmtTime(value) {
  if (!value) return 'never';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

function fmtBytes(value) {
  const n = Number(value || 0);
  if (n > 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  if (n > 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${n} B`;
}

function fmtUptime(value) {
  if (!value) return 'unknown';
  const start = new Date(value).getTime();
  if (!start) return 'unknown';
  const seconds = Math.max(0, Math.floor((Date.now() - start) / 1000));
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${mins}m`;
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function App() {
  const [session, setSession] = useState(() => localStorage.getItem(SESSION_KEY) || '');
  const [bootstrap, setBootstrap] = useState(null);
  const [active, setActive] = useState('overview');
  const [status, setStatus] = useState('Loading...');
  const [loading, setLoading] = useState(false);
  const [uiConfig, setUiConfig] = useState({ wgDashboardUrl: '' });
  const [data, setData] = useState({
    health: null,
    clients: [],
    packages: [],
    profiles: [],
    portalUsers: [],
    portalUrl: '',
    certPassword: '',
  });

  const wgUrl = uiConfig.wgDashboardUrl || '';

  const loadBootstrap = useCallback(async () => {
    try {
      const config = await fetch('/api/ui-config').then((response) => response.json()).catch(() => ({ wgDashboardUrl: '' }));
      setUiConfig(config);
      const response = await fetch('/api/bootstrap/status');
      setBootstrap(await response.json());
    } catch (error) {
      setStatus(error.message);
    }
  }, []);

  const load = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    try {
      const health = await fetch('/api/health').then((r) => r.json());
      const [packages, clients, profiles, portal] = await Promise.all([
        api('/api/datapackages', session),
        api('/api/clients', session),
        api('/api/cert-profiles', session),
        api('/api/portal-users', session),
      ]);
      setData({
        health,
        packages: packages.items || [],
        clients: clients.items || [],
        profiles: profiles.items || [],
        portalUsers: portal.items || [],
        portalUrl: portal.portal_url || `${location.origin}/connect/`,
        certPassword: profiles.cert_password || '',
      });
      setStatus('Dashboard refreshed.');
    } catch (error) {
      if (String(error.message).includes('unauthorized')) {
        localStorage.removeItem(SESSION_KEY);
        setSession('');
        await loadBootstrap();
      }
      setStatus(error.message);
    } finally {
      setLoading(false);
    }
  }, [loadBootstrap, session]);

  useEffect(() => {
    loadBootstrap();
  }, [loadBootstrap]);

  useEffect(() => {
    load();
    const timer = setInterval(load, 15000);
    return () => clearInterval(timer);
  }, [load]);

  const logout = async () => {
    try {
      await api('/api/logout', session, { method: 'POST', body: '{}' });
    } catch {}
    localStorage.removeItem(SESSION_KEY);
    setSession('');
    setData({ health: null, clients: [], packages: [], profiles: [], portalUsers: [], portalUrl: '', certPassword: '' });
    await loadBootstrap();
  };

  if (!session) {
    return <AuthScreen bootstrap={bootstrap} setSession={setSession} setStatus={setStatus} status={status} />;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">TL</div>
          <div>
            <div className="brand-title">TAKlite</div>
            <div className="brand-subtitle">TAK Relay</div>
          </div>
        </div>
        <nav>
          {navItems.map(([key, Icon, label]) => (
            <button key={key} className={active === key ? 'nav-item active' : 'nav-item'} onClick={() => setActive(key)}>
              <Icon size={17} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="mini-label">Server</div>
          <div className="mini-value">{data.health?.ok ? 'Online' : 'Checking'}</div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>{navItems.find(([key]) => key === active)?.[2] || 'Overview'}</h1>
            <p>{status}</p>
          </div>
          <div className="top-actions">
            {wgUrl ? (
              <a className="btn ghost" href={wgUrl} target="_blank" rel="noreferrer">
                <ExternalLink size={16} />
                WG Dashboard
              </a>
            ) : null}
            <button className="btn ghost" onClick={load} disabled={loading}>
              <RefreshCw size={16} className={loading ? 'spin' : ''} />
              Refresh
            </button>
            <button className="btn danger-soft" onClick={logout}>
              <LogOut size={16} />
              Log Out
            </button>
          </div>
        </header>

        <OverviewStrip data={data} />

        {active === 'overview' && <Overview data={data} session={session} load={load} setStatus={setStatus} />}
        {active === 'clients' && <ClientsPanel clients={data.clients} />}
        {active === 'datapackages' && <DatapackagesPanel packages={data.packages} session={session} load={load} setStatus={setStatus} />}
        {active === 'users' && <UsersPanel users={data.portalUsers} portalUrl={data.portalUrl} session={session} load={load} setStatus={setStatus} />}
        {active === 'packages' && <ProfilesPanel profiles={data.profiles} certPassword={data.certPassword} session={session} load={load} setStatus={setStatus} />}
      </main>
    </div>
  );
}

function AuthScreen({ bootstrap, setSession, setStatus, status }) {
  const hasAdmin = Boolean(bootstrap?.has_admin);
  const [form, setForm] = useState({ username: '', password: '', token: '' });

  const submit = async (event) => {
    event.preventDefault();
    try {
      const path = hasAdmin ? '/api/login' : '/api/bootstrap/admin';
      const headers = hasAdmin ? { 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json', 'X-Admin-Token': form.token };
      const response = await fetch(path, {
        method: 'POST',
        headers,
        body: JSON.stringify({ username: form.username, password: form.password }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || response.statusText);
      localStorage.setItem(SESSION_KEY, body.session);
      setSession(body.session);
      setStatus('Authenticated.');
    } catch (error) {
      setStatus(error.message);
    }
  };

  return (
    <main className="auth-screen">
      <section className="auth-card">
        <div className="brand large">
          <div className="brand-mark">TL</div>
          <div>
            <div className="brand-title">TAKlite</div>
            <div className="brand-subtitle">Admin Console</div>
          </div>
        </div>
        <h1>{hasAdmin ? 'Admin Login' : 'Create First Admin'}</h1>
        <p>{hasAdmin ? 'Sign in over the VPN to manage clients and packages.' : 'Use the one-time bootstrap token from installation.'}</p>
        <form onSubmit={submit}>
          {!hasAdmin ? (
            <label>
              Bootstrap token
              <input value={form.token} onChange={(e) => setForm({ ...form, token: e.target.value })} autoComplete="one-time-code" />
            </label>
          ) : null}
          <label>
            Username
            <input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} autoComplete="username" />
          </label>
          <label>
            Password
            <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} autoComplete={hasAdmin ? 'current-password' : 'new-password'} />
          </label>
          <button className="btn primary" type="submit">{hasAdmin ? 'Log In' : 'Create Admin'}</button>
        </form>
        <div className="auth-status">{status}</div>
      </section>
    </main>
  );
}

function OverviewStrip({ data }) {
  const cards = [
    ['Health', data.health?.ok ? 'Online' : 'Checking', Gauge],
    ['Clients', String(data.clients.length), Wifi],
    ['Datapackages', String(data.packages.length), FileArchive],
    ['Users', String(data.portalUsers.length), Users],
    ['Packages', String(data.profiles.length), Boxes],
  ];
  return (
    <section className="stat-strip">
      {cards.map(([label, value, Icon]) => (
        <div className="stat-card" key={label}>
          <Icon size={18} />
          <div>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        </div>
      ))}
    </section>
  );
}

function Overview({ data, session, load, setStatus }) {
  return (
    <div className="dashboard-grid">
      <Panel title="Connected Clients" icon={Wifi}>
        <ClientsTable clients={data.clients.slice(0, 6)} compact />
      </Panel>
      <Panel title="Datapackages" icon={FileArchive}>
        <DatapackagesTable packages={data.packages.slice(0, 6)} session={session} load={load} setStatus={setStatus} compact />
      </Panel>
      <Panel title="Connection Users" icon={Users} wide>
        <UsersTable users={data.portalUsers.slice(0, 6)} portalUrl={data.portalUrl} session={session} load={load} setStatus={setStatus} compact />
      </Panel>
    </div>
  );
}

function Panel({ title, icon: Icon, children, wide = false, actions = null }) {
  return (
    <section className={wide ? 'panel wide' : 'panel'}>
      <div className="panel-head">
        <div>
          <Icon size={18} />
          <h2>{title}</h2>
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

function ClientsPanel({ clients }) {
  return (
    <Panel title="Connected Clients" icon={Wifi} wide>
      <ClientsTable clients={clients} />
    </Panel>
  );
}

function ClientsTable({ clients, compact = false }) {
  if (!clients.length) return <Empty title="No connected clients" detail="Clients will appear after ATAK or WinTAK sends CoT traffic." />;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>UID</th>
            <th>IP</th>
            <th>Mode</th>
            {!compact && <th>Client Cert</th>}
            <th>Uptime</th>
            {!compact && <th>Last Seen</th>}
          </tr>
        </thead>
        <tbody>
          {clients.map((client) => (
            <tr key={`${client.uid}-${client.ip}`}>
              <td><strong>{client.callsign || 'Unknown'}</strong></td>
              <td><code>{client.uid || 'unknown'}</code></td>
              <td>{client.ip || '-'}</td>
              <td><Badge tone={client.transport === 'tls' ? 'good' : 'neutral'}>{client.transport || 'tcp'}</Badge></td>
              {!compact && <td>{client.peer_cert_cn || '-'}</td>}
              <td>{fmtUptime(client.connected_at)}</td>
              {!compact && <td>{fmtTime(client.last_seen)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DatapackagesPanel({ packages, session, load, setStatus }) {
  return (
    <Panel title="Datapackages" icon={FileArchive} wide>
      <DatapackagesTable packages={packages} session={session} load={load} setStatus={setStatus} />
    </Panel>
  );
}

function DatapackagesTable({ packages, session, load, setStatus, compact = false }) {
  if (!packages.length) return <Empty title="No datapackages" detail="Uploaded packages from TAK clients will appear here." />;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            {!compact && <th>Hash</th>}
            <th>Size</th>
            <th>Tool</th>
            <th>Submitted</th>
            {!compact && <th>Creator</th>}
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {packages.map((pkg) => (
            <tr key={pkg.Hash}>
              <td><strong>{pkg.Name}</strong></td>
              {!compact && <td><code>{pkg.Hash}</code></td>}
              <td>{fmtBytes(pkg.Size)}</td>
              <td><Badge>{pkg.Tool || 'public'}</Badge></td>
              <td>{fmtTime(pkg.SubmissionDateTime)}</td>
              {!compact && <td><code>{pkg.CreatorUid || '-'}</code></td>}
              <td>
                <div className="row-actions">
                  <a className="icon-btn" href={`/Marti/sync/content?hash=${encodeURIComponent(pkg.Hash)}`} download={pkg.Name} title="Download"><Download size={15} /></a>
                  <button className="icon-btn danger" title="Delete" onClick={() => deletePackage(pkg, session, load, setStatus)}><Trash2 size={15} /></button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

async function deletePackage(pkg, session, load, setStatus) {
  if (!confirm(`Delete datapackage "${pkg.Name}" from TAKlite?`)) return;
  await api('/api/datapackages/delete', session, { method: 'POST', body: JSON.stringify({ hash: pkg.Hash, delete_file: true }) });
  setStatus('Datapackage deleted.');
  await load();
}

function UsersPanel({ users, portalUrl, session, load, setStatus }) {
  return (
    <Panel title="Connection Users" icon={Users} wide actions={<span className="hint">Portal: <code>{portalUrl}</code></span>}>
      <CreateUser session={session} load={load} setStatus={setStatus} />
      <UsersTable users={users} portalUrl={portalUrl} session={session} load={load} setStatus={setStatus} />
    </Panel>
  );
}

function CreateUser({ session, load, setStatus }) {
  const [form, setForm] = useState({ username: '', password: '', description: '', allow_redownload: false });
  const submit = async (event) => {
    event.preventDefault();
    await api('/api/portal-users/create', session, { method: 'POST', body: JSON.stringify(form) });
    setStatus(`Connection user ${form.username} created.`);
    setForm({ username: '', password: '', description: '', allow_redownload: false });
    await load();
  };
  return (
    <form className="create-grid" onSubmit={submit}>
      <label>Username<input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} placeholder="alpha-phone" /></label>
      <label>Password<input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="Download password" /></label>
      <label>Description<input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Optional note" /></label>
      <label className="check"><input type="checkbox" checked={form.allow_redownload} onChange={(e) => setForm({ ...form, allow_redownload: e.target.checked })} /> Allow re-download</label>
      <button className="btn primary" type="submit"><UserPlus size={16} />Create User</button>
    </form>
  );
}

function UsersTable({ users, session, load, setStatus, compact = false }) {
  if (!users.length) return <Empty title="No connection users" detail="Create a user to issue a portal login and matching DP.zip." />;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>User</th>
            <th>Status</th>
            <th>Connection</th>
            {!compact && <th>Downloads</th>}
            {!compact && <th>Re-download</th>}
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => {
            const url = `${location.origin}${user.portal_path || '/connect/'}`;
            return (
              <tr key={user.id}>
                <td><strong>{user.username}</strong><span>{user.description || user.display_name || ''}</span></td>
                <td><Badge tone={user.revoked ? 'bad' : 'good'}>{user.revoked ? 'revoked' : 'active'}</Badge></td>
                <td><code>{user.connect_string || '-'}</code><br /><code>{url}</code></td>
                {!compact && <td>{user.download_count || 0}<span>last {fmtTime(user.last_download_at)}</span></td>}
                {!compact && <td>{user.allow_redownload ? 'yes' : 'no'}</td>}
                <td><UserActions user={user} url={url} session={session} load={load} setStatus={setStatus} compact={compact} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function UserActions({ user, url, session, load, setStatus, compact }) {
  return (
    <div className="row-actions">
      <button className="icon-btn" title="Download DP.zip" disabled={user.revoked} onClick={() => downloadProfile(user.cert_profile_id, session)}><Download size={15} /></button>
      {!compact && <button className="icon-btn" title="Copy URL" disabled={user.revoked} onClick={() => copyText(url, setStatus)}><Copy size={15} /></button>}
      {!compact && <button className="icon-btn" title="QR" disabled={user.revoked} onClick={() => showQr(user.id, session, setStatus)}><QrCode size={15} /></button>}
      {!compact && <button className="icon-btn" title="Edit" disabled={user.revoked} onClick={() => editUser(user, session, load, setStatus)}><Pencil size={15} /></button>}
      {!compact && <button className="icon-btn" title="Reset password" disabled={user.revoked} onClick={() => resetUser(user, session, load, setStatus)}><KeyRound size={15} /></button>}
      {!compact && <button className="icon-btn" title={user.allow_redownload ? 'Disable re-download' : 'Allow re-download'} disabled={user.revoked} onClick={() => toggleRedownload(user, session, load, setStatus)}><RotateCw size={15} /></button>}
      <button className="icon-btn" title="Reissue" onClick={() => reissueUser(user, session, load, setStatus)}><PackagePlus size={15} /></button>
      <button className="icon-btn danger" title="Revoke" disabled={user.revoked} onClick={() => revokeUser(user, session, load, setStatus)}><XCircle size={15} /></button>
      <button className="icon-btn danger" title="Delete" onClick={() => deleteUser(user, session, load, setStatus)}><Trash2 size={15} /></button>
    </div>
  );
}

function ProfilesPanel({ profiles, certPassword, session, load, setStatus }) {
  return (
    <Panel title="Connection Packages" icon={Boxes} wide actions={<span className="hint">Certificate password: <code>{certPassword}</code></span>}>
      <CreateProfile session={session} load={load} setStatus={setStatus} />
      <ProfilesTable profiles={profiles} session={session} load={load} setStatus={setStatus} />
    </Panel>
  );
}

function CreateProfile({ session, load, setStatus }) {
  const [form, setForm] = useState({ name: '', description: '' });
  const submit = async (event) => {
    event.preventDefault();
    await api('/api/cert-profiles/create', session, { method: 'POST', body: JSON.stringify(form) });
    setStatus('Connection package created.');
    setForm({ name: '', description: '' });
    await load();
  };
  return (
    <form className="create-grid compact" onSubmit={submit}>
      <label>Name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="alpha-phone" /></label>
      <label>Description<input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Optional note" /></label>
      <button className="btn primary" type="submit"><PackagePlus size={16} />Create DP.zip</button>
    </form>
  );
}

function ProfilesTable({ profiles, session, load, setStatus }) {
  if (!profiles.length) return <Empty title="No connection packages" detail="Create or reissue packages for ATAK/WinTAK TLS connections." />;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Status</th>
            <th>Connection / URL</th>
            <th>Description</th>
            <th>Created</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {profiles.map((profile) => {
            const url = `${location.origin}${profile.public_download_path || ''}`;
            return (
              <tr key={profile.id}>
                <td><strong>{profile.name}</strong></td>
                <td><Badge tone={profile.revoked ? 'bad' : 'good'}>{profile.revoked ? 'revoked' : 'active'}</Badge></td>
                <td><code>{profile.connect_string}</code><br /><code>{url}</code></td>
                <td>{profile.description || '-'}</td>
                <td>{fmtTime(profile.created_at)}</td>
                <td>
                  <div className="row-actions">
                    <button className="icon-btn" title="Download" disabled={profile.revoked} onClick={() => downloadProfile(profile.id, session)}><Download size={15} /></button>
                    <button className="icon-btn" title="Copy URL" disabled={profile.revoked} onClick={() => copyText(url, setStatus)}><Copy size={15} /></button>
                    <button className="icon-btn danger" title="Revoke" disabled={profile.revoked} onClick={() => revokeProfile(profile, session, load, setStatus)}><XCircle size={15} /></button>
                    <button className="icon-btn danger" title="Delete" onClick={() => deleteProfile(profile, session, load, setStatus)}><Trash2 size={15} /></button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

async function downloadProfile(id, session) {
  const response = await fetch(`/api/cert-profiles/download?id=${encodeURIComponent(id)}`, { headers: authHeaders(session, {}) });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ error: response.statusText }));
    throw new Error(body.error || response.statusText);
  }
  const name = (response.headers.get('Content-Disposition') || '').match(/filename="([^"]+)"/)?.[1] || 'taklite-connection.dp.zip';
  downloadBlob(await response.blob(), name);
}

async function copyText(text, setStatus) {
  await navigator.clipboard.writeText(text);
  setStatus('Copied to clipboard.');
}

async function showQr(id, session, setStatus) {
  const response = await fetch(`/api/portal-users/qr?id=${encodeURIComponent(id)}`, { headers: authHeaders(session, {}) });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ error: response.statusText }));
    throw new Error(body.error || response.statusText);
  }
  const url = URL.createObjectURL(await response.blob());
  const win = window.open('', 'takliteQr', 'width=420,height=470');
  win.document.write(`<title>TAKlite QR</title><body style="margin:0;background:#101814;color:#e6eee8;font-family:system-ui;text-align:center;padding:24px"><h2>Connection Portal</h2><img src="${url}" style="width:320px;height:320px;background:white;padding:12px;border-radius:16px"><p>Scan after VPN is connected.</p></body>`);
  setStatus('QR opened.');
}

async function resetUser(user, session, load, setStatus) {
  const password = prompt(`New password for ${user.username}`);
  if (!password) return;
  await api('/api/portal-users/reset-password', session, { method: 'POST', body: JSON.stringify({ id: user.id, password }) });
  setStatus('Password reset.');
  await load();
}

async function editUser(user, session, load, setStatus) {
  const displayName = prompt(`Display name for ${user.username}`, user.display_name || '');
  if (displayName === null) return;
  const description = prompt(`Description for ${user.username}`, user.description || '');
  if (description === null) return;
  await api('/api/portal-users/edit', session, { method: 'POST', body: JSON.stringify({ id: user.id, display_name: displayName, description }) });
  setStatus('User updated.');
  await load();
}

async function toggleRedownload(user, session, load, setStatus) {
  await api('/api/portal-users/redownload', session, { method: 'POST', body: JSON.stringify({ id: user.id, allow_redownload: !user.allow_redownload }) });
  setStatus('Re-download setting updated.');
  await load();
}

async function reissueUser(user, session, load, setStatus) {
  if (!confirm(`Reissue ${user.username} with a new certificate package?`)) return;
  await api('/api/portal-users/reissue', session, { method: 'POST', body: JSON.stringify({ id: user.id }) });
  setStatus('User reissued.');
  await load();
}

async function revokeUser(user, session, load, setStatus) {
  if (!confirm(`Revoke ${user.username} and their certificate package?`)) return;
  await api('/api/portal-users/revoke', session, { method: 'POST', body: JSON.stringify({ id: user.id }) });
  setStatus('User revoked.');
  await load();
}

async function deleteUser(user, session, load, setStatus) {
  if (!confirm(`Delete user ${user.username}?`)) return;
  const deleteProfile = confirm('Delete generated DP.zip/certificate package files too?');
  await api('/api/portal-users/delete', session, { method: 'POST', body: JSON.stringify({ id: user.id, delete_profile: deleteProfile }) });
  setStatus('User deleted.');
  await load();
}

async function revokeProfile(profile, session, load, setStatus) {
  if (!confirm(`Revoke connection package ${profile.name}?`)) return;
  await api('/api/cert-profiles/revoke', session, { method: 'POST', body: JSON.stringify({ id: profile.id }) });
  setStatus('Package revoked.');
  await load();
}

async function deleteProfile(profile, session, load, setStatus) {
  if (!confirm(`Delete connection package ${profile.name} and generated files?`)) return;
  await api('/api/cert-profiles/delete', session, { method: 'POST', body: JSON.stringify({ id: profile.id, delete_files: true }) });
  setStatus('Package deleted.');
  await load();
}

function Empty({ title, detail }) {
  return (
    <div className="empty-state">
      <Activity size={20} />
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}

function Badge({ children, tone = 'neutral' }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

createRoot(document.getElementById('root')).render(<App />);
