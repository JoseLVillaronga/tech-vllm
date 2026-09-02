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
import ipaddress
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId

# Cargar variables del entorno
load_dotenv()

# Helper de conexión a MongoDB
def get_db():
    from config import get_mongo_uri, MONGO_DB
    client = MongoClient(get_mongo_uri(), serverSelectionTimeoutMS=2000)
    return client[MONGO_DB]

def slugify_provider_name(name: str) -> str:
    slug = re.sub(r'[^a-zA-Z0-9_\-]', '_', name.strip().lower()).strip('_')
    return slug or "cloud"

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
from config import API_KEY

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
    "fallback_stt": "vllm-fallback-stt",
    "tts": "vllm-tts",
    "fallback_tts": "vllm-fallback-tts",
    "diarization": "vllm-diarization",
    "embeddings": "vllm-embeddings",
    "image": "vllm-image",
    "rag_sync": "vllm-rag-sync.timer",
    "gateway": "vllm-gateway",
    "docling": "docling"
}

# Puertos locales de cada servicio
SERVICE_PORTS = {
    "gemma": 8000,
    "whisper": 8001,
    "fallback_stt": 18011,
    "tts": 8002,
    "fallback_tts": 18012,
    "diarization": 8003,
    "embeddings": 8005,
    "image": 8006,
    "rag_sync": "00:00:00",
    "gateway": "8000-8020",
    "docling": "5020 / 8020"
}

