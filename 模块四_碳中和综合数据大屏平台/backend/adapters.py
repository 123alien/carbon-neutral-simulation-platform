"""Read-only module-one gateway, with explicit source and period semantics."""
import asyncio
import os
import time
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException

cache: dict = {}
lock = asyncio.Lock()


def base_url():
    return os.environ.get('MODULE_ONE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')


async def get_json(client, path):
    response = await client.get(path)
    response.raise_for_status()
    return response.json()


async def read_energy_meter(client):
    """Compose the meter view from stable module-one APIs; keeps compatibility during rolling upgrades."""
    sources = await get_json(client, '/api/data-sources?enterprise_id=11')
    source = next((item for item in reversed(sources) if item.get('source_type') == 'MQTT' and item.get('name') == '能源管控电表 MQTT 实时数据'), None)
    if not source:
        return {'connected': False, 'subscribed': False, 'devices': [], 'device_count': 0, 'online_count': 0}
    source_id = source['id']
    runtime, devices = await asyncio.gather(
        get_json(client, f'/api/data-sources/{source_id}/runtime'),
        get_json(client, f'/api/devices?enterprise_id=11&data_source_id={source_id}'),
    )
    last_message = runtime.get('last_message_at')
    fresh = False
    if last_message:
        observed = datetime.fromisoformat(str(last_message).replace('Z', '+00:00'))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        fresh = (datetime.now(timezone.utc) - observed).total_seconds() <= 180
    online = bool(runtime.get('connected') and runtime.get('subscribed') and fresh)
    labels = {'phase_a_voltage_v':'A相电压','phase_b_voltage_v':'B相电压','phase_c_voltage_v':'C相电压','phase_a_current_a':'A相电流','phase_b_current_a':'B相电流','phase_c_current_a':'C相电流','power_kw':'实时功率','energy_kwh':'累计电量','water_m3':'累计水量','temperature_c':'温度','humidity_pct':'湿度'}
    result = []
    for device in devices:
        metrics = await get_json(client, f"/api/devices/{device['id']}/metrics")
        grouped = {}
        for row in metrics[-660:]:
            grouped.setdefault(row.get('metric_name'), []).append(row)
        factors = []
        for code, rows in grouped.items():
            latest = rows[-1]
            factors.append({'metric_code': code, 'metric_name': labels.get(code, code), 'value': latest.get('value'), 'unit': latest.get('unit'), 'timestamp': latest.get('timestamp'), 'quality_status': latest.get('quality'), 'points': [{'timestamp': x.get('timestamp'), 'value': x.get('value')} for x in rows[-60:]]})
        location=device.get('metadata_json') or {}
        result.append({'device_id': device.get('external_id'), 'device_name': device.get('name'), 'device_type': device.get('device_type'), 'online': online, 'device_status': 'online' if online else 'offline', 'building_id': location.get('building_id'), 'floor_id': location.get('floor_id'), 'mapping_status': location.get('mapping_status','UNMAPPED'), 'latest_observation_time': last_message, 'factors': factors})
    return {'source_type':'ENERGY_MQTT','data_label':'REALTIME','connected':bool(runtime.get('connected')),'subscribed':bool(runtime.get('subscribed')),'runtime_status':runtime.get('runtime_status'),'last_message_at':last_message,'device_count':len(result),'online_count':sum(x['online'] for x in result),'offline_count':sum(not x['online'] for x in result),'devices':result}


def aggregate(snapshot):
    rows = snapshot['buildings']
    current = snapshot['current']
    demand = current['load_after_saving_kwh'] + current['ev_charging_load_kwh']
    return [
        {'code': 'electricity', 'name': '本年累计用电', 'value': sum(r['energy_kwh'] for r in rows), 'unit': 'kWh'},
        {'code': 'water', 'name': '本年累计用水', 'value': sum(r['water_m3'] for r in rows), 'unit': 'm³'},
        {'code': 'carbon', 'name': '本年累计碳排', 'value': snapshot['total_emission_t'], 'unit': 'tCO₂e'},
        {'code': 'renewable', 'name': '当前可再生能源占比', 'value': current['renewable_generation_kwh'] / demand * 100 if demand else None, 'unit': '%'},
        {'code': 'load', 'name': '当前负荷', 'value': demand, 'unit': 'kW'},
        {'code': 'storage', 'name': '当前储能状态', 'value': current['storage_soc_kwh'], 'unit': 'kWh'},
    ]


