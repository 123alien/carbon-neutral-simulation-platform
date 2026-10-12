from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.simulation import (
    SimulationRunRequest, SimulationTaskRead, SimulationResultRead,
    MultiScenarioCompareRequest, MultiScenarioCompareRead,
)
from app.services.simulation_service import run_simulation, get_task_result, compare_scenarios
from app.schemas.batch import SimulationBatchRead
from app.services import batch_simulation_service
from app.schemas.long_term import LongTermPathRequest, LongTermPathRunRead, StrengthenedPathRequest
from app.services.long_term_path_service import run_long_term_path, get_long_term_path, list_long_term_paths, strengthen_long_term_path

router = APIRouter(prefix="/simulation", tags=["simulation"])

@router.post("/long-term/run", response_model=LongTermPathRunRead, status_code=201)
def run_long_term(req: LongTermPathRequest, db: Session = Depends(get_db)):
    try:
        return run_long_term_path(db, req)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e))

@router.get("/long-term/runs", response_model=list[LongTermPathRunRead])
def long_term_runs(enterprise_id: int, limit: int = 20, db: Session = Depends(get_db)):
    return list_long_term_paths(db, enterprise_id, max(1, min(limit, 100)))

@router.get("/long-term/{run_id}", response_model=LongTermPathRunRead)
def long_term_result(run_id: int, db: Session = Depends(get_db)):
    row = get_long_term_path(db, run_id)
    if row is None: raise HTTPException(404, "long-term path run not found")
    return row

@router.post("/long-term/{run_id}/strengthen", response_model=LongTermPathRunRead, status_code=201)
def strengthen_path(run_id: int, req: StrengthenedPathRequest, db: Session = Depends(get_db)):
    try:return strengthen_long_term_path(db,run_id,req)
    except LookupError as e:raise HTTPException(404,str(e))
    except (ValueError,KeyError) as e:raise HTTPException(400,str(e))

@router.post("/run", response_model=SimulationTaskRead)
def run(req: SimulationRunRequest, db: Session = Depends(get_db)):
    try:
        return run_simulation(db, req)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e))

@router.post("/compare", response_model=MultiScenarioCompareRead)
def compare(req: MultiScenarioCompareRequest, db: Session = Depends(get_db)):
    try:
        items = compare_scenarios(db, req.scenario_ids, {
            "electricity_price_per_kwh": req.electricity_price_per_kwh,
            "feed_in_tariff_per_kwh": req.feed_in_tariff_per_kwh,
            "neutrality_epsilon_t": req.neutrality_epsilon_t,
            "peak_stability_years": req.peak_stability_years,
            "neutrality_stability_years": req.neutrality_stability_years,
        })
        return {"items": items}
    except LookupError as e:
        raise HTTPException(404, str(e))
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e))

@router.get("/batches", response_model=list[SimulationBatchRead])
def batches(enterprise_id: int | None = None, limit: int = 50, db: Session = Depends(get_db)):
    return batch_simulation_service.list_batches(db, enterprise_id, max(1, min(limit, 200)))

@router.get("/{task_id}", response_model=SimulationResultRead)
def get_result(task_id: int, db: Session = Depends(get_db)):
    task, results = get_task_result(db, task_id)
    if not task:
        raise HTTPException(404, "simulation task not found")
    return {"task": task, "results": results}
