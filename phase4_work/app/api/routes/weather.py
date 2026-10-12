import json
from datetime import datetime
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.weather import WeatherSiteCreate, WeatherSiteRead, WeatherImportOptions, WeatherImportPreview, WeatherImportConfirm, WeatherHourlyResponse, WeatherStatistics, WeatherDataQuality
from app.services import weather_service

router = APIRouter(prefix="/weather", tags=["weather"])


def _call(fn, *args):
    try: return fn(*args)
    except LookupError as exc: raise HTTPException(404, str(exc))
    except ValueError as exc: raise HTTPException(400, str(exc))


def _options(raw):
    try: return WeatherImportOptions.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as exc: raise HTTPException(422, f"invalid options: {exc}")


@router.post("/sites", response_model=WeatherSiteRead, status_code=201)
def create_site(data: WeatherSiteCreate, db: Session = Depends(get_db)):
    return _call(weather_service.create_site, db, data)


@router.get("/sites", response_model=list[WeatherSiteRead])
def sites(enterprise_id: int | None = None, db: Session = Depends(get_db)):
    return weather_service.list_sites(db, enterprise_id)


@router.post("/import/preview", response_model=WeatherImportPreview)
async def preview(file: UploadFile = File(...), options: str = Form(...), db: Session = Depends(get_db)):
    report, _, _ = _call(weather_service.parse_weather, db, file.filename or "upload", await file.read(), _options(options))
    return report


@router.post("/import/confirm", response_model=WeatherImportConfirm, status_code=201)
async def confirm(file: UploadFile = File(...), options: str = Form(...), db: Session = Depends(get_db)):
    return _call(weather_service.confirm_weather, db, file.filename or "upload", await file.read(), _options(options))


@router.get("/hourly", response_model=WeatherHourlyResponse)
def hourly(site_id: int, start: datetime, end: datetime, timezone_name: str = Query("UTC", alias="timezone"), db: Session = Depends(get_db)):
    return _call(weather_service.hourly, db, site_id, start, end, timezone_name)


@router.get("/statistics", response_model=WeatherStatistics)
def statistics(site_id: int, start: datetime, end: datetime, interval_minutes: int = Query(60, gt=0, le=1440), timezone_name: str = Query("UTC", alias="timezone"), db: Session = Depends(get_db)):
    return _call(weather_service.statistics, db, site_id, start, end, timezone_name, interval_minutes)


@router.get("/data-quality", response_model=WeatherDataQuality)
def quality(site_id: int, start: datetime, end: datetime, interval_minutes: int = Query(60, gt=0, le=1440), timezone_name: str = Query("UTC", alias="timezone"), db: Session = Depends(get_db)):
    return _call(weather_service.data_quality, db, site_id, start, end, timezone_name, interval_minutes)
