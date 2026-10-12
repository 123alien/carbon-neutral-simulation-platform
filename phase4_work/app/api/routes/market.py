import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.market import PriceImportOptions, FactorImportOptions, MarketImportPreview, MarketImportConfirm, ElectricityPriceRead, GridFactorRead, GreenPowerContractCreate, GreenPowerContractRead
from app.services import market_service
from app.services.green_power_service import GreenPowerService

router = APIRouter(prefix="/market", tags=["electricity-market"])

def _call(fn, *args):
    try: return fn(*args)
    except LookupError as exc: raise HTTPException(404, str(exc))
    except ValueError as exc: raise HTTPException(400, str(exc))

def _options(raw, schema):
    try: return schema.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as exc: raise HTTPException(422, f"invalid options: {exc}")

@router.post("/prices/import/preview", response_model=MarketImportPreview)
async def preview_prices(file: UploadFile = File(...), options: str = Form(...), db: Session = Depends(get_db)):
    return _call(market_service.preview_price, db, file.filename or "upload", await file.read(), _options(options, PriceImportOptions))[0]

@router.post("/prices/import/confirm", response_model=MarketImportConfirm, status_code=201)
async def confirm_prices(file: UploadFile = File(...), options: str = Form(...), db: Session = Depends(get_db)):
    return _call(market_service.confirm_price, db, file.filename or "upload", await file.read(), _options(options, PriceImportOptions))

@router.post("/grid-factors/import/preview", response_model=MarketImportPreview)
async def preview_factors(file: UploadFile = File(...), options: str = Form(...), db: Session = Depends(get_db)):
    return _call(market_service.preview_factor, db, file.filename or "upload", await file.read(), _options(options, FactorImportOptions))[0]

@router.post("/grid-factors/import/confirm", response_model=MarketImportConfirm, status_code=201)
async def confirm_factors(file: UploadFile = File(...), options: str = Form(...), db: Session = Depends(get_db)):
    return _call(market_service.confirm_factor, db, file.filename or "upload", await file.read(), _options(options, FactorImportOptions))

def _utc(value): return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value

@router.get("/prices", response_model=list[ElectricityPriceRead])
def prices(enterprise_id: int, start: datetime, end: datetime, db: Session = Depends(get_db)):
    return market_service.query_prices(db, enterprise_id, _utc(start), _utc(end))

@router.get("/grid-factors", response_model=list[GridFactorRead])
def factors(region: str, start: datetime, end: datetime, db: Session = Depends(get_db)):
    return market_service.query_factors(db, region, _utc(start), _utc(end))

@router.post("/green-power/contracts", response_model=GreenPowerContractRead, status_code=201)
def create_contract(data: GreenPowerContractCreate, db: Session = Depends(get_db)):
    normalized = data.model_copy(update={"start_at": _utc(data.start_at), "end_at": _utc(data.end_at)})
    return _call(GreenPowerService.create_contract, db, normalized)

@router.get("/green-power/contracts", response_model=list[GreenPowerContractRead])
def contracts(enterprise_id: int, db: Session = Depends(get_db)):
    return GreenPowerService.list_contracts(db, enterprise_id)
