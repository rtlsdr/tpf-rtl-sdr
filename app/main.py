import datetime as dt
import re
import subprocess
import time

import matplotlib.animation as animation
from matplotlib import pyplot as plt
import numpy as np
from rtlsdr import RtlSdr
from matplotlib.ticker import MultipleLocator
from matplotlib.widgets import Slider, TextBox, Button


# =========================
# AJUSTES
# =========================
KAL_CHAN = 175
KAL_GAIN = 49
KAL_EVERY_S = 2 * 60 * 60   # cada 2 horas

MIN_FREQ_HZ = 24e6
MAX_FREQ_HZ = 1766e6

CENTER_FREQ_HZ = 102.3e6
SAMPLE_RATE_HZ = 2.4e6
SDR_GAIN_DB = 48
INITIAL_PPM = 2

SEG = 1024
OVERLAP = 0.5
STEP = int(SEG * (1 - OVERLAP))
WIN = np.hamming(SEG)
WIN_POW = (WIN**2).sum()
N = 65536

Y_MIN_INIT = -120
Y_MAX_INIT = -30

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
current_center_hz = CENTER_FREQ_HZ


def open_sdr(ppm_correction: float, retries: int = 5):
    last_error = None
    global current_center_hz

    for attempt in range(1, retries + 1):
        try:
            sdr = RtlSdr()

            sdr.sample_rate = SAMPLE_RATE_HZ
            sdr.center_freq = current_center_hz

            print(f"[FFT] corrección de frecuencia = {ppm_correction:+.3f} ppm", flush=True)

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
fig, ax = plt.subplots(figsize=(18, 5))
plt.subplots_adjust(left=0.08, right=0.78, bottom=0.18)

line = None
sdr = None
Fs = None
freqs_w = None
center_line = None
center_text = None
freq_slider = None
freq_box = None
ymin_slider = None
ymax_slider = None
peak_enabled = False
peak_span_pct = 0.0
peak_button = None
peak_slider = None
peak_value_box = None
peak_marker = None

t0 = time.time()
next_kal = None

def make_freq_axis():
    f_rel = np.fft.fftshift(np.fft.fftfreq(SEG, d=1.0 / Fs))

    # Eje sin corregir
    f_axis_hz = current_center_hz + f_rel

    # Corrección manual exacta en ppm, usando el valor decimal de kal
    # Si el signo queda invertido respecto de kal, cambiar el "-" por "+"
    f_axis_hz = f_axis_hz - current_center_hz * current_ppm * 1e-6

    return f_axis_hz / 1e6


def update_freq_axis():
    global freqs_w, center_line, center_text

    freqs_w = make_freq_axis()
    line.set_xdata(freqs_w)

    ax.set_xlim(freqs_w[0], freqs_w[-1])

    center_mhz = current_center_hz / 1e6

    center_line.set_xdata([center_mhz, center_mhz])
    center_text.set_position((center_mhz, ax.get_ylim()[1] - 3))
    center_text.set_text(f"{center_mhz:.4f} MHz")

    ax.set_title(
        f"Welch en vivo — fs={Fs/1e6:.1f} MS/s | "
        f"fc={center_mhz:.4f} MHz | gain={SDR_GAIN_DB} dB"
    )

    fig.canvas.draw_idle()



# =========================
# CALLBACKS
# =========================
def set_center_freq_mhz(freq_mhz):
    global current_center_hz

    freq_hz = float(freq_mhz) * 1e6

    if freq_hz < MIN_FREQ_HZ:
        freq_hz = MIN_FREQ_HZ
    if freq_hz > MAX_FREQ_HZ:
        freq_hz = MAX_FREQ_HZ

    current_center_hz = freq_hz

    try:
        sdr.center_freq = current_center_hz
        print(f"[SDR] Nueva frecuencia central: {current_center_hz/1e6:.4f} MHz", flush=True)
    except Exception as e:
        print("[ERROR] No pude setear frecuencia:", repr(e), flush=True)

    freq_box.set_val(f"{current_center_hz/1e6:.4f}")
    update_freq_axis()


def on_freq_slider_change(val):
    set_center_freq_mhz(val)


def on_freq_box_submit(text):
    try:
        val = float(text)
        freq_slider.set_val(val)
        set_center_freq_mhz(val)
    except ValueError:
        print("[ERROR] Frecuencia inválida:", text, flush=True)


def on_y_change(_):
    ymin = ymin_slider.val
    ymax = ymax_slider.val

    if ymin >= ymax:
        return

    ax.set_ylim(ymin, ymax)

    center_text.set_position(
        (current_center_hz / 1e6, ymax - 3)
    )

    fig.canvas.draw_idle()



