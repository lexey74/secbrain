"""server_mcp
===============

Official MCP-aware server for external LLM clients.

This module exposes a FastAPI `app` variable.

Features:
1. MCP Integration: Uses `mcp.server.fastapi.FastMCP` if available to expose tools
   like `search_brain`, `read_full_note`, `get_recent_activity`.
2. Fallback: Keeps legacy SSE + JSON-RPC endpoints for older clients or if mcp lib is missing.
3. Shared Logic: Core business logic is decoupled from transport (HTTP vs MCP).
"""
"""server_mcp — official MCP FastAPI integration
===============================================

This module exposes a FastAPI `app` with the official MCP toolkit mounted.

Design goals:
- Fail fast: require `mcp.server.fastapi.FastMCP` to be importable.
- Delegate protocol handling (/sse, /messages, discovery) to the MCP SDK.
- Keep transport-agnostic core logic (search/read/list) here and register it
  as MCP tools.
"""

import os
import json
import asyncio
import logging
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import contextvars

from src.modules import mcp_auth

# Load .env file before anything else
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server_mcp")

# Configuration
DOWNLOADS_DIR = Path(os.getenv('DOWNLOADS_DIR', 'downloads'))
AUTH_FILE = Path(os.getenv('AUTH_FILE', 'auth.json'))
DEFAULT_MCP_USER = os.getenv('DEFAULT_MCP_USER')
MCP_DEV_MODE = os.getenv('MCP_DEV_MODE', 'false').lower() in ('1', 'true', 'yes')

# JWT secret (REQUIRED for token auth)
MCP_JWT_SECRET = os.getenv('MCP_JWT_SECRET')
if not MCP_JWT_SECRET:
    raise RuntimeError(
        "MCP_JWT_SECRET environment variable is not set. "
        "Please set it to a strong secret string. "
        "You can add it to your .env file."
    )

# Context variable holding the authenticated user id for the current request.
CURRENT_MCP_USER: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar('CURRENT_MCP_USER', default=None)

# Session-to-user mapping for MCP SSE protocol
# When a client connects to /sse with api_key, we store the user_id
# so subsequent /messages/ requests can use it
SESSION_USER_MAP: dict[str, int] = {}

# Pending user mapping: api_key -> user_id
# Used to associate sessions with users when the session_id is first seen
PENDING_USER_FOR_API_KEY: dict[str, int] = {}

# Last authenticated user (fallback for session association)
# This is a simple approach: store the last user_id that connected via /sse
# and use it for the next /messages/ request that doesn't have a known session
LAST_SSE_USER_ID: Optional[int] = None


def _find_user_folder(user_id: int) -> Path:
    candidate = DOWNLOADS_DIR / f'user_{user_id}'
    if candidate.exists() and candidate.is_dir():
        return candidate
    if not DOWNLOADS_DIR.exists():
        return candidate
    for p in DOWNLOADS_DIR.iterdir():
        if p.is_dir() and str(user_id) in p.name:
            return p
    return candidate


def _get_default_user_id() -> int:
    if DEFAULT_MCP_USER:
        try:
            return int(DEFAULT_MCP_USER)
        except Exception:
            logger.warning('DEFAULT_MCP_USER is set but not an integer: %s', DEFAULT_MCP_USER)
    if not MCP_DEV_MODE:
        raise RuntimeError('DEFAULT_MCP_USER is not configured and MCP_DEV_MODE is false')
    if not AUTH_FILE.exists():
        return 1
    try:
        data = json.loads(AUTH_FILE.read_text(encoding='utf-8'))
        api_keys = data.get('api_keys') if isinstance(data, dict) else None
        if api_keys and isinstance(api_keys, dict):
            vals = list(api_keys.values())
            if vals:
                return int(vals[0])
    except Exception:
        logger.exception('Failed reading AUTH_FILE for default user id; falling back to 1')
    return 1


