import csv
import datetime as dt
import re
import subprocess
import time
from pathlib import Path

import matplotlib.animation as animation
from matplotlib import pyplot as plt
import numpy as np
from rtlsdr import RtlSdr


# =========================
# AJUSTES
# =========================
KAL_CHAN = 175
KAL_GAIN = 49
KAL_EVERY_S = 30

CSV_PATH = Path("/workspace/data/ppm_log.csv")

CENTER_FREQ_HZ = 102.3e6
SAMPLE_RATE_HZ = 2.4e6
SDR_GAIN_DB = 40
INITIAL_PPM = 2

# Parámetros Welch
SEG = 1024
OVERLAP = 0.5
STEP = int(SEG * (1 - OVERLAP))

# Si en el informe van a justificar Hamming, usen Hamming:
WIN = np.hamming(SEG)

# Si prefieren mantener exactamente lo que ya tenían, era Hann:
# WIN = np.hanning(SEG)

WIN_POW = (WIN**2).sum()

N = 65536


# =========================
# CSV
# =========================
def append_csv_row(row: dict):
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    exists = CSV_PATH.exists()

    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=row.keys())
        if not exists:
            w.writeheader()
        w.writerow(row)


def now_iso_local():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


# =========================
# SDR
# =========================
def open_sdr():
    sdr = RtlSdr()

    sdr.sample_rate = SAMPLE_RATE_HZ
    sdr.center_freq = CENTER_FREQ_HZ

    try:
        sdr.freq_correction = INITIAL_PPM
    except Exception as e:
        print("[WARN] No pude setear freq_correction:", repr(e), flush=True)

    try:
        sdr.gain = SDR_GAIN_DB
    except Exception as e:
        print("[WARN] No pude setear gain:", repr(e), flush=True)

    return sdr


# =========================
# KALIBRATE EN LINUX
# =========================
def kal_once(timeout_s=45) -> float | None:
    cmd = ["kal", "-c", str(KAL_CHAN), "-g", str(KAL_GAIN)]

    print("[KAL] ejecutando:", " ".join(cmd), flush=True)

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

    return float(m.group(1))


# =========================
# FIGURA
# =========================
fig, ax = plt.subplots(figsize=(9, 4))

line = None
sdr = None
Fs = None
freqs_w = None

t0 = time.time()
next_kal = t0 + KAL_EVERY_S


def setup_plot():
    global line, freqs_w

    freqs_w = np.fft.fftshift(np.fft.fftfreq(SEG, d=1.0 / Fs)) / 1e6
    (line,) = ax.plot(freqs_w, np.full_like(freqs_w, -140.0))

    ax.set_xlabel("Frecuencia relativa al centro (MHz)")
    ax.set_ylabel("PSD (dB)")
    ax.set_title(
        f"Welch en vivo — fs={Fs/1e6:.1f} MS/s | "
        f"fc={sdr.center_freq/1e6:.4f} MHz | kal cada {KAL_EVERY_S}s"
    )

    ax.set_xlim(freqs_w[0], freqs_w[-1])
    ax.set_ylim(-120, -30)
    ax.grid(True, alpha=0.3)


def run_kalibrate_cycle():
    global sdr, next_kal, Fs

    elapsed = int(time.time() - t0)
    print(f"\n=== KAL CYCLE START t={elapsed}s ===", flush=True)

    ppm = None

    try:
        print("[1] cerrando SDR", flush=True)
        if sdr is not None:
            try:
                sdr.close()
            except Exception:
                pass
        sdr = None

        time.sleep(1.0)

        print("[2] corriendo kalibrate dentro de Linux/Docker", flush=True)
        ppm = kal_once(timeout_s=45)

        append_csv_row({
            "iso_time": now_iso_local(),
            "uptime_s": elapsed,
            "ppm": "" if ppm is None else ppm,
            "kal_chan": KAL_CHAN,
            "kal_gain": KAL_GAIN,
            "status": "ok" if ppm is not None else "no_ppm",
        })

        print(f"[KAL] t={elapsed}s -> ppm={ppm if ppm is not None else 'sin dato'}", flush=True)

    except Exception as e:
        print("[KAL ERROR] desactivando scheduler:", repr(e), flush=True)
        next_kal = float("inf")

    finally:
        time.sleep(1.0)

        print("[3] reabriendo SDR", flush=True)
        try:
            sdr = open_sdr()
            Fs = sdr.sample_rate
        except Exception as e_open:
            print("[SDR OPEN FAIL]", repr(e_open), flush=True)
            sdr = None

        if next_kal != float("inf"):
            next_kal = time.time() + KAL_EVERY_S

    print("=== KAL CYCLE END ===\n", flush=True)


def animate(_):
    global sdr, Fs, line, next_kal

    if time.time() >= next_kal:
        ani.event_source.stop()
        try:
            run_kalibrate_cycle()
        except Exception as e:
            print("[KAL ERROR] desactivando scheduler:", repr(e), flush=True)
            next_kal = float("inf")
        finally:
            ani.event_source.start()

        if sdr is not None:
            ax.set_title(
                f"Welch en vivo — fs={Fs/1e6:.1f} MS/s | "
                f"fc={sdr.center_freq/1e6:.4f} MHz | kal cada {KAL_EVERY_S}s"
            )

    if sdr is None:
        return (line,)

    x = sdr.read_samples(N)

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
    sdr = open_sdr()
    Fs = sdr.sample_rate

    setup_plot()

    ani = animation.FuncAnimation(fig, animate, interval=60, blit=True)
    plt.show()

except KeyboardInterrupt:
    pass

finally:
    try:
        if sdr is not None:
            sdr.close()
    except Exception:
        pass