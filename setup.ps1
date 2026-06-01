# setup.ps1
# Configuración inicial para usar el analizador RTL-SDR con Docker + WSL2.
# Ejecutar desde PowerShell como administrador, dentro de la carpeta del proyecto.

Write-Host ""
Write-Host "=== Setup inicial RTL-SDR + Docker ===" -ForegroundColor Cyan
Write-Host ""

# Verificar administrador
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: ejecutá este script desde PowerShell como administrador." -ForegroundColor Red
    exit 1
}

# Verificar que se ejecuta desde la carpeta del proyecto
if (-not (Test-Path ".\Dockerfile") -or -not (Test-Path ".\docker-compose.yml") -or -not (Test-Path ".\app\main.py")) {
    Write-Host "ERROR: ejecutá setup.ps1 desde la carpeta raíz del proyecto." -ForegroundColor Red
    Write-Host "La carpeta debe contener Dockerfile, docker-compose.yml y app\main.py."
    exit 1
}

# Verificar winget
Write-Host "[1/8] Verificando winget..." -ForegroundColor Cyan
try {
    winget --version | Out-Null
    Write-Host "winget OK" -ForegroundColor Green
} catch {
    Write-Host "ERROR: winget no está disponible. Instalá App Installer desde Microsoft Store." -ForegroundColor Red
    exit 1
}

# Verificar Docker Desktop
Write-Host "[2/8] Verificando Docker Desktop..." -ForegroundColor Cyan
try {
    docker --version | Out-Null
    Write-Host "Docker CLI detectado." -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "ERROR: Docker Desktop no parece estar instalado." -ForegroundColor Red
    Write-Host "Instalá Docker Desktop, abrilo y volvé a ejecutar setup.ps1."
    exit 1
}

try {
    docker info | Out-Null
    Write-Host "Docker Desktop está corriendo." -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "ERROR: Docker Desktop está instalado pero no está corriendo." -ForegroundColor Red
    Write-Host "Abrí Docker Desktop y volvé a ejecutar setup.ps1."
    exit 1
}

# Instalar/verificar WSL + Ubuntu
Write-Host "[3/8] Instalando/verificando WSL + Ubuntu..." -ForegroundColor Cyan
wsl --install -d Ubuntu
wsl --update

# Instalar/verificar usbipd-win
Write-Host "[4/8] Instalando/verificando usbipd-win..." -ForegroundColor Cyan
try {
    usbipd --version | Out-Null
    Write-Host "usbipd-win detectado." -ForegroundColor Green
} catch {
    Write-Host "usbipd-win no detectado. Instalando..." -ForegroundColor Yellow
    winget install --interactive --exact dorssel.usbipd-win
}

# Iniciar Ubuntu
Write-Host "[5/8] Iniciando Ubuntu/WSL..." -ForegroundColor Cyan
wsl -d Ubuntu -- echo WSL_OK | Out-Null

# Verificar Docker desde WSL
Write-Host "[6/8] Verificando Docker dentro de Ubuntu/WSL..." -ForegroundColor Cyan
wsl -d Ubuntu -- bash -lc "docker --version && docker compose version"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Docker no está disponible dentro de Ubuntu/WSL." -ForegroundColor Red
    Write-Host "Abrí Docker Desktop y verificá:"
    Write-Host "  Settings -> Resources -> WSL Integration -> Ubuntu activado"
    Write-Host "Luego ejecutá setup.ps1 nuevamente."
    exit 1
}

# Copiar proyecto desde Windows al filesystem Linux de WSL
Write-Host "[7/8] Copiando proyecto a Ubuntu/WSL..." -ForegroundColor Cyan

$ProjectWinPath = (Resolve-Path ".").Path
$ProjectWslPath = (wsl -d Ubuntu -- wslpath -a "$ProjectWinPath").Trim()
$ProjectWslPathEscaped = $ProjectWslPath.Replace("'", "'\''")

wsl -d Ubuntu -- bash -lc "mkdir -p ~/tpf-rtl-sdr && cp -a '$ProjectWslPathEscaped/.' ~/tpf-rtl-sdr/"

# Preparar scripts y construir Docker
Write-Host "[8/8] Construyendo imagen Docker..." -ForegroundColor Cyan

wsl -d Ubuntu -- bash -lc "cd ~/tpf-rtl-sdr && mkdir -p data && touch data/.gitkeep && chmod +x scripts/*.sh && docker compose build"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: falló la construcción de Docker." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Setup finalizado correctamente ===" -ForegroundColor Green
Write-Host ""
Write-Host "Para usar el analizador:"
Write-Host "1. Conectá el RTL-SDR."
Write-Host "2. Ejecutá desde esta carpeta, en PowerShell como administrador:"
Write-Host "   .\start.ps1"
Write-Host ""
