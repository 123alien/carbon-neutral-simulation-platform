from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.recommendation import PathRecommendationRequest,RecommendationRunRead
from app.services import recommendation_service
from app.recommendation import measure_catalog
router=APIRouter(prefix="/recommendations",tags=["recommendations"])
@router.get("/measure-catalog")
def catalog():return measure_catalog()
def _call(fn,*args):
    try:return fn(*args)
    except LookupError as exc:raise HTTPException(404,str(exc))
    except ValueError as exc:raise HTTPException(400,str(exc))
@router.post("/low-carbon-paths",response_model=RecommendationRunRead,status_code=201)
def recommend(data:PathRecommendationRequest,db:Session=Depends(get_db)):return _call(recommendation_service.generate,db,data)
@router.get("/low-carbon-paths",response_model=list[RecommendationRunRead])
def recommendations(enterprise_id:int|None=None,limit:int=50,db:Session=Depends(get_db)):return recommendation_service.list_runs(db,enterprise_id,max(1,min(limit,200)))
@router.get("/low-carbon-paths/{run_id}",response_model=RecommendationRunRead)
def get_recommendation(run_id:int,db:Session=Depends(get_db)):return _call(recommendation_service.get,db,run_id)
