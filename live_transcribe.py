import os
import sys
import time
import queue
import threading
import requests
import tempfile
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

API_KEY = os.getenv("API_KEY", "tu_clave_api_aqui")
WHISPER_URL = "http://localhost:8001/v1/audio/transcriptions"
DIARIZATION_URL = "http://localhost:8003/v1/audio/diarize"

# Cola thread-safe para procesar audio en segundo plano sin bloquear el micrófono
audio_queue = queue.Queue()

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

# Detectar la frecuencia de muestreo predeterminada de tu micrófono
try:
    device_info = sd.query_devices(kind='input')
    REC_SAMPLE_RATE = int(device_info['default_samplerate'])
except Exception:
    REC_SAMPLE_RATE = 44100  # Fallback estándar si falla la detección

TARGET_SAMPLE_RATE = 16000  # Frecuencia nativa esperada por Whisper y PyAnnote (16 kHz)
CHANNELS = 1                # Canal único (Mono)
THRESHOLD = 0.02            # Se autocalibrará al inicio
SILENCE_LIMIT = 1.5         # Segundos de silencio continuo antes de considerar que la frase terminó
CHUNK_DURATION = 0.1        # Duración de cada trozo de análisis en segundos

# Estado del grabador
recording_buffer = []
is_speaking = False
silence_counter = 0

# Variables para autocalibración de ruido ambiente
calibration_frames = []
is_calibrated = False
calibration_limit = 15      # 15 chunks de 0.1s = 1.5 segundos de calibración

print("=" * 60)
print("🎙️ Iniciando Asistente de Grabación en Vivo...")
print(f"🔗 Whisper API: {WHISPER_URL}")
print(f"🔗 Diarization API: {DIARIZATION_URL}")
print(f"🎤 Micrófono: {REC_SAMPLE_RATE} Hz (Grabación) -> {TARGET_SAMPLE_RATE} Hz (Procesamiento)")
print(f"🔊 Tiempo de silencio límite: {SILENCE_LIMIT}s")
print("=" * 60)
print("⏳ Por favor, mantente en silencio para calibrar el ruido de fondo...")

def process_audio_chunk(audio_data):
    """
    Guarda el audio capturado, llama a la API de Diarización (8003) y a la de Whisper (8001) en paralelo.
    """
    # Si la frecuencia de grabación es distinta a 16kHz, remuestreamos en memoria
    if REC_SAMPLE_RATE != TARGET_SAMPLE_RATE:
        from scipy import signal
        num_samples = int(len(audio_data) * TARGET_SAMPLE_RATE / REC_SAMPLE_RATE)
        # Asegurar de aplanar el array mono
        audio_data_flat = audio_data.flatten()
        audio_data = signal.resample(audio_data_flat, num_samples)
        # Convertir de vuelta a float32 o el tipo de entrada original
        audio_data = audio_data.astype(np.float32)

    # Crear un archivo temporal WAV
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_filename = temp_file.name
        
    try:
        # Guardar los datos en formato WAV a 16kHz (TARGET_SAMPLE_RATE)
        wav.write(temp_filename, TARGET_SAMPLE_RATE, audio_data)
        
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
    global calibration_frames, is_calibrated, THRESHOLD
    
    if status:
        print(status, file=sys.stderr)
        
    # Calcular volumen eficaz (RMS) del trozo actual
    volume_norm = np.linalg.norm(indata) / np.sqrt(len(indata))
    
    # 1. Fase de Autocalibración Inicial
    if not is_calibrated:
        calibration_frames.append(volume_norm)
        pct = (len(calibration_frames) / calibration_limit) * 100
        print(f"⏳ Calibrando micrófono... {pct:.0f}%", end="\r", flush=True)
        if len(calibration_frames) >= calibration_limit:
            avg_noise = np.mean(calibration_frames)
            # Fijamos el umbral en 2.5 veces el ruido promedio con un piso de 0.015
            THRESHOLD = max(avg_noise * 2.5, 0.015)
            is_calibrated = True
            print(f"\n✅ ¡Calibrado! Ruido promedio: {avg_noise:.4f} | Umbral de voz fijado en: {THRESHOLD:.4f}")
            print("-" * 60)
            print("🔴 Grabador en vivo activo. Empieza a hablar (Presiona Ctrl+C para salir)...")
            print("-" * 60)
        return

    # 2. Bucle principal de Detección de Voz (VAD)
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
            
            # Si el silencio supera el límite, encolamos la frase para procesar
            if silence_counter >= SILENCE_LIMIT:
                print("⏳ (Procesando audio...)", end="\r", flush=True)
                # Concatenar todos los bloques capturados
                audio_data = np.concatenate(recording_buffer, axis=0)
                
                # Encolar el bloque de audio para el hilo trabajador en segundo plano
                audio_queue.put(audio_data)
                
                # Resetear buffers inmediatamente para no bloquear la captura del micrófono
                recording_buffer = []
                is_speaking = False
                silence_counter = 0
                print("🔴 Grabador en vivo activo. Empieza a hablar...", end="\r", flush=True)

def audio_processing_worker():
    """
    Hilo trabajador en segundo plano que procesa las peticiones HTTP a las APIs de
    Diarización y Whisper para no bloquear la captura de audio del micrófono.
    """
    while True:
        try:
            audio_data = audio_queue.get()
            if audio_data is None:
                break
            process_audio_chunk(audio_data)
            audio_queue.task_done()
        except Exception as e:
            print(f"\n❌ Error en el hilo de procesamiento: {e}")

# Iniciar el hilo de procesamiento de audio
worker_thread = threading.Thread(target=audio_processing_worker, daemon=True)
worker_thread.start()

# Iniciar flujo de entrada de audio
try:
    with sd.InputStream(
        samplerate=REC_SAMPLE_RATE,
        channels=CHANNELS,
        callback=audio_callback,
        blocksize=int(REC_SAMPLE_RATE * CHUNK_DURATION)
    ):
        while True:
            time.sleep(0.1)
except KeyboardInterrupt:
    print("\n👋 Grabación finalizada por el usuario.")
    # Parar el hilo trabajador
    audio_queue.put(None)
except Exception as e:
    print(f"\n❌ Error al abrir el stream de audio: {e}")
