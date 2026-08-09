import os
import torchaudio
from dotenv import load_dotenv
from f5_tts.api import F5TTS

load_dotenv()

# 1. Modelo base oficial SWivid/F5-TTS (Inglés y Chino)
# Se descarga automáticamente al no especificar ckpt_file
print("📥 Cargando modelo base F5-TTS (Inglés/Chino) desde Hugging Face...")

# 2. Pre-procesar audio a Mono 24kHz para optimizar la alineación
ref_audio_orig = "mi_voz.flac"
ref_audio_mono = "mi_voz_24k_mono.wav"

if os.path.exists(ref_audio_orig):
    waveform, sr = torchaudio.load(ref_audio_orig)
    # Convertir a mono si es estéreo
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    # Resamplear a 24000Hz si es necesario
    if sr != 24000:
        resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=24000)
        waveform = resampler(waveform)
    torchaudio.save(ref_audio_mono, waveform, 24000)
    print("🔊 Audio de referencia convertido a Mono 24kHz.")
else:
    ref_audio_mono = ref_audio_orig

# 3. Inicializar F5-TTS con el modelo base oficial (F5TTS_v1_Base)
f5tts = F5TTS(model="F5TTS_v1_Base")

ref_text = "Hola, este es un ejemplo de mi voz grabado para entrenar el modelo de síntesis de voz F5-TTS en mi computadora."
gen_text = "Hello Jose! This is a message generated using your own voice cloned locally with F5 TTS. The technology is truly amazing."

print("🎙️ Generating cloned audio in English...")
f5tts.infer(
    ref_file=ref_audio_mono,
    ref_text=ref_text,
    gen_text=gen_text,
    speed=1.0,
    file_wave="resultado_clonado_en.wav"
)

print("✅ Audio generated successfully in 'resultado_clonado_en.wav'!")
