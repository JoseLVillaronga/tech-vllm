import os
import sys
import time
import queue
import argparse
import threading
import requests
import tempfile
from datetime import timedelta
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

from config import API_KEY
WHISPER_URL = os.getenv("WHISPER_URL", "http://localhost:8001/v1/audio/transcriptions")
DIARIZATION_URL = os.getenv("DIARIZATION_URL", "http://localhost:8003/v1/audio/diarize")

# Cola thread-safe para procesar audio en segundo plano sin congelar la captura
audio_queue = queue.Queue()

# Verificar dependencias de audio
try:
    import numpy as np
    import sounddevice as sd
    import scipy.io.wavfile as wav
except ImportError:
    print("=" * 70)
    print("❌ Faltan dependencias de audio.")
    print("Para instalar las librerías necesarias, ejecuta:")
    print("  sudo apt update && sudo apt install -y libportaudio2")
    print("  pip install sounddevice numpy scipy requests python-dotenv")
    print("=" * 70)
    sys.exit(1)

def find_system_output_monitor(user_device=None):
    """
    Busca automáticamente el dispositivo 'Monitor' de PulseAudio/PipeWire
    que permite capturar el audio que sale por los altavoces/auriculares.
    """
    devices = sd.query_devices()
    
    if user_device is not None:
        try:
            dev_idx = int(user_device)
            return dev_idx, devices[dev_idx]['name']
        except (ValueError, IndexError):
            # Buscar por subcadena
            for idx, dev in enumerate(devices):
                if user_device.lower() in dev['name'].lower() and dev['max_input_channels'] > 0:
                    return idx, dev['name']

    # Búsqueda automática de fuentes monitor de PulseAudio / ALSA
    monitor_candidates = []
    for idx, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            name_lower = dev['name'].lower()
            if 'monitor' in name_lower or '.monitor' in name_lower:
                monitor_candidates.append((idx, dev['name']))

    if monitor_candidates:
        # Preferir el dispositivo por defecto si existe o el primer monitor disponible
        for idx, name in monitor_candidates:
            if 'default' in name.lower() or 'analog-stereo.monitor' in name.lower():
                return idx, name
        return monitor_candidates[0][0], monitor_candidates[0][1]

    # Fallback al dispositivo de entrada por defecto
    default_in = sd.default.device[0]
    return default_in, devices[default_in]['name']

def format_timestamp_txt(seconds):
    """Formato HH:MM:SS para subtítulo TXT simple."""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def format_timestamp_srt(seconds):
    """Formato HH:MM:SS,mmm para subtítulos estándar SRT."""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

# Diccionario dinámico para mapear nombres de hablantes (SPEAKER_00 -> Hablante A)
speaker_map = {}
speaker_counter = 0

def get_speaker_label(raw_speaker):
    global speaker_counter
    if not raw_speaker or raw_speaker == "DESCONOCIDO":
        return "Hablante ?"
    if raw_speaker not in speaker_map:
        label_char = chr(ord('A') + speaker_counter)
        speaker_map[raw_speaker] = f"Hablante {label_char}"
        speaker_counter += 1
    return speaker_map[raw_speaker]

# Contador global de bloques SRT
srt_index = 1

def process_audio_chunk(task_info, output_txt_path, output_srt_path):
    global srt_index
    audio_data, start_sec, end_sec, rec_rate, target_rate = task_info

    # Remuestrear a 16kHz si la frecuencia del dispositivo es diferente
    if rec_rate != target_rate:
        from scipy import signal
        num_samples = int(len(audio_data) * target_rate / rec_rate)
        audio_data_flat = audio_data.flatten()
        audio_data = signal.resample(audio_data_flat, num_samples).astype(np.float32)

    # Crear archivo temporal WAV
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_filename = temp_file.name

    try:
        wav.write(temp_filename, target_rate, audio_data)
        headers = {"Authorization": f"Bearer {API_KEY}"}

        # 1. Diarización de Hablante (PyAnnote 8003)
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
                    diarize_speaker = segments[0].get("speaker", "SPEAKER_00")
        except Exception as e:
            print(f"\n⚠️ Error en diarización: {e}")

        # 2. Transcripción de Voz (Whisper 8001)
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

        # 3. Formatear y guardar resultado si hay texto
        if transcript_text:
            speaker_label = get_speaker_label(diarize_speaker)
            time_txt = format_timestamp_txt(start_sec)
            srt_start = format_timestamp_srt(start_sec)
            srt_end = format_timestamp_srt(end_sec)

            # Mostrar en pantalla
            console_msg = f"🎬 [{time_txt}] [{speaker_label}]: \"{transcript_text}\""
            print(f"\n{console_msg}")
            print("-" * 65)

            # A. Escribir en subtitulos.txt
            if output_txt_path:
                with open(output_txt_path, "a", encoding="utf-8") as f_txt:
                    f_txt.write(f"[{time_txt}] [{speaker_label}]: {transcript_text}\n")

            # B. Escribir en subtitulos.srt
            if output_srt_path:
                with open(output_srt_path, "a", encoding="utf-8") as f_srt:
                    f_srt.write(f"{srt_index}\n")
                    f_srt.write(f"{srt_start} --> {srt_end}\n")
                    f_srt.write(f"[{speaker_label}]: {transcript_text}\n\n")
                srt_index += 1

    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

