"""Read-only upstream adapters. No device controls, binding guesses or fake units."""
import asyncio
import hashlib
import json
import os
import time
from datetime import datetime,timezone,timedelta
from pathlib import Path
import httpx
from sqlalchemy import select
from app.models.external_data import ExternalDataRecord
from app.models import Building, Site
from app.database import SessionLocal

ROOT=Path(__file__).resolve().parents[2]
def config():
    values={}
    for name in ('.env','.env.external-data'):
        path=ROOT/name
        if path.exists():
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                    key,value=line.split('=',1);values[key.strip()]=value.strip().strip('"').strip("'")
    return {**values,**os.environ}

class ExternalError(Exception):pass

def _business_error(data):
    """Return a safe upstream business error without exposing credentials/tokens."""
    if not isinstance(data,dict):return None
    code=data.get('code')
    if code in (None,0,200,1000,'0','200','1000'):return None
    message=data.get('message') or data.get('msg') or '上游业务接口返回失败'
    return f'物联网云平台鉴权失败（上游代码 {code}）：{message}'

class IotCloudClient:
    def __init__(self):self.token=None;self.expiry=0;self.lock=asyncio.Lock();self.credentials=None
    async def login(self,client,cfg):
        async with self.lock:
            if str(cfg.get('IOT_CLOUD_USE_IOTSIN_CREDENTIALS','false')).lower()=='true':
                credentials=(cfg.get('IOTSIN_LOGIN_NAME'),cfg.get('IOTSIN_PASSWORD'))
            else:
                credentials=(cfg.get('IOT_CLOUD_LOGIN_NAME'),cfg.get('IOT_CLOUD_PASSWORD'))
            if not all(credentials):raise ExternalError('物联网云平台未配置登录凭证')
            if self.credentials==credentials and self.token and time.monotonic()<self.expiry:return
            r=await client.get('/api/getToken',params={'loginName':credentials[0],'password':credentials[1]})
            if r.status_code>=400:raise ExternalError('物联网云平台登录失败')
            envelope=r.json()
            error=_business_error(envelope)
            if error:raise ExternalError(error)
            data=envelope.get('data',envelope) if isinstance(envelope,dict) else envelope
            if not isinstance(data,dict) or not data.get('token'):raise ExternalError('登录响应未包含Token，需核对真实响应')
            self.token=data['token'];self.credentials=credentials
            # Unknown expiration format => short conservative cache, never assume permanent.
            duration=60
            try:
                expiration=data.get('expiration')
                if isinstance(expiration,(float,int)):
                    duration=(expiration/1000 if expiration>1e12 else expiration)-time.time()
                elif expiration:duration=datetime.fromisoformat(str(expiration).replace('Z','+00:00')).timestamp()-time.time()
            except (ValueError,TypeError):pass
            self.expiry=time.monotonic()+max(1,min(duration-5,300))
    async def get(self,client,path,cfg,params=None):
        allowed={'/api/device/getGroupList','/api/device/getDeviceList','/api/data/getRealTimeData','/api/data/getRealTimeDataByDeviceAddr','/api/data/historyList','/api/data/alarmRecordList'}
        if path not in allowed:raise ExternalError('只允许读取设备和数据接口')
        await self.login(client,cfg)
        for attempt in range(2):
            r=await client.get(path,params=params,headers={'authorization':self.token})
            if r.status_code in (401,403) and attempt==0:
                self.token=None;await self.login(client,cfg);continue
            if r.status_code>=400:raise ExternalError('物联网数据请求失败，请检查权限和接口参数')
            payload=r.json()
            if isinstance(payload,dict) and payload.get('code') in (401,403,'401','403'):
                if attempt==0:self.token=None;await self.login(client,cfg);continue
                raise ExternalError('物联网鉴权失败')
            return payload
        raise ExternalError('物联网Token重新获取后仍无效')

cloud=IotCloudClient()

