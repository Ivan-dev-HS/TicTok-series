"""Actores de voz.

Principal: Gemini TTS (voces neuronales muy naturales, entiende indicaciones de emoción).
Respaldo gratuito: Kokoro (CPU) si Gemini falla o no hay clave.
"""
import os, wave
import numpy as np
import soundfile as sf

MODELOS = os.path.join(os.path.dirname(__file__), "..", "modelos")
TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-2.5-flash-preview-tts")

# Voces de Gemini que suenan bien en español. Mujer: Kore, Aoede, Leda, Zephyr, Sulafat · Hombre: Puck, Charon, Fenrir, Orus, Algenib
VOCES_GEMINI = {"mujer": ["Kore", "Leda", "Aoede", "Zephyr", "Sulafat"], "hombre": ["Puck", "Orus", "Charon", "Fenrir", "Algenib"]}
KOKORO_DEFECTO = {"mujer": "ef_dora", "hombre": "em_alex"}


def _gemini_tts(texto, voz, direccion):
    from google.genai import types
    from . import gemini
    prompt = (f"{direccion}. Lee en español de España, con naturalidad, como una actriz o actor de doblaje de anime, "
              f"respetando las pausas de la puntuación. Di exactamente este texto, sin añadir nada:\n{texto}")
    cfg = types.GenerateContentConfig(response_modalities=["AUDIO"], speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voz))))
    r = gemini._reintentar(lambda: gemini.client().models.generate_content(model=TTS_MODEL, contents=prompt, config=cfg))
    pcm = r.candidates[0].content.parts[0].inline_data.data  # PCM 16 bits, 24 kHz, mono
    return np.frombuffer(pcm, np.int16).astype(np.float32) / 32768, 24000


_kokoro = None
def _kokoro_tts(texto, voz, velocidad):
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(os.path.join(MODELOS, "kokoro.onnx"), os.path.join(MODELOS, "voices.bin"))
    return _kokoro.create(texto, voice=voz, speed=velocidad, lang="es")


def _recortar_silencios(a, sr):
    """Quita silencio al principio y al final para que la boca y los subtítulos casen."""
    env = np.abs(a) > 0.02 * np.abs(a).max()
    idx = np.where(env)[0]
    if not len(idx):
        return a
    i0 = max(0, idx[0] - int(0.03 * sr)); i1 = min(len(a), idx[-1] + int(0.08 * sr))
    return a[i0:i1]


def generar_lineas(guion, reparto, carpeta):
    """reparto: {"narrador": {"gemini": "Kore", "kokoro": "ef_dora", "direccion": "Narradora misteriosa, voz cálida y pausada"}, ...}
    Cada línea puede llevar "emocion" (p. ej. "susurrando, asustada") que se añade a la dirección."""
    os.makedirs(os.path.join(carpeta, "audio"), exist_ok=True)
    usar_gemini = bool(os.environ.get("GEMINI_API_KEY")) and os.environ.get("VOZ_MOTOR", "gemini") == "gemini"
    duraciones = {}
    for p in guion["planos"]:
        for n, linea in enumerate(p.get("lineas", [])):
            ruta = os.path.join(carpeta, "audio", f"linea_{p['id']:02d}_{n}.wav")
            if not os.path.exists(ruta):
                cfg = reparto.get(linea["quien"]) or reparto["narrador"]
                direccion = cfg.get("direccion", "Voz natural")
                if linea.get("emocion"):
                    direccion += f". En esta frase: {linea['emocion']}"
                audio = None
                if usar_gemini:
                    try:
                        audio, sr = _gemini_tts(linea["texto"], cfg.get("gemini", "Kore"), direccion)
                    except Exception as e:
                        print(f"Gemini TTS falló ({e}); uso Kokoro")
                if audio is None:
                    audio, sr = _kokoro_tts(linea["texto"], cfg.get("kokoro", "ef_dora"), cfg.get("velocidad", 1.0))
                sf.write(ruta, _recortar_silencios(np.asarray(audio, np.float32), sr), sr)
            info = sf.info(ruta)
            duraciones[(p["id"], n)] = info.frames / info.samplerate
    return duraciones
