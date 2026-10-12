from datetime import datetime,timezone,timedelta
from fastapi import APIRouter,Depends,HTTPException,Query,Response
from pydantic import BaseModel,Field
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models.external_data import ExternalDataRecord
from app.models import DataSource,DataSourceRuntimeState,Device,DeviceMetric
from app.services import external_data_service as service
router=APIRouter(prefix='/external-data',tags=['external-data'])

@router.get('/status')
def status(db:Session=Depends(get_db)):return service.status(db)

@router.get('/device-dashboard')
def device_dashboard(hours:int=Query(default=6,ge=1,le=24),db:Session=Depends(get_db)):
    return service.cloud_device_dashboard(db,hours)

@router.get('/energy-meter-dashboard')
def energy_meter_dashboard(hours:int=Query(default=6,ge=1,le=24),db:Session=Depends(get_db)):
    """Expose stored read-only MQTT meter observations without credentials or broker details."""
    source=db.scalars(select(DataSource).where(DataSource.enterprise_id==11,DataSource.source_type=='MQTT',DataSource.name=='能源管控电表 MQTT 实时数据').order_by(DataSource.id.desc())).first()
    if not source:return {'source_type':'ENERGY_MQTT','data_label':'REALTIME','connected':False,'subscribed':False,'devices':[],'device_count':0,'online_count':0,'offline_count':0}
    runtime=db.scalars(select(DataSourceRuntimeState).where(DataSourceRuntimeState.data_source_id==source.id)).first()
    cutoff=datetime.utcnow()-timedelta(hours=hours)
    rows=list(db.scalars(select(DeviceMetric).where(DeviceMetric.data_source_id==source.id,DeviceMetric.timestamp>=cutoff).order_by(DeviceMetric.timestamp.desc()).limit(3000)).all())
    devices=list(db.scalars(select(Device).where(Device.data_source_id==source.id).order_by(Device.id)).all())
    labels={'phase_a_voltage_v':'A相电压','phase_b_voltage_v':'B相电压','phase_c_voltage_v':'C相电压','phase_a_current_a':'A相电流','phase_b_current_a':'B相电流','phase_c_current_a':'C相电流','power_kw':'实时功率','energy_kwh':'累计电量','water_m3':'累计水量','temperature_c':'温度','humidity_pct':'湿度'}
    latest_message=runtime.last_message_at if runtime else None
    fresh=bool(latest_message and latest_message>=datetime.utcnow()-timedelta(minutes=3))
    online=bool(runtime and runtime.connected and runtime.subscribed and fresh)
    result=[]
    for device in devices:
        grouped={}
        for row in rows:
            if row.device_id==device.id:grouped.setdefault(row.metric_name,[]).append(row)
        factors=[]
        for code,items in grouped.items():
            latest=items[0]
            factors.append({'metric_code':code,'metric_name':labels.get(code,code),'value':latest.value,'unit':latest.unit,'timestamp':latest.timestamp,'quality_status':latest.quality,'points':[{'timestamp':x.timestamp,'value':x.value} for x in reversed(items[:60])]})
        location=device.metadata_json or {}
        result.append({'device_id':device.external_id,'device_name':device.name,'device_type':device.device_type,'online':online,'device_status':'online' if online else 'offline','building_id':location.get('building_id'),'floor_id':location.get('floor_id'),'mapping_status':location.get('mapping_status','UNMAPPED'),'latest_observation_time':max((x.timestamp for x in rows if x.device_id==device.id),default=None),'factors':factors})
    return {'source_type':'ENERGY_MQTT','data_label':'REALTIME','connected':bool(runtime and runtime.connected),'subscribed':bool(runtime and runtime.subscribed),'runtime_status':runtime.runtime_status if runtime else 'STOPPED','last_message_at':latest_message,'device_count':len(result),'online_count':sum(x['online'] for x in result),'offline_count':sum(not x['online'] for x in result),'devices':result}

@router.get('/iotsin/captcha')
async def iotsin_captcha():
    try:
        content,content_type=await service.iotsin.captcha(service.config());return Response(content=content,media_type=content_type,headers={'Cache-Control':'no-store'})
    except Exception as exc:raise HTTPException(502,'塞恩云平台验证码获取失败') from exc

class IotsinLoginRequest(BaseModel):
    captcha_code:str=Field(min_length=1,max_length=12)

@router.post('/iotsin/login')
async def iotsin_login(data:IotsinLoginRequest):
    try:
        result=await service.iotsin.login(service.config(),data.captcha_code)
        service.iotsin_collector.trigger()
        return result
    except service.ExternalError as exc:raise HTTPException(401,str(exc)) from exc

@router.get('/iotsin/health')
def iotsin_health(db:Session=Depends(get_db)):
    state=service.status(db).get('IOTSIN_SENSOR',{})
    return {'base_url':service.config().get('IOTSIN_BASE_URL','http://iot.iotsin.com'),'credentials_configured':state.get('credentials_configured',False),'session_valid':state.get('session_valid',False),'connected':state.get('connected',False),'device_count':state.get('device_count'),'online_count':state.get('online_count'),'offline_count':state.get('offline_count'),'latest_metric_count':state.get('latest_metric_count'),'error':state.get('error')}