class IotsinClient:
    """Read-only adapter for iot.iotsin.com. The authenticated cookie stays in backend memory."""
    def __init__(self):
        self.cookies=httpx.Cookies();self.authenticated=False;self.lock=asyncio.Lock()
    async def captcha(self,cfg):
        async with httpx.AsyncClient(base_url=cfg.get('IOTSIN_BASE_URL','http://iot.iotsin.com'),timeout=15,trust_env=False,cookies=self.cookies) as client:
            r=await client.get('/sysUser/verifyCode',params={'time':int(time.time()*1000)});r.raise_for_status();self.cookies.update(client.cookies);return r.content,r.headers.get('content-type','image/jpeg')
    async def login(self,cfg,code):
        username=cfg.get('IOTSIN_LOGIN_NAME');password=cfg.get('IOTSIN_PASSWORD')
        if not username or not password:raise ExternalError('塞恩云平台未配置登录凭证')
        if not code:raise ExternalError('请输入塞恩云平台图形验证码')
        async with self.lock:
            async with httpx.AsyncClient(base_url=cfg.get('IOTSIN_BASE_URL','http://iot.iotsin.com'),timeout=15,trust_env=False,cookies=self.cookies) as client:
                r=await client.post('/sysUser/userLogin',data={'loginName':username,'loginPassword':password,'code':code});r.raise_for_status();payload=r.json();self.cookies.update(client.cookies)
            if not isinstance(payload,dict) or payload.get('code')!=1000:
                self.authenticated=False;raise ExternalError(f"塞恩云平台登录失败：{payload.get('message','未知错误') if isinstance(payload,dict) else '响应格式异常'}")
            self.authenticated=True;return {'connected':True,'session_valid':True,'message':payload.get('message')}
    async def get(self,path,params=None):
        allowed={'/device/userDevices','/group/groupListPage','/sysData/getRealTimeData','/device/deviceWithEnabledFactorsByDeviceAddr','/sysData/multicolumnHistory','/sysData/getAlarmRecords'}
        if path not in allowed:raise ExternalError('塞恩云平台仅允许只读数据接口')
        if not self.authenticated:raise ExternalError('塞恩云平台尚未完成验证码登录')
        cfg=config()
        async with httpx.AsyncClient(base_url=cfg.get('IOTSIN_BASE_URL','http://iot.iotsin.com'),timeout=20,trust_env=False,cookies=self.cookies) as client:
            r=await client.get(path,params=params)
            if r.status_code in (401,403):
                self.authenticated=False
                raise ExternalError('塞恩云平台会话已失效，需要重新鉴权')
            r.raise_for_status();payload=r.json();self.cookies.update(client.cookies)
        if isinstance(payload,dict) and payload.get('code')==2000:
            self.authenticated=False;raise ExternalError('塞恩云平台会话已失效，请重新输入验证码登录')
        if not isinstance(payload,dict) or payload.get('code')!=1000:raise ExternalError(f"塞恩云平台读取失败：{payload.get('message','响应格式异常') if isinstance(payload,dict) else '响应格式异常'}")
        return payload

iotsin=IotsinClient()

def metric(source,device,code,name,value,unit,timestamp,raw):
    status='READY'
    if value is None:status='MISSING_VALUE'
    elif timestamp is None:status='MISSING_TIMESTAMP'
    elif unit is None:status='UNIT_NOT_PROVIDED'
    if timestamp is not None:
        try:
            if isinstance(timestamp,(int,float)):
                timestamp=datetime.fromtimestamp(timestamp/1000 if timestamp>1e12 else timestamp,timezone.utc).isoformat()
            else:
                parsed=datetime.fromisoformat(str(timestamp).replace('Z','+00:00'))
                if parsed.tzinfo is None:
                    status='TIMESTAMP_TIMEZONE_UNVERIFIED'
                else:timestamp=parsed.astimezone(timezone.utc).isoformat()
        except (ValueError,TypeError,OverflowError):status='INVALID_TIMESTAMP'
    return dict(source_type=source,source_id=source,campus_id=None,building_id=None,device_id=str(device),device_name=raw.get('deviceName'),metric_code=str(code),metric_name=name,value=value,unit=unit,timestamp=timestamp,quality_status=status,raw_payload=raw)

def weather_metrics(raw):
    if raw.get('code')!=0:raise ExternalError('气象站业务接口返回失败')
    data=raw['data'];properties=data.get('identifier2property')
    if not isinstance(properties,dict):raise ExternalError('气象站属性结构发生变化')
    rows=[]
    for code,p in properties.items():
        row=metric('WEATHER_STATION',data['dn'],code,p['name'],p.get('value'),p.get('unit'),p.get('time'),p)
        row['device_name']='气象站';rows.append(row)
    return rows

def list_payload(raw):
    if isinstance(raw,list):return raw
    if isinstance(raw,dict) and isinstance(raw.get('data'),list):return raw['data']
    raise ExternalError('尚未确认物联网列表响应结构，原始返回已保留，不猜测解析')

