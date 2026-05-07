# attach_rtlsdr.ps1
# Adjunta el RTL-SDR a WSL usando usbipd-win.
# Ejecutar desde PowerShell como administrador.

Write-Host ""
Write-Host "=== Attach RTL-SDR a WSL ===" -ForegroundColor Cyan
Write-Host ""

$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: Ejecutá este script desde PowerShell como administrador." -ForegroundColor Red
    exit 1
}

try {
    usbipd --version | Out-Null
} catch {
    Write-Host "ERROR: usbipd-win no está instalado o no está en PATH." -ForegroundColor Red
    Write-Host "Ejecutá primero: .\scripts\setup_windows.ps1"
    exit 1
}

Write-Host "[1/5] Listando dispositivos USB..." -ForegroundColor Cyan
$usbipdOutput = usbipd list
Write-Host $usbipdOutput

Write-Host "[2/5] Buscando RTL-SDR 0bda:2838..." -ForegroundColor Cyan
$rtlLine = $usbipdOutput | Select-String -Pattern "0bda:2838"

if (-not $rtlLine) {
    Write-Host "ERROR: No se encontró ningún RTL-SDR con VID:PID 0bda:2838." -ForegroundColor Red
    Write-Host "Verificá que el dongle esté conectado."
    exit 1
}

$lineText = $rtlLine.Line.Trim()
$busid = ($lineText -split "\s+")[0]

Write-Host "RTL-SDR encontrado en BUSID: $busid" -ForegroundColor Green

Write-Host "[3/5] Iniciando WSL si estaba detenido..." -ForegroundColor Cyan
wsl -d Ubuntu -- echo WSL_OK | Out-Null

Write-Host "[4/5] Compartiendo dispositivo con usbipd..." -ForegroundColor Cyan
usbipd bind --busid $busid

Write-Host "[5/5] Adjuntando RTL-SDR a WSL..." -ForegroundColor Cyan
usbipd attach --wsl --busid $busid

Write-Host ""
Write-Host "RTL-SDR adjuntado a WSL." -ForegroundColor Green
Write-Host ""
Write-Host "Verificá en Ubuntu/WSL con:" -ForegroundColor Yellow
Write-Host "  lsusb"
Write-Host "  docker compose run --rm rtl-sdr lsusb"
Write-Host ""
