param(
    [string]$Target = "x86_64-pc-windows-msvc"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Sidecars = Join-Path $Frontend "sidecars"
$BackendExe = "cisco-backend-$Target.exe"

New-Item -ItemType Directory -Force -Path $Sidecars | Out-Null

if (-not (Test-Path (Join-Path $Backend ".venv\Scripts\python.exe"))) {
    Push-Location $Backend
    try {
        python -m venv .venv
    }
    finally {
        Pop-Location
    }
}

Push-Location $Backend
try {
    .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
    $PyInstallerArgs = @(
        "entrypoint.py",
        "--name", "cisco-backend",
        "--onefile",
        "--noconsole",
        "--clean",
        "--noconfirm",
        "--distpath", "dist",
        "--workpath", "build"
    )
    .\.venv\Scripts\python.exe -m PyInstaller @PyInstallerArgs
    Copy-Item -Force (Join-Path $Backend "dist\cisco-backend.exe") (Join-Path $Sidecars $BackendExe)
}
finally {
    Pop-Location
}

Push-Location $Frontend
try {
    npm install
    npm run tauri build
}
finally {
    Pop-Location
}

Write-Host "Windows artifacts:"
Write-Host "  $Frontend\src-tauri\target\release"
Write-Host "  $Frontend\src-tauri\target\release\bundle"