def cloud_metrics(raw):
    rows=[]
    def visit(obj,device=None,node=None,stamp=None):
        if isinstance(obj,list):
            for x in obj:visit(x,device,node,stamp)
        elif isinstance(obj,dict):
            if 'deviceAddr' in obj:device=obj
            node=obj.get('nodeId',node);stamp=obj.get('timeStamp',stamp)
            if device and 'registerId' in obj and 'value' in obj:
                context={**obj,'deviceName':device.get('deviceName'),'nodeId':node,'deviceStatus':device.get('deviceStatus'),'lat':device.get('lat'),'lng':device.get('lng')}
                rows.append(metric('IOT_CLOUD',device['deviceAddr'],f'{node}:{obj["registerId"]}',obj.get('registerName'),obj['value'],obj.get('unit'),stamp,context))
            for v in obj.values():
                if isinstance(v,(dict,list)):visit(v,device,node,stamp)
    visit(raw)
    return rows

def iotsin_metrics(raw):
    payload=raw.get('data',raw) if isinstance(raw,dict) else raw;rows=[]
    if not isinstance(payload,list):raise ExternalError('塞恩云平台实时数据结构发生变化')
    for device in payload:
        stamp=device.get('timeStamp')
        for node in device.get('dataItem') or []:
            for register in node.get('registerItem') or []:
                context={**register,'deviceAddr':device.get('deviceAddr'),'deviceName':device.get('deviceName'),'deviceStatus':device.get('deviceStatus'),'lat':device.get('lat'),'lng':device.get('lng'),'nodeId':node.get('nodeId'),'timeStamp':stamp}
                rows.append(metric('IOTSIN_SENSOR',device.get('deviceAddr'),f"{node.get('nodeId')}:{register.get('registerId')}",register.get('registerName'),register.get('value'),register.get('unit'),stamp,context))
    return rows

def save(db,source,kind,key,payload):
    row=db.scalar(select(ExternalDataRecord).where(ExternalDataRecord.source_type==source,ExternalDataRecord.record_kind==kind,ExternalDataRecord.record_key==key))
    if row is None:row=ExternalDataRecord(source_type=source,record_kind=kind,record_key=key,payload=payload);db.add(row)
    else:row.payload=payload;row.collected_at=datetime.utcnow()
    db.flush()

def store_metrics(db,source,rows):
    for row in rows:
        key=hashlib.sha256(json.dumps([row['device_id'],row['metric_code'],row['timestamp'],row['value']],sort_keys=True,default=str).encode()).hexdigest()
        save(db,source,'METRIC',key,row)

def bind_iotsin_device(db,device_addr,building_code,floor_number):
    """Persist an explicitly confirmed device location; never infer a room or coordinates."""
    device=db.scalar(select(ExternalDataRecord).where(ExternalDataRecord.source_type=='IOTSIN_SENSOR',ExternalDataRecord.record_kind=='DEVICE',ExternalDataRecord.record_key==device_addr))
    if device is None:raise ExternalError('设备尚未由上游发现，不能绑定建筑')
    site=db.scalar(select(Site).where(Site.code=='HBUE'))
    if site is None:raise ExternalError('湖北经济学院园区不存在')
    building=db.scalar(select(Building).where(Building.site_id==site.id,Building.code==building_code))
    if building is None:raise ExternalError('湖北经济学院建筑编码不存在')
    if floor_number<1 or (building.floor_count and floor_number>building.floor_count):raise ExternalError('楼层超出该建筑记录范围')
    binding=dict(campus_id='HBUE',building_id=building.code,floor_id=f'{building.code}-F{floor_number:02d}',area_id=None,
                 mapping_status='MANUAL_VERIFIED',mapping_source='user_confirmation',mapped_at=datetime.now(timezone.utc).isoformat())
    device.payload={**device.payload,**binding,'enabled':True}
    metrics=db.scalars(select(ExternalDataRecord).where(ExternalDataRecord.source_type=='IOTSIN_SENSOR',ExternalDataRecord.record_kind=='METRIC')).all()
    for row in metrics:
        if row.payload.get('device_id')==device_addr:row.payload={**row.payload,**binding}
    state=db.scalar(select(ExternalDataRecord).where(ExternalDataRecord.source_type=='IOTSIN_SENSOR',ExternalDataRecord.record_kind=='STATE',ExternalDataRecord.record_key=='latest'))
    if state is not None:
        device_rows=db.scalars(select(ExternalDataRecord).where(ExternalDataRecord.source_type=='IOTSIN_SENSOR',ExternalDataRecord.record_kind=='DEVICE')).all()
        state.payload={**state.payload,'unmapped_count':sum(not row.payload.get('building_id') for row in device_rows)}
    db.commit()
    return dict(device_id=device_addr,building_name=building.name,**binding)

