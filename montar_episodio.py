"""Uso: python montar_episodio.py <carpeta_episodio>
La carpeta debe tener guion.json e img/plano_XX.png (y opcionalmente plano_XX_boca1/2.png)."""
import json, sys, time
from trabajadores import voces, montador, animador

carpeta = sys.argv[1]
guion = json.load(open(f"{carpeta}/guion.json"))
t0 = time.time()
if '--animar' in sys.argv:
    print(f"clips: {animador.animar(carpeta, guion)}")
dur = voces.generar_lineas(guion, guion["reparto"], carpeta)
print(f"voces: {len(dur)} líneas en {time.time()-t0:.0f}s")
colores = {k: tuple(v) for k, v in guion.get("colores", {}).items()}
final, total = montador.montar(carpeta, guion, dur, colores=colores)
print(f"listo: {final} ({total:.1f}s) en {time.time()-t0:.0f}s")