async def dashboard(force=False):
    now = time.monotonic()
    if not force and cache.get('expires', 0) > now:
        return cache['data']
    async with lock:
        if not force and cache.get('expires', 0) > time.monotonic():
            return cache['data']
        data = {'campus_id': 'HBUE', 'campus_name': '湖北经济学院智慧低碳校园',
                'received_at': datetime.now(timezone.utc).isoformat(), 'observation_time': None,
                'data_notice': '尚未接入业务结果', 'metrics': [], 'building_results': [],
                'hourly': [], 'trend': [], 'alerts': [], 'simulation': None, 'market': None,
                'external_status': {}, 'device_status': [], 'sources': [
                    {'id': 'iot', 'name': '室内环境物联网', 'status': 'NOT_CONNECTED'},
                    {'id': 'energy_meter', 'name': '能源管控电表', 'status': 'NOT_CONNECTED'},
                    {'id': 'weather', 'name': '室外气象站', 'status': 'NOT_CONNECTED'},
                    {'id': 'simulation', 'name': '模块一校园结果', 'status': 'ERROR'},
                    {'id': 'cross_camera', 'name': '跨镜追踪统计', 'status': 'ON_DEMAND'},
                ]}
        try:
            async with httpx.AsyncClient(base_url=base_url(), timeout=30, trust_env=False) as client:
                sites = await get_json(client, '/api/sites')
                site = next((s for s in sites if s['code'] == 'HBUE'), None)
                if not site:
                    raise ValueError('上游没有 HBUE 校园对象')
                sid = site['id']
                snapshot = await get_json(client, f'/api/result-interface/campuses/{sid}/live-demo?history_hours=24')
                if snapshot['campus_id'] != 'HBUE' or snapshot['source_type'] != 'DEMO_SIMULATION':
                    raise ValueError('校园结果来源与预期不一致')
                data.update(metrics=aggregate(snapshot), building_results=snapshot['buildings'],
                            hourly=snapshot['hourly'], current=snapshot['current'], trend=snapshot['trend'],
                            observation_time=snapshot['timestamp'], data_notice=snapshot['data_notice'],
                            limitations=snapshot['limitations'], factors=snapshot['factors'],
                            period_start=snapshot['period_start'], clean_reduction_t=snapshot['clean_reduction_t'])
                for metric in data['metrics']:
                    metric.update(source_system='MODULE_ONE', source_type='DEMO_SIMULATION', data_class='DEMO_SIMULATION',
                                  campus_id='HBUE', building_id=None, floor_id=None, area_id=None, camera_id=None,
                                  observation_time=snapshot['timestamp'], received_at=data['received_at'],
                                  metric_code=metric['code'], quality_status='SIMULATED')
                data['sources'][3]['status'] = 'DEMO_SIMULATION'
                data['sources'][3]['message'] = '校园能耗与碳排为示范仿真数据'
                optional = await asyncio.gather(*[get_json(client, p) for p in (
                    f'/api/result-interface/campuses/{sid}/simulation',
                    f'/api/result-interface/campuses/{sid}/carbon-market',
                    '/api/external-data/status',
                    '/api/external-data/device-dashboard?hours=1',
                    '/api/external-data/energy-meter-dashboard?hours=1',
                    '/api/cross-camera-adapter/health',
                )], return_exceptions=True)
                for key, result in zip(('simulation', 'market', 'external_status', 'device_dashboard', 'energy_meter_dashboard', 'cross_camera_health'), optional):
                    if not isinstance(result, Exception):
                        data[key] = result
                from backend.simulation_results import read_paths
                try:
                    data['simulation'] = await read_paths(client, site)
                except (httpx.HTTPError, ValueError, KeyError, TypeError):
                    data['simulation'] = {'campus_id': 'HBUE', 'paths': [], 'data_notice': '校园推演结果读取失败'}
                ext = data['external_status']
                device_dashboard = data.pop('device_dashboard', {})
                energy_meter_dashboard = data.pop('energy_meter_dashboard', {})
                if not isinstance(energy_meter_dashboard, dict) or not energy_meter_dashboard:
                    try:
                        energy_meter_dashboard = await read_energy_meter(client)
                    except (httpx.HTTPError, ValueError, KeyError, TypeError):
                        energy_meter_dashboard = {}
                cross_health = data.pop('cross_camera_health', {})
                if isinstance(device_dashboard, dict) and device_dashboard.get('collection_connected'):
                    device_count = int(device_dashboard.get('device_count') or 0)
                    online_count = int(device_dashboard.get('online_count') or 0)
                    data['sources'][0]['status'] = 'OBSERVED' if online_count else 'NO_OBSERVATIONS'
                    data['sources'][0]['message'] = (
                        f'真实设备 {device_count} 台 · 在线 {online_count} 台 · 最近采集 '
                        f'{device_dashboard.get("last_collected_at") or "未提供"}'
                    )
                    for device in device_dashboard.get('devices', []):
                        factors = [{
                            'metric_name': factor.get('metric_name'), 'value': factor.get('value'),
                            'unit': factor.get('unit'), 'timestamp': factor.get('timestamp'),
                            'quality_status': factor.get('quality_status'),
                        } for factor in device.get('factors', [])]
                        timestamps = [factor.get('timestamp') for factor in factors if factor.get('timestamp')]
                        data['device_status'].append({
                            'device_id': device.get('device_id'), 'device_name': device.get('device_name'),
                            'online': device.get('online'), 'device_status': device.get('device_status'),
                            'building_id': device.get('building_id'), 'floor_id': device.get('floor_id'),
                            'mapping_status': device.get('mapping_status'), 'latest_observation_time': max(timestamps) if timestamps else None,
                            'factors': factors,
                        })
                    data['alerts'] = [{
                        'device_id': device.get('device_id'), 'level': 'OFFLINE',
                        'message': '设备离线', 'timestamp': device.get('latest_observation_time'),
                    } for device in data['device_status'] if device.get('online') is False]
                elif ext.get('IOT_CLOUD', {}).get('connected'):
                    data['sources'][0]['status'] = 'NO_OBSERVATIONS'
                    data['sources'][0]['message'] = '平台可达，但未读取到设备实时状态'
                if isinstance(energy_meter_dashboard, dict):
                    meter_source=data['sources'][1]
                    meter_source['status']='OBSERVED' if energy_meter_dashboard.get('online_count') else ('NO_OBSERVATIONS' if energy_meter_dashboard.get('connected') else 'NOT_CONNECTED')
                    meter_source['message']=(f"真实电表 {energy_meter_dashboard.get('device_count',0)} 台 · 在线 {energy_meter_dashboard.get('online_count',0)} 台 · 最近上报 {energy_meter_dashboard.get('last_message_at') or '等待设备上报'}")
                    data['device_status'].extend(energy_meter_dashboard.get('devices') or [])
                weather = ext.get('WEATHER_STATION', {})
                data['sources'][2]['status'] = 'OBSERVED' if weather.get('online') and weather.get('valid_value_count', 0) > 0 else ('NO_OBSERVATIONS' if weather.get('connected') else 'NOT_CONNECTED')
                data['sources'][2]['message'] = '已有室外气象观测' if data['sources'][2]['status'] == 'OBSERVED' else '接口可达，当前无有效气象观测值'
                if isinstance(cross_health, dict) and cross_health.get('upstream_reachable'):
                    ready = cross_health.get('login_success') and cross_health.get('token_valid')
                    data['sources'][4]['status'] = 'LIVE_READY' if ready else 'NO_OBSERVATIONS'
                    data['sources'][4]['message'] = cross_health.get('message') or ('实时服务已就绪' if ready else '服务可达，认证未就绪')
                # Return only whitelisted status fields, never upstream secrets or raw auth responses.
                fields = ('connected', 'online', 'property_count', 'valid_value_count', 'latest_observation_time', 'collected_at', 'credentials_configured')
                data['external_status'] = {k: {f: v[f] for f in fields if f in v} for k, v in ext.items() if isinstance(v, dict)}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            data['sources'][3]['message'] = '模块一校园结果暂不可用，请检查后端地址与校园数据'
        from backend.metric_rules import apply_to_dashboard
        apply_to_dashboard(data)
        cache.update(data=data, expires=time.monotonic() + 25)
        return data


