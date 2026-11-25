"""岗位账号。管理员看全部知识库，专员只看被授权的知识库。"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from hashlib import sha256

from fastapi import HTTPException, Request

from app.core.config import APP_ROOT, settings

TOKEN_TTL_SECONDS = 12 * 60 * 60


@dataclass(frozen=True)
class Account:
    username: str
    role: str
    display_name: str
    kb_ids: tuple[str, ...]

    def allows(self, kb_id: str) -> bool:
        return self.role == "admin" or kb_id in self.kb_ids


def authenticate(username: str, password: str) -> Account | None:
    for item in _load_accounts():
        if item["username"] != username:
            continue
        if not hmac.compare_digest(item["password"], password):
            return None
        return Account(
            username=item["username"],
            role=item["role"],
            display_name=item["display_name"],
            kb_ids=tuple(item.get("kb_ids") or []),
        )
    return None


def issue_token(account: Account) -> str:
    payload = json.dumps(
        {"username": account.username, "exp": int(time.time()) + TOKEN_TTL_SECONDS},
        separators=(",", ":"),
    )
    signature = hmac.new(_secret(), payload.encode("utf-8"), sha256).hexdigest()
    return f"{payload}.{signature}"


def read_account(token: str) -> Account | None:
    payload, separator, signature = token.partition(".")
    if not separator:
        return None
    expected = hmac.new(_secret(), payload.encode("utf-8"), sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if int(data.get("exp") or 0) < time.time():
        return None
    username = str(data.get("username") or "")
    for item in _load_accounts():
        if item["username"] == username:
            return Account(
                username=item["username"],
                role=item["role"],
                display_name=item["display_name"],
                kb_ids=tuple(item.get("kb_ids") or []),
            )
    return None


def require_account(request: Request) -> Account:
    header = request.headers.get("authorization", "")
    token = header.removeprefix("Bearer ").strip()
    if not token or token == header:
        raise HTTPException(status_code=401, detail="请先登录")
    account = read_account(token)
    if account is None:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    return account


def require_admin(account: Account) -> None:
    if account.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")


def _secret() -> bytes:
    raw = (settings.app.auth_secret or "contract-rag-demo").encode("utf-8")
    return hashlib.sha256(raw).digest()


def _load_accounts() -> list[dict]:
    path = APP_ROOT / "data" / "accounts.json"
    return json.loads(path.read_text(encoding="utf-8"))
