import os
import torchaudio
from dotenv import load_dotenv
from huggingface_hub import hf_hub_download
from f5_tts.api import F5TTS

load_dotenv()

# 1. Descargar el checkpoint en japonés desde Hugging Face
# Repo: Jmica/F5TTS (requiere vocab_japanese.txt específico)
print("📥 Hugging Faceから F5-TTS-Japanese モデルをロード中...")
ckpt_path = hf_hub_download(repo_id="Jmica/F5TTS", filename="JA_21999120/model_21999120.pt")
vocab_path = hf_hub_download(repo_id="Jmica/F5TTS", filename="JA_21999120/vocab_japanese.txt")

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
    print("🔊 リファレンスオーディオをMono 24kHzに変換しました。")
else:
    ref_audio_mono = ref_audio_orig

# 3. Inicializar F5-TTS con el checkpoint de japonés
# IMPORTANTE: Modelos comunitarios fueron entrenados sobre F5TTS_Base
f5tts = F5TTS(model="F5TTS_Base", ckpt_file=ckpt_path, vocab_file=vocab_path)

ref_text = "Hola, este es un ejemplo de mi voz grabado para entrenar el modelo de síntesis de voz F5-TTS en mi computadora."
gen_text = "こんにちは、ホセです。これはF5 TTSを使ってローカルでクローンされたあなた自身の声で生成されたメッセージです。このテクノロジーは本当に素晴らしいです。"

print("🎙️ 日本語でクローンされたオーディオを生成中...")
f5tts.infer(
    ref_file=ref_audio_mono,
    ref_text=ref_text,
    gen_text=gen_text,
    speed=1.0,
    file_wave="resultado_clonado_ja.wav"
)

print("✅ オーディオが正常に生成されました 'resultado_clonado_ja.wav'!")
