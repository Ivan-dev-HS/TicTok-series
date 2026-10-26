# Se ejecuta DENTRO de Kaggle (GPU gratuita). Lo sube y lanza trabajadores/animador.py.
# Lee trabajo.json + imágenes del dataset adjunto y genera un clip por plano con LTX-Video.
import glob, json, os, socket, subprocess, sys, time
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

# Comprobaciones previas con mensajes claros
try:
    socket.gethostbyname("pypi.org"); internet = True
except OSError:
    internet = False
import shutil
smi = shutil.which("nvidia-smi") or next((c for c in ("/usr/bin/nvidia-smi", "/usr/local/nvidia/bin/nvidia-smi") if os.path.exists(c)), None)
gpu = subprocess.run([smi, "-L"], capture_output=True, text=True).stdout.strip() if smi else ""
devs = sorted(glob.glob("/dev/nvidia*"))
try:
    import torch as _t
    tinfo = f"torch {_t.__version__} cuda={_t.version.cuda} disponible={_t.cuda.is_available()}"
    if not gpu and _t.cuda.is_available():
        gpu = _t.cuda.get_device_name(0)
except Exception as e:
    tinfo = f"torch: {e}"
print(f"INTERNET={internet} GPU={gpu or 'ninguna'} | smi={smi} | dev={devs} | {tinfo} | "
      f"KAGGLE_KERNEL_RUN_TYPE={os.environ.get('KAGGLE_KERNEL_RUN_TYPE')} ACC={os.environ.get('KAGGLE_GPU_TYPE') or os.environ.get('ACCELERATOR_TYPE')}", flush=True)
if not internet or not gpu:
    raise SystemExit("FALTA " + ("INTERNET " if not internet else "") + ("GPU " if not gpu else "")
                     + "en Kaggle")

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "diffusers>=0.32", "transformers", "accelerate",
                "sentencepiece", "imageio", "imageio-ffmpeg"], check=True)

import torch
from diffusers import LTXImageToVideoPipeline
from diffusers.utils import export_to_video
from PIL import Image

t0 = time.time()
ruta_job = glob.glob("/kaggle/input/**/trabajo.json", recursive=True)[0]
carpeta = os.path.dirname(ruta_job)
job = json.load(open(ruta_job))
salida = "/kaggle/working/clips"
os.makedirs(salida, exist_ok=True)

dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
print("GPU:", torch.cuda.get_device_name(0), "| dtype:", dtype, flush=True)
pipe = LTXImageToVideoPipeline.from_pretrained(job.get("modelo", "Lightricks/LTX-Video"), torch_dtype=dtype)
pipe.enable_model_cpu_offload()  # cabe en 16 GB
pipe.vae.enable_tiling()

W, H = job.get("ancho", 512), job.get("alto", 896)
NEG = ("worst quality, inconsistent motion, blurry, jittery, distorted face, deformed hands, extra limbs, "
       "morphing, flickering, text, watermark, static image")
registro = []
for p in job["planos"]:
    if (time.time() - t0) / 60 > job.get("max_minutos", 600):
        print("⏱️ Tiempo agotado, el resto de planos irá con cámara 3D", flush=True)
        break
    ini = time.time()
    img = Image.open(os.path.join(carpeta, p["imagen"])).convert("RGB")
    # recorte 9:16 centrado y al tamaño de trabajo
    r = W / H
    if img.width / img.height > r:
        nw = int(img.height * r); img = img.crop(((img.width - nw) // 2, 0, (img.width + nw) // 2, img.height))
    else:
        nh = int(img.width / r); img = img.crop((0, (img.height - nh) // 2, img.width, (img.height + nh) // 2))
    img = img.resize((W, H), Image.LANCZOS)
    prompt = (f"{p['movimiento']}. Anime style, high quality 2D animation, smooth natural motion, "
              f"consistent character, cinematic lighting. {p.get('escena', '')}")
    estado = "sin intentar"
    # si no cabe en memoria, prueba con clips más cortos (el montador los alarga)
    for nf in [f for f in (job.get("frames", 73), 61, 49) if f <= job.get("frames", 73)]:
        try:
            frames = pipe(image=img, prompt=prompt, negative_prompt=NEG, width=W, height=H,
                          num_frames=nf, num_inference_steps=job.get("pasos", 30),
                          guidance_scale=3.0, decode_timestep=0.05, decode_noise_scale=0.025,
                          generator=torch.Generator("cpu").manual_seed(p["id"])).frames[0]
            export_to_video(frames, os.path.join(salida, f"plano_{p['id']:02d}.mp4"), fps=24)
            estado = f"ok ({nf} frames)"
            break
        except torch.cuda.OutOfMemoryError:
            estado = f"sin memoria con {nf} frames"
            torch.cuda.empty_cache()
        except Exception as e:
            estado = f"error: {str(e)[:200]}"
            break
    seg = time.time() - ini
    registro.append({"id": p["id"], "estado": estado, "segundos": round(seg)})
    print(f"plano {p['id']}: {estado} ({seg:.0f}s)", flush=True)
    torch.cuda.empty_cache()

json.dump({"planos": registro, "minutos": round((time.time() - t0) / 60, 1)}, open("/kaggle/working/registro.json", "w"), indent=2)
print("FIN", flush=True)
