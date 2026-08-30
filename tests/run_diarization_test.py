#!/usr/bin/env python3
"""
run_diarization_test.py — Script de prueba rápida para Diarización de Voz (PyAnnote 3.1).
Carga la API Key y configuración de forma segura desde .env (cero credenciales hardcodeadas).

Uso:
    python tests/run_diarization_test.py [ruta_al_audio.wav]
"""
import os
import sys
import json
import requests
from dotenv import load_dotenv

# Cargar .env de forma determinista desde la raíz del proyecto
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_ENV_PATH = os.path.join(_PROJECT_ROOT, ".env")
load_dotenv(_ENV_PATH)

from config import API_KEY, env

GATEWAY_PORT = int(env("DIARIZATION_GATEWAY_PORT", "8003"))
GATEWAY_URL = f"http://127.0.0.1:{GATEWAY_PORT}"
DEFAULT_SAMPLE = os.path.join(_PROJECT_ROOT, "tests", "samples", "sample_dialogue_two_speakers.wav")


def main():
    print("=" * 70)
    print("🎙️  vLLM Suite: Prueba Rápida de Diarización de Hablantes (PyAnnote)")
    print("=" * 70)

    # 1. Validar clave de API cargada desde .env
    if not API_KEY:
        print("❌ Error: No se encontró API_KEY en el archivo .env.")
        sys.exit(1)

    print(f"🔑 API Key cargada desde .env: {API_KEY[:8]}...{API_KEY[-4:]} (Segura / No Hardcodeada)")
    print(f"🌐 Conectando al Gateway en: {GATEWAY_URL}/v1/audio/diarize")

    # 2. Determinar archivo de audio a procesar
    audio_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SAMPLE
    if not os.path.exists(audio_path):
        print(f"❌ Error: El archivo de audio '{audio_path}' no existe.")
        sys.exit(1)

    audio_size_kb = os.path.getsize(audio_path) / 1024
    print(f"📁 Archivo de prueba: {os.path.basename(audio_path)} ({audio_size_kb:.1f} KB)")
    print("\n⏳ Enviando audio al Gateway para diarización...")

    headers = {"Authorization": f"Bearer {API_KEY}"}

    try:
        with open(audio_path, "rb") as f:
            files = {"file": (os.path.basename(audio_path), f, "audio/wav")}
            resp = requests.post(f"{GATEWAY_URL}/v1/audio/diarize", headers=headers, files=files, timeout=45.0)

        if resp.status_code == 200:
            data = resp.json()
            segments = data.get("segments", [])
            print(f"\n✅ Diarización completada exitosamente! Segmentos detectados: {len(segments)}")
            print("-" * 70)
            print(f"{'INICIO':<12} | {'FIN':<12} | {'HABLANTE':<15} | {'DURACIÓN'}")
            print("-" * 70)
            for seg in segments:
                start = seg.get("start", 0)
                end = seg.get("end", 0)
                speaker = seg.get("speaker", "N/D")
                duration = round(end - start, 2)
                print(f"{start:>8.2f} s   | {end:>8.2f} s   | {speaker:<15} | {duration:>6.2f} s")
            print("-" * 70)
        else:
            print(f"\n❌ Error HTTP {resp.status_code}: {resp.text}")
            sys.exit(1)

    except requests.exceptions.ConnectionError:
        print(f"\n❌ Error: No se pudo conectar al Gateway en {GATEWAY_URL}. Asegúrate de que vllm-gateway esté corriendo.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
