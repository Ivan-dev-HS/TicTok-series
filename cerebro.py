"""Jefe de producción: decide qué toca hacer hoy.

  python cerebro.py                       → turno diario automático
  python cerebro.py aprobar <serie>       → apruebas la idea de una serie
  python cerebro.py rechazar <serie>      → la descartas (mañana se inventa otra)
  python cerebro.py nueva-serie "idea"    → encargas una serie con tu idea

Estados de una serie: pendiente_aprobacion → aprobada → en_produccion → terminada (o rechazada).
"""
import json, os, sys
import producir

RAIZ = producir.RAIZ


def series():
    if not os.path.isdir(RAIZ):
        return []
    res = []
    for d in sorted(os.listdir(RAIZ)):
        f = os.path.join(RAIZ, d, "biblia.json")
        if os.path.exists(f):
            res.append((d, json.load(open(f))))
    return res


def guardar(sid, biblia):
    json.dump(biblia, open(os.path.join(RAIZ, sid, "biblia.json"), "w"), ensure_ascii=False, indent=2)


def salida(clave, valor):
    """Deja datos para el workflow de GitHub (nombre del artefacto, etc.)."""
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"{clave}={valor}\n")


def turno_diario():
    lista = series()
    for estado in ("en_produccion", "aprobada"):
        for sid, b in lista:
            if b.get("estado") != estado:
                continue
            n = next((i for i in range(1, len(b["episodios"]) + 1)
                      if not os.path.exists(os.path.join(RAIZ, sid, f"ep_{i:02d}", "publicacion.json"))), None)
            if n is None:
                b["estado"] = "terminada"; guardar(sid, b); continue
            b["estado"] = "en_produccion"; guardar(sid, b)
            print(f"🎬 Produciendo {b['serie']} — episodio {n}")
            producir.episodio(sid, n)
            salida("video", os.path.join(RAIZ, sid, f"ep_{n:02d}", "episodio.mp4"))
            salida("nombre", f"{sid}-ep{n:02d}")
            if n == len(b["episodios"]):
                b["estado"] = "terminada"; guardar(sid, b)
            return
    pendientes = [b["serie"] for _, b in lista if b.get("estado") == "pendiente_aprobacion"]
    if pendientes:
        print(f"⏸️ Esperando tu aprobación: {', '.join(pendientes)}")
        return
    print("💡 No hay series en marcha: el guionista propone una nueva")
    producir.nueva_serie()


def cambiar_estado(sid, estado):
    b = json.load(open(os.path.join(RAIZ, sid, "biblia.json")))
    b["estado"] = estado; guardar(sid, b)
    print(f"{b['serie']} → {estado}")


if __name__ == "__main__":
    accion = sys.argv[1] if len(sys.argv) > 1 else "diario"
    if accion == "diario":
        turno_diario()
    elif accion == "aprobar":
        cambiar_estado(sys.argv[2], "aprobada")
    elif accion == "rechazar":
        cambiar_estado(sys.argv[2], "rechazada")
    elif accion == "nueva-serie":
        producir.nueva_serie(sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None)
