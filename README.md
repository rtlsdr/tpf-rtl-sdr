# Analizador de Espectro RTL-SDR con Docker

Este proyecto ejecuta un analizador de espectro basado en RTL-SDR dentro de un entorno Linux reproducible usando Docker.

El sistema permite:

- adquirir muestras I/Q desde un dongle RTL-SDR;
- procesar el espectro mediante FFT/Welch;
- visualizar el espectro en tiempo real;
- ejecutar herramientas Linux como `rtl_test` y `kalibrate-rtl`;
- guardar logs y mediciones en la carpeta `data/`.

El programa corre dentro de un contenedor Linux. En Windows, el RTL-SDR se pasa a WSL2 mediante `usbipd-win`.

---

## 1. Requisitos

El usuario necesita:

- Windows 10/11;
- conexión a internet;
- permisos de administrador;
- RTL-SDR conectado por USB;
- PowerShell;
- WSL2 + Ubuntu;
- Docker Desktop;
- usbipd-win.

No hace falta instalar:

- Zadig;
- DLLs de RTL-SDR para Windows;
- drivers SDR nativos de Windows;
- Python en Windows.

El software SDR corre dentro de Linux/Docker.

---

## 2. Instalación inicial en Windows

Abrir PowerShell como administrador.

Clonar el repositorio desde GitHub:

```powershell
cd C:\Users\USUARIO\Downloads
git clone https://github.com/rtlsdr/tpf-rtl-sdr.git
cd tpf-rtl-sdr
