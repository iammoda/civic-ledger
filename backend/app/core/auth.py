"""Admin authentication via a static token.

There are no user accounts on this platform. The only protected surface
is the admin review queue (integrity flags + corrections), gated by a
shared secret in the ADMIN_API_TOKEN environment variable, sent as the
X-Admin-Token header. If the token is unset, admin endpoints are disabled.
"""
from __future__ import annotations

import hmac

from fastapi import Header, HTTPException


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    from app.core.config import get_settings

    expected = get_settings().admin_api_token
    if not expected:
        raise HTTPException(status_code=503, detail="Admin access is not configured (ADMIN_API_TOKEN unset)")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=403, detail="Admin access required")
