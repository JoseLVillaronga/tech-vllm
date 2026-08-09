import os
from dotenv import load_dotenv
from huggingface_hub import hf_hub_download
from f5_tts.api import F5TTS

load_dotenv()

# Descargar/Obtener la ruta local del checkpoint en español desde Hugging Face
print("📥 Cargando modelo F5-Spanish desde Hugging Face...")
ckpt_path = hf_hub_download(repo_id="jpgallegoar/F5-Spanish", filename="model_1200000.safetensors")

# Inicializar F5-TTS con la ruta local descargada
f5tts = F5TTS(ckpt_file=ckpt_path)

ref_audio = "mi_voz.flac"
ref_text = "Hola, este es un ejemplo de mi voz grabado para entrenar el modelo de síntesis de voz F5-TTS en mi computadora."
gen_text = "¡Hola Jose! Este es un mensaje generado usando tu propia voz clonada localmente con F5 TTS."

print("🎙️ Generando audio clonado en español...")
f5tts.infer(
    ref_file=ref_audio,
    ref_text=ref_text,
    gen_text=gen_text,
    speed=1.0,
    file_wave="resultado_clonado.wav"
)

print("✅ ¡Audio generado con éxito en 'resultado_clonado.wav'!")
