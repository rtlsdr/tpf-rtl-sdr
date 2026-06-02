# setup.ps1
# Setup inicial para usar el analizador RTL-SDR con Docker + WSL2.
# Ejecutar desde PowerShell como administrador, dentro de la carpeta del proyecto.

Write-Host ""
Write-Host "=== Setup inicial RTL-SDR + Docker ===" -ForegroundColor Cyan
Write-Host ""

# Verificar administrador
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: ejecutar este script desde PowerShell como administrador." -ForegroundColor Red
    exit 1
}

# Verificar carpeta del proyecto
if (-not (Test-Path ".\Dockerfile") -or -not (Test-Path ".\docker-compose.yml") -or -not (Test-Path ".\app\main.py")) {
    Write-Host "ERROR: ejecutar setup.ps1 desde la carpeta raiz del proyecto." -ForegroundColor Red
    Write-Host "La carpeta debe contener Dockerfile, docker-compose.yml y app\main.py."
    exit 1
}

# Verificar winget
Write-Host "[1/8] Verificando winget..." -ForegroundColor Cyan
winget --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: winget no esta disponible. Instalar App Installer desde Microsoft Store." -ForegroundColor Red
    exit 1
}
Write-Host "winget OK" -ForegroundColor Green

# Verificar Docker Desktop
Write-Host "[2/8] Verificando Docker Desktop..." -ForegroundColor Cyan
docker --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop no parece estar instalado." -ForegroundColor Red
    Write-Host "Instalar Docker Desktop, abrirlo y ejecutar setup.ps1 nuevamente."
    exit 1
}
Write-Host "Docker CLI detectado." -ForegroundColor Green

docker info | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop esta instalado pero no esta corriendo." -ForegroundColor Red
    Write-Host "Abrir Docker Desktop y ejecutar setup.ps1 nuevamente."
    exit 1
}
Write-Host "Docker Desktop esta corriendo." -ForegroundColor Green

# Verificar WSL
Write-Host "[3/8] Verificando WSL..." -ForegroundColor Cyan

$wslListRaw = wsl -l -q 2>$null
$wslNames = @()

foreach ($line in $wslListRaw) {
    $clean = ($line -replace "`0", "").Trim()
    if ($clean.Length -gt 0) {
        $wslNames += $clean
    }
}

if ($wslNames -contains "Ubuntu") {
    Write-Host "Ubuntu ya existe en WSL. Se omite instalacion." -ForegroundColor Green
} else {
    Write-Host "Ubuntu no existe. Instalando Ubuntu en WSL..." -ForegroundColor Yellow
    wsl --install -d Ubuntu

    Write-Host ""
    Write-Host "Si Ubuntu se abrio para crear usuario y password, completar ese paso." -ForegroundColor Yellow
    Write-Host "Luego ejecutar setup.ps1 nuevamente." -ForegroundColor Yellow
    exit 0
}

# Verificar version de WSL
Write-Host "[4/8] Verificando version de Ubuntu en WSL..." -ForegroundColor Cyan
$wslVerbose = wsl -l -v
Write-Host $wslVerbose

$ubuntuLine = $wslVerbose | Select-String -Pattern "Ubuntu"
if ($ubuntuLine -and ($ubuntuLine.Line -notmatch "\s2\s*$")) {
    Write-Host "Ubuntu no parece estar en WSL2. Convirtiendo..." -ForegroundColor Yellow
    wsl --set-version Ubuntu 2
}

# Actualizar WSL
Write-Host "[5/8] Verificando actualizacion de WSL..." -ForegroundColor Cyan
wsl --update
if ($LASTEXITCODE -ne 0) {
    Write-Host "Advertencia: wsl --update no termino correctamente. Se continua igual." -ForegroundColor Yellow
}

