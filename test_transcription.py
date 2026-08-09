import base64
import requests

# 1. Cargar y codificar el archivo de audio en Base64
audio_file = "resultado_clonado_fr.wav"
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
# IMPORTANTE: Definimos max_tokens=100 para evitar que el modelo entre en un bucle infinito
payload = {
    "model": "google/gemma-4-E4B-it",
    "max_tokens": 100,
    "temperature": 0.0,  # Temperatura 0 para una transcripción más precisa
    "messages": [{
        "role": "user",
        "content": [
            {"type": "text", "text": "Transcribe exactamente lo que se dice en este audio de voz:"},
            {"type": "input_audio", "input_audio": {"data": audio_b64, "format": "wav"}}
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
