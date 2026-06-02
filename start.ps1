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
    Write-Host "ERROR: ejecutá este script desde PowerShell como administrador." -ForegroundColor Red
    exit 1
}

# Verificar usbipd
try {
    usbipd --version | Out-Null
} catch {
    Write-Host "ERROR: usbipd-win no está instalado. Ejecutá setup.ps1 primero." -ForegroundColor Red
    exit 1
}

# Verificar Docker
try {
    docker info | Out-Null
} catch {
    Write-Host "ERROR: Docker Desktop no está corriendo. Abrí Docker Desktop y volvé a intentar." -ForegroundColor Red
    exit 1
}

# Iniciar WSL
Write-Host "[1/5] Iniciando Ubuntu/WSL..." -ForegroundColor Cyan
wsl -d Ubuntu -- echo WSL_OK | Out-Null

# Buscar RTL-SDR
Write-Host "[2/5] Buscando RTL-SDR..." -ForegroundColor Cyan
$usbipdOutput = usbipd list
$rtlLine = $usbipdOutput | Select-String -Pattern "0bda:2838"

if (-not $rtlLine) {
    Write-Host "ERROR: no se encontró un RTL-SDR con VID:PID 0bda:2838." -ForegroundColor Red
    Write-Host "Conectá el dongle y ejecutá start.ps1 nuevamente."
    exit 1
}

$lineText = $rtlLine.Line.Trim()
$busid = ($lineText -split "\s+")[0]

Write-Host "RTL-SDR encontrado en BUSID: $busid" -ForegroundColor Green

# Adjuntar USB a WSL
Write-Host "[3/5] Adjuntando RTL-SDR a WSL..." -ForegroundColor Cyan
usbipd bind --busid $busid | Out-Null
usbipd attach --wsl --busid $busid

Start-Sleep -Seconds 2

# Verificar que WSL lo vea
Write-Host "[4/5] Verificando RTL-SDR dentro de WSL..." -ForegroundColor Cyan
wsl -d Ubuntu -- bash -lc "lsusb | grep -i '0bda:2838'"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Ubuntu/WSL no detecta el RTL-SDR." -ForegroundColor Red
    Write-Host "Probá desconectar y reconectar el dongle, y ejecutá start.ps1 nuevamente."
    exit 1
}

# Ejecutar programa
Write-Host "[5/5] Ejecutando analizador..." -ForegroundColor Cyan
Write-Host ""

wsl -d Ubuntu -- bash -lc "cd ~/tpf-rtl-sdr && ./scripts/run.sh"
