"""Fixed-account login / logout / me. No self-registration."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend.core.config import (
    get_session_cookie_name,
    is_session_cookie_secure,
)
from backend.infrastructure.auth_repo import (
    create_session,
    get_user_with_hash,
    resolve_session_token,
    revoke_session_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["门禁"])


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    username: str


def _set_session_cookie(response: Response, token: str, expires_at) -> None:
    response.set_cookie(
        key=get_session_cookie_name(),
        value=token,
        httponly=True,
        samesite="lax",
        secure=is_session_cookie_secure(),
        path="/",
        expires=expires_at,
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=get_session_cookie_name(),
        path="/",
        samesite="lax",
        secure=is_session_cookie_secure(),
    )


@router.post("/login")
def login(body: LoginBody, response: Response) -> dict:
    found = get_user_with_hash(body.username)
    if found is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    user, password_hash = found
    if not user.is_active or not verify_password(body.password, password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token, expires_at = create_session(user.id)
    _set_session_cookie(response, token, expires_at)
    return {"status": "success", "username": user.username}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(get_session_cookie_name())
    revoke_session_token(token)
    _clear_session_cookie(response)
    return {"status": "success"}


@router.get("/me")
def me(request: Request) -> UserOut:
    token = request.cookies.get(get_session_cookie_name())
    user = resolve_session_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="未登录")
    return UserOut(username=user.username)
