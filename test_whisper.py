import os
from faster_whisper import WhisperModel

# 1. Definir el modelo convertido a CTranslate2 (CT2) de Whisper-large-v3-turbo
# Es la versión optimizada de Whisper Large v3 (4 capas decoder en lugar de 32)
model_id = "deepdml/faster-whisper-large-v3-turbo-ct2"
audio_file = "mi_voz_24k_mono.wav"

if not os.path.exists(audio_file):
    # Si no existe, usamos el de francés para probar la traducción
    audio_file = "resultado_clonado_fr.wav"

print(f"📥 Cargando model '{model_id}' en GPU...")
# Cargamos en float16 para máximo rendimiento y mínimo consumo de VRAM (~1.5 GB)
model = WhisperModel(model_id, device="cuda", compute_type="float16")

print(f"🎙️ Procesando audio: '{audio_file}'")

# --- Prueba A: Transcripción NATIVA (Transcribe) ---
print("\n📝 [A] Transcribiendo en su idioma original...")
segments_trans, info_trans = model.transcribe(audio_file, beam_size=5, task="transcribe")

print(f"🔍 Idioma detectado: {info_trans.language} (probabilidad: {info_trans.language_probability:.2f})")
print("Texto transcrito:")
print("-" * 50)
for segment in segments_trans:
    print(f"[{segment.start:.2f}s -> {segment.end:.2f}s]: {segment.text}")
print("-" * 50)


# --- Prueba B: Traducción NATIVA (Translate - Traduce cualquier idioma al Inglés) ---
print("\n🌍 [B] Traduciendo directamente al Inglés (al vuelo)...")
segments_trans_en, info_trans_en = model.transcribe(audio_file, beam_size=5, task="translate")

print("Texto traducido al Inglés:")
print("-" * 50)
for segment in segments_trans_en:
    print(f"[{segment.start:.2f}s -> {segment.end:.2f}s]: {segment.text}")
print("-" * 50)
