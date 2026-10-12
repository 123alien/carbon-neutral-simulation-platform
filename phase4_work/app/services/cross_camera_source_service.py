"""DEMO/LIVE sources, unified camera-anchor paths; no image-to-GIS projection."""
import asyncio
import json
import os
import time
from itertools import permutations
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

ROOT=Path(__file__).resolve().parents[2]
# Backend-only private configuration; explicit process variables take precedence.
private_config=ROOT/'.env.cross-camera'
if private_config.exists():
    for line in private_config.read_text(encoding='utf-8-sig').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key,value=line.split('=',1)
            if key.strip().startswith('CROSS_CAMERA_'):
                os.environ.setdefault(key.strip(),value.strip().strip('"').strip("'"))
CAMERAS=[('CAM01','教学楼一主入口','HBUE-B120'),('CAM02','教学楼二主入口','HBUE-B119'),('CAM03','实验楼一主入口','HBUE-B041'),('CAM04','行政楼入口','HBUE-B001'),('CAM05','枫苑宿舍主入口','HBUE-B124'),('CAM06','三清园入口','HBUE-B009'),('CAM07','室内体育馆入口','HBUE-B003'),('CAM08','大学生活动中心入口','HBUE-B002')]

def inside(point,ring):
    x,y=point; result=False
    for a,b in zip(ring,ring[1:]):
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:result=not result
    return result

def demo_cameras():
    data=json.loads((ROOT/'spatial_data/hbue/hbue_buildings.geojson').read_text(encoding='utf-8'))
    features={x['properties']['building_id']:x for x in data['features']}
    boundary=json.loads((ROOT/'spatial_data/hbue/hbue_campus_boundary.geojson').read_text(encoding='utf-8'))['features'][0]['geometry']['coordinates'][0]
    result=[]
    for camera,name,bid in CAMERAS:
        feature=features[bid];ring=feature['geometry']['coordinates'][0];center=[sum(p[i] for p in ring[:-1])/len(ring[:-1]) for i in (0,1)]
        # Near polygon edge, not a surveyed entrance or real camera deployment.
        lon,lat=[ring[0][i]*.9+center[i]*.1 for i in (0,1)]
        if not inside((lon,lat),boundary):raise ValueError('示范摄像头锚点不在校园内')
        result.append(dict(camera_id=camera,camera_name=name,campus_id='HBUE',building_id=bid,building_name=feature['properties']['name'],floor_id=None,area_id=f'{bid}-DEMO-ENTRY',longitude=lon,latitude=lat,location_type='DEMO_PLACEMENT',location_notice='示范布点，并非学校真实摄像头或已测绘入口位置'))
    return result

