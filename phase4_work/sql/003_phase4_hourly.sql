CREATE TABLE IF NOT EXISTS load_timeseries (
    id BIGSERIAL PRIMARY KEY,
    enterprise_id BIGINT NOT NULL REFERENCES enterprise(id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL,
    load_kwh DOUBLE PRECISION NOT NULL CHECK (load_kwh >= 0),
    irradiation_wm2 DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (irradiation_wm2 >= 0),
    temperature_c DOUBLE PRECISION,
    humidity_pct DOUBLE PRECISION,
    source VARCHAR(300),
    CONSTRAINT uq_enterprise_load_ts UNIQUE (enterprise_id, timestamp)
);
CREATE INDEX IF NOT EXISTS ix_load_timeseries_enterprise ON load_timeseries(enterprise_id);
CREATE INDEX IF NOT EXISTS ix_load_timeseries_timestamp ON load_timeseries(timestamp);

CREATE TABLE IF NOT EXISTS simulation_hour_result (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES simulation_task(id) ON DELETE CASCADE,
    scenario_id BIGINT NOT NULL REFERENCES scenario(id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL,
    load_base_kwh DOUBLE PRECISION NOT NULL DEFAULT 0,
    hvac_saved_kwh DOUBLE PRECISION NOT NULL DEFAULT 0,
    lighting_saved_kwh DOUBLE PRECISION NOT NULL DEFAULT 0,
    load_after_saving_kwh DOUBLE PRECISION NOT NULL DEFAULT 0,
    pv_generation_kwh DOUBLE PRECISION NOT NULL DEFAULT 0,
    pv_self_use_kwh DOUBLE PRECISION NOT NULL DEFAULT 0,
    pv_export_kwh DOUBLE PRECISION NOT NULL DEFAULT 0,
    grid_power_kwh DOUBLE PRECISION NOT NULL DEFAULT 0,
    carbon_emission_t DOUBLE PRECISION NOT NULL DEFAULT 0,
    electricity_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
    feed_in_revenue DOUBLE PRECISION NOT NULL DEFAULT 0,
    CONSTRAINT uq_task_hour UNIQUE (task_id, timestamp)
);
CREATE INDEX IF NOT EXISTS ix_sim_hour_task ON simulation_hour_result(task_id);
CREATE INDEX IF NOT EXISTS ix_sim_hour_timestamp ON simulation_hour_result(timestamp);
