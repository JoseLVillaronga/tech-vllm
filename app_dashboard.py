import os
import re
import sys
import psutil
import requests
import subprocess
from flask import Flask, render_template, request, jsonify, Response
from dotenv import load_dotenv

# Cargar variables del entorno
load_dotenv()

PORT = int(os.getenv("DASHBOARD_PORT", "8004"))
API_KEY = os.getenv("API_KEY", "tu_clave_api_aqui")

app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates"
)

ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")

# Mapeo de nombres de servicios systemd
SERVICES = {
    "gemma": "vllm",
    "whisper": "vllm-whisper",
    "tts": "vllm-tts",
    "diarization": "vllm-diarization"
}

# Puertos locales de cada servicio
SERVICE_PORTS = {
    "gemma": 8000,
    "whisper": 8001,
    "tts": 8002,
    "diarization": 8003
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

def read_env_file():
    """
    Lee las líneas del archivo .env preservando el formato original y comentarios.
    """
    if not os.path.exists(ENV_PATH):
        return []
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        return f.readlines()

def parse_env_to_dict():
    """
    Parsea las variables de entorno en un diccionario simple, ignorando comentarios.
    """
    lines = read_env_file()
    env_vars = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            parts = stripped.split("=", 1)
            key = parts[0].strip()
            val = parts[1].strip()
            # Eliminar comillas externas si existen
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            env_vars[key] = val
    return env_vars

def save_env_from_dict(new_values):
    """
    Guarda las nuevas variables de entorno en el archivo .env,
    preservando el resto de las líneas y comentarios.
    """
    lines = read_env_file()
    updated_lines = []
    keys_written = set()
    
    # Recorrer el archivo original y actualizar claves existentes
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in new_values:
                val = new_values[key]
                # Envolver en comillas si es una cadena de modelo o tiene espacios
                if key in ["MODEL"] or " " in str(val):
                    updated_lines.append(f'{key}="{val}"\n')
                else:
                    updated_lines.append(f'{key}={val}\n')
                keys_written.add(key)
                continue
        updated_lines.append(line)
        
    # Escribir las claves que son totalmente nuevas
    for key, val in new_values.items():
        if key not in keys_written:
            if key in ["MODEL"] or " " in str(val):
                updated_lines.append(f'{key}="{val}"\n')
            else:
                updated_lines.append(f'{key}={val}\n')
                
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)

# --- Rutas de Frontend ---

@app.route("/")
def index():
    return render_template("index.html")

# --- Rutas de API ---

@app.route("/api/status", methods=["GET"])
def api_status():
    """
    Devuelve las métricas del sistema y el estado de los servicios.
    """
    gpu = get_gpu_info()
    
    services_info = {}
    for key, service_name in SERVICES.items():
        services_info[key] = {
            "name": service_name,
            "status": get_service_status(service_name),
            "port": SERVICE_PORTS[key]
        }
        
    return jsonify({
        "system": {
            "cpu": psutil.cpu_percent(),
            "ram": psutil.virtual_memory().percent,
            "gpu_util": gpu["gpu_util"],
            "gpu_temp": gpu["gpu_temp"],
            "vram_total": gpu["total_vram"],
            "vram_used": gpu["used_vram"],
            "vram_percent": round((gpu["used_vram"] / gpu["total_vram"]) * 100, 2)
        },
        "services": services_info
    })

@app.route("/api/service/<service_key>/<action>", methods=["POST"])
def api_control_service(service_key, action):
    """
    Inicia, detiene o reinicia un servicio systemd.
    """
    if service_key not in SERVICES:
        return jsonify({"success": False, "error": "Servicio inválido"}), 400
    if action not in ["start", "stop", "restart"]:
        return jsonify({"success": False, "error": "Acción inválida"}), 400
        
    service_name = SERVICES[service_key]
    success = control_service(service_name, action)
    
    return jsonify({
        "success": success,
        "service": service_key,
        "action": action,
        "new_status": get_service_status(service_name)
    })

@app.route("/api/config", methods=["GET"])
def api_get_config():
    """
    Retorna las variables del archivo .env como un JSON.
    """
    return jsonify(parse_env_to_dict())

