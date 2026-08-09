import os
import torchaudio
from dotenv import load_dotenv
from huggingface_hub import hf_hub_download
from f5_tts.api import F5TTS

load_dotenv()

# 1. Descargar el checkpoint en ruso desde Hugging Face
# Repo: hotstone228/F5-TTS-Russian
print("📥 Загрузка модели F5-TTS-Russian из Hugging Face...")
ckpt_path = hf_hub_download(repo_id="hotstone228/F5-TTS-Russian", filename="model_last.safetensors")
vocab_path = hf_hub_download(repo_id="hotstone228/F5-TTS-Russian", filename="vocab.txt")

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
    print("🔊 Эталонное аудио преобразовано в Mono 24kHz.")
else:
    ref_audio_mono = ref_audio_orig

# 3. Inicializar F5-TTS con el checkpoint de ruso
# IMPORTANTE: Modelos comunitarios fueron entrenados sobre F5TTS_Base
f5tts = F5TTS(model="F5TTS_Base", ckpt_file=ckpt_path, vocab_file=vocab_path)

ref_text = "Hola, este es un ejemplo de mi voz grabado para entrenar el modelo de síntesis de voz F5-TTS en mi computadora."
gen_text = "Привет Хосе! Это сообщение создано с использованием вашего собственного голоса, клонированного локально с помощью F5 TTS. Технология действительно удивительна."

print("🎙️ Генерация клонированного аудио на русском языке...")
f5tts.infer(
    ref_file=ref_audio_mono,
    ref_text=ref_text,
    gen_text=gen_text,
    speed=1.0,
    file_wave="resultado_clonado_ru.wav"
)

print("✅ Аудио успешно сгенерировано в 'resultado_clonado_ru.wav'!")
