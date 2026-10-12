"""Independent display gateway. Upstream datasets are read-only."""
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import RedirectResponse
from backend import adapters

app = FastAPI(title="碳中和综合数据大屏平台", version="0.1.0")
ROOT = Path(__file__).resolve().parents[1]
SPATIAL = Path(os.environ.get("HBUE_SPATIAL_DIR") or str(ROOT.parent / "phase4_work/frontend/public/data/hbue"))


@app.get('/api/edge-entry')
def edge_entry(request: Request):
    from backend.edge_gateway import enabled
    if not enabled():
        raise HTTPException(503, '边缘平台共享入口未启用')
    host = request.url.hostname
    if not host:
        raise HTTPException(400, '缺少访问地址')
    host = f'[{host}]' if ':' in host else host
    port = int(os.environ.get('EDGE_GATEWAY_PORT', '8210'))
    return RedirectResponse(f'{request.url.scheme}://{host}:{port}/#/id-manage', status_code=303,
                            headers={'Cache-Control': 'no-store'})


@app.get('/api/cross-entry')
def cross_entry(request: Request, task_id: str | None = None):
    from backend.cross_gateway import enabled
    from urllib.parse import urlencode
    if not enabled():
        raise HTTPException(503, '跨镜平台共享入口未启用')
    if task_id is not None and not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', task_id):
        raise HTTPException(400, '任务编号无效')
    host = request.url.hostname
    if not host:
        raise HTTPException(400, '缺少访问地址')
    host = f'[{host}]' if ':' in host else host
    port = int(os.environ.get('CROSS_GATEWAY_PORT', '8220'))
    query = '?' + urlencode({'task_id': task_id}) if task_id else ''
    return RedirectResponse(f'{request.url.scheme}://{host}:{port}/embed/analysis{query}', status_code=303,
                            headers={'Cache-Control': 'no-store'})


class Metric(BaseModel):
    source_system: str
    source_type: str
    campus_id: str
    building_id: str | None = None
    floor_id: str | None = None
    area_id: str | None = None
    camera_id: str | None = None
    observation_time: datetime
    received_at: datetime
    metric_code: str
    value: float
    unit: str
    quality_status: str
    data_class: Literal["OBSERVED", "DEMO_SIMULATION", "PREDICTED"]


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "module-four", "version": "0.1.0"}


@app.get("/api/spatial/{layer}")
def spatial(layer: str):
    names = {"boundary": "hbue_campus_boundary.geojson", "buildings": "hbue_buildings.geojson", "roads": "hbue_roads.geojson", "landscape": "hbue_landscape.geojson"}
    if layer not in names:
        raise HTTPException(404, "空间图层不存在")
    path = SPATIAL / names[layer]
    if not path.is_file():
        raise HTTPException(503, "校园空间文件未配置，请设置 HBUE_SPATIAL_DIR")
    return json.loads(path.read_text(encoding="utf-8-sig"))


@app.get("/api/dashboard")
async def dashboard(force: bool = False):
    return await adapters.dashboard(force)


@app.get("/api/bff/overview")
async def bff_overview(force: bool = False):
    """Stable, normalized overview contract consumed by the large screen."""
    from backend.bff import overview
    return await overview(force)


@app.get("/api/bff/chart-library")
def bff_chart_library():
    from backend.chart_library import library
    return library()


@app.get('/api/weather/current')
async def current_weather():
    from backend.weather import current_weather as read
    return await read()


class PathRequest(BaseModel):
    source: Literal['DEMO', 'LIVE'] = 'DEMO'
    task_id: str | None = None
    video_start_time: datetime | None = None


class MetricRulePayload(BaseModel):
    parameters: dict[str, float]
    rules: list[dict]
    change_note: str | None = None
    expected_version: int | None = None


class MetricRuleRollback(BaseModel):
    target_version: int
    expected_version: int


@app.get('/api/metric-rules')
async def metric_rules():
    from backend.metric_rules import get_store
    return get_store()


@app.post('/api/metric-rules/preview')
async def metric_rules_preview(payload: MetricRulePayload):
    from backend.metric_rules import FormulaError, preview
    try:
        data = await adapters.dashboard(False)
        return preview(payload.model_dump(), data)
    except FormulaError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post('/api/metric-rules/publish')
async def metric_rules_publish(payload: MetricRulePayload):
    from backend.metric_rules import FormulaError, publish
    try:
        data = await adapters.dashboard(False)
        result = publish(payload.model_dump(), data)
        adapters.cache.clear()
        return result
    except FormulaError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post('/api/metric-rules/rollback')
async def metric_rules_rollback(payload: MetricRuleRollback):
    from backend.metric_rules import FormulaError, rollback
    try:
        data = await adapters.dashboard(False)
        result = rollback(payload.target_version, payload.expected_version, data)
        adapters.cache.clear()
        return result
    except FormulaError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post('/api/activities/paths')
async def activity_paths(request: PathRequest):
    payload = request.model_dump(mode='json')
    payload['allow_demo_fallback'] = False
    from backend.road_routes import adapt_routes
    from starlette.concurrency import run_in_threadpool
    result = await adapters.paths(payload)
    return await run_in_threadpool(adapt_routes, result, SPATIAL)


