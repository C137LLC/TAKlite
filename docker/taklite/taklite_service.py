#!/usr/bin/env python3
import base64
import hashlib
import hmac
import html
import io
import json
import os
import re
import secrets
import shlex
import shutil
import socket
import sqlite3
import ssl
import subprocess
import threading
import time
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from socketserver import ThreadingMixIn, TCPServer, BaseRequestHandler
from urllib.parse import parse_qs, quote, unquote, urlparse
from urllib.request import Request, urlopen

HTTP_BIND = os.environ.get("TAKLITE_HTTP_BIND", "0.0.0.0")
HTTP_PORT = int(os.environ.get("TAKLITE_HTTP_PORT", "8080"))
HTTP_PUBLIC_PORT = int(os.environ.get("TAKLITE_HTTP_PUBLIC_PORT", os.environ.get("TAKLITE_HTTP_HOST_PORT", str(HTTP_PORT))))
HTTPS_BIND = os.environ.get("TAKLITE_HTTPS_BIND", "0.0.0.0")
HTTPS_PORT = int(os.environ.get("TAKLITE_HTTPS_PORT", "8443"))
HTTPS_PUBLIC_PORT = int(os.environ.get("TAKLITE_HTTPS_PUBLIC_PORT", os.environ.get("TAKLITE_HTTPS_HOST_PORT", str(HTTPS_PORT))))
HTTPS_CERT = Path(os.environ.get("TAKLITE_HTTPS_CERT", "/certs/taklite.crt"))
HTTPS_KEY = Path(os.environ.get("TAKLITE_HTTPS_KEY", "/certs/taklite.key"))
CERT_DIR = HTTPS_CERT.parent
CLIENT_CA = Path(os.environ.get("TAKLITE_CLIENT_CA", "/certs/taklite-ca.crt"))
AUTO_INIT_CERTS = os.environ.get("TAKLITE_AUTO_INIT_CERTS", "false").lower() in ("1", "true", "yes", "on")
COT_BIND = os.environ.get("TAKLITE_COT_BIND", "0.0.0.0")
COT_PORT = int(os.environ.get("TAKLITE_COT_PORT", "58087"))
COT_PUBLIC_PORT = int(os.environ.get("TAKLITE_COT_PUBLIC_PORT", os.environ.get("TAKLITE_COT_HOST_PORT", str(COT_PORT))))
COT_TLS_BIND = os.environ.get("TAKLITE_COT_TLS_BIND", "0.0.0.0")
COT_TLS_PORT = int(os.environ.get("TAKLITE_COT_TLS_PORT", "8089"))
COT_TLS_PUBLIC_PORT = int(os.environ.get("TAKLITE_COT_TLS_PUBLIC_PORT", os.environ.get("TAKLITE_COT_TLS_HOST_PORT", str(COT_TLS_PORT))))
ADMIN_TOKEN = os.environ.get("TAKLITE_ADMIN_TOKEN", "")
PUBLIC_HOST = os.environ.get("TAKLITE_PUBLIC_HOST", "")
SERVER_HOST = os.environ.get("TAKLITE_SERVER_HOST", PUBLIC_HOST or "10.66.66.1")
CERT_PASSWORD = os.environ.get("TAKLITE_CERT_PASSWORD", "")
DB_PATH = Path(os.environ.get("TAKLITE_DB", "/data/taklite.sqlite3"))
PACKAGE_DIR = Path(os.environ.get("TAKLITE_PACKAGE_DIR", "/packages"))
STATIC_DIR = Path(os.environ.get("TAKLITE_STATIC_DIR", "/app/static"))
WG_DASHBOARD_URL = os.environ.get("TAKLITE_WGDASHBOARD_URL", "")
VERSION = "TAKlite 0.2.19"
STARTED_AT = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
PORTAL_SESSION_HOURS = 2
MAX_UPLOAD_BYTES = int(os.environ.get("TAKLITE_MAX_UPLOAD_BYTES", str(256 * 1024 * 1024)))
MAX_ZIP_ENTRIES = int(os.environ.get("TAKLITE_MAX_ZIP_ENTRIES", "1000"))
MAX_ZIP_UNCOMPRESSED_BYTES = int(os.environ.get("TAKLITE_MAX_ZIP_UNCOMPRESSED_BYTES", str(512 * 1024 * 1024)))
MAX_ZIP_COMPRESSION_RATIO = int(os.environ.get("TAKLITE_MAX_ZIP_COMPRESSION_RATIO", "100"))
MAX_JSON_BYTES = int(os.environ.get("TAKLITE_MAX_JSON_BYTES", str(256 * 1024)))
COT_MAX_BUFFER_BYTES = int(os.environ.get("TAKLITE_COT_MAX_BUFFER_BYTES", str(1024 * 1024)))
EVENT_RETENTION_ROWS = int(os.environ.get("TAKLITE_EVENT_RETENTION_ROWS", "50000"))
COT_TLS_REQUIRE_CLIENT_CERT = os.environ.get("TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT", "true").lower() in ("1", "true", "yes", "on")
ALLOW_LEGACY_CLIENT_CERT = os.environ.get("TAKLITE_ALLOW_LEGACY_CLIENT_CERT", "false").lower() in ("1", "true", "yes", "on")
ACCESS_CONTROL_ENFORCE = os.environ.get("TAKLITE_ACCESS_CONTROL_ENFORCE", "true").lower() in ("1", "true", "yes", "on")
LEGACY_CERT_DOWNLOADS = os.environ.get("TAKLITE_LEGACY_CERT_DOWNLOADS", "false").lower() in ("1", "true", "yes", "on")
LOGIN_LIMIT_ATTEMPTS = int(os.environ.get("TAKLITE_LOGIN_LIMIT_ATTEMPTS", "8"))
LOGIN_LIMIT_WINDOW_SECONDS = int(os.environ.get("TAKLITE_LOGIN_LIMIT_WINDOW_SECONDS", "300"))
MAX_BULK_USERS = int(os.environ.get("TAKLITE_MAX_BULK_USERS", "100"))
SOCKET_SEND_TIMEOUT_SECONDS = float(os.environ.get("TAKLITE_SOCKET_SEND_TIMEOUT_SECONDS", "2.5"))
GUI_UPDATE_ENABLED = os.environ.get("TAKLITE_GUI_UPDATE_ENABLED", "false").lower() in ("1", "true", "yes", "on")
GUI_UPDATE_COMMAND = os.environ.get("TAKLITE_GUI_UPDATE_COMMAND", "")
GUI_UPDATE_WORKDIR = os.environ.get("TAKLITE_GUI_UPDATE_WORKDIR", "")
GUI_UPDATE_TIMEOUT_SECONDS = int(os.environ.get("TAKLITE_GUI_UPDATE_TIMEOUT_SECONDS", "900"))
GUI_UPDATE_REQUEST_DIR = os.environ.get("TAKLITE_GUI_UPDATE_REQUEST_DIR", "")
SETTINGS_REQUEST_DIR = os.environ.get("TAKLITE_SETTINGS_REQUEST_DIR", "")
FIREWALL_REQUEST_DIR = os.environ.get("TAKLITE_FIREWALL_REQUEST_DIR", "")
WG_INTERFACE = os.environ.get("TAKLITE_WG_INTERFACE", "wg0")
PUBLIC_INTERFACE = os.environ.get("TAKLITE_PUBLIC_INTERFACE", "")
WIREGUARD_PORT = int(os.environ.get("TAKLITE_WIREGUARD_PORT", "51820"))
WGDASHBOARD_PORT = int(os.environ.get("TAKLITE_WGDASHBOARD_PORT", "10086"))
RELEASES_URL = "https://github.com/C137LLC/TAKlite/releases"
LATEST_RELEASE_API_URL = "https://api.github.com/repos/C137LLC/TAKlite/releases/latest"
UPDATE_STATUS_CACHE = {"checked_at": 0, "status": None}
UPDATE_STATUS_CACHE_SECONDS = 300
FIREWALL_SERVICES = {
    "ssh": {"label": "SSH", "protocol": "tcp", "port": 22, "lockout_sensitive": True},
    "wireguard": {"label": "WireGuard", "protocol": "udp", "port": WIREGUARD_PORT, "lockout_sensitive": True},
    "wg_dashboard": {"label": "WG Dashboard", "protocol": "tcp", "port": WGDASHBOARD_PORT},
    "taklite_admin": {"label": "TAKlite Admin", "protocol": "tcp", "port": HTTP_PUBLIC_PORT},
    "tak_https": {"label": "TAK HTTPS/Marti", "protocol": "tcp", "port": HTTPS_PUBLIC_PORT},
    "cot_tcp": {"label": "CoT TCP", "protocol": "tcp", "port": COT_PUBLIC_PORT},
    "cot_tls": {"label": "TLS CoT", "protocol": "tcp", "port": COT_TLS_PUBLIC_PORT},
}
FIREWALL_STATES = {"public", "vpn", "closed"}

EVENT_END = b"</event>"
EVENT_RE = re.compile(rb"<event\b.*?</event>", re.DOTALL)
UID_RE = re.compile(rb'\buid="([^"]+)"')
CALLSIGN_RE = re.compile(rb'<contact\b[^>]*\bcallsign="([^"]+)"')
EVENT_SAVE_COUNT = 0
LOGIN_FAILURES = {}
LOGIN_LOCK = threading.Lock()
BULK_PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
BULK_PORTAL_PASSWORD = "atakatak"


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def version_tuple(value):
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", value or "")
    if not match:
        return ()
    return tuple(int(part) for part in match.groups())


def version_tag(value):
    parts = version_tuple(value)
    return f"v{'.'.join(str(part) for part in parts)}" if parts else ""


def ensure_dirs():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=15, factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    conn.execute("pragma journal_mode = wal")
    conn.execute("pragma synchronous = normal")
    return conn


def init_db():
    ensure_dirs()
    with db_connect() as conn:
        conn.execute("""
            create table if not exists datapackages (
                PrimaryKey integer primary key autoincrement,
                UID text not null,
                Name text not null,
                Hash text not null unique,
                SubmissionDateTime text not null,
                SubmissionUser text,
                CreatorUid text,
                Keywords text,
                MIMEType text,
                Size integer not null default 0,
                Path text not null,
                Tool text not null default 'public'
            )
        """)
        conn.execute("""
            create table if not exists events (
                id integer primary key autoincrement,
                uid text,
                callsign text,
                received_at text not null,
                remote text,
                cot text not null
            )
        """)
        conn.execute("""
            create table if not exists admins (
                username text primary key,
                password_hash text not null,
                created_at text not null,
                totp_secret text,
                totp_enabled integer not null default 0
            )
        """)
        conn.execute("""
            create table if not exists admin_sessions (
                token text primary key,
                username text not null,
                created_at text not null,
                expires_at text not null
            )
        """)
        conn.execute("""
            create table if not exists cert_profiles (
                id integer primary key autoincrement,
                name text not null unique,
                description text,
                download_token text unique,
                connect_string text not null,
                truststore_file text not null,
                client_cert_file text not null,
                datapackage_file text not null,
                created_at text not null,
                revoked_at text
            )
        """)
        conn.execute("""
            create table if not exists portal_users (
                id integer primary key autoincrement,
                username text not null unique,
                password_hash text not null,
                display_name text,
                description text,
                cert_profile_id integer not null,
                allow_redownload integer not null default 0,
                first_download_at text,
                last_download_at text,
                download_count integer not null default 0,
                created_at text not null,
                revoked_at text,
                foreign key(cert_profile_id) references cert_profiles(id)
            )
        """)
        conn.execute("""
            create table if not exists access_roles (
                id integer primary key autoincrement,
                name text not null unique,
                description text,
                can_see_all integer not null default 0,
                can_send_all integer not null default 0,
                can_see_own_groups integer not null default 1,
                can_send_own_groups integer not null default 1,
                created_at text not null
            )
        """)
        conn.execute("""
            create table if not exists access_groups (
                id integer primary key autoincrement,
                name text not null unique,
                description text,
                color text,
                created_at text not null
            )
        """)
        conn.execute("""
            create table if not exists access_user_groups (
                user_id integer not null,
                group_id integer not null,
                primary key(user_id, group_id),
                foreign key(user_id) references portal_users(id) on delete cascade,
                foreign key(group_id) references access_groups(id) on delete cascade
            )
        """)
        conn.execute("""
            create table if not exists access_policy_links (
                source_group_id integer not null,
                target_group_id integer not null,
                can_see integer not null default 0,
                can_send integer not null default 0,
                primary key(source_group_id, target_group_id),
                foreign key(source_group_id) references access_groups(id) on delete cascade,
                foreign key(target_group_id) references access_groups(id) on delete cascade
            )
        """)
        conn.execute("""
            create table if not exists portal_sessions (
                token text primary key,
                user_id integer not null,
                created_at text not null,
                expires_at text not null,
                foreign key(user_id) references portal_users(id)
            )
        """)
        columns = {row["name"] for row in conn.execute("pragma table_info(cert_profiles)").fetchall()}
        if "download_token" not in columns:
            conn.execute("alter table cert_profiles add column download_token text")
        for row in conn.execute("select id from cert_profiles where download_token is null or download_token = ''").fetchall():
            conn.execute("update cert_profiles set download_token = ? where id = ?", (secrets.token_urlsafe(18), row["id"]))
        portal_columns = {row["name"] for row in conn.execute("pragma table_info(portal_users)").fetchall()}
        if "role_id" not in portal_columns:
            conn.execute("alter table portal_users add column role_id integer")
        admin_columns = {row["name"] for row in conn.execute("pragma table_info(admins)").fetchall()}
        if "totp_secret" not in admin_columns:
            conn.execute("alter table admins add column totp_secret text")
        if "totp_enabled" not in admin_columns:
            conn.execute("alter table admins add column totp_enabled integer not null default 0")
        package_columns = {row["name"] for row in conn.execute("pragma table_info(datapackages)").fetchall()}
        if "CreatorUserId" not in package_columns:
            conn.execute("alter table datapackages add column CreatorUserId integer")
        if "Visibility" not in package_columns:
            conn.execute("alter table datapackages add column Visibility text not null default 'private'")
        conn.execute("create index if not exists idx_events_uid on events(uid)")
        conn.execute("create index if not exists idx_events_received_at on events(received_at)")
        conn.execute("create index if not exists idx_datapackages_hash on datapackages(Hash)")
        conn.execute("create index if not exists idx_portal_users_profile on portal_users(cert_profile_id)")
        conn.execute("create index if not exists idx_access_user_groups_user on access_user_groups(user_id)")
        conn.execute("create index if not exists idx_access_user_groups_group on access_user_groups(group_id)")
        conn.commit()


def package_path(hash_value, filename):
    safe_hash = re.sub(r"[^A-Za-z0-9_.-]", "_", hash_value or uuid.uuid4().hex)
    suffix = Path(filename or "package.dp.zip").suffix or ".zip"
    return PACKAGE_DIR / f"{safe_hash}{suffix}"


def safe_download_name(filename, fallback="download.bin"):
    name = Path(filename or fallback).name
    name = re.sub(r"[^A-Za-z0-9_.() -]+", "_", name).strip(" .")
    return name[:160] or fallback


def normalize_datapackage_name(filename, fallback="datapackage.zip"):
    name = safe_download_name(unquote(filename or ""), fallback)
    if not name.lower().endswith((".zip", ".dp.zip")):
        name = f"{name}.zip"
    return name


def marti_timestamp(value):
    try:
        parsed = parse_utc(value)
    except Exception:
        parsed = None
    if not parsed:
        return value or utc_now().replace("Z", ".000Z")
    parsed = parsed.astimezone(timezone.utc)
    return parsed.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def row_to_package(row):
    return {
        "PrimaryKey": row["PrimaryKey"],
        "UID": row["UID"],
        "Name": row["Name"],
        "Hash": row["Hash"],
        "SubmissionDateTime": marti_timestamp(row["SubmissionDateTime"]),
        "SubmissionUser": row["SubmissionUser"] or "",
        "CreatorUid": row["CreatorUid"] or "",
        "Keywords": row["Keywords"] or "missionpackage",
        "MIMEType": row["MIMEType"] or "application/x-zip-compressed",
        "Size": row["Size"],
        "Tool": row["Tool"] or "public",
        "CreatorUserId": row["CreatorUserId"] if "CreatorUserId" in row.keys() else None,
        "Visibility": row["Visibility"] if "Visibility" in row.keys() else "private",
    }


def list_packages(user_id=None, enforce=None):
    with db_connect() as conn:
        rows = conn.execute(
            "select * from datapackages order by PrimaryKey desc"
        ).fetchall()
    packages = [row_to_package(row) for row in rows]
    if enforce is None:
        enforce = ACCESS_CONTROL_ENFORCE
    if not enforce:
        return packages
    return [package for package in packages if package_visible_to_user(package, user_id, enforce=True)]


def find_package(hash_value):
    with db_connect() as conn:
        return conn.execute(
            "select * from datapackages where Hash = ?", (hash_value,)
        ).fetchone()


def upsert_package(hash_value, filename, creator_uid, data, host_url, creator_user_id=None, visibility="private"):
    actual_hash = hashlib.sha256(data).hexdigest()
    hash_value = hash_value or actual_hash
    filename = filename or f"{hash_value}.dp.zip"
    path = package_path(hash_value, filename)
    path.write_bytes(data)
    now = utc_now()
    uid = str(uuid.uuid4())
    with db_connect() as conn:
        existing = conn.execute(
            "select UID from datapackages where Hash = ?", (hash_value,)
        ).fetchone()
        if existing:
            uid = existing["UID"]
        conn.execute("""
            insert into datapackages
                (UID, Name, Hash, SubmissionDateTime, SubmissionUser, CreatorUid, Keywords, MIMEType, Size, Path, Tool, CreatorUserId, Visibility)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, coalesce((select Tool from datapackages where Hash = ?), ?), ?, ?)
            on conflict(Hash) do update set
                Name=excluded.Name,
                SubmissionDateTime=excluded.SubmissionDateTime,
                CreatorUid=excluded.CreatorUid,
                Keywords=excluded.Keywords,
                MIMEType=excluded.MIMEType,
                Size=excluded.Size,
                Path=excluded.Path,
                CreatorUserId=coalesce(excluded.CreatorUserId, CreatorUserId),
                Visibility=excluded.Visibility
        """, (
            uid, filename, hash_value, now, creator_uid or "", creator_uid or "",
            "missionpackage", "application/x-zip-compressed", len(data), str(path), hash_value, visibility or "private", creator_user_id, visibility or "private",
        ))
        conn.commit()
    return f"{host_url}/Marti/sync/content?hash={quote(hash_value)}"


def tak_marti_base_url():
    host = PUBLIC_HOST or SERVER_HOST
    if HTTPS_CERT.exists() and HTTPS_KEY.exists():
        return f"https://{host}:{HTTPS_PUBLIC_PORT}"
    return f"http://{host}:{HTTP_PUBLIC_PORT}"


def tak_marti_content_url(hash_value):
    return f"{tak_marti_base_url()}/Marti/sync/content?hash={quote(hash_value)}"


