import os
import sys
import psutil
import subprocess

# Mapeo de nombres de servicios systemd
SERVICES = {
    "gemma": "vllm",
    "llama": "vllm-llama",
    "whisper": "vllm-whisper",
    "fallback_stt": "vllm-fallback-stt",
    "tts": "vllm-tts",
    "fallback_tts": "vllm-fallback-tts",
    "diarization": "vllm-diarization",
    "embeddings": "vllm-embeddings",
    "image_cuda": "vllm-image",
    "image": "vllm-sd",
    "vision": "vllm-vision",
    "rag_sync": "vllm-rag-sync.timer",
    "gateway": "vllm-gateway",
    "docling": "docling"
}

# Puertos locales de cada servicio
SERVICE_PORTS = {
    "gemma": "8000 / 8010",
    "llama": "8000 / 8010",
    "whisper": 8001,
    "fallback_stt": 18011,
    "tts": 8002,
    "fallback_tts": 18012,
    "diarization": 8003,
    "embeddings": 8005,
    "image_cuda": 8006,
    "image": 8006,
    "vision": 18200,
    "rag_sync": "00:00:00",
    "gateway": "8000-8020",
    "docling": "5020 / 8020"
}

# Puertos internos de los motores reales detrás del Gateway
BACKEND_PORTS = {
    "gemma": int(os.getenv("GEMMA_BACKEND_PORT", "18000")),
    "llama": int(os.getenv("LLAMA_PORT", os.getenv("GEMMA_BACKEND_PORT", "18100"))),
    "whisper": int(os.getenv("WHISPER_BACKEND_PORT", "18001")),
    "fallback_stt": int(os.getenv("STT_FALLBACK_PORT", "18011")),
    "tts": int(os.getenv("TTS_BACKEND_PORT", "18002")),
    "fallback_tts": int(os.getenv("TTS_FALLBACK_PORT", "18012")),
    "diarization": int(os.getenv("DIARIZATION_BACKEND_PORT", "18003")),
    "image_cuda": int(os.getenv("IMAGE_BACKEND_PORT", "18004")),
    "image": int(os.getenv("IMAGE_BACKEND_PORT", "18004")),
    "vision": int(os.getenv("VISION_BACKEND_PORT", "18200")),
    "embeddings": int(os.getenv("EMBEDDINGS_BACKEND_PORT", "18005")),
    "docling": int(os.getenv("DOCLING_BACKEND_PORT", "5020"))
}


def get_gpu_info():
    """
    Obtiene métricas de la GPU utilizando nvidia-smi de forma robusta.
    """
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2
        )
        if res.returncode == 0 and res.stdout.strip():
            parts = [p.strip() for p in res.stdout.strip().split("\n")[0].split(",")]
            return {
                "total_vram": float(parts[0]),
                "used_vram": float(parts[1]),
                "gpu_util": float(parts[2]),
                "gpu_temp": float(parts[3])
            }
    except Exception as e:
        print(f"⚠️ Error al obtener info de GPU: {e}", file=sys.stderr)
    
    # Fallback predeterminado para RTX 3090
    return {
        "total_vram": 24576.0,
        "used_vram": 0.0,
        "gpu_util": 0.0,
        "gpu_temp": 0.0
    }


def get_cpu_temperature():
    """Obtiene la temperatura de la CPU en °C desde los sensores del kernel con cero sobrecarga."""
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return None
        # Sensores comunes de CPU en Linux (AMD k10temp/zenpower, Intel coretemp, ARM cpu_thermal)
        for key in ['k10temp', 'coretemp', 'cpu_thermal', 'zenpower', 'acpitz']:
            if key in temps and temps[key]:
                return round(temps[key][0].current, 1)
        # Fallback a cualquier sensor que contenga 'cpu' o 'temp'
        for key, entries in temps.items():
            if ('cpu' in key.lower() or 'temp' in key.lower()) and entries:
                return round(entries[0].current, 1)
        # Fallback al primer sensor disponible si existe
        first_key = next(iter(temps))
        if temps[first_key]:
            return round(temps[first_key][0].current, 1)
    except Exception:
        pass
    return None


def get_service_status(service_name):
    """
    Obtiene el estado de ejecución de un servicio systemd.
    """
    try:
        res = subprocess.run(
            ["systemctl", "is-active", service_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2
        )
        status = res.stdout.strip()
        # Mapear estados a strings uniformes
        if status == "active":
            return "active"
        elif status == "inactive":
            return "inactive"
        elif status == "failed":
            return "failed"
        else:
            return "inactive"
    except Exception as e:
        print(f"⚠️ Error al comprobar estado de {service_name}: {e}", file=sys.stderr)
        return "unknown"


def control_service(service_name, action):
    """
    Ejecuta comandos de systemctl en segundo plano usando sudo.
    El usuario actual ya tiene configurados privilegios sudo sin contraseña.
    """
    if action not in ["start", "stop", "restart"]:
        return False
    try:
        res = subprocess.run(
            ["sudo", "systemctl", action, service_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        return res.returncode == 0
    except Exception as e:
        print(f"⚠️ Error al ejecutar {action} en {service_name}: {e}", file=sys.stderr)
        return False
