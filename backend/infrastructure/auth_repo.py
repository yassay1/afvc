"""Postgres persistence for fixed accounts and server-side sessions."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt

from backend.core.config import get_session_ttl_hours
from backend.infrastructure.db import get_pool


@dataclass(frozen=True)
class AuthUser:
    id: str
    username: str
    is_active: bool


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def get_user_by_username(username: str) -> AuthUser | None:
    with get_pool().connection() as conn:
        row = conn.execute(
            """
            SELECT id::text AS id, username, is_active
            FROM auth.users
            WHERE lower(username) = lower(%s)
            """,
            (username.strip(),),
        ).fetchone()
    if not row:
        return None
    return AuthUser(id=row["id"], username=row["username"], is_active=bool(row["is_active"]))


def get_user_with_hash(username: str) -> tuple[AuthUser, str] | None:
    with get_pool().connection() as conn:
        row = conn.execute(
            """
            SELECT id::text AS id, username, is_active, password_hash
            FROM auth.users
            WHERE lower(username) = lower(%s)
            """,
            (username.strip(),),
        ).fetchone()
    if not row:
        return None
    user = AuthUser(id=row["id"], username=row["username"], is_active=bool(row["is_active"]))
    return user, row["password_hash"]


def create_user(username: str, password: str) -> AuthUser:
    name = username.strip()
    if not name:
        raise ValueError("用户名不能为空")
    if len(password) < 8:
        raise ValueError("密码至少 8 位")
    user_id = str(uuid.uuid4())
    password_hash = hash_password(password)
    with get_pool().connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM auth.users WHERE lower(username) = lower(%s)",
            (name,),
        ).fetchone()
        if existing:
            raise ValueError(f"用户已存在：{name}")
        conn.execute(
            """
            INSERT INTO auth.users (id, username, password_hash, is_active)
            VALUES (%s::uuid, %s, %s, TRUE)
            """,
            (user_id, name, password_hash),
        )
        conn.commit()
    return AuthUser(id=user_id, username=name, is_active=True)


def set_user_active(username: str, *, active: bool) -> AuthUser:
    with get_pool().connection() as conn:
        row = conn.execute(
            """
            UPDATE auth.users
            SET is_active = %s, updated_at = NOW()
            WHERE lower(username) = lower(%s)
            RETURNING id::text AS id, username, is_active
            """,
            (active, username.strip()),
        ).fetchone()
        if not row:
            raise ValueError(f"用户不存在：{username.strip()}")
        if not active:
            conn.execute(
                """
                UPDATE auth.sessions
                SET revoked_at = NOW()
                WHERE user_id = %s::uuid AND revoked_at IS NULL
                """,
                (row["id"],),
            )
        conn.commit()
    return AuthUser(id=row["id"], username=row["username"], is_active=bool(row["is_active"]))


def reset_password(username: str, password: str) -> AuthUser:
    if len(password) < 8:
        raise ValueError("密码至少 8 位")
    password_hash = hash_password(password)
    with get_pool().connection() as conn:
        row = conn.execute(
            """
            UPDATE auth.users
            SET password_hash = %s, updated_at = NOW()
            WHERE lower(username) = lower(%s)
            RETURNING id::text AS id, username, is_active
            """,
            (password_hash, username.strip()),
        ).fetchone()
        if not row:
            raise ValueError(f"用户不存在：{username.strip()}")
        conn.execute(
            """
            UPDATE auth.sessions
            SET revoked_at = NOW()
            WHERE user_id = %s::uuid AND revoked_at IS NULL
            """,
            (row["id"],),
        )
        conn.commit()
    return AuthUser(id=row["id"], username=row["username"], is_active=bool(row["is_active"]))


def create_session(user_id: str) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=get_session_ttl_hours())
    with get_pool().connection() as conn:
        conn.execute(
            """
            INSERT INTO auth.sessions (user_id, token_hash, expires_at)
            VALUES (%s::uuid, %s, %s)
            """,
            (user_id, token_hash, expires_at),
        )
        conn.commit()
    return token, expires_at


def revoke_session_token(token: str | None) -> None:
    if not token:
        return
    token_hash = _hash_token(token)
    with get_pool().connection() as conn:
        conn.execute(
            """
            UPDATE auth.sessions
            SET revoked_at = NOW()
            WHERE token_hash = %s AND revoked_at IS NULL
            """,
            (token_hash,),
        )
        conn.commit()


def resolve_session_token(token: str | None) -> AuthUser | None:
    if not token:
        return None
    token_hash = _hash_token(token)
    with get_pool().connection() as conn:
        row = conn.execute(
            """
            SELECT u.id::text AS id, u.username, u.is_active
            FROM auth.sessions s
            JOIN auth.users u ON u.id = s.user_id
            WHERE s.token_hash = %s
              AND s.revoked_at IS NULL
              AND s.expires_at > NOW()
            """,
            (token_hash,),
        ).fetchone()
    if not row or not row["is_active"]:
        return None
    return AuthUser(id=row["id"], username=row["username"], is_active=True)
