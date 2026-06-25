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
  Settings,
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
  ['settings', Settings, 'Settings'],
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

function fmtDuration(secondsValue) {
  const seconds = Math.max(0, Math.floor(Number(secondsValue || 0)));
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (days) return `${days}d ${hours}h`;
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
            <button key={key} className={active === key ? 'nav-item active' : 'nav-item'} onClick={() => setActive(key)} aria-label={label} title={label}>
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
        {active === 'settings' && <SettingsPanel health={data.systemHealth} wgUrl={wgUrl} session={session} load={load} setStatus={setStatus} />}
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
          <HealthMetric label="TLS Client Cert Required" value={security.cot_tls_require_client_cert ? 'On' : 'Off'} tone={security.cot_tls_require_client_cert ? 'good' : 'warn'} />
          <HealthMetric label="Legacy Shared Cert CN" value={security.allow_legacy_client_cert ? 'Allowed' : 'Blocked'} tone={security.allow_legacy_client_cert ? 'warn' : 'good'} />
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

function SettingsPanel({ health, wgUrl, session, load, setStatus }) {
  const [updating, setUpdating] = useState(false);
  if (!health) return <Panel title="Settings" icon={Settings} wide><Empty title="Settings loading" detail="Refresh the dashboard to reload server settings." /></Panel>;
  const connections = health.connections || {};
  const config = health.config || {};
  const runtime = health.runtime || {};
  const security = health.security || {};
  const updates = health.updates || {};
  const gitCommand = `cd /root
rm -rf /root/TAKlite-update
git clone https://github.com/C137LLC/TAKlite.git /root/TAKlite-update

cd /root/taklite || cd /root/TAKlite
./update.sh --from-dir /root/TAKlite-update --app-dir "$PWD"`;
  const zipCommand = `cd /root/taklite || cd /root/TAKlite
./update.sh /root/TAKlite-v0.2.13.zip`;

  const copy = async (text, message) => {
    await navigator.clipboard.writeText(text);
    setStatus(message);
  };
  const runUpdate = async () => {
    if (!updates.gui_runner_enabled) return;
    if (!confirm('Run the configured TAKlite update command now? The updater should create a backup and preserve local data.')) return;
    setUpdating(true);
    try {
      const result = await api('/api/admin/update/run', session, {
        method: 'POST',
        body: JSON.stringify({ confirm: 'RUN_UPDATE' }),
      });
      setStatus(`Update finished with code ${result.returncode ?? 0}.`);
      await load();
    } catch (error) {
      setStatus(`Update failed: ${error.message}`);
    } finally {
      setUpdating(false);
    }
  };

  return (
    <div className="dashboard-grid">
      <Panel title="Server" icon={Gauge}>
        <div className="health-grid">
          <HealthMetric label="Version" value={health.version || '-'} />
          <HealthMetric label="Uptime" value={fmtDuration(runtime.uptime_seconds)} />
          <HealthMetric label="Host" value={config.public_host || config.server_host || '-'} />
          <HealthMetric label="Container" value={runtime.container_status || '-'} tone={runtime.container_status === 'running' ? 'good' : 'warn'} />
          <HealthMetric label="HTTP / HTTPS" value={`${connections.http_port || '-'} / ${connections.https_port || '-'}`} />
          <HealthMetric label="CoT / TLS CoT" value={`${connections.cot_port || '-'} / ${connections.cot_tls_port || '-'}`} />
          <HealthMetric label="Max Upload" value={fmtBytes(config.max_upload_bytes || 0)} />
          <HealthMetric label="Started" value={fmtTime(runtime.started_at)} />
        </div>
      </Panel>

      <Panel title="Security" icon={ShieldCheck}>
        <div className="health-grid">
          <HealthMetric label="Access Enforcement" value={security.access_enforcement ? 'On' : 'Off'} tone={security.access_enforcement ? 'good' : 'warn'} />
          <HealthMetric label="TLS Client Cert" value={security.cot_tls_require_client_cert ? 'Required' : 'Optional'} tone={security.cot_tls_require_client_cert ? 'good' : 'warn'} />
          <HealthMetric label="Legacy Shared CN" value={security.allow_legacy_client_cert ? 'Allowed' : 'Blocked'} tone={security.allow_legacy_client_cert ? 'warn' : 'good'} />
          <HealthMetric label="Admin Auth" value={security.admin_auth_enabled ? 'On' : 'Off'} tone={security.admin_auth_enabled ? 'good' : 'bad'} />
        </div>
      </Panel>

      <Panel title="WireGuard" icon={Wifi}>
        <div className="settings-stack">
          <div className="health-grid">
            <HealthMetric label="Dashboard" value={wgUrl || health.wireguard?.dashboard_url || '-'} />
            <HealthMetric label="VPN Health" value="Planned" />
          </div>
          {wgUrl || health.wireguard?.dashboard_url ? (
            <a className="btn ghost settings-action" href={wgUrl || health.wireguard.dashboard_url} target="_blank" rel="noreferrer">
              <ExternalLink size={16} />
              Open WG Dashboard
            </a>
          ) : null}
        </div>
      </Panel>

      <Panel title="Updates" icon={RotateCw} wide>
        <div className="settings-stack">
          <div className="settings-note">
            Updates preserve <code>.env</code>, TAKlite data, certificates, packages, WireGuard, the admin peer, and WGDashboard config.
          </div>
          <div className="health-grid wide">
            <HealthMetric label="Current Version" value={health.version || '-'} />
            <HealthMetric label="GUI Runner" value={updates.gui_runner_enabled ? 'Enabled' : 'Disabled'} tone={updates.gui_runner_enabled ? 'good' : 'neutral'} />
            <HealthMetric label="Backup" value="Created before update" />
            <HealthMetric label="Release Source" value="GitHub" />
            <HealthMetric label="Zip Update" value="Supported by CLI" />
          </div>
          <div className="settings-actions">
            <a className="btn ghost" href={updates.release_url || 'https://github.com/C137LLC/TAKlite/releases'} target="_blank" rel="noreferrer">
              <ExternalLink size={16} />
              Check Latest Release
            </a>
            <button className="btn ghost" onClick={() => copy(gitCommand, 'GitHub update command copied.')}>
              <Copy size={16} />
              Copy GitHub Update
            </button>
            <button className="btn ghost" onClick={() => copy(zipCommand, 'Zip update command copied.')}>
              <Copy size={16} />
              Copy Zip Update
            </button>
            <button className="btn primary" disabled={!updates.gui_runner_enabled || updating} onClick={runUpdate} title={updates.gui_runner_enabled ? 'Run the configured update command.' : 'Enable TAKLITE_GUI_UPDATE_ENABLED and TAKLITE_GUI_UPDATE_COMMAND to allow GUI updates.'}>
              <RotateCw size={16} className={updating ? 'spin' : ''} />
              {updating ? 'Updating' : 'Run Update'}
            </button>
          </div>
          <div className="code-block">
            <div className="mini-label">GitHub update command</div>
            <pre>{gitCommand}</pre>
          </div>
          <div className="code-block">
            <div className="mini-label">Zip update command</div>
            <pre>{zipCommand}</pre>
          </div>
        </div>
      </Panel>
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

function PanelHint({ children }) {
  return <div className="panel-hint">{children}</div>;
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
      <Panel title="User Membership" icon={UserPlus} wide>
        <PanelHint>Choose each user&apos;s role and group membership. Roles define broad permissions; groups define who users can see by default.</PanelHint>
        <UserAccessTable users={users} roles={roles} groups={groups} session={session} load={load} setStatus={setStatus} />
      </Panel>
      <Panel title="Bulk Membership" icon={Users} wide>
        <PanelHint>Select multiple users, then apply one role or group change to the whole selection.</PanelHint>
        <BulkAccess users={users} roles={roles} groups={groups} session={session} load={load} setStatus={setStatus} />
      </Panel>
      <Panel title="Role Permissions" icon={ShieldCheck}>
        <PanelHint>Use roles for permission levels. An admin-style role can see everyone without being visible to everyone else.</PanelHint>
        <CreateRole session={session} load={load} setStatus={setStatus} />
        <RolesTable roles={roles} session={session} load={load} setStatus={setStatus} />
      </Panel>
      <Panel title="Groups" icon={Users}>
        <PanelHint>Use groups for teams or visibility buckets such as Alpha, Bravo, Admin, or Rabbit.</PanelHint>
        <CreateGroup session={session} load={load} setStatus={setStatus} />
        <GroupsTable groups={groups} session={session} load={load} setStatus={setStatus} />
      </Panel>
      <Panel title="Visibility Links" icon={Link2} wide>
        <PanelHint>Link groups only when one group should see and send to another. No link means groups stay isolated unless a role has see-all/send-all.</PanelHint>
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
        <label className="check"><input type="checkbox" checked={form.can_see_all} onChange={(e) => setForm({ ...form, can_see_all: e.target.checked })} /> Can see everyone</label>
        <label className="check"><input type="checkbox" checked={form.can_send_all} onChange={(e) => setForm({ ...form, can_send_all: e.target.checked })} /> Can send to everyone</label>
        <label className="check"><input type="checkbox" checked={form.can_see_own_groups} onChange={(e) => setForm({ ...form, can_see_own_groups: e.target.checked })} /> Can see assigned groups</label>
        <label className="check"><input type="checkbox" checked={form.can_send_own_groups} onChange={(e) => setForm({ ...form, can_send_own_groups: e.target.checked })} /> Can send to assigned groups</label>
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
                  <label className="check"><input type="checkbox" checked={role.can_see_all} onChange={(e) => updateRole(role, { can_see_all: e.target.checked })} /> See everyone</label>
                  <label className="check"><input type="checkbox" checked={role.can_send_all} onChange={(e) => updateRole(role, { can_send_all: e.target.checked })} /> Send everyone</label>
                  <label className="check"><input type="checkbox" checked={role.can_see_own_groups} onChange={(e) => updateRole(role, { can_see_own_groups: e.target.checked })} /> See assigned</label>
                  <label className="check"><input type="checkbox" checked={role.can_send_own_groups} onChange={(e) => updateRole(role, { can_send_own_groups: e.target.checked })} /> Send assigned</label>
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
  const [form, setForm] = useState({ filter: '', role_id: '', group_ids: [], group_mode: 'replace', selected_user_ids: [] });
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
  const selectedIds = new Set(form.selected_user_ids);
  const selectedUsers = users.filter((user) => selectedIds.has(user.id));
  const toggleGroup = (id) => {
    const groupIds = new Set(form.group_ids);
    if (groupIds.has(id)) groupIds.delete(id);
    else groupIds.add(id);
    setForm({ ...form, group_ids: [...groupIds] });
  };
  const toggleUser = (id) => {
    const userIds = new Set(form.selected_user_ids);
    if (userIds.has(id)) userIds.delete(id);
    else userIds.add(id);
    setForm({ ...form, selected_user_ids: [...userIds] });
  };
  const selectMatched = () => {
    setForm({ ...form, selected_user_ids: [...new Set([...form.selected_user_ids, ...matched.map((user) => user.id)])] });
  };
  const clearSelected = () => {
    setForm({ ...form, selected_user_ids: [] });
  };
  const submit = async (event) => {
    event.preventDefault();
    if (!selectedUsers.length) {
      setStatus('Select one or more users first.');
      return;
    }
    const names = selectedUsers.slice(0, 8).map((user) => user.username).join(', ');
    const suffix = selectedUsers.length > 8 ? '...' : '';
    if (!confirm(`Apply access changes to ${selectedUsers.length} selected user(s): ${names}${suffix}`)) return;
    try {
      await api('/api/access-users/bulk-set', session, {
        method: 'POST',
        body: JSON.stringify({
          user_ids: selectedUsers.map((user) => user.id),
          role_id: form.role_id || null,
          group_ids: form.group_ids,
          group_mode: form.group_mode,
        }),
      });
      setStatus(`Updated access for ${selectedUsers.length} user(s).`);
      await load();
    } catch (error) {
      setStatus(`Bulk access update failed: ${error.message}`);
    }
  };
  return (
    <form className="bulk-access" onSubmit={submit}>
      <div className="bulk-access-grid">
        <label>Filter users<input value={form.filter} onChange={(e) => setForm({ ...form, filter: e.target.value })} placeholder="username, display name, role, or group" /></label>
        <label>Role<select value={form.role_id} onChange={(e) => setForm({ ...form, role_id: e.target.value })}>
          <option value="">Leave role unchanged</option>
          {roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}
        </select></label>
        <label>Group action<select value={form.group_mode} onChange={(e) => setForm({ ...form, group_mode: e.target.value })}>
          <option value="replace">Replace groups</option>
          <option value="add">Add groups</option>
          <option value="remove">Remove groups</option>
        </select></label>
        <button className="btn primary" type="submit"><ShieldCheck size={16} />Apply Policy to {selectedUsers.length}</button>
      </div>
      <div className="selection-toolbar">
        <span className="hint">{selectedUsers.length} selected, {matched.length} visible</span>
        <button className="btn ghost" type="button" onClick={selectMatched} disabled={!matched.length}>Select Visible</button>
        <button className="btn ghost" type="button" onClick={clearSelected} disabled={!selectedUsers.length}>Clear</button>
      </div>
      <UserSelectionList users={matched} selectedIds={selectedIds} toggleUser={toggleUser} />
      <div className="group-picks">
        {groups.length ? groups.map((group) => (
          <label className="check group-chip" key={group.id}>
            <input type="checkbox" checked={form.group_ids.includes(group.id)} onChange={() => toggleGroup(group.id)} />
            <span className="color-dot" style={{ background: group.color || '#64c18c' }} /> {group.name}
          </label>
        )) : <span className="hint">Create groups before bulk assigning users.</span>}
      </div>
      <div className="matched-users selected-users">
        {selectedUsers.slice(0, 12).map((user) => <Badge key={user.id}>{user.username}</Badge>)}
        {selectedUsers.length > 12 && <Badge>{selectedUsers.length - 12} more</Badge>}
      </div>
    </form>
  );
}

function UserSelectionList({ users, selectedIds, toggleUser }) {
  if (!users.length) return <Empty title="No matching users" detail="Adjust the filter or create connection users first." />;
  return (
    <div className="user-selection-list">
      {users.map((user) => (
        <label className={selectedIds.has(user.id) ? 'user-select-row selected' : 'user-select-row'} key={user.id}>
          <input type="checkbox" checked={selectedIds.has(user.id)} onChange={() => toggleUser(user.id)} />
          <span>
            <strong>{user.username}</strong>
            <small>{user.display_name || user.description || 'No description'}</small>
          </span>
          <span className="user-access-summary">
            {user.role_name ? <Badge>{user.role_name}</Badge> : <Badge>no role</Badge>}
            {(user.groups || []).length ? user.groups.map((group) => <Badge key={group.id}>{group.name}</Badge>) : <Badge>no groups</Badge>}
          </span>
        </label>
      ))}
    </div>
  );
}

function UserAccessTable({ users, roles, groups, session, load, setStatus }) {
  const [filter, setFilter] = useState('');
  const [drafts, setDrafts] = useState({});

  useEffect(() => {
    setDrafts(Object.fromEntries(users.map((user) => [
      user.id,
      {
        role_id: user.role_id || '',
        group_ids: [...(user.group_ids || [])],
      },
    ])));
  }, [users]);

  const filtered = users.filter((user) => {
    const value = filter.trim().toLowerCase();
    if (!value) return true;
    return [
      user.username,
      user.display_name,
      user.description,
      user.role_name,
      ...(user.groups || []).map((group) => group.name),
    ].join(' ').toLowerCase().includes(value);
  });

  const updateDraft = (userId, patch) => {
    setDrafts((current) => ({
      ...current,
      [userId]: {
        ...(current[userId] || { role_id: '', group_ids: [] }),
        ...patch,
      },
    }));
  };

  const toggleDraftGroup = (userId, groupId) => {
    const draft = drafts[userId] || { role_id: '', group_ids: [] };
    const groupIds = new Set(draft.group_ids || []);
    if (groupIds.has(groupId)) groupIds.delete(groupId);
    else groupIds.add(groupId);
    updateDraft(userId, { group_ids: [...groupIds] });
  };

  const saveUser = async (user) => {
    const draft = drafts[user.id] || { role_id: '', group_ids: [] };
    try {
      await api('/api/access-users/set', session, {
        method: 'POST',
        body: JSON.stringify({
          user_id: user.id,
          role_id: draft.role_id || null,
          group_ids: draft.group_ids || [],
        }),
      });
      setStatus(`Updated access for ${user.username}.`);
      await load();
    } catch (error) {
      setStatus(`User access update failed: ${error.message}`);
    }
  };

  if (!users.length) return <Empty title="No connection users" detail="Create users before assigning roles or groups." />;

  return (
    <div className="individual-access">
      <div className="selection-toolbar">
        <label className="inline-filter">Filter users<input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="username, role, or group" /></label>
        <span className="hint">{filtered.length} visible</span>
      </div>
      <div className="table-wrap">
        <table className="access-table individual-access-table">
          <thead>
            <tr><th>User</th><th>Role</th><th>Groups</th><th>Action</th></tr>
          </thead>
          <tbody>
            {filtered.map((user) => {
              const draft = drafts[user.id] || { role_id: user.role_id || '', group_ids: user.group_ids || [] };
              return (
                <tr key={user.id}>
                  <td>
                    <strong>{user.username}</strong>
                    <span>{user.display_name || user.description || 'No description'}</span>
                  </td>
                  <td>
                    <select value={draft.role_id || ''} onChange={(event) => updateDraft(user.id, { role_id: event.target.value })}>
                      <option value="">No role</option>
                      {roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}
                    </select>
                  </td>
                  <td>
                    <div className="group-picks compact">
                      {groups.length ? groups.map((group) => (
                        <label className="check group-chip" key={group.id}>
                          <input type="checkbox" checked={(draft.group_ids || []).includes(group.id)} onChange={() => toggleDraftGroup(user.id, group.id)} />
                          <span className="color-dot" style={{ background: group.color || '#64c18c' }} /> {group.name}
                        </label>
                      )) : <span className="hint">No groups</span>}
                    </div>
                  </td>
                  <td>
                    <button className="btn ghost" type="button" onClick={() => saveUser(user)}><ShieldCheck size={16} />Save</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function GroupLinks({ groups, links, session, load, setStatus }) {
  if (groups.length < 2) return <Empty title="Need at least two groups" detail="Create groups first, then link cross-group access." />;
  const findLink = (sourceId, targetId) => links.find((link) => link.source_group_id === sourceId && link.target_group_id === targetId) || {};
  const pairs = [];
  groups.forEach((source, sourceIndex) => {
    groups.slice(sourceIndex + 1).forEach((target) => pairs.push([source, target]));
  });
  const linkEnabled = (sourceId, targetId) => {
    const link = findLink(sourceId, targetId);
    return Boolean(link.can_see && link.can_send);
  };
  const pairMode = (source, target) => {
    const forward = linkEnabled(source.id, target.id);
    const reverse = linkEnabled(target.id, source.id);
    if (forward && reverse) return 'two-way';
    if (forward) return 'forward';
    if (reverse) return 'reverse';
    return 'none';
  };
  const setDirection = async (sourceId, targetId, enabled) => {
    await api('/api/access-links/set', session, {
      method: 'POST',
      body: JSON.stringify({
        source_group_id: sourceId,
        target_group_id: targetId,
        can_see: enabled,
        can_send: enabled,
      }),
    });
  };
  const setMode = async (source, target, mode) => {
    try {
      await Promise.all([
        setDirection(source.id, target.id, mode === 'forward' || mode === 'two-way'),
        setDirection(target.id, source.id, mode === 'reverse' || mode === 'two-way'),
      ]);
      setStatus(`Updated cross-group access for ${source.name} and ${target.name}.`);
      await load();
    } catch (error) {
      setStatus(`Cross-group access update failed: ${error.message}`);
    }
  };
  return (
    <div className="link-pairs">
      {pairs.map(([source, target]) => {
        const mode = pairMode(source, target);
        return (
          <div className="link-pair-card" key={`${source.id}-${target.id}`}>
            <div className="link-pair-names">
              <strong><span className="color-dot" style={{ background: source.color || '#64c18c' }} />{source.name}</strong>
              <Link2 size={15} />
              <strong><span className="color-dot" style={{ background: target.color || '#64c18c' }} />{target.name}</strong>
            </div>
            <div className="link-mode-buttons">
              <button className={mode === 'none' ? 'link-mode active' : 'link-mode'} type="button" onClick={() => setMode(source, target, 'none')}>No Link</button>
              <button className={mode === 'forward' ? 'link-mode active' : 'link-mode'} type="button" onClick={() => setMode(source, target, 'forward')}>{source.name}{' -> '}{target.name}</button>
              <button className={mode === 'reverse' ? 'link-mode active' : 'link-mode'} type="button" onClick={() => setMode(source, target, 'reverse')}>{target.name}{' -> '}{source.name}</button>
              <button className={mode === 'two-way' ? 'link-mode active' : 'link-mode'} type="button" onClick={() => setMode(source, target, 'two-way')}>Two Way</button>
            </div>
          </div>
        );
      })}
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
            {!compact && <th>Role</th>}
            {!compact && <th>Groups</th>}
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
                {!compact && <td>{user.role_name ? <Badge>{user.role_name}</Badge> : <span className="hint">none</span>}</td>}
                {!compact && (
                  <td>
                    <div className="table-badges">
                      {(user.groups || []).length ? user.groups.map((group) => <Badge key={group.id}>{group.name}</Badge>) : <span className="hint">none</span>}
                    </div>
                  </td>
                )}
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
