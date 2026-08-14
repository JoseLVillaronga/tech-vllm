import os
import re
import sys
import psutil
import requests
import subprocess
import uuid
import torchaudio
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, Response
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId

# Cargar variables del entorno
load_dotenv()

# Helper de conexión a MongoDB
def get_db():
    user = os.getenv("MONGO_USER", "admin")
    password = os.getenv("MONGO_PASS", "joseMDB365$")
    host = os.getenv("MONGO_HOST", "127.0.0.1")
    db_name = os.getenv("MONGO_DB", "vllm")
    uri = f"mongodb://{user}:{password}@{host}:27017/{db_name}?authSource=admin"
    client = MongoClient(uri, serverSelectionTimeoutMS=2000)
    return client[db_name]

# Helper para re-muestrear audio a 24kHz mono (esperado por F5-TTS)
def resample_audio_to_24k_mono(input_path, output_path):
    try:
        waveform, sample_rate = torchaudio.load(input_path)
        # Convertir a mono si es estéreo
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        # Re-muestrear a 24000 Hz si es diferente
        if sample_rate != 24000:
            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=24000)
            waveform = resampler(waveform)
        torchaudio.save(output_path, waveform, 24000)
        return True
    except Exception as e:
        print(f"Error re-muestreando audio {input_path} -> {output_path}: {e}")
        return False

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

