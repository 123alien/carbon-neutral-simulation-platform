-- V0.3 migration: canonical physical fuel units.
ALTER TABLE simulation_year_result RENAME COLUMN natural_gas_kwh TO natural_gas_m3;
ALTER TABLE simulation_year_result ADD COLUMN coal_kg NUMERIC(20,6) DEFAULT 0;
ALTER TABLE simulation_year_result ADD COLUMN oil_kg NUMERIC(20,6) DEFAULT 0;
