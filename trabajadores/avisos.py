"""Muestra los errores como anotaciones de GitHub Actions (se ven en el resumen de la ejecución)."""
import os, sys, traceback


def _gh(texto):
    return texto.replace("%", "%25").replace("\r", "").replace("\n", "%0A")


def ejecutar(fn):
    if "GEMINI_API_KEY" not in os.environ or not os.environ["GEMINI_API_KEY"]:
        print("::error title=Falta la clave de Gemini::Añade el secreto GEMINI_API_KEY en Settings → Secrets and variables → Actions")
        sys.exit(1)
    try:
        fn()
    except SystemExit:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        ultimas = "\n".join(tb.strip().splitlines()[-6:])
        print(f"::error title={type(e).__name__}::{_gh(ultimas)[:3000]}")
        sys.exit(1)
