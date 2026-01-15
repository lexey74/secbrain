"""
Secure MCP-like SSE server for external LLM clients.

Provides:
- GET /sse?api_key=...  -> Server-Sent Events stream
- POST /messages        -> JSON-RPC-like endpoint: {"method": "search_brain", "params": { ... }, "id": ...}

Authentication is based on auth.json (api_key -> telegram_user_id).

This server is intentionally lightweight: it validates api_keys, keeps per-connection asyncio queues,
and dispatches three tools: search_brain, read_full_note, get_recent_activity.
"""
from fastapi import FastAPI, Request, HTTPException, Depends, Query, Header
from fastapi.responses import StreamingResponse, JSONResponse
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional
import os

from src.modules import mcp_auth

app = FastAPI()

# mapping user_id -> list of asyncio.Queue
_connections: Dict[int, list] = {}

DOWNLOADS_DIR = Path(os.getenv('DOWNLOADS_DIR', 'downloads'))
AUTH_FILE = Path(os.getenv('AUTH_FILE', 'auth.json'))


async def _get_user_id(api_key: Optional[str] = Query(None), x_api_key: Optional[str] = Header(None)) -> int:
    token = api_key or x_api_key
    if not token:
        raise HTTPException(status_code=401, detail='Missing API key')
    user_id = mcp_auth.validate_key(token, path=AUTH_FILE)
    if not user_id:
        raise HTTPException(status_code=401, detail='Invalid API key')
    return user_id


def _format_sse(data: Any, event: Optional[str] = None) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    s = ''
    if event:
        s += f'event: {event}\n'
    for line in payload.splitlines():
        s += f'data: {line}\n'
    s += '\n'
    return s


@app.get('/sse')
async def sse_endpoint(request: Request, user_id: int = Depends(_get_user_id)):
    """Open SSE connection for authenticated user."""
    queue: asyncio.Queue = asyncio.Queue()
    _connections.setdefault(user_id, []).append(queue)

    async def event_generator():
        try:
            # send initial connected event
            yield _format_sse({'status': 'connected', 'user_id': user_id}, event='connected')
            while True:
                try:
                    item = await queue.get()
                    yield _format_sse(item)
                except asyncio.CancelledError:
                    break
                # handle client disconnect
                if await request.is_disconnected():
                    break
        finally:
            # cleanup
            lst = _connections.get(user_id, [])
            if queue in lst:
                lst.remove(queue)

    return StreamingResponse(event_generator(), media_type='text/event-stream')


async def _run_in_thread(fn, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


def _find_user_folder(user_id: int) -> Path:
    # Prefer downloads/user_{id}
    candidate = DOWNLOADS_DIR / f'user_{user_id}'
    if candidate.exists() and candidate.is_dir():
        return candidate
    # Otherwise, try to find a folder containing the user_id
    for p in DOWNLOADS_DIR.iterdir():
        if p.is_dir() and str(user_id) in p.name:
            return p
    # Fallback to downloads/user_{id} (may not exist)
    return candidate


@app.post('/messages')
async def messages(request: Request, user_id: int = Depends(_get_user_id)):
    """Handle JSON-RPC-like messages from external LLMs.

    Body should include: {"method": "search_brain"|"read_full_note"|"get_recent_activity", "params": {...}, "id": optional}
    """
    body = await request.json()
    method = body.get('method')
    params = body.get('params', {})
    req_id = body.get('id')

    if method == 'search_brain':
        query = params.get('query')
        if not query:
            raise HTTPException(status_code=400, detail='Missing query')

        # run search in thread
        from src.modules.module4_rag import RAGEngine

        user_folder = _find_user_folder(user_id)

        def _search():
            try:
                rag = RAGEngine(user_root=user_folder)
                res = rag.query(query)
                # Return chunks or documents
                return {'result': res}
            except Exception as e:
                return {'error': str(e)}

        result = await _run_in_thread(_search)

    elif method == 'read_full_note':
        folder_name = params.get('folder_name')
        if not folder_name:
            raise HTTPException(status_code=400, detail='Missing folder_name')

        user_folder = _find_user_folder(user_id)

        def _read_note():
            for p in user_folder.iterdir():
                if p.is_dir() and folder_name in p.name:
                    note = p / 'Knowledge.md'
                    if note.exists():
                        return {'result': note.read_text(encoding='utf-8')}
                    return {'error': 'Knowledge.md not found in folder'}
            return {'error': 'Folder not found'}

        result = await _run_in_thread(_read_note)

    elif method == 'get_recent_activity':
        user_folder = _find_user_folder(user_id)

        def _list_recent():
            out = []
            if not user_folder.exists():
                return {'result': out}
            for p in sorted([d for d in user_folder.iterdir() if d.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
                out.append(p.name)
            return {'result': out}

        result = await _run_in_thread(_list_recent)

    else:
        raise HTTPException(status_code=400, detail='Unknown method')

    # push to any connected SSE clients for this user
    queues = _connections.get(user_id, [])
    for q in list(queues):
        try:
            await q.put({'method': method, 'id': req_id, 'payload': result})
        except Exception:
            # ignore
            pass

    return JSONResponse({'id': req_id, 'result': result})