# Puertos internos de los motores reales detrás del Gateway
BACKEND_PORTS = {
    "gemma": int(os.getenv("GEMMA_BACKEND_PORT", "18000")),
    "whisper": int(os.getenv("WHISPER_BACKEND_PORT", "18001")),
    "fallback_stt": int(os.getenv("STT_FALLBACK_PORT", "18011")),
    "tts": int(os.getenv("TTS_BACKEND_PORT", "18002")),
    "fallback_tts": int(os.getenv("TTS_FALLBACK_PORT", "18012")),
    "diarization": int(os.getenv("DIARIZATION_BACKEND_PORT", "18003")),
    "image": int(os.getenv("IMAGE_BACKEND_PORT", "18004")),
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

# Inicializar la base de datos de telemetría e índices de seguridad
def init_db_telemetry():
    try:
        db = get_db()
        db.telemetry_history.create_index("timestamp", expireAfterSeconds=604800)
        print("💾 MongoDB: Índice TTL de 7 días configurado en telemetry_history.")
        
        # Crear índice TTL en ip_rules sobre expires_at para autolimpieza de baneos temporales (48h)
        db.ip_rules.create_index("expires_at", expireAfterSeconds=0)
        print("💾 MongoDB: Índice TTL dinámico configurado en ip_rules (expires_at).")
    except Exception as e:
        print(f"⚠️ Error al configurar índices de base de datos en MongoDB: {e}", file=sys.stderr)

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
                cpu_temp = get_cpu_temperature() or 0.0
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
                    "cpu_temp": cpu_temp,
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

@app.route("/outputs/images/<path:filename>")
def serve_output_image(filename):
    image_dir = os.getenv("IMAGE_OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "outputs", "images"))
    return send_from_directory(image_dir, filename)

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
                "audio_url": (v.get("audio_path", "")[v.get("audio_path", "").find("/static/"):] if "/static/" in v.get("audio_path", "") else v.get("audio_path", "")),
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
            
        base_dir = os.path.dirname(os.path.abspath(__file__))
        upload_dir = os.path.join(base_dir, "static", "audio", "clones")
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

def check_and_reset_key_quota_dict(k: dict, db) -> dict:
    quota_reset = k.get("quota_reset", "none")
    if quota_reset in ["daily", "monthly"]:
        last_reset_at = k.get("last_reset_at")
        now = datetime.utcnow()
        reset_needed = False
        
        if not last_reset_at:
            reset_needed = True
        else:
            if isinstance(last_reset_at, str):
                try:
                    last_dt = datetime.fromisoformat(last_reset_at.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    last_dt = now
            elif isinstance(last_reset_at, datetime):
                last_dt = last_reset_at.replace(tzinfo=None)
            else:
                last_dt = now
                
            if quota_reset == "daily":
                if now.date() > last_dt.date():
                    reset_needed = True
            elif quota_reset == "monthly":
                if (now.year, now.month) > (last_dt.year, last_dt.month):
                    reset_needed = True
                    
        if reset_needed:
            db.api_keys.update_one(
                {"_id": k["_id"]},
                {"$set": {"used_tokens": 0, "last_reset_at": now}}
            )
            k["used_tokens"] = 0
            k["last_reset_at"] = now
    return k

@app.route("/api/keys", methods=["GET"])
def api_get_keys():
    try:
        db = get_db()
        keys = list(db.api_keys.find())
        result = []
        for k in keys:
            k = check_and_reset_key_quota_dict(k, db)
            key_id = k["_id"]
            # Obtener modelos asignados para esta clave
            key_models = list(db.api_key_models.find({"key_id": key_id}))
            models_by_provider = {}
            for km in key_models:
                p_id = str(km.get("provider_id", ""))
                if p_id:
                    if p_id not in models_by_provider:
                        models_by_provider[p_id] = []
                    models_by_provider[p_id].append(km.get("model_id"))
            
            result.append({
                "id": str(key_id),
                "name": k.get("name", "Sin nombre"),
                "description": k.get("description", ""),
                "key": k.get("key", ""),
                "services": k.get("services", []),
                "allowed_providers": k.get("allowed_providers", []),
                "allowed_models_count": len(key_models),
                "models_by_provider": models_by_provider,
                "max_tokens": int(k.get("max_tokens") or 0),
                "used_tokens": int(k.get("used_tokens") or 0),
                "quota_reset": k.get("quota_reset", "none"),
                "last_reset_at": str(k.get("last_reset_at") or ""),
                "expires_at": k.get("expires_at", ""),
                "is_active": k.get("is_active", True)
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/keys/<key_id>/models", methods=["GET"])
def api_get_key_models(key_id):
    try:
        db = get_db()
        key_models = list(db.api_key_models.find({"key_id": ObjectId(key_id)}))
        result = []
        for km in key_models:
            result.append({
                "id": str(km["_id"]),
                "key_id": str(km.get("key_id", "")),
                "provider_id": str(km.get("provider_id", "")),
                "provider_name": km.get("provider_name", ""),
                "provider_slug": km.get("provider_slug", ""),
                "model_id": km.get("model_id", ""),
                "prefixed_id": km.get("prefixed_id", "")
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
        allowed_providers = data.get("allowed_providers", [])
        allowed_models = data.get("allowed_models", {})  # Dict { "<provider_id>": ["m1", "m2"] }
        max_tokens = int(data.get("max_tokens") or 0)
        quota_reset = data.get("quota_reset", "none")
        if quota_reset not in ["none", "daily", "monthly"]:
            quota_reset = "none"
        expires_at = data.get("expires_at", "").strip()
        
        if not name:
            return jsonify({"error": "El nombre es obligatorio"}), 400
            
        if not services and not allowed_providers:
            return jsonify({"error": "Debes seleccionar al menos un servicio local o un proveedor en la nube"}), 400
            
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
            "allowed_providers": allowed_providers,
            "max_tokens": max_tokens,
            "used_tokens": 0,
            "quota_reset": quota_reset,
            "last_reset_at": datetime.utcnow(),
            "expires_at": expires_val,
            "is_active": True
        }).inserted_id
        
        # Persistir modelos granulares seleccionados en db.api_key_models
        if allowed_models and isinstance(allowed_models, dict):
            docs_to_insert = []
            for p_id, m_list in allowed_models.items():
                if not m_list:
                    continue
                try:
                    p_obj = db.cloud_providers.find_one({"_id": ObjectId(p_id)})
                    if p_obj:
                        p_name = p_obj.get("name", "")
                        p_slug = slugify_provider_name(p_name)
                        for m_id in m_list:
                            docs_to_insert.append({
                                "key_id": key_id,
                                "provider_id": ObjectId(p_id),
                                "provider_name": p_name,
                                "provider_slug": p_slug,
                                "model_id": m_id,
                                "prefixed_id": f"{p_slug}/{m_id}",
                                "created_at": datetime.utcnow()
                            })
                except Exception as p_err:
                    print(f"Error procesando modelos para clave {key_id}: {p_err}", file=sys.stderr, flush=True)
            if docs_to_insert:
                db.api_key_models.insert_many(docs_to_insert)
        
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
        allowed_providers = data.get("allowed_providers", [])
        allowed_models = data.get("allowed_models", None)  # Dict { "<provider_id>": ["m1", "m2"] }
        max_tokens = int(data.get("max_tokens") or 0)
        quota_reset = data.get("quota_reset", "none")
        if quota_reset not in ["none", "daily", "monthly"]:
            quota_reset = "none"
        expires_at = data.get("expires_at", "").strip()
        is_active = data.get("is_active", True)
        
        if not name:
            return jsonify({"error": "El nombre es obligatorio"}), 400
            
        if not services and not allowed_providers:
            return jsonify({"error": "Debes seleccionar al menos un servicio local o un proveedor en la nube"}), 400
            
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
                "allowed_providers": allowed_providers,
                "max_tokens": max_tokens,
                "quota_reset": quota_reset,
                "expires_at": expires_val,
                "is_active": is_active
            }}
        )
        
        if res.matched_count == 0:
            return jsonify({"error": "Clave API no encontrada"}), 404
            
        # Actualizar modelos granulares si se enviaron
        if allowed_models is not None and isinstance(allowed_models, dict):
            db.api_key_models.delete_many({"key_id": ObjectId(key_id)})
            docs_to_insert = []
            for p_id, m_list in allowed_models.items():
                if not m_list:
                    continue
                try:
                    p_obj = db.cloud_providers.find_one({"_id": ObjectId(p_id)})
                    if p_obj:
                        p_name = p_obj.get("name", "")
                        p_slug = slugify_provider_name(p_name)
                        for m_id in m_list:
                            docs_to_insert.append({
                                "key_id": ObjectId(key_id),
                                "provider_id": ObjectId(p_id),
                                "provider_name": p_name,
                                "provider_slug": p_slug,
                                "model_id": m_id,
                                "prefixed_id": f"{p_slug}/{m_id}",
                                "created_at": datetime.utcnow()
                            })
                except Exception as p_err:
                    print(f"Error actualizando modelos para clave {key_id}: {p_err}", file=sys.stderr, flush=True)
            if docs_to_insert:
                db.api_key_models.insert_many(docs_to_insert)
            
        return jsonify({"message": "Clave API actualizada con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/keys/<key_id>/reset-quota", methods=["POST"])
def api_reset_key_quota(key_id):
    try:
        db = get_db()
        now = datetime.utcnow()
        res = db.api_keys.update_one(
            {"_id": ObjectId(key_id)},
            {"$set": {"used_tokens": 0, "last_reset_at": now}}
        )
        if res.matched_count == 0:
            return jsonify({"error": "Clave API no encontrada"}), 404
            
        return jsonify({"message": "Cupo de tokens reiniciado a cero con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/keys/<key_id>", methods=["DELETE"])
def api_delete_key(key_id):
    try:
        db = get_db()
        db.api_key_models.delete_many({"key_id": ObjectId(key_id)})
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
                "cpu_temp": r.get("cpu_temp", 0),
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

@app.route("/api/metrics", methods=["GET"])
def api_metrics():
    try:
        # 1. Parsear filtros
        days = request.args.get("days", default=7, type=int)
        service = request.args.get("service", default="", type=str)
        api_key = request.args.get("api_key", default="", type=str)
        model = request.args.get("model", default="", type=str)
        
        # 2. Calcular fecha de inicio
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # 3. Construir query de filtrado
        query = {"timestamp": {"$gte": start_date}}
        if service:
            query["service"] = service
        if api_key:
            query["api_key_name"] = api_key
        if model:
            query["model"] = model
            
        db = get_db()
        logs = list(db.usage_logs.find(query).sort("timestamp", 1))
        
        # 4. Agrupar datos por fecha (YYYY-MM-DD) para la serie temporal
        # y acumular estadísticas agregadas
        time_series = {}
        service_shares = {}
        api_key_shares = {}
        model_shares = {}
        
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_audio_sec = 0.0
        total_calls = len(logs)
        
        # Inicializar serie temporal con ceros para todos los días en el rango
        for i in range(days):
            day_str = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
            time_series[day_str] = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "audio_duration_sec": 0.0,
                "calls": 0
            }
            
        for log in logs:
            ts = log["timestamp"]
            day_str = ts.strftime("%Y-%m-%d") if isinstance(ts, datetime) else ts[:10]
            
            p_tokens = log.get("prompt_tokens", 0)
            c_tokens = log.get("completion_tokens", 0)
            a_sec = log.get("audio_duration_sec", 0.0)
            
            total_prompt_tokens += p_tokens
            total_completion_tokens += c_tokens
            total_audio_sec += a_sec
            
            # Acumular en serie temporal
            if day_str in time_series:
                time_series[day_str]["prompt_tokens"] += p_tokens
                time_series[day_str]["completion_tokens"] += c_tokens
                time_series[day_str]["audio_duration_sec"] += a_sec
                time_series[day_str]["calls"] += 1
                
            # Acumular reparto por servicio
            srv = log.get("service", "unknown")
            service_shares[srv] = service_shares.get(srv, 0) + 1
            
            # Acumular reparto por clave API
            key = log.get("api_key_name", "unknown")
            api_key_shares[key] = api_key_shares.get(key, 0) + 1
            
            # Acumular reparto por modelo
            mdl = log.get("model", "unknown")
            model_shares[mdl] = model_shares.get(mdl, 0) + 1
            
        # Ordenar cronológicamente la serie temporal para gráficos
        sorted_time_series = [
            {"date": date, **metrics}
            for date, metrics in sorted(time_series.items())
        ]
        
        # Obtener lista de claves API y modelos únicos en la BD para llenar los dropdowns de filtros en la interfaz
        api_keys_list = list(db.api_keys.find({}, {"name": 1}))
        api_key_names = ["Master Key"] + [k["name"] for k in api_keys_list if k.get("name")]
        
        # Modelos únicos en usage_logs
        unique_models = db.usage_logs.distinct("model")
        
        return jsonify({
            "summary": {
                "total_calls": total_calls,
                "total_prompt_tokens": total_prompt_tokens,
                "total_completion_tokens": total_completion_tokens,
                "total_audio_sec": round(total_audio_sec, 2),
            },
            "time_series": sorted_time_series,
            "shares": {
                "service": service_shares,
                "api_key": api_key_shares,
                "model": model_shares
            },
            "filters_data": {
                "api_keys": api_key_names,
                "models": unique_models
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/metrics/export", methods=["GET"])
def api_export_metrics():
    try:
        # 1. Parsear filtros
        days = request.args.get("days", default=7, type=int)
        service = request.args.get("service", default="", type=str)
        api_key = request.args.get("api_key", default="", type=str)
        model = request.args.get("model", default="", type=str)
        
        # 2. Calcular fecha de inicio
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # 3. Construir query de filtrado
        query = {"timestamp": {"$gte": start_date}}
        if service:
            query["service"] = service
        if api_key:
            query["api_key_name"] = api_key
        if model:
            query["model"] = model
            
        db = get_db()
        logs = list(db.usage_logs.find(query).sort("timestamp", -1))
        
        # 4. Generar CSV
        def generate():
            yield "\ufeff"
            headers = [
                "Fecha y Hora",
                "IP Cliente",
                "Clave API",
                "Servicio",
                "Endpoint",
                "Modelo",
                "Tokens Entrada",
                "Tokens Salida",
                "Duracion Audio (seg)",
                "Tiempo Procesamiento (seg)"
            ]
            yield ";".join(headers) + "\n"
            
            for log in logs:
                ts = log.get("timestamp")
                ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if isinstance(ts, datetime) else str(ts)
                
                row = [
                    ts_str,
                    log.get("ip") or log.get("client_ip", ""),
                    log.get("api_key_name", ""),
                    log.get("service", ""),
                    log.get("endpoint") or log.get("path", ""),
                    log.get("model", ""),
                    str(log.get("prompt_tokens", 0)),
                    str(log.get("completion_tokens", 0)),
                    f"{log.get('audio_duration_sec', 0.0):.2f}",
                    f"{log.get('duration_sec', 0.0):.2f}"
                ]
                row_cleaned = [str(val).replace(";", " ").replace("\n", " ").replace("\r", " ") for val in row]
                yield ";".join(row_cleaned) + "\n"
                
        return Response(
            generate(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=telemetria_consumo.csv"}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Gestión de Reglas de IP (Whitelist/Blacklist CIDR) en MongoDB
@app.route("/api/ip-rules", methods=["GET"])
def api_get_ip_rules():
    try:
        db = get_db()
        rules = list(db.ip_rules.find())
        result = []
        for r in rules:
            result.append({
                "id": str(r["_id"]),
                "name": r.get("name", "Sin nombre"),
                "network": r.get("network", ""),
                "action": r.get("action", "whitelist"),
                "is_active": r.get("is_active", True)
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/blocked-requests", methods=["GET"])
def api_get_blocked_requests():
    try:
        # 1. Parsear paginación
        page = request.args.get("page", default=1, type=int)
        limit = request.args.get("limit", default=10, type=int)
        if page < 1:
            page = 1
        if limit < 1:
            limit = 10
            
        # 2. Parsear filtros
        start_date_str = request.args.get("start_date", default="", type=str)
        end_date_str = request.args.get("end_date", default="", type=str)
        ip = request.args.get("ip", default="", type=str)
        service = request.args.get("service", default="", type=str)
        endpoint = request.args.get("endpoint", default="", type=str)
        reason = request.args.get("reason", default="", type=str)
        
        # 3. Construir query MongoDB
        query = {}
        
        # Filtro de rango de fechas
        if start_date_str or end_date_str:
            time_filter = {}
            if start_date_str:
                try:
                    start_dt = datetime.fromisoformat(start_date_str)
                    time_filter["$gte"] = start_dt
                except Exception:
                    pass
            if end_date_str:
                try:
                    end_dt = datetime.fromisoformat(end_date_str) + timedelta(days=1) - timedelta(milliseconds=1)
                    time_filter["$lte"] = end_dt
                except Exception:
                    pass
            if time_filter:
                query["timestamp"] = time_filter
        else:
            # Por defecto las últimas 24h
            hours = request.args.get("hours", default=24, type=int)
            start_date = datetime.utcnow() - timedelta(hours=hours)
            query["timestamp"] = {"$gte": start_date}
            
        if ip:
            query["ip"] = {"$regex": re.escape(ip), "$options": "i"}
        if service:
            query["service"] = service
        if endpoint:
            query["endpoint"] = {"$regex": re.escape(endpoint), "$options": "i"}
        if reason:
            query["reason"] = reason
            
        db = get_db()
        
        # 4. Calcular conteo total y paginar
        total_records = db.blocked_requests.count_documents(query)
        total_pages = (total_records + limit - 1) // limit if total_records > 0 else 1
        
        skip = (page - 1) * limit
        logs = list(db.blocked_requests.find(query).sort("timestamp", -1).skip(skip).limit(limit))
        
        result = []
        for l in logs:
            ts_str = l["timestamp"].isoformat() + "Z" if isinstance(l["timestamp"], datetime) else l["timestamp"]
            result.append({
                "id": str(l["_id"]),
                "timestamp": ts_str,
                "ip": l.get("ip", ""),
                "service": l.get("service", ""),
                "endpoint": l.get("endpoint", ""),
                "reason": l.get("reason", "")
            })
            
        return jsonify({
            "logs": result,
            "total_records": total_records,
            "total_pages": total_pages,
            "current_page": page,
            "limit": limit
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/blocked-requests/export", methods=["GET"])
def api_export_blocked_requests():
    try:
        # 1. Parsear filtros
        start_date_str = request.args.get("start_date", default="", type=str)
        end_date_str = request.args.get("end_date", default="", type=str)
        ip = request.args.get("ip", default="", type=str)
        service = request.args.get("service", default="", type=str)
        endpoint = request.args.get("endpoint", default="", type=str)
        reason = request.args.get("reason", default="", type=str)
        
        query = {}
        if start_date_str or end_date_str:
            time_filter = {}
            if start_date_str:
                try:
                    start_dt = datetime.fromisoformat(start_date_str)
                    time_filter["$gte"] = start_dt
                except Exception:
                    pass
            if end_date_str:
                try:
                    end_dt = datetime.fromisoformat(end_date_str) + timedelta(days=1) - timedelta(milliseconds=1)
                    time_filter["$lte"] = end_dt
                except Exception:
                    pass
            if time_filter:
                query["timestamp"] = time_filter
        else:
            hours = request.args.get("hours", default=24, type=int)
            start_date = datetime.utcnow() - timedelta(hours=hours)
            query["timestamp"] = {"$gte": start_date}
            
        if ip:
            query["ip"] = {"$regex": re.escape(ip), "$options": "i"}
        if service:
            query["service"] = service
        if endpoint:
            query["endpoint"] = {"$regex": re.escape(endpoint), "$options": "i"}
        if reason:
            query["reason"] = reason
            
        db = get_db()
        logs = list(db.blocked_requests.find(query).sort("timestamp", -1))
        
        # 2. Generar CSV compatible con Excel en Español
        import io
        import csv
        from flask import make_response
        
        si = io.StringIO()
        si.write('\ufeff') # UTF-8 BOM
        cw = csv.writer(si, delimiter=';')
        
        cw.writerow(["Fecha y Hora (UTC)", "Dirección IP", "Servicio", "Ruta (Endpoint)", "Motivo / Filtro"])
        
        for l in logs:
            ts = l["timestamp"]
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if isinstance(ts, datetime) else str(ts)
            cw.writerow([
                ts_str,
                l.get("ip", ""),
                l.get("service", ""),
                l.get("endpoint", ""),
                "LISTA BLANCA" if l.get("reason") == "whitelist" else ("CLAVE API ERROR" if l.get("reason") == "api_key" else "LISTA NEGRA")
            ])
            
        response = make_response(si.getvalue())
        response.headers["Content-Disposition"] = "attachment; filename=bloqueos_seguridad.csv"
        response.headers["Content-type"] = "text/csv; charset=utf-8"
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ip-rules", methods=["POST"])
def api_create_ip_rule():
    try:
        data = request.json or {}
        name = data.get("name", "").strip()
        network_str = data.get("network", "").strip()
        action = data.get("action", "whitelist").lower()
        is_active = data.get("is_active", True)
        
        if not name or not network_str:
            return jsonify({"error": "Nombre y Red/IP son requeridos"}), 400
            
        if action not in ["whitelist", "blacklist"]:
            return jsonify({"error": "Acción inválida. Debe ser whitelist o blacklist"}), 400
            
        # Validar la IP o el CIDR usando la biblioteca ipaddress
        try:
            ipaddress.ip_network(network_str, strict=False)
        except ValueError as val_err:
            return jsonify({"error": f"Sintaxis de Red/IP inválida: {val_err}"}), 400
            
        db = get_db()
        # Verificar duplicados
        existing = db.ip_rules.find_one({"network": network_str})
        if existing:
            return jsonify({"error": f"La IP o rango '{network_str}' ya existe registrado."}), 400
            
        rule = {
            "name": name,
            "network": network_str,
            "action": action,
            "is_active": is_active
        }
        res = db.ip_rules.insert_one(rule)
        return jsonify({"message": "Regla de IP creada con éxito", "id": str(res.inserted_id)}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ip-rules/<rule_id>", methods=["PUT"])
def api_update_ip_rule(rule_id):
    try:
        data = request.json or {}
        name = data.get("name", "").strip()
        network_str = data.get("network", "").strip()
        action = data.get("action", "whitelist").lower()
        is_active = data.get("is_active", True)
        
        if not name or not network_str:
            return jsonify({"error": "Nombre y Red/IP son requeridos"}), 400
            
        if action not in ["whitelist", "blacklist"]:
            return jsonify({"error": "Acción inválida"}), 400
            
        # Validar sintaxis
        try:
            ipaddress.ip_network(network_str, strict=False)
        except ValueError as val_err:
            return jsonify({"error": f"Sintaxis de Red/IP inválida: {val_err}"}), 400
            
        db = get_db()
        res = db.ip_rules.update_one(
            {"_id": ObjectId(rule_id)},
            {"$set": {
                "name": name,
                "network": network_str,
                "action": action,
                "is_active": is_active
            }}
        )
        if res.matched_count == 0:
            return jsonify({"error": "Regla de IP no encontrada"}), 404
            
        return jsonify({"message": "Regla de IP actualizada con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ip-rules/<rule_id>", methods=["DELETE"])
def api_delete_ip_rule(rule_id):
    try:
        db = get_db()
        res = db.ip_rules.delete_one({"_id": ObjectId(rule_id)})
        if res.deleted_count == 0:
            return jsonify({"error": "Regla de IP no encontrada"}), 404
            
        return jsonify({"message": "Regla de IP eliminada con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/cloud-providers", methods=["GET"])
def api_get_cloud_providers():
    try:
        db = get_db()
        providers = list(db.cloud_providers.find())
        result = []
        for p in providers:
            key = p.get("api_key", "")
            masked_key = key[:8] + "..." if len(key) > 8 else "..."
            result.append({
                "id": str(p["_id"]),
                "name": p.get("name", ""),
                "base_url": p.get("base_url", ""),
                "api_key": masked_key,
                "is_active": p.get("is_active", True)
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/cloud-providers", methods=["POST"])
def api_create_cloud_provider():
    try:
        data = request.json or {}
        name = data.get("name", "").strip()
        base_url = data.get("base_url", "").strip()
        api_key = data.get("api_key", "").strip()
        is_active = data.get("is_active", True)
        
        if not name or not base_url or not api_key:
            return jsonify({"error": "Todos los campos son requeridos"}), 400
            
        db = get_db()
        db.cloud_providers.insert_one({
            "name": name,
            "base_url": base_url,
            "api_key": api_key,
            "is_active": is_active
        })
        return jsonify({"message": "Proveedor en la nube creado con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/cloud-providers/<provider_id>", methods=["PUT"])
def api_update_cloud_provider(provider_id):
    try:
        data = request.json or {}
        name = data.get("name", "").strip()
        base_url = data.get("base_url", "").strip()
        api_key = data.get("api_key", "").strip()
        is_active = data.get("is_active", True)
        
        update_doc = {
            "name": name,
            "base_url": base_url,
            "is_active": is_active
        }
        if api_key and not api_key.endswith("..."):
            update_doc["api_key"] = api_key
            
        db = get_db()
        res = db.cloud_providers.update_one(
            {"_id": ObjectId(provider_id)},
            {"$set": update_doc}
        )
        if res.matched_count == 0:
            return jsonify({"error": "Proveedor no encontrado"}), 404
            
        return jsonify({"message": "Proveedor en la nube actualizado con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/cloud-providers/<provider_id>/models", methods=["GET"])
def api_get_cloud_provider_models(provider_id):
    try:
        db = get_db()
        provider = db.cloud_providers.find_one({"_id": ObjectId(provider_id)})
        if not provider:
            return jsonify({"error": "Proveedor no encontrado"}), 404
        
        base_url = provider.get("base_url", "").rstrip("/")
        api_key = provider.get("api_key", "")
        if not base_url or not api_key:
            return jsonify({"error": "El proveedor no tiene configurada base_url o api_key"}), 400
        
        headers = {"Authorization": f"Bearer {api_key}"}
        models_url = f"{base_url}/models" if not base_url.endswith("/models") else base_url
        try:
            resp = requests.get(models_url, headers=headers, timeout=7.0)
        except Exception as net_err:
            return jsonify({"error": f"No se pudo conectar con el proveedor: {net_err}"}), 502
            
        if resp.status_code != 200:
            return jsonify({"error": f"El proveedor devolvió código HTTP {resp.status_code}: {resp.text[:200]}"}), 502
            
        models_data = resp.json()
        raw_list = models_data.get("data", [])
        formatted_models = []
        slug = slugify_provider_name(provider.get("name", "cloud"))
        for m in raw_list:
            m_id = m.get("id")
            if m_id:
                formatted_models.append({
                    "id": m_id,
                    "prefixed_id": f"{slug}/{m_id}",
                    "name": m.get("name") or m_id,
                    "created": m.get("created"),
                    "owned_by": m.get("owned_by") or provider.get("name", "cloud")
                })
        return jsonify({
            "provider_id": provider_id,
            "provider_name": provider.get("name", ""),
            "provider_slug": slug,
            "models": formatted_models
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/cloud-providers/<provider_id>", methods=["DELETE"])
def api_delete_cloud_provider(provider_id):
    try:
        db = get_db()
        db.api_key_models.delete_many({"provider_id": ObjectId(provider_id)})
        res = db.cloud_providers.delete_one({"_id": ObjectId(provider_id)})
        if res.deleted_count == 0:
            return jsonify({"error": "Proveedor no encontrado"}), 404
            
        return jsonify({"message": "Proveedor en la nube eliminado con éxito"})
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
            "cpu_temp": get_cpu_temperature(),
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
        API_KEY = os.getenv("API_KEY", "")
        
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
    
    data = request.json or {}
    prompt = data.get("prompt", "¡Hola!")
    model = data.get("model") or current_vars.get("MODEL", "google/gemma-4-E4B-it")
    max_tokens = int(data.get("max_tokens", 400))
    
    url = f"http://127.0.0.1:{BACKEND_PORTS['gemma']}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens
    }
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=60)
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

@app.route("/api/test/image", methods=["POST"])
def api_test_image():
    """
    Proxy interactivo para probar la generación de imágenes en el puerto 18004.
    """
    current_vars = parse_env_to_dict()
    api_key = current_vars.get("API_KEY", API_KEY)
    
    data = request.json or {}
    prompt = data.get("prompt", "A cute futuristic robot in high-tech laboratory")
    size = data.get("size", "512x512")
    
    url = f"http://127.0.0.1:{BACKEND_PORTS['image']}/v1/images/generations"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "prompt": prompt,
        "size": size,
        "n": 1,
        "response_format": "url"
    }
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=120)
        return Response(res.text, status=res.status_code, content_type="application/json")
    except Exception as e:
        return jsonify({"error": f"No se pudo conectar al servicio de Generación de Imágenes (puerto {BACKEND_PORTS['image']}): {str(e)}"}), 502

# ==============================================================================
# Endpoints de Base de Conocimiento RAG & LanceDB (Teccam PDF)
# ==============================================================================

@app.route("/api/rag/stats", methods=["GET"])
def api_rag_stats():
    """Obtiene métricas y estado actual de la base de conocimiento LanceDB."""
    try:
        from rag_engine import get_rag_stats
        stats = get_rag_stats()
        
        # Obtener último log de sincronización desde MongoDB
        try:
            db = get_db()
            log_entry = db.rag_sync_logs.find_one(sort=[("timestamp", -1)])
            if log_entry:
                ts = log_entry.get("timestamp")
                stats["last_sync"] = {
                    "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                    "status": log_entry.get("status", "success"),
                    "duration_sec": log_entry.get("duration_sec", 0),
                    "docs_synced_count": log_entry.get("docs_synced_count", 0),
                    "total_chunks": log_entry.get("total_chunks_in_db", 0)
                }
            else:
                stats["last_sync"] = None
        except Exception:
            stats["last_sync"] = None
            
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": f"Error obteniendo estadísticas RAG: {str(e)}"}), 500

@app.route("/api/rag/sync", methods=["POST"])
def api_rag_sync():
    """Dispara una sincronización diferencial de Teccam PDF -> LanceDB en segundo plano utilizando el orquestador de VRAM."""
    try:
        import threading
        import subprocess
        
        force = request.json.get("force", False) if request.is_json else False
        
        def run_sync():
            try:
                cmd = ["sudo", "/bin/bash", "/home/jose/vllm/sync_rag_scheduled.sh"]
                if force:
                    cmd.append("--force")
                subprocess.run(cmd, check=True)
            except Exception as se:
                print(f"❌ Error en background sync con orquestador: {se}", file=sys.stderr)
                
        thread = threading.Thread(target=run_sync, daemon=True)
        thread.start()
        
        return jsonify({
            "status": "started",
            "message": "Sincronización RAG iniciada. El LLM se pausará brevemente para proteger la VRAM y se reanudará automáticamente."
        })
    except Exception as e:
        return jsonify({"error": f"Error al iniciar sincronización: {str(e)}"}), 500

@app.route("/api/rag/sync-metadata", methods=["POST"])
def api_rag_sync_metadata():
    """Actualiza en milisegundos y en caliente la metadata (vigencia, fecha_publicacion) desde Teccam PDF sin tocar la GPU ni pausar vLLM."""
    try:
        from app_rag_sync import fetch_teccam_documents_index
        from rag_engine import get_lancedb, TABLE_NAME

        remote_docs = fetch_teccam_documents_index()
        if not remote_docs:
            return jsonify({"error": "No se pudo conectar con la API de Teccam PDF o no retornó documentos."}), 502

        db = get_lancedb()
        table = db.open_table(TABLE_NAME)

        # Verificar columnas en LanceDB
        if "doc_vigencia" not in table.schema.names or "doc_fecha_publicacion" not in table.schema.names:
            table.add_columns({"doc_vigencia": "'NA (no aplica)'", "doc_fecha_publicacion": "cast(null as string)"})
            table = db.open_table(TABLE_NAME)

        updated_count = 0
        for doc in remote_docs:
            doc_id = doc.get("id")
            if not doc_id:
                continue
            vig = doc.get("vigencia") or "NA (no aplica)"
            fpub = doc.get("fecha_publicacion") or ""
            clean_id = doc_id.replace("'", "''")
            table.update(
                where=f"doc_id = '{clean_id}'",
                values={
                    "doc_vigencia": vig,
                    "doc_fecha_publicacion": str(fpub)
                }
            )
            updated_count += 1

        return jsonify({
            "success": True,
            "updated_count": updated_count,
            "message": f"Metadata de {updated_count} documentos actualizada en LanceDB en milisegundos (sin pausa de LLM ni uso de GPU)."
        })
    except Exception as e:
        return jsonify({"error": f"Error actualizando metadata: {str(e)}"}), 500

@app.route("/api/rag/settings", methods=["GET", "POST"])
def api_rag_settings():
    """Lee o actualiza la configuración global de RAG (estado, dominios activos y modelo cloud para RAG)."""
    try:
        from rag_engine import get_rag_settings, save_rag_settings
        if request.method == "POST":
            data = request.get_json() or {}
            active_topics = data.get("active_topics", None)
            enabled = data.get("enabled", None)
            cloud_rag_provider_id = data.get("cloud_rag_provider_id", None)
            cloud_rag_provider_name = data.get("cloud_rag_provider_name", None)
            cloud_rag_model_id = data.get("cloud_rag_model_id", None)
            
            success = save_rag_settings(
                active_topics=active_topics,
                enabled=enabled,
                cloud_rag_provider_id=cloud_rag_provider_id,
                cloud_rag_provider_name=cloud_rag_provider_name,
                cloud_rag_model_id=cloud_rag_model_id
            )
            settings = get_rag_settings()
            return jsonify({"success": success, **settings})
        else:
            settings = get_rag_settings()
            return jsonify(settings)
    except Exception as e:
        return jsonify({"error": f"Error en settings RAG: {str(e)}"}), 500

@app.route("/api/rag/search", methods=["POST"])
def api_rag_search():
    """Ejecuta una búsqueda de prueba en la base vectorial LanceDB."""
    try:
        from rag_engine import search_knowledge_base
        data = request.get_json() or {}
        query = data.get("query", "").strip()
        tema = data.get("tema") or None
        temas = data.get("temas") or None
        top_k = int(data.get("top_k", 5))
        
        if not query:
            return jsonify({"error": "La consulta 'query' no puede estar vacía"}), 400
            
        t0 = time.time()
        results = search_knowledge_base(query=query, tema=tema, temas=temas, top_k=top_k)
        dur_ms = round((time.time() - t0) * 1000, 2)
        
        return jsonify({
            "query": query,
            "tema": tema,
            "temas": temas,
            "results_count": len(results),
            "latency_ms": dur_ms,
            "results": results
        })
    except Exception as e:
        return jsonify({"error": f"Error ejecutando búsqueda RAG: {str(e)}"}), 500

@app.route("/api/rag/documents/<doc_id>", methods=["DELETE"])
def api_rag_delete_document(doc_id):
    """Elimina todos los fragmentos vectoriales de un documento específico en LanceDB."""
    try:
        from rag_engine import get_table
        table = get_table()
        if table is None:
            return jsonify({"error": "La tabla de LanceDB no existe"}), 404
            
        clean_doc_id = doc_id.strip().replace("'", "''")
        table.delete(f"doc_id = '{clean_doc_id}'")
        
        # Actualizar índice FTS
        try:
            table.create_fts_index("text", replace=True)
        except Exception:
            pass
            
        return jsonify({
            "success": True,
            "deleted_doc_id": doc_id,
            "remaining_chunks": len(table)
        })
    except Exception as e:
        return jsonify({"error": f"Error al eliminar documento de LanceDB: {str(e)}"}), 500

@app.route("/api/rag/structure/<doc_id>", methods=["GET"])
def api_rag_structure(doc_id):
    """Obtiene el GPS Documental y mapa de secciones de un documento desde LanceDB."""
    try:
        from rag_engine import get_document_structure
        res = get_document_structure(doc_id=doc_id)
        if not res.get("success"):
            return jsonify({"error": res.get("error", "Error consultando estructura")}), 404
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": f"Error obteniendo estructura RAG: {str(e)}"}), 500

@app.route("/api/rag/library-index", methods=["GET"])
def api_rag_library_index():
    """Obtiene el Mapa Ontológico Global y árbol temático jerárquico de la biblioteca LanceDB."""
    try:
        from rag_engine import get_library_index
        solo_vigentes = request.args.get("solo_vigentes", "false").lower() in ("true", "1", "yes")
        tema = request.args.get("tema") or None
        res = get_library_index(solo_vigentes=solo_vigentes, tema=tema)
        if not res.get("success"):
            return jsonify({"error": res.get("error", "Error generando índice de biblioteca")}), 500
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": f"Error obteniendo índice de biblioteca: {str(e)}"}), 500


# ==============================================================================
# ENDPOINTS: ALINEACIÓN Y POLÍTICAS MEA
# ==============================================================================
@app.route("/api/alignment/settings", methods=["GET", "POST"])
def api_alignment_settings():
    """Obtiene o actualiza las directivas y políticas de alineación MEA en MongoDB."""
    try:
        from gateway.core.alignment_engine import get_alignment_settings, save_alignment_settings
        if request.method == "POST":
            data = request.get_json() or {}
            success = save_alignment_settings(data)
            if success:
                return jsonify({"success": True, "message": "Políticas de alineación guardadas y aplicadas en caliente."})
            return jsonify({"success": False, "message": "Error al persistir en base de datos."}), 500
        else:
            settings = get_alignment_settings()
            return jsonify({"success": True, "settings": settings})
    except Exception as e:
        return jsonify({"success": False, "error": f"Error en configuración de alineación: {str(e)}"}), 500

if __name__ == "__main__":
    init_db_telemetry()
    start_telemetry_collector()
    app.run(host="0.0.0.0", port=PORT)