async def collect_weather(db):
    cfg=config()
    async with httpx.AsyncClient(timeout=10,trust_env=False) as client:
        r=await client.post(cfg.get('WEATHER_STATION_URL','http://119.96.23.24:8850/admin-api/eiot/device/getDeviceWithProperty'),json={'dn':cfg.get('WEATHER_STATION_DN','IFSGCOA0003')})
        r.raise_for_status();raw=r.json()
    rows=weather_metrics(raw);store_metrics(db,'WEATHER_STATION',rows)
    state=dict(connected=True,online=raw['data'].get('online'),property_count=len(rows),valid_value_count=sum(x['quality_status']=='READY' for x in rows),latest_observation_time=next((x['timestamp'] for x in rows if x['timestamp'] is not None),None),raw_payload=raw)
    save(db,'WEATHER_STATION','STATE','latest',state);db.commit();return state

async def collect_cloud(db):
    cfg=config()
    async with httpx.AsyncClient(base_url=cfg.get('IOT_CLOUD_BASE_URL','http://iot.lwbsq.com'),timeout=10,trust_env=False) as client:
        groups=await cloud.get(client,'/api/device/getGroupList',cfg)
        devices=await cloud.get(client,'/api/device/getDeviceList',cfg)
        save(db,'IOT_CLOUD','RAW','groups',groups);save(db,'IOT_CLOUD','RAW','devices',devices);db.commit()
        rows=list_payload(devices);group_rows=list_payload(groups)
        confirmed={row.record_key:row.payload for row in db.scalars(select(ExternalDataRecord).where(ExternalDataRecord.source_type=='IOTSIN_SENSOR',ExternalDataRecord.record_kind=='DEVICE')).all() if row.payload.get('mapping_status')=='MANUAL_VERIFIED'}
        for d in rows:
            if 'deviceAddr' not in d:raise ExternalError('真实设备缺少deviceAddr')
            key=str(d['deviceAddr'])
            existing=db.scalar(select(ExternalDataRecord).where(ExternalDataRecord.source_type=='IOT_CLOUD',ExternalDataRecord.record_kind=='DEVICE',ExternalDataRecord.record_key==key))
            binding=(existing.payload if existing and existing.payload.get('building_id') else confirmed.get(key)) or {}
            save(db,'IOT_CLOUD','DEVICE',key,dict(upstream_device_id=key,upstream_device_name=d.get('deviceName'),source_type='IOT_CLOUD',campus_id=binding.get('campus_id'),building_id=binding.get('building_id'),floor_id=binding.get('floor_id'),area_id=binding.get('area_id'),energy_type=None,metric_mapping={},enabled=bool(binding.get('building_id')),mapping_status=binding.get('mapping_status','UNMAPPED'),mapping_source=binding.get('mapping_source'),mapped_at=binding.get('mapped_at'),raw_payload=d))
        db.commit()
        raw=await cloud.get(client,'/api/data/getRealTimeData',cfg)
        save(db,'IOT_CLOUD','RAW','realtime',raw);metrics=cloud_metrics(raw)
        mappings={row.record_key:row.payload for row in db.scalars(select(ExternalDataRecord).where(ExternalDataRecord.source_type=='IOT_CLOUD',ExternalDataRecord.record_kind=='DEVICE')).all()}
        for item in metrics:
            binding=mappings.get(item['device_id'],{})
            if binding.get('building_id'):
                item.update({field:binding.get(field) for field in ('campus_id','building_id','floor_id','area_id','mapping_status','mapping_source','mapped_at')})
        store_metrics(db,'IOT_CLOUD',metrics)
        live=list_payload(raw)
        state=dict(connected=True,token_valid=True,group_count=len(group_rows),device_count=len(rows),latest_metric_count=len(metrics),online_count=sum(x.get('deviceStatus')=='normal' for x in live),offline_count=sum(x.get('deviceStatus')!='normal' for x in live),unmapped_count=sum(not mappings.get(str(x.get('deviceAddr')),{}).get('building_id') for x in rows),latest_observation_time=max((x.get('timestamp') for x in metrics if x.get('timestamp')),default=None),collection_mode='AUTOMATIC_TOKEN_API_POLL')
        save(db,'IOT_CLOUD','STATE','latest',state);db.commit();return state

