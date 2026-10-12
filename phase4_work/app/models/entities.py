from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Enterprise(Base):
    __tablename__ = "enterprise"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    region: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(100))
    building_area: Mapped[float | None] = mapped_column(Float)
    population: Mapped[int | None] = mapped_column(Integer)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    base_year: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EnergyHistory(Base):
    __tablename__ = "energy_history"
    __table_args__ = (UniqueConstraint("enterprise_id", "year", "month", "energy_type", name="uq_energy_history"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    enterprise_id: Mapped[int] = mapped_column(ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int | None] = mapped_column(Integer)
    energy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    consumption: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str | None] = mapped_column(String(300))

class EmissionFactor(Base):
    __tablename__ = "emission_factor"
    __table_args__ = (UniqueConstraint("region", "year", "energy_type", "version", name="uq_emission_factor"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    region: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    energy_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    factor: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str | None] = mapped_column(String(500))
    version: Mapped[str] = mapped_column(String(80), nullable=False)

class Scenario(Base):
    __tablename__ = "scenario"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    enterprise_id: Mapped[int] = mapped_column(ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    base_year: Mapped[int] = mapped_column(Integer, nullable=False)
    start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    end_year: Mapped[int] = mapped_column(Integer, nullable=False)
    target_peak_year: Mapped[int | None] = mapped_column(Integer)
    target_neutral_year: Mapped[int | None] = mapped_column(Integer)
    baseline_growth_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    scenario_type: Mapped[str] = mapped_column(String(30), nullable=False, default="CUSTOM")
    current_version_id: Mapped[int | None] = mapped_column(BigInteger)
    measures: Mapped[list["ScenarioMeasure"]] = relationship(back_populates="scenario", cascade="all, delete-orphan")

class ScenarioMeasure(Base):
    __tablename__ = "scenario_measure"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenario.id", ondelete="CASCADE"), nullable=False, index=True)
    measure_type: Mapped[str] = mapped_column(String(50), nullable=False)
    start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    end_year: Mapped[int | None] = mapped_column(Integer)
    parameters_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    scenario: Mapped[Scenario] = relationship(back_populates="measures")

class SimulationTask(Base):
    __tablename__ = "simulation_task"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenario.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    parameter_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    summary_json: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)
    scenario_version_id: Mapped[int | None] = mapped_column(ForeignKey("scenario_version.id", ondelete="RESTRICT"), index=True)
    carbon_market_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    risk_parameter_snapshot_json: Mapped[dict | None] = mapped_column(JSON)

class LongTermPathRun(Base):
    """Immutable input and result snapshot for a multi-year path projection."""
    __tablename__ = "long_term_path_run"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    enterprise_id: Mapped[int] = mapped_column(ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False, index=True)
    scenario_version_id: Mapped[int] = mapped_column(ForeignKey("scenario_version.id", ondelete="RESTRICT"), nullable=False, index=True)
    baseline_task_id: Mapped[int | None] = mapped_column(ForeignKey("simulation_task.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SUCCESS")
    input_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

class SimulationYearResult(Base):
    __tablename__ = "simulation_year_result"
    __table_args__ = (UniqueConstraint("task_id", "year", name="uq_task_year"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("simulation_task.id", ondelete="CASCADE"), nullable=False, index=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenario.id", ondelete="CASCADE"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    electricity_base_kwh: Mapped[float] = mapped_column(Float, default=0)
    electricity_after_saving_kwh: Mapped[float] = mapped_column(Float, default=0)
    grid_power_kwh: Mapped[float] = mapped_column(Float, default=0)
    natural_gas_m3: Mapped[float] = mapped_column(Float, default=0)
    coal_kg: Mapped[float] = mapped_column(Float, default=0)
    oil_kg: Mapped[float] = mapped_column(Float, default=0)
    pv_generation_kwh: Mapped[float] = mapped_column(Float, default=0)
    pv_self_use_kwh: Mapped[float] = mapped_column(Float, default=0)
    pv_export_kwh: Mapped[float] = mapped_column(Float, default=0)
    energy_saved_kwh: Mapped[float] = mapped_column(Float, default=0)
    carbon_emission_t: Mapped[float] = mapped_column(Float, default=0)
    carbon_reduction_t: Mapped[float] = mapped_column(Float, default=0)
    investment: Mapped[float] = mapped_column(Float, default=0)
    annual_benefit: Mapped[float] = mapped_column(Float, default=0)

class LoadTimeseries(Base):
    __tablename__ = "load_timeseries"
    __table_args__ = (UniqueConstraint("enterprise_id", "timestamp", name="uq_enterprise_load_ts"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    enterprise_id: Mapped[int] = mapped_column(ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    load_kw: Mapped[float | None] = mapped_column(Float)
    load_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    irradiation_wm2: Mapped[float] = mapped_column(Float, default=0.0)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    humidity_pct: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String(300))

class SimulationHourResult(Base):
    __tablename__ = "simulation_hour_result"
    __table_args__ = (UniqueConstraint("task_id", "timestamp", name="uq_task_hour"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("simulation_task.id", ondelete="CASCADE"), nullable=False, index=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenario.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    load_base_kwh: Mapped[float] = mapped_column(Float, default=0)
    hvac_saved_kwh: Mapped[float] = mapped_column(Float, default=0)
    lighting_saved_kwh: Mapped[float] = mapped_column(Float, default=0)
    load_after_saving_kwh: Mapped[float] = mapped_column(Float, default=0)
    pv_generation_kwh: Mapped[float] = mapped_column(Float, default=0)
    pv_self_use_kwh: Mapped[float] = mapped_column(Float, default=0)
    pv_export_kwh: Mapped[float] = mapped_column(Float, default=0)
    grid_power_kwh: Mapped[float] = mapped_column(Float, default=0)
    carbon_emission_t: Mapped[float] = mapped_column(Float, default=0)
    electricity_cost: Mapped[float] = mapped_column(Float, default=0)
    feed_in_revenue: Mapped[float] = mapped_column(Float, default=0)
    storage_charge_kwh: Mapped[float] = mapped_column(Float, default=0)
    storage_discharge_kwh: Mapped[float] = mapped_column(Float, default=0)
    storage_soc_kwh: Mapped[float] = mapped_column(Float, default=0)
    curtailed_pv_kwh: Mapped[float] = mapped_column(Float, default=0)
    energy_balance_error_kwh: Mapped[float] = mapped_column(Float, default=0)
    purchase_price_per_kwh: Mapped[float] = mapped_column(Float, default=0)
    feed_in_tariff_per_kwh: Mapped[float] = mapped_column(Float, default=0)
    grid_emission_factor_kg_per_kwh: Mapped[float] = mapped_column(Float, default=0)
    green_power_kwh: Mapped[float] = mapped_column(Float, default=0)
    green_power_emission_t: Mapped[float] = mapped_column(Float, default=0)
    green_power_carbon_reduction_t: Mapped[float] = mapped_column(Float, default=0)
    ev_charging_load_kwh: Mapped[float] = mapped_column(Float, default=0)
    wind_generation_kwh: Mapped[float] = mapped_column(Float, default=0)
    wind_self_use_kwh: Mapped[float] = mapped_column(Float, default=0)
    wind_export_kwh: Mapped[float] = mapped_column(Float, default=0)
    renewable_generation_kwh: Mapped[float] = mapped_column(Float, default=0)
    renewable_export_kwh: Mapped[float] = mapped_column(Float, default=0)
    curtailed_renewable_kwh: Mapped[float] = mapped_column(Float, default=0)


class WeatherSite(Base):
    __tablename__ = "weather_site"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    enterprise_id: Mapped[int] = mapped_column(ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, default="UTC")
    source: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WeatherTimeseries(Base):
    __tablename__ = "weather_timeseries"
    __table_args__ = (UniqueConstraint("site_id", "timestamp", name="uq_weather_site_ts"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("weather_site.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    temperature_c: Mapped[float] = mapped_column(Float, nullable=False)
    humidity_pct: Mapped[float] = mapped_column(Float, nullable=False)
    ghi_w_m2: Mapped[float] = mapped_column(Float, nullable=False)
    dni_w_m2: Mapped[float | None] = mapped_column(Float)
    dhi_w_m2: Mapped[float | None] = mapped_column(Float)
    wind_speed_m_s: Mapped[float | None] = mapped_column(Float)
    cloud_cover_pct: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String(300))


class ElectricityPriceTimeseries(Base):
    __tablename__ = "electricity_price_timeseries"
    __table_args__ = (UniqueConstraint("enterprise_id", "timestamp", name="uq_enterprise_price_ts"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    enterprise_id: Mapped[int] = mapped_column(ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    purchase_price_per_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    feed_in_tariff_per_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    source: Mapped[str | None] = mapped_column(String(300))


class GridEmissionFactorTimeseries(Base):
    __tablename__ = "grid_emission_factor_timeseries"
    __table_args__ = (UniqueConstraint("region", "timestamp", "version", name="uq_grid_factor_ts"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    region: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    factor_kg_per_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str | None] = mapped_column(String(300))
    version: Mapped[str] = mapped_column(String(80), nullable=False)


class GreenPowerContract(Base):
    __tablename__ = "green_power_contract"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    enterprise_id: Mapped[int] = mapped_column(ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    purchase_kwh: Mapped[float | None] = mapped_column(Float)
    purchase_share: Mapped[float | None] = mapped_column(Float)
    emission_factor_kg_per_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    premium_per_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")
    source: Mapped[str | None] = mapped_column(String(300))


class DataSource(Base):
    __tablename__ = "data_source"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    enterprise_id: Mapped[int] = mapped_column(ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("site.id", ondelete="RESTRICT"), index=True)
    building_id: Mapped[int | None] = mapped_column(ForeignKey("building.id", ondelete="RESTRICT"), index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("device.id", ondelete="RESTRICT", use_alter=True, name="fk_data_source_device"), index=True)
    metering_point_id: Mapped[int | None] = mapped_column(ForeignKey("metering_point.id", ondelete="RESTRICT", use_alter=True, name="fk_data_source_metering_point"), index=True)
    data_nature: Mapped[str | None] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    credentials_encrypted: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")
    collection_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="MANUAL")
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interval_minutes: Mapped[int | None] = mapped_column(Integer)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DataSourceRuntimeState(Base):
    __tablename__ = "data_source_runtime_state"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer,"sqlite"),primary_key=True,autoincrement=True)
    data_source_id: Mapped[int] = mapped_column(ForeignKey("data_source.id",ondelete="CASCADE"),nullable=False,unique=True,index=True)
    runtime_status: Mapped[str] = mapped_column(String(30),nullable=False,default="STOPPED")
    connected: Mapped[bool] = mapped_column(Boolean,nullable=False,default=False)
    subscribed: Mapped[bool] = mapped_column(Boolean,nullable=False,default=False)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_disconnected_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_received_count: Mapped[int] = mapped_column(Integer,nullable=False,default=0)
    last_persisted_count: Mapped[int] = mapped_column(Integer,nullable=False,default=0)
    last_rejected_count: Mapped[int] = mapped_column(Integer,nullable=False,default=0)
    received_count: Mapped[int] = mapped_column(BigInteger,nullable=False,default=0)
    persisted_count: Mapped[int] = mapped_column(BigInteger,nullable=False,default=0)
    rejected_count: Mapped[int] = mapped_column(BigInteger,nullable=False,default=0)
    dropped_count: Mapped[int] = mapped_column(BigInteger,nullable=False,default=0)
    reconnect_count: Mapped[int] = mapped_column(Integer,nullable=False,default=0)
    consecutive_failures: Mapped[int] = mapped_column(Integer,nullable=False,default=0)
    current_topic: Mapped[str | None] = mapped_column(String(500))
    last_error: Mapped[str | None] = mapped_column(Text)
    last_success_watermark: Mapped[datetime | None] = mapped_column(DateTime)
    current_window_start: Mapped[datetime | None] = mapped_column(DateTime)
    current_window_end: Mapped[datetime | None] = mapped_column(DateTime)
    requested_pages: Mapped[int] = mapped_column(Integer,nullable=False,default=0)
    successful_pages: Mapped[int] = mapped_column(Integer,nullable=False,default=0)
    failed_page: Mapped[int | None] = mapped_column(Integer)
    pages_fetched: Mapped[int] = mapped_column(Integer,nullable=False,default=0)
    records_fetched: Mapped[int] = mapped_column(Integer,nullable=False,default=0)
    duplicates_skipped: Mapped[int] = mapped_column(Integer,nullable=False,default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class ExternalRecordDedup(Base):
    __tablename__="external_record_dedup"
    __table_args__=(UniqueConstraint("data_source_id","source_record_id","metric_name",name="uq_external_record_metric"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer,"sqlite"),primary_key=True,autoincrement=True)
    data_source_id: Mapped[int] = mapped_column(ForeignKey("data_source.id",ondelete="CASCADE"),nullable=False,index=True)
    source_record_id: Mapped[str] = mapped_column(String(500),nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100),nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime,nullable=False,default=datetime.utcnow)


class Device(Base):
    __tablename__ = "device"
    __table_args__ = (UniqueConstraint("enterprise_id", "external_id", name="uq_device_external"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    enterprise_id: Mapped[int] = mapped_column(ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False, index=True)
    data_source_id: Mapped[int | None] = mapped_column(ForeignKey("data_source.id", ondelete="SET NULL"), index=True)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    device_type: Mapped[str] = mapped_column(String(50), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    longitude: Mapped[float | None] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)
    position_json: Mapped[dict | None] = mapped_column(JSON)
    geometry_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DeviceMetric(Base):
    __tablename__ = "device_metric"
    __table_args__ = (UniqueConstraint("device_id", "timestamp", "metric_name", name="uq_device_metric_ts"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("device.id", ondelete="CASCADE"), nullable=False, index=True)
    data_source_id: Mapped[int] = mapped_column(ForeignKey("data_source.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    quality: Mapped[str] = mapped_column(String(30), nullable=False, default="VALID")
    raw_json: Mapped[dict | None] = mapped_column(JSON)


class DataValidationLog(Base):
    __tablename__ = "data_validation_log"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    data_source_id: Mapped[int] = mapped_column(ForeignKey("data_source.id", ondelete="CASCADE"), nullable=False, index=True)
    device_external_id: Mapped[str | None] = mapped_column(String(200))
    timestamp: Mapped[datetime | None] = mapped_column(DateTime)
    level: Mapped[str] = mapped_column(String(10), nullable=False)
    validation_stage: Mapped[str] = mapped_column(String(30), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OrganizationNode(Base):
    __tablename__ = "organization_node"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    enterprise_id: Mapped[int] = mapped_column(ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("organization_node.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    level: Mapped[str] = mapped_column(String(30), nullable=False)
    code: Mapped[str | None] = mapped_column(String(100))
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class CarbonAccountingRun(Base):
    __tablename__ = "carbon_accounting_run"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    enterprise_id: Mapped[int] = mapped_column(ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SUCCESS")
    scopes_json: Mapped[list] = mapped_column(JSON, nullable=False)
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CarbonAccountingResult(Base):
    __tablename__ = "carbon_accounting_result"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("carbon_accounting_run.id", ondelete="CASCADE"), nullable=False, index=True)
    enterprise_id: Mapped[int] = mapped_column(ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_node_id: Mapped[int | None] = mapped_column(ForeignKey("organization_node.id", ondelete="SET NULL"), index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("device.id", ondelete="SET NULL"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    energy_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    activity_value: Mapped[float] = mapped_column(Float, nullable=False)
    activity_unit: Mapped[str] = mapped_column(String(30), nullable=False)
    original_activity_value: Mapped[float] = mapped_column(Float, nullable=False)
    original_activity_unit: Mapped[str] = mapped_column(String(30), nullable=False)
    emission_factor: Mapped[float] = mapped_column(Float, nullable=False)
    factor_unit: Mapped[str] = mapped_column(String(50), nullable=False)
    factor_source: Mapped[str | None] = mapped_column(String(500))
    factor_version: Mapped[str] = mapped_column(String(100), nullable=False)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    standard_basis: Mapped[str] = mapped_column(String(300), nullable=False)
    emission_t: Mapped[float] = mapped_column(Float, nullable=False)
    activity_source: Mapped[str | None] = mapped_column(String(300))


class PathRecommendationRun(Base):
    __tablename__ = "path_recommendation_run"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    enterprise_id: Mapped[int] = mapped_column(ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False, index=True)
    simulation_year: Mapped[int] = mapped_column(Integer, nullable=False)
    input_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    baseline_summary_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PathRecommendation(Base):
    __tablename__ = "path_recommendation"
    __table_args__ = (UniqueConstraint("run_id", "profile", "rank", name="uq_recommendation_rank"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("path_recommendation_run.id", ondelete="CASCADE"), nullable=False, index=True)
    profile: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    measures_json: Mapped[list] = mapped_column(JSON, nullable=False)
    reasons_json: Mapped[list] = mapped_column(JSON, nullable=False)
    metrics_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    validation_summary_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class ScenarioVersion(Base):
    __tablename__ = "scenario_version"
    __table_args__ = (UniqueConstraint("scenario_id", "version_number", name="uq_scenario_version"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenario.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(30), nullable=False)
    parameter_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    carbon_market_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    risk_parameter_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    source_recommendation_id: Mapped[int | None] = mapped_column(ForeignKey("path_recommendation.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SimulationBatch(Base):
    __tablename__ = "simulation_batch"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    enterprise_id: Mapped[int] = mapped_column(ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False, index=True)
    baseline_scenario_version_id: Mapped[int] = mapped_column(ForeignKey("scenario_version.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="RUNNING")
    request_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    comparison_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class SimulationBatchItem(Base):
    __tablename__ = "simulation_batch_item"
    __table_args__ = (UniqueConstraint("batch_id", "scenario_version_id", name="uq_batch_version"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("simulation_batch.id", ondelete="CASCADE"), nullable=False, index=True)
    scenario_version_id: Mapped[int] = mapped_column(ForeignKey("scenario_version.id", ondelete="RESTRICT"), nullable=False)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("simulation_task.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    metrics_json: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)


class CarbonMarketScenario(Base):
    __tablename__ = "carbon_market_scenario"
    __table_args__ = (UniqueConstraint("scenario_version_id", name="uq_market_scenario_version"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    scenario_version_id: Mapped[int] = mapped_column(ForeignKey("scenario_version.id", ondelete="CASCADE"), nullable=False, index=True)
    carbon_price_per_t: Mapped[float] = mapped_column(Float, nullable=False)
    carbon_quota_t: Mapped[float] = mapped_column(Float, nullable=False)
    ccer_quantity_t: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    ccer_price_per_t: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    green_certificate_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    green_certificate_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CarbonMarketTimeseries(Base):
    __tablename__ = "carbon_market_timeseries"
    __table_args__ = (UniqueConstraint("region", "timestamp", "source", name="uq_market_indicator"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    region: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    carbon_price_per_t: Mapped[float | None] = mapped_column(Float)
    carbon_quota_t: Mapped[float | None] = mapped_column(Float)
    trading_volume_t: Mapped[float | None] = mapped_column(Float)
    trading_amount_yuan: Mapped[float | None] = mapped_column(Float)
    ccer_volume_t: Mapped[float | None] = mapped_column(Float)
    ccer_price_per_t: Mapped[float | None] = mapped_column(Float)
    ccer_trading_amount_yuan: Mapped[float | None] = mapped_column(Float)
    green_certificate_volume: Mapped[float | None] = mapped_column(Float)
    green_certificate_price: Mapped[float | None] = mapped_column(Float)
    green_certificate_issued_count: Mapped[float | None] = mapped_column(Float)
    green_certificate_traded_count: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(300), nullable=False)


class CarbonCostAssessment(Base):
    __tablename__ = "carbon_cost_assessment"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    scenario_version_id: Mapped[int] = mapped_column(ForeignKey("scenario_version.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("simulation_task.id", ondelete="RESTRICT"), nullable=False, index=True)
    gross_emission_t: Mapped[float] = mapped_column(Float, nullable=False)
    input_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RiskAssessmentRun(Base):
    __tablename__ = "risk_assessment_run"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    scenario_version_id: Mapped[int] = mapped_column(ForeignKey("scenario_version.id", ondelete="RESTRICT"), nullable=False, index=True)
    simulation_task_id: Mapped[int] = mapped_column(ForeignKey("simulation_task.id", ondelete="RESTRICT"), nullable=False, index=True)
    batch_item_id: Mapped[int | None] = mapped_column(ForeignKey("simulation_batch_item.id", ondelete="SET NULL"))
    input_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    overall_level: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class RiskAssessmentResult(Base):
    __tablename__ = "risk_assessment_result"
    __table_args__ = (UniqueConstraint("run_id", "risk_category", name="uq_risk_run_category"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("risk_assessment_run.id", ondelete="CASCADE"), nullable=False, index=True)
    risk_category: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    indicator_value_json: Mapped[dict | float | None] = mapped_column(JSON)
    trigger_reason: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)

class ReportTask(Base):
    __tablename__ = "report_task"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    enterprise_id: Mapped[int] = mapped_column(ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False, index=True)
    scenario_version_id: Mapped[int] = mapped_column(ForeignKey("scenario_version.id", ondelete="RESTRICT"), nullable=False, index=True)
    simulation_task_id: Mapped[int] = mapped_column(ForeignKey("simulation_task.id", ondelete="RESTRICT"), nullable=False, index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("simulation_batch.id", ondelete="SET NULL"))
    accounting_run_id: Mapped[int | None] = mapped_column(ForeignKey("carbon_accounting_run.id", ondelete="SET NULL"))
    recommendation_run_id: Mapped[int | None] = mapped_column(ForeignKey("path_recommendation_run.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SUCCESS")
    failure_reason: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ReportSnapshot(Base):
    __tablename__ = "report_snapshot"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    report_task_id: Mapped[int] = mapped_column(ForeignKey("report_task.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    scenario_version_id: Mapped[int] = mapped_column(ForeignKey("scenario_version.id", ondelete="RESTRICT"), nullable=False, index=True)
    simulation_task_id: Mapped[int] = mapped_column(ForeignKey("simulation_task.id", ondelete="RESTRICT"), nullable=False, index=True)
    input_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    report_data_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ReportFile(Base):
    __tablename__ = "report_file"
    __table_args__ = (UniqueConstraint("report_task_id","format",name="uq_report_file_format"),)
    id:Mapped[int]=mapped_column(BigInteger().with_variant(Integer,"sqlite"),primary_key=True,autoincrement=True)
    report_task_id:Mapped[int]=mapped_column(ForeignKey("report_task.id",ondelete="CASCADE"),nullable=False,index=True)
    format:Mapped[str]=mapped_column(String(10),nullable=False)
    file_name:Mapped[str]=mapped_column(String(500),nullable=False)
    storage_path:Mapped[str]=mapped_column(String(1000),nullable=False)
    file_size:Mapped[int]=mapped_column(BigInteger,nullable=False)
    checksum:Mapped[str]=mapped_column(String(64),nullable=False)
    generated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class Site(Base):
    __tablename__ = "site"
    __table_args__ = (UniqueConstraint("enterprise_id","code",name="uq_site_enterprise_code"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer,"sqlite"),primary_key=True,autoincrement=True)
    enterprise_id: Mapped[int] = mapped_column(ForeignKey("enterprise.id",ondelete="RESTRICT"),nullable=False,index=True)
    organization_node_id: Mapped[int|None] = mapped_column(ForeignKey("organization_node.id",ondelete="SET NULL"),index=True)
    code: Mapped[str] = mapped_column(String(100),nullable=False)
    name: Mapped[str] = mapped_column(String(200),nullable=False)
    site_type: Mapped[str] = mapped_column(String(40),nullable=False,index=True)
    address: Mapped[str|None] = mapped_column(String(500));area_m2: Mapped[float|None]=mapped_column(Float);population:Mapped[int|None]=mapped_column(Integer)
    timezone:Mapped[str]=mapped_column(String(100),nullable=False,default="Asia/Shanghai");status:Mapped[str]=mapped_column(String(30),nullable=False,default="ACTIVE");metadata_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    longitude:Mapped[float|None]=mapped_column(Float);latitude:Mapped[float|None]=mapped_column(Float);position_json:Mapped[dict|None]=mapped_column(JSON);geometry_json:Mapped[dict|None]=mapped_column(JSON)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow);updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class Building(Base):
    __tablename__="building";__table_args__=(UniqueConstraint("site_id","code",name="uq_building_site_code"),)
    id:Mapped[int]=mapped_column(BigInteger().with_variant(Integer,"sqlite"),primary_key=True,autoincrement=True);site_id:Mapped[int]=mapped_column(ForeignKey("site.id",ondelete="RESTRICT"),nullable=False,index=True);organization_node_id:Mapped[int|None]=mapped_column(ForeignKey("organization_node.id",ondelete="SET NULL"),index=True)
    code:Mapped[str]=mapped_column(String(100),nullable=False);name:Mapped[str]=mapped_column(String(200),nullable=False);building_type:Mapped[str]=mapped_column(String(50),nullable=False);area_m2:Mapped[float|None]=mapped_column(Float);floor_count:Mapped[int|None]=mapped_column(Integer);population:Mapped[int|None]=mapped_column(Integer);status:Mapped[str]=mapped_column(String(30),nullable=False,default="ACTIVE");metadata_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    longitude:Mapped[float|None]=mapped_column(Float);latitude:Mapped[float|None]=mapped_column(Float);position_json:Mapped[dict|None]=mapped_column(JSON);geometry_json:Mapped[dict|None]=mapped_column(JSON);created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow);updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class EnergySystem(Base):
    __tablename__="energy_system";__table_args__=(UniqueConstraint("site_id","code",name="uq_energy_system_site_code"),)
    id:Mapped[int]=mapped_column(BigInteger().with_variant(Integer,"sqlite"),primary_key=True,autoincrement=True);site_id:Mapped[int]=mapped_column(ForeignKey("site.id",ondelete="RESTRICT"),nullable=False,index=True);building_id:Mapped[int|None]=mapped_column(ForeignKey("building.id",ondelete="SET NULL"),index=True);code:Mapped[str]=mapped_column(String(100),nullable=False);name:Mapped[str]=mapped_column(String(200),nullable=False);system_type:Mapped[str]=mapped_column(String(40),nullable=False,index=True);status:Mapped[str]=mapped_column(String(30),nullable=False,default="ACTIVE");metadata_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict);created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow);updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class MeteringPoint(Base):
    __tablename__="metering_point";__table_args__=(UniqueConstraint("site_id","code",name="uq_metering_point_site_code"),)
    id:Mapped[int]=mapped_column(BigInteger().with_variant(Integer,"sqlite"),primary_key=True,autoincrement=True);site_id:Mapped[int]=mapped_column(ForeignKey("site.id",ondelete="RESTRICT"),nullable=False,index=True);building_id:Mapped[int|None]=mapped_column(ForeignKey("building.id",ondelete="SET NULL"),index=True);energy_system_id:Mapped[int|None]=mapped_column(ForeignKey("energy_system.id",ondelete="SET NULL"),index=True);device_id:Mapped[int|None]=mapped_column(ForeignKey("device.id",ondelete="RESTRICT"),index=True);data_source_id:Mapped[int|None]=mapped_column(ForeignKey("data_source.id",ondelete="RESTRICT"),index=True);code:Mapped[str]=mapped_column(String(100),nullable=False);name:Mapped[str]=mapped_column(String(200),nullable=False);metric_type:Mapped[str]=mapped_column(String(100),nullable=False,index=True);energy_type:Mapped[str]=mapped_column(String(50),nullable=False,index=True);unit:Mapped[str]=mapped_column(String(30),nullable=False);status:Mapped[str]=mapped_column(String(30),nullable=False,default="ACTIVE");metadata_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict);created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow);updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class CameraSpatialMapping(Base):
    """GIS anchor for an upstream camera; it does not store or infer person tracks."""
    __tablename__="camera_spatial_mapping"
    __table_args__=(UniqueConstraint("campus_id","camera_id",name="uq_camera_spatial_campus_camera"),)
    id:Mapped[int]=mapped_column(BigInteger().with_variant(Integer,"sqlite"),primary_key=True,autoincrement=True)
    site_id:Mapped[int]=mapped_column(ForeignKey("site.id",ondelete="RESTRICT"),nullable=False,index=True)
    building_id:Mapped[int|None]=mapped_column(ForeignKey("building.id",ondelete="RESTRICT"),index=True)
    campus_id:Mapped[str]=mapped_column(String(100),nullable=False,index=True)
    camera_id:Mapped[str]=mapped_column(String(200),nullable=False,index=True)
    floor_id:Mapped[str|None]=mapped_column(String(200),index=True)
    area_id:Mapped[str|None]=mapped_column(String(200),index=True)
    longitude:Mapped[float]=mapped_column(Float,nullable=False)
    latitude:Mapped[float]=mapped_column(Float,nullable=False)
    anchor_source:Mapped[str]=mapped_column(String(50),nullable=False,default="CAMERA_LOCATION")
    status:Mapped[str]=mapped_column(String(30),nullable=False,default="ACTIVE")
    metadata_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
