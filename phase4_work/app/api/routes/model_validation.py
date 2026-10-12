from fastapi import APIRouter,HTTPException
from app.services import model_validation_service as service
router=APIRouter(prefix="/model-validation",tags=["model-validation"])
@router.get("")
def summaries():return service.summaries()
@router.get("/{model}")
def detail(model:str):
    try:return service.detail(model)
    except LookupError as exc:raise HTTPException(404,str(exc))
