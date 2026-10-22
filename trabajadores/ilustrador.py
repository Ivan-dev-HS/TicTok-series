"""Diseñadora de personajes + ilustrador: fichas de referencia y una imagen por plano (con variantes de boca)."""
import os
from . import gemini

FICHA = ("Anime character reference sheet, single character, full body front view plus a close-up of the face, "
         "plain light grey background, clean lines, consistent design. {estilo}. Character: {aspecto}")
PLANO = ("Vertical 9:16 anime illustration, one cinematic frame from an anime series. {estilo}. "
         "{prompt}. Keep every character EXACTLY as in the reference images (face, hair, eyes, clothes). "
         "No text, no speech bubbles, no watermark.")
BOCAS = {1: "slightly open, mid-word, as if speaking softly", 2: "clearly open, as if speaking a vowel"}
EDITAR_BOCA = ("Edit this image: change ONLY the mouth of {nombre} so it is {forma}. "
               "Everything else must stay pixel-identical: same framing, pose, eyes, hair, lighting, background and colors.")


def fichas(biblia, carpeta_serie):
    os.makedirs(os.path.join(carpeta_serie, "personajes"), exist_ok=True)
    rutas = {}
    for p in biblia["personajes"]:
        ruta = os.path.join(carpeta_serie, "personajes", f"{p['nombre']}.png")
        if not os.path.exists(ruta):
            gemini.imagen(FICHA.format(estilo=biblia["estilo_visual"], aspecto=p["aspecto"]), aspecto="1:1").save(ruta)
        rutas[p["nombre"]] = ruta
    return rutas


def planos(biblia, guion, carpeta_ep, fichas_rutas, progreso=print):
    os.makedirs(os.path.join(carpeta_ep, "img"), exist_ok=True)
    n_img = 0
    for p in guion["planos"]:
        base = os.path.join(carpeta_ep, "img", f"plano_{p['id']:02d}")
        refs = [fichas_rutas[n] for n in p.get("personajes", []) if n in fichas_rutas]
        if not os.path.exists(base + ".png"):  # reanudable si se corta a medias
            gemini.imagen(PLANO.format(estilo=biblia["estilo_visual"], prompt=p["prompt_imagen"]), refs).save(base + ".png")
            n_img += 1
        if p.get("boca"):
            for k, forma in BOCAS.items():
                if not os.path.exists(f"{base}_boca{k}.png"):
                    from PIL import Image
                    tam = Image.open(base + ".png").size  # mismo tamaño que la base para que no "salte"
                    gemini.imagen(EDITAR_BOCA.format(nombre=p["boca"], forma=forma), [base + ".png"]).resize(tam).save(f"{base}_boca{k}.png")
                    n_img += 1
        progreso(f"plano {p['id']}/{len(guion['planos'])}")
    return n_img