@app.get('/api/activities/latest-paths')
async def latest_activity_paths():
    """Return the newest finished task that actually contains cross-camera paths."""
    from backend.road_routes import adapt_routes
    from starlette.concurrency import run_in_threadpool
    tasks = await adapters.cross_camera_status('tasks')
    completed = [task for task in tasks if str(task.get('status', '')).lower() == 'finished']
    checked = []
    for task in completed[:10]:
        task_id = task.get('task_id')
        if not task_id:
            continue
        checked.append(task_id)
        try:
            result = await adapters.paths({'source': 'LIVE', 'task_id': task_id,
                                           'video_start_time': None, 'allow_demo_fallback': False})
            if result.get('paths'):
                routed = await run_in_threadpool(adapt_routes, result, SPATIAL)
                routed['selected_task_id'] = task_id
                routed['selection_notice'] = '最新完成任务没有跨镜匹配时，自动选取最近一条包含真实跨镜路径的完成任务。'
                return routed
        except HTTPException:
            continue
    return {'source': 'LIVE', 'selected_task_id': None, 'paths': [], 'cameras': [], 'warnings': [],
            'checked_task_ids': checked, 'data_notice': '最近完成任务中没有可绘制的真实跨镜路径。'}


@app.get('/api/activities/showcase-paths')
async def showcase_activity_paths():
    """Road-routed demonstration paths for the spatial overview showcase."""
    from backend.road_routes import adapt_routes
    from starlette.concurrency import run_in_threadpool
    result = await adapters.paths({'source': 'DEMO', 'task_id': None,
                                   'video_start_time': None, 'allow_demo_fallback': False})
    routed = await run_in_threadpool(adapt_routes, result, SPATIAL)
    routed['selected_task_id'] = 'DEMO_SHOWCASE'
    routed['data_class'] = 'DEMO_SIMULATION'
    routed['selection_notice'] = '综合总览使用示范跨镜路径展示；真实任务请从跨镜追踪入口查看。'
    return routed


@app.get('/api/activities/health')
async def activity_health():
    return await adapters.cross_camera_status('health')


@app.get('/api/activities/tasks')
async def activity_tasks():
    return await adapters.cross_camera_status('tasks')

@app.get('/api/person-energy/tasks/{task_id}')
async def person_energy(task_id:str):
    import re
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',task_id):raise HTTPException(400,'任务编号无效')
    from backend.person_energy import normalize
    try:
        async with httpx.AsyncClient(base_url=adapters.base_url(),timeout=35,trust_env=False) as client:
            response=await client.get(f'/api/cross-camera-adapter/tasks/{task_id}/carbon-association')
            response.raise_for_status()
        return normalize(response.json())
    except (httpx.HTTPError,ValueError,TypeError,KeyError):
        raise HTTPException(502,'人员耗能关联结果暂不可用，请检查上游真实任务和登录状态')


@app.get('/api/person-energy/environment')
async def person_energy_environment():
    """Read-only HBUE sensor observations; not asserted to be co-located with video cameras."""
    try:
        async with httpx.AsyncClient(base_url=adapters.base_url(),timeout=12,trust_env=False) as client:
            response=await client.get('/api/external-data/device-dashboard',params={'hours':1})
            response.raise_for_status()
        payload=response.json()
        if payload.get('source_type')!='IOT_CLOUD' or payload.get('data_label')!='REALTIME':raise ValueError('unexpected source')
        devices=[]
        for item in payload.get('devices',[]):
            if item.get('building_id')!='HBUE-B125':continue
            devices.append({'device_id':item.get('device_id'),'device_name':item.get('device_name'),'online':item.get('online'),
                            'building_id':item.get('building_id'),'floor_id':item.get('floor_id'),
                            'factors':[{'metric_name':factor.get('metric_name'),'value':factor.get('value'),'unit':factor.get('unit'),'timestamp':factor.get('timestamp'),'quality_status':factor.get('quality_status'),
                                        'points':[{'timestamp':point.get('timestamp'),'value':point.get('value')} for point in factor.get('points',[])[:60] if isinstance(point,dict)]} for factor in item.get('factors',[])]})
        return {'source_type':'IOT_CLOUD','data_label':'REALTIME','location_notice':'香帅楼10楼传感器实测；未核实与视频摄像头同房间，不参与本任务个人能耗计算。',
                'last_collected_at':payload.get('last_collected_at'),'collection_connected':payload.get('collection_connected'),'devices':devices}
    except (httpx.HTTPError,ValueError,TypeError,KeyError):
        raise HTTPException(502,'室内环境实时设备数据暂不可用')


@app.get('/api/videos/tasks/{task_id}/{camera}')
async def video(task_id: str, camera: str, request: Request):
    from backend.video import task_video
    return await task_video(task_id,camera,request.headers.get('range'))


@app.get("/api/adapters/{source}/probe")
async def probe(source: str):
    """Probe only a configured, fixed health URL, never a frontend-supplied URL."""
    env_names = {"iot": "IOT_HEALTH_URL", "simulation": "SIMULATION_HEALTH_URL", "cross_camera": "CROSS_CAMERA_HEALTH_URL"}
    if source not in env_names:
        raise HTTPException(404, "数据源不存在")
    url = os.environ.get(env_names[source])
    if not url:
        return {"source": source, "status": "NOT_CONFIGURED", "message": "尚未配置后端连通性检查地址"}
    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=False, trust_env=False) as client:
            response = await client.get(url)
        return {"source": source, "status": "REACHABLE" if response.is_success else "ERROR", "http_status": response.status_code, "message": "仅验证服务响应，尚未验证业务数据与鉴权"}
    except httpx.HTTPError:
        return {"source": source, "status": "ERROR", "message": "上游服务不可达或请求超时"}
