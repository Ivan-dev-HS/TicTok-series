# TicTok-series · Estudio de miniseries anime

Trabajadores IA que inventan, escriben, ilustran, ponen voz y montan miniseries anime de 10 episodios para TikTok.

| Trabajador | Archivo | Herramienta |
|---|---|---|
| Jefe de producción | `cerebro.py` | decide qué toca cada día |
| Guionista | `trabajadores/guionista.py` | Gemini (texto) |
| Diseñadora de personajes e ilustrador | `trabajadores/ilustrador.py` | Gemini (imagen) |
| Actores de voz | `trabajadores/voces.py` | Gemini TTS · respaldo Kokoro |
| Animador | `trabajadores/animador.py` + `animador/kaggle_animar.py` | LTX-Video en GPU gratuita de Kaggle |
| Montador | `trabajadores/montador.py` | cámara 3D con profundidad, boca anime, subtítulos karaoke |

## Cómo se usa (pestaña **Actions → Estudio → Run workflow**)
- **diario**: se ejecuta solo cada mañana. Si no hay serie, propone una; si hay una aprobada, produce el siguiente episodio.
- **aprobar / rechazar**: escribe el id de la serie (carpeta dentro de `series/`).
- **nueva-serie**: encarga una serie con tu idea.
- **demo**: monta el episodio de prueba de *El farol azul*.

El vídeo de cada episodio aparece como **artefacto** en la ejecución (30 días).

Necesita los secretos `GEMINI_API_KEY`, `KAGGLE_USERNAME` y `KAGGLE_KEY` en *Settings → Secrets and variables → Actions*. Sin los de Kaggle, todo funciona igual pero con cámara 3D en vez de animación.
