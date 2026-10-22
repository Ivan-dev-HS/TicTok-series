"""Mapa de profundidad (Depth Anything V2) y máscara de personajes (ISNet anime). Gratis, CPU."""
import os
import numpy as np
from PIL import Image

MODELOS = os.path.join(os.path.dirname(__file__), "..", "modelos")
_s = {}
def _sesion(nombre):
    if nombre not in _s:
        import onnxruntime as ort
        _s[nombre] = ort.InferenceSession(os.path.join(MODELOS, nombre), providers=["CPUExecutionProvider"])
    return _s[nombre]


def profundidad(im: Image.Image):
    """Devuelve array float32 HxW en [0,1], 1 = cerca de la cámara."""
    x = np.asarray(im.convert("RGB").resize((518, 518), Image.BICUBIC)).astype(np.float32) / 255
    x = (x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
    d = _sesion("depth_anything_v2_vits.onnx").run(None, {"l_x_": x.transpose(2, 0, 1)[None].astype(np.float32)})[0][0]
    d = (d - d.min()) / (d.max() - d.min() + 1e-6)
    d = np.asarray(Image.fromarray(d.astype(np.float32)).resize(im.size, Image.BICUBIC))
    return np.clip(d, 0, 1).astype(np.float32)


def mascara_personaje(im: Image.Image):
    x = np.asarray(im.convert("RGB").resize((1024, 1024), Image.BILINEAR)).astype(np.float32) / 255
    m = _sesion("isnet-anime.onnx").run(None, {"img": x.transpose(2, 0, 1)[None]})[0][0, 0]
    m = (m - m.min()) / (m.max() - m.min() + 1e-6)
    return np.asarray(Image.fromarray(m.astype(np.float32)).resize(im.size, Image.BILINEAR)).astype(np.float32)


def preparar(ruta_img):
    """Calcula y guarda <img>.prof.npy y <img>.masc.npy junto a la imagen (cache)."""
    base = os.path.splitext(ruta_img)[0]
    im = Image.open(ruta_img)
    if not os.path.exists(base + ".prof.npy"):
        np.save(base + ".prof.npy", profundidad(im).astype(np.float16))
    if not os.path.exists(base + ".masc.npy"):
        np.save(base + ".masc.npy", mascara_personaje(im).astype(np.float16))
    return np.load(base + ".prof.npy").astype(np.float32), np.load(base + ".masc.npy").astype(np.float32)
