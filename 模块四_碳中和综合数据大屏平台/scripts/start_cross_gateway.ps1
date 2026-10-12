$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
foreach ($taskKey in @('CROSS_CAMERA_BASE_URL', 'CROSS_CAMERA_USERNAME', 'CROSS_CAMERA_PASSWORD', 'CROSS_SHARED_ADMIN_ACCESS', 'CROSS_GATEWAY_PORT')) {
    $taskValue = [Environment]::GetEnvironmentVariable($taskKey, 'User')
    if ($taskValue) { [Environment]::SetEnvironmentVariable($taskKey, $taskValue, 'Process') }
}
if ($env:CROSS_SHARED_ADMIN_ACCESS -ne 'true') { throw 'Shared cross-camera entry is not enabled.' }
$taskPort = if ($env:CROSS_GATEWAY_PORT) { $env:CROSS_GATEWAY_PORT } else { '8220' }
if (Get-NetTCPConnection -LocalPort $taskPort -State Listen -ErrorAction SilentlyContinue) {
    Write-Output "Cross-camera gateway already listening on port $taskPort."
    exit
}
Start-Process -FilePath 'D:\Anaconda3\python.exe' -ArgumentList '-m', 'uvicorn', 'backend.cross_gateway:app', '--host', '0.0.0.0', '--port', $taskPort -WorkingDirectory $taskRoot -WindowStyle Hidden
Write-Output "Cross-camera gateway starting on port $taskPort."
