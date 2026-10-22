"""Guionista: inventa series y escribe cada episodio como guion JSON que entiende el montador."""
from . import gemini

SISTEMA = """Eres el guionista jefe de una cuenta de TikTok de miniseries anime en español.
Cada serie tiene 10 episodios de 1:30 a 2 minutos. Las historias deben enganchar desde el primer segundo:
gancho visual inmediato, misterio, giros, y cada episodio termina en cliffhanger.
Escribes en español de España, natural y emocionante, frases cortas que se lean bien como subtítulos.
Contenido apto para todo público de TikTok: nada sexual, sin violencia gráfica, sin marcas ni personajes con copyright."""

CAMARAS = "acercar, alejar, subir (revelación de abajo arriba), bajar, izquierda, derecha, golpe (zoom rápido de impacto), fijo"
EFECTOS = "ninguno, flash_azul, flash_blanco, flash_rojo, flash_dorado, temblor"


def crear_serie(evitar=(), idea=None):
    return gemini.texto_json(f"""Crea una nueva miniserie anime original.
{('Idea del productor: ' + idea) if idea else 'Elige el género que creas que mejor funciona hoy en TikTok (fantasía, misterio, acción, romance, terror suave...).'}
No repitas estas series anteriores: {', '.join(evitar) or 'ninguna'}.

Devuelve JSON con esta forma exacta:
{{"serie": "título corto y potente",
  "logline": "una frase que venda la serie",
  "genero": "...",
  "tono": "misterio|epico|triste",
  "ambiente": "lluvia|viento|ninguno",
  "estilo_visual": "en INGLÉS: estilo de ilustración común para todas las imágenes (anime moderno de alta calidad, paleta, iluminación)",
  "personajes": [{{"nombre": "...", "rol": "...", "personalidad": "...",
                  "aspecto": "en INGLÉS, descripción visual MUY concreta y fija (edad, pelo, ojos, ropa, rasgo distintivo)",
                  "sexo": "mujer|hombre",
                  "voz_descripcion": "cómo suena su voz (edad, timbre, forma de hablar)",
                  "color_subtitulo": [r, g, b]}}],
  "narrador": {{"sexo": "mujer|hombre", "voz_descripcion": "cómo debe sonar la narración"}},
  "episodios": [{{"numero": 1, "titulo": "...", "resumen": "3-4 frases con lo que pasa y el cliffhanger final"}}]}}
Máximo 4 personajes. Exactamente 10 episodios.""", SISTEMA)


def escribir_episodio(biblia, numero, anteriores_resumen=""):
    ep = biblia["episodios"][numero - 1]
    nombres = [p["nombre"] for p in biblia["personajes"]]
    g = gemini.texto_json(f"""Serie: {biblia['serie']} — {biblia['logline']}
Personajes: {[{k: p[k] for k in ('nombre', 'rol', 'personalidad', 'aspecto')} for p in biblia['personajes']]}
Lo que ha pasado antes: {anteriores_resumen or 'nada, es el primer episodio'}
Episodio {numero}: "{ep['titulo']}" — {ep['resumen']}

Escribe el guion completo como una secuencia de 18 a 24 planos (ilustraciones) que sumen 90-120 segundos.
Mezcla narración (quien = "narrador") y diálogos de los personajes. 1 o 2 líneas por plano, frases cortas.
El primer plano debe enganchar en 2 segundos. El último plano es el cliffhanger.

Para cada plano:
- "prompt_imagen": en INGLÉS, descripción completa de la ilustración vertical (acción, encuadre, luz, emoción). Nombra a los personajes que salen.
- "personajes": lista de nombres de los que aparecen (de {nombres}).
- "movimiento": en INGLÉS, qué se MUEVE en el plano para animarlo (una acción simple y clara de 4 segundos: "she slowly turns her head toward the camera and gasps, rain falling, hair moving in the wind"). Evita acciones complejas o con muchas personas.
- "camara": una de [{CAMARAS}]. "foco": [x, y] de 0 a 1, punto de interés de la imagen.
- "efecto": una de [{EFECTOS}] (úsalos poco, solo en momentos clave).
- "boca": nombre del personaje SOLO si el plano es un primer plano frontal suyo y él/ella habla en este plano; si no, null.
- "lineas": [{{"quien": "narrador" o nombre, "texto": "...", "emocion": "cómo se dice (p. ej. susurrando y asustada, gritando con rabia, con ironía)"}}].
- "duracion_min": segundos (3 a 6).

Devuelve JSON: {{"titulo": "...", "planos": [{{"id": 1, ...}}]}}""", SISTEMA)
    from .voces import VOCES_GEMINI, KOKORO_DEFECTO
    nar = biblia.get("narrador", {"sexo": "mujer", "voz_descripcion": "narradora misteriosa, cálida y pausada"})
    sexo_n = "hombre" if nar.get("sexo") == "hombre" else "mujer"
    reparto = {"narrador": {"gemini": VOCES_GEMINI[sexo_n][0], "kokoro": KOKORO_DEFECTO[sexo_n], "velocidad": 0.92,
                            "direccion": "Narración de anime: " + nar.get("voz_descripcion", "")}}
    colores = {"narrador": [255, 222, 90]}
    usadas = {"mujer": 1 if sexo_n == "mujer" else 0, "hombre": 1 if sexo_n == "hombre" else 0}
    for p in biblia["personajes"]:
        sexo = "hombre" if p.get("sexo") == "hombre" else "mujer"
        voz = VOCES_GEMINI[sexo][usadas[sexo] % len(VOCES_GEMINI[sexo])]; usadas[sexo] += 1
        reparto[p["nombre"]] = {"gemini": voz, "kokoro": KOKORO_DEFECTO[sexo], "velocidad": 1.0,
                                "direccion": f"Personaje {p['nombre']} ({p['personalidad']}). Voz: {p.get('voz_descripcion', '')}"}
        colores[p["nombre"]] = p.get("color_subtitulo", [255, 214, 120])
    return {"serie": biblia["serie"], "episodio": numero, "total_episodios": len(biblia["episodios"]),
            "titulo": g["titulo"], "ambiente": biblia.get("ambiente", "ninguno"), "tono": biblia.get("tono", "misterio"),
            "reparto": reparto, "colores": colores, "planos": g["planos"]}


def texto_tiktok(biblia, guion):
    """Descripción y hashtags para la publicación."""
    return gemini.texto_json(f"""Escribe la descripción de TikTok para el episodio {guion['episodio']} de "{biblia['serie']}" ({guion['titulo']}).
Logline: {biblia['logline']}. Máx. 150 caracteres + 5 hashtags relevantes en español (incluye #anime).
JSON: {{"descripcion": "...", "hashtags": ["#..."]}}""", SISTEMA)
