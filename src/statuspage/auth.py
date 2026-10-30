"""Magic-link login: HMAC-signed, expiring tokens. No passwords stored."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(email: str, secret: str, ttl: int = 900, now: float | None = None) -> str:
    payload = _b64(json.dumps({"e": email.lower(), "x": int((now or time.time()) + ttl)}).encode())
    sig = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def verify_token(token: str, secret: str, now: float | None = None) -> str | None:
    try:
        payload, sig = token.split(".")
    except ValueError:
        return None
    good = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(good, sig):
        return None
    data = json.loads(_unb64(payload))
    if data["x"] < (now or time.time()):
        return None
    return data["e"]
