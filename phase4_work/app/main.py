from fastapi import FastAPI

# Application process is reload-safe; database migrations remain an explicit step.
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.database import engine, settings
from app.settings import database_identity
from app.api.routes import enterprises_router, energy_router, scenarios_router, simulation_router, hourly_router, weather_router, market_router, data_sources_router, accounting_router, recommendations_router, batches_router, carbon_market_router, localized_router, system_router, model_validation_router, acceptance_demo_router, result_interface_router, cross_camera_router
from app.services.acquisition_runtime_service import scheduler,mqtt_manager
from app.services.external_data_service import iotsin_collector,cloud_collector

@asynccontextmanager
async def lifespan(_app):
    show_runtime_database()
    await scheduler.start();await mqtt_manager.start();await iotsin_collector.start();await cloud_collector.start()
    try:yield
    finally:await cloud_collector.stop();await iotsin_collector.stop();await mqtt_manager.stop();await scheduler.stop()

app = FastAPI(
    title="Carbon Neutrality Simulation Platform V1",
    version="1.0.0-alpha.11",
    description="Enterprise data -> annual/hourly scenario simulation -> carbon/economic comparison",lifespan=lifespan,
)

def show_runtime_database() -> None:
    database_type, database_name = database_identity(settings.database_url)
    revision = "unversioned"
    try:
        with engine.connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none() or "unversioned"
    except Exception:
        revision = "unavailable"
    print(f"[database] environment={settings.environment} type={database_type} name={database_name} alembic_head={revision}")
app.include_router(enterprises_router, prefix="/api")
app.include_router(energy_router, prefix="/api")
app.include_router(scenarios_router, prefix="/api")
app.include_router(simulation_router, prefix="/api")
app.include_router(hourly_router, prefix="/api")
app.include_router(weather_router, prefix="/api")
app.include_router(market_router, prefix="/api")
app.include_router(data_sources_router, prefix="/api")
app.include_router(accounting_router, prefix="/api")
app.include_router(recommendations_router, prefix="/api")
app.include_router(batches_router, prefix="/api")
app.include_router(carbon_market_router, prefix="/api")
app.include_router(localized_router, prefix="/api")
app.include_router(system_router, prefix="/api")
app.include_router(model_validation_router, prefix="/api")
app.include_router(acceptance_demo_router, prefix="/api")
app.include_router(result_interface_router, prefix="/api")
app.include_router(cross_camera_router, prefix="/api")
from app.api.routes.external_data import router as external_data_router
app.include_router(external_data_router,prefix='/api')

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0-alpha.11"}