# Puertos internos de los motores reales detrás del Gateway
BACKEND_PORTS = {
    "gemma": int(os.getenv("GEMMA_BACKEND_PORT", "18000")),
    "whisper": int(os.getenv("WHISPER_BACKEND_PORT", "18001")),
    "tts": int(os.getenv("TTS_BACKEND_PORT", "18002")),
    "diarization": int(os.getenv("DIARIZATION_BACKEND_PORT", "18003"))
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

# Inicializar la base de datos de telemetría y crear índice TTL de 7 días
def init_db_telemetry():
    try:
        db = get_db()
        db.telemetry_history.create_index("timestamp", expireAfterSeconds=604800)
        print("💾 MongoDB: Índice TTL de 7 días configurado en telemetry_history.")
    except Exception as e:
        print(f"⚠️ Error al configurar índice TTL en MongoDB: {e}", file=sys.stderr)

# Hilo recolector de telemetría histórica (muestreo cada 60s)
def start_telemetry_collector():
    def telemetry_loop():
        # Esperar 5s de calentamiento inicial
        time.sleep(5)
        print("📊 Recolector de Telemetría Histórica Iniciado (muestreo cada 60s).")
        while True:
            try:
                # 1. Obtener info de GPU
                gpu = get_gpu_info()
                gpu_util = gpu.get("gpu_util", 0) if gpu else 0
                gpu_temp = gpu.get("gpu_temp", 0) if gpu else 0
                vram_used = gpu.get("used_vram", 0) / 1024.0 if gpu else 0 # Convertir a GB
                vram_total = gpu.get("total_vram", 0) / 1024.0 if gpu else 0
                
                # 2. Obtener info de CPU y RAM
                cpu_util = psutil.cpu_percent()
                ram = psutil.virtual_memory()
                ram_util = ram.percent
                
                # 3. Obtener estado de los servicios
                services_status = {}
                for key, svc_name in SERVICES.items():
                    services_status[key] = get_service_status(svc_name)
                    
                # 4. Registrar en MongoDB
                db = get_db()
                db.telemetry_history.insert_one({
                    "timestamp": datetime.utcnow(),
                    "cpu": cpu_util,
                    "ram": ram_util,
                    "gpu_util": gpu_util,
                    "gpu_temp": gpu_temp,
                    "vram_used": round(vram_used, 2),
                    "vram_total": round(vram_total, 2),
                    "services": services_status
                })
            except Exception as ex:
                print(f"⚠️ Error en bucle de telemetría: {ex}", file=sys.stderr)
            time.sleep(60)

    t = threading.Thread(target=telemetry_loop, daemon=True)
    t.start()

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

@app.route("/favicon.ico")
def favicon():
    return app.send_static_file("favicon.svg")

# --- Rutas de API ---

# Gestión de voces clonadas y perfiles en MongoDB

@app.route("/api/voices", methods=["GET"])
def api_get_voices():
    try:
        db = get_db()
        voices = list(db.reference_voices.find())
        result = []
        for v in voices:
            result.append({
                "id": str(v["_id"]),
                "name": v.get("name", "Sin nombre"),
                "description": v.get("description", ""),
                "text": v.get("text", ""),
                "audio_path": v.get("audio_path", ""),
                "audio_url": v.get("audio_path", "").replace("/home/jose/vllm", ""),
                "is_active": v.get("is_active", False)
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/voices", methods=["POST"])
def api_create_voice():
    try:
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        text = request.form.get("text", "").strip()
        
        if not name or not text:
            return jsonify({"error": "El nombre y el texto de referencia son obligatorios"}), 400
            
        if "file" not in request.files:
            return jsonify({"error": "El archivo de audio es obligatorio"}), 400
            
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No se seleccionó ningún archivo"}), 400
            
        upload_dir = "/home/jose/vllm/static/audio/clones"
        os.makedirs(upload_dir, exist_ok=True)
        
        temp_ext = os.path.splitext(file.filename)[1] or ".wav"
        temp_filename = f"temp_{uuid.uuid4().hex}{temp_ext}"
        temp_path = os.path.join(upload_dir, temp_filename)
        file.save(temp_path)
        
        final_filename = f"voice_{uuid.uuid4().hex}.wav"
        final_path = os.path.join(upload_dir, final_filename)
        
        success = resample_audio_to_24k_mono(temp_path, final_path)
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        if not success:
            return jsonify({"error": "Error al procesar y re-muestrear el archivo de audio"}), 500
            
        db = get_db()
        has_voices = db.reference_voices.count_documents({}) > 0
        is_active = not has_voices  # Activa si es la primera
        
        if is_active:
            db.reference_voices.update_many({}, {"$set": {"is_active": False}})
            
        voice_id = db.reference_voices.insert_one({
            "name": name,
            "description": description,
            "text": text,
            "audio_path": final_path,
            "is_active": is_active
        }).inserted_id
        
        return jsonify({
            "message": "Perfil de voz creado con éxito",
            "id": str(voice_id),
            "is_active": is_active
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/voices/<voice_id>", methods=["PUT"])
def api_update_voice(voice_id):
    try:
        data = request.json or {}
        name = data.get("name", "").strip()
        description = data.get("description", "").strip()
        text = data.get("text", "").strip()
        
        if not name or not text:
            return jsonify({"error": "El nombre y el texto de referencia son obligatorios"}), 400
            
        db = get_db()
        res = db.reference_voices.update_one(
            {"_id": ObjectId(voice_id)},
            {"$set": {
                "name": name,
                "description": description,
                "text": text
            }}
        )
        
        if res.matched_count == 0:
            return jsonify({"error": "Perfil de voz no encontrado"}), 404
            
        return jsonify({"message": "Perfil de voz actualizado con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/voices/<voice_id>/activate", methods=["POST"])
def api_activate_voice(voice_id):
    try:
        db = get_db()
        voice = db.reference_voices.find_one({"_id": ObjectId(voice_id)})
        if not voice:
            return jsonify({"error": "Perfil de voz no encontrado"}), 404
            
        db.reference_voices.update_many({}, {"$set": {"is_active": False}})
        db.reference_voices.update_one({"_id": ObjectId(voice_id)}, {"$set": {"is_active": True}})
        
        return jsonify({"message": f"Perfil '{voice['name']}' activado con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/voices/<voice_id>", methods=["DELETE"])
def api_delete_voice(voice_id):
    try:
        db = get_db()
        voice = db.reference_voices.find_one({"_id": ObjectId(voice_id)})
        if not voice:
            return jsonify({"error": "Perfil de voz no encontrado"}), 404
            
        audio_path = voice.get("audio_path", "")
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception as e:
                print(f"Error borrando archivo de audio {audio_path}: {e}")
                
        db.reference_voices.delete_one({"_id": ObjectId(voice_id)})
        
        if voice.get("is_active", False):
            first_remaining = db.reference_voices.find_one()
            if first_remaining:
                db.reference_voices.update_one(
                    {"_id": first_remaining["_id"]},
                    {"$set": {"is_active": True}}
                )
                
        return jsonify({"message": "Perfil de voz eliminado con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Gestión de Claves API específicas en MongoDB

@app.route("/api/keys", methods=["GET"])
def api_get_keys():
    try:
        db = get_db()
        keys = list(db.api_keys.find())
        result = []
        for k in keys:
            result.append({
                "id": str(k["_id"]),
                "name": k.get("name", "Sin nombre"),
                "description": k.get("description", ""),
                "key": k.get("key", ""),
                "services": k.get("services", []),
                "expires_at": k.get("expires_at", ""),
                "is_active": k.get("is_active", True)
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/keys", methods=["POST"])
def api_create_key():
    try:
        data = request.json or {}
        name = data.get("name", "").strip()
        description = data.get("description", "").strip()
        services = data.get("services", [])
        expires_at = data.get("expires_at", "").strip()
        
        if not name:
            return jsonify({"error": "El nombre es obligatorio"}), 400
            
        if not services:
            return jsonify({"error": "Debes seleccionar al menos un servicio"}), 400
            
        import secrets
        new_key = "vllm_key_" + secrets.token_hex(20)
        
        expires_val = None
        if expires_at:
            expires_val = expires_at
                
        db = get_db()
        key_id = db.api_keys.insert_one({
            "name": name,
            "description": description,
            "key": new_key,
            "services": services,
            "expires_at": expires_val,
            "is_active": True
        }).inserted_id
        
        return jsonify({
            "message": "Clave API creada con éxito",
            "id": str(key_id),
            "key": new_key
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/keys/<key_id>", methods=["PUT"])
def api_update_key(key_id):
    try:
        data = request.json or {}
        name = data.get("name", "").strip()
        description = data.get("description", "").strip()
        services = data.get("services", [])
        expires_at = data.get("expires_at", "").strip()
        is_active = data.get("is_active", True)
        
        if not name:
            return jsonify({"error": "El nombre es obligatorio"}), 400
            
        if not services:
            return jsonify({"error": "Debes seleccionar al menos un servicio"}), 400
            
        expires_val = None
        if expires_at:
            expires_val = expires_at
            
        db = get_db()
        res = db.api_keys.update_one(
            {"_id": ObjectId(key_id)},
            {"$set": {
                "name": name,
                "description": description,
                "services": services,
                "expires_at": expires_val,
                "is_active": is_active
            }}
        )
        
        if res.matched_count == 0:
            return jsonify({"error": "Clave API no encontrada"}), 404
            
        return jsonify({"message": "Clave API actualizada con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/keys/<key_id>", methods=["DELETE"])
def api_delete_key(key_id):
    try:
        db = get_db()
        res = db.api_keys.delete_one({"_id": ObjectId(key_id)})
        if res.deleted_count == 0:
            return jsonify({"error": "Clave API no encontrada"}), 404
            
        return jsonify({"message": "Clave API eliminada con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Rutas de API ---

@app.route("/api/telemetry/history", methods=["GET"])
def api_telemetry_history():
    try:
        hours = request.args.get("hours", default=6, type=int)
        
        # Calcular fecha de inicio
        start_date = datetime.utcnow() - timedelta(hours=hours)
        
        db = get_db()
        records = list(db.telemetry_history.find(
            {"timestamp": {"$gte": start_date}}
        ).sort("timestamp", 1)) # Orden cronológico ascendente para graficar
        
        result = []
        for r in records:
            ts_str = r["timestamp"].isoformat() + "Z" if isinstance(r["timestamp"], datetime) else r["timestamp"]
            result.append({
                "timestamp": ts_str,
                "cpu": r.get("cpu", 0),
                "ram": r.get("ram", 0),
                "gpu_util": r.get("gpu_util", 0),
                "gpu_temp": r.get("gpu_temp", 0),
                "vram_used": r.get("vram_used", 0),
                "vram_total": r.get("vram_total", 0),
                "services": r.get("services", {})
            })
            
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
    
    url = f"http://127.0.0.1:{BACKEND_PORTS['gemma']}/v1/chat/completions"
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
        return jsonify({"error": f"No se pudo conectar al servicio Gemma (puerto {BACKEND_PORTS['gemma']}): {str(e)}"}), 502

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
    url = f"http://127.0.0.1:{BACKEND_PORTS['whisper']}/v1/audio/transcriptions"
    
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
        return jsonify({"error": f"No se pudo conectar al servicio Whisper (puerto {BACKEND_PORTS['whisper']}): {str(e)}"}), 502

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
    
    url = f"http://127.0.0.1:{BACKEND_PORTS['tts']}/v1/audio/speech"
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
        return jsonify({"error": f"No se pudo conectar al servicio F5-TTS (puerto {BACKEND_PORTS['tts']}): {str(e)}"}), 502

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
    url = f"http://127.0.0.1:{BACKEND_PORTS['diarization']}/v1/audio/diarize"
    
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
        return jsonify({"error": f"No se pudo conectar al servicio de Diarización (puerto {BACKEND_PORTS['diarization']}): {str(e)}"}), 502

if __name__ == "__main__":
    init_db_telemetry()
    start_telemetry_collector()
    app.run(host="0.0.0.0", port=PORT)
