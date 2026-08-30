import sys
from datetime import datetime, timezone
from pymongo import MongoClient
from config import API_KEY as MASTER_KEY, get_mongo_uri, MONGO_DB


def get_db():
    client = MongoClient(get_mongo_uri(), serverSelectionTimeoutMS=1000)
    return client[MONGO_DB]


def save_usage_log(ip: str, token: str, service: str, endpoint: str, model: str,
                   prompt_tokens: int, completion_tokens: int, audio_duration_sec: float,
                   duration_sec: float):
    """
    Función síncrona ejecutada en BackgroundTasks para no bloquear el bucle de eventos.
    Registra el consumo y actualiza el contador de tokens utilizados.
    """
    try:
        db = get_db()
        # 1. Determinar el nombre de la API Key de forma segura
        if token == MASTER_KEY:
            key_name = "Master Key"
        else:
            key_doc = db.api_keys.find_one({"key": token})
            key_name = key_doc.get("name", "Clave Desconocida") if key_doc else "Clave Desconocida"

        # 2. Construir e insertar el log de auditoría
        total_tokens = (int(prompt_tokens) if prompt_tokens is not None else 0) + (int(completion_tokens) if completion_tokens is not None else 0)
        log_doc = {
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None),
            "ip": ip,
            "api_key_name": key_name,
            "service": service,
            "model": model or service,
            "endpoint": endpoint,
            "prompt_tokens": int(prompt_tokens) if prompt_tokens is not None else 0,
            "completion_tokens": int(completion_tokens) if completion_tokens is not None else 0,
            "audio_duration_sec": float(audio_duration_sec) if audio_duration_sec is not None else 0.0,
            "duration_sec": float(duration_sec) if duration_sec is not None else 0.0
        }
        db.usage_logs.insert_one(log_doc)

        # 3. Incrementar el contador atómico de tokens consumidos en la clave API de forma desacoplada
        if token != MASTER_KEY and total_tokens > 0:
            db.api_keys.update_one({"key": token}, {"$inc": {"used_tokens": total_tokens}})

        print(f"📊 Telemetría: Registro de uso guardado para '{service}' ({key_name}) - Modelo: {model} - Tokens: {total_tokens}", flush=True)
    except Exception as e:
        print(f"⚠️ Error al guardar telemetría de uso en MongoDB: {e}", file=sys.stderr, flush=True)