# Verificar usbipd-win
Write-Host "[6/8] Verificando usbipd-win..." -ForegroundColor Cyan
usbipd --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "usbipd-win no detectado. Instalando..." -ForegroundColor Yellow
    winget install --interactive --exact dorssel.usbipd-win

    Write-Host ""
    Write-Host "Si la instalacion de usbipd-win pidio reiniciar, reiniciar Windows." -ForegroundColor Yellow
    Write-Host "Luego ejecutar setup.ps1 nuevamente." -ForegroundColor Yellow
    exit 0
}
Write-Host "usbipd-win detectado." -ForegroundColor Green

# Iniciar Ubuntu
Write-Host "[7/8] Iniciando Ubuntu/WSL y copiando proyecto..." -ForegroundColor Cyan
wsl -d Ubuntu -- echo WSL_OK | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: no se pudo iniciar Ubuntu/WSL." -ForegroundColor Red
    Write-Host "Abrir Ubuntu desde el menu inicio, completar usuario/password si lo pide, y ejecutar setup.ps1 nuevamente."
    exit 1
}

# Verificar Docker dentro de WSL
wsl -d Ubuntu -- bash -lc "docker --version && docker compose version"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Docker no esta disponible dentro de Ubuntu/WSL." -ForegroundColor Red
    Write-Host "Abrir Docker Desktop y verificar:"
    Write-Host "  Settings -> Resources -> WSL Integration -> Ubuntu activado"
    Write-Host "Luego ejecutar setup.ps1 nuevamente."
    exit 1
}

# Obtener usuario WSL
$WslUser = (wsl -d Ubuntu -- bash -lc "whoami").Trim()
if ([string]::IsNullOrWhiteSpace($WslUser)) {
    Write-Host "ERROR: no se pudo detectar el usuario de Ubuntu/WSL." -ForegroundColor Red
    exit 1
}

# Copiar proyecto desde Windows al filesystem Linux de WSL usando UNC
$ProjectWinPath = (Resolve-Path ".").Path

$WslRoot1 = "\\wsl.localhost\Ubuntu\home\$WslUser"
$WslRoot2 = "\\wsl$\Ubuntu\home\$WslUser"

if (Test-Path $WslRoot1) {
    $WslHomeWinPath = $WslRoot1
} elseif (Test-Path $WslRoot2) {
    $WslHomeWinPath = $WslRoot2
} else {
    Write-Host "ERROR: no se pudo acceder al filesystem de Ubuntu desde Windows." -ForegroundColor Red
    Write-Host "Probar abrir en el Explorador: \\wsl.localhost\Ubuntu\home\$WslUser"
    exit 1
}

$DestWinPath = Join-Path $WslHomeWinPath "tpf-rtl-sdr"

Write-Host "Copiando proyecto desde:" -ForegroundColor Cyan
Write-Host "  $ProjectWinPath"
Write-Host "hacia:" -ForegroundColor Cyan
Write-Host "  $DestWinPath"

if (Test-Path $DestWinPath) {
    Remove-Item -Recurse -Force $DestWinPath
}

New-Item -ItemType Directory -Force -Path $DestWinPath | Out-Null

$ExcludeNames = @(".git", "data", "__pycache__", ".venv", "venv", ".pytest_cache")

Get-ChildItem -Force -LiteralPath $ProjectWinPath | Where-Object {
    $ExcludeNames -notcontains $_.Name
} | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $DestWinPath -Recurse -Force
}

# Construir Docker dentro de WSL
Write-Host "[8/8] Construyendo imagen Docker..." -ForegroundColor Cyan

wsl -d Ubuntu -- bash -lc "cd ~/tpf-rtl-sdr && mkdir -p data && touch data/.gitkeep && chmod +x scripts/*.sh && docker compose build"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: fallo la construccion de Docker." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Setup finalizado correctamente ===" -ForegroundColor Green
Write-Host ""
Write-Host "Para usar el analizador:"
Write-Host "1. Conectar el RTL-SDR."
Write-Host "2. Ejecutar desde esta carpeta, en PowerShell como administrador:"
Write-Host "   .\start.ps1"
Write-Host ""