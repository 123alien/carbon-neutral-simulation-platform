$ErrorActionPreference = 'Stop'
$env:APP_ENV = 'test'
$env:DATABASE_URL = 'sqlite:///./test_carbon_sim.db'
python -m pytest -q
