import os
import sys
import time
import requests
import tempfile
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

API_KEY = os.getenv("API_KEY", "token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939")
WHISPER_URL = "http://localhost:8001/v1/audio/transcriptions"
DIARIZATION_URL = "http://localhost:8003/v1/audio/diarize"

# 1. Verificar librerías para captura de audio
try:
    import numpy as np
    import sounddevice as sd
    import scipy.io.wavfile as wav
except ImportError:
    print("=" * 70)
    print("❌ Faltan dependencias para grabar audio desde el micrófono.")
    print("Para instalar las librerías necesarias, ejecuta:")
    print("  1. Instalar PortAudio del sistema:  sudo apt update && sudo apt install -y libportaudio2")
    print("  2. Instalar paquetes de Python:     pip install sounddevice numpy scipy")
    print("=" * 70)
    sys.exit(1)

# Configuración del micrófono y detección de silencio
SAMPLE_RATE = 16000     # Frecuencia nativa de Whisper (16 kHz)
CHANNELS = 1            # Canal único (Mono)
THRESHOLD = 0.02        # Umbral de volumen para detectar voz (ajustar si tu micrófono es muy sensible)
SILENCE_LIMIT = 1.5     # Segundos de silencio continuo antes de considerar que la frase terminó
CHUNK_DURATION = 0.1    # Duración de cada trozo de análisis en segundos

# Estado del grabador
recording_buffer = []
is_speaking = False
silence_counter = 0

print("=" * 60)
print("🎙️ Iniciando Asistente de Grabación en Vivo...")
print(f"🔗 Whisper API: {WHISPER_URL}")
print(f"🔗 Diarization API: {DIARIZATION_URL}")
print(f"🔊 Umbral de Voz: {THRESHOLD} | Tiempo de silencio límite: {SILENCE_LIMIT}s")
print("=" * 60)
print("🔴 Grabador en vivo activo. Empieza a hablar (Presiona Ctrl+C para salir)...")
print("-" * 60)

def process_audio_chunk(audio_data):
    """
    Guarda el audio capturado, llama a la API de Diarización (8003) y a la de Whisper (8001) en paralelo.
    """
    # Crear un archivo temporal WAV
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_filename = temp_file.name
        
    try:
        # Guardar los datos en formato WAV a 16kHz
        wav.write(temp_filename, SAMPLE_RATE, audio_data)
        
        headers = {"Authorization": f"Bearer {API_KEY}"}
        
        # A. Llamar a la API de Diarización (Detección de Hablante)
        diarize_speaker = "DESCONOCIDO"
        try:
            with open(temp_filename, "rb") as f:
                res_diarize = requests.post(
                    DIARIZATION_URL, 
                    headers=headers, 
                    files={"file": (os.path.basename(temp_filename), f, "audio/wav")}
                )
            if res_diarize.status_code == 200:
                segments = res_diarize.json().get("segments", [])
                if segments:
                    # Tomamos el hablante con más presencia en el segmento
                    diarize_speaker = segments[0].get("speaker", "SPEAKER_00")
        except Exception as e:
            print(f"\n⚠️ Error en diarización: {e}")
            
        # B. Llamar a la API de Transcripción (Whisper)
        transcript_text = ""
        try:
            with open(temp_filename, "rb") as f:
                res_transcribe = requests.post(
                    WHISPER_URL,
                    headers=headers,
                    files={"file": (os.path.basename(temp_filename), f, "audio/wav")},
                    data={"model": "openai/whisper-large-v3-turbo"}
                )
            if res_transcribe.status_code == 200:
                transcript_text = res_transcribe.json().get("text", "").strip()
        except Exception as e:
            print(f"\n⚠️ Error en transcripción: {e}")

        # Mostrar el resultado final
        if transcript_text:
            # Reemplazar SPEAKER_00 por etiquetas amigables
            speaker_label = "Hablante A" if diarize_speaker == "SPEAKER_00" else "Hablante B"
            print(f"🗣️  [{speaker_label}]: \"{transcript_text}\"")
            print("-" * 50)
            
    finally:
        # Limpiar archivo temporal
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

def audio_callback(indata, frames, callback_time, status):
    """
    Callback del stream de sounddevice. Se ejecuta de forma continua analizando el volumen.
    """
    global is_speaking, recording_buffer, silence_counter
    
    if status:
        print(status, file=sys.stderr)
        
    # Calcular volumen eficaz (RMS) del trozo actual
    volume_norm = np.linalg.norm(indata) / np.sqrt(len(indata))
    
    if volume_norm > THRESHOLD:
        # Se detecta voz
        if not is_speaking:
            is_speaking = True
            print("🎤 (Hablando...)", end="\r", flush=True)
        recording_buffer.append(indata.copy())
        silence_counter = 0
    else:
        # Se detecta silencio
        if is_speaking:
            recording_buffer.append(indata.copy())
            silence_counter += CHUNK_DURATION
            
            # Si el silencio supera el límite, procesamos la frase
            if silence_counter >= SILENCE_LIMIT:
                print("⏳ (Procesando audio...)", end="\r", flush=True)
                # Concatenar todos los bloques capturados
                audio_data = np.concatenate(recording_buffer, axis=0)
                
                # Procesar audio de forma síncrona
                process_audio_chunk(audio_data)
                
                # Resetear buffers
                recording_buffer = []
                is_speaking = False
                silence_counter = 0
                print("🔴 Grabador en vivo activo. Empieza a hablar...", end="\r", flush=True)

# Iniciar flujo de entrada de audio
try:
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        callback=audio_callback,
        blocksize=int(SAMPLE_RATE * CHUNK_DURATION)
    ):
        while True:
            time.sleep(0.1)
except KeyboardInterrupt:
    print("\n👋 Grabación finalizada por el usuario.")
except Exception as e:
    print(f"\n❌ Error al abrir el stream de audio: {e}")
