"""
Authentication + multi-tenant organization management.

Three roles:
- super_admin: creates organizations and admin accounts. Not tied to any
  one organization -- can see across all of them.
- admin: belongs to exactly one organization. Uploads/ingests documents
  and creates agent accounts, scoped to their own organization only.
- agent: belongs to exactly one organization. Uses chat/voice/calls,
  scoped to their own organization's documents only.

A default super admin account is created automatically the first time
init_auth_db() runs, if no users exist yet -- otherwise there would be no
way to log in at all on a fresh install. Change its password immediately
after first login in a real deployment.
"""

import os
import sqlite3
from datetime import datetime, timezone

import bcrypt

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth.db")

DEFAULT_SUPER_ADMIN_USERNAME = "superadmin"
DEFAULT_SUPER_ADMIN_PASSWORD = "ChangeMe123!"

VALID_ROLES = ("super_admin", "admin", "agent")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db():
    conn = _connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('super_admin', 'admin', 'agent')),
            organization_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (organization_id) REFERENCES organizations(id)
        )
        """
    )
    conn.commit()

    # Bootstrap: without this, a fresh install would have zero users and
    # therefore no way to log in at all.
    existing = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    if existing == 0:
        _create_user(
            conn,
            DEFAULT_SUPER_ADMIN_USERNAME,
            DEFAULT_SUPER_ADMIN_PASSWORD,
            "super_admin",
            organization_id=None,
        )
        print(
            f"[auth] Created default super admin account: "
            f"username='{DEFAULT_SUPER_ADMIN_USERNAME}' password='{DEFAULT_SUPER_ADMIN_PASSWORD}' "
            f"-- change this after first login."
        )

    conn.close()


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password, password_hash):
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_organization(name):
    conn = _connect()
    try:
        cursor = conn.execute(
            "INSERT INTO organizations (name, created_at) VALUES (?, ?)",
            (name.strip(), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError(f"An organization named '{name}' already exists")
    finally:
        conn.close()


def get_organizations():
    conn = _connect()
    rows = conn.execute("SELECT * FROM organizations ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def rename_organization(organization_id, new_name):
    conn = _connect()
    try:
        conn.execute(
            "UPDATE organizations SET name = ? WHERE id = ?",
            (new_name.strip(), organization_id),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"An organization named '{new_name}' already exists")
    finally:
        conn.close()


def get_organization(organization_id):
    conn = _connect()
    row = conn.execute("SELECT * FROM organizations WHERE id = ?", (organization_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _create_user(conn, username, password, role, organization_id):
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}")
    if role in ("admin", "agent") and organization_id is None:
        raise ValueError(f"role '{role}' requires an organization_id")

    try:
        conn.execute(
            """
            INSERT INTO users (username, password_hash, role, organization_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                username.strip(),
                hash_password(password),
                role,
                organization_id if role != "super_admin" else None,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"Username '{username}' already exists")


def create_user(username, password, role, organization_id=None):
    """Creates a user. role must be 'super_admin', 'admin', or 'agent'.
    organization_id is required for admin/agent, ignored for super_admin."""
    conn = _connect()
    try:
        _create_user(conn, username, password, role, organization_id)
    finally:
        conn.close()


def verify_login(username, password):
    """Returns the user dict (without password_hash) if credentials are
    correct, or None otherwise."""
    conn = _connect()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()
    conn.close()

    if row is None or not verify_password(password, row["password_hash"]):
        return None

    user = dict(row)
    user.pop("password_hash")
    return user


def get_users_by_organization(organization_id):
    conn = _connect()
    rows = conn.execute(
        """
        SELECT id, username, role, organization_id, created_at
        FROM users WHERE organization_id = ? ORDER BY username
        """,
        (organization_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_users():
    conn = _connect()
    rows = conn.execute(
        """
        SELECT id, username, role, organization_id, created_at
        FROM users ORDER BY role, username
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
