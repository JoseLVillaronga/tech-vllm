import time
import sys
import asyncio
from datetime import datetime, timedelta
from config import get_mongo_uri, MONGO_DB
from pymongo import MongoClient

# Control de intrusión (Fail2ban nativo en memoria)
failed_attempts = {}
failed_attempts_lock = asyncio.Lock()


def get_db():
    client = MongoClient(get_mongo_uri(), serverSelectionTimeoutMS=1000)
    return client[MONGO_DB]


async def register_failed_attempt(client_ip: str):
    """
    Registra un intento de acceso no autorizado y aplica baneo automático
    de 48 horas en MongoDB si se acumulan 3 fallos en una ventana de 5 minutos.
    """
    now = time.time()
    async with failed_attempts_lock:
        history = failed_attempts.get(client_ip, [])
        # Filtrar intentos dentro de la ventana de 5 minutos (300 segundos)
        history = [t for t in history if now - t < 300]
        history.append(now)
        failed_attempts[client_ip] = history

        if len(history) >= 3:
            # Bloquear automáticamente en MongoDB por 48 horas
            try:
                db = get_db()
                ban_until = datetime.utcnow() + timedelta(hours=48)
                db.ip_rules.update_one(
                    {"network": client_ip},
                    {
                        "$set": {
                            "network": client_ip,
                            "action": "blacklist",
                            "description": "Auto-ban Fail2ban (3 intentos fallidos)",
                            "is_active": True,
                            "created_at": datetime.utcnow(),
                            "expires_at": ban_until
                        }
                    },
                    upsert=True
                )
                print(f"🚨 Fail2ban: IP {client_ip} bloqueada automáticamente por 48 horas tras 3 fallos en 5 minutos.", file=sys.stderr, flush=True)
                # Limpiar historial para evitar re-bloqueos en bucle
                failed_attempts.pop(client_ip, None)
            except Exception as ban_err:
                print(f"⚠️ Error aplicando regla de auto-ban en MongoDB para {client_ip}: {ban_err}", file=sys.stderr, flush=True)
