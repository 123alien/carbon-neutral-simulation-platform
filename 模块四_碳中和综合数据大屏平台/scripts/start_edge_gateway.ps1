$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
foreach ($taskKey in @('EDGE_BOX_BASE_URL', 'EDGE_BOX_USERNAME', 'EDGE_BOX_PASSWORD', 'EDGE_SHARED_ADMIN_ACCESS', 'EDGE_GATEWAY_PORT')) {
    $taskValue = [Environment]::GetEnvironmentVariable($taskKey, 'User')
    if ($taskValue) { [Environment]::SetEnvironmentVariable($taskKey, $taskValue, 'Process') }
}
if ($env:EDGE_SHARED_ADMIN_ACCESS -ne 'true') { throw 'Shared administrator entry is not enabled.' }
$taskPort = if ($env:EDGE_GATEWAY_PORT) { $env:EDGE_GATEWAY_PORT } else { '8210' }
if (Get-NetTCPConnection -LocalPort $taskPort -State Listen -ErrorAction SilentlyContinue) {
    Write-Output "Edge gateway already listening on port $taskPort."
    exit
}
Start-Process -FilePath 'D:\Anaconda3\python.exe' -ArgumentList '-m', 'uvicorn', 'backend.edge_gateway:app', '--host', '0.0.0.0', '--port', $taskPort -WorkingDirectory $taskRoot -WindowStyle Hidden
Write-Output "Edge gateway starting on port $taskPort."
