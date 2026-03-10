"""JWT authentication utilities."""
from __future__ import annotations

import time
from typing import Any

import jwt


def create_token(secret: str, expiry_hours: int = 168) -> str:
    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + expiry_hours * 3600,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_token(token: str, secret: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except (jwt.InvalidTokenError, jwt.DecodeError):
        return None
