#!/usr/bin/env python3
import hashlib
import hmac
import html
import io
import json
import os
import re
import secrets
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
from pathlib import Path
from socketserver import ThreadingMixIn, TCPServer, BaseRequestHandler
from urllib.parse import parse_qs, quote, unquote, urlparse

HTTP_BIND = os.environ.get("TAKLITE_HTTP_BIND", "0.0.0.0")
HTTP_PORT = int(os.environ.get("TAKLITE_HTTP_PORT", "8080"))
HTTPS_BIND = os.environ.get("TAKLITE_HTTPS_BIND", "0.0.0.0")
HTTPS_PORT = int(os.environ.get("TAKLITE_HTTPS_PORT", "8443"))
HTTPS_CERT = Path(os.environ.get("TAKLITE_HTTPS_CERT", "/certs/taklite.crt"))
HTTPS_KEY = Path(os.environ.get("TAKLITE_HTTPS_KEY", "/certs/taklite.key"))
CERT_DIR = HTTPS_CERT.parent
CLIENT_CA = Path(os.environ.get("TAKLITE_CLIENT_CA", "/certs/taklite-ca.crt"))
COT_BIND = os.environ.get("TAKLITE_COT_BIND", "0.0.0.0")
COT_PORT = int(os.environ.get("TAKLITE_COT_PORT", "58087"))
COT_TLS_BIND = os.environ.get("TAKLITE_COT_TLS_BIND", "0.0.0.0")
COT_TLS_PORT = int(os.environ.get("TAKLITE_COT_TLS_PORT", "8089"))
ADMIN_TOKEN = os.environ.get("TAKLITE_ADMIN_TOKEN", "")
PUBLIC_HOST = os.environ.get("TAKLITE_PUBLIC_HOST", "")
SERVER_HOST = os.environ.get("TAKLITE_SERVER_HOST", PUBLIC_HOST or "10.66.66.1")
CERT_PASSWORD = os.environ.get("TAKLITE_CERT_PASSWORD", "")
DB_PATH = Path(os.environ.get("TAKLITE_DB", "/data/taklite.sqlite3"))
PACKAGE_DIR = Path(os.environ.get("TAKLITE_PACKAGE_DIR", "/packages"))
VERSION = "TAKlite 0.2"
PORTAL_SESSION_HOURS = 2
MAX_UPLOAD_BYTES = int(os.environ.get("TAKLITE_MAX_UPLOAD_BYTES", str(256 * 1024 * 1024)))
MAX_JSON_BYTES = int(os.environ.get("TAKLITE_MAX_JSON_BYTES", str(256 * 1024)))
COT_MAX_BUFFER_BYTES = int(os.environ.get("TAKLITE_COT_MAX_BUFFER_BYTES", str(1024 * 1024)))
EVENT_RETENTION_ROWS = int(os.environ.get("TAKLITE_EVENT_RETENTION_ROWS", "50000"))
COT_TLS_REQUIRE_CLIENT_CERT = os.environ.get("TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT", "false").lower() in ("1", "true", "yes", "on")
ALLOW_LEGACY_CLIENT_CERT = os.environ.get("TAKLITE_ALLOW_LEGACY_CLIENT_CERT", "true").lower() in ("1", "true", "yes", "on")
LOGIN_LIMIT_ATTEMPTS = int(os.environ.get("TAKLITE_LOGIN_LIMIT_ATTEMPTS", "8"))
LOGIN_LIMIT_WINDOW_SECONDS = int(os.environ.get("TAKLITE_LOGIN_LIMIT_WINDOW_SECONDS", "300"))

EVENT_END = b"</event>"
EVENT_RE = re.compile(rb"<event\b.*?</event>", re.DOTALL)
UID_RE = re.compile(rb'\buid="([^"]+)"')
CALLSIGN_RE = re.compile(rb'<contact\b[^>]*\bcallsign="([^"]+)"')
EVENT_SAVE_COUNT = 0
LOGIN_FAILURES = {}
LOGIN_LOCK = threading.Lock()


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dirs():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)


def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
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
                created_at text not null
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
        conn.commit()


