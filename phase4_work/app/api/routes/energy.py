from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Enterprise
from app.schemas.energy import (
    EnergyHistoryCreate, EnergyHistoryRead, EmissionFactorCreate, EmissionFactorRead,
    GrowthEstimateRead,
)
from app.services import energy_service

router = APIRouter(tags=["energy"])

@router.post("/energy-history", response_model=EnergyHistoryRead, status_code=201)
def add_energy(data: EnergyHistoryCreate, db: Session = Depends(get_db)):
    if not db.get(Enterprise, data.enterprise_id):
        raise HTTPException(404, "enterprise not found")
    try:
        return energy_service.add_energy(db, data)
    except Exception as e:
        db.rollback(); raise HTTPException(400, str(e))

@router.get("/energy-history/{enterprise_id}", response_model=list[EnergyHistoryRead])
def list_energy(enterprise_id: int, year: int | None = None, db: Session = Depends(get_db)):
    return energy_service.list_energy(db, enterprise_id, year)

@router.get("/energy-history/{enterprise_id}/growth-estimate", response_model=GrowthEstimateRead)
def growth_estimate(enterprise_id: int, energy_type: str = "electricity", method: str = "median_yoy",
                    db: Session = Depends(get_db)):
    if not db.get(Enterprise, enterprise_id):
        raise HTTPException(404, "enterprise not found")
    try:
        return energy_service.estimate_growth(db, enterprise_id, energy_type, method)
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.post("/emission-factors", response_model=EmissionFactorRead, status_code=201)
def add_factor(data: EmissionFactorCreate, db: Session = Depends(get_db)):
    try:
        return energy_service.add_emission_factor(db, data)
    except Exception as e:
        db.rollback(); raise HTTPException(400, str(e))
