# Analizador de Espectro RTL-SDR con Docker

Este proyecto ejecuta un analizador de espectro basado en RTL-SDR dentro de un entorno Linux reproducible usando Docker.

El sistema permite:

- adquirir muestras I/Q desde un dongle RTL-SDR;
- procesar el espectro mediante FFT/Welch;
- visualizar el espectro en tiempo real;
- ejecutar herramientas Linux como `rtl_test` y `kalibrate-rtl`;
- guardar logs y mediciones en la carpeta `data/`.

El programa corre dentro de Docker sobre Linux/WSL2. En Windows, el RTL-SDR se pasa a WSL2 mediante `usbipd-win`.

---

## Instalación rápida en Windows

### 1. Instalar Docker Desktop

Instalar Docker Desktop para Windows.

Luego abrir Docker Desktop y verificar:

```text
Settings -> General -> Use WSL 2 based engine
Settings -> Resources -> WSL Integration -> Ubuntu activado