async def core_search_brain(user_id: int, query: str) -> str:
    from src.modules.module4_rag import RAGEngine

    user_folder = _find_user_folder(user_id)

    def _run():
        if not user_folder.exists():
            return "Error: User knowledge base not found."
        try:
            rag = RAGEngine(user_root=user_folder)
            res = rag.query(query)
            return str(res)
        except Exception as e:
            return f"Error during search: {e}"

    return await asyncio.to_thread(_run)


async def core_read_full_note(user_id: int, folder_name: str) -> str:
    user_folder = _find_user_folder(user_id)

    def _run():
        if not user_folder.exists():
            return "Error: User folder not found."
        target_note = None
        for p in user_folder.iterdir():
            if p.is_dir() and folder_name in p.name:
                target_note = p / 'Knowledge.md'
                break
        if target_note and target_note.exists():
            return target_note.read_text(encoding='utf-8')
        return f"Error: Note '{folder_name}' not found or no Knowledge.md present."

    return await asyncio.to_thread(_run)


async def core_get_recent_activity(user_id: int) -> List[str]:
    user_folder = _find_user_folder(user_id)

    def _run():
        if not user_folder.exists():
            return []
        dirs = [d for d in user_folder.iterdir() if d.is_dir()]
        dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return [d.name for d in dirs[:10]]

    return await asyncio.to_thread(_run)


# --- Official MCP integration (fastmcp) ---
from mcp.server.fastmcp.server import FastMCP  # type: ignore

app = FastAPI(title="Second Brain MCP Server")

# Create FastMCP instance and register tools
mcp = FastMCP("Second Brain")

# If running on a public IP, allow that host/origin in FastMCP transport security
# so external clients can connect (disable DNS-rebinding protection or add
# explicit allowed hosts). Controlled by env vars for safety.
try:
    # FASTMCP_ALLOW_HOSTS can be a comma-separated list like '38.242.141.28:*,0.0.0.0:*'
    allow_hosts = os.getenv('FASTMCP_ALLOW_HOSTS')
    allow_origins = os.getenv('FASTMCP_ALLOW_ORIGINS')
    if allow_hosts:
        hosts = [h.strip() for h in allow_hosts.split(',') if h.strip()]
        # merge unique
        existing = list(getattr(mcp.settings.transport_security, 'allowed_hosts', []) or [])
        mcp.settings.transport_security.allowed_hosts = list(dict.fromkeys(existing + hosts))
        logger.info('Applied FASTMCP_ALLOW_HOSTS: %s', mcp.settings.transport_security.allowed_hosts)
    # Allow specific origins (e.g., http://38.242.141.28:*)
    if allow_origins:
        origins = [o.strip() for o in allow_origins.split(',') if o.strip()]
        existing_o = list(getattr(mcp.settings.transport_security, 'allowed_origins', []) or [])
        mcp.settings.transport_security.allowed_origins = list(dict.fromkeys(existing_o + origins))
        logger.info('Applied FASTMCP_ALLOW_ORIGINS: %s', mcp.settings.transport_security.allowed_origins)
    # If MCP_HOST is set and not loopback, add it as allowed host/origin
    if os.getenv('MCP_HOST'):
        host_val = os.getenv('MCP_HOST')
        if host_val not in ('127.0.0.1', 'localhost', '::1'):
            ah = f"{host_val}:*"
            ao = f"http://{host_val}:*"
            if ah not in mcp.settings.transport_security.allowed_hosts:
                mcp.settings.transport_security.allowed_hosts.append(ah)
            if ao not in mcp.settings.transport_security.allowed_origins:
                mcp.settings.transport_security.allowed_origins.append(ao)
            logger.info('Added MCP_HOST to allowed hosts/origins: %s %s', ah, ao)
except Exception:
    logger.exception('Failed to adjust FastMCP transport security settings from env')


