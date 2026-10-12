import json
from datetime import datetime
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.hourly import (
    LoadTimeseriesBulkCreate, LoadTimeseriesRead, HourlySimulationRunRequest,
    HourlySimulationResultRead,
    LoadImportOptions, LoadImportPreviewResponse, LoadImportConfirmResponse,
    LoadQueryResponse, LoadAggregateResponse, LoadStatisticsResponse, LoadDataQualityResponse,
)
from app.services.energy_service import add_load_points, list_load_points
from app.services.hourly_simulation_service import run_hourly_simulation, get_hourly_task_result
from app.services.load_import_service import parse_and_validate, confirm_import
from app.services import load_query_service
from app.simulation.device_models import HourlyDeviceModelRegistry

router = APIRouter(tags=["hourly-simulation"])


@router.get("/simulation/hourly/models")
def hourly_device_models():
    return {"models": HourlyDeviceModelRegistry.available(), "measure_types": ["WIND", "EV_CHARGER"]}


def _import_options(raw: str) -> LoadImportOptions:
    try:
        return LoadImportOptions.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(422, f"invalid options: {exc}")


@router.post("/loads/hourly/import/preview", response_model=LoadImportPreviewResponse)
async def preview_hourly_import(file: UploadFile = File(...), options: str = Form(...), db: Session = Depends(get_db)):
    try:
        parsed = parse_and_validate(db, file.filename or "upload", await file.read(), _import_options(options))
        return parsed.report
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except (ValueError, UnicodeError) as exc:
        raise HTTPException(400, str(exc))


@router.post("/loads/hourly/import/confirm", response_model=LoadImportConfirmResponse, status_code=201)
async def confirm_hourly_import(file: UploadFile = File(...), options: str = Form(...), db: Session = Depends(get_db)):
    try:
        return confirm_import(db, file.filename or "upload", await file.read(), _import_options(options))
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except (ValueError, UnicodeError) as exc:
        db.rollback()
        raise HTTPException(400, str(exc))


def _query_call(function, *args):
    try:
        return function(*args)
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/loads/hourly", response_model=LoadQueryResponse)
def query_hourly_loads(enterprise_id: int, start: datetime, end: datetime,
                       timezone_name: str = Query(default="UTC", alias="timezone"),
                       db: Session = Depends(get_db)):
    return _query_call(load_query_service.query_loads, db, enterprise_id, start, end, timezone_name)


@router.get("/loads/aggregate", response_model=LoadAggregateResponse)
def aggregate_hourly_loads(enterprise_id: int, start: datetime, end: datetime,
                           granularity: str = "day", interval_minutes: int = Query(default=60, gt=0, le=1440),
                           timezone_name: str = Query(default="UTC", alias="timezone"),
                           db: Session = Depends(get_db)):
    return _query_call(load_query_service.aggregate_loads, db, enterprise_id, start, end, timezone_name, granularity, interval_minutes)


@router.get("/loads/statistics", response_model=LoadStatisticsResponse)
def load_statistics(enterprise_id: int, start: datetime, end: datetime,
                    interval_minutes: int = Query(default=60, gt=0, le=1440),
                    timezone_name: str = Query(default="UTC", alias="timezone"),
                    db: Session = Depends(get_db)):
    return _query_call(load_query_service.statistics, db, enterprise_id, start, end, timezone_name, interval_minutes)


@router.get("/loads/data-quality", response_model=LoadDataQualityResponse)
def load_data_quality(enterprise_id: int, start: datetime, end: datetime,
                      interval_minutes: int = Query(default=60, gt=0, le=1440),
                      timezone_name: str = Query(default="UTC", alias="timezone"),
                      db: Session = Depends(get_db)):
    return _query_call(load_query_service.data_quality, db, enterprise_id, start, end, timezone_name, interval_minutes)


@router.post("/loads/hourly/bulk", response_model=list[LoadTimeseriesRead])
def upload_hourly(req: LoadTimeseriesBulkCreate, db: Session = Depends(get_db)):
    if not req.items:
        raise HTTPException(400, "items cannot be empty")
    try:
        return add_load_points(db, req.items)
    except Exception as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.get("/loads/hourly/{enterprise_id}", response_model=list[LoadTimeseriesRead])
def get_hourly(enterprise_id: int, year: int | None = None, db: Session = Depends(get_db)):
    return list_load_points(db, enterprise_id, year)


@router.post("/simulation/hourly/run", response_model=HourlySimulationResultRead)
def run_hourly(req: HourlySimulationRunRequest, db: Session = Depends(get_db)):
    try:
        task, results, summary = run_hourly_simulation(db, req)
        return {
            "summary": {"task_id": task.id, "scenario_id": task.scenario_id, "scenario_version_id": task.scenario_version_id, **summary.__dict__},
            "results": results,
        }
    except LookupError as e:
        raise HTTPException(404, str(e))
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e))


@router.get("/simulation/hourly/{task_id}")
def hourly_result(task_id: int, db: Session = Depends(get_db)):
    task, rows = get_hourly_task_result(db, task_id)
    if task is None:
        raise HTTPException(404, "simulation task not found")
    return {"task": task, "results": rows}
