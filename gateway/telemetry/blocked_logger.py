import sys
from datetime import datetime, timezone
from pymongo import MongoClient
from config import get_mongo_uri, MONGO_DB


def get_db():
    client = MongoClient(get_mongo_uri(), serverSelectionTimeoutMS=1000)
    return client[MONGO_DB]


def save_blocked_request_log(ip: str, service: str, endpoint: str, reason: str):
    """
    Función síncrona para guardar bloqueos de seguridad en MongoDB en un hilo de fondo.
    """
    try:
        db = get_db()
        log_doc = {
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None),
            "ip": ip,
            "service": service,
            "endpoint": endpoint or "/",
            "reason": reason
        }
        db.blocked_requests.insert_one(log_doc)
        print(f"🛡️ Seguridad: Intento de acceso bloqueado registrado para {ip} en servicio {service} ({reason})", flush=True)
    except Exception as e:
        print(f"⚠️ Error al guardar telemetría de seguridad en MongoDB: {e}", file=sys.stderr, flush=True)
