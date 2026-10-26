"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import HTTPException, Request

from backend.core.config import get_session_cookie_name
from backend.infrastructure.auth_repo import AuthUser, resolve_session_token


def require_login(request: Request) -> AuthUser:
    """Require a valid session cookie. Applied to all business routers."""
    token = request.cookies.get(get_session_cookie_name())
    user = resolve_session_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="未登录")
    return user
