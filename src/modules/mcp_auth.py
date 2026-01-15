from pathlib import Path
import json
import uuid
from typing import Optional


AUTH_FILE = Path('auth.json')


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
    data = load_auth(path)
    api_keys = data.get('api_keys', {})
    return api_keys.get(token)
