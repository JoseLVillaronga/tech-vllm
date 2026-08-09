import base64
import requests

# 1. Cargar y codificar el archivo de audio en Base64
audio_file = "mi_voz_24k_mono.wav"
print(f"📂 Cargando y codificando '{audio_file}'...")
with open(audio_file, "rb") as f:
    audio_b64 = base64.b64encode(f.read()).decode("utf-8")

# 2. Configurar headers y endpoint del servidor local
url = "http://localhost:8000/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939"
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
