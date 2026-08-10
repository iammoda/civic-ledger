"""Authenticate API requests against better-auth's session table.

better-auth (in the Next.js app) owns sign-in and writes sessions to the
shared Postgres. The cookie value is "<token>.<signature>"; the session
row stores the raw token. Possession of a valid, unexpired random token
is the authentication — we look it up and join the user.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import unquote

from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

SESSION_COOKIES = (
    "__Secure-better-auth.session_token",
    "better-auth.session_token",
)


@dataclass(slots=True)
class AuthUser:
    id: str
    email: str
    name: str


def _extract_token(request: Request) -> str | None:
    for cookie_name in SESSION_COOKIES:
        raw = request.cookies.get(cookie_name)
        if raw:
            value = unquote(raw)
            # Cookie format is "<token>.<hmac-signature>".
            return value.split(".", 1)[0]
    return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> AuthUser | None:
    token = _extract_token(request)
    if not token:
        return None
    row = db.execute(
        text(
            'SELECT u.id, u.email, u.name, s."expiresAt" '
            'FROM "session" s JOIN "user" u ON u.id = s."userId" '
            "WHERE s.token = :token"
        ),
        {"token": token},
    ).first()
    if row is None:
        return None
    expires_at = row[3]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            return None
    return AuthUser(id=row[0], email=row[1], name=row[2])


def require_user(user: AuthUser | None = Depends(get_current_user)) -> AuthUser:
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in required")
    return user
