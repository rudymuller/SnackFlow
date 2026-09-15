$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

& $python -m PyInstaller --noconfirm --clean --onedir --windowed `
    --name SnackFlow --paths src src\Main.py

$dataTarget = Join-Path $PSScriptRoot "dist\SnackFlow\data"
New-Item -ItemType Directory -Force -Path $dataTarget | Out-Null
$database = Join-Path $PSScriptRoot "data\SysDB.db"
if (Test-Path $database) {
    Copy-Item $database (Join-Path $dataTarget "SysDB.db") -Force
}

Write-Host "Executavel criado em: dist\SnackFlow\SnackFlow.exe"