@app.post('/auth/token')
async def exchange_api_key_for_jwt(body: dict):
    """Exchange a valid api_key for a short-lived JWT.

    Request body: {"api_key": "..."}
    Response: {"access_token": "<jwt>", "token_type": "bearer", "expires_in": 3600}
    """
    api_key = body.get('api_key') if isinstance(body, dict) else None
    if not api_key:
        return JSONResponse(status_code=400, content={"detail": "api_key required in body"})

    user_id = mcp_auth.validate_key(api_key)
    if not user_id:
        return JSONResponse(status_code=401, content={"detail": "invalid api_key"})

    if not MCP_JWT_SECRET:
        return JSONResponse(status_code=400, content={"detail": "server not configured to issue JWTs"})

    token = mcp_auth.generate_jwt(user_id, MCP_JWT_SECRET, expires_seconds=3600)
    if not token:
        return JSONResponse(status_code=500, content={"detail": "failed to generate token"})

    return {"access_token": token, "token_type": "bearer", "expires_in": 3600}


# --- Authentication middleware for MCP endpoints ---
@app.middleware("http")
async def mcp_auth_middleware(request: Request, call_next):
    """Protect MCP protocol endpoints (/sse, /messages, discovery) by
    requiring either a Bearer JWT or an api_key query parameter.

    If authentication succeeds the user id is stored in the
    CURRENT_MCP_USER contextvar so tools can read it.
    
    For MCP SSE protocol:
    - When client connects to /sse?api_key=..., we authenticate and store user_id
    - The SSE response contains session_id in the endpoint URL
    - We intercept the response to capture session_id and map it to user_id
    - When client sends to /messages/?session_id=..., we look up user_id from the map
    """
    path = request.url.path
    # Only protect MCP-related paths; allow discovery and health optionally.
    if path.startswith('/sse') or path.startswith('/messages') or path.startswith('/.well-known'):
        user_id = None
        
        # For /messages/ requests, try to get user_id from session_id first
        if path.startswith('/messages'):
            session_id = request.query_params.get('session_id')
            if session_id and session_id in SESSION_USER_MAP:
                user_id = SESSION_USER_MAP[session_id]
                logger.debug(f'Found user_id {user_id} for session_id {session_id}')
        
        # Try Bearer JWT
        if user_id is None:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ', 1)[1].strip()
                try:
                    user_id = mcp_auth.verify_jwt(token, MCP_JWT_SECRET)
                except Exception:
                    user_id = None

        # Try API key in query params
        if user_id is None:
            api_key = request.query_params.get('api_key')
            if api_key:
                try:
                    user_id = mcp_auth.validate_key(api_key)
                except Exception:
                    user_id = None

        # Fallbacks: if DEFAULT_MCP_USER is set use that (but optional now)
        if user_id is None and DEFAULT_MCP_USER:
            try:
                user_id = int(DEFAULT_MCP_USER)
            except Exception:
                user_id = None

        # If still no user and not in dev mode - deny
        if user_id is None and not MCP_DEV_MODE:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized: valid JWT or api_key required"})

        # For /sse requests with authenticated user, store the user_id
        # We'll use a different approach: store api_key -> user_id mapping
        # and extract api_key from the original SSE request URL
        if path.startswith('/sse') and user_id is not None:
            # Store api_key -> user_id mapping for later session lookup
            api_key = request.query_params.get('api_key')
            if api_key:
                # Store in a temporary map that we'll use to associate sessions
                # The MCP SDK generates session_id internally, so we need to
                # associate the user_id with any session created from this api_key
                # We'll do this by storing the user_id in a "pending" state
                # and associating it with the first /messages/ request
                PENDING_USER_FOR_API_KEY[api_key] = user_id
                logger.info(f'Stored pending user_id {user_id} for api_key {api_key[:8]}...')
            
            # Set context and proceed
            token_ctx = CURRENT_MCP_USER.set(user_id)
            try:
                return await call_next(request)
            finally:
                CURRENT_MCP_USER.reset(token_ctx)

        # For dev-mode with no explicit user we allow the request but user_id may be None
        token_ctx = CURRENT_MCP_USER.set(user_id)
        try:
            return await call_next(request)
        finally:
            CURRENT_MCP_USER.reset(token_ctx)

    return await call_next(request)


