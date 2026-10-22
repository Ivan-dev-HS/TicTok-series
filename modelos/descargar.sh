#!/usr/bin/env bash
# Descarga los modelos gratuitos (voz de respaldo, profundidad y recorte de personajes).
set -e
cd "$(dirname "$0")"
dl() { [ -f "$2" ] || curl -sSL --retry 3 -o "$2" "$1"; }
dl https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx kokoro.onnx
dl https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin voices.bin
dl https://github.com/fabio-sim/Depth-Anything-ONNX/releases/download/v2.0.0/depth_anything_v2_vits.onnx depth_anything_v2_vits.onnx
dl https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-anime.onnx isnet-anime.onnx
ls -la
