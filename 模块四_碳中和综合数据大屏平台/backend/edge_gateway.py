"""Explicitly enabled shared-admin gateway, isolated from the dashboard origin.

Only deploy on a trusted network: all reachable clients share appliance privileges.
No appliance password, Digest secret or stream authorization is injected into JS.
"""
import asyncio
import hashlib
import json
import os
import re
import secrets
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket
from starlette.responses import Response
from websockets.asyncio.client import connect

LOGIN = '/API/V1.0/System/Security/Login'


def enabled():
    return os.environ.get('EDGE_SHARED_ADMIN_ACCESS', '').lower() == 'true'


class ApplianceSession:
    def __init__(self, client, username, password):
        self.client = client
        self.username = username
        self.password = password
        self.nonce = None
        self.realm = None
        self.lock = asyncio.Lock()

    def authorization(self, method, uri):
        # Vendor browser signs the URL path, before Axios appends query parameters.
        uri = urlsplit(uri).path
        md5 = lambda text: hashlib.md5(text.encode()).hexdigest()
        cnonce = secrets.token_hex(16)
        ha1 = md5(f'{self.username}:{self.realm}:{self.password}')
        response = md5(f'{ha1}:{self.nonce}:00000001:{cnonce}:auth:{md5(f"{method}:{uri}")}')
        return (f'Digest username="{self.username}",realm="{self.realm}",qop="auth",'
                f'nonce="{self.nonce}",algorithm="MD5",cnonce="{cnonce}",'
                f'nc="00000001",uri="{uri}",response="{response}"')

    @staticmethod
    def rejected(response):
        if response.status_code == 401:
            return True
        if 'json' not in response.headers.get('content-type', ''):
            return False
        try:
            body = response.json()
            return isinstance(body, dict) and (body.get('code') == 401 or body.get('status_code') in (401, 60031)
                                               or (body.get('Response') or {}).get('StatusCode') in (401, 60031))
        except ValueError:
            return False

    async def login(self, previous=None):
        async with self.lock:
            if previous is not None and self.nonce and self.nonce != previous:
                return
            challenge = await self.client.put(LOGIN)
            header = challenge.headers.get('www-authenticate', '')
            nonce = re.search(r'nonce="([^"]+)"', header)
            realm = re.search(r'realm="([^"]+)"', header)
            if not nonce or not realm:
                raise ValueError('unsupported authentication challenge')
            self.nonce, self.realm = nonce.group(1), realm.group(1)
            response = await self.client.put(LOGIN, headers={'Authorization': self.authorization('PUT', LOGIN)})
            body = response.json()
            if response.status_code != 200 or body.get('code', body.get('status_code')) != 0:
                self.nonce = None
                raise ValueError('appliance login rejected')

    async def request(self, method, uri, content=b'', headers=None):
        if not self.nonce:
            await self.login()
        original = self.nonce
        response = await self.client.request(method, uri, content=content, headers={
            **(headers or {}), 'Authorization': self.authorization(method, uri)})
        # Renew expired session once; never hide other business errors or loop on bad credentials.
        if self.rejected(response):
            await self.login(previous=original)
            response = await self.client.request(method, uri, content=content, headers={
                **(headers or {}), 'Authorization': self.authorization(method, uri)})
        return response


def patch_script(source):
    start = source.find('function HttpRequestHeaders(')
    end = source.find('function downloadFileFunc(', start)
    guard = 'const l=sessionStorage.getItem("pwd");if(isHDMI.value'
    if start < 0 or end < 0 or source.count(guard) != 1:
        raise ValueError('vendor frontend changed; refusing unverified auto-login adaptation')
    source = source[:start] + 'function HttpRequestHeaders(){return {}}' + source[end:]
    return source.replace(guard, 'const l="edge-gateway-session";if(isHDMI.value')


def patch_html(source, username):
    # Marker satisfies the original UI's session checks, but cannot authenticate directly.
    name = json.dumps(username).replace('<', '\\u003c')
    script = ('<script>sessionStorage.setItem("name",' + name + ');'
              'sessionStorage.setItem("pwd","edge-gateway-session");'
              'if(!location.hash||location.hash==="#/login"||location.hash==="#/")'
              'history.replaceState(null,"",location.pathname+location.search+"#/id-manage");</script>')
    if '<head>' not in source:
        raise ValueError('unexpected appliance document')
    return source.replace('<head>', '<head>' + script, 1)


