# Codex Handoff - Carbon Neutrality Simulation Platform V1

## Mission
Continue development from V0.4.0. Do not rewrite the working annual/hourly simulation engines unless a failing test or explicit requirement justifies it.

## Current verified baseline
- `pytest -q` passes all tests.
- Annual simulation: baseline growth -> measures -> energy balance -> carbon -> economics -> peak/neutrality.
- Hourly simulation: load profile -> HVAC/lighting saving -> PV -> grid balance -> carbon/electricity economics.
- SQLite is for developer/test use. PostgreSQL is the production target.

## First commands
```bash
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --reload
```
Open `http://127.0.0.1:8000/docs`.

## Required development order
1. Add Alembic and migrate `001_init.sql`, `002_phase3.sql`, `003_phase4_hourly.sql` into versioned migrations.
2. Implement CSV/Excel hourly data import with validation, timezone, interval consistency, duplicate handling and missing-value report.
3. Add hourly result aggregation endpoints: day/month/year and chart-friendly series.
4. Add weather/irradiance provider abstraction; keep imported irradiance as highest priority.
5. Add storage model (SOC, charge/discharge limits, efficiency, capacity) as a measure plugin.
6. Add green power / purchased renewable electricity model.
7. Add scenario clone/update/delete/versioning and parameter snapshot reproducibility.
8. Add async simulation task execution for large 8760/multi-scenario runs.
9. Build Vue3 + Element Plus + ECharts frontend.
10. Add report generation only after result APIs are stable.

## Hard rules
- Target peak/neutral year is a target, never force simulation results to equal it.
- Never add reductions by simple sum if measures affect the same electricity balance; always apply load-saving before PV/storage balance.
- Emission factors must have region/year/source/version/unit and must be resolved through service code; no hard-coded production factor.
- Store task parameter snapshots and keep results reproducible.
- Canonical energy units are enforced at service boundaries.
- Any new measure must implement the measure abstraction and unit tests.
- Keep annual and hourly modes both available. Annual is for long horizon; hourly is for energy-balance fidelity.

## Acceptance gate for each PR
- `pytest -q` passes.
- API schema remains backward compatible or migration note is provided.
- New algorithm has unit tests and at least one end-to-end API test.
- No negative grid import/export/energy values caused by arithmetic.
- Error cases return 4xx, not 500, for user input problems.
- Database migration included for schema changes.

See the Word development manual delivered with this package for full specifications.
