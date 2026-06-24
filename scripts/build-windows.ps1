param(
    [string]$Target = "x86_64-pc-windows-msvc"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Sidecars = Join-Path $Frontend "sidecars"
$BackendExe = "netpanel-backend-$Target.exe"

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
    if ($LASTEXITCODE -ne 0) { throw "Python dependencies installation failed" }
    $PyInstallerArgs = @(
        "entrypoint.py",
        "--name", "netpanel-backend",
        "--onefile",
        "--noconsole",
        "--clean",
        "--noconfirm",
        "--distpath", "dist",
        "--workpath", "build"
    )
    .\.venv\Scripts\python.exe -m PyInstaller @PyInstallerArgs
    if ($LASTEXITCODE -ne 0) { throw "Backend build failed" }
    Copy-Item -Force (Join-Path $Backend "dist\netpanel-backend.exe") (Join-Path $Sidecars $BackendExe)
}
finally {
    Pop-Location
}

Push-Location $Frontend
try {
    npm install
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependencies installation failed" }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
    cargo build --release --features custom-protocol --manifest-path src-tauri\Cargo.toml
    if ($LASTEXITCODE -ne 0) { throw "Tauri build failed" }
}
finally {
    Pop-Location
}

$Version = (Get-Content (Join-Path $Frontend "package.json") | ConvertFrom-Json).version
$Release = Join-Path $Frontend "src-tauri\target\release"
$PortableName = "Netpanel Portable $Version"
$Portable = Join-Path $Release $PortableName
$Archive = Join-Path $Release "$PortableName.zip"

if (Test-Path $Portable) {
    Remove-Item -LiteralPath $Portable -Recurse -Force
}
if (Test-Path $Archive) {
    Remove-Item -LiteralPath $Archive -Force
}

New-Item -ItemType Directory -Path $Portable | Out-Null
Copy-Item -LiteralPath (Join-Path $Release "netpanel.exe") -Destination (Join-Path $Portable "Netpanel.exe")
Copy-Item -LiteralPath (Join-Path $Backend "dist\netpanel-backend.exe") -Destination $Portable
Compress-Archive -LiteralPath $Portable -DestinationPath $Archive -CompressionLevel Optimal

Write-Host "Portable artifact:"
Write-Host "  $Archive"