@app.route("/api/config", methods=["POST"])
def api_save_config():
    """
    Actualiza el archivo .env con los nuevos valores del formulario.
    """
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "No se recibieron datos"}), 400
        
    try:
        # Guardar en el archivo .env
        save_env_from_dict(data)
        
        # Recargar variables de entorno locales de la app Flask
        load_dotenv(override=True)
        global API_KEY
        API_KEY = os.getenv("API_KEY", "tu_clave_api_aqui")
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- Rutas de Pruebas de API (Proxies locales) ---

@app.route("/api/test/chat", methods=["POST"])
def api_test_chat():
    """
    Proxy interactivo para probar el endpoint del Chat de Gemma en puerto 8000.
    """
    current_vars = parse_env_to_dict()
    api_key = current_vars.get("API_KEY", API_KEY)
    
    data = request.json
    prompt = data.get("prompt", "¡Hola!")
    model = current_vars.get("MODEL", "google/gemma-4-E4B-it")
    
    url = f"http://localhost:{SERVICE_PORTS['gemma']}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 150
    }
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=30)
        return Response(res.text, status=res.status_code, content_type="application/json")
    except Exception as e:
        return jsonify({"error": f"No se pudo conectar al servicio Gemma (puerto {SERVICE_PORTS['gemma']}): {str(e)}"}), 502

@app.route("/api/test/transcribe", methods=["POST"])
def api_test_transcribe():
    """
    Proxy para subir un audio y obtener la transcripción vía Whisper (puerto 8001).
    """
    current_vars = parse_env_to_dict()
    api_key = current_vars.get("API_KEY", API_KEY)
    
    if "file" not in request.files:
        return jsonify({"error": "No se subió ningún archivo"}), 400
        
    audio_file = request.files["file"]
    url = f"http://localhost:{SERVICE_PORTS['whisper']}/v1/audio/transcriptions"
    
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    files = {
        "file": (audio_file.filename, audio_file.read(), audio_file.content_type or "audio/wav")
    }
    data = {
        "model": "openai/whisper-large-v3-turbo"
    }
    
    try:
        res = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        return Response(res.text, status=res.status_code, content_type="application/json")
    except Exception as e:
        return jsonify({"error": f"No se pudo conectar al servicio Whisper (puerto {SERVICE_PORTS['whisper']}): {str(e)}"}), 502

@app.route("/api/test/speech", methods=["POST"])
def api_test_speech():
    """
    Proxy para generar voz mediante F5-TTS (puerto 8002) y transmitir el archivo de audio resultante.
    """
    current_vars = parse_env_to_dict()
    api_key = current_vars.get("API_KEY", API_KEY)
    
    data = request.json
    text = data.get("text", "Hola, esta es una prueba de voz.")
    voice = data.get("voice", "alloy")
    
    url = f"http://localhost:{SERVICE_PORTS['tts']}/v1/audio/speech"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": "tts-1",
        "input": text,
        "voice": voice,
        "response_format": "mp3"
    }
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=60)
        if res.status_code == 200:
            return Response(res.content, mimetype="audio/mpeg")
        else:
            return Response(res.text, status=res.status_code, content_type="application/json")
    except Exception as e:
        return jsonify({"error": f"No se pudo conectar al servicio F5-TTS (puerto {SERVICE_PORTS['tts']}): {str(e)}"}), 502

@app.route("/api/test/diarize", methods=["POST"])
def api_test_diarize():
    """
    Proxy para subir un audio y obtener la diarización de hablantes vía PyAnnote (puerto 8003).
    """
    current_vars = parse_env_to_dict()
    api_key = current_vars.get("API_KEY", API_KEY)
    
    if "file" not in request.files:
        return jsonify({"error": "No se subió ningún archivo"}), 400
        
    audio_file = request.files["file"]
    url = f"http://localhost:{SERVICE_PORTS['diarization']}/v1/audio/diarize"
    
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    files = {
        "file": (audio_file.filename, audio_file.read(), audio_file.content_type or "audio/wav")
    }
    
    try:
        res = requests.post(url, headers=headers, files=files, timeout=60)
        return Response(res.text, status=res.status_code, content_type="application/json")
    except Exception as e:
        return jsonify({"error": f"No se pudo conectar al servicio de Diarización (puerto {SERVICE_PORTS['diarization']}): {str(e)}"}), 502

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
