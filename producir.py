"""Productora: coordina a los trabajadores.

  python producir.py nueva-serie ["idea opcional"]   → series/<id>/biblia.json + fichas de personajes
  python producir.py episodio <id> <numero>          → series/<id>/ep_XX/episodio.mp4 + publicacion.json
"""
import json, os, re, sys, time
from trabajadores import guionista, ilustrador, voces, montador

RAIZ = os.path.join(os.path.dirname(__file__), "series")


def slug(t):
    t = t.lower()
    for a, b in zip("áéíóúñü", "aeiounu"):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def nueva_serie(idea=None):
    os.makedirs(RAIZ, exist_ok=True)
    previas = [json.load(open(os.path.join(RAIZ, d, "biblia.json")))["serie"] for d in os.listdir(RAIZ)
               if os.path.exists(os.path.join(RAIZ, d, "biblia.json"))]
    biblia = guionista.crear_serie(previas, idea)
    sid = slug(biblia["serie"]); carpeta = os.path.join(RAIZ, sid)
    os.makedirs(carpeta, exist_ok=True)
    biblia["estado"] = "pendiente_aprobacion"
    json.dump(biblia, open(os.path.join(carpeta, "biblia.json"), "w"), ensure_ascii=False, indent=2)
    ilustrador.fichas(biblia, carpeta)
    print(f"serie creada: {sid}")
    return sid


def episodio(sid, numero):
    t0 = time.time()
    carpeta_serie = os.path.join(RAIZ, sid)
    biblia = json.load(open(os.path.join(carpeta_serie, "biblia.json")))
    carpeta = os.path.join(carpeta_serie, f"ep_{numero:02d}")
    os.makedirs(carpeta, exist_ok=True)
    ruta_guion = os.path.join(carpeta, "guion.json")
    if os.path.exists(ruta_guion):
        guion = json.load(open(ruta_guion))
    else:
        antes = " ".join(e["resumen"] for e in biblia["episodios"][: numero - 1])
        guion = guionista.escribir_episodio(biblia, numero, antes)
        json.dump(guion, open(ruta_guion, "w"), ensure_ascii=False, indent=2)
    print(f"guion: {len(guion['planos'])} planos")
    fichas = ilustrador.fichas(biblia, carpeta_serie)
    n = ilustrador.planos(biblia, guion, carpeta, fichas)
    print(f"imágenes nuevas: {n}")
    dur = voces.generar_lineas(guion, guion["reparto"], carpeta)
    colores = {k: tuple(v) for k, v in guion.get("colores", {}).items()}
    final, total = montador.montar(carpeta, guion, dur, colores=colores)
    pub = guionista.texto_tiktok(biblia, guion)
    pub.update({"estado": "pendiente_aprobacion", "video": final, "duracion": round(total, 1), "imagenes": n})
    json.dump(pub, open(os.path.join(carpeta, "publicacion.json"), "w"), ensure_ascii=False, indent=2)
    print(f"episodio listo: {final} ({total:.0f}s) en {(time.time()-t0)/60:.1f} min")
    return final


if __name__ == "__main__":
    if sys.argv[1] == "nueva-serie":
        nueva_serie(sys.argv[2] if len(sys.argv) > 2 else None)
    elif sys.argv[1] == "episodio":
        episodio(sys.argv[2], int(sys.argv[3]))
