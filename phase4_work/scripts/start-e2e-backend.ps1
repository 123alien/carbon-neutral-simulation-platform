$ErrorActionPreference = 'Stop'
$env:APP_ENV = 'e2e'
$env:DATABASE_URL = 'sqlite:///./frontend_smoke.db'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
