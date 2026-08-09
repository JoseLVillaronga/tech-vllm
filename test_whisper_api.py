import os
import requests

# 1. Configurar el endpoint y token del servicio de Whisper
url = "http://localhost:8001/v1/audio/transcriptions"
headers = {
    "Authorization": "Bearer token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939"
}

# 2. Elegir archivo de audio local
audio_file = "mi_voz_24k_mono.wav"
if not os.path.exists(audio_file):
    audio_file = "resultado_clonado_fr.wav"

print(f"📂 Cargando archivo: '{audio_file}'")

# 3. Preparar la petición multipart/form-data
# Whisper en vLLM requiere especificar el modelo y el idioma (es, fr, en, etc.)
files = {
    "file": (os.path.basename(audio_file), open(audio_file, "rb"), "audio/wav")
}
data = {
    "model": "openai/whisper-large-v3-turbo",
    "language": "es" if "mi_voz" in audio_file else "fr",
    "response_format": "verbose_json"
}

print(f"🎙️ Enviando petición de transcripción al endpoint en puerto 8001...")
try:
    response = requests.post(url, headers=headers, files=files, data=data)
    response.raise_for_status()
    result = response.json()
    
    print("\n📝 Transcripción exitosa:")
    print("-" * 50)
    print(result.get("text", ""))
    print("-" * 50)
except Exception as e:
    print(f"❌ Error al conectar con el servicio: {e}")
    if 'response' in locals() and response.text:
        print(f"Detalle del servidor: {response.text}")