def demo_paths():
    cameras=demo_cameras();lookup={x['camera_id']:x for x in cameras}
    routes=[('宿舍区活动',['CAM05','CAM06','CAM01']),('教学区活动',['CAM01','CAM02','CAM03']),('综合活动',['CAM04','CAM08']),('体育活动',['CAM05','CAM07']),('餐饮区活动',['CAM02','CAM06','CAM05'])]
    boundary=json.loads((ROOT/'spatial_data/hbue/hbue_campus_boundary.geojson').read_text(encoding='utf-8'))['features'][0]['geometry']['coordinates'][0]
    valid=[]
    for kind,route in routes:
        if all(all(inside((lookup[a]['longitude']+(lookup[b]['longitude']-lookup[a]['longitude'])*t/100,lookup[a]['latitude']+(lookup[b]['latitude']-lookup[a]['latitude'])*t/100),boundary) for t in range(101)) for a,b in zip(route,route[1:])):valid.append((kind,route))
    if not valid:raise ValueError('未找到校园内有效示范路线')
    # Different camera sequences per activity, rather than five coincident copies.
    # Nodes remain the original camera anchors; these are NOT continuous GPS tracks.
    variants={}
    for kind,base in valid:
        candidates=[base,list(reversed(base))]
        candidates.extend(list(p) for length in (3,2,4) for p in permutations(base,length))
        candidates.extend(list(p) for p in permutations(lookup,3) if base[0] in p and base[-1] in p)
        selected=[]
        for candidate in candidates:
            if candidate in selected:continue
            if all(all(inside((lookup[a]['longitude']+(lookup[b]['longitude']-lookup[a]['longitude'])*t/100,lookup[a]['latitude']+(lookup[b]['latitude']-lookup[a]['latitude'])*t/100),boundary) for t in range(101)) for a,b in zip(candidate,candidate[1:])):
                selected.append(candidate)
            if len(selected)==5:break
        variants[kind]=selected
    paths=[];origin=datetime(2026,9,16,7,tzinfo=timezone(timedelta(hours=8)))
    for index in range(25):
        kind,_=valid[index%len(valid)];route=variants[kind][(index//len(valid))%len(variants[kind])];start=origin+timedelta(minutes=index*17);gid=f'G{index+1:03d}'
        nodes=[dict(lookup[camera],global_id=gid,local_id=f'{camera}-L{index+1:03d}',timestamp=(start+timedelta(minutes=n*8)).isoformat(),end_timestamp=(start+timedelta(minutes=n*8,seconds=30)).isoformat()) for n,camera in enumerate(route)]
        paths.append(dict(global_id=gid,activity_type=kind,start_time=nodes[0]['timestamp'],end_time=nodes[-1]['end_timestamp'],score=round(.8+(index%10)*.018,3),confidence=round(.82+(index%8)*.02,3),nodes=nodes,raw_pixel_tracks=[],raw_match={'data_notice':'示范匹配结果，不代表真实算法输出'}))
    return dict(source='DEMO',data_notice='示范摄像头布点与示范跨镜活动路径',cameras=cameras,paths=paths,warnings=[],disclaimer='连线仅表示摄像头区域之间的活动顺序，不是人员真实连续步行GPS路径。')

class SourceRequest(BaseModel):
    source: str='DEMO'
    task_id: str|None=None
    video_start_time: datetime|None=None
    allow_demo_fallback: bool=True

class UpstreamUnavailable(Exception):pass

class CrossCameraClient:
    def __init__(self):self.token=None;self.expires=0;self.lock=asyncio.Lock()
    async def login(self,client):
        async with self.lock:
            if self.token and time.monotonic()<self.expires:return
            username=os.getenv('CROSS_CAMERA_USERNAME');password=os.getenv('CROSS_CAMERA_PASSWORD')
            if not username or not password:raise UpstreamUnavailable('跨镜服务登录凭证未配置')
            response=await client.post('/api/v1/auth/login',json={'username':username,'password':password})
            if response.status_code>=400:raise UpstreamUnavailable('跨镜服务登录失败')
            payload=response.json();payload=payload.get('data',payload);self.token=payload.get('access_token') or payload.get('token')
            if not self.token:raise UpstreamUnavailable('跨镜登录响应未包含可识别Token')
            duration=float(payload['expires_at'])-time.time() if payload.get('expires_at') is not None else float(payload.get('expires_in',300))
            if duration<=0:
                self.token=None
                raise UpstreamUnavailable('跨镜登录返回的Token已过期')
            self.expires=time.monotonic()+max(1,min(duration-10,3600))
    async def get(self,client,path,params=None):
        await self.login(client)
        for attempt in range(2):
            response=await client.get(path,params=params,headers={'Authorization':f'Bearer {self.token}'})
            if response.status_code==401 and attempt==0:self.token=None;await self.login(client);continue
            if response.status_code==404:raise UpstreamUnavailable('跨镜任务或匿名编号不存在')
            if response.status_code>=400:raise UpstreamUnavailable('跨镜服务请求失败')
            return response.json()
        raise UpstreamUnavailable('跨镜Token失效，重新登录后仍无法访问')

client_cache=CrossCameraClient()

async def live_carbon_association(task_id):
    import re
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',task_id):
        raise ValueError('真实任务编号无效')
    async with httpx.AsyncClient(base_url=os.getenv('CROSS_CAMERA_BASE_URL','http://10.120.203.134:8100'),timeout=15,trust_env=False) as client:
        report=await client_cache.get(client,f'/api/v1/tasks/{task_id}/carbon-association')
        occupancy=await client_cache.get(client,f'/api/v1/tasks/{task_id}/carbon-association/occupancy')
    return {'task_id':task_id,'association':report,'occupancy':occupancy}

async def live_health():
    """Verify HTTP service and authenticated identity without exposing secrets."""
    if private_config.exists():
        for line in private_config.read_text(encoding='utf-8-sig').splitlines():
            if line.startswith('CROSS_CAMERA_') and '=' in line:
                key,value=line.split('=',1)
                os.environ.setdefault(key.strip(),value.strip().strip('"').strip("'"))
    credentials=bool(os.getenv('CROSS_CAMERA_USERNAME') and os.getenv('CROSS_CAMERA_PASSWORD'))
    result=dict(upstream_reachable=False,http_responding=False,credentials_configured=credentials,
                login_success=False,token_valid=False,status='DEMO',message='实时接口未配置凭证')
    result['video_start_time']=os.getenv('CROSS_CAMERA_VIDEO_START_TIME')
    result['time_notice']='演示时间假设，并非已核实的录像时间' if os.getenv('CROSS_CAMERA_DEMO_CONTEXT')=='1' else None
    try:
        async with httpx.AsyncClient(base_url=os.getenv('CROSS_CAMERA_BASE_URL','http://10.120.203.134:8100'),timeout=5,trust_env=False) as client:
            response=await client.get('/openapi.json')
            result['http_responding']=True
            result['upstream_reachable']=response.status_code==200
            if not result['upstream_reachable']:raise UpstreamUnavailable('实时服务文档检查失败')
            if credentials:
                await client_cache.get(client,'/api/v1/auth/me')
                result.update(login_success=True,token_valid=True,status='LIVE_READY',message='实时接口已连接，认证有效')
    except (httpx.HTTPError,UpstreamUnavailable,ValueError,TypeError):
        result.update(status='LIVE_ERROR',message='实时接口登录失败或服务不可达')
    return result

async def live_tasks():
    async with httpx.AsyncClient(base_url=os.getenv('CROSS_CAMERA_BASE_URL','http://10.120.203.134:8100'),timeout=5,trust_env=False) as client:
        rows=await client_cache.get(client,'/api/v1/tasks',{'limit':100})
        if not isinstance(rows,list):raise UpstreamUnavailable('任务列表格式与上游文档不一致')
        return [{'task_id':x['task_id'],'status':x.get('status'),'created_at':x.get('created_at')} for x in rows]

async def load_source(db,request:SourceRequest):
    if request.source=='DEMO':return demo_paths()
    if request.source!='LIVE':raise ValueError('数据源必须为DEMO或LIVE')
    try:
        if request.video_start_time is None and os.getenv('CROSS_CAMERA_VIDEO_START_TIME'):
            request=request.model_copy(update={'video_start_time':datetime.fromisoformat(os.environ['CROSS_CAMERA_VIDEO_START_TIME'])})
        if not request.task_id:
            request=request.model_copy(update={'task_id':os.getenv('CROSS_CAMERA_TASK_ID')})
        if not request.task_id:
            tasks=await live_tasks()
            completed=[x for x in tasks if x['status']=='finished']
            if not completed:raise UpstreamUnavailable('尚无已完成的真实跨镜任务，请配置已有任务编号')
            request=request.model_copy(update={'task_id':completed[0]['task_id']})
        async with httpx.AsyncClient(base_url=os.getenv('CROSS_CAMERA_BASE_URL','http://10.120.203.134:8100'),timeout=5,trust_env=False) as client:
            raw=await client_cache.get(client,f'/api/v1/tasks/{request.task_id}/result')
            return await normalize_live(db,client,raw,request)
    except (httpx.HTTPError,UpstreamUnavailable,ValueError,KeyError,TypeError) as exc:
        message=str(exc) if isinstance(exc,UpstreamUnavailable) else '跨镜服务不可达或响应格式尚未完成联调'
        if not request.allow_demo_fallback:raise UpstreamUnavailable(message) from exc
        result=demo_paths();result['requested_source']='LIVE';result['warnings']=[message+'；当前已切换为明确标识的示范数据'];return result

async def normalize_live(db,client,raw,request):
    from app.schemas.cross_camera import CrossCameraAdaptRequest
    from app.services.cross_camera_adapter_service import adapt,list_mappings
    payload=raw.get('data',raw);matches=payload.get('matches',payload.get('results'))
    if not isinstance(matches,list):raise ValueError('未识别上游匹配列表')
    if request.video_start_time is None or request.video_start_time.tzinfo is None:raise UpstreamUnavailable('实时接入需要带时区的视频开始时间')
    normalized=[];raw_details={};schema_warnings=[]
    for match in matches:
        gid=match['global_id'];details=await client_cache.get(client,f'/api/v1/tasks/{request.task_id}/trajectories',{'global_id':gid});raw_details[gid]=details
        if 'cam1_local_id' in match:
            converted_match=convert_current_match(match,details)
            if converted_match is None:
                schema_warnings.append(f'{gid}：上游匹配评分缺失，保留原始结果但不生成GIS路径')
                continue
            normalized.append(converted_match)
        else:
            tracks=details.get('data',details);tracks=tracks.get('tracks',tracks.get('trajectories')) if isinstance(tracks,dict) else tracks
            normalized.append({**match,'tracks':tracks,'upstream_raw':match})
    converted=adapt(db,CrossCameraAdaptRequest.model_validate(dict(campus_id='HBUE',video_start_time=request.video_start_time,matches=normalized)))
    mapping_rows=list_mappings(db,'HBUE');cameras=[dict(x,building_id=x['building_code'],camera_name=x['metadata_json'].get('camera_name',x['camera_id']),location_type=x['anchor_source']) for x in mapping_rows]
    paths=[]
    for gid in dict.fromkeys(x['global_id'] for x in converted['nodes']):
        nodes=[x for x in converted['nodes'] if x['global_id']==gid];nodes.sort(key=lambda x:x['timestamp'])
        confidences=[point['confidence'] for track in converted['raw_pixel_tracks'] if track['global_id']==gid for point in track['points'] if point.get('confidence') is not None]
        paths.append(dict(global_id=gid,activity_type='未分类活动',start_time=nodes[0]['timestamp'].isoformat(),end_time=nodes[-1]['end_timestamp'].isoformat(),segments=[s for s in converted['segments'] if s['global_id']==gid],score=min(x['comprehensive_score'] for x in nodes),confidence=min(confidences) if confidences else None,nodes=[{**x,'timestamp':x['timestamp'].isoformat(),'end_timestamp':x['end_timestamp'].isoformat()} for x in nodes],raw_pixel_tracks=[x for x in converted['raw_pixel_tracks'] if x['global_id']==gid],raw_match=[x for x in matches if x['global_id']==gid],upstream_trajectory=raw_details[gid]))
    notice='真实跨镜匹配结果；空间位置以配置锚点为准'
    if any(x['anchor_source']=='DEMO_PLACEMENT' for x in mapping_rows):notice+='；使用示范校园布点，不代表视频实际拍摄地点'
    if os.getenv('CROSS_CAMERA_DEMO_CONTEXT')=='1':notice+='；日期采用演示时间假设，不代表已核实录像时间'
    return dict(source='LIVE',task_id=request.task_id,global_id_count=len({m['global_id'] for m in matches}),unmapped_camera_ids=converted['unmapped_camera_ids'],raw_result=raw,raw_trajectories=raw_details,data_notice=notice,cameras=cameras,paths=paths,warnings=schema_warnings+[f'{x}：摄像头空间位置未配置' for x in converted['unmapped_camera_ids']],disclaimer=converted['disclaimer'])

def convert_current_match(match,details):
    """Schema confirmed from authenticated 2026-09-16 result/trajectories."""
    if any(match.get(k) is None for k in ('similarity','temporal_consistency','combined_score')):return None
    identities=details.get('identities',[])
    tracks=[]
    for identity in identities:
        if identity['global_id']!=match['global_id']:continue
        for track in identity['tracks']:
            points=[]
            for point in track['points']:
                center=point.get('center')
                if center is None:raise UpstreamUnavailable('真实像素轨迹缺少中心点，无法解析')
                points.append(dict(relative_time_s=point['time_seconds'],x=center[0],y=center[1],center={'x':center[0],'y':center[1]},bbox=point.get('bbox'),confidence=point.get('conf'),direction=point.get('direction'),speed=point.get('speed_px_s')))
            tracks.append(dict(camera_id=track['camera_id'],local_id=str(track['local_id']),start_relative_time_s=track['start_seconds'],end_relative_time_s=track['end_seconds'],points=points))
    def score(key):
        value=float(match[key])
        # Cosine similarity can exceed one by floating-point roundoff. Raw is retained.
        if not -1e-6 <= value <= 1+1e-6:
            raise UpstreamUnavailable('上游匹配评分超出有效范围')
        return max(0.0,min(1.0,value))
    return dict(global_id=match['global_id'],camera_a_id='cam1',camera_b_id='cam2',local_id_a=str(match['cam1_local_id']),local_id_b=str(match['cam2_local_id']),match_similarity=score('similarity'),time_consistency=score('temporal_consistency'),comprehensive_score=score('combined_score'),tracks=tracks,upstream_raw=match)
