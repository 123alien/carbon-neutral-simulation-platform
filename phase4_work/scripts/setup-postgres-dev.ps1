$ErrorActionPreference = 'Stop'

$containerName = 'carbon-neutral-postgres'
$volumeName = 'carbon_neutral_pgdata'
$databaseName = 'carbon_neutral_dev'
$databaseUser = 'carbon_app'
$existingUrl = [Environment]::GetEnvironmentVariable('DEV_DATABASE_URL', 'User')
$containerExists = docker inspect $containerName 2>$null

if ($LASTEXITCODE -ne 0) {
    $randomBytes = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Fill($randomBytes)
    $databasePassword = [Convert]::ToBase64String($randomBytes).Replace('+', 'A').Replace('/', 'B').TrimEnd('=')
    $databaseUrl = "postgresql+psycopg://${databaseUser}:${databasePassword}@127.0.0.1:5432/${databaseName}"
    docker volume create $volumeName | Out-Null
    docker run -d --name $containerName --restart unless-stopped `
        -p 127.0.0.1:5432:5432 `
        -e POSTGRES_USER=$databaseUser `
        -e POSTGRES_PASSWORD=$databasePassword `
        -e POSTGRES_DB=$databaseName `
        -v "${volumeName}:/var/lib/postgresql/data" `
        postgres:17-alpine | Out-Null
    [Environment]::SetEnvironmentVariable('DEV_DATABASE_URL', $databaseUrl, 'User')
    $existingUrl = $databaseUrl
    Write-Host 'Created local PostgreSQL with a persistent volume. The generated connection secret was stored in the Windows user environment and was not printed.'
} elseif (-not $existingUrl) {
    throw 'The PostgreSQL container exists but DEV_DATABASE_URL is missing. Restore the matching credential instead of resetting the database.'
} else {
    $status = docker inspect -f '{{.State.Status}}' $containerName
    if ($status -ne 'running') { docker start $containerName | Out-Null }
}

for ($attempt = 0; $attempt -lt 30; $attempt++) {
    docker exec $containerName pg_isready -U $databaseUser -d $databaseName *> $null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 1
}
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL did not become ready in 30 seconds.' }

$env:APP_ENV = 'development'
$env:DATABASE_URL = $existingUrl
python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Alembic upgrade failed.' }
python -m alembic current

