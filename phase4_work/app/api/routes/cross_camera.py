from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.cross_camera import (
    CameraSpatialMappingCreate, CameraSpatialMappingRead, CameraSpatialMappingUpdate,
    CrossCameraAdaptRequest, CrossCameraAdaptResponse,
)
from app.services import cross_camera_adapter_service as service

router=APIRouter(prefix="/cross-camera-adapter",tags=["cross-camera-adapter"])

from app.services.cross_camera_source_service import SourceRequest, load_source, UpstreamUnavailable, live_health, live_tasks

@router.get('/health')
async def health():return await live_health()

@router.get('/tasks')
async def tasks():
    try:return await live_tasks()
    except Exception as exc:
        raise HTTPException(502,'实时任务列表无法读取，请检查连接及登录凭证') from exc

@router.get('/tasks/{task_id}/carbon-association')
async def carbon_association(task_id:str):
    from app.services.cross_camera_source_service import live_carbon_association
    try:return await live_carbon_association(task_id)
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc
    except Exception as exc:raise HTTPException(502,'人员耗能关联结果读取失败，请检查真实任务及认证') from exc

@router.post('/paths')
async def paths(data:SourceRequest,db:Session=Depends(get_db)):
    try:return await load_source(db,data)
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc
    except UpstreamUnavailable as exc:raise HTTPException(502,str(exc)) from exc

def call(function,*args):
    try:return function(*args)
    except LookupError as exc:raise HTTPException(404,str(exc)) from exc
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc

@router.post("/camera-mappings",response_model=CameraSpatialMappingRead,status_code=201)
def create_mapping(data:CameraSpatialMappingCreate,db:Session=Depends(get_db)):return call(service.create_mapping,db,data)

@router.put("/camera-mappings/{mapping_id}",response_model=CameraSpatialMappingRead)
def update_mapping(mapping_id:int,data:CameraSpatialMappingUpdate,db:Session=Depends(get_db)):return call(service.update_mapping,db,mapping_id,data)

@router.get("/camera-mappings",response_model=list[CameraSpatialMappingRead])
def mappings(campus_id:str,camera_id:str|None=None,db:Session=Depends(get_db)):return service.list_mappings(db,campus_id,camera_id)

@router.post("/adapt",response_model=CrossCameraAdaptResponse)
def adapt(data:CrossCameraAdaptRequest,db:Session=Depends(get_db)):return call(service.adapt,db,data)
