"""Shared cross-camera entry. Credentials and upstream bearer stay server-side.

Explicit opt-in only; every reachable client shares the configured identity.
Deploy only on a trusted LAN, not on the public internet.
"""
import asyncio
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException, Request
from starlette.responses import Response


def enabled():
    return os.environ.get('CROSS_SHARED_ADMIN_ACCESS', '').lower() == 'true'


class CrossSession:
    def __init__(self, client, username, password):
        self.client, self.username, self.password = client, username, password
        self.token, self.expires = None, 0
        self.lock = asyncio.Lock()

    async def login(self):
        async with self.lock:
            if self.token and time.monotonic() < self.expires:
                return
            response = await self.client.post('/api/v1/auth/login', json={
                'username': self.username, 'password': self.password})
            response.raise_for_status()
            body = response.json()
            body = body.get('data', body)
            token = body.get('access_token') or body.get('token')
            if not token:
                raise ValueError('authentication response missing token')
            duration = float(body.get('expires_in', 300))
            if body.get('expires_at') is not None:
                try:
                    deadline = float(body['expires_at'])
                except ValueError:
                    deadline = datetime.fromisoformat(body['expires_at'].replace('Z', '+00:00')).timestamp()
                duration = deadline - time.time()
            if duration <= 0:
                raise ValueError('token already expired')
            self.token, self.expires = token, time.monotonic() + max(1, min(duration - 10, 3600))

    async def request(self, method, uri, body=b'', headers=None):
        await self.login()
        token = self.token
        response = await self.client.request(method, uri, content=body,
                                            headers={**(headers or {}), 'Authorization': f'Bearer {token}'})
        if response.status_code == 401:
            if self.token == token:
                self.token = None
            await self.login()
            response = await self.client.request(method, uri, content=body,
                                                headers={**(headers or {}), 'Authorization': f'Bearer {self.token}'})
        return response


def patch_html(source):
    # A UI marker, not an upstream token. The router restores the user through the proxy.
    script = ('<script>localStorage.setItem("cross_camera_access_token","cross-gateway-session");'
              'localStorage.removeItem("cross_camera_user");'
              'if(location.pathname==="/login")history.replaceState(null,"","/embed/analysis");</script>')
    if '<head>' not in source:
        raise ValueError('unexpected cross-camera document')
    return source.replace('<head>', '<head>' + script, 1)


@asynccontextmanager
async def lifespan(app):
    base = os.environ.get('CROSS_CAMERA_BASE_URL', '').rstrip('/')
    parsed = urlsplit(base)
    username, password = os.environ.get('CROSS_CAMERA_USERNAME', ''), os.environ.get('CROSS_CAMERA_PASSWORD', '')
    if not enabled() or parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.query or parsed.fragment or not username or not password:
        raise RuntimeError('Shared cross-camera entry is not explicitly configured')
    async with httpx.AsyncClient(base_url=base, timeout=45, trust_env=False, follow_redirects=False) as client:
        app.state.session = CrossSession(client, username, password)
        yield


app = FastAPI(title='跨镜追踪共享入口', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.api_route('/{path:path}', methods=['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])
async def forward(path: str, request: Request):
    if not enabled():
        raise HTTPException(503, '跨镜共享入口未启用')
    if path.startswith('/') or '\\' in path or any(part in ('.', '..') for part in path.split('/')):
        raise HTTPException(400, '无效路径')
    uri = '/' + path + (('?' + request.url.query) if request.url.query else '')
    headers = {key: value for key, value in request.headers.items()
               if key.lower() in ('content-type', 'accept', 'range', 'if-range')}
    try:
        upstream = await request.app.state.session.request(request.method, uri, await request.body(), headers)
        if upstream.is_redirect:
            raise ValueError('unexpected upstream redirect')
        content = upstream.content
        content_type = upstream.headers.get('content-type', '')
        if upstream.status_code == 200 and 'text/html' in content_type:
            content = patch_html(upstream.text).encode()
        safe_headers = {key: value for key, value in upstream.headers.items()
                        if key.lower() in ('content-type', 'content-range', 'accept-ranges', 'content-disposition')}
        safe_headers.update({'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer', 'X-Content-Type-Options': 'nosniff'})
        return Response(content, status_code=upstream.status_code, headers=safe_headers)
    except (httpx.HTTPError, ValueError, TypeError):
        raise HTTPException(502, '跨镜平台连接或自动认证失败，请检查后台配置') from None
