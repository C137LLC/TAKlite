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
  Link2,
  LayoutDashboard,
  LogOut,
  PackagePlus,
  Pencil,
  QrCode,
  RefreshCw,
  RotateCw,
  ShieldCheck,
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
  ['health', Gauge, 'Health'],
  ['clients', Wifi, 'Clients'],
  ['datapackages', FileArchive, 'Datapackages'],
  ['users', Users, 'Users'],
  ['packages', Boxes, 'Connection Packages'],
  ['access', ShieldCheck, 'Access'],
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

function downloadText(text, filename, type = 'text/plain') {
  downloadBlob(new Blob([text], { type }), filename);
}

function csvCell(value) {
  return `"${String(value ?? '').replaceAll('"', '""')}"`;
}

function bulkUsersCsv(items) {
  const rows = [
    ['username', 'password', 'portal_url', 'connection'],
    ...items.map((item) => [item.username, item.password, item.portal_url || `${location.origin}${item.portal_path || '/connect/'}`, item.connect_string]),
  ];
  return rows.map((row) => row.map(csvCell).join(',')).join('\n');
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
    access: { roles: [], groups: [], links: [] },
    systemHealth: null,
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
      const [packages, clients, profiles, portal, access, systemHealth] = await Promise.all([
        api('/api/datapackages', session),
        api('/api/clients', session),
        api('/api/cert-profiles', session),
        api('/api/portal-users', session),
        api('/api/access-control', session),
        api('/api/system-health', session),
      ]);
      setData({
        health,
        packages: packages.items || [],
        clients: clients.items || [],
        profiles: profiles.items || [],
        portalUsers: portal.items || [],
        access: access || { roles: [], groups: [], links: [] },
        systemHealth,
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
    setData({ health: null, clients: [], packages: [], profiles: [], portalUsers: [], access: { roles: [], groups: [], links: [] }, systemHealth: null, portalUrl: '', certPassword: '' });
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
        {active === 'health' && <HealthPanel health={data.systemHealth} />}
        {active === 'clients' && <ClientsPanel clients={data.clients} />}
        {active === 'datapackages' && <DatapackagesPanel packages={data.packages} session={session} load={load} setStatus={setStatus} />}
        {active === 'users' && <UsersPanel users={data.portalUsers} access={data.access} portalUrl={data.portalUrl} session={session} load={load} setStatus={setStatus} />}
        {active === 'packages' && <ProfilesPanel profiles={data.profiles} certPassword={data.certPassword} session={session} load={load} setStatus={setStatus} />}
        {active === 'access' && <AccessPanel users={data.portalUsers} access={data.access} session={session} load={load} setStatus={setStatus} />}
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
    ['Access', String((data.access?.roles?.length || 0) + (data.access?.groups?.length || 0)), ShieldCheck],
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

function HealthPanel({ health }) {
  if (!health) return <Panel title="Server Health" icon={Gauge} wide><Empty title="Health loading" detail="Refresh the dashboard to reload service health." /></Panel>;
  const database = health.database || {};
  const storage = health.storage || {};
  const security = health.security || {};
  const connections = health.connections || {};
  return (
    <div className="dashboard-grid">
      <Panel title="Server Health" icon={Gauge}>
        <div className="health-grid">
          <HealthMetric label="Version" value={health.version || '-'} />
          <HealthMetric label="Database" value={database.ok ? 'Online' : 'Error'} tone={database.ok ? 'good' : 'bad'} />
          <HealthMetric label="Clients" value={connections.clients ?? 0} />
          <HealthMetric label="Packages" value={database.counts?.datapackages ?? 0} />
        </div>
      </Panel>
      <Panel title="Storage" icon={FileArchive}>
        <div className="health-grid">
          <HealthMetric label="Database" value={fmtBytes(database.bytes || 0)} />
          <HealthMetric label="WAL" value={fmtBytes(database.wal_bytes || 0)} />
          <HealthMetric label="Packages" value={fmtBytes(storage.package_bytes || 0)} />
          <HealthMetric label="Certificates" value={fmtBytes(storage.cert_bytes || 0)} />
        </div>
      </Panel>
      <Panel title="Security" icon={ShieldCheck} wide>
        <div className="health-grid wide">
          <HealthMetric label="Access Enforcement" value={security.access_enforcement ? 'On' : 'Off'} tone={security.access_enforcement ? 'good' : 'warn'} />
          <HealthMetric label="Client Cert Required" value={security.cot_tls_require_client_cert ? 'On' : 'Off'} tone={security.cot_tls_require_client_cert ? 'good' : 'warn'} />
          <HealthMetric label="Legacy Cert CN" value={security.allow_legacy_client_cert ? 'Allowed' : 'Blocked'} tone={security.allow_legacy_client_cert ? 'warn' : 'good'} />
          <HealthMetric label="Admin Auth" value={security.admin_auth_enabled ? 'On' : 'Off'} tone={security.admin_auth_enabled ? 'good' : 'bad'} />
          <HealthMetric label="WG Dashboard" value={health.wireguard?.dashboard_url || '-'} />
        </div>
      </Panel>
      {database.error ? (
        <Panel title="Health Error" icon={XCircle} wide>
          <div className="error-box">{database.error}</div>
        </Panel>
      ) : null}
    </div>
  );
}

function HealthMetric({ label, value, tone = 'neutral' }) {
  return (
    <div className={`health-metric ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
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

async function editRole(role, session, load, setStatus) {
  const name = prompt(`Role name`, role.name);
  if (name === null) return;
  const description = prompt(`Description for ${name}`, role.description || '');
  if (description === null) return;
  await api('/api/access-roles/update', session, { method: 'POST', body: JSON.stringify({ ...role, name, description }) });
  setStatus('Role updated.');
  await load();
}

async function deleteRole(role, session, load, setStatus) {
  if (!confirm(`Delete role ${role.name}? Users with this role will keep their groups but lose the role.`)) return;
  await api('/api/access-roles/delete', session, { method: 'POST', body: JSON.stringify({ id: role.id }) });
  setStatus('Role deleted.');
  await load();
}

async function editGroup(group, session, load, setStatus) {
  const name = prompt(`Group name`, group.name);
  if (name === null) return;
  const description = prompt(`Description for ${name}`, group.description || '');
  if (description === null) return;
  const color = prompt(`Hex color for ${name}`, group.color || '#64c18c');
  if (color === null) return;
  await api('/api/access-groups/update', session, { method: 'POST', body: JSON.stringify({ ...group, name, description, color }) });
  setStatus('Group updated.');
  await load();
}

async function deleteGroup(group, session, load, setStatus) {
  if (!confirm(`Delete group ${group.name}? Membership and links for this group will be removed.`)) return;
  await api('/api/access-groups/delete', session, { method: 'POST', body: JSON.stringify({ id: group.id }) });
  setStatus('Group deleted.');
  await load();
}

function UsersPanel({ users, access, portalUrl, session, load, setStatus }) {
  const [showBulk, setShowBulk] = useState(false);
  return (
    <Panel title="Connection Users" icon={Users} wide actions={<span className="hint">Portal: <code>{portalUrl}</code></span>}>
      <CreateUser access={access} session={session} load={load} setStatus={setStatus} />
      <div className="panel-tools">
        <button className="btn ghost" type="button" onClick={() => setShowBulk(!showBulk)}><Users size={16} />Create Bulk Users</button>
        <span className="hint">Bulk users receive one shared portal password for the batch.</span>
      </div>
      {showBulk && <CreateBulkUsers access={access} session={session} load={load} setStatus={setStatus} />}
      <UsersTable users={users} portalUrl={portalUrl} session={session} load={load} setStatus={setStatus} />
    </Panel>
  );
}

function CreateUser({ access, session, load, setStatus }) {
  const roles = access?.roles || [];
  const groups = access?.groups || [];
  const [form, setForm] = useState({ username: '', password: '', description: '', allow_redownload: false, role_id: '', group_ids: [] });
  const toggleGroup = (id) => {
    const groupIds = new Set(form.group_ids);
    if (groupIds.has(id)) groupIds.delete(id);
    else groupIds.add(id);
    setForm({ ...form, group_ids: [...groupIds] });
  };
  const submit = async (event) => {
    event.preventDefault();
    await api('/api/portal-users/create', session, { method: 'POST', body: JSON.stringify({ ...form, role_id: form.role_id || null }) });
    setStatus(`Connection user ${form.username} created.`);
    setForm({ username: '', password: '', description: '', allow_redownload: false, role_id: '', group_ids: [] });
    await load();
  };
  return (
    <form className="create-grid" onSubmit={submit}>
      <label>Username<input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} placeholder="alpha-phone" /></label>
      <label>Password<input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="Download password" /></label>
      <label>Description<input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Optional note" /></label>
      <label>Role<select value={form.role_id} onChange={(e) => setForm({ ...form, role_id: e.target.value })}>
        <option value="">No role</option>
        {roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}
      </select></label>
      <div className="group-picks compact">
        {groups.map((group) => (
          <label className="check group-chip" key={group.id}>
            <input type="checkbox" checked={form.group_ids.includes(group.id)} onChange={() => toggleGroup(group.id)} />
            {group.name}
          </label>
        ))}
      </div>
      <label className="check"><input type="checkbox" checked={form.allow_redownload} onChange={(e) => setForm({ ...form, allow_redownload: e.target.checked })} /> Allow re-download</label>
      <button className="btn primary" type="submit"><UserPlus size={16} />Create User</button>
    </form>
  );
}

function CreateBulkUsers({ access, session, load, setStatus }) {
  const roles = access?.roles || [];
  const groups = access?.groups || [];
  const [form, setForm] = useState({ prefix: 'user', count: 20, description: '', allow_redownload: false, role_id: '', group_ids: [] });
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const toggleGroup = (id) => {
    const groupIds = new Set(form.group_ids);
    if (groupIds.has(id)) groupIds.delete(id);
    else groupIds.add(id);
    setForm({ ...form, group_ids: [...groupIds] });
  };
  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const body = await api('/api/portal-users/bulk-create', session, { method: 'POST', body: JSON.stringify({ ...form, role_id: form.role_id || null }) });
      setResult(body);
      setStatus(`Created ${body.count} bulk connection user(s). Save the shared password before leaving this page.`);
      await load();
    } finally {
      setBusy(false);
    }
  };
  const items = result?.items || [];
  const csv = items.length ? bulkUsersCsv(items) : '';
  return (
    <div className="bulk-panel">
      <form className="create-grid bulk" onSubmit={submit}>
        <label>Name prefix<input value={form.prefix} onChange={(e) => setForm({ ...form, prefix: e.target.value })} placeholder="user" /></label>
        <label>Number<input type="number" min="1" max="100" value={form.count} onChange={(e) => setForm({ ...form, count: e.target.value })} /></label>
        <label>Description<input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Optional note" /></label>
        <label>Role<select value={form.role_id} onChange={(e) => setForm({ ...form, role_id: e.target.value })}>
          <option value="">No role</option>
          {roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}
        </select></label>
        <label className="check"><input type="checkbox" checked={form.allow_redownload} onChange={(e) => setForm({ ...form, allow_redownload: e.target.checked })} /> Allow re-download</label>
        <button className="btn primary" type="submit" disabled={busy}><UserPlus size={16} />{busy ? 'Creating...' : 'Create Batch'}</button>
      </form>
      {groups.length ? (
        <div className="group-picks">
          {groups.map((group) => (
            <label className="check group-chip" key={group.id}>
              <input type="checkbox" checked={form.group_ids.includes(group.id)} onChange={() => toggleGroup(group.id)} />
              <span className="color-dot" style={{ background: group.color || '#64c18c' }} /> {group.name}
            </label>
          ))}
        </div>
      ) : null}
      {items.length > 0 && (
        <div className="bulk-result">
          <div className="bulk-summary">
            <div>
              <span className="mini-label">Shared Password</span>
              <code>{result.shared_password}</code>
            </div>
            <div className="row-actions">
              <button className="btn ghost" type="button" onClick={() => copyText(result.shared_password, setStatus)}><Copy size={15} />Copy Password</button>
              <button className="btn ghost" type="button" onClick={() => copyText(csv, setStatus)}><Copy size={15} />Copy CSV</button>
              <button className="btn ghost" type="button" onClick={() => downloadText(csv, `${form.prefix || 'taklite'}-bulk-users.csv`, 'text/csv')}><Download size={15} />Download CSV</button>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Password</th>
                  <th>Portal / Connection</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id || item.username}>
                    <td><strong>{item.username}</strong></td>
                    <td><code>{item.password}</code></td>
                    <td><code>{item.portal_url}</code><br /><code>{item.connect_string}</code></td>
                    <td>
                      <div className="row-actions">
                        <button className="icon-btn" title="Download DP.zip" onClick={() => downloadProfile(item.cert_profile_id, session)}><Download size={15} /></button>
                        <button className="icon-btn" title="Copy portal URL" onClick={() => copyText(item.portal_url, setStatus)}><Copy size={15} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function AccessPanel({ users, access, session, load, setStatus }) {
  const roles = access?.roles || [];
  const groups = access?.groups || [];
  const links = access?.links || [];
  return (
    <div className="dashboard-grid">
      <Panel title="Roles" icon={ShieldCheck}>
        <CreateRole session={session} load={load} setStatus={setStatus} />
        <RolesTable roles={roles} session={session} load={load} setStatus={setStatus} />
      </Panel>
      <Panel title="Groups" icon={Users}>
        <CreateGroup session={session} load={load} setStatus={setStatus} />
        <GroupsTable groups={groups} session={session} load={load} setStatus={setStatus} />
      </Panel>
      <Panel title="Bulk User Access" icon={Users} wide>
        <BulkAccess users={users} roles={roles} groups={groups} session={session} load={load} setStatus={setStatus} />
      </Panel>
      <Panel title="Group Links" icon={Link2} wide>
        <GroupLinks groups={groups} links={links} session={session} load={load} setStatus={setStatus} />
      </Panel>
    </div>
  );
}

function CreateRole({ session, load, setStatus }) {
  const [form, setForm] = useState({
    name: '',
    description: '',
    can_see_all: false,
    can_send_all: false,
    can_see_own_groups: true,
    can_send_own_groups: true,
  });
  const submit = async (event) => {
    event.preventDefault();
    try {
      await api('/api/access-roles/create', session, { method: 'POST', body: JSON.stringify(form) });
      setStatus(`Role ${form.name} created.`);
      setForm({ name: '', description: '', can_see_all: false, can_send_all: false, can_see_own_groups: true, can_send_own_groups: true });
      await load();
    } catch (error) {
      setStatus(`Role create failed: ${error.message}`);
    }
  };
  return (
    <form className="access-create" onSubmit={submit}>
      <label>Role name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Supervisor" /></label>
      <label>Description<input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Optional note" /></label>
      <div className="check-row">
        <label className="check"><input type="checkbox" checked={form.can_see_all} onChange={(e) => setForm({ ...form, can_see_all: e.target.checked })} /> See all</label>
        <label className="check"><input type="checkbox" checked={form.can_send_all} onChange={(e) => setForm({ ...form, can_send_all: e.target.checked })} /> Send all</label>
        <label className="check"><input type="checkbox" checked={form.can_see_own_groups} onChange={(e) => setForm({ ...form, can_see_own_groups: e.target.checked })} /> See own groups</label>
        <label className="check"><input type="checkbox" checked={form.can_send_own_groups} onChange={(e) => setForm({ ...form, can_send_own_groups: e.target.checked })} /> Send own groups</label>
      </div>
      <button className="btn primary" type="submit"><ShieldCheck size={16} />Create Role</button>
    </form>
  );
}

function RolesTable({ roles, session, load, setStatus }) {
  if (!roles.length) return <Empty title="No roles" detail="Create generic roles, then assign them to connection users." />;
  const updateRole = async (role, patch) => {
    try {
      await api('/api/access-roles/update', session, { method: 'POST', body: JSON.stringify({ ...role, ...patch }) });
      setStatus('Role updated.');
      await load();
    } catch (error) {
      setStatus(`Role update failed: ${error.message}`);
    }
  };
  return (
    <div className="table-wrap">
      <table className="access-table">
        <thead><tr><th>Role</th><th>Permissions</th><th>Action</th></tr></thead>
        <tbody>
          {roles.map((role) => (
            <tr key={role.id}>
              <td><strong>{role.name}</strong><span>{role.description || '-'}</span></td>
              <td>
                <div className="check-row compact">
                  <label className="check"><input type="checkbox" checked={role.can_see_all} onChange={(e) => updateRole(role, { can_see_all: e.target.checked })} /> See all</label>
                  <label className="check"><input type="checkbox" checked={role.can_send_all} onChange={(e) => updateRole(role, { can_send_all: e.target.checked })} /> Send all</label>
                  <label className="check"><input type="checkbox" checked={role.can_see_own_groups} onChange={(e) => updateRole(role, { can_see_own_groups: e.target.checked })} /> See own</label>
                  <label className="check"><input type="checkbox" checked={role.can_send_own_groups} onChange={(e) => updateRole(role, { can_send_own_groups: e.target.checked })} /> Send own</label>
                </div>
              </td>
              <td>
                <div className="row-actions">
                  <button className="icon-btn" title="Edit" onClick={() => editRole(role, session, load, setStatus)}><Pencil size={15} /></button>
                  <button className="icon-btn danger" title="Delete" onClick={() => deleteRole(role, session, load, setStatus)}><Trash2 size={15} /></button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CreateGroup({ session, load, setStatus }) {
  const [form, setForm] = useState({ name: '', description: '', color: '#64c18c' });
  const submit = async (event) => {
    event.preventDefault();
    try {
      await api('/api/access-groups/create', session, { method: 'POST', body: JSON.stringify(form) });
      setStatus(`Group ${form.name} created.`);
      setForm({ name: '', description: '', color: '#64c18c' });
      await load();
    } catch (error) {
      setStatus(`Group create failed: ${error.message}`);
    }
  };
  return (
    <form className="access-create group-create" onSubmit={submit}>
      <label>Group name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Alpha" /></label>
      <label>Description<input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Optional note" /></label>
      <label>Color<input type="color" value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} /></label>
      <button className="btn primary" type="submit"><Users size={16} />Create Group</button>
    </form>
  );
}

function GroupsTable({ groups, session, load, setStatus }) {
  if (!groups.length) return <Empty title="No groups" detail="Create teams or access buckets, then link them together as needed." />;
  return (
    <div className="table-wrap">
      <table className="access-table">
        <thead><tr><th>Group</th><th>Description</th><th>Action</th></tr></thead>
        <tbody>
          {groups.map((group) => (
            <tr key={group.id}>
              <td><strong><span className="color-dot" style={{ background: group.color || '#64c18c' }} />{group.name}</strong></td>
              <td>{group.description || '-'}</td>
              <td>
                <div className="row-actions">
                  <button className="icon-btn" title="Edit" onClick={() => editGroup(group, session, load, setStatus)}><Pencil size={15} /></button>
                  <button className="icon-btn danger" title="Delete" onClick={() => deleteGroup(group, session, load, setStatus)}><Trash2 size={15} /></button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BulkAccess({ users, roles, groups, session, load, setStatus }) {
  const [form, setForm] = useState({ filter: '', role_id: '', group_ids: [], group_mode: 'replace' });
  const filter = form.filter.trim().toLowerCase();
  const matched = users.filter((user) => {
    if (!filter) return true;
    const haystack = [
      user.username,
      user.display_name,
      user.description,
      user.role_name,
      ...(user.groups || []).map((group) => group.name),
    ].join(' ').toLowerCase();
    return haystack.includes(filter);
  });
  const toggleGroup = (id) => {
    const groupIds = new Set(form.group_ids);
    if (groupIds.has(id)) groupIds.delete(id);
    else groupIds.add(id);
    setForm({ ...form, group_ids: [...groupIds] });
  };
  const submit = async (event) => {
    event.preventDefault();
    if (!matched.length) {
      setStatus('No users match that filter.');
      return;
    }
    const names = matched.slice(0, 8).map((user) => user.username).join(', ');
    const suffix = matched.length > 8 ? '...' : '';
    if (!confirm(`Apply access changes to ${matched.length} user(s): ${names}${suffix}`)) return;
    try {
      await api('/api/access-users/bulk-set', session, {
        method: 'POST',
        body: JSON.stringify({
          user_ids: matched.map((user) => user.id),
          role_id: form.role_id || null,
          group_ids: form.group_ids,
          group_mode: form.group_mode,
        }),
      });
      setStatus(`Updated access for ${matched.length} user(s).`);
      await load();
    } catch (error) {
      setStatus(`Bulk access update failed: ${error.message}`);
    }
  };
  return (
    <form className="bulk-access" onSubmit={submit}>
      <div className="bulk-access-grid">
        <label>Match users<input value={form.filter} onChange={(e) => setForm({ ...form, filter: e.target.value })} placeholder="alpha, team name, role name, or blank for all" /></label>
        <label>Role<select value={form.role_id} onChange={(e) => setForm({ ...form, role_id: e.target.value })}>
          <option value="">Leave role unchanged</option>
          {roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}
        </select></label>
        <label>Group mode<select value={form.group_mode} onChange={(e) => setForm({ ...form, group_mode: e.target.value })}>
          <option value="replace">Replace groups</option>
          <option value="add">Add groups</option>
          <option value="remove">Remove groups</option>
        </select></label>
        <button className="btn primary" type="submit"><ShieldCheck size={16} />Apply to {matched.length}</button>
      </div>
      <div className="group-picks">
        {groups.length ? groups.map((group) => (
          <label className="check group-chip" key={group.id}>
            <input type="checkbox" checked={form.group_ids.includes(group.id)} onChange={() => toggleGroup(group.id)} />
            <span className="color-dot" style={{ background: group.color || '#64c18c' }} /> {group.name}
          </label>
        )) : <span className="hint">Create groups before bulk assigning users.</span>}
      </div>
      <div className="matched-users">
        {matched.slice(0, 12).map((user) => <Badge key={user.id}>{user.username}</Badge>)}
        {matched.length > 12 && <Badge>{matched.length - 12} more</Badge>}
      </div>
    </form>
  );
}

function GroupLinks({ groups, links, session, load, setStatus }) {
  if (groups.length < 2) return <Empty title="Need at least two groups" detail="Create groups first, then link which groups can see or send to other groups." />;
  const findLink = (sourceId, targetId) => links.find((link) => link.source_group_id === sourceId && link.target_group_id === targetId) || {};
  const update = async (sourceId, targetId, patch) => {
    const current = findLink(sourceId, targetId);
    try {
      await api('/api/access-links/set', session, {
        method: 'POST',
        body: JSON.stringify({
          source_group_id: sourceId,
          target_group_id: targetId,
          can_see: Boolean(current.can_see),
          can_send: Boolean(current.can_send),
          ...patch,
        }),
      });
      setStatus('Group link updated.');
      await load();
    } catch (error) {
      setStatus(`Group link update failed: ${error.message}`);
    }
  };
  return (
    <div className="table-wrap">
      <table className="link-matrix">
        <thead>
          <tr>
            <th>Source group</th>
            {groups.map((group) => <th key={group.id}>{group.name}</th>)}
          </tr>
        </thead>
        <tbody>
          {groups.map((source) => (
            <tr key={source.id}>
              <td><strong><span className="color-dot" style={{ background: source.color || '#64c18c' }} />{source.name}</strong></td>
              {groups.map((target) => {
                const link = findLink(source.id, target.id);
                const same = source.id === target.id;
                return (
                  <td key={target.id}>
                    {same ? <span className="hint">own group</span> : (
                      <div className="link-checks">
                        <label className="check"><input type="checkbox" checked={Boolean(link.can_see)} onChange={(e) => update(source.id, target.id, { can_see: e.target.checked })} /> See</label>
                        <label className="check"><input type="checkbox" checked={Boolean(link.can_send)} onChange={(e) => update(source.id, target.id, { can_send: e.target.checked })} /> Send</label>
                      </div>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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