@router.get('/iotsin/devices/{device_addr}/factors')
async def iotsin_factors(device_addr:str):
    try:return await service.iotsin.get('/device/deviceWithEnabledFactorsByDeviceAddr',{'deviceAddr':device_addr})
    except service.ExternalError as exc:raise HTTPException(502,str(exc)) from exc

class IotsinDeviceBinding(BaseModel):
    building_id:str
    floor_number:int=Field(ge=1)

@router.post('/iotsin/devices/{device_addr}/binding')
def bind_iotsin_device(device_addr:str,data:IotsinDeviceBinding,db:Session=Depends(get_db)):
    try:return service.bind_iotsin_device(db,device_addr,data.building_id,data.floor_number)
    except service.ExternalError as exc:db.rollback();raise HTTPException(400,str(exc)) from exc

class IotsinHistoryRequest(BaseModel):
    device_addr:str
    factor_ids:list[str]=Field(min_length=1)
    start_time:datetime
    end_time:datetime

def _epoch_ms(value:datetime)->int:
    if value.tzinfo is None:value=value.replace(tzinfo=timezone.utc)
    return int(value.timestamp()*1000)

@router.post('/iotsin/history')
async def iotsin_history(data:IotsinHistoryRequest,db:Session=Depends(get_db)):
    if data.end_time<=data.start_time:raise HTTPException(400,'结束时间必须晚于开始时间')
    if (data.end_time-data.start_time).days>31:raise HTTPException(400,'单次历史查询不能超过31天')
    params={'deviceAddr':data.device_addr,'factorIds':','.join(data.factor_ids),'startTime':_epoch_ms(data.start_time),'endTime':_epoch_ms(data.end_time)}
    try:return await service.read_iotsin(db,'/sysData/multicolumnHistory',params,'HISTORY')
    except service.ExternalError as exc:db.rollback();raise HTTPException(502,str(exc)) from exc

class IotsinAlarmRequest(BaseModel):
    device_addrs:list[str]=Field(min_length=1)
    factor_id:str='-1'
    start_time:datetime
    end_time:datetime

@router.post('/iotsin/alarms')
async def iotsin_alarms(data:IotsinAlarmRequest,db:Session=Depends(get_db)):
    if data.end_time<=data.start_time:raise HTTPException(400,'结束时间必须晚于开始时间')
    if (data.end_time-data.start_time).days>31:raise HTTPException(400,'单次报警查询不能超过31天')
    params={'deviceAddr':','.join(data.device_addrs)+',','factorId':data.factor_id,'beginTime':_epoch_ms(data.start_time),'endTime':_epoch_ms(data.end_time)}
    try:return await service.read_iotsin(db,'/sysData/getAlarmRecords',params,'ALARM')
    except service.ExternalError as exc:db.rollback();raise HTTPException(502,str(exc)) from exc

@router.get('/records')
def records(source_type:str,kind:str='METRIC',limit:int=Query(default=100,ge=1,le=500),db:Session=Depends(get_db)):
    rows=db.scalars(select(ExternalDataRecord).where(ExternalDataRecord.source_type==source_type,ExternalDataRecord.record_kind==kind).order_by(ExternalDataRecord.collected_at.desc(),ExternalDataRecord.id.desc()).limit(limit)).all()
    return [dict(id=x.id,collected_at=x.collected_at,payload=x.payload) for x in rows]

@router.post('/collect/{source_type}')
async def collect(source_type:str,db:Session=Depends(get_db)):
    if source_type not in ('IOT_CLOUD','WEATHER_STATION','IOTSIN_SENSOR'):raise HTTPException(400,'请选择已配置的外部数据源')
    try:
        if source_type=='IOT_CLOUD':return await service.collect_cloud(db)
        if source_type=='IOTSIN_SENSOR':return await service.collect_iotsin(db)
        return await service.collect_weather(db)
    except Exception as exc:
        db.rollback()
        message=str(exc) if isinstance(exc,service.ExternalError) else '外部服务不可达或响应异常'
        service.save(db,source_type,'STATE','latest',{'connected':False,'error':message});db.commit()
        raise HTTPException(502,message) from exc

class HistoryRequest(BaseModel):
    deviceAddr:str
    nodeId:str
    startTime:str
    endTime:str

@router.post('/history')
async def history(data:HistoryRequest,db:Session=Depends(get_db)):
    try:return await service.read_cloud(db,'/api/data/historyList',data.model_dump())
    except Exception as exc:
        db.rollback();raise HTTPException(502,'历史数据读取失败，请核对凭证和查询时间范围') from exc

@router.get('/realtime/{device_addr}')
async def realtime(device_addr:str,db:Session=Depends(get_db)):
    try:return await service.read_cloud(db,'/api/data/getRealTimeDataByDeviceAddr',{'deviceAddr':device_addr})
    except Exception as exc:
        db.rollback();raise HTTPException(502,'指定设备实时数据读取失败') from exc

@router.get('/alarms')
async def alarms(db:Session=Depends(get_db)):
    try:return await service.read_cloud(db,'/api/data/alarmRecordList',{})
    except Exception as exc:
        db.rollback();raise HTTPException(502,'报警记录读取失败') from exc