def setup_plot():
    global line, freqs_w
    global center_line, center_text
    global freq_slider, freq_box, ymin_slider, ymax_slider
    global peak_button, peak_slider, peak_value_box, peak_marker

    freqs_w = make_freq_axis()
    (line,) = ax.plot(freqs_w, np.full_like(freqs_w, -140.0))

    ax.set_xlabel("Frecuencia (MHz)")
    ax.set_ylabel("PSD (dB)")
    ax.set_xlim(freqs_w[0], freqs_w[-1])
    ax.set_ylim(Y_MIN_INIT, Y_MAX_INIT)
    ax.xaxis.set_major_locator(MultipleLocator(0.1))
    ax.grid(True, alpha=0.3)

    center_mhz = current_center_hz / 1e6
    center_line = ax.axvline(center_mhz, color="red", linewidth=1.5)

    center_text = ax.text(
        center_mhz,
        ax.get_ylim()[1] - 3,
        f"{center_mhz:.4f} MHz",
        color="red",
        ha="center",
        va="top",
        fontsize=9,
        bbox=dict(facecolor="white", edgecolor="red", alpha=0.8),
    )

    (peak_marker,) = ax.plot(
        [],
        [],
        marker="o",
        markersize=7,
        linestyle="None",
        color="red",
    )

    ax.set_title(
        f"Welch en vivo — fs={Fs/1e6:.1f} MS/s | "
        f"fc={center_mhz:.4f} MHz | gain={SDR_GAIN_DB} dB"
    )

    # Slider vertical frecuencia central
    ax_freq_slider = plt.axes([0.82, 0.25, 0.03, 0.60])
    freq_slider = Slider(
        ax=ax_freq_slider,
        label="Fc MHz",
        valmin=MIN_FREQ_HZ / 1e6,
        valmax=MAX_FREQ_HZ / 1e6,
        valinit=current_center_hz / 1e6,
        orientation="vertical",
    )

    # Caja numérica frecuencia central
    ax_freq_box = plt.axes([0.81, 0.12, 0.045, 0.05])
    freq_box = TextBox(
        ax_freq_box,
        " ",
        initial=f"{current_center_hz/1e6:.4f}"
    )

    # Slider Y max
    ax_ymax_slider = plt.axes([0.90, 0.25, 0.03, 0.60])
    ymax_slider = Slider(
        ax=ax_ymax_slider,
        label="Y max",
        valmin=-100,
        valmax=20,
        valinit=Y_MAX_INIT,
        orientation="vertical",
    )

    # Slider Y min
    ax_ymin_slider = plt.axes([0.95, 0.25, 0.03, 0.60])
    ymin_slider = Slider(
        ax=ax_ymin_slider,
        label="Y min",
        valmin=-160,
        valmax=0,
        valinit=Y_MIN_INIT,
        orientation="vertical",
    )

    # Boton ON/OFF Peak Finder
    ax_peak_button = plt.axes([0.86, 0.12, 0.04, 0.05])
    peak_button = Button(ax_peak_button, "Peak OFF")

    # Caja donde se muestra el máximo
    ax_peak_value = plt.axes([0.86, 0.06, 0.11, 0.05])
    peak_value_box = TextBox(ax_peak_value, "Peak", initial="---")

    # Slider vertical porcentaje de búsqueda
    ax_peak_slider = plt.axes([0.86, 0.25, 0.03, 0.60])
    peak_slider = Slider(
        ax=ax_peak_slider,
        label="Peak %",
        valmin=0,
        valmax=100,
        valinit=0,
        orientation="vertical",
    )

    peak_slider.set_active(False)
    peak_slider.ax.set_facecolor("0.85")   

    freq_slider.on_changed(on_freq_slider_change)
    freq_box.on_submit(on_freq_box_submit)
    ymin_slider.on_changed(on_y_change)
    ymax_slider.on_changed(on_y_change)
    peak_button.on_clicked(on_peak_button_clicked)
    peak_slider.on_changed(on_peak_slider_change)

def on_peak_button_clicked(_):
    global peak_enabled

    peak_enabled = not peak_enabled

    if peak_enabled:
        peak_button.label.set_text("Peak ON")
        peak_slider.set_active(True)
        peak_slider.ax.set_facecolor("white")
        print("[PEAK] habilitado", flush=True)
    else:
        peak_button.label.set_text("Peak OFF")
        peak_slider.set_active(False)
        peak_slider.ax.set_facecolor("0.85")
        peak_value_box.set_val("---")
        peak_marker.set_data([], [])
        print("[PEAK] deshabilitado", flush=True)

    fig.canvas.draw_idle()


def on_peak_slider_change(val):
    global peak_span_pct

    peak_span_pct = float(val)
    print(f"[PEAK] ancho de búsqueda = {peak_span_pct:.1f} %", flush=True)


def update_peak_finder(mag_db):
    """
    Busca el máximo dentro de un porcentaje del ancho mostrado.
    peak_span_pct = 0  -> solo zona central mínima
    peak_span_pct = 100 -> todo el ancho mostrado
    """

    if not peak_enabled:
        return

    center_mhz = current_center_hz / 1e6

    full_span_mhz = freqs_w[-1] - freqs_w[0]

    # Evita ventana de ancho cero. Con 0%, busca en una ventana mínima de 1 bin.
    requested_span_mhz = full_span_mhz * (peak_span_pct / 100.0)

    if requested_span_mhz <= 0:
        idx_center = np.argmin(np.abs(freqs_w - center_mhz))
        search_idx = np.array([idx_center])
    else:
        half_span = requested_span_mhz / 2.0
        mask = np.abs(freqs_w - center_mhz) <= half_span
        search_idx = np.where(mask)[0]

    if len(search_idx) == 0:
        peak_value_box.set_val("---")
        peak_marker.set_data([], [])
        return

    local_mag = mag_db[search_idx]
    local_max_pos = np.argmax(local_mag)
    idx_peak = search_idx[local_max_pos]

    peak_freq_mhz = freqs_w[idx_peak]
    peak_power_db = mag_db[idx_peak]

    peak_value_box.set_val(f"{peak_freq_mhz:.4f} MHz / {peak_power_db:.1f} dB")

    peak_marker.set_data([peak_freq_mhz], [peak_power_db])

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
    try:
        x = sdr.read_samples(N)
    except Exception as e:
        print("[SDR READ ERROR]", repr(e), flush=True)
        return (line, center_line, center_text)

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
        return (line, center_line, center_text)

    psd = psd_acc / count
    mag_db = 10.0 * np.log10(psd + 1e-20)

    line.set_ydata(mag_db)

    update_peak_finder(mag_db)

    return (line, center_line, center_text, peak_marker)


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

    ani = animation.FuncAnimation(fig, animate, interval=80, blit=False)
    plt.show()

except KeyboardInterrupt:
    pass

finally:
    close_sdr()