async def paths(request):
    try:
        async with httpx.AsyncClient(base_url=base_url(), timeout=45, trust_env=False) as client:
            response = await client.post('/api/cross-camera-adapter/paths', json=request)
        if not response.is_success:
            raise HTTPException(502, '轨迹读取失败，请检查上游服务、凭证、任务及视频起始时间')
        result = response.json()
        if result.get('source') != request['source']:
            raise HTTPException(502, '轨迹数据源不一致，拒绝使用静默备用数据')
        return result
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, '跨镜结果服务不可达或响应异常')


async def cross_camera_status(resource):
    try:
        async with httpx.AsyncClient(base_url=base_url(), timeout=15, trust_env=False) as client:
            result = await get_json(client, '/api/cross-camera-adapter/' + resource)
        if resource == 'health':
            fields = ('upstream_reachable', 'credentials_configured', 'login_success', 'token_valid', 'status', 'message', 'video_start_time', 'time_notice')
            return {key: result.get(key) for key in fields}
        return [{'task_id': row['task_id'], 'status': row.get('status'), 'created_at': row.get('created_at')} for row in result]
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise HTTPException(502, '跨镜状态或真实任务列表读取失败')


async def edge_box_overview():
    """Read a configured edge-box overview endpoint; never substitute IoT sensors."""
    if os.environ.get('EDGE_BOX_BASE_URL', '').strip():
        from backend.edge_box import overview
        return await overview()
    url = os.environ.get('EDGE_BOX_OVERVIEW_URL', '').strip()
    if not url:
        return {'configured': False, 'status': 'UNCONFIGURED', 'message': '尚未配置边缘盒子聚合接口'}
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=False, trust_env=False) as client:
            response = await client.get(url)
            response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError('unexpected payload')
        # Whitelist the contract so credentials and arbitrary upstream fields cannot leak to the screen.
        boxes = payload.get('boxes') if isinstance(payload.get('boxes'), list) else []
        alarms = payload.get('alarms') if isinstance(payload.get('alarms'), list) else []
        return {'configured': True, 'status': payload.get('status'), 'observed_at': payload.get('observed_at'),
                'message': payload.get('message'),
                'boxes': [{'box_id': x.get('box_id'), 'name': x.get('name'), 'online': x.get('online'),
                           'algorithm_count': x.get('algorithm_count'), 'running_algorithms': x.get('running_algorithms'),
                           'longitude': x.get('longitude'), 'latitude': x.get('latitude'), 'building_id': x.get('building_id')}
                          for x in boxes if isinstance(x, dict)],
                'alarms': [{'alarm_id': x.get('alarm_id'), 'box_id': x.get('box_id'), 'level': x.get('level'),
                            'title': x.get('title'), 'occurred_at': x.get('occurred_at')}
                           for x in alarms if isinstance(x, dict)]}
    except (httpx.HTTPError, ValueError, TypeError):
        return {'configured': True, 'status': 'OFFLINE', 'message': '边缘盒子接口不可达或响应格式异常', 'boxes': [], 'alarms': []}