def package_path(hash_value, filename):
    safe_hash = re.sub(r"[^A-Za-z0-9_.-]", "_", hash_value or uuid.uuid4().hex)
    suffix = Path(filename or "package.dp.zip").suffix or ".zip"
    return PACKAGE_DIR / f"{safe_hash}{suffix}"


def safe_download_name(filename, fallback="download.bin"):
    name = Path(filename or fallback).name
    name = re.sub(r"[^A-Za-z0-9_.() -]+", "_", name).strip(" .")
    return name[:160] or fallback


def row_to_package(row):
    return {
        "PrimaryKey": row["PrimaryKey"],
        "UID": row["UID"],
        "Name": row["Name"],
        "Hash": row["Hash"],
        "SubmissionDateTime": row["SubmissionDateTime"],
        "SubmissionUser": row["SubmissionUser"] or "",
        "CreatorUid": row["CreatorUid"] or "",
        "Keywords": row["Keywords"] or "missionpackage",
        "MIMEType": row["MIMEType"] or "application/x-zip-compressed",
        "Size": row["Size"],
        "Tool": row["Tool"] or "public",
    }


def list_packages():
    with db_connect() as conn:
        rows = conn.execute(
            "select * from datapackages order by PrimaryKey desc"
        ).fetchall()
    return [row_to_package(row) for row in rows]


def find_package(hash_value):
    with db_connect() as conn:
        return conn.execute(
            "select * from datapackages where Hash = ?", (hash_value,)
        ).fetchone()


def upsert_package(hash_value, filename, creator_uid, data, host_url):
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
                (UID, Name, Hash, SubmissionDateTime, SubmissionUser, CreatorUid, Keywords, MIMEType, Size, Path, Tool)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, coalesce((select Tool from datapackages where Hash = ?), 'public'))
            on conflict(Hash) do update set
                Name=excluded.Name,
                SubmissionDateTime=excluded.SubmissionDateTime,
                CreatorUid=excluded.CreatorUid,
                Keywords=excluded.Keywords,
                MIMEType=excluded.MIMEType,
                Size=excluded.Size,
                Path=excluded.Path
        """, (
            uid, filename, hash_value, now, creator_uid or "", creator_uid or "",
            "missionpackage", "application/x-zip-compressed", len(data), str(path), hash_value,
        ))
        conn.commit()
    return f"{host_url}/Marti/sync/content?hash={quote(hash_value)}"


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


def save_event(data, remote):
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
        RELAY.remember_event(uid, data)


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


def authenticate_admin(username, password):
    with db_connect() as conn:
        row = conn.execute("select password_hash from admins where username = ?", ((username or "").strip(),)).fetchone()
    if not row or not verify_password(password or "", row["password_hash"]):
        return ""
    return (username or "").strip()


def validate_portal_username(username):
    username = (username or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.@-]{3,64}", username):
        raise ValueError("portal username must be 3-64 characters: letters, numbers, dot, underscore, dash, or @")
    return username


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
        "portal_path": f"/connect/?u={quote(username)}",
        "qr_path": f"/api/portal-users/qr?id={row['id']}",
    }


def list_portal_users():
    with db_connect() as conn:
        rows = conn.execute("""
            select u.*, p.name as profile_name, p.connect_string, p.revoked_at as profile_revoked_at
            from portal_users u
            left join cert_profiles p on p.id = u.cert_profile_id
            order by u.id desc
        """).fetchall()
    return [portal_user_row(row) for row in rows]


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


def create_portal_user(username, password, display_name="", description="", allow_redownload=False):
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
    return portal_user_row(find_portal_user(user_id))


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


def run_openssl(args):
    result = subprocess.run(["openssl", *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "openssl failed").strip())


def ensure_truststore_file():
    ca_cert = CERT_DIR / "taklite-ca.crt"
    ca_key = CERT_DIR / "taklite-ca.key"
    truststore = CERT_DIR / f"{SERVER_HOST}.p12"
    if not ca_cert.exists() or not ca_key.exists():
        raise RuntimeError("TAKlite CA is missing; rerun the installer or restore taklite-ca.crt/taklite-ca.key")
    if not truststore.exists():
        run_openssl([
            "pkcs12", "-export", "-nokeys",
            "-in", str(ca_cert),
            "-out", str(truststore),
            "-name", "taklite-ca",
            "-passout", f"pass:{CERT_PASSWORD}",
        ])
        truststore.chmod(0o644)
    return truststore


def build_server_pref(connect_string, truststore_name, client_cert_name):
    return f"""<?xml version='1.0' encoding='ASCII' standalone='yes'?>