async def collect_iotsin(db):
    devices=await iotsin.get('/device/userDevices');groups=await iotsin.get('/group/groupListPage',{'parentId':''});realtime=await iotsin.get('/sysData/getRealTimeData')
    device_rows=devices.get('data') or []
    save(db,'IOTSIN_SENSOR','RAW','groups',groups);save(db,'IOTSIN_SENSOR','RAW','devices',devices);save(db,'IOTSIN_SENSOR','RAW','realtime',realtime)
    for device in device_rows:
        key=str(device.get('deviceAddr'))
        existing=db.scalar(select(ExternalDataRecord).where(ExternalDataRecord.source_type=='IOTSIN_SENSOR',ExternalDataRecord.record_kind=='DEVICE',ExternalDataRecord.record_key==key))
        previous=existing.payload if existing else {}
        binding={field:previous.get(field) for field in ('campus_id','building_id','floor_id','area_id','mapping_status','mapping_source','mapped_at')}
        enriched=dict(device)
        try:
            factor_response=await iotsin.get('/device/deviceWithEnabledFactorsByDeviceAddr',{'deviceAddr':key})
            factor_data=factor_response.get('data') or {}
            enriched['factors']=factor_data.get('factors') or [] if isinstance(factor_data,dict) else []
            save(db,'IOTSIN_SENSOR','RAW',f'factors:{key}',factor_response)
        except ExternalError as exc:
            enriched['factors']=[];enriched['factor_read_error']=str(exc)
        save(db,'IOTSIN_SENSOR','DEVICE',key,dict(upstream_device_id=key,upstream_device_name=device.get('deviceName'),source_type='IOTSIN_SENSOR',campus_id=binding['campus_id'],building_id=binding['building_id'],floor_id=binding['floor_id'],area_id=binding['area_id'],energy_type=None,metric_mapping={},enabled=bool(binding['building_id']),mapping_status=binding['mapping_status'] or 'UNMAPPED',mapping_source=binding['mapping_source'],mapped_at=binding['mapped_at'],raw_payload=enriched))
    metrics=iotsin_metrics(realtime)
    mappings={row.record_key:row.payload for row in db.scalars(select(ExternalDataRecord).where(ExternalDataRecord.source_type=='IOTSIN_SENSOR',ExternalDataRecord.record_kind=='DEVICE')).all()}
    for item in metrics:
        binding=mappings.get(item['device_id'],{})
        if binding.get('building_id'):
            item.update({field:binding.get(field) for field in ('campus_id','building_id','floor_id','area_id','mapping_status','mapping_source','mapped_at')})
    store_metrics(db,'IOTSIN_SENSOR',metrics)
    live=realtime.get('data') or [];state=dict(connected=True,session_valid=True,device_count=len(device_rows),online_count=sum(x.get('deviceStatus')=='normal' for x in live),offline_count=sum(x.get('deviceStatus')!='normal' for x in live),unmapped_count=sum(not mappings.get(str(x.get('deviceAddr')),{}).get('building_id') for x in device_rows),latest_metric_count=len(metrics),latest_observation_time=max((x.get('timestamp') for x in metrics if x.get('timestamp')),default=None))
    save(db,'IOTSIN_SENSOR','STATE','latest',state);db.commit();return state

