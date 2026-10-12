$ErrorActionPreference = 'Stop'
$env:APP_ENV = 'development'
$databaseUrl = $env:DEV_DATABASE_URL
if (-not $databaseUrl) {
    $databaseUrl = [Environment]::GetEnvironmentVariable('DEV_DATABASE_URL', 'User')
}
if (-not $databaseUrl) {
    throw 'DEV_DATABASE_URL is required. Configure the local PostgreSQL carbon_neutral_dev connection first.'
}
if ($databaseUrl -notmatch '^postgresql\+psycopg://') {
    throw 'Development must use PostgreSQL through postgresql+psycopg://; SQLite is reserved for automated tests.'
}
$env:DATABASE_URL = $databaseUrl

$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker) {
    $containerStatus = docker inspect -f '{{.State.Status}}' carbon-neutral-postgres 2>$null
    if ($LASTEXITCODE -eq 0 -and $containerStatus -ne 'running') {
        docker start carbon-neutral-postgres | Out-Null
    }
}
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
