"""Montador v2: guion + imágenes + voces → episodio vertical 1080x1920 listo para TikTok.

- Cámara 2.5D: cada ilustración tiene mapa de profundidad, así que al moverse la cámara
  los personajes se desplazan más que el fondo (parallax) y el "dolly" acerca de verdad.
- Movimiento siempre vivo: la cámara nunca se para en seco, los personajes "respiran".
- Boca anime (kuchipaku) sincronizada con la voz.
- Subtítulos karaoke: aparecen palabra a palabra siguiendo el audio real.
"""
import math, os, random, re, subprocess, wave
import cv2
import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont
from . import profundidad

W, H, FPS = 1080, 1920, 30
SR = 44100
FONT = os.environ.get("FUENTE", "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc")
XF = 0.6             # duración del fundido entre planos
PAUSA_INICIO = 0.35
PAUSA_LINEAS = 0.3
COLA_PLANO = 0.5

# zoom (inicio, fin) · desplazamiento del centro (dx0, dy0, dx1, dy1) · parallax (px0, py0, px1, py1) · dolly
CAMARAS = {
    "acercar":   dict(z=(1.06, 1.16), pan=(0, 0, 0, 0.02), par=(-0.012, 0, 0.012, 0), dolly=0.10),
    "alejar":    dict(z=(1.18, 1.07), pan=(0, 0.01, 0, 0), par=(0.012, 0, -0.012, 0), dolly=-0.08),
    "subir":     dict(z=(1.32, 1.08), pan=(0, 0.26, 0, -0.06), par=(0, 0.02, 0, -0.01), dolly=0.05),
    "bajar":     dict(z=(1.32, 1.08), pan=(0, -0.22, 0, 0.06), par=(0, -0.02, 0, 0.01), dolly=0.05),
    "izquierda": dict(z=(1.20, 1.22), pan=(0.08, 0, -0.08, 0), par=(0.02, 0, -0.02, 0), dolly=0.0),
    "derecha":   dict(z=(1.20, 1.22), pan=(-0.08, 0, 0.08, 0), par=(-0.02, 0, 0.02, 0), dolly=0.0),
    "golpe":     dict(z=(1.02, 1.24), pan=(0, 0, 0, -0.01), par=(0, 0, 0, 0), dolly=0.12, rapido=True),
    "fijo":      dict(z=(1.10, 1.14), pan=(0, 0, 0, 0), par=(-0.008, 0.003, 0.008, -0.003), dolly=0.04),
}
FLASHES = {"flash_azul": (90, 170, 255), "flash_blanco": (255, 255, 255), "flash_rojo": (255, 60, 50), "flash_dorado": (255, 210, 110)}


def curva(k):
    """Mitad lineal, mitad suave: arranca y termina con suavidad pero nunca se queda quieta."""
    return 0.5 * k + 0.5 * k * k * (3 - 2 * k)


# ---------------------------------------------------------------- línea de tiempo
def linea_de_tiempo(guion, duraciones):
    t, planos = 0.0, []
    for p in guion["planos"]:
        lineas, cur = [], t + PAUSA_INICIO
        for n, l in enumerate(p.get("lineas", [])):
            d = duraciones[(p["id"], n)]
            lineas.append({**l, "n": n, "ini": cur, "fin": cur + d})
            cur += d + PAUSA_LINEAS
        fin_dialogo = (lineas[-1]["fin"] + COLA_PLANO) if lineas else t
        dur = max(p.get("duracion_min", 3.0), fin_dialogo - t)
        planos.append({**p, "ini": t, "dur": dur, "lineas_t": lineas})
        t += dur
    return planos, t


# ---------------------------------------------------------------- imágenes con profundidad
class Fuente:
    def __init__(self, ruta, prof=None, masc=None):
        im = Image.open(ruta).convert("RGB")
        if prof is None:
            prof, masc = profundidad.preparar(ruta)
        esc = max(W * 1.3 / im.width, H * 1.3 / im.height)
        self.sw, self.sh = int(im.width * esc), int(im.height * esc)
        self.img = np.asarray(im.resize((self.sw, self.sh), Image.LANCZOS))
        d = cv2.resize(prof, (self.sw, self.sh), interpolation=cv2.INTER_LINEAR)
        # suavizar la profundidad evita "desgarros" en los bordes de los personajes
        self.prof = cv2.GaussianBlur(d, (0, 0), self.sw * 0.012)
        self.masc = cv2.GaussianBlur(cv2.resize(masc, (self.sw, self.sh)), (0, 0), 3)
        self.prof_raw, self.masc_raw = prof, masc


