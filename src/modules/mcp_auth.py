from pathlib import Path
import json
import uuid
import os
import time
from typing import Optional

try:
    import jwt
except Exception:  # pragma: no cover - runtime environment may not have PyJWT until installed
    jwt = None


AUTH_FILE = Path(os.getenv('AUTH_FILE', 'auth.json'))


def ensure_auth_file(path: Path = AUTH_FILE):
    if not path.exists():
        data = {'api_keys': {}}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def load_auth(path: Path = AUTH_FILE) -> dict:
    p = ensure_auth_file(path)
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return {'api_keys': {}}


def save_auth(data: dict, path: Path = AUTH_FILE) -> None:
    p = ensure_auth_file(path)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def get_key_for_user(user_id: int, path: Path = AUTH_FILE) -> Optional[str]:
    data = load_auth(path)
    api_keys = data.get('api_keys', {})
    for k, v in api_keys.items():
        if v == user_id:
            return k
    return None


def create_key_for_user(user_id: int, path: Path = AUTH_FILE) -> str:
    data = load_auth(path)
    api_keys = data.setdefault('api_keys', {})
    # generate uuid until unique
    while True:
        token = str(uuid.uuid4())
        if token not in api_keys:
            break
    api_keys[token] = user_id
    save_auth(data, path)
    return token


def validate_key(token: str, path: Path = AUTH_FILE) -> Optional[int]:
    """Return user_id for a given API key or None."""
    data = load_auth(path)
    api_keys = data.get('api_keys', {})
    return api_keys.get(token)


def generate_jwt(user_id: int, secret: Optional[str], expires_seconds: int = 3600) -> Optional[str]:
    """Create a signed JWT for the given user_id.

    If `secret` is None, returns None.
    """
    if not secret or jwt is None:
        return None
    now = int(time.time())
    payload = {
        'sub': str(user_id),
        'iat': now,
        'exp': now + int(expires_seconds),
    }
    return jwt.encode(payload, secret, algorithm='HS256')


def verify_jwt(token: str, secret: Optional[str]) -> Optional[int]:
    """Verify JWT and return user_id (int) on success, otherwise None.

    If PyJWT is not installed or secret is None, returns None.
    """
    if not token or not secret or jwt is None:
        return None
    try:
        payload = jwt.decode(token, secret, algorithms=['HS256'])
        sub = payload.get('sub')
        if sub is None:
            return None
        return int(sub)
    except Exception:
        return None