def delete_package(hash_value, delete_file=True):
    row = find_package(hash_value)
    if not row:
        return {"deleted_rows": 0, "deleted_files": []}
    deleted_files = []
    path = Path(row["Path"])
    with db_connect() as conn:
        conn.execute("delete from datapackages where Hash = ?", (hash_value,))
        conn.commit()
    if delete_file and path.exists() and path.resolve().is_relative_to(PACKAGE_DIR.resolve()):
        path.unlink()
        deleted_files.append(str(path))
    return {"deleted_rows": 1, "deleted_files": deleted_files}


def prune_events_if_needed(conn):
    global EVENT_SAVE_COUNT
    if EVENT_RETENTION_ROWS <= 0:
        return
    EVENT_SAVE_COUNT += 1
    if EVENT_SAVE_COUNT % 100:
        return
    conn.execute("""
        delete from events
        where id not in (
            select id from events order by id desc limit ?
        )
    """, (EVENT_RETENTION_ROWS,))


def save_event(data, remote, user_id=None):
    uid = decode_match(UID_RE.search(data))
    callsign = decode_match(CALLSIGN_RE.search(data))
    try:
        cot = data.decode("utf-8", "replace")
    except Exception:
        cot = repr(data)
    with db_connect() as conn:
        conn.execute(
            "insert into events (uid, callsign, received_at, remote, cot) values (?, ?, ?, ?, ?)",
            (uid, callsign, utc_now(), remote, cot),
        )
        prune_events_if_needed(conn)
        conn.commit()
    if uid or callsign:
        RELAY.update_client(remote, uid, callsign)
    if uid:
        RELAY.remember_event(uid, data, user_id)


def decode_match(match):
    if not match:
        return ""
    return match.group(1).decode("utf-8", "replace")


def cert_common_name(peer_cert):
    for part in peer_cert.get("subject", ()):
        for key, value in part:
            if key == "commonName":
                return value
    return ""