async def collect_iotsin_realtime(db):
    """Poll the read-only realtime API without repeating device/factor discovery."""
    realtime=await iotsin.get('/sysData/getRealTimeData')
    live=realtime.get('data') or []
    if not isinstance(live,list):raise ExternalError('塞恩云平台实时设备列表结构异常')
    save(db,'IOTSIN_SENSOR','RAW','realtime',realtime)
    devices=db.scalars(select(ExternalDataRecord).where(ExternalDataRecord.source_type=='IOTSIN_SENSOR',ExternalDataRecord.record_kind=='DEVICE')).all()
    mappings={row.record_key:row.payload for row in devices}
    metrics=iotsin_metrics(realtime)
    for item in metrics:
        binding=mappings.get(item['device_id'],{})
        if binding.get('building_id'):
            item.update({field:binding.get(field) for field in ('campus_id','building_id','floor_id','area_id','mapping_status','mapping_source','mapped_at')})
    store_metrics(db,'IOTSIN_SENSOR',metrics)
    state=dict(connected=True,session_valid=True,device_count=len(devices),online_count=sum(x.get('deviceStatus')=='normal' for x in live),offline_count=sum(x.get('deviceStatus')!='normal' for x in live),unmapped_count=sum(not x.payload.get('building_id') for x in devices),latest_metric_count=len(metrics),latest_observation_time=max((x.get('timestamp') for x in metrics if x.get('timestamp')),default=None),collection_mode='AUTOMATIC_API_POLL',error=None)
    save(db,'IOTSIN_SENSOR','STATE','latest',state);db.commit();return state

class IotsinRealtimeCollector:
    def __init__(self):self.task=None;self.running=False;self.wake=asyncio.Event();self.lock=asyncio.Lock()
    async def start(self):
        if self.running:return
        self.running=True;self.task=asyncio.create_task(self._loop(),name='iotsin-realtime-poll')
    async def stop(self):
        self.running=False
        if self.task:self.task.cancel();await asyncio.gather(self.task,return_exceptions=True);self.task=None
    def trigger(self):self.wake.set()
    async def _loop(self):
        while self.running:
            if iotsin.authenticated:
                async with self.lock:
                    with SessionLocal() as db:
                        try:await collect_iotsin_realtime(db)
                        except Exception as exc:
                            db.rollback()
                            message=str(exc) if isinstance(exc,ExternalError) else '实时接口请求失败'
                            save(db,'IOTSIN_SENSOR','STATE','latest',dict(connected=False,session_valid=iotsin.authenticated,collection_mode='AUTOMATIC_API_POLL',error=message))
                            db.commit()
            interval=int(config().get('IOTSIN_POLL_SECONDS','30'))
            self.wake.clear()
            try:await asyncio.wait_for(self.wake.wait(),timeout=max(10,min(interval,3600)))
            except asyncio.TimeoutError:pass

iotsin_collector=IotsinRealtimeCollector()

class IotCloudRealtimeCollector:
    """Token-backed read-only polling; survives backend restarts without captcha."""
    def __init__(self):self.task=None;self.running=False
    async def start(self):
        if self.running:return
        self.running=True;self.task=asyncio.create_task(self._loop(),name='iot-cloud-realtime-poll')
    async def stop(self):
        self.running=False
        if self.task:self.task.cancel();await asyncio.gather(self.task,return_exceptions=True);self.task=None
    async def _loop(self):
        while self.running:
            cfg=config()
            if str(cfg.get('IOT_CLOUD_AUTO_POLL','false')).lower()=='true':
                with SessionLocal() as db:
                    try:await collect_cloud(db)
                    except Exception as exc:
                        db.rollback()
                        message=str(exc) if isinstance(exc,ExternalError) else '第三方实时接口请求失败'
                        save(db,'IOT_CLOUD','STATE','latest',dict(connected=False,token_valid=False,collection_mode='AUTOMATIC_TOKEN_API_POLL',error=message))
                        db.commit()
            interval=int(cfg.get('IOT_CLOUD_POLL_SECONDS','30'))
            await asyncio.sleep(max(10,min(interval,3600)))

cloud_collector=IotCloudRealtimeCollector()

async def read_iotsin(db,path,params,kind):
    payload=await iotsin.get(path,params)
    key=hashlib.sha256(json.dumps([path,params],sort_keys=True,default=str).encode()).hexdigest()
    save(db,'IOTSIN_SENSOR',kind,key,payload);db.commit();return payload

async def read_cloud(db,path,params):
    cfg=config()
    async with httpx.AsyncClient(base_url=cfg.get('IOT_CLOUD_BASE_URL','http://iot.lwbsq.com'),timeout=15,trust_env=False) as client:
        raw=await cloud.get(client,path,cfg,params)
    save(db,'IOT_CLOUD','RAW',hashlib.sha256(json.dumps([path,params],sort_keys=True).encode()).hexdigest(),raw)
    store_metrics(db,'IOT_CLOUD',cloud_metrics(raw));db.commit();return raw

