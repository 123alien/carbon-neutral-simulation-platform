"""Read-only adapter for the edge appliance; never expose stream credentials."""
import asyncio
import hashlib
import os
import re
import secrets
from datetime import datetime, timezone

import httpx


async def overview():
    base = os.environ.get('EDGE_BOX_BASE_URL', '').rstrip('/')
    user = os.environ.get('EDGE_BOX_USERNAME', '')
    password = os.environ.get('EDGE_BOX_PASSWORD', '')
    if not user or not password:
        return {'configured': True, 'status': 'OFFLINE', 'message': '边缘盒子凭证未配置'}
    try:
        async with httpx.AsyncClient(base_url=base, timeout=12, trust_env=False,
                                     headers={'Custom-Header': 'WebLoginHandle=10081124'}) as client:
            challenge = await client.put('/API/V1.0/System/Security/Login')
            header = challenge.headers.get('www-authenticate', '')
            nonce = re.search(r'nonce="([^"]+)"', header).group(1)
            realm = re.search(r'realm="([^"]+)"', header).group(1)
            md5 = lambda value: hashlib.md5(value.encode()).hexdigest()

            async def read(method, path, body=None):
                cnonce = secrets.token_hex(16)
                digest = md5(f'{md5(f"{user}:{realm}:{password}")}:{nonce}:00000001:{cnonce}:auth:{md5(f"{method}:{path}")}')
                auth = (f'Digest username="{user}",realm="{realm}",qop="auth",nonce="{nonce}",'
                        f'algorithm="MD5",cnonce="{cnonce}",nc="00000001",uri="{path}",response="{digest}"')
                response = await client.request(method, path, json=body, headers={'Authorization': auth})
                response.raise_for_status()
                result = response.json()
                if result.get('code') != 0:
                    raise ValueError('upstream rejected request')
                return result.get('data')

            await read('PUT', '/API/V1.0/System/Security/Login')
            device, channels, algorithms, runtime = await asyncio.gather(
                read('POST', '/api/v2/device/get', {}), read('POST', '/api/v2/channel/list', {}),
                read('POST', '/api/v2/smart/enable/list', {}), read('GET', '/API/V1.0/System/RunInfo'))
        safe_channels = [{'channel_id': x.get('channel_id'), 'name': x.get('channel_name'),
                          'online': True if x.get('status') == 1 else False if x.get('status') == 2 else None,
                          'status': x.get('status'), 'offline_reason': x.get('off_reason')}
                         for x in channels.get('channel_list', [])]
        configured = sum(len(x.get('algo_model') or []) for x in algorithms)
        offline = sum(x['online'] is False for x in safe_channels)
        box = {'box_id': device.get('serial_number'), 'name': device.get('device_name'),
               'model': device.get('device_model'), 'firmware': device.get('firmware_version'),
               'online': True, 'algorithm_count': configured, 'running_algorithms': None,
               'uptime_seconds': runtime.get('Runtime'), 'channels': safe_channels,
               'longitude': None, 'latitude': None, 'building_id': None}
        # The source-system status represents the appliance itself. Camera/channel
        # availability is reported separately and must not downgrade an online box.
        return {'configured': True, 'status': 'READY',
                'observed_at': datetime.now(timezone.utc).isoformat(), 'boxes': [box], 'alarms': [],
                'alarms_available': False, 'configured_algorithms': configured,
                'message': f"{box['name']}已连接 · {len(safe_channels)}个点位 / {offline}个离线 · {configured}项已配置算法；告警接口待核验"}
    except (httpx.HTTPError, ValueError, TypeError, AttributeError, KeyError):
        return {'configured': True, 'status': 'OFFLINE', 'boxes': [], 'alarms': [],
                'alarms_available': False, 'message': '边缘盒子读取失败，请检查网络或登录凭证'}