def parse_utc(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def cot_time(delta_seconds=0):
    value = datetime.now(timezone.utc) + timedelta(seconds=delta_seconds)
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def server_status_event():
    return (
        f'<event version="2.0" uid="taklite-server" type="t-x-c-t" '
        f'time="{cot_time()}" start="{cot_time()}" stale="{cot_time(30)}" how="m-g">'
        '<point lat="0.0" lon="0.0" hae="9999999.0" ce="9999999.0" le="9999999.0"/>'
        '<detail><contact callsign="TAKlite"/><remarks>TAKlite keepalive</remarks></detail>'
        '</event>'
    ).encode("utf-8")


def fileshare_event(package):
    name = safe_download_name(package["Name"], "datapackage.zip")
    hash_value = package["Hash"]
    size = int(package["Size"] or 0)
    event_uid = f"taklite-fileshare-{uuid.uuid4()}"
    ack_uid = str(uuid.uuid4())
    sender_url = tak_marti_content_url(hash_value)
    return (
        f'<event version="2.0" uid="{html.escape(event_uid)}" type="b-f-t-r" '
        f'time="{cot_time()}" start="{cot_time()}" stale="{cot_time(600)}" how="h-e">'
        '<point lat="0.0" lon="0.0" hae="9999999.0" ce="9999999.0" le="9999999.0"/>'
        '<detail>'
        f'<fileshare filename="{html.escape(name)}" name="{html.escape(name)}" '
        f'senderUrl="{html.escape(sender_url)}" sizeInBytes="{size}" '
        f'sha256="{html.escape(hash_value)}" senderUid="taklite-server" senderCallsign="TAKlite Admin"/>'
        f'<ackrequest uid="{html.escape(ack_uid)}" ackrequested="true" tag="{html.escape(name)}"/>'
        '</detail></event>'
    ).encode("utf-8")


def password_hash(password):
    salt = secrets.token_bytes(16)
    iterations = 220000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    try:
        alg, iterations, salt_hex, digest_hex = stored.split("$", 3)
        if alg != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def new_totp_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def decode_totp_secret(secret):
    normalized = re.sub(r"\s+", "", secret or "").upper()
    normalized += "=" * ((8 - len(normalized) % 8) % 8)
    return base64.b32decode(normalized, casefold=True)


def totp_code(secret, for_time=None, step=30, digits=6):
    timestamp = time.time() if for_time is None else float(for_time)
    counter = int(timestamp // step)
    digest = hmac.new(decode_totp_secret(secret), counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF
    return str(value % (10 ** digits)).zfill(digits)


def verify_totp_code(secret, code, for_time=None, window=1):
    candidate = re.sub(r"\s+", "", code or "")
    if not re.fullmatch(r"\d{6}", candidate):
        return False
    timestamp = time.time() if for_time is None else float(for_time)
    for drift in range(-window, window + 1):
        expected = totp_code(secret, timestamp + drift * 30)
        if hmac.compare_digest(expected, candidate):
            return True
    return False


def rate_limit_key(scope, remote, username):
    return f"{scope}:{remote}:{(username or '').strip().lower()}"


def login_limited(scope, remote, username):
    now = time.time()
    key = rate_limit_key(scope, remote, username)
    with LOGIN_LOCK:
        attempts = [seen for seen in LOGIN_FAILURES.get(key, []) if now - seen < LOGIN_LIMIT_WINDOW_SECONDS]
        LOGIN_FAILURES[key] = attempts
        return len(attempts) >= LOGIN_LIMIT_ATTEMPTS


def record_login_failure(scope, remote, username):
    now = time.time()
    key = rate_limit_key(scope, remote, username)
    with LOGIN_LOCK:
        attempts = [seen for seen in LOGIN_FAILURES.get(key, []) if now - seen < LOGIN_LIMIT_WINDOW_SECONDS]
        attempts.append(now)
        LOGIN_FAILURES[key] = attempts
    safe_scope = re.sub(r"[^A-Za-z0-9_.:-]", "_", scope or "unknown")
    safe_remote = re.sub(r"[^A-Za-z0-9_.:-]", "_", remote or "unknown")
    safe_user = re.sub(r"[^A-Za-z0-9_.@-]", "_", username or "unknown")
    print(f"TAKlite auth failure scope={safe_scope} remote={safe_remote} username={safe_user} attempts={len(attempts)}", flush=True)


def clear_login_failures(scope, remote, username):
    key = rate_limit_key(scope, remote, username)
    with LOGIN_LOCK:
        LOGIN_FAILURES.pop(key, None)


def admin_count():
    with db_connect() as conn:
        return int(conn.execute("select count(*) from admins").fetchone()[0])


def create_admin(username, password):
    username = (username or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.@-]{3,64}", username):
        raise ValueError("username must be 3-64 characters: letters, numbers, dot, underscore, dash, or @")
    if len(password or "") < 10:
        raise ValueError("password must be at least 10 characters")
    with db_connect() as conn:
        conn.execute(
            "insert into admins (username, password_hash, created_at) values (?, ?, ?)",
            (username, password_hash(password), utc_now()),
        )
        conn.commit()
    return username


def admin_totp_status(username):
    with db_connect() as conn:
        row = conn.execute("select totp_enabled, totp_secret from admins where username = ?", ((username or "").strip(),)).fetchone()
    if not row:
        raise ValueError("admin user not found")
    return {"username": (username or "").strip(), "totp_enabled": bool(row["totp_enabled"]), "totp_configured": bool(row["totp_secret"])}


def create_admin_totp_setup(username, current_password):
    username = (username or "").strip()
    if authenticate_admin(username, current_password, allow_missing_totp=True) != username:
        raise PermissionError("current password is incorrect")
    secret = new_totp_secret()
    issuer = quote("TAKlite")
    label = quote(f"TAKlite:{username}")
    uri = f"otpauth://totp/{label}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"
    with db_connect() as conn:
        conn.execute("update admins set totp_secret = ?, totp_enabled = 0 where username = ?", (secret, username))
        conn.commit()
    return {"username": username, "secret": secret, "otpauth_uri": uri, "totp_enabled": False}


def enable_admin_totp(username, current_password, code, for_time=None, current_token=""):
    username = (username or "").strip()
    if authenticate_admin(username, current_password, allow_missing_totp=True) != username:
        raise PermissionError("current password is incorrect")
    with db_connect() as conn:
        row = conn.execute("select totp_secret from admins where username = ?", (username,)).fetchone()
        if not row or not row["totp_secret"]:
            raise ValueError("two-factor setup has not been started")
        if not verify_totp_code(row["totp_secret"], code, for_time=for_time):
            raise PermissionError("two-factor code is incorrect")
        conn.execute("update admins set totp_enabled = 1 where username = ?", (username,))
        if current_token:
            conn.execute("delete from admin_sessions where username = ? and token != ?", (username, current_token))
        else:
            conn.execute("delete from admin_sessions where username = ?", (username,))
        conn.commit()
    return admin_totp_status(username)


def disable_admin_totp(username, current_password, code, for_time=None, current_token=""):
    username = (username or "").strip()
    if authenticate_admin(username, current_password, code, for_time=for_time) != username:
        raise PermissionError("current password or two-factor code is incorrect")
    with db_connect() as conn:
        conn.execute("update admins set totp_secret = null, totp_enabled = 0 where username = ?", (username,))
        if current_token:
            conn.execute("delete from admin_sessions where username = ? and token != ?", (username, current_token))
        else:
            conn.execute("delete from admin_sessions where username = ?", (username,))
        conn.commit()
    return admin_totp_status(username)


def create_session(username):
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=12)
    with db_connect() as conn:
        conn.execute(
            "insert into admin_sessions (token, username, created_at, expires_at) values (?, ?, ?, ?)",
            (token, username, now.replace(microsecond=0).isoformat().replace("+00:00", "Z"), expires.replace(microsecond=0).isoformat().replace("+00:00", "Z")),
        )
        conn.commit()
    return token


def validate_session(token):
    if not token:
        return ""
    with db_connect() as conn:
        row = conn.execute("select username, expires_at from admin_sessions where token = ?", (token,)).fetchone()
        if not row:
            return ""
        expires = parse_utc(row["expires_at"])
        if not expires or expires <= datetime.now(timezone.utc):
            conn.execute("delete from admin_sessions where token = ?", (token,))
            conn.commit()
            return ""
        return row["username"]


def authenticate_admin(username, password, totp_value="", for_time=None, allow_missing_totp=False):
    with db_connect() as conn:
        row = conn.execute("select password_hash, totp_secret, totp_enabled from admins where username = ?", ((username or "").strip(),)).fetchone()
    if not row or not verify_password(password or "", row["password_hash"]):
        return ""
    if row["totp_enabled"] and not allow_missing_totp:
        if not row["totp_secret"] or not verify_totp_code(row["totp_secret"], totp_value, for_time=for_time):
            return ""
    return (username or "").strip()


def admin_requires_totp(username, password):
    with db_connect() as conn:
        row = conn.execute("select password_hash, totp_enabled from admins where username = ?", ((username or "").strip(),)).fetchone()
    return bool(row and row["totp_enabled"] and verify_password(password or "", row["password_hash"]))


def change_admin_password(username, current_password, new_password, keep_session_token=""):
    username = (username or "").strip()
    if len(new_password or "") < 10:
        raise ValueError("new password must be at least 10 characters")
    with db_connect() as conn:
        row = conn.execute("select password_hash from admins where username = ?", (username,)).fetchone()
        if not row or not verify_password(current_password or "", row["password_hash"]):
            raise PermissionError("current password is incorrect")
        conn.execute("update admins set password_hash = ? where username = ?", (password_hash(new_password), username))
        if keep_session_token:
            conn.execute("delete from admin_sessions where username = ? and token != ?", (username, keep_session_token))
        else:
            conn.execute("delete from admin_sessions where username = ?", (username,))
        conn.commit()
    clear_login_failures("admin", "", username)
    return True


def validate_portal_username(username):
    username = (username or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.@-]{3,64}", username):
        raise ValueError("portal username must be 3-64 characters: letters, numbers, dot, underscore, dash, or @")
    return username


def validate_access_name(name, label="name"):
    name = (name or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@() -]{0,63}", name):
        raise ValueError(f"{label} must be 1-64 characters and start with a letter or number")
    return name


def row_to_role(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"] or "",
        "can_see_all": bool(row["can_see_all"]),
        "can_send_all": bool(row["can_send_all"]),
        "can_see_own_groups": bool(row["can_see_own_groups"]),
        "can_send_own_groups": bool(row["can_send_own_groups"]),
        "created_at": row["created_at"],
    }


def row_to_group(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"] or "",
        "color": row["color"] or "",
        "created_at": row["created_at"],
    }


def row_to_policy_link(row):
    return {
        "source_group_id": row["source_group_id"],
        "target_group_id": row["target_group_id"],
        "can_see": bool(row["can_see"]),
        "can_send": bool(row["can_send"]),
    }


def create_access_role(name, description="", can_see_all=False, can_send_all=False, can_see_own_groups=True, can_send_own_groups=True):
    name = validate_access_name(name, "role name")
    with db_connect() as conn:
        conn.execute("""
            insert into access_roles
              (name, description, can_see_all, can_send_all, can_see_own_groups, can_send_own_groups, created_at)
            values (?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            (description or "").strip(),
            1 if can_see_all else 0,
            1 if can_send_all else 0,
            1 if can_see_own_groups else 0,
            1 if can_send_own_groups else 0,
            utc_now(),
        ))
        conn.commit()
        row = conn.execute("select * from access_roles where name = ?", (name,)).fetchone()
    return row_to_role(row)


def update_access_role(role_id, name, description="", can_see_all=False, can_send_all=False, can_see_own_groups=True, can_send_own_groups=True):
    name = validate_access_name(name, "role name")
    with db_connect() as conn:
        conn.execute("""
            update access_roles
            set name = ?, description = ?, can_see_all = ?, can_send_all = ?, can_see_own_groups = ?, can_send_own_groups = ?
            where id = ?
        """, (
            name,
            (description or "").strip(),
            1 if can_see_all else 0,
            1 if can_send_all else 0,
            1 if can_see_own_groups else 0,
            1 if can_send_own_groups else 0,
            role_id,
        ))
        conn.commit()
        row = conn.execute("select * from access_roles where id = ?", (role_id,)).fetchone()
    if not row:
        raise ValueError("role not found")
    return row_to_role(row)


def delete_access_role(role_id):
    with db_connect() as conn:
        conn.execute("update portal_users set role_id = null where role_id = ?", (role_id,))
        deleted = conn.execute("delete from access_roles where id = ?", (role_id,)).rowcount
        conn.commit()
    return {"deleted_rows": deleted}


def create_access_group(name, description="", color=""):
    name = validate_access_name(name, "group name")
    color = (color or "").strip()
    if color and not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        raise ValueError("group color must be a hex color like #64c18c")
    with db_connect() as conn:
        conn.execute("""
            insert into access_groups (name, description, color, created_at)
            values (?, ?, ?, ?)
        """, (name, (description or "").strip(), color, utc_now()))
        conn.commit()
        row = conn.execute("select * from access_groups where name = ?", (name,)).fetchone()
    return row_to_group(row)


def update_access_group(group_id, name, description="", color=""):
    name = validate_access_name(name, "group name")
    color = (color or "").strip()
    if color and not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        raise ValueError("group color must be a hex color like #64c18c")
    with db_connect() as conn:
        conn.execute("update access_groups set name = ?, description = ?, color = ? where id = ?", (name, (description or "").strip(), color, group_id))
        conn.commit()
        row = conn.execute("select * from access_groups where id = ?", (group_id,)).fetchone()
    if not row:
        raise ValueError("group not found")
    return row_to_group(row)


def delete_access_group(group_id):
    with db_connect() as conn:
        conn.execute("delete from access_user_groups where group_id = ?", (group_id,))
        conn.execute("delete from access_policy_links where source_group_id = ? or target_group_id = ?", (group_id, group_id))
        deleted = conn.execute("delete from access_groups where id = ?", (group_id,)).rowcount
        conn.commit()
    return {"deleted_rows": deleted}


def list_access_roles():
    with db_connect() as conn:
        rows = conn.execute("select * from access_roles order by lower(name)").fetchall()
    return [row_to_role(row) for row in rows]


def list_access_groups():
    with db_connect() as conn:
        rows = conn.execute("select * from access_groups order by lower(name)").fetchall()
    return [row_to_group(row) for row in rows]


def list_policy_links():
    with db_connect() as conn:
        rows = conn.execute("select * from access_policy_links order by source_group_id, target_group_id").fetchall()
    return [row_to_policy_link(row) for row in rows]


def set_user_access(user_id, role_id=None, group_ids=None):
    group_ids = [int(value) for value in (group_ids or []) if str(value).strip()]
    role_id = int(role_id or 0) or None
    with db_connect() as conn:
        if role_id and not conn.execute("select id from access_roles where id = ?", (role_id,)).fetchone():
            raise ValueError("role not found")
        if group_ids:
            placeholders = ",".join("?" for _ in group_ids)
            found = {row["id"] for row in conn.execute(f"select id from access_groups where id in ({placeholders})", group_ids).fetchall()}
            missing = sorted(set(group_ids) - found)
            if missing:
                raise ValueError(f"group not found: {missing[0]}")
        if not conn.execute("select id from portal_users where id = ?", (user_id,)).fetchone():
            raise ValueError("user not found")
        conn.execute("update portal_users set role_id = ? where id = ?", (role_id, user_id))
        conn.execute("delete from access_user_groups where user_id = ?", (user_id,))
        conn.executemany("insert into access_user_groups (user_id, group_id) values (?, ?)", [(user_id, gid) for gid in group_ids])
        conn.commit()
    return attach_access_to_users([portal_user_row(find_portal_user(user_id))])[0]


def bulk_set_user_access(user_ids, role_id=None, group_ids=None, group_mode="replace"):
    user_ids = sorted({int(value) for value in (user_ids or []) if str(value).strip()})
    if not user_ids:
        raise ValueError("select at least one user")
    group_ids = [int(value) for value in (group_ids or []) if str(value).strip()]
    group_mode = (group_mode or "replace").strip().lower()
    if group_mode not in ("replace", "add", "remove"):
        raise ValueError("group mode must be replace, add, or remove")
    role_id = int(role_id or 0) or None
    with db_connect() as conn:
        placeholders = ",".join("?" for _ in user_ids)
        found_users = {row["id"] for row in conn.execute(f"select id from portal_users where id in ({placeholders})", user_ids).fetchall()}
        missing_users = sorted(set(user_ids) - found_users)
        if missing_users:
            raise ValueError(f"user not found: {missing_users[0]}")
        if role_id and not conn.execute("select id from access_roles where id = ?", (role_id,)).fetchone():
            raise ValueError("role not found")
        if group_ids:
            group_placeholders = ",".join("?" for _ in group_ids)
            found_groups = {row["id"] for row in conn.execute(f"select id from access_groups where id in ({group_placeholders})", group_ids).fetchall()}
            missing_groups = sorted(set(group_ids) - found_groups)
            if missing_groups:
                raise ValueError(f"group not found: {missing_groups[0]}")
        if role_id is not None:
            conn.executemany("update portal_users set role_id = ? where id = ?", [(role_id, user_id) for user_id in user_ids])
        if group_mode == "replace":
            conn.executemany("delete from access_user_groups where user_id = ?", [(user_id,) for user_id in user_ids])
            conn.executemany(
                "insert into access_user_groups (user_id, group_id) values (?, ?)",
                [(user_id, gid) for user_id in user_ids for gid in group_ids],
            )
        elif group_mode == "add" and group_ids:
            conn.executemany(
                "insert or ignore into access_user_groups (user_id, group_id) values (?, ?)",
                [(user_id, gid) for user_id in user_ids for gid in group_ids],
            )
        elif group_mode == "remove" and group_ids:
            conn.executemany(
                "delete from access_user_groups where user_id = ? and group_id = ?",
                [(user_id, gid) for user_id in user_ids for gid in group_ids],
            )
        conn.commit()
    return {"ok": True, "updated": len(user_ids)}


def set_policy_link(source_group_id, target_group_id, can_see=False, can_send=False):
    source_group_id = int(source_group_id)
    target_group_id = int(target_group_id)
    with db_connect() as conn:
        for gid in (source_group_id, target_group_id):
            if not conn.execute("select id from access_groups where id = ?", (gid,)).fetchone():
                raise ValueError("group not found")
        if can_see or can_send:
            conn.execute("""
                insert into access_policy_links (source_group_id, target_group_id, can_see, can_send)
                values (?, ?, ?, ?)
                on conflict(source_group_id, target_group_id) do update set
                    can_see = excluded.can_see,
                    can_send = excluded.can_send
            """, (source_group_id, target_group_id, 1 if can_see else 0, 1 if can_send else 0))
        else:
            conn.execute("delete from access_policy_links where source_group_id = ? and target_group_id = ?", (source_group_id, target_group_id))
        conn.commit()
        row = conn.execute("select * from access_policy_links where source_group_id = ? and target_group_id = ?", (source_group_id, target_group_id)).fetchone()
    return row_to_policy_link(row) if row else {"source_group_id": source_group_id, "target_group_id": target_group_id, "can_see": False, "can_send": False}


def access_policy_active():
    with db_connect() as conn:
        row = conn.execute("""
            select
              (select count(*) from portal_users where role_id is not null and revoked_at is null) as assigned_roles,
              (select count(*) from access_user_groups) as group_memberships,
              (select count(*) from access_policy_links) as group_links
        """).fetchone()
    return any(int(row[key] or 0) > 0 for key in row.keys())


def subject_policy(user_id):
    with db_connect() as conn:
        row = conn.execute("""
            select u.id, u.username, r.can_see_all, r.can_send_all, r.can_see_own_groups, r.can_send_own_groups
            from portal_users u
            left join access_roles r on r.id = u.role_id
            where u.id = ? and u.revoked_at is null
        """, (user_id,)).fetchone()
        if not row:
            return None
        groups = {group_row["group_id"] for group_row in conn.execute("select group_id from access_user_groups where user_id = ?", (user_id,)).fetchall()}
    return {
        "id": row["id"],
        "username": row["username"],
        "can_see_all": bool(row["can_see_all"]),
        "can_send_all": bool(row["can_send_all"]),
        "can_see_own_groups": bool(row["can_see_own_groups"]),
        "can_send_own_groups": bool(row["can_send_own_groups"]),
        "groups": groups,
    }


def can_subject_action(viewer_id, target_id, action):
    if int(viewer_id) == int(target_id):
        return True
    viewer = subject_policy(viewer_id)
    target = subject_policy(target_id)
    if not viewer or not target:
        return False
    if not access_policy_active():
        return True
    if viewer[f"can_{action}_all"]:
        return True
    if viewer[f"can_{action}_own_groups"] and viewer["groups"] & target["groups"]:
        return True
    if not viewer["groups"] or not target["groups"]:
        return False
    column = f"can_{action}"
    with db_connect() as conn:
        source_placeholders = ",".join("?" for _ in viewer["groups"])
        target_placeholders = ",".join("?" for _ in target["groups"])
        params = list(viewer["groups"]) + list(target["groups"])
        row = conn.execute(f"""
            select 1
            from access_policy_links
            where source_group_id in ({source_placeholders})
              and target_group_id in ({target_placeholders})
              and {column} = 1
            limit 1
        """, params).fetchone()
    return bool(row)


def can_subject_see(viewer_id, target_id):
    return can_subject_action(viewer_id, target_id, "see")


def can_subject_send(viewer_id, target_id):
    return can_subject_action(viewer_id, target_id, "send")


def access_summary():
    return {
        "roles": list_access_roles(),
        "groups": list_access_groups(),
        "links": list_policy_links(),
        "policy_active": access_policy_active(),
        "open_default": ACCESS_CONTROL_ENFORCE and not access_policy_active(),
    }


def access_preview(user_id):
    user_id = int(user_id or 0)
    users = [user for user in list_portal_users() if not user.get("revoked")]
    subject = next((user for user in users if int(user["id"]) == user_id), None)
    if not subject:
        raise ValueError("user not found")

    def preview_user(user, can_see=False, can_send=False):
        return {
            "id": user["id"],
            "username": user["username"],
            "display_name": user.get("display_name", ""),
            "role_name": user.get("role_name", ""),
            "groups": user.get("groups", []),
            "can_see": can_see,
            "can_send": can_send,
        }

    can_see = []
    can_send = []
    seen_by = []
    senders = []
    for target in users:
        if can_subject_see(user_id, target["id"]):
            can_see.append(preview_user(target, can_see=True, can_send=can_subject_send(user_id, target["id"])))
        if can_subject_send(user_id, target["id"]):
            can_send.append(preview_user(target, can_see=can_subject_see(user_id, target["id"]), can_send=True))
        if can_subject_see(target["id"], user_id):
            seen_by.append(preview_user(target, can_see=True, can_send=can_subject_send(target["id"], user_id)))
        if can_subject_send(target["id"], user_id):
            senders.append(preview_user(target, can_see=can_subject_see(target["id"], user_id), can_send=True))
    return {
        "subject": preview_user(subject),
        "can_see": can_see,
        "can_send": can_send,
        "seen_by": seen_by,
        "senders": senders,
        "enforced": ACCESS_CONTROL_ENFORCE,
        "policy_active": access_policy_active(),
        "open_default": ACCESS_CONTROL_ENFORCE and not access_policy_active(),
    }


def marti_groups_response():
    groups = []
    for idx, group in enumerate(list_access_groups(), start=1):
        groups.append({
            "name": group["name"],
            "direction": "OUT",
            "created": group.get("created_at", ""),
            "type": "USER",
            "bitpos": idx,
            "active": True,
            "description": group.get("description", ""),
            "color": group.get("color", ""),
        })
    return {"version": 3, "type": "GroupList", "data": groups}


def client_endpoints_response():
    endpoints = []
    for info in RELAY.snapshot():
        endpoints.append({
            **info,
            "uid": info.get("uid", ""),
            "callsign": info.get("callsign", ""),
            "address": info.get("ip", ""),
            "port": info.get("port", 0),
            "transport": info.get("transport", ""),
            "username": info.get("username", "") or info.get("peer_cert_cn", ""),
            "lastEventTime": info.get("last_seen", ""),
            "connectionTime": info.get("connected_at", ""),
        })
    return {"version": 3, "type": "ClientEndpointList", "data": endpoints}


def mission_empty_response(kind="MissionList"):
    return {"version": 3, "type": kind, "data": []}


def create_policy_subject(username, role_id=None, group_ids=None):
    username = validate_portal_username(username)
    with db_connect() as conn:
        conn.execute("""
            insert into cert_profiles
              (name, description, download_token, connect_string, truststore_file, client_cert_file, datapackage_file, created_at, revoked_at)
            values (?, ?, ?, ?, ?, ?, ?, ?, null)
        """, (username, "test policy subject", secrets.token_urlsafe(18), "10.66.66.1:8089:ssl", "", "", "", utc_now()))
        profile_id = conn.execute("select id from cert_profiles where name = ?", (username,)).fetchone()["id"]
        conn.execute("""
            insert into portal_users
              (username, password_hash, display_name, description, cert_profile_id, allow_redownload, created_at, revoked_at, role_id)
            values (?, ?, ?, ?, ?, 0, ?, null, ?)
        """, (username, password_hash("atakatak"), username, "", profile_id, utc_now(), role_id))
        user_id = conn.execute("select id from portal_users where username = ?", (username,)).fetchone()["id"]
        conn.commit()
    return set_user_access(user_id, role_id=role_id, group_ids=group_ids)


def build_bulk_usernames(prefix, count):
    prefix = (prefix or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.@-]{1,56}", prefix):
        raise ValueError("bulk username prefix must use letters, numbers, dot, underscore, dash, or @")
    try:
        count = int(count)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"bulk user count must be between 1 and {MAX_BULK_USERS}") from exc
    if count < 1 or count > MAX_BULK_USERS:
        raise ValueError(f"bulk user count must be between 1 and {MAX_BULK_USERS}")
    usernames = [validate_portal_username(f"{prefix}{idx}") for idx in range(1, count + 1)]
    if len(set(usernames)) != len(usernames):
        raise ValueError("bulk username prefix produced duplicate users")
    return usernames


def generate_portal_password(length=12):
    return "".join(secrets.choice(BULK_PASSWORD_ALPHABET) for _ in range(length))


def ensure_bulk_users_available(usernames):
    if not usernames:
        raise ValueError("no users requested")
    placeholders = ",".join("?" for _ in usernames)
    with db_connect() as conn:
        users = conn.execute(f"select username from portal_users where username in ({placeholders})", usernames).fetchall()
        profiles = conn.execute(f"select name from cert_profiles where name in ({placeholders})", usernames).fetchall()
    conflicts = sorted({row[0] for row in users} | {row[0] for row in profiles})
    if conflicts:
        preview = ", ".join(conflicts[:8])
        suffix = "..." if len(conflicts) > 8 else ""
        raise ValueError(f"bulk user/profile already exists: {preview}{suffix}")


def create_bulk_portal_users(prefix, count, description="", allow_redownload=False, base_url="", role_id=None, group_ids=None):
    usernames = build_bulk_usernames(prefix, count)
    ensure_bulk_users_available(usernames)
    shared_password = BULK_PORTAL_PASSWORD
    items = []
    note = (description or "").strip()
    for username in usernames:
        create_args = [
            username,
            shared_password,
            username,
            note or f"Bulk user {username}",
            allow_redownload,
        ]
        if role_id or group_ids:
            create_args.extend([role_id, group_ids])
        user = create_portal_user(*create_args)
        portal_path = user.get("portal_path") or "/connect/"
        items.append({
            **user,
            "password": shared_password,
            "portal_url": f"{base_url}{portal_path}" if base_url else portal_path,
            "download_url": f"/api/cert-profiles/download?id={user['cert_profile_id']}",
        })
    return {"ok": True, "count": len(items), "shared_password": shared_password, "items": items}


def unique_profile_name(base):
    base = safe_profile_name(base)
    with db_connect() as conn:
        for idx in range(100):
            candidate = base if idx == 0 else f"{base}-{idx + 1}"
            row = conn.execute("select id from cert_profiles where name = ?", (candidate,)).fetchone()
            if not row:
                return candidate
    return f"{base}-{secrets.token_hex(3)}"


def portal_user_row(row):
    profile = row["profile_name"] or ""
    revoked = bool(row["revoked_at"] or row["profile_revoked_at"])
    username = row["username"]
    role_id = row["role_id"] if "role_id" in row.keys() else None
    return {
        "id": row["id"],
        "username": username,
        "display_name": row["display_name"] or "",
        "description": row["description"] or "",
        "cert_profile_id": row["cert_profile_id"],
        "profile_name": profile,
        "connect_string": row["connect_string"] or "",
        "allow_redownload": bool(row["allow_redownload"]),
        "first_download_at": row["first_download_at"] or "",
        "last_download_at": row["last_download_at"] or "",
        "download_count": row["download_count"] or 0,
        "created_at": row["created_at"],
        "revoked_at": row["revoked_at"] or row["profile_revoked_at"] or "",
        "revoked": revoked,
        "role_id": role_id,
        "role_name": "",
        "groups": [],
        "group_ids": [],
        "portal_path": f"/connect/?u={quote(username)}",
        "qr_path": f"/api/portal-users/qr?id={row['id']}",
    }


def attach_access_to_users(items):
    if not items:
        return items
    user_ids = [item["id"] for item in items]
    placeholders = ",".join("?" for _ in user_ids)
    with db_connect() as conn:
        role_rows = conn.execute(f"""
            select u.id as user_id, r.name as role_name
            from portal_users u
            left join access_roles r on r.id = u.role_id
            where u.id in ({placeholders})
        """, user_ids).fetchall()
        group_rows = conn.execute(f"""
            select ug.user_id, g.id, g.name, g.description, g.color, g.created_at
            from access_user_groups ug
            join access_groups g on g.id = ug.group_id
            where ug.user_id in ({placeholders})
            order by lower(g.name)
        """, user_ids).fetchall()
    role_names = {row["user_id"]: row["role_name"] or "" for row in role_rows}
    groups_by_user = {user_id: [] for user_id in user_ids}
    for row in group_rows:
        groups_by_user.setdefault(row["user_id"], []).append(row_to_group(row))
    for item in items:
        groups = groups_by_user.get(item["id"], [])
        item["role_name"] = role_names.get(item["id"], "")
        item["groups"] = groups
        item["group_ids"] = [group["id"] for group in groups]
    return items


def list_portal_users():
    with db_connect() as conn:
        rows = conn.execute("""
            select u.*, p.name as profile_name, p.connect_string, p.revoked_at as profile_revoked_at
            from portal_users u
            left join cert_profiles p on p.id = u.cert_profile_id
            order by u.id desc
        """).fetchall()
    return attach_access_to_users([portal_user_row(row) for row in rows])


def find_portal_user(user_id):
    with db_connect() as conn:
        return conn.execute("""
            select u.*, p.name as profile_name, p.connect_string, p.datapackage_file, p.revoked_at as profile_revoked_at
            from portal_users u
            left join cert_profiles p on p.id = u.cert_profile_id
            where u.id = ?
        """, (user_id,)).fetchone()


def find_portal_user_by_username(username):
    with db_connect() as conn:
        return conn.execute("""
            select u.*, p.name as profile_name, p.connect_string, p.datapackage_file, p.revoked_at as profile_revoked_at
            from portal_users u
            left join cert_profiles p on p.id = u.cert_profile_id
            where u.username = ?
        """, ((username or "").strip(),)).fetchone()


def create_portal_user(username, password, display_name="", description="", allow_redownload=False, role_id=None, group_ids=None):
    username = validate_portal_username(username)
    if len(password or "") < 8:
        raise ValueError("portal password must be at least 8 characters")
    with db_connect() as conn:
        if conn.execute("select id from portal_users where username = ?", (username,)).fetchone():
            raise ValueError("a portal user with that username already exists")
    profile_name = unique_profile_name(username)
    profile = create_cert_profile(profile_name, description or f"Portal user {username}")
    with db_connect() as conn:
        conn.execute("""
            insert into portal_users
              (username, password_hash, display_name, description, cert_profile_id, allow_redownload, created_at, revoked_at)
            values (?, ?, ?, ?, ?, ?, ?, null)
        """, (
            username,
            password_hash(password),
            (display_name or username).strip(),
            (description or "").strip(),
            profile["id"],
            1 if allow_redownload else 0,
            utc_now(),
        ))
        conn.commit()
        user_id = conn.execute("select id from portal_users where username = ?", (username,)).fetchone()["id"]
    if role_id or group_ids:
        return set_user_access(user_id, role_id=role_id, group_ids=group_ids)
    return attach_access_to_users([portal_user_row(find_portal_user(user_id))])[0]


def authenticate_portal_user(username, password):
    row = find_portal_user_by_username(username)
    if not row or row["revoked_at"] or row["profile_revoked_at"]:
        return None
    if not verify_password(password or "", row["password_hash"]):
        return None
    return row


def create_portal_session(user_id):
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=PORTAL_SESSION_HOURS)
    with db_connect() as conn:
        conn.execute(
            "insert into portal_sessions (token, user_id, created_at, expires_at) values (?, ?, ?, ?)",
            (token, user_id, now.replace(microsecond=0).isoformat().replace("+00:00", "Z"), expires.replace(microsecond=0).isoformat().replace("+00:00", "Z")),
        )
        conn.commit()
    return token


def validate_portal_session(token):
    if not token:
        return None
    with db_connect() as conn:
        row = conn.execute("""
            select s.user_id, s.expires_at
            from portal_sessions s
            join portal_users u on u.id = s.user_id
            left join cert_profiles p on p.id = u.cert_profile_id
            where s.token = ? and u.revoked_at is null and p.revoked_at is null
        """, (token,)).fetchone()
        if not row:
            return None
        expires = parse_utc(row["expires_at"])
        if not expires or expires <= datetime.now(timezone.utc):
            conn.execute("delete from portal_sessions where token = ?", (token,))
            conn.commit()
            return None
    return find_portal_user(row["user_id"])


def portal_logout(token):
    if token:
        with db_connect() as conn:
            conn.execute("delete from portal_sessions where token = ?", (token,))
            conn.commit()


def reset_portal_password(user_id, password):
    if len(password or "") < 8:
        raise ValueError("portal password must be at least 8 characters")
    with db_connect() as conn:
        row = conn.execute("select id from portal_users where id = ?", (user_id,)).fetchone()
        if not row:
            raise ValueError("portal user not found")
        conn.execute("update portal_users set password_hash = ? where id = ?", (password_hash(password), user_id))
        conn.execute("delete from portal_sessions where user_id = ?", (user_id,))
        conn.commit()
    return portal_user_row(find_portal_user(user_id))


def edit_portal_user(user_id, display_name="", description=""):
    with db_connect() as conn:
        row = conn.execute("select id from portal_users where id = ?", (user_id,)).fetchone()
        if not row:
            raise ValueError("portal user not found")
        conn.execute("""
            update portal_users
            set display_name = ?, description = ?
            where id = ?
        """, ((display_name or "").strip(), (description or "").strip(), user_id))
        conn.commit()
    return portal_user_row(find_portal_user(user_id))


def set_portal_redownload(user_id, allow_redownload):
    with db_connect() as conn:
        row = conn.execute("select id from portal_users where id = ?", (user_id,)).fetchone()
        if not row:
            raise ValueError("portal user not found")
        conn.execute("update portal_users set allow_redownload = ? where id = ?", (1 if allow_redownload else 0, user_id))
        conn.commit()
    return portal_user_row(find_portal_user(user_id))


def revoke_portal_user(user_id):
    row = find_portal_user(user_id)
    if not row:
        raise ValueError("portal user not found")
    revoke_cert_profile(row["cert_profile_id"])
    with db_connect() as conn:
        conn.execute("update portal_users set revoked_at = coalesce(revoked_at, ?) where id = ?", (utc_now(), user_id))
        conn.execute("delete from portal_sessions where user_id = ?", (user_id,))
        conn.commit()
    return portal_user_row(find_portal_user(user_id))


def delete_portal_user(user_id, delete_profile=False):
    row = find_portal_user(user_id)
    if not row:
        raise ValueError("portal user not found")
    profile_id = row["cert_profile_id"]
    with db_connect() as conn:
        conn.execute("delete from portal_sessions where user_id = ?", (user_id,))
        conn.execute("delete from portal_users where id = ?", (user_id,))
        conn.commit()
    deleted_profile = None
    if delete_profile and profile_id:
        deleted_profile = delete_cert_profile(profile_id, True)
    return {"deleted": True, "deleted_profile": deleted_profile}


def reissue_portal_user(user_id):
    row = find_portal_user(user_id)
    if not row:
        raise ValueError("portal user not found")
    if row["cert_profile_id"]:
        revoke_cert_profile(row["cert_profile_id"])
    profile_name = unique_profile_name(row["username"])
    profile = create_cert_profile(profile_name, row["description"] or f"Portal user {row['username']}")
    with db_connect() as conn:
        conn.execute("""
            update portal_users
            set cert_profile_id = ?, first_download_at = null, last_download_at = null, download_count = 0, revoked_at = null
            where id = ?
        """, (profile["id"], user_id))
        conn.execute("delete from portal_sessions where user_id = ?", (user_id,))
        conn.commit()
    return portal_user_row(find_portal_user(user_id))


def mark_portal_download(user_id):
    now = utc_now()
    with db_connect() as conn:
        conn.execute("""
            update portal_users
            set first_download_at = coalesce(first_download_at, ?),
                last_download_at = ?,
                download_count = download_count + 1
            where id = ?
        """, (now, now, user_id))
        conn.commit()


def safe_profile_name(name):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", (name or "").strip()).strip(".-")
    if not safe:
        raise ValueError("profile name is required")
    return safe[:64]


def cert_profile_row(row):
    token = row["download_token"] or ""
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"] or "",
        "download_token": token,
        "public_download_path": f"/connect/{token}.dp.zip" if token else "",
        "connect_string": row["connect_string"],
        "truststore_file": Path(row["truststore_file"]).name,
        "client_cert_file": Path(row["client_cert_file"]).name,
        "datapackage_file": Path(row["datapackage_file"]).name,
        "created_at": row["created_at"],
        "revoked_at": row["revoked_at"] or "",
        "revoked": bool(row["revoked_at"]),
    }


def list_cert_profiles():
    with db_connect() as conn:
        rows = conn.execute("select * from cert_profiles order by id desc").fetchall()
    return [cert_profile_row(row) for row in rows]


def find_cert_profile(profile_id):
    with db_connect() as conn:
        return conn.execute("select * from cert_profiles where id = ?", (profile_id,)).fetchone()


def find_cert_profile_by_token(token):
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", token or ""):
        return None
    with db_connect() as conn:
        return conn.execute("select * from cert_profiles where download_token = ?", (token,)).fetchone()


def client_cert_authorized(common_name):
    if not common_name:
        return not COT_TLS_REQUIRE_CLIENT_CERT
    if ALLOW_LEGACY_CLIENT_CERT and common_name == "taklite-client":
        return True
    with db_connect() as conn:
        row = conn.execute(
            "select revoked_at from cert_profiles where name = ?", (common_name,)
        ).fetchone()
    return bool(row and not row["revoked_at"])


def client_identity_for_cert(common_name):
    common_name = (common_name or "").strip()
    if not common_name:
        return None
    with db_connect() as conn:
        row = conn.execute("""
            select u.id as user_id,
                   u.username,
                   u.revoked_at as user_revoked_at,
                   p.id as cert_profile_id,
                   p.name as cert_name,
                   p.revoked_at as profile_revoked_at
            from cert_profiles p
            left join portal_users u on u.cert_profile_id = p.id
            where p.name = ?
        """, (common_name,)).fetchone()
    if not row or row["profile_revoked_at"] or row["user_revoked_at"] or not row["user_id"]:
        return None
    return {
        "user_id": row["user_id"],
        "username": row["username"],
        "cert_profile_id": row["cert_profile_id"],
        "cert_cn": row["cert_name"],
    }


def cot_delivery_allowed(sender_user_id, target_user_id, enforce=None):
    if enforce is None:
        enforce = ACCESS_CONTROL_ENFORCE
    if not enforce:
        return True
    if not sender_user_id or not target_user_id:
        return False
    return can_subject_send(sender_user_id, target_user_id) or can_subject_see(target_user_id, sender_user_id)


def package_visible_to_user(package, user_id, enforce=None):
    if enforce is None:
        enforce = ACCESS_CONTROL_ENFORCE
    if not enforce:
        return True
    if not user_id:
        visibility = (package.get("Visibility") or package.get("Tool") or "private").lower()
        tool = (package.get("Tool") or "").lower()
        return visibility == "public" or tool == "public"
    if not access_policy_active():
        return True
    visibility = (package.get("Visibility") or package.get("Tool") or "private").lower()
    tool = (package.get("Tool") or "").lower()
    if visibility == "private" and tool == "public":
        visibility = "public"
    creator_user_id = package.get("CreatorUserId")
    if visibility == "public":
        return True
    if not creator_user_id:
        return False
    if int(user_id) == int(creator_user_id):
        return True
    return can_subject_see(user_id, creator_user_id) and can_subject_send(creator_user_id, user_id)


def package_visible_to_request(row, handler):
    return package_visible_to_user(row_to_package(row), handler.authenticated_user_id(), ACCESS_CONTROL_ENFORCE)


def run_openssl(args):
    result = subprocess.run(["openssl", *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "openssl failed").strip())


P12_CERT_COMPAT_ARGS = [
    "-certpbe", "PBE-SHA1-3DES",
    "-macalg", "sha1",
]
P12_KEY_COMPAT_ARGS = [
    *P12_CERT_COMPAT_ARGS,
    "-keypbe", "PBE-SHA1-3DES",
]


def subject_alt_name_for_host(host):
    host = (host or "127.0.0.1").strip()
    if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", host):
        return f"IP:{host}"
    if ":" in host:
        return f"IP:{host}"
    return f"DNS:{host}"


def ensure_base_certs():
    ca_cert = CERT_DIR / "taklite-ca.crt"
    ca_key = CERT_DIR / "taklite-ca.key"
    server_csr = CERT_DIR / "taklite-server.csr"
    server_crt = CERT_DIR / "taklite-server.crt"
    server_ext = CERT_DIR / "taklite-server.ext"
    server_name = SERVER_HOST or PUBLIC_HOST or "127.0.0.1"

    CERT_DIR.mkdir(parents=True, exist_ok=True)
    if not ca_cert.exists() or not ca_key.exists():
        run_openssl(["genrsa", "-out", str(ca_key), "4096"])
        run_openssl([
            "req", "-x509", "-new", "-nodes",
            "-key", str(ca_key),
            "-sha256", "-days", "3650",
            "-out", str(ca_cert),
            "-subj", "/CN=TAKlite Local CA",
        ])
        ca_key.chmod(0o600)
        ca_cert.chmod(0o644)

    if not HTTPS_CERT.exists() or not HTTPS_KEY.exists():
        run_openssl(["genrsa", "-out", str(HTTPS_KEY), "3072"])
        run_openssl([
            "req", "-new",
            "-key", str(HTTPS_KEY),
            "-out", str(server_csr),
            "-subj", f"/CN={server_name}",
        ])
        server_ext.write_text(
            "\n".join([
                "authorityKeyIdentifier=keyid,issuer",
                "basicConstraints=CA:FALSE",
                "keyUsage = digitalSignature, keyEncipherment",
                "extendedKeyUsage = serverAuth",
                f"subjectAltName = {subject_alt_name_for_host(server_name)},DNS:taklite.local",
                "",
            ]),
            encoding="utf-8",
        )
        run_openssl([
            "x509", "-req",
            "-in", str(server_csr),
            "-CA", str(ca_cert),
            "-CAkey", str(ca_key),
            "-CAcreateserial",
            "-out", str(server_crt),
            "-days", "825",
            "-sha256",
            "-extfile", str(server_ext),
        ])
        HTTPS_CERT.write_bytes(server_crt.read_bytes() + ca_cert.read_bytes())
        HTTPS_KEY.chmod(0o600)
        HTTPS_CERT.chmod(0o644)

    ensure_truststore_file()
    packaged_truststore_file()


def ensure_truststore_file():
    ca_cert = CERT_DIR / "taklite-ca.crt"
    ca_key = CERT_DIR / "taklite-ca.key"
    truststore = CERT_DIR / "taklite-truststore.p12"
    tmp_truststore = CERT_DIR / ".taklite-truststore.p12.tmp"
    holder_key = CERT_DIR / "taklite-truststore-holder.key"
    holder_csr = CERT_DIR / "taklite-truststore-holder.csr"
    holder_crt = CERT_DIR / "taklite-truststore-holder.crt"
    holder_ext = CERT_DIR / "taklite-truststore-holder.ext"
    if not ca_cert.exists() or not ca_key.exists():
        raise RuntimeError("TAKlite CA is missing; rerun the installer or restore taklite-ca.crt/taklite-ca.key")
    if not holder_crt.exists() or not holder_key.exists():
        run_openssl(["genrsa", "-out", str(holder_key), "2048"])
        run_openssl(["req", "-new", "-key", str(holder_key), "-out", str(holder_csr), "-subj", "/CN=taklite-truststore"])
        holder_ext.write_text("basicConstraints=CA:FALSE\nkeyUsage = digitalSignature, keyEncipherment\n", encoding="utf-8")
        run_openssl([
            "x509", "-req",
            "-in", str(holder_csr),
            "-CA", str(ca_cert),
            "-CAkey", str(ca_key),
            "-CAcreateserial",
            "-out", str(holder_crt),
            "-days", "825",
            "-sha256",
            "-extfile", str(holder_ext),
        ])
        holder_key.chmod(0o600)
        holder_crt.chmod(0o644)
    run_openssl([
        "pkcs12", "-export",
        "-inkey", str(holder_key),
        "-in", str(holder_crt),
        "-certfile", str(ca_cert),
        "-out", str(tmp_truststore),
        "-name", "taklite-ca",
        *P12_KEY_COMPAT_ARGS,
        "-passout", f"pass:{CERT_PASSWORD}",
    ])
    tmp_truststore.replace(truststore)
    truststore.chmod(0o644)
    return truststore


def packaged_truststore_file():
    truststore = ensure_truststore_file()
    truststore_name = f"{safe_profile_name(SERVER_HOST)}.p12"
    packaged = CERT_DIR / truststore_name
    if packaged != truststore:
        tmp_packaged = CERT_DIR / f".{truststore_name}.tmp"
        tmp_packaged.write_bytes(truststore.read_bytes())
        tmp_packaged.replace(packaged)
        packaged.chmod(0o644)
    return packaged


def build_server_pref(connect_string, truststore_name, client_cert_name, description="TAKlite"):
    return f"""<?xml version='1.0' encoding='ASCII' standalone='yes'?>
<preferences>
  <preference version="1" name="cot_streams">
    <entry key="count" class="class java.lang.Integer">1</entry>
    <entry key="description0" class="class java.lang.String">{html.escape(description)}</entry>
    <entry key="enabled0" class="class java.lang.Boolean">true</entry>
    <entry key="connectString0" class="class java.lang.String">{html.escape(connect_string)}</entry>
    <entry key="caLocation0" class="class java.lang.String">cert/{html.escape(truststore_name)}</entry>
    <entry key="caPassword0" class="class java.lang.String">{html.escape(CERT_PASSWORD)}</entry>
    <entry key="clientPassword0" class="class java.lang.String">{html.escape(CERT_PASSWORD)}</entry>
    <entry key="certificateLocation0" class="class java.lang.String">cert/{html.escape(client_cert_name)}</entry>
  </preference>
  <preference version="1" name="com.atakmap.app_preferences">
    <entry key="displayServerConnectionWidget" class="class java.lang.Boolean">true</entry>
    <entry key="caLocation" class="class java.lang.String">cert/{html.escape(truststore_name)}</entry>
    <entry key="caPassword" class="class java.lang.String">{html.escape(CERT_PASSWORD)}</entry>
    <entry key="clientPassword" class="class java.lang.String">{html.escape(CERT_PASSWORD)}</entry>
    <entry key="certificateLocation" class="class java.lang.String">cert/{html.escape(client_cert_name)}</entry>
    <entry key="apiSecureServerPort" class="class java.lang.String">{HTTPS_PUBLIC_PORT}</entry>
    <entry key="apiUnsecureServerPort" class="class java.lang.String">{HTTP_PUBLIC_PORT}</entry>
  </preference>
</preferences>
"""


def build_manifest(uid, display_name, truststore_name, client_cert_name):
    return f"""<MissionPackageManifest version="2">
  <Configuration>
    <Parameter name="uid" value="{html.escape(uid)}"/>
    <Parameter name="name" value="{html.escape(display_name)}"/>
    <Parameter name="onReceiveImport" value="true"/>
    <Parameter name="onReceiveDelete" value="true"/>
  </Configuration>
  <Contents>
    <Content ignore="false" zipEntry="certs/server.pref"/>
    <Content ignore="false" zipEntry="certs/{html.escape(truststore_name)}"/>
    <Content ignore="false" zipEntry="certs/{html.escape(client_cert_name)}"/>
  </Contents>
</MissionPackageManifest>
"""


def create_cert_profile(name, description=""):
    name = safe_profile_name(name)
    description = (description or "").strip()
    truststore = packaged_truststore_file()
    ca_cert = CERT_DIR / "taklite-ca.crt"
    ca_key = CERT_DIR / "taklite-ca.key"
    client_key = CERT_DIR / f"{name}.key"
    client_csr = CERT_DIR / f"{name}.csr"
    client_ext = CERT_DIR / f"{name}.ext"
    client_crt = CERT_DIR / f"{name}.crt"
    client_p12 = CERT_DIR / f"{name}.p12"
    dp_zip = CERT_DIR / f"{name}-{SERVER_HOST}.dp.zip"
    connect_string = f"{SERVER_HOST}:{COT_TLS_PUBLIC_PORT}:ssl"
    download_token = secrets.token_urlsafe(18)

    with db_connect() as conn:
        existing = conn.execute("select id from cert_profiles where name = ?", (name,)).fetchone()
        if existing:
            raise ValueError("a connection package with that name already exists")

    run_openssl(["genrsa", "-out", str(client_key), "3072"])
    run_openssl(["req", "-new", "-key", str(client_key), "-out", str(client_csr), "-subj", f"/CN={name}"])
    client_ext.write_text("basicConstraints=CA:FALSE\nkeyUsage = digitalSignature, keyEncipherment\nextendedKeyUsage = clientAuth\n", encoding="utf-8")
    run_openssl([
        "x509", "-req",
        "-in", str(client_csr),
        "-CA", str(ca_cert),
        "-CAkey", str(ca_key),
        "-CAcreateserial",
        "-out", str(client_crt),
        "-days", "825",
        "-sha256",
        "-extfile", str(client_ext),
    ])
    run_openssl([
        "pkcs12", "-export",
        "-inkey", str(client_key),
        "-in", str(client_crt),
        "-certfile", str(ca_cert),
        "-out", str(client_p12),
        "-name", name,
        *P12_KEY_COMPAT_ARGS,
        "-passout", f"pass:{CERT_PASSWORD}",
    ])
    client_key.chmod(0o600)
    client_p12.chmod(0o644)

    display_name = f"TAKlite {name}"
    manifest = build_manifest(f"taklite-{name}", display_name, truststore.name, client_p12.name)
    server_pref = build_server_pref(connect_string, truststore.name, client_p12.name, display_name)
    with zipfile.ZipFile(dp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("MANIFEST/manifest.xml", manifest)
        zf.writestr("certs/server.pref", server_pref)
        zf.write(truststore, f"certs/{truststore.name}")
        zf.write(client_p12, f"certs/{client_p12.name}")
    dp_zip.chmod(0o644)

    with db_connect() as conn:
        conn.execute("""
            insert into cert_profiles
              (name, description, download_token, connect_string, truststore_file, client_cert_file, datapackage_file, created_at, revoked_at)
            values (?, ?, ?, ?, ?, ?, ?, ?, null)
        """, (name, description, download_token, connect_string, str(truststore), str(client_p12), str(dp_zip), utc_now()))
        conn.commit()
        row = conn.execute("select * from cert_profiles where name = ?", (name,)).fetchone()
    return cert_profile_row(row)


def revoke_cert_profile(profile_id):
    with db_connect() as conn:
        row = conn.execute("select * from cert_profiles where id = ?", (profile_id,)).fetchone()
        if not row:
            raise ValueError("connection package not found")
        conn.execute("update cert_profiles set revoked_at = coalesce(revoked_at, ?) where id = ?", (utc_now(), profile_id))
        conn.commit()
        row = conn.execute("select * from cert_profiles where id = ?", (profile_id,)).fetchone()
    disconnected = RELAY.disconnect_cert_cn(row["name"]) if row and row["name"] else 0
    if disconnected:
        print(f"TAKlite disconnected {disconnected} active client(s) for revoked cert_cn={row['name']}", flush=True)
    return cert_profile_row(row)


def delete_cert_profile(profile_id, delete_files=True):
    row = find_cert_profile(profile_id)
    if not row:
        raise ValueError("connection package not found")
    deleted = []
    with db_connect() as conn:
        conn.execute("delete from cert_profiles where id = ?", (profile_id,))
        conn.commit()
    if delete_files:
        cert_root = CERT_DIR.resolve()
        for key in ("client_cert_file", "datapackage_file"):
            path = Path(row[key])
            if path.exists() and path.resolve().is_relative_to(cert_root):
                path.unlink()
                deleted.append(str(path))
    return {"deleted": True, "deleted_files": deleted}


def server_tls_context(request_client_cert=False):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(str(HTTPS_CERT), str(HTTPS_KEY))
    if request_client_cert and CLIENT_CA.exists():
        context.load_verify_locations(cafile=str(CLIENT_CA))
        context.verify_mode = ssl.CERT_REQUIRED if COT_TLS_REQUIRE_CLIENT_CERT else ssl.CERT_OPTIONAL
    return context


class CotRelay:
    def __init__(self):
        self.lock = threading.Lock()
        self.clients = {}
        self.last_events = {}

    def add(self, handler):
        remote = handler.remote
        host, port = handler.client_address
        now = utc_now()
        peer_cert = {}
        peer_cert_cn = ""
        if hasattr(handler.request, "getpeercert"):
            try:
                peer_cert = handler.request.getpeercert() or {}
                peer_cert_cn = cert_common_name(peer_cert)
            except OSError:
                peer_cert = {}
        with self.lock:
            self.clients[handler] = {
                "remote": remote,
                "ip": host,
                "port": port,
                "transport": getattr(handler.server, "transport", "tcp"),
                "peer_cert_cn": peer_cert_cn,
                "peer_cert_present": bool(peer_cert),
                "user_id": getattr(handler, "user_id", None),
                "username": "",
                "uid": "",
                "callsign": "",
                "connected_at": now,
                "last_seen": now,
            }
            identity = client_identity_for_cert(peer_cert_cn)
            if identity:
                self.clients[handler]["username"] = identity["username"]
        self.send_recent(handler)
        self.send_to(handler, server_status_event())

    def remove(self, handler):
        with self.lock:
            self.clients.pop(handler, None)

    def disconnect_cert_cn(self, cert_cn):
        cert_cn = (cert_cn or "").strip()
        if not cert_cn:
            return 0
        with self.lock:
            handlers = [
                handler
                for handler, info in self.clients.items()
                if (info.get("peer_cert_cn") or "") == cert_cn
            ]
        for handler in handlers:
            try:
                handler.request.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                handler.request.close()
            except OSError:
                pass
        return len(handlers)

    def update_client(self, remote, uid, callsign):
        with self.lock:
            for info in self.clients.values():
                if info["remote"] == remote:
                    if uid:
                        info["uid"] = uid
                    if callsign:
                        info["callsign"] = callsign
                    info["last_seen"] = utc_now()

    def snapshot(self):
        with self.lock:
            return list(self.clients.values())

    def remember_event(self, uid, event, user_id=None):
        with self.lock:
            self.last_events[uid] = (time.time(), event, user_id)
            cutoff = time.time() - 300
            for old_uid, (seen, _, _) in list(self.last_events.items()):
                if seen < cutoff:
                    self.last_events.pop(old_uid, None)

    def send_to(self, handler, event):
        try:
            with handler.send_lock:
                previous_timeout = None
                try:
                    previous_timeout = handler.request.gettimeout()
                    handler.request.settimeout(SOCKET_SEND_TIMEOUT_SECONDS)
                    handler.request.sendall(event)
                finally:
                    try:
                        handler.request.settimeout(previous_timeout)
                    except OSError:
                        pass
            return True
        except OSError:
            self.remove(handler)
            return False

    def send_recent(self, handler):
        with self.lock:
            events = [(event, user_id) for _, event, user_id in self.last_events.values()]
        for event, sender_user_id in events:
            if cot_delivery_allowed(sender_user_id, getattr(handler, "user_id", None)):
                self.send_to(handler, event)

    def broadcast(self, sender, event):
        with self.lock:
            handlers = [(handler, dict(info)) for handler, info in self.clients.items()]
        sender_user_id = getattr(sender, "user_id", None) if sender is not None else None
        for handler, info in handlers:
            if sender is not None and handler is sender:
                continue
            if sender is not None and not cot_delivery_allowed(sender_user_id, info.get("user_id")):
                continue
            self.send_to(handler, event)

    def send_to_client_uids(self, event, client_uids=None, send_all=False):
        requested = set(client_uids or [])
        with self.lock:
            handlers = [(handler, dict(info)) for handler, info in self.clients.items()]
        results = []
        matched = set()
        for handler, info in handlers:
            uid = info.get("uid") or ""
            if not send_all and uid not in requested:
                continue
            if uid:
                matched.add(uid)
            sent = self.send_to(handler, event)
            results.append({
                "uid": uid,
                "callsign": info.get("callsign") or "Unknown",
                "ip": info.get("ip") or "",
                "sent": sent,
            })
        missed = sorted(requested - matched)
        return {"sent": sum(1 for item in results if item["sent"]), "results": results, "missed": missed}

    def heartbeat(self):
        self.broadcast(None, server_status_event())


RELAY = CotRelay()


class CotHandler(BaseRequestHandler):
    def setup(self):
        self.remote = f"{self.client_address[0]}:{self.client_address[1]}"
        self.bytes_in = 0
        self.events_in = 0
        self.send_lock = threading.Lock()
        self.user_id = None
        self.cert_cn = ""
        transport = getattr(self.server, "transport", "tcp")
        peer_cert_cn = ""
        if hasattr(self.request, "getpeercert"):
            try:
                peer_cert_cn = cert_common_name(self.request.getpeercert() or {})
            except OSError:
                peer_cert_cn = ""
        if transport == "tls" and not client_cert_authorized(peer_cert_cn):
            print(f"CoT reject {self.remote} transport={transport} cert_cn={peer_cert_cn or 'none'} reason=unauthorized_cert")
            try:
                self.request.close()
            except OSError:
                pass
            return
        identity = client_identity_for_cert(peer_cert_cn)
        self.user_id = identity["user_id"] if identity else None
        self.cert_cn = peer_cert_cn
        if ACCESS_CONTROL_ENFORCE and not self.user_id:
            print(f"CoT reject {self.remote} transport={transport} cert_cn={peer_cert_cn or 'none'} reason=missing_policy_identity")
            try:
                self.request.close()
            except OSError:
                pass
            return
        RELAY.add(self)
        cert_note = f" cert_cn={peer_cert_cn}" if peer_cert_cn else " cert_cn=none"
        print(f"CoT connect {self.remote} transport={transport}{cert_note}")

    def handle(self):
        buf = b""
        while True:
            try:
                chunk = self.request.recv(65536)
            except OSError as exc:
                print(f"CoT recv error {self.remote}: {exc}")
                break
            if not chunk:
                break
            self.bytes_in += len(chunk)
            buf += chunk
            if len(buf) > COT_MAX_BUFFER_BYTES:
                print(f"CoT closing {self.remote}: buffered data exceeded {COT_MAX_BUFFER_BYTES} bytes without complete event")
                break
            while EVENT_END in buf:
                end = buf.find(EVENT_END) + len(EVENT_END)
                candidate, buf = buf[:end], buf[end:]
                match = EVENT_RE.search(candidate)
                event = match.group(0) if match else candidate
                self.events_in += 1
                save_event(event, self.remote, self.user_id)
                RELAY.broadcast(self, event)

    def finish(self):
        RELAY.remove(self)
        print(f"CoT disconnect {self.remote} events={self.events_in} bytes={self.bytes_in}")


class CotServer(ThreadingMixIn, TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, handler_class, transport="tcp"):
        self.transport = transport
        super().__init__(server_address, handler_class)


def absolute_base_url(handler):
    host = PUBLIC_HOST or handler.headers.get("Host", f"127.0.0.1:{HTTP_PORT}").split(":")[0]
    if ":" in host:
        return f"http://{host}"
    return f"http://{host}:{HTTP_PORT}"


def dir_size(path):
    total = 0
    if not path.exists():
        return 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except FileNotFoundError:
            continue
    return total


def file_size(path):
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def read_json_file(path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def request_dir_status(path_value):
    request_dir = Path(path_value) if path_value else None
    if not request_dir or not request_dir.is_dir():
        return {
            "enabled": False,
            "request_dir": path_value,
            "pending": False,
            "processing": False,
            "last_status": None,
        }
    return {
        "enabled": True,
        "request_dir": path_value,
        "pending": (request_dir / "request.json").exists(),
        "processing": (request_dir / "processing.json").exists(),
        "last_status": read_json_file(request_dir / "status.json"),
    }


def validate_host(value, label):
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{label} is required")
    if len(value) > 253 or any(ch.isspace() for ch in value):
        raise ValueError(f"{label} is not valid")
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", value):
        raise ValueError(f"{label} contains unsupported characters")
    return value


def validate_url(value, label):
    value = (value or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"{label} must be an http or https URL")
    if len(value) > 500:
        raise ValueError(f"{label} is too long")
    return value


def validate_port(value, label):
    try:
        port = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a port number")
    if port < 1 or port > 65535:
        raise ValueError(f"{label} must be between 1 and 65535")
    return port


def validate_max_upload(value):
    try:
        size = int(value)
    except (TypeError, ValueError):
        raise ValueError("max upload size must be a number of bytes")
    if size < 1024 * 1024 or size > 2 * 1024 * 1024 * 1024:
        raise ValueError("max upload size must be between 1 MB and 2 GB")
    return size


def validate_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off", ""):
        return False
    raise ValueError("boolean setting must be true or false")


def editable_settings_status():
    runner = request_dir_status(SETTINGS_REQUEST_DIR)
    values = {
        "public_host": PUBLIC_HOST or SERVER_HOST,
        "server_host": SERVER_HOST,
        "wg_dashboard_url": WG_DASHBOARD_URL,
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "cot_host_port": COT_PUBLIC_PORT,
        "cot_tls_host_port": COT_TLS_PUBLIC_PORT,
        "http_host_port": HTTP_PUBLIC_PORT,
        "https_host_port": HTTPS_PUBLIC_PORT,
        "access_control_enforce": ACCESS_CONTROL_ENFORCE,
        "cot_tls_require_client_cert": COT_TLS_REQUIRE_CLIENT_CERT,
        "allow_legacy_client_cert": ALLOW_LEGACY_CLIENT_CERT,
    }
    return {
        "values": values,
        "runner": runner,
        "restart_required_fields": [
            "public_host",
            "server_host",
            "wg_dashboard_url",
            "max_upload_bytes",
            "cot_host_port",
            "cot_tls_host_port",
            "http_host_port",
            "https_host_port",
            "access_control_enforce",
            "cot_tls_require_client_cert",
            "allow_legacy_client_cert",
        ],
        "port_warning": "Changing service ports restarts TAKlite and must match WireGuard/firewall exposure.",
    }


def queue_settings_update(payload):
    runner = request_dir_status(SETTINGS_REQUEST_DIR)
    if not runner["enabled"]:
        return {"ok": False, "error": "settings runner is not enabled"}
    if runner["pending"] or runner["processing"]:
        return {"ok": False, "error": "a settings update is already pending or running"}
    values = payload.get("values") if isinstance(payload, dict) else {}
    if not isinstance(values, dict):
        raise ValueError("settings values are required")
    sanitized = {
        "TAKLITE_PUBLIC_HOST": validate_host(values.get("public_host"), "public host"),
        "TAKLITE_SERVER_HOST": validate_host(values.get("server_host"), "server host"),
        "TAKLITE_WGDASHBOARD_URL": validate_url(values.get("wg_dashboard_url"), "WireGuard dashboard URL"),
        "TAKLITE_MAX_UPLOAD_BYTES": str(validate_max_upload(values.get("max_upload_bytes"))),
        "TAKLITE_COT_HOST_PORT": str(validate_port(values.get("cot_host_port"), "plain CoT port")),
        "TAKLITE_COT_TLS_HOST_PORT": str(validate_port(values.get("cot_tls_host_port"), "TLS CoT port")),
        "TAKLITE_HTTP_HOST_PORT": str(validate_port(values.get("http_host_port"), "admin HTTP port")),
        "TAKLITE_HTTPS_HOST_PORT": str(validate_port(values.get("https_host_port"), "HTTPS/Marti port")),
        "TAKLITE_ACCESS_CONTROL_ENFORCE": "true" if validate_bool(values.get("access_control_enforce")) else "false",
        "TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT": "true" if validate_bool(values.get("cot_tls_require_client_cert")) else "false",
        "TAKLITE_ALLOW_LEGACY_CLIENT_CERT": "true" if validate_bool(values.get("allow_legacy_client_cert")) else "false",
    }
    request_dir = Path(SETTINGS_REQUEST_DIR)
    request = {
        "id": secrets.token_urlsafe(12),
        "requested_at": utc_now(),
        "env": sanitized,
    }
    tmp_file = request_dir / f".request-{request['id']}.tmp"
    tmp_file.write_text(json.dumps(request, indent=2))
    tmp_file.replace(request_dir / "request.json")
    return {"ok": True, "queued": True, "request": {"id": request["id"], "requested_at": request["requested_at"]}}


def firewall_status():
    runner = request_dir_status(FIREWALL_REQUEST_DIR)
    last_status = runner.get("last_status") or {}
    service_states = last_status.get("service_states") if isinstance(last_status, dict) else {}
    if not isinstance(service_states, dict):
        service_states = {}
    defaults = {
        "ssh": "vpn",
        "wireguard": "public",
        "wg_dashboard": "vpn",
        "taklite_admin": "vpn",
        "tak_https": "vpn",
        "cot_tcp": "vpn",
        "cot_tls": "vpn",
    }
    services = []
    for key, config in FIREWALL_SERVICES.items():
        state = service_states.get(key) or defaults.get(key, "vpn")
        if state not in FIREWALL_STATES:
            state = defaults.get(key, "vpn")
        services.append({
            "key": key,
            "label": config["label"],
            "protocol": config["protocol"],
            "port": config["port"],
            "state": state,
            "recommended_state": defaults.get(key, "vpn"),
            "lockout_sensitive": bool(config.get("lockout_sensitive")),
        })
    return {
        "runner": runner,
        "services": services,
        "interfaces": {
            "wireguard": WG_INTERFACE,
            "public": PUBLIC_INTERFACE,
        },
        "states": ["public", "vpn", "closed"],
        "warnings": [
            "WireGuard UDP should remain public or remote VPN access will fail.",
            "Closing public SSH can lock you out unless SSH over WireGuard is confirmed.",
            "Firewall changes are separate from TAKlite port settings.",
        ],
    }


def queue_firewall_update(payload):
    runner = request_dir_status(FIREWALL_REQUEST_DIR)
    if not runner["enabled"]:
        return {"ok": False, "error": "firewall runner is not enabled"}
    if runner["pending"] or runner["processing"]:
        return {"ok": False, "error": "a firewall update is already pending or running"}
    services = payload.get("services") if isinstance(payload, dict) else None
    if not isinstance(services, dict):
        raise ValueError("firewall services are required")
    sanitized = {}
    for key, state in services.items():
        if key not in FIREWALL_SERVICES:
            raise ValueError(f"unknown firewall service: {key}")
        state = (state or "").strip().lower()
        if state not in FIREWALL_STATES:
            raise ValueError(f"invalid firewall state for {key}")
        sanitized[key] = state
    if sanitized.get("wireguard") == "closed":
        raise ValueError("WireGuard cannot be closed from the GUI")
    if sanitized.get("ssh") == "closed" and payload.get("confirm_ssh_close") != "SSH_OVER_WG_CONFIRMED":
        raise ValueError("confirm SSH over WireGuard before closing SSH")
    for key in FIREWALL_SERVICES:
        sanitized.setdefault(key, next((item["state"] for item in firewall_status()["services"] if item["key"] == key), "vpn"))
    request_dir = Path(FIREWALL_REQUEST_DIR)
    request = {
        "id": secrets.token_urlsafe(12),
        "requested_at": utc_now(),
        "services": sanitized,
        "interfaces": {"wireguard": WG_INTERFACE, "public": PUBLIC_INTERFACE},
    }
    tmp_file = request_dir / f".request-{request['id']}.tmp"
    tmp_file.write_text(json.dumps(request, indent=2))
    tmp_file.replace(request_dir / "request.json")
    return {"ok": True, "queued": True, "request": {"id": request["id"], "requested_at": request["requested_at"]}}


def runtime_health():
    db_ok = False
    db_error = ""
    counts = {}
    try:
        with db_connect() as conn:
            for table in ("admins", "portal_users", "cert_profiles", "datapackages", "events", "access_roles", "access_groups"):
                counts[table] = int(conn.execute(f"select count(*) from {table}").fetchone()[0])
            conn.execute("select 1").fetchone()
        db_ok = True
    except Exception as exc:
        db_error = str(exc)
    db_size = file_size(DB_PATH)
    wal_path = DB_PATH.with_name(DB_PATH.name + "-wal")
    return {
        "version": VERSION,
        "database": {
            "ok": db_ok,
            "path": str(DB_PATH),
            "bytes": db_size,
            "wal_bytes": file_size(wal_path),
            "counts": counts,
            "error": db_error,
        },
        "storage": {
            "package_dir": str(PACKAGE_DIR),
            "package_bytes": dir_size(PACKAGE_DIR),
            "cert_dir": str(CERT_DIR),
            "cert_bytes": dir_size(CERT_DIR),
        },
        "connections": {
            "clients": len(RELAY.snapshot()),
            "cot_port": COT_PORT,
            "cot_tls_port": COT_TLS_PORT,
            "http_port": HTTP_PORT,
            "https_port": HTTPS_PORT,
        },
        "runtime": {
            "started_at": STARTED_AT,
            "uptime_seconds": int(time.time() - parse_utc(STARTED_AT).timestamp()) if parse_utc(STARTED_AT) else 0,
            "hostname": socket.gethostname(),
            "container_status": "running",
        },
        "config": {
            "server_host": SERVER_HOST,
            "public_host": PUBLIC_HOST or SERVER_HOST,
            "http_bind": HTTP_BIND,
            "https_bind": HTTPS_BIND,
            "cot_bind": COT_BIND,
            "cot_tls_bind": COT_TLS_BIND,
            "max_upload_bytes": MAX_UPLOAD_BYTES,
        },
        "security": {
            "access_enforcement": ACCESS_CONTROL_ENFORCE,
            "cot_tls_require_client_cert": COT_TLS_REQUIRE_CLIENT_CERT,
            "allow_legacy_client_cert": ALLOW_LEGACY_CLIENT_CERT,
            "admin_auth_enabled": bool(ADMIN_TOKEN),
        },
        "wireguard": {
            "dashboard_url": WG_DASHBOARD_URL,
            "visible_from_container": False,
        },
        "updates": {
            **gui_update_status(),
            "release_url": RELEASES_URL,
            "repo_url": "https://github.com/C137LLC/TAKlite.git",
            "preserves": [".env", "taklite/data", "taklite/certs", "taklite/packages", "/etc/wireguard", "/root/taklite-admin", "WGDashboard config"],
        },
    }


def gui_update_status():
    request_dir = Path(GUI_UPDATE_REQUEST_DIR) if GUI_UPDATE_REQUEST_DIR else None
    request_runner = bool(request_dir and request_dir.is_dir())
    command_runner = bool(GUI_UPDATE_COMMAND.strip())
    last_status = read_json_file(request_dir / "status.json") if request_dir else None
    pending = bool(request_dir and (request_dir / "request.json").exists())
    processing = bool(request_dir and (request_dir / "processing.json").exists())
    return {
        "gui_runner_enabled": GUI_UPDATE_ENABLED and (request_runner or command_runner),
        "enabled": GUI_UPDATE_ENABLED and (request_runner or command_runner),
        "configured": request_runner or command_runner,
        "runner_mode": "request" if request_runner else "command" if command_runner else "disabled",
        "workdir": GUI_UPDATE_WORKDIR,
        "request_dir": GUI_UPDATE_REQUEST_DIR,
        "timeout_seconds": GUI_UPDATE_TIMEOUT_SECONDS,
        "pending": pending,
        "processing": processing,
        "last_status": last_status,
    }


def latest_release_status(refresh=False):
    now = time.time()
    if not refresh and UPDATE_STATUS_CACHE["status"] and now - UPDATE_STATUS_CACHE["checked_at"] < UPDATE_STATUS_CACHE_SECONDS:
        return UPDATE_STATUS_CACHE["status"]
    current_parts = version_tuple(VERSION)
    current_tag = version_tag(VERSION)
    status = {
        "current_version": VERSION,
        "current_tag": current_tag,
        "latest_tag": "",
        "latest_version": "",
        "update_available": False,
        "release_url": RELEASES_URL,
        "verified_asset": None,
        "verified_update_available": False,
        "checked_at": utc_now(),
        "check_error": "",
        **gui_update_status(),
    }
    try:
        req = Request(LATEST_RELEASE_API_URL, headers={"Accept": "application/vnd.github+json", "User-Agent": "TAKlite"})
        with urlopen(req, timeout=4) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        latest_tag = payload.get("tag_name", "")
        latest_parts = version_tuple(latest_tag)
        verified_asset = verified_release_asset(payload)
        status.update({
            "latest_tag": latest_tag,
            "latest_version": latest_tag.lstrip("v"),
            "release_url": payload.get("html_url") or RELEASES_URL,
            "update_available": bool(latest_parts and current_parts and latest_parts > current_parts),
            "verified_asset": verified_asset,
            "verified_update_available": bool(verified_asset and latest_parts and current_parts and latest_parts > current_parts),
        })
    except Exception as exc:
        status["check_error"] = str(exc)
    UPDATE_STATUS_CACHE["checked_at"] = now
    UPDATE_STATUS_CACHE["status"] = status
    return status


def verified_release_asset(payload):
    tag = payload.get("tag_name", "")
    expected_names = {f"TAKlite-{tag}.zip"} if tag else set()
    if tag.startswith("v"):
        expected_names.add(f"TAKlite-{tag[1:]}.zip")
    for asset in payload.get("assets") or []:
        name = asset.get("name", "")
        if expected_names and name not in expected_names:
            continue
        digest = asset.get("digest", "")
        match = re.fullmatch(r"sha256:([A-Fa-f0-9]{64})", digest or "")
        url = asset.get("browser_download_url", "")
        if match and url.startswith("https://github.com/"):
            return {"name": name, "url": url, "sha256": match.group(1).lower(), "digest": digest}
    return None


def validate_release_zip_url(url):
    url = (url or "").strip()
    if not re.fullmatch(r"https://github\.com/C137LLC/TAKlite/releases/download/v[0-9]+\.[0-9]+\.[0-9]+/[A-Za-z0-9_.-]+\.zip", url):
        raise ValueError("verified release zip URL is required")
    return url


def validate_sha256(value):
    value = (value or "").strip().lower()
    if not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("verified release zip SHA-256 is required")
    return value


def run_gui_update(confirm, target_tag="", release_zip_url="", expected_sha256=""):
    if not GUI_UPDATE_ENABLED:
        return {"ok": False, "error": "GUI update runner is disabled"}
    if confirm != "RUN_UPDATE":
        return {"ok": False, "error": "update confirmation is required"}
    request_dir = Path(GUI_UPDATE_REQUEST_DIR) if GUI_UPDATE_REQUEST_DIR else None
    if request_dir and request_dir.is_dir():
        request_file = request_dir / "request.json"
        processing_file = request_dir / "processing.json"
        if request_file.exists() or processing_file.exists():
            return {"ok": False, "error": "an update is already pending or running"}
        try:
            release_zip_url = validate_release_zip_url(release_zip_url)
            expected_sha256 = validate_sha256(expected_sha256)
        except ValueError as exc:
            return {"ok": False, "error": f"{exc}; GUI host updates require a verified release zip"}
        request = {
            "id": secrets.token_urlsafe(12),
            "requested_at": utc_now(),
            "current_version": VERSION,
            "target_tag": target_tag,
            "release_zip_url": release_zip_url,
            "expected_sha256": expected_sha256,
        }
        tmp_file = request_dir / f".request-{request['id']}.tmp"
        tmp_file.write_text(json.dumps(request, indent=2))
        tmp_file.replace(request_file)
        return {"ok": True, "queued": True, "request": request}
    if not GUI_UPDATE_COMMAND.strip():
        return {"ok": False, "error": "GUI update command is not configured"}
    workdir = Path(GUI_UPDATE_WORKDIR) if GUI_UPDATE_WORKDIR else None
    if workdir and not workdir.is_dir():
        return {"ok": False, "error": f"GUI update workdir does not exist: {workdir}"}
    started = utc_now()
    try:
        result = subprocess.run(
            shlex.split(GUI_UPDATE_COMMAND),
            cwd=str(workdir) if workdir else None,
            capture_output=True,
            text=True,
            timeout=GUI_UPDATE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "error": f"GUI update timed out after {GUI_UPDATE_TIMEOUT_SECONDS} seconds",
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "started_at": started,
            "finished_at": utc_now(),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "started_at": started, "finished_at": utc_now()}
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout[-12000:],
        "stderr": result.stderr[-12000:],
        "started_at": started,
        "finished_at": utc_now(),
    }


def heartbeat_loop():
    while True:
        time.sleep(10)
        RELAY.heartbeat()


def parse_upload(handler):
    ctype = handler.headers.get("Content-Type", "")
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        raise ValueError("empty upload")
    if length > MAX_UPLOAD_BYTES:
        raise ValueError(f"upload exceeds maximum size of {MAX_UPLOAD_BYTES} bytes")
    body = handler.rfile.read(length)
    if ctype.lower().startswith("multipart/form-data"):
        filename, data = parse_multipart_assetfile(ctype, body)
    else:
        filename, data = None, body
    validate_datapackage_upload(filename, data)
    return filename, data


def parse_multipart_assetfile(ctype, body):
    match = re.search(r'boundary="?([^";]+)"?', ctype, re.IGNORECASE)
    if not match:
        raise ValueError("multipart boundary missing")
    boundary = ("--" + match.group(1)).encode("utf-8")
    fallback_file = None
    for part in body.split(boundary):
        part = part.strip(b"\r\n")
        if not part or part == b"--" or b"\r\n\r\n" not in part:
            continue
        raw_headers, content = part.split(b"\r\n\r\n", 1)
        headers = raw_headers.decode("utf-8", "replace")
        name_match = re.search(r'name="([^"]+)"', headers, re.IGNORECASE)
        filename_match = re.search(r'filename="([^"]*)"', headers)
        filename = filename_match.group(1) if filename_match else None
        if content.endswith(b"\r\n"):
            content = content[:-2]
        field_name = name_match.group(1).lower() if name_match else ""
        if field_name in ("assetfile", "file", "upload", "data", "content", "contents"):
            return filename, content
        if filename and fallback_file is None:
            fallback_file = (filename, content)
    if fallback_file is not None:
        return fallback_file
    raise ValueError("missing multipart field assetfile")


def validate_datapackage_upload(filename, data):
    if not data:
        raise ValueError("empty upload")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"datapackage exceeds maximum size of {MAX_UPLOAD_BYTES} bytes")
    if data[:4] != b"PK\x03\x04" and data[:4] != b"PK\x05\x06" and data[:4] != b"PK\x07\x08":
        raise ValueError("datapackage must be a zip file")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            entries = zf.infolist()
            if len(entries) > MAX_ZIP_ENTRIES:
                raise ValueError(f"datapackage zip contains too many entries: {len(entries)}")
            total_uncompressed = 0
            total_compressed = 0
            for entry in entries:
                entry_path = PurePosixPath(entry.filename.replace("\\", "/"))
                if entry_path.is_absolute() or ".." in entry_path.parts:
                    raise ValueError(f"datapackage zip contains unsafe entry path: {entry.filename}")
                if entry.flag_bits & 0x1:
                    raise ValueError(f"datapackage zip contains encrypted entry: {entry.filename}")
                total_uncompressed += entry.file_size
                total_compressed += entry.compress_size
            if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
                raise ValueError(f"datapackage zip uncompressed size exceeds maximum of {MAX_ZIP_UNCOMPRESSED_BYTES} bytes")
            if total_uncompressed > 0:
                effective_compressed = max(total_compressed, 1)
                if total_uncompressed / effective_compressed > MAX_ZIP_COMPRESSION_RATIO:
                    raise ValueError("datapackage zip compression ratio is too high")
            bad = zf.testzip()
            if bad:
                raise ValueError(f"datapackage zip contains corrupt entry: {bad}")
    except zipfile.BadZipFile as exc:
        raise ValueError("datapackage must be a valid zip file") from exc


def upload_datapackage_from_request(handler, qs):
    creator_user_id = handler.authenticated_user_id()
    if ACCESS_CONTROL_ENFORCE and not creator_user_id:
        handler.send_json({"error": "client certificate identity required"}, HTTPStatus.FORBIDDEN)
        return
    filename, data = parse_upload(handler)
    hash_value = qs.get("hash", [""])[0]
    query_name = qs.get("filename", qs.get("name", [""]))[0]
    creator_uid = qs.get("creatorUid", qs.get("creatoruid", [""]))[0]
    package_name = normalize_datapackage_name(query_name or filename or f"{hash_value}.dp.zip")
    url = upsert_package(
        hash_value,
        package_name,
        creator_uid,
        data,
        tak_marti_base_url(),
        creator_user_id=creator_user_id,
        visibility="private",
    )
    handler.send_text(url)


def datapackage_content_row(handler, qs):
    hash_value = qs.get("hash", [""])[0]
    row = find_package(hash_value)
    if not row:
        handler.send_json({"error": "package not found"}, HTTPStatus.NOT_FOUND)
        return None
    if not package_visible_to_request(row, handler):
        handler.send_json({"error": "package not allowed"}, HTTPStatus.FORBIDDEN)
        return None
    package = Path(row["Path"])
    if not package.exists():
        handler.send_json({"error": "package file missing"}, HTTPStatus.NOT_FOUND)
        return None
    return row


def send_datapackage_to_clients(payload):
    hash_value = str(payload.get("hash", "")).strip()
    if not hash_value:
        raise ValueError("hash is required")
    row = find_package(hash_value)
    if not row:
        raise ValueError("datapackage not found")
    package = row_to_package(row)
    path = Path(row["Path"])
    if not path.exists():
        raise ValueError("datapackage file missing")
    send_all = bool(payload.get("all_clients", False))
    client_uids = [str(uid).strip() for uid in payload.get("client_uids", []) if str(uid).strip()]
    if not send_all and not client_uids:
        raise ValueError("select at least one connected client")
    result = RELAY.send_to_client_uids(fileshare_event(package), client_uids, send_all=send_all)
    result.update({
        "ok": result["sent"] > 0,
        "package": package,
        "url": tak_marti_content_url(hash_value),
    })
    if not result["ok"]:
        result["error"] = "no matching connected clients"
    return result


class HttpHandler(BaseHTTPRequestHandler):
    server_version = "TAKliteHTTP/0.2"

    def log_message(self, fmt, *args):
        print(f"{self.client_address[0]} - {fmt % args}")

    def bootstrap_authorized(self):
        return bool(admin_count() == 0 and ADMIN_TOKEN and self.headers.get("X-Admin-Token", "") == ADMIN_TOKEN)

    def authorized(self):
        if validate_session(self.headers.get("X-Session-Token", "")):
            return True
        if self.bootstrap_authorized():
            return True
        return False

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        if length > MAX_JSON_BYTES:
            raise ValueError(f"JSON body exceeds maximum size of {MAX_JSON_BYTES} bytes")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_text(self, text, status=HTTPStatus.OK, content_type="text/plain"):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_security_headers(content_type)
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, obj, status=HTTPStatus.OK):
        self.send_text(json.dumps(obj, indent=2), status, "application/json")

    def send_bytes(self, body, status=HTTPStatus.OK, content_type="application/octet-stream", extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.send_security_headers(content_type)
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, filename):
        filename = safe_download_name(filename, "datapackage.zip")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/x-zip-compressed")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_security_headers("application/x-zip-compressed")
        self.end_headers()
        with path.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile)

    def send_file_head(self, path, filename):
        filename = safe_download_name(filename, "datapackage.zip")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/x-zip-compressed")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_security_headers("application/x-zip-compressed")
        self.end_headers()

    def send_download(self, path, filename, content_type):
        filename = safe_download_name(filename)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_security_headers(content_type)
        self.end_headers()
        with path.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile)

    def send_static_file(self, path):
        content_types = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".ico": "image/x-icon",
            ".json": "application/json",
        }
        content_type = content_types.get(path.suffix.lower(), "application/octet-stream")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_security_headers(content_type)
        self.end_headers()
        with path.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile)

    def send_security_headers(self, content_type):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        if content_type.startswith("text/html"):
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'")

    def require_auth(self):
        if self.authorized():
            return True
        self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        return False

    def require_portal_auth(self):
        user = validate_portal_session(self.headers.get("X-Portal-Token", ""))
        if user:
            return user
        self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
        return None

    def client_cert_common_name(self):
        if hasattr(self.connection, "getpeercert"):
            try:
                return cert_common_name(self.connection.getpeercert() or {})
            except OSError:
                return ""
        return ""

    def authenticated_user_id(self):
        identity = client_identity_for_cert(self.client_cert_common_name())
        return identity["user_id"] if identity else None

    def do_HEAD(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)
        if path in ("/Marti/sync/content", "/sync/content"):
            row = datapackage_content_row(self, qs)
            if not row:
                return
            self.send_file_head(Path(row["Path"]), row["Name"])
            return
        self.send_response(HTTPStatus.NOT_FOUND)
        self.send_header("Content-Length", "0")
        self.send_security_headers("text/plain")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)
        if path == "/":
            index = STATIC_DIR / "index.html"
            if index.exists():
                self.send_static_file(index)
            else:
                self.send_text(INDEX_HTML, content_type="text/html; charset=utf-8")
            return
        if path.startswith("/assets/"):
            rel = Path(path.lstrip("/"))
            static_path = (STATIC_DIR / rel).resolve()
            try:
                static_path.relative_to(STATIC_DIR.resolve())
            except ValueError:
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            if not static_path.is_file():
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_static_file(static_path)
            return
        if path == "/connect":
            self.send_text(CONNECT_HTML, content_type="text/html; charset=utf-8")
            return
        public_match = re.match(r"^/connect/([A-Za-z0-9_-]+)\.dp\.zip$", path)
        if public_match:
            row = find_cert_profile_by_token(public_match.group(1))
            if not row or row["revoked_at"]:
                self.send_json({"error": "connection package not found"}, HTTPStatus.NOT_FOUND)
                return
            package = Path(row["datapackage_file"])
            if not package.exists():
                self.send_json({"error": "connection package file missing"}, HTTPStatus.NOT_FOUND)
                return
            self.send_download(package, package.name, "application/zip")
            return
        if path == "/api/bootstrap/status":
            self.send_json({"has_admin": admin_count() > 0, "token_required": bool(ADMIN_TOKEN)})
            return
        if path == "/api/me":
            if not self.require_auth():
                return
            username = validate_session(self.headers.get("X-Session-Token", "")) or "bootstrap-token"
            self.send_json({"authenticated": True, "username": username, "bootstrap": username == "bootstrap-token"})
            return
        if path == "/api/admin/2fa/status":
            username = validate_session(self.headers.get("X-Session-Token", ""))
            if not username:
                self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                return
            self.send_json(admin_totp_status(username))
            return
        if path == "/api/connect/me":
            user = self.require_portal_auth()
            if not user:
                return
            self.send_json({"authenticated": True, "user": portal_user_row(user), "cert_password": CERT_PASSWORD})
            return
        if path == "/api/connect/download":
            user = self.require_portal_auth()
            if not user:
                return
            if user["first_download_at"] and not user["allow_redownload"]:
                self.send_json({"error": "connection package already downloaded; contact your TAKlite admin for re-download"}, HTTPStatus.FORBIDDEN)
                return
            package = Path(user["datapackage_file"] or "")
            if not package.exists():
                self.send_json({"error": "connection package file missing"}, HTTPStatus.NOT_FOUND)
                return
            mark_portal_download(user["id"])
            self.send_download(package, package.name, "application/zip")
            return
        if path in ("/Marti/api/version", "/api/version"):
            self.send_text(VERSION)
            return
        if path in ("/Marti/api/version/config", "/api/version/config"):
            self.send_json({"version": 2, "type": "ServerConfig", "data": {"version": VERSION, "api": "2", "hostname": socket.gethostname()}})
            return
        if path in ("/Marti/api/clientEndPoints", "/api/clientEndPoints"):
            self.send_json(client_endpoints_response())
            return
        if path in ("/Marti/api/groups/groupCacheEnabled", "/api/groups/groupCacheEnabled"):
            self.send_json(False)
            return
        if path in ("/Marti/api/groups/all", "/api/groups/all"):
            self.send_json(marti_groups_response())
            return
        if path in ("/Marti/api/missions/invitations", "/api/missions/invitations"):
            self.send_json(mission_empty_response("MissionInvitationList"))
            return
        if path in ("/Marti/api/missions/all/invitations", "/api/missions/all/invitations"):
            self.send_json(mission_empty_response("MissionInvitationList"))
            return
        if path in ("/Marti/api/missions", "/api/missions"):
            self.send_json(mission_empty_response("MissionList"))
            return
        if re.match(r"^/(?:Marti/)?api/missions/[^/]+/(?:changes|contents|subscriptions|log)$", path):
            self.send_json(mission_empty_response("MissionDetailList"))
            return
        if path in ("/Marti/api/citrap", "/api/citrap"):
            self.send_json({"version": 2, "type": "CitrapList", "data": []})
            return
        if path in ("/Marti/sync/search", "/sync/search"):
            try:
                items = list_packages(self.authenticated_user_id(), ACCESS_CONTROL_ENFORCE)
                self.send_json({"resultCount": len(items), "results": items})
            except Exception as exc:
                print(f"TAKlite GET {path} failed: {exc}", flush=True)
                self.send_json({"error": str(exc), "resultCount": 0, "results": []}, HTTPStatus.BAD_REQUEST)
            return
        if path in ("/Marti/sync/missionquery", "/sync/missionquery"):
            try:
                hash_value = qs.get("hash", [""])[0]
                row = find_package(hash_value)
                if not row:
                    self.send_json({"error": "package not found"}, HTTPStatus.NOT_FOUND)
                    return
                if not package_visible_to_request(row, self):
                    self.send_json({"error": "package not allowed"}, HTTPStatus.FORBIDDEN)
                    return
                self.send_text(tak_marti_content_url(hash_value))
            except Exception as exc:
                print(f"TAKlite GET {path} failed: {exc}", flush=True)
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if path in ("/Marti/sync/content", "/sync/content"):
            try:
                row = datapackage_content_row(self, qs)
                if not row:
                    return
                self.send_file(Path(row["Path"]), row["Name"])
            except Exception as exc:
                print(f"TAKlite GET {path} failed: {exc}", flush=True)
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if path == "/certs/taklite-truststore.p12":
            if not LEGACY_CERT_DOWNLOADS:
                self.send_json({"error": "legacy cert downloads are disabled"}, HTTPStatus.FORBIDDEN)
                return
            truststore = CERT_DIR / "taklite-truststore.p12"
            if not truststore.exists():
                self.send_json({"error": "truststore not found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_download(truststore, "taklite-truststore.p12", "application/x-pkcs12")
            return
        if path == "/certs/taklite-atak-ssl.dp.zip":
            if not self.require_auth():
                return
            datapackage = CERT_DIR / "taklite-atak-ssl.dp.zip"
            if not datapackage.exists():
                self.send_json({"error": "certificate datapackage not found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_download(datapackage, "taklite-atak-ssl.dp.zip", "application/zip")
            return
        if path == "/certs/taklite-client.p12":
            if not self.require_auth():
                return
            client_cert = CERT_DIR / "taklite-client.p12"
            if not client_cert.exists():
                self.send_json({"error": "client certificate not found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_download(client_cert, "taklite-client.p12", "application/x-pkcs12")
            return
        if path == "/certs/10.66.66.1.p12":
            if not LEGACY_CERT_DOWNLOADS:
                self.send_json({"error": "legacy cert downloads are disabled"}, HTTPStatus.FORBIDDEN)
                return
            atak_truststore = CERT_DIR / "10.66.66.1.p12"
            if not atak_truststore.exists():
                self.send_json({"error": "ATAK truststore not found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_download(atak_truststore, "10.66.66.1.p12", "application/x-pkcs12")
            return
        if path == "/certs/taklite-ca.crt":
            ca_cert = CERT_DIR / "taklite-ca.crt"
            if not ca_cert.exists():
                self.send_json({"error": "ca certificate not found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_download(ca_cert, "taklite-ca.crt", "application/x-x509-ca-cert")
            return
        if path == "/api/health":
            tls_enabled = HTTPS_CERT.exists() and HTTPS_KEY.exists()
            self.send_json({"ok": True, "version": VERSION, "cot_port": COT_PORT, "cot_tls_port": COT_TLS_PORT if tls_enabled else None, "http_port": HTTP_PORT, "https_port": HTTPS_PORT if tls_enabled else None, "clients": len(RELAY.snapshot()), "packages": len(list_packages(enforce=False)), "auth_enabled": bool(ADMIN_TOKEN), "access_enforcement": ACCESS_CONTROL_ENFORCE})
            return
        if path == "/api/system-health":
            if not self.require_auth():
                return
            self.send_json(runtime_health())
            return
        if path == "/api/settings":
            if not self.require_auth():
                return
            self.send_json(editable_settings_status())
            return
        if path == "/api/firewall/status":
            if not self.require_auth():
                return
            self.send_json(firewall_status())
            return
        if path == "/api/admin/update/status":
            if not self.require_auth():
                return
            self.send_json(latest_release_status(refresh=qs.get("refresh", ["0"])[0] in ("1", "true", "yes")))
            return
        if path == "/api/ui-config":
            self.send_json({"wgDashboardUrl": WG_DASHBOARD_URL})
            return
        if path == "/api/datapackages":
            if not self.require_auth():
                return
            self.send_json({"items": list_packages(enforce=False)})
            return
        if path == "/api/clients":
            if not self.require_auth():
                return
            self.send_json({"items": RELAY.snapshot()})
            return
        if path == "/api/cert-profiles":
            if not self.require_auth():
                return
            self.send_json({"items": list_cert_profiles(), "cert_password": CERT_PASSWORD, "server_host": SERVER_HOST})
            return
        if path == "/api/portal-users":
            if not self.require_auth():
                return
            self.send_json({"items": list_portal_users(), "portal_url": f"{absolute_base_url(self)}/connect/"})
            return
        if path == "/api/access-control":
            if not self.require_auth():
                return
            self.send_json(access_summary())
            return
        if path == "/api/access-preview":
            if not self.require_auth():
                return
            self.send_json(access_preview(qs.get("user_id", ["0"])[0]))
            return
        if path == "/api/portal-users/qr":
            if not self.require_auth():
                return
            user_id = int(qs.get("id", ["0"])[0] or "0")
            user = find_portal_user(user_id)
            if not user:
                self.send_json({"error": "portal user not found"}, HTTPStatus.NOT_FOUND)
                return
            url = f"{absolute_base_url(self)}{portal_user_row(user)['portal_path']}"
            result = subprocess.run(["qrencode", "-t", "SVG", "-o", "-", url], capture_output=True)
            if result.returncode:
                self.send_json({"error": (result.stderr or b"qrencode failed").decode("utf-8", "replace")}, HTTPStatus.BAD_REQUEST)
                return
            self.send_bytes(result.stdout, content_type="image/svg+xml")
            return
        if path == "/api/cert-profiles/download":
            if not self.require_auth():
                return
            profile_id = int(qs.get("id", ["0"])[0] or "0")
            row = find_cert_profile(profile_id)
            if not row:
                self.send_json({"error": "connection package not found"}, HTTPStatus.NOT_FOUND)
                return
            if row["revoked_at"]:
                self.send_json({"error": "connection package is revoked"}, HTTPStatus.GONE)
                return
            package = Path(row["datapackage_file"])
            if not package.exists():
                self.send_json({"error": "connection package file missing"}, HTTPStatus.NOT_FOUND)
                return
            self.send_download(package, package.name, "application/zip")
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)
        try:
            if path == "/api/bootstrap/admin":
                if admin_count() > 0:
                    raise ValueError("admin user already exists")
                remote = self.client_address[0]
                if login_limited("bootstrap", remote, "bootstrap"):
                    self.send_json({"error": "too many failed attempts; try again later"}, HTTPStatus.TOO_MANY_REQUESTS)
                    return
                if not self.bootstrap_authorized():
                    record_login_failure("bootstrap", remote, "bootstrap")
                    self.send_json({"error": "bootstrap token required"}, HTTPStatus.UNAUTHORIZED)
                    return
                payload = self.read_json()
                username = create_admin(payload.get("username", ""), payload.get("password", ""))
                clear_login_failures("bootstrap", remote, "bootstrap")
                session = create_session(username)
                self.send_json({"ok": True, "username": username, "session": session})
                return
            if path == "/api/login":
                payload = self.read_json()
                remote = self.client_address[0]
                login_user = payload.get("username", "")
                if login_limited("admin", remote, login_user):
                    self.send_json({"error": "too many failed attempts; try again later"}, HTTPStatus.TOO_MANY_REQUESTS)
                    return
                username = authenticate_admin(payload.get("username", ""), payload.get("password", ""), payload.get("totp_code", ""))
                if not username:
                    record_login_failure("admin", remote, login_user)
                    if admin_requires_totp(payload.get("username", ""), payload.get("password", "")):
                        self.send_json({"error": "two-factor code required", "totp_required": True}, HTTPStatus.UNAUTHORIZED)
                    else:
                        self.send_json({"error": "invalid username or password"}, HTTPStatus.UNAUTHORIZED)
                    return
                clear_login_failures("admin", remote, username)
                self.send_json({"ok": True, "username": username, "session": create_session(username)})
                return
            if path == "/api/logout":
                token = self.headers.get("X-Session-Token", "")
                if token:
                    with db_connect() as conn:
                        conn.execute("delete from admin_sessions where token = ?", (token,))
                        conn.commit()
                self.send_json({"ok": True})
                return
            if path == "/api/admin/password":
                token = self.headers.get("X-Session-Token", "")
                username = validate_session(token)
                if not username:
                    self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                    return
                payload = self.read_json()
                current_password = payload.get("current_password", "")
                new_password = payload.get("new_password", "")
                confirm_password = payload.get("confirm_password", "")
                if new_password != confirm_password:
                    raise ValueError("new passwords do not match")
                change_admin_password(username, current_password, new_password, token)
                self.send_json({"ok": True, "username": username, "message": "admin password changed"})
                return
            if path == "/api/admin/2fa/setup":
                token = self.headers.get("X-Session-Token", "")
                username = validate_session(token)
                if not username:
                    self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                    return
                payload = self.read_json()
                self.send_json(create_admin_totp_setup(username, payload.get("current_password", "")))
                return
            if path == "/api/admin/2fa/enable":
                token = self.headers.get("X-Session-Token", "")
                username = validate_session(token)
                if not username:
                    self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                    return
                payload = self.read_json()
                self.send_json(enable_admin_totp(username, payload.get("current_password", ""), payload.get("totp_code", ""), current_token=token))
                return
            if path == "/api/admin/2fa/disable":
                token = self.headers.get("X-Session-Token", "")
                username = validate_session(token)
                if not username:
                    self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                    return
                payload = self.read_json()
                self.send_json(disable_admin_totp(username, payload.get("current_password", ""), payload.get("totp_code", ""), current_token=token))
                return
            if path == "/api/connect/login":
                payload = self.read_json()
                remote = self.client_address[0]
                login_user = payload.get("username", "")
                if login_limited("portal", remote, login_user):
                    self.send_json({"error": "too many failed attempts; try again later"}, HTTPStatus.TOO_MANY_REQUESTS)
                    return
                user = authenticate_portal_user(payload.get("username", ""), payload.get("password", ""))
                if not user:
                    record_login_failure("portal", remote, login_user)
                    self.send_json({"error": "invalid username or password"}, HTTPStatus.UNAUTHORIZED)
                    return
                clear_login_failures("portal", remote, user["username"])
                self.send_json({"ok": True, "session": create_portal_session(user["id"]), "user": portal_user_row(user), "cert_password": CERT_PASSWORD})
                return
            if path == "/api/connect/logout":
                portal_logout(self.headers.get("X-Portal-Token", ""))
                self.send_json({"ok": True})
                return
            if path == "/api/admin/update/run":
                if not self.require_auth():
                    return
                payload = self.read_json()
                result = run_gui_update(
                    payload.get("confirm", ""),
                    payload.get("target_tag", ""),
                    payload.get("release_zip_url", ""),
                    payload.get("expected_sha256", ""),
                )
                self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
                return
            if path == "/api/settings/apply":
                if not self.require_auth():
                    return
                result = queue_settings_update(self.read_json())
                self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
                return
            if path == "/api/firewall/apply":
                if not self.require_auth():
                    return
                result = queue_firewall_update(self.read_json())
                self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
                return
            if path in ("/Marti/sync/missionupload", "/sync/missionupload", "/Marti/sync/upload", "/sync/upload", "/Marti/sync/content", "/sync/content"):
                upload_datapackage_from_request(self, qs)
                return
            if path == "/api/datapackages/send":
                if not self.require_auth():
                    return
                result = send_datapackage_to_clients(self.read_json())
                self.send_json(result, HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST)
                return
            if path == "/api/datapackages/delete":
                if not self.require_auth():
                    return
                payload = self.read_json()
                hash_value = payload.get("hash", "")
                if not hash_value:
                    raise ValueError("hash is required")
                self.send_json(delete_package(hash_value, bool(payload.get("delete_file", True))))
                return
            if path == "/api/cert-profiles/create":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(create_cert_profile(payload.get("name", ""), payload.get("description", "")))
                return
            if path == "/api/portal-users/create":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(create_portal_user(
                    payload.get("username", ""),
                    payload.get("password", ""),
                    payload.get("display_name", ""),
                    payload.get("description", ""),
                    bool(payload.get("allow_redownload", False)),
                    payload.get("role_id"),
                    payload.get("group_ids", []),
                ))
                return
            if path == "/api/portal-users/bulk-create":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(create_bulk_portal_users(
                    payload.get("prefix", ""),
                    payload.get("count", 0),
                    payload.get("description", ""),
                    bool(payload.get("allow_redownload", False)),
                    absolute_base_url(self),
                    payload.get("role_id"),
                    payload.get("group_ids", []),
                ))
                return
            if path == "/api/access-roles/create":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(create_access_role(
                    payload.get("name", ""),
                    payload.get("description", ""),
                    bool(payload.get("can_see_all", False)),
                    bool(payload.get("can_send_all", False)),
                    bool(payload.get("can_see_own_groups", True)),
                    bool(payload.get("can_send_own_groups", True)),
                ))
                return
            if path == "/api/access-roles/update":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(update_access_role(
                    int(payload.get("id", 0)),
                    payload.get("name", ""),
                    payload.get("description", ""),
                    bool(payload.get("can_see_all", False)),
                    bool(payload.get("can_send_all", False)),
                    bool(payload.get("can_see_own_groups", True)),
                    bool(payload.get("can_send_own_groups", True)),
                ))
                return
            if path == "/api/access-roles/delete":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(delete_access_role(int(payload.get("id", 0))))
                return
            if path == "/api/access-groups/create":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(create_access_group(payload.get("name", ""), payload.get("description", ""), payload.get("color", "")))
                return
            if path == "/api/access-groups/update":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(update_access_group(int(payload.get("id", 0)), payload.get("name", ""), payload.get("description", ""), payload.get("color", "")))
                return
            if path == "/api/access-groups/delete":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(delete_access_group(int(payload.get("id", 0))))
                return
            if path == "/api/access-users/set":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(set_user_access(int(payload.get("user_id", 0)), payload.get("role_id"), payload.get("group_ids", [])))
                return
            if path == "/api/access-users/bulk-set":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(bulk_set_user_access(payload.get("user_ids", []), payload.get("role_id"), payload.get("group_ids", []), payload.get("group_mode", "replace")))
                return
            if path == "/api/access-links/set":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(set_policy_link(
                    int(payload.get("source_group_id", 0)),
                    int(payload.get("target_group_id", 0)),
                    bool(payload.get("can_see", False)),
                    bool(payload.get("can_send", False)),
                ))
                return
            if path == "/api/portal-users/reset-password":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(reset_portal_password(int(payload.get("id", 0)), payload.get("password", "")))
                return
            if path == "/api/portal-users/edit":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(edit_portal_user(int(payload.get("id", 0)), payload.get("display_name", ""), payload.get("description", "")))
                return
            if path == "/api/portal-users/redownload":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(set_portal_redownload(int(payload.get("id", 0)), bool(payload.get("allow_redownload", False))))
                return
            if path == "/api/portal-users/reissue":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(reissue_portal_user(int(payload.get("id", 0))))
                return
            if path == "/api/portal-users/revoke":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(revoke_portal_user(int(payload.get("id", 0))))
                return
            if path == "/api/portal-users/delete":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(delete_portal_user(int(payload.get("id", 0)), bool(payload.get("delete_profile", False))))
                return
            if path == "/api/cert-profiles/revoke":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(revoke_cert_profile(int(payload.get("id", 0))))
                return
            if path == "/api/cert-profiles/delete":
                if not self.require_auth():
                    return
                payload = self.read_json()
                self.send_json(delete_cert_profile(int(payload.get("id", 0)), bool(payload.get("delete_files", True))))
                return
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            print(f"TAKlite POST {path} failed: {exc}", flush=True)
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        qs = parse_qs(parsed.query)
        if path in ("/Marti/api/missions/citrap/subscription", "/api/missions/citrap/subscription"):
            self.send_json({"version": 2, "type": "MissionSubscription", "data": {"subscribed": True}})
            return
        if path in ("/Marti/sync/content", "/sync/content", "/Marti/sync/upload", "/sync/upload", "/Marti/sync/missionupload", "/sync/missionupload"):
            try:
                upload_datapackage_from_request(self, qs)
            except Exception as exc:
                print(f"TAKlite PUT {path} failed: {exc}", flush=True)
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        match = re.match(r"^/(?:Marti/)?api/sync/metadata/([^/]+)/tool$", path)
        if not match:
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        hash_value = unquote(match.group(1))
        length = int(self.headers.get("Content-Length", "0") or "0")
        tool = self.rfile.read(length).decode("utf-8", "replace").strip() or "public"
        visibility = tool.lower() if tool.lower() in ("public", "private") else None
        with db_connect() as conn:
            if visibility:
                conn.execute("update datapackages set Tool = ?, Visibility = ? where Hash = ?", (tool, visibility, hash_value))
            else:
                conn.execute("update datapackages set Tool = ? where Hash = ?", (tool, hash_value))
            conn.commit()
        self.send_text("OK")


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TAKlite</title>
<style>
body{margin:0;font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#f6f7f4;color:#1d231f}
header{box-sizing:border-box;width:100%;background:#17201b;color:white;padding:18px 24px;display:flex;gap:16px;justify-content:space-between;align-items:center}
h1{font-size:20px;margin:0;white-space:nowrap}#health{min-width:0;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.wrap{box-sizing:border-box;max-width:1180px;margin:0 auto;padding:20px 24px}
button,input{font:inherit;border:1px solid #b9c0ba;border-radius:6px;padding:8px 10px}
button{background:#315c46;color:white;border-color:#315c46;cursor:pointer}button.secondary{background:#eef1ec;color:#1d231f;border-color:#b9c0ba}.danger{background:#8d2d28;border-color:#8d2d28}
button:disabled{opacity:.55;cursor:not-allowed}.grid{display:grid;grid-template-columns:1fr;gap:22px}.section{min-width:0}h2{font-size:16px;margin:18px 0 10px}
table{width:100%;border-collapse:collapse;background:white;border:1px solid #d8ddd8}th,td{text-align:left;padding:9px;border-bottom:1px solid #e6e9e4;font-size:14px;vertical-align:top}
th{background:#eef1ec}code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;word-break:break-all}.muted{color:#66736a}.bar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}.status{min-height:24px;margin:10px 0}.actions{display:flex;gap:7px;flex-wrap:wrap}.empty{padding:14px;background:white;border:1px solid #d8ddd8}.nowrap{white-space:nowrap}.auth{max-width:520px;background:white;border:1px solid #d8ddd8;padding:18px}.auth input,.create input{box-sizing:border-box;width:100%;margin:5px 0 10px}.create{display:grid;grid-template-columns:minmax(170px,240px) 1fr auto;gap:8px;align-items:end}.tag{display:inline-block;padding:2px 7px;border-radius:999px;background:#eef1ec}.revoked{background:#f4d9d7;color:#69201b}
@media(max-width:760px){.create{grid-template-columns:1fr}.wrap{padding:16px 14px}table{display:block;overflow-x:auto;white-space:nowrap}}
</style>
</head>
<body><header><h1>TAKlite</h1><span id="health">checking</span></header>
<main class="wrap"><div id="toolbar" class="bar"></div><div id="status" class="status"></div><div id="content" class="grid">Loading...</div></main>
<script>
const toolbar=document.getElementById('toolbar'),statusEl=document.getElementById('status'),content=document.getElementById('content'),healthEl=document.getElementById('health');
let session=localStorage.getItem('takliteSession')||'';
function headers(extra={}){let h={'Content-Type':'application/json',...extra};if(session)h['X-Session-Token']=session;return h}
async function api(p,o={}){const r=await fetch(p,{...o,headers:{...headers(),...(o.headers||{})}});const b=await r.json();if(!r.ok)throw new Error(b.error||r.statusText);return b}
function esc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function fmtBytes(n){n=Number(n)||0;if(n<1024)return `${n} B`;if(n<1048576)return `${(n/1024).toFixed(1)} KB`;return `${(n/1048576).toFixed(1)} MB`}
function fmtTime(s){if(!s)return '<span class="muted">never</span>';return esc(new Date(s).toLocaleString())}
function fmtUptime(s){if(!s)return '';let ms=Date.now()-new Date(s).getTime();if(!Number.isFinite(ms)||ms<0)ms=0;let sec=Math.floor(ms/1000),h=Math.floor(sec/3600),m=Math.floor((sec%3600)/60);if(h)return `${h}h ${m}m`;if(m)return `${m}m ${sec%60}s`;return `${sec}s`}
async function init(){try{const s=await fetch('/api/bootstrap/status').then(r=>r.json());if(!session){renderAuth(s);return}await load()}catch(e){content.textContent=e.message;statusEl.textContent='Unable to initialize.'}}
function renderAuth(s){toolbar.innerHTML='';healthEl.textContent='login required';statusEl.textContent=s.has_admin?'Sign in to manage TAKlite.':'Create the first admin account with the install token.';content.innerHTML=s.has_admin?loginHtml():setupHtml();bindAuth()}
function loginHtml(){return `<section class="auth"><h2>Admin Login</h2><input id="loginUser" autocomplete="username" placeholder="Username"><input id="loginPass" autocomplete="current-password" type="password" placeholder="Password"><button id="loginBtn">Log In</button></section>`}
function setupHtml(){return `<section class="auth"><h2>First Admin Setup</h2><input id="setupToken" type="password" placeholder="Install token"><input id="setupUser" autocomplete="username" placeholder="Username"><input id="setupPass" autocomplete="new-password" type="password" placeholder="Password"><button id="setupBtn">Create Admin</button></section>`}
function bindAuth(){const login=document.getElementById('loginBtn');if(login)login.onclick=async()=>{try{const b=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:document.getElementById('loginUser').value,password:document.getElementById('loginPass').value})}).then(async r=>{const b=await r.json();if(!r.ok)throw new Error(b.error||r.statusText);return b});session=b.session;localStorage.setItem('takliteSession',session);await load()}catch(e){statusEl.textContent=e.message}};const setup=document.getElementById('setupBtn');if(setup)setup.onclick=async()=>{try{const b=await fetch('/api/bootstrap/admin',{method:'POST',headers:{'Content-Type':'application/json','X-Admin-Token':document.getElementById('setupToken').value},body:JSON.stringify({username:document.getElementById('setupUser').value,password:document.getElementById('setupPass').value})}).then(async r=>{const b=await r.json();if(!r.ok)throw new Error(b.error||r.statusText);return b});session=b.session;localStorage.setItem('takliteSession',session);await load()}catch(e){statusEl.textContent=e.message}}}
async function load(){try{toolbar.innerHTML='<button id="refresh">Refresh</button><button id="logout" class="secondary">Log Out</button>';document.getElementById('refresh').onclick=load;document.getElementById('logout').onclick=logout;const health=await fetch('/api/health').then(r=>r.json());healthEl.textContent=`${health.clients} clients, ${health.packages} packages`;const [packages,clients,profiles,portal]=await Promise.all([api('/api/datapackages'),api('/api/clients'),api('/api/cert-profiles'),api('/api/portal-users')]);render(packages.items||[],clients.items||[],profiles.items||[],portal.items||[],profiles.cert_password,portal.portal_url);statusEl.textContent=`Loaded ${(clients.items||[]).length} client(s), ${(packages.items||[]).length} package(s), ${(profiles.items||[]).length} connection package(s), ${(portal.items||[]).length} portal user(s).`}catch(e){if(String(e.message).includes('unauthorized')){session='';localStorage.removeItem('takliteSession');init();return}content.textContent=e.message;statusEl.textContent='Unable to load.'}}
function render(packages,clients,profiles,portalUsers,certPassword,portalUrl){content.innerHTML=`<section class="section"><h2>Connected Clients</h2>${clientTable(clients)}</section><section class="section"><h2>Datapackages</h2>${packageTable(packages)}</section><section class="section"><h2>Connection Users</h2>${portalCreate()}${portalTable(portalUsers,portalUrl)}</section><section class="section"><h2>Connection Packages</h2>${profileCreate()}${profileTable(profiles,certPassword)}</section>`;bindActions()}
function clientTable(items){if(!items.length)return '<div class="empty">No connected clients.</div>';let rows=items.map(x=>`<tr><td>${esc(x.callsign||'Unknown')}</td><td><code>${esc(x.uid||'')}</code></td><td class="nowrap">${esc(x.ip||'')}</td><td>${esc(x.transport||'tcp')}</td><td>${esc(x.peer_cert_cn||'')}</td><td class="nowrap">${fmtUptime(x.connected_at)}</td><td>${fmtTime(x.connected_at)}</td><td>${fmtTime(x.last_seen)}</td></tr>`).join('');return `<table><thead><tr><th>Name</th><th>UID</th><th>IP</th><th>Mode</th><th>Client Cert</th><th>Uptime</th><th>Connected</th><th>Last Seen</th></tr></thead><tbody>${rows}</tbody></table>`}
function packageTable(items){if(!items.length)return '<div class="empty">No datapackages yet.</div>';let rows=items.map(x=>`<tr><td>${esc(x.Name)}</td><td><code>${esc(x.Hash)}</code></td><td class="nowrap">${fmtBytes(x.Size)}</td><td>${esc(x.Tool||'')}</td><td>${fmtTime(x.SubmissionDateTime)}</td><td>${esc(x.CreatorUid)}</td><td><div class="actions"><a href="/Marti/sync/content?hash=${encodeURIComponent(x.Hash)}" download="${esc(x.Name)}"><button class="secondary" type="button">Download</button></a><button class="danger" data-hash="${esc(x.Hash)}">Delete</button></div></td></tr>`).join('');return `<table><thead><tr><th>Name</th><th>Hash</th><th>Size</th><th>Tool</th><th>Submitted</th><th>Creator</th><th>Action</th></tr></thead><tbody>${rows}</tbody></table>`}
function profileCreate(){return `<div class="create"><label>Name<input id="profileName" placeholder="e.g. alpha-phone"></label><label>Description<input id="profileDesc" placeholder="Optional note"></label><button id="createProfile">Create DP.zip</button></div>`}
function portalCreate(){return `<div class="create"><label>Username<input id="portalUser" autocomplete="off" placeholder="e.g. alpha-phone"></label><label>Password<input id="portalPass" autocomplete="new-password" type="password" placeholder="User download password"></label><label>Description<input id="portalDesc" placeholder="Optional note"></label><label><input id="portalRedownload" type="checkbox" style="width:auto;margin-right:6px">Allow re-download</label><button id="createPortal">Create User</button></div>`}
function publicUrl(x){return `${location.origin}${x.public_download_path||''}`}
function portalAbs(path){return `${location.origin}${path||'/connect/'}`}
function portalTable(items,portalUrl){let hint=`<p class="muted">Client portal: <code>${esc(portalUrl||portalAbs('/connect/'))}</code></p>`;if(!items.length)return hint+'<div class="empty">No connection users yet.</div>';let rows=items.map(x=>{let url=portalAbs(x.portal_path);return `<tr><td>${esc(x.username)}<br><span class="muted">${esc(x.display_name||'')}</span><br><span class="muted">${esc(x.description||'')}</span></td><td>${x.revoked?'<span class="tag revoked">revoked</span>':'<span class="tag">active</span>'}</td><td><code>${esc(url)}</code><br><code>${esc(x.connect_string||'')}</code></td><td>${x.download_count||0}<br><span class="muted">first ${fmtTime(x.first_download_at)}</span><br><span class="muted">last ${fmtTime(x.last_download_at)}</span></td><td>${x.allow_redownload?'yes':'no'}</td><td><div class="actions"><button class="secondary" data-download-profile="${x.cert_profile_id}" ${x.revoked?'disabled':''}>Download DP.zip</button><button class="secondary" data-copy-url="${esc(url)}" ${x.revoked?'disabled':''}>Copy URL</button><button class="secondary" data-qr-user="${x.id}" ${x.revoked?'disabled':''}>QR</button><button class="secondary" data-edit-user="${x.id}" data-display="${esc(x.display_name||'')}" data-description="${esc(x.description||'')}" ${x.revoked?'disabled':''}>Edit</button><button class="secondary" data-reset-user="${x.id}" ${x.revoked?'disabled':''}>Reset Password</button><button class="secondary" data-toggle-redownload="${x.id}" data-allow="${x.allow_redownload?'0':'1'}" ${x.revoked?'disabled':''}>${x.allow_redownload?'Disable':'Allow'} Re-download</button><button data-reissue-user="${x.id}">Reissue</button><button class="danger" data-revoke-user="${x.id}" ${x.revoked?'disabled':''}>Revoke</button><button class="danger" data-delete-user="${x.id}">Delete</button></div></td></tr>`}).join('');return hint+`<table><thead><tr><th>User</th><th>Status</th><th>Portal / Connection</th><th>Downloads</th><th>Re-download</th><th>Action</th></tr></thead><tbody>${rows}</tbody></table>`}
function profileTable(items,certPassword){let hint=`<p class="muted">Certificate password: <code>${esc(certPassword||'')}</code></p>`;if(!items.length)return hint+'<div class="empty">No connection packages yet.</div>';let rows=items.map(x=>{let url=publicUrl(x);return `<tr><td>${esc(x.name)}</td><td>${x.revoked?'<span class="tag revoked">revoked</span>':'<span class="tag">active</span>'}</td><td><code>${esc(x.connect_string)}</code><br><code>${esc(url)}</code></td><td>${esc(x.description)}</td><td>${fmtTime(x.created_at)}</td><td><div class="actions"><button class="secondary" data-download-profile="${x.id}" ${x.revoked?'disabled':''}>Download DP.zip</button><button class="secondary" data-copy-url="${esc(url)}" ${x.revoked?'disabled':''}>Copy URL</button><button data-revoke-profile="${x.id}" ${x.revoked?'disabled':''}>Revoke</button><button class="danger" data-delete-profile="${x.id}">Delete</button></div></td></tr>`}).join('');return hint+`<table><thead><tr><th>Name</th><th>Status</th><th>Connection / URL</th><th>Description</th><th>Created</th><th>Action</th></tr></thead><tbody>${rows}</tbody></table>`}
function bindActions(){const create=document.getElementById('createProfile');if(create)create.onclick=async()=>{try{await api('/api/cert-profiles/create',{method:'POST',body:JSON.stringify({name:document.getElementById('profileName').value,description:document.getElementById('profileDesc').value})});statusEl.textContent='Connection package created.';await load()}catch(e){statusEl.textContent=e.message}};const createPortal=document.getElementById('createPortal');if(createPortal)createPortal.onclick=async()=>{try{let user=document.getElementById('portalUser').value;await api('/api/portal-users/create',{method:'POST',body:JSON.stringify({username:user,password:document.getElementById('portalPass').value,description:document.getElementById('portalDesc').value,allow_redownload:document.getElementById('portalRedownload').checked})});statusEl.textContent=`Connection user ${user} created.`;await load()}catch(e){statusEl.textContent=e.message}};content.querySelectorAll('button[data-hash]').forEach(btn=>btn.onclick=async()=>{if(!confirm('Delete this datapackage from TAKlite?'))return;await api('/api/datapackages/delete',{method:'POST',body:JSON.stringify({hash:btn.dataset.hash,delete_file:true})});await load();});content.querySelectorAll('button[data-revoke-profile]').forEach(btn=>btn.onclick=async()=>{if(!confirm('Revoke this connection package?'))return;await api('/api/cert-profiles/revoke',{method:'POST',body:JSON.stringify({id:btn.dataset.revokeProfile})});await load()});content.querySelectorAll('button[data-delete-profile]').forEach(btn=>btn.onclick=async()=>{if(!confirm('Delete this connection package and generated files?'))return;await api('/api/cert-profiles/delete',{method:'POST',body:JSON.stringify({id:btn.dataset.deleteProfile,delete_files:true})});await load()});content.querySelectorAll('button[data-download-profile]').forEach(btn=>btn.onclick=()=>downloadProfile(btn.dataset.downloadProfile));content.querySelectorAll('button[data-copy-url]').forEach(btn=>btn.onclick=async()=>{await navigator.clipboard.writeText(btn.dataset.copyUrl);statusEl.textContent='URL copied.'});content.querySelectorAll('button[data-qr-user]').forEach(btn=>btn.onclick=()=>showQr(btn.dataset.qrUser));content.querySelectorAll('button[data-edit-user]').forEach(btn=>btn.onclick=async()=>{let display=prompt('Display name',btn.dataset.display||'');if(display===null)return;let description=prompt('Description / note',btn.dataset.description||'');if(description===null)return;await api('/api/portal-users/edit',{method:'POST',body:JSON.stringify({id:btn.dataset.editUser,display_name:display,description})});await load()});content.querySelectorAll('button[data-reset-user]').forEach(btn=>btn.onclick=async()=>{let password=prompt('New portal password, at least 8 characters');if(!password)return;await api('/api/portal-users/reset-password',{method:'POST',body:JSON.stringify({id:btn.dataset.resetUser,password})});await load()});content.querySelectorAll('button[data-toggle-redownload]').forEach(btn=>btn.onclick=async()=>{await api('/api/portal-users/redownload',{method:'POST',body:JSON.stringify({id:btn.dataset.toggleRedownload,allow_redownload:btn.dataset.allow==='1'})});await load()});content.querySelectorAll('button[data-reissue-user]').forEach(btn=>btn.onclick=async()=>{if(!confirm('Reissue this user with a new certificate package? Old package will be revoked.'))return;await api('/api/portal-users/reissue',{method:'POST',body:JSON.stringify({id:btn.dataset.reissueUser})});await load()});content.querySelectorAll('button[data-revoke-user]').forEach(btn=>btn.onclick=async()=>{if(!confirm('Revoke this user and their certificate package?'))return;await api('/api/portal-users/revoke',{method:'POST',body:JSON.stringify({id:btn.dataset.revokeUser})});await load()});content.querySelectorAll('button[data-delete-user]').forEach(btn=>btn.onclick=async()=>{if(!confirm('Delete this user? Choose OK again to also delete their generated certificate package files.'))return;let deleteProfile=confirm('Delete generated DP.zip/certificate package files too?');await api('/api/portal-users/delete',{method:'POST',body:JSON.stringify({id:btn.dataset.deleteUser,delete_profile:deleteProfile})});await load()})}
async function downloadProfile(id){const r=await fetch(`/api/cert-profiles/download?id=${encodeURIComponent(id)}`,{headers:headers({})});if(!r.ok){let b=await r.json().catch(()=>({error:r.statusText}));throw new Error(b.error||r.statusText)}let blob=await r.blob();let name=(r.headers.get('Content-Disposition')||'').match(/filename="([^"]+)"/)?.[1]||'taklite-connection.dp.zip';let a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
async function showQr(id){const r=await fetch(`/api/portal-users/qr?id=${encodeURIComponent(id)}`,{headers:headers({})});if(!r.ok){let b=await r.json().catch(()=>({error:r.statusText}));throw new Error(b.error||r.statusText)}let blob=await r.blob();let url=URL.createObjectURL(blob);let w=window.open('','takliteQr','width=420,height=460');w.document.write(`<title>TAKlite QR</title><body style="font-family:system-ui;text-align:center;padding:20px"><img src="${url}" style="width:320px;height:320px"><p>Scan after VPN is connected.</p></body>`)}
async function logout(){try{await api('/api/logout',{method:'POST',body:'{}'})}catch(e){}session='';localStorage.removeItem('takliteSession');init()}
init();
setInterval(load,15000);
</script></body></html>"""


CONNECT_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TAKlite Connect</title>
<style>
body{margin:0;font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#f6f7f4;color:#1d231f}
header{background:#17201b;color:white;padding:18px 22px}h1{font-size:20px;margin:0}.wrap{max-width:520px;margin:0 auto;padding:26px 18px}
.panel{background:white;border:1px solid #d8ddd8;border-radius:8px;padding:18px}h2{font-size:18px;margin:0 0 12px}
label{display:block;font-weight:600;margin:12px 0 4px}input,button{box-sizing:border-box;width:100%;font:inherit;border:1px solid #b9c0ba;border-radius:6px;padding:10px}
button{margin-top:14px;background:#315c46;color:white;border-color:#315c46;cursor:pointer}.secondary{background:#eef1ec;color:#1d231f;border-color:#b9c0ba}
.status{min-height:24px;margin:14px 0;color:#455349}.muted{color:#66736a}code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;word-break:break-all}
</style>
</head>
<body><header><h1>TAKlite Connect</h1></header><main class="wrap"><div id="status" class="status"></div><section id="content" class="panel"></section></main>
<script>
const statusEl=document.getElementById('status'),content=document.getElementById('content');
let portalSession=localStorage.getItem('taklitePortalSession')||'';
function esc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function initialUser(){return new URLSearchParams(location.search).get('u')||''}
function portalHeaders(extra={}){let h={'Content-Type':'application/json',...extra};if(portalSession)h['X-Portal-Token']=portalSession;return h}
async function portalApi(p,o={}){const r=await fetch(p,{...o,headers:{...portalHeaders(),...(o.headers||{})}});const b=await r.json();if(!r.ok)throw new Error(b.error||r.statusText);return b}
function renderLogin(){content.innerHTML=`<h2>Download Connection Package</h2><p class="muted">Sign in after WireGuard VPN is connected.</p><label>Username</label><input id="u" autocomplete="username" value="${esc(initialUser())}"><label>Password</label><input id="p" autocomplete="current-password" type="password"><button id="login">Log In</button>`;document.getElementById('login').onclick=login}
async function login(){try{const b=await portalApi('/api/connect/login',{method:'POST',body:JSON.stringify({username:document.getElementById('u').value,password:document.getElementById('p').value})});portalSession=b.session;localStorage.setItem('taklitePortalSession',portalSession);renderUser(b.user,b.cert_password)}catch(e){statusEl.textContent=e.message}}
function renderUser(user,certPassword){let blocked=user.first_download_at&&!user.allow_redownload;content.innerHTML=`<h2>${esc(user.display_name||user.username)}</h2><p class="muted">Connection: <code>${esc(user.connect_string)}</code></p><p class="muted">Certificate password: <code>${esc(certPassword||'')}</code></p>${blocked?'<p>This package was already downloaded. Contact your TAKlite admin to allow another download or reissue your package.</p>':'<button id="download">Download DP.zip</button>'}<button id="logout" class="secondary">Log Out</button>`;let dl=document.getElementById('download');if(dl)dl.onclick=download;document.getElementById('logout').onclick=logout;statusEl.textContent='Ready.'}
async function download(){try{const r=await fetch('/api/connect/download',{headers:{'X-Portal-Token':portalSession}});if(!r.ok){let b=await r.json().catch(()=>({error:r.statusText}));throw new Error(b.error||r.statusText)}let blob=await r.blob();let name=(r.headers.get('Content-Disposition')||'').match(/filename="([^"]+)"/)?.[1]||'taklite-connection.dp.zip';let a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),1000);statusEl.textContent='Downloaded. Import the DP.zip in ATAK or WinTAK.';setTimeout(check,1000)}catch(e){statusEl.textContent=e.message}}
async function logout(){try{await portalApi('/api/connect/logout',{method:'POST',body:'{}'})}catch(e){}portalSession='';localStorage.removeItem('taklitePortalSession');renderLogin()}
async function check(){if(!portalSession){renderLogin();return}try{const b=await portalApi('/api/connect/me');renderUser(b.user,b.cert_password)}catch(e){portalSession='';localStorage.removeItem('taklitePortalSession');renderLogin()}}
check();
</script></body></html>"""


def main():
    if not CERT_PASSWORD:
        raise RuntimeError("TAKLITE_CERT_PASSWORD is required")
    if AUTO_INIT_CERTS:
        ensure_base_certs()
    init_db()
    cot_server = CotServer((COT_BIND, COT_PORT), CotHandler, "tcp")
    http_server = ThreadingHTTPServer((HTTP_BIND, HTTP_PORT), HttpHandler)
    threading.Thread(target=cot_server.serve_forever, daemon=True).start()
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    if HTTPS_CERT.exists() and HTTPS_KEY.exists():
        cot_tls_context = server_tls_context(request_client_cert=True)
        https_context = server_tls_context(request_client_cert=True)
        cot_tls_server = CotServer((COT_TLS_BIND, COT_TLS_PORT), CotHandler, "tls")
        cot_tls_server.socket = cot_tls_context.wrap_socket(cot_tls_server.socket, server_side=True)
        threading.Thread(target=cot_tls_server.serve_forever, daemon=True).start()
        https_server = ThreadingHTTPServer((HTTPS_BIND, HTTPS_PORT), HttpHandler)
        https_server.socket = https_context.wrap_socket(https_server.socket, server_side=True)
        threading.Thread(target=https_server.serve_forever, daemon=True).start()
        if CLIENT_CA.exists():
            client_cert_mode = "client cert required/verified" if COT_TLS_REQUIRE_CLIENT_CERT else "client cert optional/verified"
        else:
            client_cert_mode = "client cert required; CA missing" if COT_TLS_REQUIRE_CLIENT_CERT else "client cert not verified; CA missing"
        print(f"TAKlite TLS CoT listening on {COT_TLS_BIND}:{COT_TLS_PORT} ({client_cert_mode})")
        print(f"TAKlite HTTPS/Marti listening on {HTTPS_BIND}:{HTTPS_PORT}")
    else:
        print(f"TAKlite HTTPS disabled; missing {HTTPS_CERT} or {HTTPS_KEY}")
    print(f"TAKlite CoT listening on {COT_BIND}:{COT_PORT}")
    print(f"TAKlite HTTP/Marti/Admin listening on {HTTP_BIND}:{HTTP_PORT}")
    http_server.serve_forever()


if __name__ == "__main__":
    main()