<preferences>
  <preference version="1" name="cot_streams">
    <entry key="count" class="class java.lang.Integer">1</entry>
    <entry key="description0" class="class java.lang.String">TAKlite</entry>
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
  </preference>
</preferences>
"""


def build_server_json_pref(connect_string, truststore_name, client_cert_name):
    return json.dumps({
        "name": "PreferenceControl",
        "version": 1,
        "takServers": [{
            "description": "TAKlite",
            "enabled": True,
            "connectString": connect_string,
            "compress": False,
            "caLocation": f"cert/{truststore_name}",
            "caPassword": CERT_PASSWORD,
            "clientPassword": CERT_PASSWORD,
            "certificateLocation": f"cert/{client_cert_name}",
        }],
    }, indent=2)


def build_manifest(uid, display_name, truststore_name, client_cert_name):
    return f"""<MissionPackageManifest version="2">
  <Configuration>
    <Parameter name="uid" value="{html.escape(uid)}"/>
    <Parameter name="name" value="{html.escape(display_name)}"/>
    <Parameter name="onReceiveDelete" value="true"/>
  </Configuration>
  <Contents>
    <Content ignore="false" zipEntry="certs\\server.pref"/>
    <Content ignore="false" zipEntry="certs\\taklite-server.pref"/>
    <Content ignore="false" zipEntry="certs\\{html.escape(truststore_name)}"/>
    <Content ignore="false" zipEntry="certs\\{html.escape(client_cert_name)}"/>
  </Contents>
