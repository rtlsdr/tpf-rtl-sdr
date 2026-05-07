# setup_windows.ps1
# Instalación/verificación básica para usar RTL-SDR + Docker + WSL2 en Windows.
# Ejecutar desde PowerShell como administrador.

Write-Host ""
Write-Host "=== Setup Windows para RTL-SDR + Docker + WSL2 ===" -ForegroundColor Cyan
Write-Host ""

$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: Ejecutá este script desde PowerShell como administrador." -ForegroundColor Red
    exit 1
}

Write-Host "[1/6] Verificando winget..." -ForegroundColor Cyan
try {
    winget --version | Out-Null
    Write-Host "winget OK" -ForegroundColor Green
} catch {
    Write-Host "ERROR: winget no está disponible. Instalá App Installer desde Microsoft Store." -ForegroundColor Red
    exit 1
}

Write-Host "[2/6] Instalando/actualizando WSL con Ubuntu..." -ForegroundColor Cyan
wsl --install -d Ubuntu

Write-Host "[3/6] Actualizando WSL..." -ForegroundColor Cyan
wsl --update

Write-Host "[4/6] Estado de distribuciones WSL:" -ForegroundColor Cyan
wsl -l -v

Write-Host "[5/6] Instalando/verificando Docker Desktop..." -ForegroundColor Cyan
winget install --exact Docker.DockerDesktop --accept-source-agreements --accept-package-agreements

Write-Host "[6/6] Instalando/verificando usbipd-win..." -ForegroundColor Cyan
winget install --interactive --exact dorssel.usbipd-win

Write-Host ""
Write-Host "=== Setup base finalizado ===" -ForegroundColor Green
Write-Host ""
Write-Host "Pasos manuales finales:" -ForegroundColor Yellow
Write-Host "1. Reiniciá Windows si alguna instalación lo solicita."
Write-Host "2. Abrí Docker Desktop."
Write-Host "3. Verificá:"
Write-Host "   Settings -> General -> Use WSL 2 based engine"
Write-Host "   Settings -> Resources -> WSL Integration -> Ubuntu activado"
Write-Host "4. Abrí Ubuntu/WSL y probá:"
Write-Host "   docker --version"
Write-Host "   docker compose version"
Write-Host "   docker run hello-world"
Write-Host ""
