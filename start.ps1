# start.ps1
# Adjunta el RTL-SDR a WSL y ejecuta el analizador dentro de Docker.
# Ejecutar desde PowerShell como administrador, dentro de la carpeta del proyecto.

Write-Host ""
Write-Host "=== Iniciando analizador RTL-SDR ===" -ForegroundColor Cyan
Write-Host ""

# Verificar administrador
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: ejecutar este script desde PowerShell como administrador." -ForegroundColor Red
    exit 1
}

function Get-UsbipdExe {
    $cmd = Get-Command usbipd -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $candidate = "C:\Program Files\usbipd-win\usbipd.exe"
    if (Test-Path $candidate) {
        return $candidate
    }

    return $null
}

$UsbipdExe = Get-UsbipdExe

if (-not $UsbipdExe) {
    Write-Host "ERROR: usbipd-win no esta instalado o no esta disponible en PATH." -ForegroundColor Red
    Write-Host "Ejecutar setup.ps1. Si ya se instalo, cerrar PowerShell y abrirlo nuevamente como administrador."
    exit 1
}

# Verificar Docker
docker info | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop no esta corriendo. Abrir Docker Desktop y volver a intentar." -ForegroundColor Red
    exit 1
}

# Iniciar Ubuntu
Write-Host "[1/5] Iniciando Ubuntu/WSL..." -ForegroundColor Cyan
wsl -d Ubuntu -- echo WSL_OK | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: no se pudo iniciar Ubuntu/WSL." -ForegroundColor Red
    exit 1
}

# Dejar Ubuntu como distro default para evitar que usbipd elija docker-desktop
wsl --set-default Ubuntu | Out-Null

# Buscar RTL-SDR
Write-Host "[2/5] Buscando RTL-SDR..." -ForegroundColor Cyan
$usbipdOutput = & $UsbipdExe list
Write-Host $usbipdOutput

$rtlLine = $usbipdOutput | Select-String -Pattern "0bda:2838"

if (-not $rtlLine) {
    Write-Host "ERROR: no se encontro un RTL-SDR con VID:PID 0bda:2838." -ForegroundColor Red
    Write-Host "Conectar el dongle y ejecutar start.ps1 nuevamente."
    exit 1
}

$lineText = $rtlLine.Line.Trim()
$busid = ($lineText -split "\s+")[0]

Write-Host "RTL-SDR encontrado en BUSID: $busid" -ForegroundColor Green

# Adjuntar USB a WSL
Write-Host "[3/5] Adjuntando RTL-SDR a WSL..." -ForegroundColor Cyan

& $UsbipdExe bind --busid $busid | Out-Null

# Si no estaba adjuntado, detach puede mostrar advertencia. No es grave.
& $UsbipdExe detach --busid $busid | Out-Null

& $UsbipdExe attach --wsl --busid $busid

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: no se pudo adjuntar el RTL-SDR a WSL." -ForegroundColor Red
    Write-Host "Probar desconectar y reconectar el dongle, y ejecutar start.ps1 nuevamente."
    exit 1
}

Start-Sleep -Seconds 2

# Verificar que Docker vea el RTL-SDR
Write-Host "[4/5] Verificando RTL-SDR dentro de Docker..." -ForegroundColor Cyan

wsl -d Ubuntu -- bash -lc "cd ~/tpf-rtl-sdr && docker compose run --rm rtl-sdr lsusb | grep -i '0bda:2838'"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Docker no detecta el RTL-SDR." -ForegroundColor Red
    Write-Host "Probar desconectar y reconectar el dongle, y ejecutar start.ps1 nuevamente."
    exit 1
}

# Ejecutar programa
Write-Host "[5/5] Ejecutando analizador..." -ForegroundColor Cyan
Write-Host ""

wsl -d Ubuntu -- bash -lc "cd ~/tpf-rtl-sdr && ./scripts/run.sh"