_U, _V = np.meshgrid(np.arange(W, dtype=np.float32) - W / 2, np.arange(H, dtype=np.float32) - H / 2)


def render_25d(f: Fuente, zoom, cx, cy, parx, pary, dolly, respiro, temblor=(0, 0)):
    """Cámara virtual sobre la imagen con profundidad. cx, cy, en fracción de la imagen."""
    crop_h = min(f.sh, f.sw * H / W) / zoom
    s = crop_h / H
    cxp = min(max(cx * f.sw, crop_h * W / H / 2), f.sw - crop_h * W / H / 2) + temblor[0]
    cyp = min(max(cy * f.sh, crop_h / 2), f.sh - crop_h / 2) + temblor[1]
    dref = float(f.prof[int(np.clip(cyp, 0, f.sh - 1)), int(np.clip(cxp, 0, f.sw - 1))])
    mx = cxp + _U * s; my = cyp + _V * s
    for _ in range(2):  # 2 iteraciones bastan para converger
        d = cv2.remap(f.prof, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT) - dref
        esc = s / (1 + dolly * d)
        mx = cxp + _U * esc + parx * f.sw * d
        my = cyp + _V * esc + pary * f.sw * d
    if respiro:
        m = cv2.remap(f.masc, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        my = my - m * respiro * (my - (cyp + crop_h / 2))  # se estira levemente desde los pies
    return cv2.remap(f.img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def cargar_imagenes(carpeta, planos):
    fuentes = {}
    for p in planos:
        base = os.path.join(carpeta, "img", f"plano_{p['id']:02d}")
        b = Fuente(base + ".png")
        fuentes[p["id"]] = [b]
        for k in (1, 2):  # las variantes de boca comparten profundidad con la base
            ruta = f"{base}_boca{k}.png"
            if os.path.exists(ruta):
                fuentes[p["id"]].append(Fuente(ruta, b.prof_raw, b.masc_raw))
    return fuentes


# ---------------------------------------------------------------- análisis de voz
def _rms(a, sr, paso_s):
    paso = max(1, int(sr * paso_s))
    return np.array([np.sqrt(np.mean(a[i:i + paso] ** 2)) for i in range(0, len(a), paso)])


def niveles_boca(carpeta, planos):
    res = {}
    for p in planos:
        quien = p.get("boca")
        if not quien:
            continue
        tramos = []
        for l in p["lineas_t"]:
            if l["quien"] != quien:
                continue
            a, sr = sf.read(os.path.join(carpeta, "audio", f"linea_{p['id']:02d}_{l['n']}.wav"))
            rms = _rms(a, sr, 1 / 12)
            pico = max(np.percentile(rms, 95), 1e-6)
            niv = np.where(rms > 0.55 * pico, 2, np.where(rms > 0.18 * pico, 1, 0))
            for i in range(2, len(niv)):
                if niv[i] == niv[i - 1] == niv[i - 2] == 2:
                    niv[i] = 1
            tramos.append((l["ini"], l["fin"], niv))
        res[p["id"]] = tramos
    return res


def _silabas(palabra):
    return max(1, len(re.findall(r"[aeiouáéíóúü]+", palabra.lower())))


def tiempos_palabras(ruta_wav, texto, ini):
    """Reparte las palabras sobre los tramos con voz real (no sobre los silencios)."""
    a, sr = sf.read(ruta_wav)
    rms = _rms(a, sr, 0.01)
    voz = np.convolve(rms > 0.07 * rms.max(), np.ones(5) / 5, "same") > 0.3
    acum = np.concatenate([[0], np.cumsum(voz)]) * 0.01  # segundos de voz acumulados
    palabras = texto.split()
    pesos = np.array([_silabas(w) for w in palabras], float)
    limites = np.concatenate([[0], np.cumsum(pesos)]) / pesos.sum() * acum[-1]
    t_real = np.interp(limites, acum, np.arange(len(acum)) * 0.01)
    return [(w, ini + t_real[i], ini + t_real[i + 1]) for i, w in enumerate(palabras)]


def bloques_subtitulos(carpeta, planos, max_palabras=4):
    """Agrupa palabras en bloques cortos que cortan en signos de puntuación."""
    bloques = []
    for p in planos:
        for l in p["lineas_t"]:
            ws = tiempos_palabras(os.path.join(carpeta, "audio", f"linea_{p['id']:02d}_{l['n']}.wav"), l["texto"], l["ini"])
            cur = []
            for w in ws:
                cur.append(w)
                if len(cur) >= max_palabras or w[0][-1] in ".,!?…;:":
                    bloques.append((l["quien"], cur)); cur = []
            if cur:
                bloques.append((l["quien"], cur))
    # cada bloque dura hasta que empieza el siguiente (si es cerca), así no parpadea
    res = []
    for i, (q, ws) in enumerate(bloques):
        fin = ws[-1][2] + 0.25
        if i + 1 < len(bloques):
            sig = bloques[i + 1][1][0][1]
            if sig - fin < 0.5:
                fin = sig
        res.append((ws[0][1], fin, q, ws))
    return res


# ---------------------------------------------------------------- capas
def capa_lluvia(gotas, t, fuerza, ov):
    d = ImageDraw.Draw(ov)
    for x, y, L, v, w in gotas:
        yy = (y + v * t) % (H + 100) - 50; xx = (x - 0.12 * v * t) % W
        d.line([(xx, yy), (xx - 0.12 * L, yy + L)], fill=(200, 220, 255, int(fuerza * (55 + 22 * w))), width=w)


def capa_particulas(chispas, t, color, ov):
    d = ImageDraw.Draw(ov)
    for x, y, r, v, fase in chispas:
        yy = (y - v * t) % H; xx = x + 25 * math.sin(t * 0.8 + fase)
        a = int(140 + 110 * math.sin(t * 3 + fase))
        d.ellipse((xx - r, yy - r, xx + r, yy + r), fill=color + (max(a, 0),))


_fx = {}
def fuente(tam):
    if tam not in _fx:
        _fx[tam] = ImageFont.truetype(FONT, tam)
    return _fx[tam]


def dibujar_bloque(d, t, s, e, ws, color):
    f = fuente(66); esp = d.textlength(" ", font=f)
    anchos = [d.textlength(w, font=f) for w, _, _ in ws]
    lineas, cur, ancho = [], [], 0
    for i, a in enumerate(anchos):
        if cur and ancho + esp + a > 940:
            lineas.append(cur); cur, ancho = [], 0
        cur.append(i); ancho += (esp if len(cur) > 1 else 0) + a
    lineas.append(cur)
    aparicion = min(1, (t - s) / 0.12); salida = min(1, (e - t) / 0.12)
    alfa = int(255 * min(aparicion, salida))
    y0 = H * 0.70 - (len(lineas) - 1) * 45 + (1 - aparicion) * 18
    for li, idxs in enumerate(lineas):
        total = sum(anchos[i] for i in idxs) + esp * (len(idxs) - 1)
        x = W / 2 - total / 2; y = y0 + li * 90
        for i in idxs:
            w, wi, wf = ws[i]
            activa = wi <= t < wf + 0.05
            dicha = t >= wi
            col = color if activa else ((255, 255, 255) if dicha else (200, 200, 200))
            sub = -6 if activa else 0
            d.text((x, y + sub), w, font=f, anchor="lm", fill=tuple(col) + (alfa if dicha else int(alfa * 0.75),),
                   stroke_width=7, stroke_fill=(0, 0, 0, alfa))
            x += anchos[i] + esp


def capa_texto(t, guion, bloques, total, colores, ov):
    d = ImageDraw.Draw(ov)
    if t < 3.5:
        a = int(255 * min(1, t / 0.5, (3.5 - t) / 0.5))
        d.text((W / 2, 170), guion["serie"].upper(), font=fuente(84), anchor="mm", fill=(170, 215, 255, a), stroke_width=5, stroke_fill=(5, 15, 40, a))
        d.text((W / 2, 250), f"CAPÍTULO {guion['episodio']}", font=fuente(38), anchor="mm", fill=(255, 255, 255, a), stroke_width=3, stroke_fill=(0, 0, 0, a))
    for s, e, quien, ws in bloques:
        if s <= t < e:
            dibujar_bloque(d, t, s, e, ws, colores.get(quien, (255, 222, 90)))
    if t > total - 2.2:
        a = int(255 * min(1, (t - (total - 2.2)) / 0.4))
        txt = f"SÍGUEME · PARTE {guion['episodio'] + 1}" if guion["episodio"] < guion.get("total_episodios", 10) else "FIN"
        f = fuente(52); w = d.textlength(txt, font=f)
        d.rounded_rectangle((W / 2 - w / 2 - 50, 1560, W / 2 + w / 2 + 50, 1660), 50, fill=(20, 110, 230, int(a * 0.9)))
        d.text((W / 2, 1610), txt, font=f, anchor="mm", fill=(255, 255, 255, a))


# ---------------------------------------------------------------- audio
def _env(n, i0, ataque, caida):
    e = np.zeros(n); k = np.arange(n - i0) / SR
    e[i0:] = np.minimum(k / ataque, 1) * np.exp(-np.maximum(k - ataque, 0) / caida)
    return e


def mezclar_audio(carpeta, guion, planos, total, salida):
    import scipy.signal as ss
    n = int(total * SR) + SR; t = np.arange(n) / SR
    rng = np.random.default_rng(1)
    amb = guion.get("ambiente", "lluvia")
    ruido = rng.normal(0, 1, n)
    fondo = np.zeros(n)
    if amb == "lluvia":
        fondo += ss.lfilter(*ss.butter(2, [800 / (SR / 2), 7000 / (SR / 2)], "band"), ruido) * 0.14
    if amb in ("lluvia", "viento"):
        fondo += ss.lfilter(*ss.butter(2, 400 / (SR / 2), "low"), ruido) * (0.28 if amb == "lluvia" else 0.55)
    acordes = {"misterio": [55, 82.4, 110, 130.8], "epico": [65.4, 98, 130.8, 164.8], "triste": [58.3, 87.3, 116.5, 138.6]}
    for f in acordes.get(guion.get("tono", "misterio"), acordes["misterio"]):
        fondo += np.sin(2 * np.pi * f * t + np.sin(2 * np.pi * 0.2 * t) * 0.4) * 0.04
    sfx = np.zeros(n)
    for p in planos:
        i0 = int(p["ini"] * SR)
        if p.get("efecto", "").startswith("flash"):
            sfx += np.sin(2 * np.pi * (45 + 60 * np.exp(-np.maximum(t - p["ini"], 0) * 8)) * t) * _env(n, i0, 0.005, 0.9) * 0.6
            sfx += ss.lfilter(*ss.butter(2, 6000 / (SR / 2), "high"), ruido) * _env(n, i0, 0.03, 0.6) * 0.08
    voz = np.zeros(n)
    for p in planos:
        for l in p["lineas_t"]:
            a, sr = sf.read(os.path.join(carpeta, "audio", f"linea_{p['id']:02d}_{l['n']}.wav"))
            if a.ndim > 1:
                a = a.mean(1)
            a = np.interp(np.arange(0, len(a), sr / SR), np.arange(len(a)), a)
            a = a / max(np.percentile(np.abs(a), 99.5), 1e-6) * 0.55  # volumen igualado entre voces
            i0 = int(l["ini"] * SR); voz[i0:i0 + len(a)] += a[: n - i0]
    env_voz = np.convolve(np.abs(voz) > 0.02, np.ones(SR // 4) / (SR // 4), "same")
    fondo *= 1 - 0.6 * np.clip(env_voz * 3, 0, 1)
    mix = fondo + sfx + voz
    mix *= np.clip(t / 0.5, 0, 1) * np.clip((total - t) / 0.4, 0, 1)
    mix = np.tanh(mix * 1.05) * 0.9
    with wave.open(salida, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix[: int(total * SR)] * 32767).astype(np.int16).tobytes())


# ---------------------------------------------------------------- render
def montar(carpeta, guion, duraciones, salida="episodio.mp4", colores=None):
    random.seed(7); np.random.seed(7)
    planos, total = linea_de_tiempo(guion, duraciones)
    fuentes = cargar_imagenes(carpeta, planos)
    bocas = niveles_boca(carpeta, planos)
    bloques = bloques_subtitulos(carpeta, planos)
    colores = colores or {}
    gotas = [[random.uniform(0, W), random.uniform(0, H), random.uniform(28, 70), random.uniform(1300, 2200), random.choice([1, 2, 2, 3])] for _ in range(220)]
    chispas = [[random.uniform(0, W), random.uniform(0, H), random.uniform(2, 5), random.uniform(30, 90), random.uniform(0, 6)] for _ in range(45)]
    r = np.sqrt((_U / (W / 2)) ** 2 + (_V / (H / 2)) ** 2)
    vig = np.clip(1 - 0.5 * np.clip(r - 0.55, 0, 1) ** 1.4, 0, 1)[..., None].astype(np.float32)
    grano = [np.random.normal(0, 4, (H, W, 1)).astype(np.float32) for _ in range(6)]

    def frame_plano(p, t):
        c = CAMARAS.get(p.get("camara", "acercar"), CAMARAS["acercar"])
        fx, fy = p.get("foco", [0.5, 0.5])
        # la cámara sigue moviéndose durante el fundido de salida (no se congela)
        lento = min(max((t - p["ini"]) / (p["dur"] + XF), 0), 1)
        if c.get("rapido"):  # entra de golpe y luego sigue deslizándose despacio
            u = min(max((t - p["ini"]) / 0.8, 0), 1)
            k = 0.8 * (1 - (1 - u) ** 3) + 0.2 * lento
        else:
            k = curva(lento)
        z = c["z"][0] + (c["z"][1] - c["z"][0]) * k
        dx0, dy0, dx1, dy1 = c["pan"]; px0, py0, px1, py1 = c["par"]
        # pequeño balanceo de cámara en mano
        cx = fx + dx0 + (dx1 - dx0) * k + 0.003 * math.sin(t * 0.9)
        cy = fy + dy0 + (dy1 - dy0) * k + 0.002 * math.sin(t * 0.7 + 1)
        temblor = (0, 0)
        if p.get("efecto", "").startswith("flash") or p.get("efecto") == "temblor":
            amp = max(0, 14 * (1 - (t - p["ini"]) / 0.6))
            temblor = (amp * math.sin(t * 90), amp * math.cos(t * 77))
        src = imagen_boca(fuentes[p["id"]], bocas.get(p["id"], []), t)
        respiro = 0.006 * math.sin(2 * math.pi * t / 3.6)
        return render_25d(src, z, cx, cy, px0 + (px1 - px0) * k, py0 + (py1 - py0) * k,
                          c["dolly"] * k, respiro, temblor).astype(np.float32)

    video_tmp = os.path.join(carpeta, "_video.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                           "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", video_tmp], stdin=subprocess.PIPE)
    for f in range(int(total * FPS)):
        t = f / FPS
        idx = max(i for i, p in enumerate(planos) if p["ini"] <= t)
        p = planos[idx]
        arr = frame_plano(p, t)
        corte = p.get("efecto", "").startswith("flash") or p.get("transicion") == "corte"
        if idx > 0 and t < p["ini"] + XF and not corte:
            a = (t - p["ini"]) / XF; a = a * a * (3 - 2 * a)
            arr = frame_plano(planos[idx - 1], t) * (1 - a) + arr * a
        # desenfoque de movimiento en los golpes de cámara
        if CAMARAS.get(p.get("camara"), {}).get("rapido") and t < p["ini"] + 0.5:
            arr = (arr + frame_plano(p, t + 0.5 / FPS)) / 2
        col = FLASHES.get(p.get("efecto", ""))
        if col and t < p["ini"] + 0.5:
            a = (1 - (t - p["ini"]) / 0.5) ** 2 * 0.8
            arr = arr * (1 - a) + np.array(col, np.float32) * a
        arr = arr * vig + grano[f % 6]
        if t < 0.5: arr *= t / 0.5
        out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        clima = p.get("clima", guion.get("ambiente"))
        if clima == "lluvia":
            capa_lluvia(gotas, t, 0.9, ov)
        elif clima in ("magia", "chispas"):
            capa_particulas(chispas, t, (150, 210, 255), ov)
        capa_texto(t, guion, bloques, total, colores, ov)
        out.paste(ov, (0, 0), ov)
        ff.stdin.write(out.tobytes())
    ff.stdin.close(); ff.wait()

    audio_tmp = os.path.join(carpeta, "_audio.wav")
    mezclar_audio(carpeta, guion, planos, total, audio_tmp)
    final = os.path.join(carpeta, salida)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video_tmp, "-i", audio_tmp, "-c:v", "libx264", "-preset", "slow",
                    "-b:v", "8M", "-maxrate", "9M", "-bufsize", "16M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                    "-shortest", "-movflags", "+faststart", final], check=True)
    os.remove(video_tmp); os.remove(audio_tmp)
    return final, total


def imagen_boca(fuentes_plano, tramos, t):
    if len(fuentes_plano) < 3:
        return fuentes_plano[0]
    for ini, fin, niv in tramos:
        if ini <= t < fin:
            return fuentes_plano[int(niv[min(int((t - ini) * 12), len(niv) - 1)])]
    return fuentes_plano[0]
