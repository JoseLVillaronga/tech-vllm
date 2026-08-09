import os
import torchaudio
from dotenv import load_dotenv
from huggingface_hub import hf_hub_download
from f5_tts.api import F5TTS

load_dotenv()

# 1. Descargar el checkpoint en alemán desde Hugging Face
# Repo: aihpi/F5-TTS-German (Hasso-Plattner-Institut, Common Voice + Emilia_DE)
print("📥 Laden des F5-TTS-German Modells von Hugging Face...")
ckpt_path = hf_hub_download(repo_id="aihpi/F5-TTS-German", filename="F5TTS_Base/model_420000.safetensors")
vocab_path = hf_hub_download(repo_id="aihpi/F5-TTS-German", filename="vocab.txt")

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
    print("🔊 Referenz-Audio in Mono 24kHz konvertiert.")
else:
    ref_audio_mono = ref_audio_orig

# 3. Inicializar F5-TTS con el checkpoint de alemán
# IMPORTANTE: Modelos comunitarios fueron entrenados sobre F5TTS_Base
f5tts = F5TTS(model="F5TTS_Base", ckpt_file=ckpt_path, vocab_file=vocab_path)

ref_text = "Hola, este es un ejemplo de mi voz grabado para entrenar el modelo de síntesis de voz F5-TTS en mi computadora."
gen_text = "Hallo Jose! Dies ist eine Nachricht, die mit deiner eigenen lokal geklonten Stimme mit F5 TTS generiert wurde. Die Technologie ist wirklich erstaunlich."

print("🎙️ Geklontes Audio auf Deutsch wird generiert...")
f5tts.infer(
    ref_file=ref_audio_mono,
    ref_text=ref_text,
    gen_text=gen_text,
    speed=1.0,
    file_wave="resultado_clonado_de.wav"
)

print("✅ Audio erfolgreich generiert in 'resultado_clonado_de.wav'!")
