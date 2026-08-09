import os
import base64
import requests
import torchaudio
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# 1. Cargar, re-muestrear a 16kHz (frecuencia nativa de Gemma 4) y codificar a Base64
audio_file = "mi_voz_24k_mono.wav"
temp_file = "audio_16k.wav"

if os.path.exists(audio_file):
    print(f"🔄 Re-muestreando '{audio_file}' a 16kHz mono...")
    waveform, sr = torchaudio.load(audio_file)
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    if sr != 16000:
        resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16000)
        waveform = resampler(waveform)
    torchaudio.save(temp_file, waveform, 16000)
else:
    print(f"❌ No se encontró el archivo '{audio_file}'")
    exit(1)

print(f"📂 Cargando y codificando '{temp_file}'...")
with open(temp_file, "rb") as f:
    audio_b64 = base64.b64encode(f.read()).decode("utf-8")

API_KEY = os.getenv("API_KEY", "tu_clave_api_aqui")
url = "http://localhost:8000/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

# 3. Payload
# IMPORTANTE: Definimos max_tokens=100 para evitar bucles infinitos.
# Colocamos el audio_url con formato data URI después del texto del prompt.
audio_data_url = f"data:audio/wav;base64,{audio_b64}"

payload = {
    "model": "google/gemma-4-E4B-it",
    "max_tokens": 100,
    "temperature": 0.0,
    "messages": [{
        "role": "user",
        "content": [
            {"type": "text", "text": "Transcribe exactamente lo que se dice en este audio de voz:"},
            {
                "type": "audio_url",
                "audio_url": {"url": audio_data_url}
            }
        ]
    }]
}

print("🎙️ Enviando audio a vLLM para transcripción...")
try:
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    result = response.json()
    print("\n📝 Transcripción generada:")
    print("-" * 40)
    print(result["choices"][0]["message"]["content"])
    print("-" * 40)
except Exception as e:
    print(f"❌ Error al conectar con el servidor: {e}")
