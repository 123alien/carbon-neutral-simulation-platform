from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.batch import SimulationBatchCreate,SimulationBatchRead,RecommendationConvertRequest
from app.schemas.scenario import ScenarioRead
from app.services import batch_simulation_service,recommendation_conversion_service
router=APIRouter(tags=["simulation-batches"])
def _call(fn,*args):
    try:return fn(*args)
    except LookupError as exc:raise HTTPException(404,str(exc))
    except ValueError as exc:raise HTTPException(400,str(exc))
@router.post("/simulation/batches",response_model=SimulationBatchRead,status_code=201)
def create_batch(data:SimulationBatchCreate,db:Session=Depends(get_db)):return _call(batch_simulation_service.run_batch,db,data)
@router.get("/simulation/batches/{batch_id}",response_model=SimulationBatchRead)
def get_batch(batch_id:int,db:Session=Depends(get_db)):return _call(batch_simulation_service.get_batch,db,batch_id)
@router.post("/recommendations/paths/{recommendation_id}/convert-to-scenario",response_model=ScenarioRead,status_code=201)
def convert(recommendation_id:int,data:RecommendationConvertRequest,db:Session=Depends(get_db)):return _call(recommendation_conversion_service.convert,db,recommendation_id,data)