</MissionPackageManifest>
"""


def create_cert_profile(name, description=""):
    name = safe_profile_name(name)
    description = (description or "").strip()
    truststore = ensure_truststore_file()
    ca_cert = CERT_DIR / "taklite-ca.crt"
    ca_key = CERT_DIR / "taklite-ca.key"
    client_key = CERT_DIR / f"{name}.key"
    client_csr = CERT_DIR / f"{name}.csr"
    client_ext = CERT_DIR / f"{name}.ext"
    client_crt = CERT_DIR / f"{name}.crt"
    client_p12 = CERT_DIR / f"{name}.p12"
    dp_zip = CERT_DIR / f"{name}-{SERVER_HOST}.dp.zip"
    connect_string = f"{SERVER_HOST}:{COT_TLS_PORT}:ssl"
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
        "-passout", f"pass:{CERT_PASSWORD}",
    ])
    client_key.chmod(0o600)
    client_p12.chmod(0o644)

    manifest = build_manifest(f"taklite-{name}", f"TAKlite {name}", truststore.name, client_p12.name)
    server_pref = build_server_pref(connect_string, truststore.name, client_p12.name)
    json_pref = build_server_json_pref(connect_string, truststore.name, client_p12.name)
    with zipfile.ZipFile(dp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.xml", manifest)
        zf.writestr("server.pref", server_pref)
        zf.writestr("certs/server.pref", server_pref)
        zf.writestr("taklite-server.pref", json_pref)
        zf.writestr("certs/taklite-server.pref", json_pref)
        zf.write(truststore, truststore.name)
        zf.write(truststore, f"certs/{truststore.name}")
        zf.write(client_p12, client_p12.name)
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
                "uid": "",
                "callsign": "",
                "connected_at": now,
                "last_seen": now,
            }
        self.send_recent(handler)
        self.send_to(handler, server_status_event())

    def remove(self, handler):
        with self.lock:
            self.clients.pop(handler, None)

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

    def remember_event(self, uid, event):
        with self.lock:
            self.last_events[uid] = (time.time(), event)
            cutoff = time.time() - 300
            for old_uid, (seen, _) in list(self.last_events.items()):
                if seen < cutoff:
                    self.last_events.pop(old_uid, None)

    def send_to(self, handler, event):
        try:
            handler.request.sendall(event)
            return True
        except OSError:
            self.remove(handler)
            return False

    def send_recent(self, handler):
        with self.lock:
            events = [event for _, event in self.last_events.values()]
        for event in events:
            self.send_to(handler, event)

    def broadcast(self, sender, event):
        with self.lock:
            handlers = list(self.clients.keys())
        for handler in handlers:
            if sender is not None and handler is sender:
                continue
            self.send_to(handler, event)

    def heartbeat(self):
        self.broadcast(None, server_status_event())


RELAY = CotRelay()


class CotHandler(BaseRequestHandler):
    def setup(self):
        self.remote = f"{self.client_address[0]}:{self.client_address[1]}"
        self.bytes_in = 0
        self.events_in = 0
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
                save_event(event, self.remote)
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
    for part in body.split(boundary):
        part = part.strip(b"\r\n")
        if not part or part == b"--" or b"\r\n\r\n" not in part:
            continue
        raw_headers, content = part.split(b"\r\n\r\n", 1)
        headers = raw_headers.decode("utf-8", "replace")
        if 'name="assetfile"' not in headers:
            continue
        filename_match = re.search(r'filename="([^"]*)"', headers)
        filename = filename_match.group(1) if filename_match else None
        if content.endswith(b"\r\n"):
            content = content[:-2]
        return filename, content
    raise ValueError("missing multipart field assetfile")


def validate_datapackage_upload(filename, data):
    if not data:
        raise ValueError("empty upload")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"datapackage exceeds maximum size of {MAX_UPLOAD_BYTES} bytes")
    if filename and not filename.lower().endswith((".zip", ".dp.zip")):
        raise ValueError("datapackage filename must end with .zip or .dp.zip")
    if data[:4] != b"PK\x03\x04" and data[:4] != b"PK\x05\x06" and data[:4] != b"PK\x07\x08":
        raise ValueError("datapackage must be a zip file")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            bad = zf.testzip()
            if bad:
                raise ValueError(f"datapackage zip contains corrupt entry: {bad}")
    except zipfile.BadZipFile as exc:
        raise ValueError("datapackage must be a valid zip file") from exc


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

    def send_security_headers(self, content_type):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        if content_type.startswith("text/html"):
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' blob: data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'")

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

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)
        if path == "/":
            self.send_text(INDEX_HTML, content_type="text/html; charset=utf-8")
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
            self.send_json({"version": 2, "type": "ClientEndpointList", "data": RELAY.snapshot()})
            return
        if path in ("/Marti/api/groups/groupCacheEnabled", "/api/groups/groupCacheEnabled"):
            self.send_json(False)
            return
        if path in ("/Marti/api/missions/invitations", "/api/missions/invitations"):
            self.send_json({"version": 2, "type": "MissionInvitationList", "data": []})
            return
        if path in ("/Marti/api/missions/all/invitations", "/api/missions/all/invitations"):
            self.send_json({"version": 2, "type": "MissionInvitationList", "data": []})
            return
        if path in ("/Marti/api/missions", "/api/missions"):
            self.send_json({"version": 2, "type": "MissionList", "data": []})
            return
        if path in ("/Marti/api/citrap", "/api/citrap"):
            self.send_json({"version": 2, "type": "CitrapList", "data": []})
            return
        if path in ("/Marti/sync/search", "/sync/search"):
            items = list_packages()
            self.send_json({"resultCount": len(items), "results": items})
            return
        if path in ("/Marti/sync/missionquery", "/sync/missionquery"):
            hash_value = qs.get("hash", [""])[0]
            row = find_package(hash_value)
            if not row:
                self.send_json({"error": "package not found"}, HTTPStatus.NOT_FOUND)
                return
            self.send_text(f"{absolute_base_url(self)}/Marti/sync/content?hash={quote(hash_value)}")
            return
        if path in ("/Marti/sync/content", "/sync/content"):
            hash_value = qs.get("hash", [""])[0]
            row = find_package(hash_value)
            if not row:
                self.send_json({"error": "package not found"}, HTTPStatus.NOT_FOUND)
                return
            package = Path(row["Path"])
            if not package.exists():
                self.send_json({"error": "package file missing"}, HTTPStatus.NOT_FOUND)
                return
            self.send_file(package, row["Name"])
            return
        if path == "/certs/taklite-truststore.p12":
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
            self.send_json({"ok": True, "version": VERSION, "cot_port": COT_PORT, "cot_tls_port": COT_TLS_PORT if tls_enabled else None, "http_port": HTTP_PORT, "https_port": HTTPS_PORT if tls_enabled else None, "clients": len(RELAY.snapshot()), "packages": len(list_packages()), "auth_enabled": bool(ADMIN_TOKEN)})
            return
        if path == "/api/datapackages":
            if not self.require_auth():
                return
            self.send_json({"items": list_packages()})
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
                username = authenticate_admin(payload.get("username", ""), payload.get("password", ""))
                if not username:
                    record_login_failure("admin", remote, login_user)
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
            if path in ("/Marti/sync/missionupload", "/sync/missionupload"):
                filename, data = parse_upload(self)
                if not data:
                    raise ValueError("empty upload")
                hash_value = qs.get("hash", [""])[0]
                query_name = qs.get("filename", [""])[0]
                creator_uid = qs.get("creatorUid", [""])[0]
                url = upsert_package(hash_value, unquote(query_name or filename or ""), creator_uid, data, absolute_base_url(self))
                self.send_text(url)
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
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path in ("/Marti/api/missions/citrap/subscription", "/api/missions/citrap/subscription"):
            self.send_json({"version": 2, "type": "MissionSubscription", "data": {"subscribed": True}})
            return
        match = re.match(r"^/(?:Marti/)?api/sync/metadata/([^/]+)/tool$", path)
        if not match:
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        hash_value = unquote(match.group(1))
        length = int(self.headers.get("Content-Length", "0") or "0")
        tool = self.rfile.read(length).decode("utf-8", "replace").strip() or "public"
        with db_connect() as conn:
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
    init_db()
    cot_server = CotServer((COT_BIND, COT_PORT), CotHandler, "tcp")
    http_server = ThreadingHTTPServer((HTTP_BIND, HTTP_PORT), HttpHandler)
    threading.Thread(target=cot_server.serve_forever, daemon=True).start()
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    if HTTPS_CERT.exists() and HTTPS_KEY.exists():
        cot_tls_context = server_tls_context(request_client_cert=True)
        https_context = server_tls_context(request_client_cert=False)
        cot_tls_server = CotServer((COT_TLS_BIND, COT_TLS_PORT), CotHandler, "tls")
        cot_tls_server.socket = cot_tls_context.wrap_socket(cot_tls_server.socket, server_side=True)
        threading.Thread(target=cot_tls_server.serve_forever, daemon=True).start()
        https_server = ThreadingHTTPServer((HTTPS_BIND, HTTPS_PORT), HttpHandler)
        https_server.socket = https_context.wrap_socket(https_server.socket, server_side=True)
        threading.Thread(target=https_server.serve_forever, daemon=True).start()
        client_cert_mode = "client cert optional/verified" if CLIENT_CA.exists() else "client cert not verified; CA missing"
        print(f"TAKlite TLS CoT listening on {COT_TLS_BIND}:{COT_TLS_PORT} ({client_cert_mode})")
        print(f"TAKlite HTTPS/Marti listening on {HTTPS_BIND}:{HTTPS_PORT}")
    else:
        print(f"TAKlite HTTPS disabled; missing {HTTPS_CERT} or {HTTPS_KEY}")
    print(f"TAKlite CoT listening on {COT_BIND}:{COT_PORT}")
    print(f"TAKlite HTTP/Marti/Admin listening on {HTTP_BIND}:{HTTP_PORT}")
    http_server.serve_forever()


if __name__ == "__main__":
    main()
