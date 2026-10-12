"""Current regional weather, explicitly distinct from campus sensor observations."""
import asyncio
import math
import time
from datetime import datetime, timedelta, timezone

import httpx

cache = {}
lock = asyncio.Lock()
PARAMS = {'latitude': 30.42023, 'longitude': 114.42966,
          'current': 'temperature_2m,relative_humidity_2m,is_day,precipitation,weather_code,cloud_cover,wind_speed_10m',
          'timezone': 'Asia/Shanghai', 'forecast_days': 1}


def normalize(raw, now=None):
    now = now or datetime.now(timezone.utc)
    current, units = raw['current'], raw['current_units']
    stamp = datetime.fromisoformat(current['time'])
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone(timedelta(seconds=raw['utc_offset_seconds'])))
    age = (now - stamp).total_seconds()
    if age > 7200 or age < -1800:
        raise ValueError('天气数据已过期或时间异常')
    code = current.get('weather_code')
    if not isinstance(code, (int, float)) or not math.isfinite(code) or int(code) != code:
        raise ValueError('缺少有效天气代码')
    code = int(code)
    rain = code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99)
    snow = code in (71, 73, 75, 77, 85, 86)
    if code not in (0, 1, 2, 3, 45, 48) and not rain and not snow:
        raise ValueError('无法识别天气代码')
    mode = 'rain' if rain else 'sunny' if code in (0, 1) else 'cloudy'
    name = '雷雨' if code >= 95 else '降雪' if snow else '小雨' if code in (51, 53, 55) else '降雨' if rain else {0: '晴', 1: '晴间多云', 2: '多云', 3: '阴', 45: '雾', 48: '雾'}.get(code, '阴')
    metrics = []
    for key, label in [('temperature_2m', '温度'), ('relative_humidity_2m', '湿度'), ('wind_speed_10m', '风速'), ('precipitation', '降水')]:
        value = current.get(key)
        if isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) and units.get(key):
            metrics.append({'code': key, 'name': label, 'value': value, 'unit': units[key]})
    return {'status': 'AVAILABLE', 'source_type': 'REGIONAL_WEATHER_MODEL',
            'source_name': 'Open-Meteo区域天气', 'data_notice': '区域气象模型数据，非校园气象站实测',
            'source_url': 'https://open-meteo.com/', 'mode': mode, 'condition': name,
            'is_day': current.get('is_day') == 1, 'observation_time': stamp.isoformat(),
            'received_at': now.isoformat(), 'requested_coordinates': [114.42966, 30.42023],
            'grid_coordinates': [raw.get('longitude'), raw.get('latitude')],
            'weather_code': code, 'metrics': metrics}


async def current_weather():
    if cache.get('expires', 0) > time.monotonic():
        return cache['data']
    async with lock:
        if cache.get('expires', 0) > time.monotonic():
            return cache['data']
        try:
            async with httpx.AsyncClient(timeout=12, trust_env=False) as client:
                response = await client.get('https://api.open-meteo.com/v1/forecast', params=PARAMS)
                response.raise_for_status()
                result = normalize(response.json())
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            result = {'status': 'UNAVAILABLE', 'mode': None, 'metrics': [],
                      'data_notice': '当前区域天气暂不可用；不使用示意天气冒充实时数据'}
        cache.update(data=result, expires=time.monotonic() + (300 if result['status'] == 'AVAILABLE' else 30))
        return result
