CREATE TABLE enterprise (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    region VARCHAR(100),
    industry VARCHAR(100),
    building_area NUMERIC(18,4),
    population INTEGER,
    latitude NUMERIC(10,6),
    longitude NUMERIC(10,6),
    base_year INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE energy_history (
    id BIGSERIAL PRIMARY KEY,
    enterprise_id BIGINT NOT NULL REFERENCES enterprise(id),
    year INTEGER NOT NULL,
    month INTEGER,
    energy_type VARCHAR(50) NOT NULL,
    consumption NUMERIC(20,6) NOT NULL,
    unit VARCHAR(30) NOT NULL,
    source VARCHAR(300),
    UNIQUE(enterprise_id, year, month, energy_type)
);

CREATE TABLE emission_factor (
    id BIGSERIAL PRIMARY KEY,
    region VARCHAR(100) NOT NULL,
    year INTEGER NOT NULL,
    energy_type VARCHAR(50) NOT NULL,
    factor NUMERIC(20,10) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    source VARCHAR(500),
    version VARCHAR(80) NOT NULL,
    UNIQUE(region, year, energy_type, version)
);

CREATE TABLE scenario (
    id BIGSERIAL PRIMARY KEY,
    enterprise_id BIGINT NOT NULL REFERENCES enterprise(id),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    base_year INTEGER NOT NULL,
    start_year INTEGER NOT NULL,
    end_year INTEGER NOT NULL,
    target_peak_year INTEGER,
    target_neutral_year INTEGER,
    baseline_growth_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE scenario_measure (
    id BIGSERIAL PRIMARY KEY,
    scenario_id BIGINT NOT NULL REFERENCES scenario(id) ON DELETE CASCADE,
    measure_type VARCHAR(50) NOT NULL,
    start_year INTEGER NOT NULL,
    end_year INTEGER,
    parameters_json JSONB NOT NULL
);

CREATE TABLE simulation_task (
    id BIGSERIAL PRIMARY KEY,
    scenario_id BIGINT NOT NULL REFERENCES scenario(id),
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    parameter_snapshot_json JSONB NOT NULL,
    summary_json JSONB,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    error_message TEXT
);

CREATE TABLE simulation_year_result (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES simulation_task(id) ON DELETE CASCADE,
    scenario_id BIGINT NOT NULL REFERENCES scenario(id),
    year INTEGER NOT NULL,
    electricity_base_kwh NUMERIC(20,6) DEFAULT 0,
    electricity_after_saving_kwh NUMERIC(20,6) DEFAULT 0,
    grid_power_kwh NUMERIC(20,6) DEFAULT 0,
    natural_gas_m3 NUMERIC(20,6) DEFAULT 0,
    coal_kg NUMERIC(20,6) DEFAULT 0,
    oil_kg NUMERIC(20,6) DEFAULT 0,
    pv_generation_kwh NUMERIC(20,6) DEFAULT 0,
    pv_self_use_kwh NUMERIC(20,6) DEFAULT 0,
    pv_export_kwh NUMERIC(20,6) DEFAULT 0,
    energy_saved_kwh NUMERIC(20,6) DEFAULT 0,
    carbon_emission_t NUMERIC(20,6) DEFAULT 0,
    carbon_reduction_t NUMERIC(20,6) DEFAULT 0,
    investment NUMERIC(20,2) DEFAULT 0,
    annual_benefit NUMERIC(20,2) DEFAULT 0,
    UNIQUE(task_id, year)
);