def status(db):
    result={}
    for source in ('IOT_CLOUD','WEATHER_STATION','IOTSIN_SENSOR'):
        row=db.scalar(select(ExternalDataRecord).where(ExternalDataRecord.source_type==source,ExternalDataRecord.record_kind=='STATE'))
        result[source]={**(row.payload if row else {'connected':False}), 'collected_at':row.collected_at.isoformat() if row else None}
        result[source].pop('raw_payload',None)
    cfg=config()
    if str(cfg.get('IOT_CLOUD_USE_IOTSIN_CREDENTIALS','false')).lower()=='true':
        result['IOT_CLOUD']['credentials_configured']=bool(cfg.get('IOTSIN_LOGIN_NAME') and cfg.get('IOTSIN_PASSWORD'))
    else:
        result['IOT_CLOUD']['credentials_configured']=bool(cfg.get('IOT_CLOUD_LOGIN_NAME') and cfg.get('IOT_CLOUD_PASSWORD'))
    result['IOTSIN_SENSOR']['credentials_configured']=bool(config().get('IOTSIN_LOGIN_NAME') and config().get('IOTSIN_PASSWORD'))
    result['IOTSIN_SENSOR']['session_valid']=iotsin.authenticated
    return result

def cloud_device_dashboard(db,hours=6):
    """Read only stored observations; never invent points for offline devices."""
    cutoff=datetime.utcnow()-timedelta(hours=hours)
    devices=db.scalars(select(ExternalDataRecord).where(ExternalDataRecord.source_type=='IOT_CLOUD',ExternalDataRecord.record_kind=='DEVICE').order_by(ExternalDataRecord.record_key)).all()
    raw=db.scalar(select(ExternalDataRecord).where(ExternalDataRecord.source_type=='IOT_CLOUD',ExternalDataRecord.record_kind=='RAW',ExternalDataRecord.record_key=='realtime'))
    latest={str(item.get('deviceAddr')):item for item in list_payload(raw.payload) if isinstance(item,dict) and item.get('deviceAddr') is not None} if raw else {}
    metric_rows=db.scalars(select(ExternalDataRecord).where(ExternalDataRecord.source_type=='IOT_CLOUD',ExternalDataRecord.record_kind=='METRIC',ExternalDataRecord.collected_at>=cutoff).order_by(ExternalDataRecord.collected_at.desc()).limit(5000)).all()
    series={}
    for record in metric_rows:
        p=record.payload;device_id=p.get('device_id');code=p.get('metric_code')
        if not device_id or not code:continue
        key=(str(device_id),str(code))
        points=series.setdefault(key,[])
        if len(points)>=60 or p.get('value') is None or not p.get('timestamp'):continue
        if any(point['timestamp']==p['timestamp'] for point in points):continue
        points.append(dict(timestamp=p['timestamp'],value=p['value']))
    result=[]
    for record in devices:
        p=record.payload;device_id=record.record_key;live=latest.get(device_id,{})
        status=live.get('deviceStatus')
        factors=[]
        for (item_id,code),points in series.items():
            if item_id!=device_id:continue
            current=next((row.payload for row in metric_rows if str(row.payload.get('device_id'))==device_id and str(row.payload.get('metric_code'))==code),{})
            factors.append(dict(metric_code=code,metric_name=current.get('metric_name') or code,unit=current.get('unit'),value=current.get('value'),timestamp=current.get('timestamp'),quality_status=current.get('quality_status'),points=list(reversed(points))))
        factors.sort(key=lambda item:item['metric_code'])
        result.append(dict(device_id=device_id,device_name=p.get('upstream_device_name') or device_id,device_status=status or 'unknown',online=status=='normal',building_id=p.get('building_id'),floor_id=p.get('floor_id'),area_id=p.get('area_id'),mapping_status=p.get('mapping_status'),factors=factors))
    state=db.scalar(select(ExternalDataRecord).where(ExternalDataRecord.source_type=='IOT_CLOUD',ExternalDataRecord.record_kind=='STATE',ExternalDataRecord.record_key=='latest'))
    collected_at=state.collected_at.replace(tzinfo=timezone.utc).isoformat() if state else None
    return dict(source_type='IOT_CLOUD',data_label='REALTIME',device_count=len(result),online_count=sum(x['online'] for x in result),offline_count=sum(x['device_status'] not in ('normal','unknown') for x in result),unknown_count=sum(x['device_status']=='unknown' for x in result),last_collected_at=collected_at,collection_connected=bool(state and state.payload.get('connected')),devices=result)