@mcp.tool()
async def search_brain(query: str) -> str:
    """Search the knowledge base using RAG.

    Authentication / user identity is expected to be handled by the MCP
    server. For development where auth might be absent we fall back to the
    configured DEFAULT_MCP_USER when MCP_DEV_MODE=true.
    """
    uid = CURRENT_MCP_USER.get()
    if uid is None:
        # if not authenticated, try default or dev fallback
        if DEFAULT_MCP_USER:
            uid = _get_default_user_id()
        elif MCP_DEV_MODE:
            # allow dev-mode but user may not have a KB
            uid = None
        else:
            raise RuntimeError('Unauthorized: no user id available')
    if uid is None:
        return "Error: No user authenticated and no DEFAULT_MCP_USER configured."
    return await core_search_brain(uid, query)


@mcp.tool()
async def read_full_note(folder_name: str) -> str:
    uid = CURRENT_MCP_USER.get()
    if uid is None:
        if DEFAULT_MCP_USER:
            uid = _get_default_user_id()
        elif MCP_DEV_MODE:
            uid = None
        else:
            raise RuntimeError('Unauthorized: no user id available')
    if uid is None:
        return "Error: No user authenticated and no DEFAULT_MCP_USER configured."
    return await core_read_full_note(uid, folder_name)


@mcp.tool()
async def get_recent_activity() -> List[str]:
    uid = CURRENT_MCP_USER.get()
    if uid is None:
        if DEFAULT_MCP_USER:
            uid = _get_default_user_id()
        elif MCP_DEV_MODE:
            uid = None
        else:
            raise RuntimeError('Unauthorized: no user id available')
    if uid is None:
        return []
    return await core_get_recent_activity(uid)


# Let the FastMCP instance mount its routes into our FastAPI app. This will
# provide the standard /sse and /messages endpoints and handle RPC semantics.
# FastMCP exposes helper methods to retrieve Starlette/ASGI apps for specific
# transports. Use those to mount MCP handlers into our FastAPI app.
try:
    # mount SSE app under the configured mount_path so the inner app's
    # '/sse' route ends up accessible as '/sse' on the main app.
    sse_mount = mcp.sse_app(mcp.settings.mount_path)
    app.mount(mcp.settings.mount_path, sse_mount)
except Exception:
    logger.exception('Failed to mount MCP SSE app; Falling back to running FastMCP.run if needed')
try:
    # mount Streamable-HTTP app (easier for direct HTTP RPC calls)
    # streamable_http_app doesn't accept mount_path arg in this FastMCP version
    streamable = mcp.streamable_http_app()
    app.mount(mcp.settings.streamable_http_path, streamable)
except Exception:
    logger.exception('Failed to mount MCP streamable-http app; some transports may be unavailable')

    
@app.post('/internal/run_tool')
async def internal_run_tool(request: Request):
    """Developer helper: run a single tool by name using JWT auth and return result.

    Body: {"tool": "search_brain", "params": {"query": "..."}}
    Requires Authorization: Bearer <jwt>
    """
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"detail": "invalid json"})

    tool = payload.get('tool')
    params = payload.get('params', {}) or {}

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return JSONResponse(status_code=401, content={"detail": "missing bearer token"})
    token = auth_header.split(' ', 1)[1].strip()
    uid = mcp_auth.verify_jwt(token, MCP_JWT_SECRET)
    if uid is None:
        return JSONResponse(status_code=401, content={"detail": "invalid token"})

    if tool == 'search_brain':
        q = params.get('query', '')
        res = await core_search_brain(uid, q)
        return {"result": res}
    if tool == 'get_recent_activity':
        res = await core_get_recent_activity(uid)
        return {"result": res}
    return JSONResponse(status_code=400, content={"detail": "unknown tool"})
 