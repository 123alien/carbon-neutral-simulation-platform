from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.data_source import DataSourceCreate, DataSourceUpdate, DataSourceRead, DeviceCreate, DeviceRead, DeviceMetricRead, ConnectionTestRead, SyncResultRead, DataQualityRead, AcquisitionConfig
from app.services import data_source_service as service
from app.services.acquisition_runtime_service import scheduler,mqtt_manager,read_runtime,configure

router=APIRouter(tags=["data-sources"])

def _call(fn,*args):
    try:return fn(*args)
    except LookupError as exc:raise HTTPException(404,str(exc))
    except ValueError as exc:raise HTTPException(400,str(exc))

@router.post("/data-sources",response_model=DataSourceRead,status_code=201)
def create(data:DataSourceCreate,db:Session=Depends(get_db)):return _call(service.create,db,data)
@router.get("/data-sources",response_model=list[DataSourceRead])
def list_all(enterprise_id:int|None=None,site_id:int|None=None,db:Session=Depends(get_db)):return service.list_all(db,enterprise_id,site_id)
@router.get("/data-sources/capabilities")
def capabilities():return service.capabilities()
@router.get("/data-sources/acquisition-overview")
def acquisition_overview(enterprise_id:int|None=None,site_id:int|None=None,db:Session=Depends(get_db)):return service.acquisition_overview(db,enterprise_id,site_id)
@router.get("/data-sources/{source_id}",response_model=DataSourceRead)
def get_one(source_id:int,db:Session=Depends(get_db)):return service._read(_call(service.get,db,source_id))
@router.get("/data-sources/{source_id}/details")
def details(source_id:int,db:Session=Depends(get_db)):return _call(service.details,db,source_id)
@router.get("/data-sources/{source_id}/validation-logs")
def validation_logs(source_id:int,limit:int=100,db:Session=Depends(get_db)):return _call(service.validation_logs,db,source_id,max(1,min(limit,500)))
@router.get("/data-sources/{source_id}/runtime")
def runtime(source_id:int,db:Session=Depends(get_db)):return _call(read_runtime,db,source_id)
@router.put("/data-sources/{source_id}/acquisition-config")
async def acquisition_config(source_id:int,data:AcquisitionConfig,db:Session=Depends(get_db)):
    result=_call(configure,db,source_id,data.collection_mode,data.enabled,data.interval_minutes)
    source=_call(service.get,db,source_id)
    if source.source_type=="MQTT":
        if data.enabled:await mqtt_manager.start_source(source_id)
        else:await mqtt_manager.stop_source(source_id)
    return read_runtime(db,source_id)
@router.post("/data-sources/{source_id}/start")
async def start_acquisition(source_id:int,db:Session=Depends(get_db)):
    source=_call(service.get,db,source_id)
    if source.source_type=="REST_API":_call(configure,db,source_id,"INTERVAL",True,source.interval_minutes or 60)
    elif source.source_type=="MQTT":_call(configure,db,source_id,"PERSISTENT",True,None);await mqtt_manager.start_source(source_id)
    else:raise HTTPException(400,"automatic acquisition is supported only for REST_API and MQTT")
    return read_runtime(db,source_id)
@router.post("/data-sources/{source_id}/stop")
async def stop_acquisition(source_id:int,db:Session=Depends(get_db)):
    source=_call(service.get,db,source_id)
    if source.source_type=="MQTT":await mqtt_manager.stop_source(source_id)
    else:_call(configure,db,source_id,source.collection_mode,False,source.interval_minutes)
    return read_runtime(db,source_id)
@router.post("/data-sources/{source_id}/sync-now")
async def sync_now(source_id:int,db:Session=Depends(get_db)):
    source=_call(service.get,db,source_id)
    if source.source_type=="REST_API":result=await scheduler.trigger(source_id)
    else:result=service.sync(db,source)
    if result is None:raise HTTPException(409,"data source is already running or synchronization failed")
    return result
@router.patch("/data-sources/{source_id}",response_model=DataSourceRead)
def update(source_id:int,data:DataSourceUpdate,db:Session=Depends(get_db)):return _call(service.update,db,_call(service.get,db,source_id),data)
@router.delete("/data-sources/{source_id}",status_code=204)
async def remove(source_id:int,db:Session=Depends(get_db)):
    source=_call(service.get,db,source_id)
    _call(service.assert_deletable,db,source)
    if source.source_type=="MQTT":await mqtt_manager.stop_source(source_id)
    elif source.source_type=="REST_API" and source.schedule_enabled:_call(configure,db,source_id,source.collection_mode,False,source.interval_minutes)
    _call(service.delete,db,source);return Response(status_code=204)
@router.post("/data-sources/{source_id}/test",response_model=ConnectionTestRead)
def test(source_id:int,db:Session=Depends(get_db)):
    obj=_call(service.get,db,source_id)
    try:return service.test_connection(obj)
    except Exception:return {"success":False,"message":"connection failed; check endpoint, TLS and credentials"}
@router.post("/data-sources/{source_id}/sync",response_model=SyncResultRead)
def sync(source_id:int,db:Session=Depends(get_db)):
    try:return service.sync(db,_call(service.get,db,source_id))
    except HTTPException:raise
    except Exception as exc:db.rollback();raise HTTPException(400,f"sync failed: {type(exc).__name__}")
@router.get("/data-sources/{source_id}/data-quality",response_model=DataQualityRead)
def quality(source_id:int,db:Session=Depends(get_db)):_call(service.get,db,source_id);return service.quality(db,source_id)

@router.post("/devices",response_model=DeviceRead,status_code=201)
def create_device(data:DeviceCreate,db:Session=Depends(get_db)):return _call(service.create_device,db,data)
@router.get("/devices",response_model=list[DeviceRead])
def devices(enterprise_id:int|None=None,data_source_id:int|None=None,db:Session=Depends(get_db)):return service.list_devices(db,enterprise_id,data_source_id)
def _utc(value):return value.astimezone(timezone.utc).replace(tzinfo=None) if value and value.tzinfo else value
@router.get("/devices/{device_id}/metrics",response_model=list[DeviceMetricRead])
def metrics(device_id:int,start:datetime|None=None,end:datetime|None=None,metric_name:str|None=None,db:Session=Depends(get_db)):return service.metrics(db,device_id,_utc(start),_utc(end),metric_name)
