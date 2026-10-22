"""Conexión con la API de Gemini (texto e imagen). La clave se lee de la variable GEMINI_API_KEY."""
import io, json, os, time
from PIL import Image

TEXT_MODEL = os.environ.get("TEXT_MODEL", "gemini-2.5-flash")
# Se prueba en orden; el primero que exista en tu cuenta se queda. Del más barato al más caro.
IMAGE_MODELS = [m for m in os.environ.get("IMAGE_MODELS", "gemini-nano-banana-2.1,gemini-3.1-flash-image,gemini-2.5-flash-image").split(",") if m]

_client = None
def client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def _reintentar(fn, intentos=5):
    for i in range(intentos):
        try:
            return fn()
        except Exception as e:  # 429 / 5xx: esperar y reintentar
            msg = str(e)
            if i == intentos - 1 or not any(c in msg for c in ("429", "500", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE")):
                raise
            time.sleep(10 * 2 ** i)


def texto_json(prompt, sistema=None):
    from google.genai import types
    cfg = types.GenerateContentConfig(response_mime_type="application/json", system_instruction=sistema, temperature=0.9)
    r = _reintentar(lambda: client().models.generate_content(model=TEXT_MODEL, contents=prompt, config=cfg))
    return json.loads(r.text)


_modelo_img = None
def imagen(prompt, referencias=(), aspecto="9:16"):
    """Genera (o edita, si se pasan referencias) una imagen. Devuelve PIL.Image."""
    global _modelo_img
    from google.genai import types
    cfg = types.GenerateContentConfig(response_modalities=["IMAGE"], image_config=types.ImageConfig(aspect_ratio=aspecto))
    contenido = [prompt] + [r if isinstance(r, Image.Image) else Image.open(r) for r in referencias]
    modelos = [_modelo_img] if _modelo_img else IMAGE_MODELS
    ultimo = None
    for m in modelos:
        try:
            r = _reintentar(lambda: client().models.generate_content(model=m, contents=contenido, config=cfg))
            for part in r.candidates[0].content.parts:
                if part.inline_data:
                    _modelo_img = m
                    return Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
            ultimo = RuntimeError(f"{m}: la respuesta no trae imagen (¿bloqueada por filtros?)")
        except Exception as e:
            ultimo = e
            if "404" not in str(e) and "NOT_FOUND" not in str(e):
                raise
    raise ultimo
