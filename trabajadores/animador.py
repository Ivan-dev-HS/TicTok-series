"""Animador: encarga a una GPU gratuita de Kaggle que convierta las ilustraciones en clips de vídeo.

Necesita los secretos KAGGLE_USERNAME y KAGGLE_KEY. Si falta algo o Kaggle falla,
el episodio sigue adelante con la cámara 3D: nunca bloquea la producción.
"""
import glob, json, os, shutil, subprocess, tempfile, time

KERNEL = os.path.join(os.path.dirname(__file__), "..", "animador", "kaggle_animar.py")


def _k(*args, check=True):
    r = subprocess.run(["kaggle", *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"kaggle {' '.join(args)}: {r.stderr or r.stdout}")
    return r.stdout + r.stderr


def disponible():
    return bool(os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"))


def animar(carpeta, guion, max_minutos=150, espera_max_min=240):
    """Genera carpeta/clips/plano_XX.mp4 para los planos con 'movimiento'. Devuelve nº de clips."""
    if not disponible():
        print("::warning title=Animador::Sin secretos KAGGLE_USERNAME/KAGGLE_KEY, se usa la cámara 3D")
        return 0
    usuario = os.environ["KAGGLE_USERNAME"]
    planos = [p for p in guion["planos"] if p.get("movimiento") and p.get("animar", True)]
    destino = os.path.join(carpeta, "clips")
    hechos = {os.path.basename(f) for f in glob.glob(os.path.join(destino, "*.mp4"))}
    planos = [p for p in planos if f"plano_{p['id']:02d}.mp4" not in hechos]
    if not planos:
        return len(hechos)

    tmp = tempfile.mkdtemp()
    ds, kn = os.path.join(tmp, "ds"), os.path.join(tmp, "kn")
    os.makedirs(ds); os.makedirs(kn)
    for p in planos:
        shutil.copy(os.path.join(carpeta, "img", f"plano_{p['id']:02d}.png"), ds)
    json.dump({"max_minutos": max_minutos,
               "planos": [{"id": p["id"], "imagen": f"plano_{p['id']:02d}.png", "movimiento": p["movimiento"],
                           "escena": p.get("prompt_imagen", "")[:300]} for p in planos]},
              open(os.path.join(ds, "trabajo.json"), "w"))
    ds_id = f"{usuario}/estudio-trabajo"
    json.dump({"title": "estudio-trabajo", "id": ds_id, "licenses": [{"name": "CC0-1.0"}]},
              open(os.path.join(ds, "dataset-metadata.json"), "w"))
    try:
        try:
            _k("datasets", "version", "-p", ds, "-m", f"ep {guion.get('episodio')}", "--dir-mode", "zip")
        except RuntimeError:
            _k("datasets", "create", "-p", ds, "--dir-mode", "zip")
    except RuntimeError as e:
        print(f"::warning title=Animador::No se pudieron subir las imágenes a Kaggle, se usa la cámara 3D. {str(e)[:400]}")
        return 0
    for _ in range(60):  # esperar a que Kaggle procese el dataset
        if "ready" in _k("datasets", "status", ds_id, check=False).lower():
            break
        time.sleep(10)

    shutil.copy(KERNEL, os.path.join(kn, "kaggle_animar.py"))
    kid = f"{usuario}/estudio-animador"
    json.dump({"id": kid, "title": "estudio-animador", "code_file": "kaggle_animar.py", "language": "python",
               "kernel_type": "script", "is_private": True, "enable_gpu": True, "enable_internet": True,
               "dataset_sources": [ds_id], "competition_sources": [], "kernel_sources": []},
              open(os.path.join(kn, "kernel-metadata.json"), "w"))
    try:
        print(_k("kernels", "push", "-p", kn))
    except RuntimeError as e:
        print(f"::warning title=Animador::No se pudo lanzar en Kaggle, se usa la cámara 3D. {str(e)[:400]}")
        return 0
    print(f"Animador: {len(planos)} planos enviados a la GPU de Kaggle…")

    inicio = time.time()
    estado = ""
    while time.time() - inicio < espera_max_min * 60:
        time.sleep(60)
        estado = _k("kernels", "status", kid, check=False).lower()
        print(f"  [{(time.time() - inicio) / 60:.0f} min] {estado.strip()[-60:]}")
        if any(s in estado for s in ("complete", "error", "cancel")):
            break
    out = os.path.join(tmp, "out")
    _k("kernels", "output", kid, "-p", out, check=False)
    os.makedirs(destino, exist_ok=True)
    for f in glob.glob(os.path.join(out, "**", "plano_*.mp4"), recursive=True):
        shutil.move(f, os.path.join(destino, os.path.basename(f)))
    reg = glob.glob(os.path.join(out, "**", "registro.json"), recursive=True)
    if reg:
        txt = open(reg[0]).read(); print("Registro de Kaggle:", txt)
        print("::notice title=Registro Kaggle::" + txt.replace("\n", " ")[:1500])
    n = len(glob.glob(os.path.join(destino, "*.mp4")))
    print(f"::notice title=Animador::{n} clips animados de {len(planos)} planos. Kaggle: {estado.strip()[-80:]}")
    return n