def audio_processing_worker(output_txt_path, output_srt_path):
    while True:
        try:
            task_info = audio_queue.get()
            if task_info is None:
                break
            process_audio_chunk(task_info, output_txt_path, output_srt_path)
            audio_queue.task_done()
        except Exception as e:
            print(f"\n❌ Error en hilo trabajador: {e}")

def main():
    parser = argparse.ArgumentParser(description="Subtitulador en Vivo desde la Salida de Audio del Sistema (Películas/Vídeos).")
    parser.add_argument("--device", type=str, default=None, help="Índice o nombre del dispositivo de audio monitor.")
    parser.add_argument("--out-txt", nargs="?", const="subtitulos.txt", default="subtitulos.txt", help="Ruta del archivo de salida .txt (por defecto subtitulos.txt).")
    parser.add_argument("--out-srt", nargs="?", const="subtitulos.srt", default="subtitulos.srt", help="Ruta del archivo de subtítulos .srt (por defecto subtitulos.srt).")
    parser.add_argument("--silence-limit", type=float, default=1.2, help="Segundos de silencio para pausar la frase.")
    args = parser.parse_args()

    # Seleccionar dispositivo monitor
    dev_idx, dev_name = find_system_output_monitor(args.device)
    dev_info = sd.query_devices(dev_idx)
    rec_sample_rate = int(dev_info['default_samplerate'])
    target_sample_rate = 16000
    channels = 1
    chunk_duration = 0.1

    print("=" * 70)
    print("🎬 SUBTITULADOR EN VIVO PARA PELÍCULAS Y AUDIO DE SISTEMA")
    print("=" * 70)
    print(f"🎧 Escuchando Salida de Audio: Dispositivo [{dev_idx}] {dev_name}")
    print(f"🎤 Tasa de Captura: {rec_sample_rate} Hz -> Procesamiento: {target_sample_rate} Hz")
    print(f"📄 Archivo TXT: {args.out_txt}")
    print(f"🎬 Archivo SRT: {args.out_srt}")
    print(f"🔗 Whisper: {WHISPER_URL} | Diarización: {DIARIZATION_URL}")
    print("=" * 70)
    print("⏳ Calibrando nivel de volumen del sistema...")

    # Inicializar archivos vacíos/limpios al arrancar
    if args.out_txt:
        with open(args.out_txt, "w", encoding="utf-8") as f:
            f.write(f"=== SUBTÍTULOS GENERADOS EN VIVO ({time.strftime('%Y-%m-%d %H:%M:%S')}) ===\n\n")

    if args.out_srt:
        with open(args.out_srt, "w", encoding="utf-8") as f:
            f.write("")  # SRT limpio

    # Iniciar hilo de procesamiento en segundo plano
    worker_thread = threading.Thread(
        target=audio_processing_worker,
        args=(args.out_txt, args.out_srt),
        daemon=True
    )
    worker_thread.start()

    # Variables de captura
    start_time = time.time()
    recording_buffer = []
    is_speaking = False
    silence_counter = 0
    phrase_start_sec = 0.0

    calibration_frames = []
    is_calibrated = False
    calibration_limit = 15
    threshold = 0.015

    def audio_callback(indata, frames, callback_time, status):
        nonlocal is_speaking, recording_buffer, silence_counter, phrase_start_sec
        nonlocal calibration_frames, is_calibrated, threshold

        if status:
            print(status, file=sys.stderr)

        volume_norm = np.linalg.norm(indata) / np.sqrt(len(indata))
        current_elapsed = time.time() - start_time

        # 1. Calibración inicial
        if not is_calibrated:
            calibration_frames.append(volume_norm)
            if len(calibration_frames) >= calibration_limit:
                avg_noise = np.mean(calibration_frames)
                threshold = max(avg_noise * 2.2, 0.012)
                is_calibrated = True
                print(f"✅ ¡Calibrado! Umbral de audio fijado en: {threshold:.4f}")
                print("▶️ Reproduce la película. Los subtítulos aparecerán a continuación...")
                print("-" * 70)
            return

        # 2. Detección de voz/diálogo
        if volume_norm > threshold:
            if not is_speaking:
                is_speaking = True
                phrase_start_sec = current_elapsed
                print("🔊 (Escuchando diálogo...)", end="\r", flush=True)
            recording_buffer.append(indata.copy())
            silence_counter = 0
        else:
            if is_speaking:
                recording_buffer.append(indata.copy())
                silence_counter += chunk_duration

                if silence_counter >= args.silence_limit:
                    phrase_end_sec = current_elapsed - silence_counter
                    if phrase_end_sec <= phrase_start_sec:
                        phrase_end_sec = phrase_start_sec + 0.5

                    audio_data = np.concatenate(recording_buffer, axis=0)
                    task_info = (audio_data, phrase_start_sec, phrase_end_sec, rec_sample_rate, target_sample_rate)
                    
                    audio_queue.put(task_info)

                    recording_buffer = []
                    is_speaking = False
                    silence_counter = 0
                    print("▶️ Escuchando salida de audio...", end="\r", flush=True)

    try:
        with sd.InputStream(
            device=dev_idx,
            samplerate=rec_sample_rate,
            channels=channels,
            callback=audio_callback,
            blocksize=int(rec_sample_rate * chunk_duration)
        ):
            while True:
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\n👋 Generación de subtítulos finalizada por el usuario.")
        print(f"💾 Subtítulos guardados en: '{args.out_txt}' y '{args.out_srt}'")
        audio_queue.put(None)
    except Exception as e:
        print(f"\n❌ Error en el stream de audio: {e}")

if __name__ == "__main__":
    main()
