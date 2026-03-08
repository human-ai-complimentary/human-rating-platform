from __future__ import annotations

import base64
import hmac
import json
import time
from hashlib import sha256

from fastapi import HTTPException

from config import Settings


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_json(obj: dict) -> str:
    return _b64url(json.dumps(obj, separators=(",", ":")).encode("utf-8"))


def _unb64url(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _unb64url_json(data: str) -> dict:
    return json.loads(_unb64url(data))


def _sign(secret: str, payload: str) -> str:
    return _b64url(hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), sha256).digest())


VERSION = "v1"


def issue_rater_session_token(settings: Settings, *, rater_id: int, experiment_id: int) -> str:
    now = int(time.time())
    payload = _b64url_json({"rid": rater_id, "eid": experiment_id, "iat": now})
    sig = _sign(settings.app_secret_key, payload)
    return f"{VERSION}.{payload}.{sig}"


def verify_rater_session_token(settings: Settings, token: str) -> dict:
    try:
        ver, payload, sig = token.split(".")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid rater session")
    if ver != VERSION:
        raise HTTPException(status_code=401, detail="Invalid rater session")
    expected = _sign(settings.app_secret_key, payload)
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=401, detail="Invalid rater session")
    data = _unb64url_json(payload)
    rid = data.get("rid")
    eid = data.get("eid")
    iat = data.get("iat")
    try:
        rid = int(rid)
        eid = int(eid)
        iat = int(iat)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid rater session")
    return {"rater_id": rid, "experiment_id": eid, "issued_at": iat}
