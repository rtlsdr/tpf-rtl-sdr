import datetime as dt
import re
import subprocess
import time

import matplotlib.animation as animation
from matplotlib import pyplot as plt
import numpy as np
from rtlsdr import RtlSdr


# =========================
# AJUSTES
# =========================
KAL_CHAN = 175
KAL_GAIN = 49
KAL_EVERY_S = 2 * 60 * 60   # cada 2 horas

CENTER_FREQ_HZ = 102.3e6
SAMPLE_RATE_HZ = 2.4e6
SDR_GAIN_DB = 40
INITIAL_PPM = 2

SEG = 1024
OVERLAP = 0.5
STEP = int(SEG * (1 - OVERLAP))
WIN = np.hamming(SEG)
WIN_POW = (WIN**2).sum()
N = 65536


# =========================
# TIEMPO
# =========================
def now_iso_local():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


# =========================
# KALIBRATE
# =========================
def kal_once(timeout_s=60) -> float | None:
    cmd = ["kal", "-c", str(KAL_CHAN), "-g", str(KAL_GAIN)]

    print("\n[KAL] ejecutando:", " ".join(cmd), flush=True)

    try:
        p = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print("[KAL] TIMEOUT", flush=True)
        return None
    except FileNotFoundError:
        print("[KAL] ERROR: no se encontró el comando 'kal'", flush=True)
        return None

    out = (p.stdout or "") + "\n" + (p.stderr or "")

    if p.returncode != 0:
        print("[KAL] ERROR returncode:", p.returncode, flush=True)
        print(out, flush=True)
        return None

    m = re.search(
        r"average absolute error.*?([+-]?\d+(?:\.\d+)?)\s*ppm",
        out,
        flags=re.IGNORECASE,
    )

    if not m:
        print("[KAL] No encontré ppm en la salida", flush=True)
        print(out, flush=True)
        return None

    ppm = float(m.group(1))
    print(f"[KAL] ppm medido = {ppm:+.3f}", flush=True)
    return ppm


# =========================
# SDR
# =========================
current_ppm = INITIAL_PPM


def open_sdr(ppm_correction: float, retries: int = 5):
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            sdr = RtlSdr()

            sdr.sample_rate = SAMPLE_RATE_HZ
            sdr.center_freq = CENTER_FREQ_HZ

            try:
                ppm_int = int(round(ppm_correction))
                sdr.freq_correction = ppm_int
                print(f"[SDR] freq_correction aplicado = {ppm_int:+d} ppm", flush=True)
            except Exception as e:
                print("[WARN] No pude setear freq_correction:", repr(e), flush=True)

            try:
                sdr.gain = SDR_GAIN_DB
            except Exception as e:
                print("[WARN] No pude setear gain:", repr(e), flush=True)

            return sdr

        except Exception as e:
            last_error = e
            print(f"[SDR OPEN] intento {attempt}/{retries} falló: {repr(e)}", flush=True)
            time.sleep(2.0)

    raise last_error


def close_sdr():
    global sdr

    if sdr is not None:
        try:
            sdr.close()
        except Exception:
            pass
        sdr = None


# =========================
# FIGURA
# =========================
fig, ax = plt.subplots(figsize=(9, 4))

line = None
sdr = None
Fs = None
freqs_w = None

t0 = time.time()
next_kal = None


def setup_plot():
    global line, freqs_w

    freqs_w = np.fft.fftshift(np.fft.fftfreq(SEG, d=1.0 / Fs)) / 1e6
    (line,) = ax.plot(freqs_w, np.full_like(freqs_w, -140.0))

    ax.set_xlabel("Frecuencia relativa al centro (MHz)")
    ax.set_ylabel("PSD (dB)")
    ax.set_xlim(freqs_w[0], freqs_w[-1])
    ax.set_ylim(-120, -30)
    ax.grid(True, alpha=0.3)
    update_title()


def update_title():
    ax.set_title(
        f"Welch en vivo — fs={Fs/1e6:.1f} MS/s | "
        f"fc={CENTER_FREQ_HZ/1e6:.4f} MHz | "
        f"corr={current_ppm:+.2f} ppm | kal cada {KAL_EVERY_S/3600:.1f} h"
    )


# =========================
# CICLO KALIBRATE
# =========================
def run_kalibrate_cycle():
    global sdr, Fs, current_ppm, next_kal

    elapsed = int(time.time() - t0)
    print(f"\n=== KAL CYCLE START t={elapsed}s | {now_iso_local()} ===", flush=True)

    print("[1] Cerrando SDR para liberar USB", flush=True)
    close_sdr()

    time.sleep(3.0)

    print("[2] Ejecutando kalibrate", flush=True)
    ppm = kal_once(timeout_s=60)

    if ppm is not None:
        current_ppm = ppm
        print(f"[KAL] Nuevo ppm para corrección = {current_ppm:+.3f}", flush=True)
    else:
        print(f"[KAL] Sin dato válido. Mantengo ppm anterior = {current_ppm:+.3f}", flush=True)

    print("[3] Esperando liberación USB", flush=True)
    time.sleep(5.0)

    print("[4] Reabriendo SDR con corrección actualizada", flush=True)
    try:
        sdr = open_sdr(current_ppm)
        Fs = sdr.sample_rate
    except Exception as e:
        print("[SDR OPEN FAIL]", repr(e), flush=True)
        sdr = None

    next_kal = time.time() + KAL_EVERY_S

    print(f"=== KAL CYCLE END | próximo kal en {KAL_EVERY_S/3600:.1f} h ===\n", flush=True)


# =========================
# ANIMACIÓN
# =========================
def animate(_):
    global sdr, Fs, line, next_kal

    if time.time() >= next_kal:
        ani.event_source.stop()
        try:
            run_kalibrate_cycle()
            if sdr is not None:
                update_title()
        finally:
            ani.event_source.start()

    if sdr is None:
        return (line,)

    try:
        x = sdr.read_samples(N)
    except Exception as e:
        print("[SDR READ ERROR]", repr(e), flush=True)
        return (line,)

    psd_acc = np.zeros(SEG, dtype=np.float64)
    count = 0

    for start in range(0, len(x) - SEG + 1, STEP):
        chunk = x[start:start + SEG]
        xw = chunk * WIN
        X = np.fft.fft(xw, n=SEG)
        pxx = (np.abs(X) ** 2) / (WIN_POW * Fs)
        pxx = np.fft.fftshift(pxx)
        psd_acc += pxx
        count += 1

    if count == 0:
        return (line,)

    psd = psd_acc / count
    mag_db = 10.0 * np.log10(psd + 1e-20)

    line.set_ydata(mag_db)
    return (line,)


# =========================
# MAIN
# =========================
try:
    print("=== CALIBRACIÓN INICIAL CON KALIBRATE ===", flush=True)

    ppm0 = kal_once(timeout_s=60)

    if ppm0 is not None:
        current_ppm = ppm0
    else:
        print(f"[KAL] Falló kal inicial. Uso fallback = {INITIAL_PPM:+.3f} ppm", flush=True)
        current_ppm = INITIAL_PPM

    print(f"[MAIN] Corrección inicial = {current_ppm:+.3f} ppm", flush=True)

    print("[MAIN] Esperando liberación USB antes de abrir SDR", flush=True)
    time.sleep(5.0)

    sdr = open_sdr(current_ppm)
    Fs = sdr.sample_rate

    next_kal = time.time() + KAL_EVERY_S

    setup_plot()

    ani = animation.FuncAnimation(fig, animate, interval=60, blit=True)
    plt.show()

except KeyboardInterrupt:
    pass

finally:
    close_sdr()