@asynccontextmanager
async def lifespan(app):
    base = os.environ.get('EDGE_BOX_BASE_URL', '').rstrip('/')
    parsed = urlsplit(base)
    if not enabled() or parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
        raise RuntimeError('Shared admin gateway not explicitly configured')
    username = os.environ.get('EDGE_BOX_USERNAME', '')
    password = os.environ.get('EDGE_BOX_PASSWORD', '')
    if not username or not password:
        raise RuntimeError('Appliance credentials missing')
    async with httpx.AsyncClient(base_url=base, timeout=30, trust_env=False, follow_redirects=False,
                                headers={'Custom-Header': 'WebLoginHandle=10081124'}) as client:
        app.state.appliance = ApplianceSession(client, username, password)
        app.state.base = base
        yield


app = FastAPI(title='边缘盒子共享入口', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.api_route('/{path:path}', methods=['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])
async def forward(path: str, request: Request):
    if not enabled():
        raise HTTPException(503, '共享入口未启用')
    # Fixed appliance only. Never follow redirects or accept a destination supplied by clients.
    if path.startswith('/') or '\\' in path or any(part in ('.', '..') for part in path.split('/')):
        raise HTTPException(400, '无效路径')
    uri = '/' + path + (('?' + request.url.query) if request.url.query else '')
    headers = {key: value for key, value in request.headers.items()
               if key.lower() in ('content-type', 'accept', 'range', 'if-range')}
    try:
        upstream = await request.app.state.appliance.request(request.method, uri, await request.body(), headers)
        content = upstream.content
        content_type = upstream.headers.get('content-type', '')
        if upstream.status_code == 200 and 'text/html' in content_type:
            content = patch_html(upstream.text, request.app.state.appliance.username).encode()
        elif upstream.status_code == 200 and path.startswith('assets/index.') and path.endswith('.js') and 'function HttpRequestHeaders(' in upstream.text:
            content = patch_script(upstream.text).encode()
        safe_headers = {key: value for key, value in upstream.headers.items()
                        if key.lower() in ('content-type', 'content-range', 'accept-ranges', 'content-disposition')}
        safe_headers.update({'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer', 'X-Content-Type-Options': 'nosniff'})
        if upstream.is_redirect:
            raise ValueError('unexpected upstream redirect')
        return Response(content, status_code=upstream.status_code, headers=safe_headers)
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, '边缘平台连接或自动认证失败，请检查后台配置') from None


@app.websocket('/{path:path}')
async def socket_proxy(socket: WebSocket, path: str):
    if not enabled() or path.startswith('/') or '\\' in path or any(part in ('.', '..') for part in path.split('/')):
        await socket.close(code=1008)
        return
    session = socket.app.state.appliance
    try:
        if not session.nonce:
            await session.login()
        uri = '/' + path + (('?' + socket.url.query) if socket.url.query else '')
        base = socket.app.state.base
        target = ('wss' if base.startswith('https:') else 'ws') + base[base.index(':'):] + uri
        protocols = [x.strip() for x in socket.headers.get('sec-websocket-protocol', '').split(',') if x.strip()]
        async with connect(target, subprotocols=protocols or None, proxy=None,
                           additional_headers={'Authorization': session.authorization('GET', uri),
                                               'Custom-Header': 'WebLoginHandle=10081124'},
                           max_size=None, open_timeout=15) as upstream:
            await socket.accept(subprotocol=upstream.subprotocol)

            async def browser_to_device():
                while True:
                    event = await socket.receive()
                    if event['type'] == 'websocket.disconnect':
                        return
                    await upstream.send(event.get('bytes') if event.get('bytes') is not None else event.get('text', ''))

            async def device_to_browser():
                async for message in upstream:
                    if isinstance(message, bytes):
                        await socket.send_bytes(message)
                    else:
                        await socket.send_text(message)

            tasks = [asyncio.create_task(browser_to_device()), asyncio.create_task(device_to_browser())]
            try:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
    except Exception:
        # Never send upstream authorization/connection details to browsers or logs.
        pass
    finally:
        try:
            await socket.close()
        except RuntimeError:
            pass
